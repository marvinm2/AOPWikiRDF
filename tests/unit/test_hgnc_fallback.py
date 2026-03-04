"""Tests for HGNC download fallback behavior and logging."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_hgnc_content(n_genes: int) -> str:
    """Generate fake HGNC TSV content with n_genes data lines plus header."""
    header = (
        "HGNC ID\tApproved symbol\tApproved name\t"
        "Previous symbols\tSynonyms\tAccession numbers\t"
        "Ensembl ID(supplied by Ensembl)"
    )
    lines = [header]
    for i in range(n_genes):
        lines.append(
            f"HGNC:{i}\tGENE{i}\tgene {i} name\t\t\t\tENSG{i:011d}"
        )
    return "\n".join(lines) + "\n"


class TestFallbackWithCache:
    """Tests for fallback when download fails but cache exists."""

    def test_returns_cache_content_on_download_failure(self, tmp_path):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        cache_content = _make_hgnc_content(20000)
        cache.write_text(cache_content)

        import requests
        with patch("aopwiki_rdf.hgnc.download.requests.get", side_effect=requests.ConnectionError("no network")):
            result = download_hgnc_data(
                url="https://example.com/hgnc",
                cache_path=cache,
                min_genes=19000,
            )
        assert result == cache_content


class TestFallbackWithoutCache:
    """Tests for fallback when download fails and cache is missing."""

    def test_raises_file_not_found_when_no_cache(self, tmp_path):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        assert not cache.exists()

        import requests
        with patch("aopwiki_rdf.hgnc.download.requests.get", side_effect=requests.ConnectionError("no network")):
            with pytest.raises(FileNotFoundError, match="cache"):
                download_hgnc_data(
                    url="https://example.com/hgnc",
                    cache_path=cache,
                    min_genes=19000,
                )


class TestFallbackLogging:
    """Tests for warning logging when falling back to cache."""

    def test_logs_warning_on_fallback(self, tmp_path, caplog):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        cache.write_text(_make_hgnc_content(20000))

        import requests
        with patch("aopwiki_rdf.hgnc.download.requests.get", side_effect=requests.ConnectionError("no network")):
            with caplog.at_level(logging.WARNING, logger="aopwiki_rdf.hgnc.download"):
                download_hgnc_data(
                    url="https://example.com/hgnc",
                    cache_path=cache,
                    min_genes=19000,
                )
        assert any("fallback" in r.message.lower() or "cache" in r.message.lower() for r in caplog.records)
