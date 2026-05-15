"""End-to-end integration test against the live BERN2 + BridgeDb services.

Skipped automatically when either service is unreachable, so the suite still
passes in offline CI. Hits the hosted BERN2 API at bern2.korea.ac.kr and
BridgeDb at webservice.bridgedb.org.
"""

import os
import socket
from pathlib import Path

import pytest


def _online(host: str, port: int = 80, timeout: float = 3.0) -> bool:
    """Return True if a TCP connect to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, OSError):
        return False


_BERN2_REACHABLE = _online("bern2.korea.ac.kr", 80)
_BRIDGEDB_REACHABLE = _online("webservice.bridgedb.org", 443)

skip_unless_online = pytest.mark.skipif(
    not (_BERN2_REACHABLE and _BRIDGEDB_REACHABLE)
    or os.environ.get("SKIP_NETWORK_TESTS"),
    reason="Skipped: BERN2 or BridgeDb unreachable, or SKIP_NETWORK_TESTS set",
)


@skip_unless_online
def test_find_hgnc_ids_against_live_services(tmp_path):
    """A sentence containing a well-known gene resolves to its HGNC ID."""
    from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el

    # TP53 = HGNC:11998. The mention is unambiguous; this should be a
    # high-confidence BERN2 detection followed by a deterministic
    # BridgeDb mapping.
    text = (
        "TP53 is a tumor suppressor gene frequently mutated in human cancers. "
        "It encodes the p53 protein which regulates the cell cycle."
    )
    hgnc_ids = find_hgnc_ids_via_ner_el(
        text,
        bern2_url="http://bern2.korea.ac.kr/plain",
        bridgedb_url="https://webservice.bridgedb.org/Human/",
        cache_dir=tmp_path,
        sleep_after=0.2,
    )

    # TP53 should be present. Other genes may or may not surface depending
    # on the model's tagging; we only assert the headline expectation.
    assert "11998" in hgnc_ids, (
        f"Expected HGNC:11998 (TP53) in result, got: {hgnc_ids}"
    )


@skip_unless_online
def test_cache_warm_skips_network(tmp_path):
    """Second call against the same text hits the disk cache, not the network."""
    from aopwiki_rdf.mapping.ner_el_mapper import find_hgnc_ids_via_ner_el

    text = "Acetylcholinesterase (ACHE) catalyses the breakdown of acetylcholine."

    # First call: warm the cache from live services.
    result1 = find_hgnc_ids_via_ner_el(
        text,
        bern2_url="http://bern2.korea.ac.kr/plain",
        bridgedb_url="https://webservice.bridgedb.org/Human/",
        cache_dir=tmp_path,
        sleep_after=0.2,
    )
    assert "108" in result1  # ACHE = HGNC:108

    # Second call with an unreachable URL: must succeed via cache.
    result2 = find_hgnc_ids_via_ner_el(
        text,
        bern2_url="http://invalid.example.invalid/plain",
        bridgedb_url="https://invalid.example.invalid/Human/",
        cache_dir=tmp_path,
    )
    assert result1 == result2, "Cache should serve identical results offline"
