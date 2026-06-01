"""Inverted ``xref_iri -> name`` label maps for external/component IRIs.

Phase 8 infrastructure (Plan 08-01). This module is the one genuinely-new
design element of the external-IRI labeling phase: it turns the pipeline's
already-built, already-trusted in-memory dicts (``geneiddict`` + ``symbol_lookup``
for genes, ``chedict`` for chemicals) into two byte-stable inverted maps keyed by
the EXACT prefixed xref IRI strings the writer iterates (``chebi:1234``,
``ncbigene:7157``, ``cas:80-05-7``, ``uniprot:P04637``, ``inchikey:...``,
``comptox:...``, ...). The writer (Plan 08-02) consumes these maps by its loop
variable to co-locate a single untagged ``rdfs:label`` with each ``dc:source``.

Design invariants (see 08-PATTERNS.md Pattern 3 and the 08-01 plan):

* **No network (LABEL-02 / D-01).** Labels come ONLY from the passed in-memory
  dicts. This module must never import ``requests`` or call BridgeDb. BridgeDb
  responses carry identifiers only -- never names -- so there is nothing to read
  there even if we wanted to.
* **Deterministic collision tiebreak (D-03).** Many source genes/chemicals can
  carry the same xref IRI (the collision surface). When two candidate names
  compete for one IRI, the alphabetically-FIRST name wins, and that winner is
  independent of dict insertion order. The builders iterate ``sorted(...)`` and
  apply ``if iri not in m or name < m[iri]: m[iri] = name`` so the result is
  byte-stable for the same (iri, candidate) multiset.
* **Exact prefixed keys.** Map keys are the prefixed IRI strings exactly as the
  writer emits/loops them, so a writer ``for chebi in listofchebi:`` can do
  ``chem_label_by_iri.get(chebi)`` directly.

This plan deliberately produces NO ``rdfs:label`` triples itself -- it produces
the data structures and the coverage report the writer reads.
"""

import json
import logging

logger = logging.getLogger(__name__)


# Chemical xref keys on chedict that hold LISTS of prefixed IRIs (BridgeDb
# cross-references). Mirrors chemical_mapper._DB_KEY_TO_LIST -- kept local so this
# module stays import-free of the mapper (and thus of requests).
_CHEM_LIST_KEYS = (
    "cheminf:000407",  # ChEBI
    "cheminf:000405",  # ChemSpider
    "cheminf:000567",  # Wikidata
    "cheminf:000412",  # ChEMBL
    "cheminf:000140",  # PubChem
    "cheminf:000406",  # DrugBank
    "cheminf:000409",  # KEGG
    "cheminf:000564",  # LIPID MAPS
    "cheminf:000408",  # HMDB
)

# Chemical xref keys on chedict that hold a SINGLE prefixed IRI string.
#   dc:identifier   -> 'cas:80-05-7'        (CAS)
#   cheminf:000059  -> 'inchikey:...'       (InChIKey)
#   cheminf:000568  -> 'comptox:...'        (CompTox / DSSTox)
# dc:identifier may also hold a quoted NOCAS literal ('"NOCAS-..."') for
# CAS-less chemicals; those are not xref IRIs and carry no ``:``-prefix scheme,
# so they are skipped below.
_CHEM_SINGLE_KEYS = (
    "dc:identifier",
    "cheminf:000059",
    "cheminf:000568",
)


def _assign(label_map, iri, name):
    """Apply the alphabetically-first collision tiebreak (D-03).

    Only overwrite an existing label when *name* sorts strictly before it, so
    the winner is independent of iteration/insertion order.
    """
    if iri not in label_map or name < label_map[iri]:
        label_map[iri] = name


def build_gene_label_map(geneiddict, symbol_lookup):
    """Build ``{gene_xref_iri: hgnc_symbol}`` from gene cross-reference data.

    Parameters
    ----------
    geneiddict:
        ``{hgnc_key: [xref_iri, ...]}`` where *hgnc_key* is ``'hgnc:<numeric>'``
        (e.g. ``'hgnc:1100'``) and the value is the list of prefixed cross-
        reference IRIs for that gene (``['ncbigene:672', 'uniprot:P38398', ...]``).
        Built by ``gene_mapper.build_gene_xrefs``.
    symbol_lookup:
        ``{numeric_id: symbol}`` (e.g. ``{'1100': 'BRCA1'}``). Built by
        ``gene_mapper.build_gene_dicts``. The human symbol for ``hgnc:1100`` is
        ``symbol_lookup['1100']``; if absent we fall back to the numeric id.

    Returns
    -------
    dict
        ``{xref_iri: symbol}`` keyed by the exact prefixed xref IRI strings the
        writer iterates, with the alphabetically-first symbol winning any
        collision. Deterministic and network-free.
    """
    label_map: dict[str, str] = {}
    for hgnc_key, xref_iris in sorted(geneiddict.items()):
        # hgnc_key is 'hgnc:<numeric>'; the symbol lives under the numeric id.
        symbol = symbol_lookup.get(hgnc_key[5:], hgnc_key[5:])
        for iri in xref_iris:
            _assign(label_map, iri, symbol)
    return label_map


def _bare_title(raw_title):
    """Strip the surrounding quotes from an already-quoted ``dc:title``.

    Chemical ``dc:title`` values are stored already-quoted as ``'"Name"'`` by the
    XML parser (xml_parser.py). Strip exactly one surrounding pair of double
    quotes to recover the bare name; leave any inner characters untouched
    (Turtle-literal escaping is the emission boundary's job in Plan 08-02 --
    T-08-01 keeps the map value byte-faithful to source here).
    """
    if (
        isinstance(raw_title, str)
        and len(raw_title) >= 2
        and raw_title[0] == '"'
        and raw_title[-1] == '"'
    ):
        return raw_title[1:-1]
    return raw_title


def build_chem_label_map(chedict):
    """Build ``{chem_xref_iri: chemical_name}`` from the chemical dict.

    Parameters
    ----------
    chedict:
        ``{chem_id: properties}``. Each chemical may carry a ``dc:title`` (the
        preferred name, stored already-quoted as ``'"Name"'``), list-valued
        BridgeDb cross-references under the ``cheminf:*`` keys in
        :data:`_CHEM_LIST_KEYS`, and single-string xref IRIs (CAS / InChIKey /
        CompTox) under the keys in :data:`_CHEM_SINGLE_KEYS`.

    Returns
    -------
    dict
        ``{xref_iri: name}`` keyed by the exact prefixed xref IRI strings the
        writer iterates (``chebi:...``, ``cas:...``, ``inchikey:...``, ...) with
        the alphabetically-first name winning any collision (many chemicals can
        share one CAS -> many can carry the same xref IRI). Deterministic and
        network-free.
    """
    label_map: dict[str, str] = {}
    # sorted() over chem ids makes the iteration deterministic; the tiebreak in
    # _assign makes the winner independent of order regardless, but sorting keeps
    # the traversal itself reproducible.
    for _chem_id, props in sorted(chedict.items()):
        raw_title = props.get("dc:title")
        if raw_title is None:
            continue
        name = _bare_title(raw_title)
        if not name:
            continue

        # List-valued BridgeDb cross-references.
        for db_key in _CHEM_LIST_KEYS:
            for iri in props.get(db_key, []) or []:
                _assign(label_map, iri, name)

        # Single-string xref IRIs (CAS / InChIKey / CompTox).
        for db_key in _CHEM_SINGLE_KEYS:
            iri = props.get(db_key)
            # Only map genuine prefixed xref IRIs; skip quoted NOCAS literals
            # (which start with '"') and any missing values.
            if isinstance(iri, str) and iri and not iri.startswith('"'):
                _assign(label_map, iri, name)

    return label_map


# Per-source classification of an xref IRI by its prefix scheme, for the
# coverage report (D-07). The order here is the report's per-source iteration
# order; "source" labels mirror the writer's dc:source strings where practical.
_SOURCE_BY_PREFIX = (
    ("chebi:", "ChEBI"),
    ("ncbigene:", "NCBIGene"),
    ("uniprot:", "UniProt"),
    ("ensembl:", "Ensembl"),
    ("cas:", "CAS"),
    ("inchikey:", "InChIKey"),
    ("comptox:", "CompTox"),
    ("chemspider:", "ChemSpider"),
    ("wikidata:", "Wikidata"),
    ("chembl.compound:", "ChEMBL"),
    ("pubchem.compound:", "PubChem"),
    ("drugbank:", "DrugBank"),
    ("kegg.compound:", "KEGG"),
    ("lipidmaps:", "LIPID MAPS"),
    ("hmdb:", "HMDB"),
)


def _source_for_iri(iri):
    """Classify a prefixed xref IRI to its source-DB bucket; 'Other' if unknown."""
    for prefix, source in _SOURCE_BY_PREFIX:
        if iri.startswith(prefix):
            return source
    return "Other"


def report_label_coverage(all_iris_by_source, label_map_combined, *, report_path):
    """Report how many external xref IRIs received a label vs not (D-02 / D-07).

    Mirrors ``ner_el_mapper.report_cache_coverage`` (same dict-return + sorted
    miss list + one INFO summary line + a single INFO miss line truncated to the
    first 50 with ``(+N more)``), and ADDITIONALLY writes the returned dict as
    JSON to *report_path* (the BERN2 probe does NOT write a file; D-07 wants the
    honest artifact). The unlabeled list is the honest record: opaque IRIs with
    no name are recorded, never silently dropped.

    Parameters
    ----------
    all_iris_by_source:
        Iterable of per-source IRI lists (e.g. ``[listofchebi, listofcas, ...]``)
        OR a flat iterable of IRIs. Each IRI is bucketed by its prefix scheme.
    label_map_combined:
        The merged ``{xref_iri: name}`` map (gene + chem). An IRI is "labeled"
        iff it is a key in this map.
    report_path:
        Filesystem path for the JSON artifact (e.g.
        ``data/label-coverage-report.json``).

    Returns
    -------
    dict
        ``{"per_source": {src: {"labeled": int, "unlabeled": int}},
           "unlabeled_iris": [sorted opaque IRIs]}``. Byte-stable for the same
        inputs (``unlabeled_iris`` is sorted; the JSON is written sorted-keyed).
    """
    # Accept either a list-of-lists or a flat iterable of IRIs.
    all_iris: list[str] = []
    for item in all_iris_by_source:
        if isinstance(item, str):
            all_iris.append(item)
        else:
            all_iris.extend(item)

    per_source: dict[str, dict[str, int]] = {}
    unlabeled_iris: list[str] = []
    total = 0
    labeled = 0

    for iri in all_iris:
        source = _source_for_iri(iri)
        bucket = per_source.setdefault(source, {"labeled": 0, "unlabeled": 0})
        total += 1
        if iri in label_map_combined:
            bucket["labeled"] += 1
            labeled += 1
        else:
            bucket["unlabeled"] += 1
            unlabeled_iris.append(iri)

    unlabeled_iris.sort()
    n_unlabeled = len(unlabeled_iris)
    pct = (100.0 * labeled / total) if total else 0.0
    logger.info(
        "IRI label coverage: %d/%d (%.1f%%); %d unlabeled",
        labeled, total, pct, n_unlabeled,
    )
    if unlabeled_iris:
        head = unlabeled_iris[:50]
        suffix = f" (+{n_unlabeled - len(head)} more)" if n_unlabeled > len(head) else ""
        logger.info("Unlabeled IRIs: %s%s", ", ".join(head), suffix)

    result = {"per_source": per_source, "unlabeled_iris": unlabeled_iris}

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return result


# Chemical per-source IRI list keys on chem_result, and gene per-source IRI list
# keys on xref_result, used to assemble the coverage report's per-source buckets.
_CHEM_RESULT_LIST_KEYS = (
    "listofchebi",
    "listofchemspider",
    "listofwikidata",
    "listofchembl",
    "listofpubchem",
    "listofdrugbank",
    "listofkegg",
    "listoflipidmaps",
    "listofhmdb",
)
_GENE_RESULT_LIST_KEYS = ("listofentrez", "listofensembl", "listofuniprot")


def report_label_coverage_from_results(
    chem_result, xref_result, chem_label_by_iri, gene_label_by_iri, *, report_path
):
    """Assemble per-source IRI lists from the pipeline results and report coverage.

    Thin orchestration wrapper around :func:`report_label_coverage` so the
    pipeline stays a thin orchestrator: it gathers the chemical and gene xref
    list-of-IRIs from *chem_result* / *xref_result*, merges the two label maps,
    and delegates. Returns the coverage dict.
    """
    combined = {**chem_label_by_iri, **gene_label_by_iri}
    per_source_iri_lists = [chem_result.get(k, []) for k in _CHEM_RESULT_LIST_KEYS]
    per_source_iri_lists += [xref_result.get(k, []) for k in _GENE_RESULT_LIST_KEYS]
    return report_label_coverage(
        per_source_iri_lists, combined, report_path=report_path
    )
