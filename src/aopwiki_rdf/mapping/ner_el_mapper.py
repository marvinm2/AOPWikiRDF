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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests

logger = logging.getLogger(__name__)


@dataclass
class NerResult:
    """Outcome of a single BERN2 NER+EL gene lookup.

    Makes a BERN2 *failure* observable to the merge step (NER-04). Today an
    empty ``set()`` is ambiguous -- it could mean "BERN2 ran and found no
    genes" OR "BERN2 was unreachable". This object disambiguates:

    Attributes
    ----------
    hgnc_ids:
        HGNC numeric IDs found (e.g. ``{"11998"}``). Empty on both a clean
        no-hit run and a failure.
    failed:
        ``True`` only when the BERN2 call itself failed (``query_bern2``
        returned ``_error`` -- unreachable / all retries exhausted /
        truncation-fallback all-failed). A successful call that found zero
        genes is ``failed=False``.
    error:
        The error message when ``failed`` is ``True``; otherwise ``None``.
    """

    hgnc_ids: set[str] = field(default_factory=set)
    failed: bool = False
    error: str | None = None

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
# Description normalisation + cache-coverage probe (NER-03)
# ---------------------------------------------------------------------------

def _description_text(props_description) -> str:
    """Normalise a parser ``dc:description`` value into one annotation block.

    The XML parser stores descriptions wrapped in triple double-quotes and,
    for KEs, occasionally as a list of such blocks. The pipeline annotates the
    *unwrapped, space-joined* text, so cache keys must be computed from the
    same string or the coverage probe reports false misses. This helper is the
    single source of truth for that normalisation, shared by
    :func:`map_ner_genes_in_kes`, :func:`is_cached`, and
    :func:`report_cache_coverage`.

    Parameters
    ----------
    props_description:
        A ``dc:description`` value: either a ``"``-wrapped string or a list of
        such strings.

    Returns
    -------
    str
        List inputs are joined with single spaces after stripping ``"``;
        scalar inputs are coerced to ``str`` and stripped of ``"``.
    """
    if isinstance(props_description, list):
        return " ".join(str(d).strip('"') for d in props_description)
    return str(props_description).strip('"')


def is_cached(text: str, ner_cache_dir) -> bool:
    """Return True iff ``text`` has a usable BERN2 cache entry.

    Pure disk probe -- never touches the network. A cache entry counts as
    present only if the file exists, parses as JSON, and carries no
    ``_error`` key (mirroring the check in :func:`query_bern2`). Corrupt JSON
    is treated as a miss; note that :func:`_read_json_cache` deletes corrupt
    files as a side effect (re-warmable), which is the desired tamper
    response (threat T-06-01).

    Parameters
    ----------
    text:
        The text to probe. Callers should pass the SAME normalised text the
        pipeline annotates (see :func:`_description_text`).
    ner_cache_dir:
        The configured ``ner_cache_dir``; BERN2 responses live under
        ``{ner_cache_dir}/bern2/{_cache_key(text)}.json`` (matching
        :func:`find_hgnc_ids_via_ner_el`).
    """
    cache_path = Path(ner_cache_dir) / "bern2" / f"{_cache_key(text)}.json"
    cached = _read_json_cache(cache_path)
    return (
        cached is not None
        and "_error" not in cached
        and not cached.get("_partial")
    )


def report_cache_coverage(*entity_dicts, config) -> dict:
    """Measure BERN2 cache coverage across one or more entity dictionaries.

    Counts entities carrying a non-empty ``dc:description`` (whitespace-only
    descriptions are skipped, matching the pipeline's
    ``if not text.strip(): continue``), and classifies each as cached or
    uncached via :func:`is_cached`. Pure disk probe -- no network I/O and no
    mutation of the passed dicts.

    Parameters
    ----------
    *entity_dicts:
        One or more ``{entity_id: properties}`` dicts (e.g. ``kedict``,
        ``kerdict``).
    config:
        PipelineConfig; only ``ner_cache_dir`` is read.

    Returns
    -------
    dict
        ``{"total": int, "cached": int, "uncached_ids": list[str]}`` where
        ``uncached_ids`` is sorted. Emits one INFO summary line and, when any
        IDs are uncached, one INFO line listing them (truncated to the first
        50 with a ``+N more`` suffix; threat T-06-02 bounds log volume).
    """
    total = 0
    cached = 0
    uncached_ids: list[str] = []

    for entity_dict in entity_dicts:
        for entity_id, props in entity_dict.items():
            description = props.get("dc:description")
            if not description:
                continue
            text = _description_text(description)
            if not text.strip():
                continue
            total += 1
            if is_cached(text, config.ner_cache_dir):
                cached += 1
            else:
                uncached_ids.append(entity_id)

    uncached_ids.sort()
    n_uncached = len(uncached_ids)
    pct = (100.0 * cached / total) if total else 0.0
    logger.info(
        "BERN2 cache coverage: %d/%d (%.1f%%); %d uncached",
        cached, total, pct, n_uncached,
    )
    if uncached_ids:
        head = uncached_ids[:50]
        suffix = f" (+{n_uncached - len(head)} more)" if n_uncached > len(head) else ""
        logger.info("BERN2 uncached IDs: %s%s", ", ".join(head), suffix)

    return {"total": total, "cached": cached, "uncached_ids": uncached_ids}


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
    if cached is not None and "_error" not in cached and not cached.get("_partial"):
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
        # All chunks failed: unreachable / all retries exhausted. Cached as a
        # re-warmable miss (find_hgnc_ids_via_ner_el_result keys failed=True
        # off "_error" only).
        result = {"_error": "; ".join(errors[:3])}
    elif errors:
        # Mixed outcome (D-11): some chunks succeeded, some errored. Keep the
        # genes we DID find (additive) but mark the entry "_partial" so both
        # cache gates treat it as a miss and the failed chunk is retried next
        # run. A "_partial" still carries "annotations" and no "_error", so it
        # composes with NerResult as failed=False -- never a regex-only
        # degradation trigger.
        result = {"annotations": merged, "_partial": True, "_errors": errors[:3]}
    else:
        # Clean all-success chunked outcome -- byte-unchanged.
        result = {"annotations": merged}
    _write_json_cache(cache_path, result)
    return result


def extract_ncbi_gene_ids(bern2_response: dict, min_prob: float = 0.0) -> set[str]:
    """Pull all NCBI Gene numeric IDs from a BERN2 response.

    Accepts both ``NCBIGene:N`` and the older ``EntrezGene:N`` ID prefixes.
    Skips ``CUI-less`` and other non-resolving identifiers.

    Parameters
    ----------
    bern2_response:
        Parsed BERN2 JSON with an ``"annotations"`` list.
    min_prob:
        Minimum BERN2 confidence (``prob``) for a gene annotation to be
        kept. Annotations scoring below this are dropped: the low-prob
        tail is dominated by entity-linking errors (HTML entities, drug
        names, generic-word mislinks). The default ``0.0`` keeps every
        annotation. An annotation whose ``prob`` is absent or ``None``
        -- BERN2 emits bare ``NaN`` for some neural-normalised entities,
        which :func:`_loads_bern2` collapses to ``None`` -- is *kept*: a
        missing score is not evidence of an error.
    """
    ids: set[str] = set()
    for ann in bern2_response.get("annotations", []) or []:
        if ann.get("obj") != "gene":
            continue
        prob = ann.get("prob")
        if isinstance(prob, (int, float)) and prob < min_prob:
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

def find_hgnc_ids_via_ner_el_result(
    text: str,
    bern2_url: str,
    bridgedb_url: str,
    cache_dir: Path,
    timeout: int = 120,
    sleep_after: float = 0.0,
    min_prob: float = 0.0,
) -> NerResult:
    """Find HGNC numeric IDs in ``text``, signalling BERN2 failure (NER-04).

    Same composition as :func:`find_hgnc_ids_via_ner_el` -- :func:`query_bern2`,
    :func:`extract_ncbi_gene_ids`, :func:`map_ncbi_to_hgnc` -- but returns a
    :class:`NerResult` so callers can distinguish a BERN2 *failure* from a
    successful run that found no genes:

    * ``query_bern2`` returns ``_error`` (unreachable / all retries failed /
      truncation-fallback all-failed) -> ``NerResult(set(), failed=True,
      error=<msg>)``. This is the ONLY failure case.
    * BERN2 ran fine but emitted no gene annotations, or BridgeDb mapped
      none of them -> ``NerResult(set(), failed=False, error=None)``.
    * BERN2 ran fine with mappable genes -> ``NerResult({hgnc...},
      failed=False, error=None)``.

    The cache layout, knobs, and network behaviour are identical to
    :func:`find_hgnc_ids_via_ner_el`; this adds no network calls.
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
        # The only failure boundary: BERN2 itself could not be reached / all
        # retries and the chunking fallback failed. NOT a clean no-hit run.
        logger.warning("BERN2 query failed: %s", bern2_response["_error"])
        return NerResult(set(), failed=True, error=bern2_response["_error"])

    ncbi_ids = extract_ncbi_gene_ids(bern2_response, min_prob=min_prob)
    if not ncbi_ids:
        return NerResult(set(), failed=False, error=None)

    ncbi_to_hgnc = map_ncbi_to_hgnc(
        ncbi_ids,
        bridgedb_url=bridgedb_url,
        cache_dir=bridgedb_cache,
        timeout=timeout,
        sleep_after=sleep_after,
    )
    return NerResult(set(ncbi_to_hgnc.values()), failed=False, error=None)


def find_hgnc_ids_via_ner_el(
    text: str,
    bern2_url: str,
    bridgedb_url: str,
    cache_dir: Path,
    timeout: int = 120,
    sleep_after: float = 0.0,
    min_prob: float = 0.0,
) -> set[str]:
    """Find HGNC numeric IDs in ``text`` via BERN2 + BridgeDb.

    Thin wrapper over :func:`find_hgnc_ids_via_ner_el_result` returning only
    the ``hgnc_ids`` set, so its ``set[str]`` contract is unchanged for every
    existing caller -- byte-identical behaviour to before NER-04 for any input
    (an empty set is still returned on both a no-hit run and a BERN2 failure).

    Composes :func:`query_bern2`, :func:`extract_ncbi_gene_ids`, and
    :func:`map_ncbi_to_hgnc`. The cache is split into two subdirectories
    under ``cache_dir``: ``cache_dir/bern2/`` for BERN2 responses and
    ``cache_dir/bridgedb/`` for BridgeDb responses. ``min_prob`` is the
    BERN2 confidence cutoff for gene annotations (see
    :func:`extract_ncbi_gene_ids`); the default ``0.0`` disables it.

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
    HGNC IDs and emitting RDF triples with appropriate provenance. Callers
    that need to react to a BERN2 outage (regex fallback) should use
    :func:`find_hgnc_ids_via_ner_el_result` instead.
    """
    return find_hgnc_ids_via_ner_el_result(
        text,
        bern2_url=bern2_url,
        bridgedb_url=bridgedb_url,
        cache_dir=cache_dir,
        timeout=timeout,
        sleep_after=sleep_after,
        min_prob=min_prob,
    ).hgnc_ids


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
        ``ner_cache_dir``, ``ner_min_prob``, and ``request_timeout``.
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
        # dc:description can be a list of triple-quoted strings (parser
        # appends MIE/AO example text); _description_text joins into one
        # block for the model -- the single source of truth for the
        # normalisation, so cache keys match the coverage probe.
        text = _description_text(kedict[ke_id]["dc:description"])
        if not text.strip():
            continue

        hgnc_numeric = find_hgnc_ids_via_ner_el(
            text,
            bern2_url=config.bern2_url,
            bridgedb_url=config.bridgedb_url,
            cache_dir=config.ner_cache_dir,
            timeout=config.request_timeout,
            sleep_after=sleep_after,
            min_prob=config.ner_min_prob,
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


def map_ner_genes_in_kes_result(
    kedict: dict, config, sleep_after: float = 0.0,
) -> dict[str, NerResult]:
    """Run BERN2 NER+EL over every KE description, signalling per-KE failure.

    Result-returning counterpart to :func:`map_ner_genes_in_kes` (NER-04).
    Iterates KEs that carry a non-empty ``dc:description`` and returns a
    :class:`NerResult` *per scanned KE* (not just those with hits) so the
    merge step can see exactly WHICH descriptions degraded and fall back to
    their regex genes. Reuses :func:`_description_text` so cache keys match
    the coverage probe and the existing KE pass.

    Parameters
    ----------
    kedict:
        Key Event dictionary (ke_id -> properties) from the XML parser. KEs
        with a non-empty ``dc:description`` are scanned.
    config:
        PipelineConfig. Reads ``bern2_url``, ``bridgedb_url``,
        ``ner_cache_dir``, ``ner_min_prob``, and ``request_timeout``.
    sleep_after:
        Optional per-call delay (seconds).

    Returns
    -------
    dict
        ``{ke_id: NerResult}`` for every scanned KE. ``NerResult.hgnc_ids``
        are formatted as ``hgnc:N`` URI-prefix strings to match the regex
        mapper's output convention. KEs with blank descriptions are absent.
    """
    results: dict[str, NerResult] = {}
    ke_ids = [
        ke_id for ke_id, props in kedict.items()
        if props.get("dc:description")
    ]
    total = len(ke_ids)
    logger.info("BERN2 NER+EL: scanning %d Key Event descriptions", total)

    n_failed = 0
    for idx, ke_id in enumerate(ke_ids, 1):
        text = _description_text(kedict[ke_id]["dc:description"])
        if not text.strip():
            continue

        result = find_hgnc_ids_via_ner_el_result(
            text,
            bern2_url=config.bern2_url,
            bridgedb_url=config.bridgedb_url,
            cache_dir=config.ner_cache_dir,
            timeout=config.request_timeout,
            sleep_after=sleep_after,
            min_prob=config.ner_min_prob,
        )
        # Re-format HGNC numeric IDs as hgnc:N to match the regex mapper.
        results[ke_id] = NerResult(
            hgnc_ids={f"hgnc:{n}" for n in result.hgnc_ids},
            failed=result.failed,
            error=result.error,
        )
        if result.failed:
            n_failed += 1

        if idx % 100 == 0 or idx == total:
            logger.info(
                "BERN2 NER+EL progress: %d/%d KEs (%d failed)",
                idx, total, n_failed,
            )

    logger.info(
        "BERN2 NER+EL complete: %d/%d KEs scanned, %d failed",
        len(results), total, n_failed,
    )
    return results


def map_ner_genes_in_kers(
    kerdict: dict, config, sleep_after: float = 0.0,
) -> dict[str, set[str]]:
    """Run BERN2 NER+EL over every Key Event Relationship description.

    Symmetric counterpart to :func:`map_ner_genes_in_kes`, iterating KERs that
    carry a ``dc:description``. Reuses :func:`_description_text` so the cache
    keys it warms match what the coverage probe (and a future Phase 7 KER
    detector) will look up. Honours the same caching/short-circuit semantics
    as the KE pass, so a warming run over both corpora is resumable.

    Parameters
    ----------
    kerdict:
        Key Event Relationship dictionary (ker_id -> properties) from the XML
        parser. KERs with a non-empty ``dc:description`` are scanned.
    config:
        PipelineConfig. Reads ``bern2_url``, ``bridgedb_url``,
        ``ner_cache_dir``, ``ner_min_prob``, and ``request_timeout``.
    sleep_after:
        Optional per-call delay (seconds).

    Returns
    -------
    dict
        ``{ker_id: set_of_hgnc_uri_strings}``. KERs with no detections are
        absent. HGNC IDs are formatted as ``hgnc:N`` to match the KE pass.
    """
    results: dict[str, set[str]] = {}
    ker_ids = [
        ker_id for ker_id, props in kerdict.items()
        if props.get("dc:description")
    ]
    total = len(ker_ids)
    logger.info("BERN2 NER+EL: scanning %d Key Event Relationship descriptions", total)

    for idx, ker_id in enumerate(ker_ids, 1):
        text = _description_text(kerdict[ker_id]["dc:description"])
        if not text.strip():
            continue

        hgnc_numeric = find_hgnc_ids_via_ner_el(
            text,
            bern2_url=config.bern2_url,
            bridgedb_url=config.bridgedb_url,
            cache_dir=config.ner_cache_dir,
            timeout=config.request_timeout,
            sleep_after=sleep_after,
            min_prob=config.ner_min_prob,
        )
        if hgnc_numeric:
            results[ker_id] = {f"hgnc:{n}" for n in hgnc_numeric}

        if idx % 100 == 0 or idx == total:
            logger.info(
                "BERN2 NER+EL progress: %d/%d KERs (%d with gene hits)",
                idx, total, len(results),
            )

    logger.info(
        "BERN2 NER+EL complete: %d/%d KERs had gene detections",
        len(results), total,
    )
    return results
