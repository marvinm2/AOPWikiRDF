"""Unit tests for protein_ontology promapping download + fallback.

Covers the QC-relevant resilience behavior: a transient proconsortium.org
outage (the 2026-06-06 ``Errno 111 Connection refused`` that crashed the
Test Python Conversion run) must degrade to a local copy instead of aborting
the whole conversion, but a total absence of any usable copy must still fail.
"""

from pathlib import Path
from unittest import mock

import pytest

from aopwiki_rdf.mapping.protein_ontology import download_and_parse_promapping

# Two PR rows: one HGNC mapping, one UniProtKB mapping (with a trailing token
# after the comma, which the parser must strip).
SAMPLE_PROMAPPING = (
    "PR:000001\tHGNC:1234\tis_a\n"
    "PR:000002\tUniProtKB:P12345,Homo sapiens\tis_a\n"
)
PROLIST = ["pr:000001", "pr:000002"]


def _write(path: Path, text: str = SAMPLE_PROMAPPING) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_download_failure_falls_back_to_local_copy(tmp_path):
    """When every download attempt fails, a bundled fallback copy is parsed."""
    out_dir = tmp_path / "data-test"
    out_dir.mkdir()
    fallback = _write(tmp_path / "bundled-promapping.txt")

    with mock.patch(
        "aopwiki_rdf.mapping.protein_ontology.urllib.request.urlretrieve",
        side_effect=ConnectionRefusedError(111, "Connection refused"),
    ), mock.patch(
        "aopwiki_rdf.mapping.protein_ontology.time.sleep"
    ):
        result = download_and_parse_promapping(
            promapping_url="https://proconsortium.org/download/current/promapping.txt",
            data_dir=out_dir,
            prolist=PROLIST,
            max_retries=2,
            fallback_paths=[fallback],
        )

    assert result["pro_hgnclist"] == ["hgnc:1234"]
    assert result["pro_uniprotlist"] == ["uniprot:P12345"]
    assert set(result["prodict"]) == {"pr:000001", "pr:000002"}


def test_download_failure_prefers_output_dir_cache(tmp_path):
    """A cached copy already in the output dir is used before the fallback."""
    out_dir = tmp_path / "data"
    out_dir.mkdir()
    _write(out_dir / "promapping.txt")  # cached prior download
    # Fallback points at a DIFFERENT (empty-of-target) file; must not be used.
    other = _write(tmp_path / "other.txt", "PR:000099\tHGNC:9999\tis_a\n")

    with mock.patch(
        "aopwiki_rdf.mapping.protein_ontology.urllib.request.urlretrieve",
        side_effect=OSError("boom"),
    ), mock.patch("aopwiki_rdf.mapping.protein_ontology.time.sleep"):
        result = download_and_parse_promapping(
            promapping_url="https://example.invalid/promapping.txt",
            data_dir=out_dir,
            prolist=PROLIST,
            max_retries=1,
            fallback_paths=[other],
        )

    assert result["pro_hgnclist"] == ["hgnc:1234"]  # from the cache, not `other`


def test_download_failure_without_any_copy_hard_fails(tmp_path):
    """No download and no local copy anywhere -> SystemExit (cannot proceed)."""
    out_dir = tmp_path / "data-test"
    out_dir.mkdir()

    with mock.patch(
        "aopwiki_rdf.mapping.protein_ontology.urllib.request.urlretrieve",
        side_effect=ConnectionRefusedError(111, "Connection refused"),
    ), mock.patch("aopwiki_rdf.mapping.protein_ontology.time.sleep"):
        with pytest.raises(SystemExit):
            download_and_parse_promapping(
                promapping_url="https://proconsortium.org/download/current/promapping.txt",
                data_dir=out_dir,
                prolist=PROLIST,
                max_retries=1,
                fallback_paths=[tmp_path / "does-not-exist.txt"],
            )


def test_successful_download_is_parsed(tmp_path):
    """The happy path still writes to the output dir and parses it."""
    out_dir = tmp_path / "data-test"
    out_dir.mkdir()

    def fake_urlretrieve(url, filename):
        _write(Path(filename))
        return filename, None

    with mock.patch(
        "aopwiki_rdf.mapping.protein_ontology.urllib.request.urlretrieve",
        side_effect=fake_urlretrieve,
    ):
        result = download_and_parse_promapping(
            promapping_url="https://proconsortium.org/download/current/promapping.txt",
            data_dir=out_dir,
            prolist=PROLIST,
        )

    assert result["pro_hgnclist"] == ["hgnc:1234"]
    assert (out_dir / "promapping.txt").is_file()
