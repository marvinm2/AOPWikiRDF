"""Thin orchestrator for AOP-Wiki XML to RDF conversion pipeline.

Wires extracted modules together in named stages with timing and logging.
Replaces the 2,334-line monolith (preserved as pipeline_monolith.py).
"""

import datetime
import gzip
import logging
import os
import shutil
import stat
import time
from datetime import date
from pathlib import Path
from xml.etree.ElementTree import parse

import requests

from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml, AOPXML_NS
from aopwiki_rdf.hgnc import download_hgnc_data
from aopwiki_rdf.mapping.gene_mapper import build_gene_dicts, map_genes_in_entities, build_gene_xrefs
from aopwiki_rdf.mapping.ner_el_mapper import (
    map_ner_genes_in_kers_result,
    map_ner_genes_in_kes_result,
    union_ner_into_entities,
)
from aopwiki_rdf.mapping.chemical_mapper import map_chemicals
from aopwiki_rdf.mapping.protein_ontology import download_and_parse_promapping
from aopwiki_rdf.rdf.writer import write_aop_rdf, write_enriched_rdf, write_genes_rdf, write_void_rdf

logger = logging.getLogger(__name__)


def _resolve_static_files(config: PipelineConfig) -> None:
    """Ensure static files are available in the data directory."""
    static_files = ["typelabels.txt", "HGNCgenes.txt"]
    search_dirs = [Path("data/"), Path("./"), Path("data-test-local/")]
    config.data_dir.mkdir(parents=True, exist_ok=True)
    for name in static_files:
        dest = config.data_dir / name
        if dest.exists():
            continue
        for sd in search_dirs:
            src = sd / name
            if src.exists():
                logger.info("Copying %s from %s to %s", name, sd, config.data_dir)
                shutil.copy2(str(src), str(dest))
                break
        else:
            logger.warning("Required file %s not found", name)


def _collect(data, key, prefix, target):
    """Append data[key] to target if it starts with prefix."""
    val = data.get(key, "")
    if isinstance(val, str) and val.startswith(prefix):
        target.append(val)


def _download_with_retry(url, filename, timeout=30, max_retries=3):
    """Download a file with retry logic and exponential backoff."""
    for attempt in range(max_retries):
        try:
            logger.info("Downloading %s (attempt %d/%d)", url, attempt + 1, max_retries)
            resp = requests.get(url, verify=False, timeout=timeout)
            resp.raise_for_status()
            with open(filename, "wb") as f:
                f.write(resp.content)
            return True
        except requests.RequestException as e:
            logger.warning("Download attempt %d failed: %s", attempt + 1, e)
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return False


def _count_triples(filepath):
    """Count triples in a Turtle file using rdflib."""
    from rdflib import Graph
    g = Graph()
    g.parse(filepath, format='turtle')
    count = len(g)
    logger.info("Triple count for %s: %d", filepath, count)
    return count


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _stage_setup(config, context):
    """Resolve static files, set up data directory and filepath."""
    _resolve_static_files(config)
    filepath = str(config.data_dir) + "/"
    os.makedirs(filepath, exist_ok=True)
    context["filepath"] = filepath


def _stage_parse(config, context):
    """Download AOP-Wiki XML, extract, and parse into entity dicts."""
    filepath = context["filepath"]
    today = date.today()
    aopwikixmlfilename = f"aop-wiki-xml-{today}"

    # Download
    try:
        _download_with_retry(
            config.aopwiki_xml_url,
            aopwikixmlfilename,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
        )
    except requests.RequestException as e:
        logger.error("Failed to download AOP-Wiki XML: %s", e)
        raise SystemExit(1)

    # Extract gzipped XML
    try:
        with gzip.open(aopwikixmlfilename, "rb") as f_in:
            with open(filepath + aopwikixmlfilename, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        logger.info("Extracted XML to %s", filepath + aopwikixmlfilename)
    except (FileNotFoundError, gzip.BadGzipFile, IOError) as e:
        logger.error("Failed to extract XML file: %s", e)
        raise SystemExit(1)

    xml_path = filepath + aopwikixmlfilename

    # Parse XML to get root for mapping stages
    tree = parse(xml_path)
    xml_root = tree.getroot()
    aopxml_ns = AOPXML_NS

    # Parse entities via the parser module (config=None to skip internal
    # promapping -- we call protein_ontology module separately)
    entities = parse_aopwiki_xml(xml_path, config=None)

    context["entities"] = entities
    context["xml_root"] = xml_root
    context["aopxml_ns"] = aopxml_ns
    context["aopwikixmlfilename"] = aopwikixmlfilename


def _stage_filter_arr_aops(config, context):
    """Optionally drop ARR-licensed AOPs from the aopdict.

    Opt-in via config.filter_arr_aops (default False). The primary licence
    mechanism is per-AOP dcterms:license emission in the writer; this stage
    is a defensive filter for strict CC-BY-SA-only release builds.
    Scope is AOP-only -- KEs/KERs/Stressors are kept regardless, since
    upstream asserts licence at AOP level only.
    """
    if not config.filter_arr_aops:
        return
    entities = context["entities"]
    aopdict = entities.aopdict
    arr_ids = [aop_id for aop_id, aop in aopdict.items()
               if aop.get("_wiki_license") == "ARR"]
    for aop_id in arr_ids:
        del aopdict[aop_id]
    logger.info(
        "Filtered %d ARR-licensed AOPs (%d remaining)",
        len(arr_ids), len(aopdict),
    )


def _stage_chemicals(config, context):
    """Map chemicals via BridgeDb batch API."""
    entities = context["entities"]
    xml_root = context["xml_root"]
    aopxml_ns = context["aopxml_ns"]

    chem_result = map_chemicals(
        entities.chemicaldict,
        xml_root,
        aopxml_ns,
        bridgedb_url=config.bridgedb_url,
        timeout=config.request_timeout,
    )
    context["chemical_result"] = chem_result


def _stage_protein_ontology(config, context):
    """Download promapping.txt and parse protein-to-identifier mappings."""
    entities = context["entities"]

    # Build prolist from biological objects that have PR identifiers
    prolist = []
    for bo_id, bo_data in entities.bodict.items():
        if bo_id is None:
            continue
        identifier = bo_data.get("dc:identifier", "")
        if isinstance(identifier, str) and identifier.startswith("pr:"):
            prolist.append(identifier)

    if not prolist:
        logger.info("No Protein Ontology terms found; skipping promapping")
        context["pro_result"] = {
            "prodict": {},
            "pro_hgnclist": [],
            "pro_uniprotlist": [],
            "pro_ncbigenelist": [],
            "modification_time": "N/A",
        }
        return

    pro_result = download_and_parse_promapping(
        promapping_url=config.promapping_url,
        data_dir=config.data_dir,
        prolist=prolist,
    )
    context["pro_result"] = pro_result


def _apply_bern2_enrichment(kedict, kerdict, gene_hgnclist, config):
    """Union BERN2 NER+EL gene detections into the regex gene mapping.

    Mutates ``kedict``, ``kerdict``, and ``gene_hgnclist`` in place:

    - Each KE/KER touched gets ``_genes_regex`` and ``_genes_ner`` lists
      recording per-method provenance for the writer.
    - ``edam:data_1025`` becomes the union (regex order preserved,
      NER-only IDs appended sorted).
    - ``gene_hgnclist`` is extended with BERN2-discovered HGNC IDs so they
      flow through BridgeDb cross-referencing and gene-identifier triples.

    Graceful degradation (NER-04): when BERN2 *fails* for a KE description
    (the hosted API is unreachable / all retries exhausted), and
    ``config.ner_fallback_on_failure`` is True, that KE keeps the regex genes
    already in ``edam:data_1025`` -- they are NEVER thinned or emptied. The KE
    is flagged ``_ner_degraded`` for audit, ``_genes_ner`` is left empty, and a
    per-run ``degraded`` counter is incremented. After the loop, if any KE
    degraded, a single loud ``logger.error`` line is emitted plus an INFO
    coverage metric. A successful-but-empty BERN2 result is NOT a failure and
    follows the normal additive union path.

    BERN2 now covers BOTH KEs and KERs (D-08). KER NER scans three text fields
    (``dc:description`` + ``nci:C80263`` + ``edam:data_2042``) for method
    parity with regex; each KER's ``edam:data_1025`` becomes the regex union
    NER union, with the same graceful-degradation guarantee as KEs (a BERN2
    KER outage falls back to the regex genes, never thins them). This whole
    function only runs when ``config.enable_bern2`` is True, so it is inert in
    the default production run.
    """
    existing_hgnc = set(gene_hgnclist)

    # KE branch: union BERN2 NER detections into KE gene mappings.
    ner_results = map_ner_genes_in_kes_result(kedict, config)
    ok, degraded, skipped = union_ner_into_entities(
        kedict, ner_results, gene_hgnclist, existing_hgnc,
        fallback_on_failure=config.ner_fallback_on_failure,
    )
    # The three buckets partition kedict exactly (WR-03): total is the number
    # of KEs considered, not just ok + degraded. "skipped" are KEs the mapper
    # returned no NER result for (e.g. blank/unscanned descriptions).
    total = len(kedict)
    assert ok + degraded + skipped == total, (
        f"KE NER bucket invariant violated: {ok}+{degraded}+{skipped} != {total}"
    )
    if degraded > 0:
        logger.error(
            "BERN2 degraded for %d/%d KE descriptions; fell back to regex "
            "(canonical gene coverage preserved)",
            degraded, total,
        )
    logger.info(
        "BERN2 enrichment coverage: %d ok, %d degraded, %d skipped, %d total",
        ok, degraded, skipped, total,
    )

    # KER branch (D-08): mirror the KE union via the same shared helper. KER
    # NER scans three text fields (dc:description + nci:C80263 + edam:data_2042)
    # for method parity with regex; each KER's edam:data_1025 becomes the regex
    # union NER union, with NER-detected genes populating :geneDetectedByNER on
    # the KER subject (the writer emits it automatically whenever _genes_ner is
    # set).
    ker_ner_results = map_ner_genes_in_kers_result(kerdict, config)
    ker_ok, ker_degraded, ker_skipped = union_ner_into_entities(
        kerdict, ker_ner_results, gene_hgnclist, existing_hgnc,
        fallback_on_failure=config.ner_fallback_on_failure,
    )
    # WR-03: KERs without NER text are common (map_ner_genes_in_kers_result only
    # returns entries for KERs with text), so most KERs land in "skipped".
    # Reporting total as len(kerdict) keeps the coverage metric honest.
    ker_total = len(kerdict)
    assert ker_ok + ker_degraded + ker_skipped == ker_total, (
        f"KER NER bucket invariant violated: "
        f"{ker_ok}+{ker_degraded}+{ker_skipped} != {ker_total}"
    )
    if ker_degraded > 0:
        logger.error(
            "BERN2 degraded for %d/%d KER descriptions; fell back to regex "
            "(canonical gene coverage preserved)",
            ker_degraded, ker_total,
        )
    logger.info(
        "BERN2 KER enrichment coverage: %d ok, %d degraded, %d skipped, %d total",
        ker_ok, ker_degraded, ker_skipped, ker_total,
    )


def _stage_gene_mapping(config, context):
    """Download HGNC data, build gene dicts, map genes, build xrefs."""
    entities = context["entities"]
    xml_root = context["xml_root"]
    aopxml_ns = context["aopxml_ns"]

    # Download HGNC data
    hgnc_cache_path = config.data_dir / "HGNCgenes.txt"
    _hgnc_content = download_hgnc_data(
        url=config.hgnc_download_url,
        cache_path=hgnc_cache_path,
        timeout=config.request_timeout,
        max_retries=config.max_retries,
        min_genes=config.hgnc_min_genes,
    )

    # Get HGNC file modification time
    hgnc_filepath = str(config.data_dir) + "/HGNCgenes.txt"
    try:
        file_stats = os.stat(hgnc_filepath)
        hgnc_mod_time = time.ctime(file_stats[stat.ST_MTIME])
    except OSError:
        hgnc_mod_time = "Unknown"
    logger.info("HGNC data last modified: %s", hgnc_mod_time)

    # Build gene dictionaries
    genedict1, genedict2, symbol_lookup = build_gene_dicts(hgnc_filepath)

    # Map genes in KE/KER text
    kedict, kerdict, gene_hgnclist = map_genes_in_entities(
        entities.kedict,
        entities.kerdict,
        genedict1,
        genedict2,
        xml_root,
        aopxml_ns,
    )

    # Optional BERN2 NER+EL enrichment (Phase B). When config.enable_bern2
    # is True, BERN2 scans KE descriptions for descriptive-name gene
    # mentions regex cannot match. Results are unioned into edam:data_1025
    # and the per-method provenance is recorded in _genes_regex/_genes_ner
    # for the writer to emit as :geneDetectedByRegex / :geneDetectedByNER.
    if config.enable_bern2:
        _apply_bern2_enrichment(kedict, kerdict, gene_hgnclist, config)

    # Build cross-references via BridgeDb (gene_hgnclist now includes any
    # BERN2-discovered HGNC IDs appended by _apply_bern2_enrichment)
    xref_result = build_gene_xrefs(
        gene_hgnclist,
        bridgedb_url=config.bridgedb_url,
        timeout=config.request_timeout,
        symbol_lookup=symbol_lookup,
    )

    context["gene_kedict"] = kedict
    context["gene_kerdict"] = kerdict
    context["gene_hgnclist"] = gene_hgnclist
    context["gene_xref_result"] = xref_result
    context["hgnc_modification_time"] = hgnc_mod_time
    context["gene_symbol_lookup"] = symbol_lookup


def _stage_write_aop_rdf(config, context):
    """Write AOPWikiRDF.ttl from assembled entity data."""
    filepath = context["filepath"]
    entities = context["entities"]
    pro_result = context["pro_result"]
    chem_result = context["chemical_result"]

    # Extract chemical identifier lists from chedict properties
    chedict = chem_result["chedict"]
    listofcas, listofinchikey, listofcomptox = [], [], []
    for chem_data in chedict.values():
        _collect(chem_data, "dc:identifier", "cas:", listofcas)
        _collect(chem_data, "cheminf:000059", "inchikey:", listofinchikey)
        _collect(chem_data, "cheminf:000568", "comptox:", listofcomptox)

    # Assemble entities dict for the writer (maps ParsedEntities names to writer keys)
    writer_entities = {
        "aopdict": entities.aopdict, "kedict": entities.kedict,
        "kerdict": entities.kerdict, "strdict": entities.stressordict,
        "chedict": chedict, "taxdict": entities.taxdict,
        "bioobjdict": entities.bodict, "bioprodict": entities.bpdict,
        "bioactdict": entities.badict,
        "prodict": pro_result["prodict"],
        "hgnclist": pro_result["pro_hgnclist"],
        "ncbigenelist": pro_result["pro_ncbigenelist"],
        "uniprotlist": pro_result["pro_uniprotlist"],
        "listofcas": listofcas, "listofinchikey": listofinchikey,
        "listofcomptox": listofcomptox,
    }
    # Add BridgeDb chemical identifier lists
    for key in ("listofchebi", "listofchemspider", "listofchembl", "listofdrugbank",
                "listofhmdb", "listofkegg", "listoflipidmaps", "listofpubchem",
                "listofwikidata"):
        writer_entities[key] = chem_result.get(key, [])

    # Pass symbol_lookup for gene rdfs:label in main RDF
    writer_entities["symbol_lookup"] = context.get("gene_symbol_lookup", {})

    prefix_csv = "prefixes.csv"
    write_aop_rdf(filepath + "AOPWikiRDF.ttl", writer_entities, prefix_csv, config=config)
    context["triple_count_main"] = _count_triples(filepath + "AOPWikiRDF.ttl")
    logger.info("RDF file created: %sAOPWikiRDF.ttl", filepath)


def _stage_write_enriched_rdf(config, context):
    """Write AOPWikiRDF-Enriched.ttl with cross-reference triples."""
    filepath = context["filepath"]
    entities = context["entities"]
    pro_result = context["pro_result"]
    chem_result = context["chemical_result"]

    enrichment_data = {
        "chedict": chem_result["chedict"],
        "bioobjdict": entities.bodict,
        "prodict": pro_result["prodict"],
    }

    write_enriched_rdf(filepath + "AOPWikiRDF-Enriched.ttl", enrichment_data, config=config)
    context["triple_count_enriched"] = _count_triples(filepath + "AOPWikiRDF-Enriched.ttl")


def _stage_write_genes_rdf(config, context):
    """Write AOPWikiRDF-Genes.ttl from gene mapping results."""
    filepath = context["filepath"]
    xref_result = context["gene_xref_result"]

    gene_data = {
        "kedict": context["gene_kedict"],
        "kerdict": context["gene_kerdict"],
        "hgnclist": context["gene_hgnclist"],
        "geneiddict": xref_result["geneiddict"],
        "listofentrez": xref_result["listofentrez"],
        "listofensembl": xref_result["listofensembl"],
        "listofuniprot": xref_result["listofuniprot"],
        "symbol_lookup": context.get("gene_symbol_lookup", {}),
    }

    write_genes_rdf(filepath + "AOPWikiRDF-Genes.ttl", gene_data, config=config)
    context["triple_count_genes"] = _count_triples(filepath + "AOPWikiRDF-Genes.ttl")


def _stage_write_void_rdf(config, context):
    """Write AOPWikiRDF-Void.ttl with provenance metadata."""
    filepath = context["filepath"]
    aopwikixmlfilename = context["aopwikixmlfilename"]
    pro_result = context["pro_result"]

    # BridgeDb properties for VoID metadata
    try:
        response = requests.get(
            config.bridgedb_url + "properties",
            timeout=config.request_timeout,
        )
        response.raise_for_status()
        lines = response.text.split("\n")
    except requests.RequestException as e:
        logger.warning("BridgeDb properties request failed: %s", e)
        lines = []

    info = {}
    for item in lines:
        parts = item.split("\t")
        # Only ``key\tvalue`` rows are meaningful. Blank lines, HTML error
        # pages, or any unexpected response shape (which split to a single
        # field) are skipped so they never pollute ``info`` with an
        # empty-string key or a key holding an empty value list.
        if len(parts) != 2:
            continue
        if parts[0] not in info:
            info[parts[0]] = []
        info[parts[0]].append(parts[1])

    if "DATASOURCENAME" in info and "DATASOURCEVERSION" in info:
        names, versions = info["DATASOURCENAME"], info["DATASOURCEVERSION"]
        logger.info(
            "BridgeDb versions - Gene/Proteins: %s:%s, Chemicals: %s:%s",
            names[0] if names else "?",
            versions[0] if versions else "?",
            names[5] if len(names) > 5 else "?",
            versions[5] if len(versions) > 5 else "?",
        )

    now = datetime.datetime.now()

    metadata = {
        "aopwikixmlfilename": aopwikixmlfilename,
        "date": str(now)[:10],
        "datetime_obj": now,
        "HGNCmodificationTime": context.get("hgnc_modification_time", "Unknown"),
        "PromodificationTime": pro_result.get("modification_time", "Unknown"),
        "service_desc_filepath": filepath + "ServiceDescription.ttl",
    }

    metadata["triple_counts"] = {
        "main": context.get("triple_count_main", 0),
        "enriched": context.get("triple_count_enriched", 0),
        "genes": context.get("triple_count_genes", 0),
    }
    metadata["bridgedb_url"] = config.bridgedb_url

    write_void_rdf(filepath + "AOPWikiRDF-Void.ttl", metadata)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

STAGES = [
    ("Setup & Static Files", _stage_setup),
    ("XML Download & Parse", _stage_parse),
    ("Filter ARR-licensed AOPs", _stage_filter_arr_aops),
    ("Chemical Mapping", _stage_chemicals),
    ("Protein Ontology Mapping", _stage_protein_ontology),
    ("HGNC Gene Mapping", _stage_gene_mapping),
    ("Write Main RDF", _stage_write_aop_rdf),
    ("Write Enriched RDF", _stage_write_enriched_rdf),
    ("Write Genes RDF", _stage_write_genes_rdf),
    ("Write VoID RDF", _stage_write_void_rdf),
]


def main(config: PipelineConfig | None = None) -> None:
    """Run the full AOP-Wiki XML to RDF conversion pipeline.

    Parameters
    ----------
    config : PipelineConfig, optional
        Pipeline configuration. Uses defaults if not provided.
    """
    if config is None:
        config = PipelineConfig()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("aop_conversion.log"),
        ],
    )

    logger.info("Starting AOP-Wiki RDF pipeline")
    logger.info(
        "Configuration: data_dir=%s, log_level=%s", config.data_dir, config.log_level
    )

    pipeline_start = time.time()
    context: dict = {}

    for stage_name, stage_fn in STAGES:
        t0 = time.time()
        logger.info("Stage: %s -- starting", stage_name)
        stage_fn(config, context)
        elapsed = time.time() - t0
        logger.info("Stage: %s -- completed in %.1fs", stage_name, elapsed)

    total_elapsed = time.time() - pipeline_start
    logger.info("AOP-Wiki RDF pipeline completed successfully in %.1fs", total_elapsed)
