"""Shared BridgeDb batch client for gene and chemical cross-references.

Extracted from pipeline.py:
- Gene batch xrefs (lines 1992-2105)
- Chemical batch xrefs (lines 513-772)

Both gene and chemical mappings share the same pattern: chunk identifiers,
POST to BridgeDb xrefsBatch endpoint, parse response, fallback to individual
calls on failure. The generic ``batch_xrefs`` function captures that pattern;
``batch_xrefs_gene`` and ``batch_xrefs_chemical`` provide domain wrappers.
"""

import logging
from typing import Callable

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System code mappings
# ---------------------------------------------------------------------------

GENE_SYSTEM_CODES: dict[str, str] = {
    "L": "Entrez Gene",
    "En": "Ensembl",
    "S": "Uniprot-TrEMBL",
    "H": "HGNC",
    "X": "Affy",
    "T": "GeneOntology",
    "Pd": "PDB",
    "Q": "RefSeq",
    "Om": "OMIM",
    "Uc": "UCSC Genome Browser",
    "Wg": "WikiGenes",
    "Ag": "Agilent",
    "Il": "Illumina",
    "Hac": "HGNC Accession number",
}

CHEMICAL_SYSTEM_CODES: dict[str, str | None] = {
    "Ca": None,  # CAS -- handled separately as dc:identifier
    "Ce": "cheminf:000407",  # ChEBI
    "Cs": "cheminf:000405",  # ChemSpider
    "Cl": "cheminf:000412",  # ChEMBL compound
    "Dr": "cheminf:000406",  # DrugBank
    "Ch": "cheminf:000408",  # HMDB
    "Ck": "cheminf:000409",  # KEGG Compound
    "Kd": "cheminf:000409",  # KEGG Drug (mapped to kegg.compound namespace)
    "Lm": "cheminf:000564",  # LIPID MAPS
    "Cpc": "cheminf:000140",  # PubChem Compound
    "Wd": "cheminf:000567",  # Wikidata
}

# Namespace prefixes used when formatting chemical identifiers.
_CHEMICAL_NS: dict[str, str] = {
    "Ce": "chebi",
    "Cs": "chemspider",
    "Cl": "chembl.compound",
    "Dr": "drugbank",
    "Ch": "hmdb",
    "Ck": "kegg.compound",
    "Kd": "kegg.compound",
    "Lm": "lipidmaps",
    "Cpc": "pubchem.compound",
    "Wd": "wikidata",
}

# Database name mapping used by the individual-call chemical fallback.
_CHEMICAL_DB_NAME_MAP: dict[str, str] = {
    "Chemspider": "cheminf:000405",
    "HMDB": "cheminf:000408",
    "DrugBank": "cheminf:000406",
    "ChEBI": "cheminf:000407",
    "ChEMBL compound": "cheminf:000412",
    "Wikidata": "cheminf:000567",
    "PubChem-compound": "cheminf:000140",
    "KEGG Compound": "cheminf:000409",
    "LIPID MAPS": "cheminf:000564",
}

# Namespace prefixes keyed by database display name (individual fallback).
_CHEMICAL_DB_NS: dict[str, str] = {
    "Chemspider": "chemspider",
    "HMDB": "hmdb",
    "DrugBank": "drugbank",
    "ChEBI": "chebi",
    "ChEMBL compound": "chembl.compound",
    "Wikidata": "wikidata",
    "PubChem-compound": "pubchem.compound",
    "KEGG Compound": "kegg.compound",
    "LIPID MAPS": "lipidmaps",
}


# ---------------------------------------------------------------------------
# Generic batch helper
# ---------------------------------------------------------------------------

def batch_xrefs(
    identifiers: list[str],
    bridgedb_url: str,
    system_code: str,
    parse_fn: Callable[[str], dict],
    *,
    id_prefix: str | None = None,
    fallback_fn: Callable | None = None,
    chunk_size: int = 100,
    timeout: int = 30,
) -> dict:
    """Generic batch xref lookup via BridgeDb.

    Chunks *identifiers* into groups of *chunk_size*, POSTs each chunk to
    ``{bridgedb_url}/xrefsBatch/{system_code}``, and delegates response
    parsing to *parse_fn*.  On failure, falls back to *fallback_fn* (if
    provided) for the failed chunk.

    Parameters
    ----------
    identifiers:
        Raw identifiers (may include a prefix that must be stripped).
    bridgedb_url:
        Base URL of the BridgeDb Human service (e.g.
        ``https://webservice.bridgedb.org/Human/``).
    system_code:
        BridgeDb system code for the batch endpoint (e.g. ``H``, ``Ca``).
    parse_fn:
        ``(response_text) -> dict`` that converts the raw text response into
        the domain-specific result dictionary.
    id_prefix:
        If set, this prefix is stripped from each identifier before sending
        to the API and re-added to result keys (e.g. ``"hgnc:"``).
    fallback_fn:
        ``(identifier, bridgedb_url, timeout) -> dict`` called per-identifier
        when the batch request fails.
    chunk_size:
        Number of identifiers per batch POST.
    timeout:
        HTTP request timeout in seconds.

    Returns
    -------
    dict
        Merged results from all chunks.
    """
    results: dict = {}
    total_chunks = (len(identifiers) + chunk_size - 1) // chunk_size
    batch_url = bridgedb_url.rstrip("/") + f"/xrefsBatch/{system_code}"
    headers = {"Content-Type": "text/plain"}

    for chunk_idx in range(0, len(identifiers), chunk_size):
        chunk = identifiers[chunk_idx : chunk_idx + chunk_size]
        chunk_num = chunk_idx // chunk_size + 1

        # Strip prefix for the API payload.
        if id_prefix:
            api_ids = [ident[len(id_prefix) :] for ident in chunk]
        else:
            api_ids = list(chunk)

        batch_data = "\n".join(api_ids)

        try:
            logger.debug(
                "BridgeDb batch %d/%d: %d identifiers",
                chunk_num, total_chunks, len(chunk),
            )
            response = requests.post(
                batch_url, data=batch_data, headers=headers, timeout=timeout,
            )
            response.raise_for_status()

            chunk_results = parse_fn(response.text)
            results.update(chunk_results)

        except requests.RequestException as exc:
            logger.warning(
                "BridgeDb batch %d failed, falling back to individual calls: %s",
                chunk_num, exc,
            )
            if fallback_fn is not None:
                for ident in chunk:
                    try:
                        individual = fallback_fn(ident, bridgedb_url, timeout)
                        results[ident] = individual
                    except Exception:
                        logger.warning("Individual fallback also failed for %s", ident)
                        results[ident] = {}
            else:
                for ident in chunk:
                    results[ident] = {}

    return results


# ---------------------------------------------------------------------------
# Gene-specific batch xrefs
# ---------------------------------------------------------------------------

def _parse_gene_batch_response(response_text: str) -> dict:
    """Parse BridgeDb batch response for genes.

    Response format per line::

        GENE_SYMBOL\\tHGNC Symbol\\tL:675,En:ENSG00000139618,S:P51587

    Returns dict mapping ``hgnc:<symbol>`` to ``{db_name: [identifiers]}``.
    """
    results: dict = {}
    for line in response_text.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        gene_symbol = parts[0]
        gene_id = f"hgnc:{gene_symbol}"
        xrefs_str = parts[2]

        if xrefs_str == "N/A":
            results[gene_id] = {}
            continue

        dictionaryforgene: dict[str, list[str]] = {}
        for xref in xrefs_str.split(","):
            if ":" not in xref:
                continue
            system_code, value = xref.split(":", 1)
            db_name = GENE_SYSTEM_CODES.get(system_code)
            if db_name is None:
                continue  # skip unknown system codes
            dictionaryforgene.setdefault(db_name, []).append(value)

        results[gene_id] = dictionaryforgene

    return results


def _gene_individual_fallback(
    gene_id: str, bridgedb_url: str, timeout: int
) -> dict:
    """Fall back to individual GET for a single gene.

    Matches the monolith fallback (lines 2085-2103).
    """
    symbol = gene_id[5:] if gene_id.startswith("hgnc:") else gene_id
    url = bridgedb_url.rstrip("/") + f"/xrefs/H/{symbol}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    dictionaryforgene: dict[str, list[str]] = {}
    for item in response.text.split("\n"):
        b = item.split("\t")
        if len(b) == 2:
            dictionaryforgene.setdefault(b[1], []).append(b[0])
    return dictionaryforgene


def batch_xrefs_gene(
    gene_list: list[str],
    bridgedb_url: str,
    timeout: int = 30,
    chunk_size: int = 100,
) -> dict:
    """Map HGNC IDs to Entrez/Ensembl/UniProt via BridgeDb batch API.

    Parameters
    ----------
    gene_list:
        List of HGNC gene IDs, e.g. ``['hgnc:BRCA2', 'hgnc:BRCA1']``.
    bridgedb_url:
        Base BridgeDb Human service URL.
    timeout:
        HTTP request timeout in seconds.
    chunk_size:
        Number of genes per batch request.

    Returns
    -------
    dict
        ``{gene_id: {db_name: [identifiers]}}``
    """
    logger.info(
        "Starting BridgeDb gene batch mapping for %d genes", len(gene_list),
    )
    return batch_xrefs(
        identifiers=gene_list,
        bridgedb_url=bridgedb_url,
        system_code="H",
        parse_fn=_parse_gene_batch_response,
        id_prefix="hgnc:",
        fallback_fn=_gene_individual_fallback,
        chunk_size=chunk_size,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Chemical-specific batch xrefs
# ---------------------------------------------------------------------------

def parse_batch_chemical_response(response_text: str) -> dict:
    """Parse BridgeDb batch response for chemicals.

    Response format per line::

        CAS_NUMBER\\tCAS\\tCs:id,Ch:id,Dr:id,Ce:id,...

    Returns dict mapping CAS number to ``{cheminf_key: [identifiers]}``.
    """
    results: dict = {}

    for line in response_text.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        cas_number = parts[0]
        xrefs_str = parts[2]

        if xrefs_str == "N/A":
            results[cas_number] = {}
            continue

        chemical_dict: dict[str, list[str]] = {}
        for xref in xrefs_str.split(","):
            if ":" not in xref:
                continue
            system_code, identifier = xref.split(":", 1)

            cheminf_key = CHEMICAL_SYSTEM_CODES.get(system_code)
            if cheminf_key is None:
                # Either explicitly skipped (Ca, Ik) or unsupported code.
                continue

            ns = _CHEMICAL_NS.get(system_code)
            if ns is None:
                continue

            # Special formatting for ChEBI: strip 'CHEBI:' prefix if present.
            if system_code == "Ce":
                identifier = identifier.split("CHEBI:")[-1]

            formatted = f"{ns}:{identifier}"
            chemical_dict.setdefault(cheminf_key, []).append(formatted)

        results[cas_number] = chemical_dict

    return results


def _chemical_individual_fallback(
    cas_number: str, bridgedb_url: str, timeout: int
) -> dict:
    """Fall back to individual GET for a single CAS number.

    Matches the monolith fallback (lines 702-772).
    """
    url = bridgedb_url.rstrip("/") + f"/xrefs/Ca/{cas_number}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    chemical_dict: dict[str, list[str]] = {}
    for line in response.text.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue

        identifier, database = parts
        cheminf_key = _CHEMICAL_DB_NAME_MAP.get(database)
        if cheminf_key is None:
            continue

        ns = _CHEMICAL_DB_NS.get(database)
        if ns is None:
            continue

        # Special formatting for ChEBI
        if database == "ChEBI":
            identifier = identifier.split("CHEBI:")[-1]

        chemical_dict.setdefault(cheminf_key, []).append(f"{ns}:{identifier}")

    return chemical_dict


def batch_xrefs_chemical(
    cas_numbers: list[str],
    bridgedb_url: str,
    timeout: int = 30,
    batch_size: int = 100,
) -> dict:
    """Map CAS numbers to chemical identifiers via BridgeDb batch API.

    Parameters
    ----------
    cas_numbers:
        List of CAS numbers to map.
    bridgedb_url:
        Base BridgeDb Human service URL.
    timeout:
        HTTP request timeout in seconds.
    batch_size:
        Number of chemicals per batch request.

    Returns
    -------
    dict
        ``{cas_number: {cheminf_key: [identifiers]}}``
    """
    logger.info(
        "Starting BridgeDb chemical batch mapping for %d chemicals",
        len(cas_numbers),
    )
    return batch_xrefs(
        identifiers=cas_numbers,
        bridgedb_url=bridgedb_url,
        system_code="Ca",
        parse_fn=parse_batch_chemical_response,
        fallback_fn=_chemical_individual_fallback,
        chunk_size=batch_size,
        timeout=timeout,
    )
