"""Tests for HGNC download function and assertion guard."""

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


@pytest.fixture
def mock_response_ok():
    """Mock response with 19500 genes (above threshold)."""
    resp = MagicMock()
    resp.text = _make_hgnc_content(19500)
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_response_low():
    """Mock response with only 100 genes (below threshold)."""
    resp = MagicMock()
    resp.text = _make_hgnc_content(100)
    resp.raise_for_status = MagicMock()
    return resp


class TestDownloadSuccess:
    """Tests for successful download path."""

    def test_returns_content_on_valid_response(self, tmp_path, mock_response_ok):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        with patch("aopwiki_rdf.hgnc.download.requests.get", return_value=mock_response_ok):
            result = download_hgnc_data(
                url="https://example.com/hgnc",
                cache_path=cache,
                min_genes=19000,
            )
        assert isinstance(result, str)
        assert "GENE0" in result

    def test_updates_cache_on_success(self, tmp_path, mock_response_ok):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        with patch("aopwiki_rdf.hgnc.download.requests.get", return_value=mock_response_ok):
            download_hgnc_data(
                url="https://example.com/hgnc",
                cache_path=cache,
                min_genes=19000,
            )
        assert cache.exists()
        assert "GENE0" in cache.read_text()


class TestAssertionGuard:
    """Tests for gene count assertion guard."""

    def test_falls_back_when_response_has_too_few_genes(self, tmp_path, mock_response_low):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        cache_content = _make_hgnc_content(19500)
        cache.write_text(cache_content)

        with patch("aopwiki_rdf.hgnc.download.requests.get", return_value=mock_response_low):
            result = download_hgnc_data(
                url="https://example.com/hgnc",
                cache_path=cache,
                min_genes=19000,
            )
        # Should have fallen back to cache content
        assert "GENE19000" in result


class TestNetworkFailure:
    """Tests for network failure fallback."""

    def test_falls_back_on_requests_exception(self, tmp_path):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        cache_content = _make_hgnc_content(19500)
        cache.write_text(cache_content)

        import requests
        with patch("aopwiki_rdf.hgnc.download.requests.get", side_effect=requests.ConnectionError("fail")):
            result = download_hgnc_data(
                url="https://example.com/hgnc",
                cache_path=cache,
                min_genes=19000,
            )
        assert "GENE0" in result

    def test_falls_back_on_http_error(self, tmp_path):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "HGNCgenes.txt"
        cache_content = _make_hgnc_content(19500)
        cache.write_text(cache_content)

        import requests
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("aopwiki_rdf.hgnc.download.requests.get", return_value=resp):
            result = download_hgnc_data(
                url="https://example.com/hgnc",
                cache_path=cache,
                min_genes=19000,
            )
        assert "GENE0" in result

    def test_raises_file_not_found_when_both_fail(self, tmp_path):
        from aopwiki_rdf.hgnc.download import download_hgnc_data

        cache = tmp_path / "nonexistent" / "HGNCgenes.txt"

        import requests
        with patch("aopwiki_rdf.hgnc.download.requests.get", side_effect=requests.ConnectionError("fail")):
            with pytest.raises(FileNotFoundError):
                download_hgnc_data(
                    url="https://example.com/hgnc",
                    cache_path=cache,
                    min_genes=19000,
                )
