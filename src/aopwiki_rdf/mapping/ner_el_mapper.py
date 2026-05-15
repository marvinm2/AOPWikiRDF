"""BERN2 NER+EL gene mapper.

Production module that closes the entity-normalisation gap Phase 5-04 surfaced.
Detects gene mentions in free text via the BERN2 hosted API (DMIS-Lab NER+EL),
which emits NCBI Gene IDs, then maps NCBI Gene -> HGNC via BridgeDb. Both
hops are cached on disk per call so re-runs amortise the network cost.

The module is library-shaped (no pipeline integration yet) -- Phase A of the
productionisation lays down the code with `PipelineConfig.enable_bern2`
defaulting False. Phase B wires this into the orchestrator alongside the
existing regex `gene_mapper`.

Feasibility evidence: `prototypes/ner_el_spike/REPORT.md` (May 2026 spike).
"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

# Default chunk size for the JSON-truncation fallback. Empirically, BERN2's
# hosted API returns truncated JSON past ~5170 characters of response. Splitting
# the input at sentence boundaries keeps each call's response well under that.
_BERN2_CHUNK_CHARS = 1500


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(text: str) -> str:
    """Deterministic 12-char filename component for arbitrary input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _read_json_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Corrupt cache file %s; deleting", path)
        path.unlink()
        return None


def _write_json_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# BERN2 client
# ---------------------------------------------------------------------------

def _loads_bern2(response_text: str) -> dict:
    """Parse a BERN2 response body into a dict.

    BERN2 emits bare ``NaN`` for the ``prob`` field of neural-normalised
    entities. ``NaN`` is not valid JSON, so ``requests.Response.json()``
    rejects it outright. Parsing with an explicit ``parse_constant`` maps
    ``NaN`` / ``Infinity`` / ``-Infinity`` to ``None`` so the rest of the
    (otherwise well-formed) response decodes. The ``prob`` field is not
    used downstream, so collapsing it to ``None`` is harmless.
    """
    return json.loads(response_text, parse_constant=lambda _c: None)


def _bern2_post(text: str, url: str, timeout: int, max_retries: int = 3) -> dict:
    """One BERN2 POST, with retry on transient failure.

    Retries up to ``max_retries`` times with exponential backoff (1s, 2s,
    4s) on genuine network errors or malformed responses. The common
    ``NaN``-in-``prob`` case is handled by :func:`_loads_bern2` and is
    *not* an error.

    Returns parsed JSON, or ``{"_error": ...}`` if every attempt failed.
    """
    last_error = "unknown"
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json={"text": text}, timeout=timeout)
            r.raise_for_status()
            return _loads_bern2(r.text)
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return {"_error": last_error}


def query_bern2(
    text: str,
    bern2_url: str,
    cache_dir: Path,
    timeout: int = 120,
    sleep_after: float = 0.0,
) -> dict:
    """Query the BERN2 NER+EL service, caching results per input text.

    Implements a JSON-truncation fallback: if the hosted API returns a
    truncated response (observed past ~5170 chars), the text is split at
    sentence boundaries and annotations are merged across sub-calls.

    Parameters
    ----------
    text:
        Free text to annotate.
    bern2_url:
        BERN2 endpoint, e.g. ``http://bern2.korea.ac.kr/plain``.
    cache_dir:
        Directory for per-call JSON cache. Created if missing.
    timeout:
        HTTP request timeout in seconds (per sub-call).
    sleep_after:
        Optional sleep after each network call (rate-limit friendliness).

    Returns
    -------
    dict
        Parsed BERN2 JSON, or ``{"_error": "..."}`` if every attempt failed.
        Successful responses have an ``"annotations"`` list.
    """
    cache_path = Path(cache_dir) / f"{_cache_key(text)}.json"
    cached = _read_json_cache(cache_path)
    if cached is not None and "_error" not in cached:
        return cached

    # First attempt: single call
    data = _bern2_post(text, bern2_url, timeout)
    if sleep_after > 0:
        time.sleep(sleep_after)
    if "_error" not in data:
        _write_json_cache(cache_path, data)
        return data

    # JSON-truncation fallback: split into sentence-bounded chunks
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 > _BERN2_CHUNK_CHARS and buf:
            chunks.append(buf)
            buf = s
        else:
            buf = (buf + " " + s).strip()
    if buf:
        chunks.append(buf)

    merged: list[dict] = []
    seen: set[tuple] = set()
    errors: list[str] = []
    for chunk in chunks:
        sub = _bern2_post(chunk, bern2_url, timeout)
        if sleep_after > 0:
            time.sleep(sleep_after)
        if "_error" in sub:
            errors.append(sub["_error"])
            continue
        for ann in sub.get("annotations", []):
            key = (
                ann.get("obj"),
                ann.get("mention", ""),
                tuple(sorted(ann.get("id", []) or [])),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(ann)

    if not merged and errors:
        result = {"_error": "; ".join(errors[:3])}
    else:
        result = {"annotations": merged}
    _write_json_cache(cache_path, result)
    return result


def extract_ncbi_gene_ids(bern2_response: dict) -> set[str]:
    """Pull all NCBI Gene numeric IDs from a BERN2 response.

    Accepts both ``NCBIGene:N`` and the older ``EntrezGene:N`` ID prefixes.
    Skips ``CUI-less`` and other non-resolving identifiers.
    """
    ids: set[str] = set()
    for ann in bern2_response.get("annotations", []) or []:
        if ann.get("obj") != "gene":
            continue
        for raw in (ann.get("id") or []):
            if not isinstance(raw, str):
                continue
            for prefix in ("NCBIGene:", "EntrezGene:"):
                if raw.startswith(prefix):
                    payload = raw[len(prefix):]
                    if payload.isdigit():
                        ids.add(payload)
                    break
    return ids


# ---------------------------------------------------------------------------
# BridgeDb reverse mapping: NCBI Gene -> HGNC
# ---------------------------------------------------------------------------

def map_ncbi_to_hgnc(
    ncbi_gene_ids: Iterable[str],
    bridgedb_url: str,
    cache_dir: Path,
    timeout: int = 60,
    chunk_size: int = 100,
    sleep_after: float = 0.0,
) -> dict[str, str]:
    """Map NCBI Gene IDs to HGNC numeric IDs via the BridgeDb batch API.

    Uses ``system_code=L`` (Entrez Gene) on the BridgeDb side. Parses the
    ``Hac:HGNC:N`` token (HGNC Accession) from each row's xref string --
    the bare ``H:`` prefix carries the gene *symbol*, which is not what we
    want for canonical identifier comparison.

    Parameters
    ----------
    ncbi_gene_ids:
        Iterable of NCBI Gene numeric IDs (strings).
    bridgedb_url:
        BridgeDb Human base URL, e.g. ``https://webservice.bridgedb.org/Human/``.
    cache_dir:
        Directory for per-chunk response cache.
    timeout, chunk_size, sleep_after:
        HTTP knobs.

    Returns
    -------
    dict
        ``{ncbi_id: hgnc_numeric_id}``. Missing mappings are absent.
    """
    ids = sorted({s for s in ncbi_gene_ids if isinstance(s, str) and s.isdigit()})
    if not ids:
        return {}

    out: dict[str, str] = {}
    base = bridgedb_url.rstrip("/") + "/"
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i + chunk_size]
        cache_path = Path(cache_dir) / f"{_cache_key(','.join(chunk))}.txt"
        if cache_path.exists():
            response_text = cache_path.read_text(encoding="utf-8")
        else:
            try:
                r = requests.post(
                    f"{base}xrefsBatch/L",
                    data="\n".join(chunk),
                    timeout=timeout,
                )
                r.raise_for_status()
                response_text = r.text
            except requests.RequestException as e:
                logger.warning("BridgeDb batch failed (chunk %d): %s", i // chunk_size, e)
                continue
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(response_text, encoding="utf-8")
            if sleep_after > 0:
                time.sleep(sleep_after)

        for line in response_text.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            ncbi_id = parts[0]
            xrefs = parts[2]
            if xrefs == "N/A":
                continue
            for token in xrefs.split(","):
                if token.startswith("Hac:HGNC:"):
                    hgnc_numeric = token[len("Hac:HGNC:"):]
                    if hgnc_numeric.isdigit():
                        out[ncbi_id] = hgnc_numeric
                    break

    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_hgnc_ids_via_ner_el(
    text: str,
    bern2_url: str,
    bridgedb_url: str,
    cache_dir: Path,
    timeout: int = 120,
    sleep_after: float = 0.0,
) -> set[str]:
    """Find HGNC numeric IDs in ``text`` via BERN2 + BridgeDb.

    Composes :func:`query_bern2`, :func:`extract_ncbi_gene_ids`, and
    :func:`map_ncbi_to_hgnc`. The cache is split into two subdirectories
    under ``cache_dir``: ``cache_dir/bern2/`` for BERN2 responses and
    ``cache_dir/bridgedb/`` for BridgeDb responses.

    Returns
    -------
    set[str]
        HGNC numeric IDs (e.g. ``{"11998", "108"}`` for TP53 and ACHE).
        Empty if BERN2 returned no gene entities or BridgeDb could not
        map any of them. Logs warnings on errors but does not raise.

    Notes
    -----
    This is the unit a Phase B caller invokes per KE/KER description. The
    caller is responsible for unioning the result with the regex-derived
    HGNC IDs and emitting RDF triples with appropriate provenance.
    """
    cache_dir = Path(cache_dir)
    bern2_cache = cache_dir / "bern2"
    bridgedb_cache = cache_dir / "bridgedb"

    bern2_response = query_bern2(
        text,
        bern2_url=bern2_url,
        cache_dir=bern2_cache,
        timeout=timeout,
        sleep_after=sleep_after,
    )
    if "_error" in bern2_response:
        logger.warning("BERN2 query failed: %s", bern2_response["_error"])
        return set()

    ncbi_ids = extract_ncbi_gene_ids(bern2_response)
    if not ncbi_ids:
        return set()

    ncbi_to_hgnc = map_ncbi_to_hgnc(
        ncbi_ids,
        bridgedb_url=bridgedb_url,
        cache_dir=bridgedb_cache,
        timeout=timeout,
        sleep_after=sleep_after,
    )
    return set(ncbi_to_hgnc.values())


def map_ner_genes_in_kes(
    kedict: dict, config, sleep_after: float = 0.0,
) -> dict[str, set[str]]:
    """Run BERN2 NER+EL over every Key Event description in ``kedict``.

    This is the pipeline-facing entry point. Iterates KEs that carry a
    ``dc:description``, queries BERN2 + BridgeDb per description, and
    returns the HGNC IDs found. Scope is KE descriptions only -- KERs are
    left to the regex mapper (a deliberate Phase B scoping decision).

    Parameters
    ----------
    kedict:
        Key Event dictionary (ke_id -> properties), as produced by the
        XML parser. KEs with a non-empty ``dc:description`` are scanned.
    config:
        PipelineConfig. Reads ``bern2_url``, ``bridgedb_url``,
        ``ner_cache_dir``, and ``request_timeout``.
    sleep_after:
        Optional per-call delay (seconds). Defaults to 0 for the
        production weekly run, which only annotates a handful of changed
        KEs. A cold-start cache-warming run over the full corpus should
        pass a small value (e.g. 0.5) to be polite to the hosted API.

    Returns
    -------
    dict
        ``{ke_id: set_of_hgnc_uri_strings}`` -- e.g.
        ``{"888": {"hgnc:11998", "hgnc:108"}}``. KEs with no detections
        are absent from the result. HGNC IDs are formatted as ``hgnc:N``
        URI-prefix strings to match the regex mapper's output convention.
    """
    results: dict[str, set[str]] = {}
    ke_ids = [
        ke_id for ke_id, props in kedict.items()
        if props.get("dc:description")
    ]
    total = len(ke_ids)
    logger.info("BERN2 NER+EL: scanning %d Key Event descriptions", total)

    for idx, ke_id in enumerate(ke_ids, 1):
        description = kedict[ke_id]["dc:description"]
        # dc:description can be a list of triple-quoted strings (parser
        # appends MIE/AO example text); join into one block for the model.
        if isinstance(description, list):
            text = " ".join(str(d).strip('"') for d in description)
        else:
            text = str(description).strip('"')
        if not text.strip():
            continue

        hgnc_numeric = find_hgnc_ids_via_ner_el(
            text,
            bern2_url=config.bern2_url,
            bridgedb_url=config.bridgedb_url,
            cache_dir=config.ner_cache_dir,
            timeout=config.request_timeout,
            sleep_after=sleep_after,
        )
        if hgnc_numeric:
            results[ke_id] = {f"hgnc:{n}" for n in hgnc_numeric}

        if idx % 100 == 0 or idx == total:
            logger.info(
                "BERN2 NER+EL progress: %d/%d KEs (%d with gene hits)",
                idx, total, len(results),
            )

    logger.info(
        "BERN2 NER+EL complete: %d/%d KEs had gene detections",
        len(results), total,
    )
    return results
