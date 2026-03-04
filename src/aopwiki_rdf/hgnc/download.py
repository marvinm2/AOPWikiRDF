"""Dynamic HGNC gene data download with assertion guard and static fallback."""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download_hgnc_data(
    url: str,
    cache_path: Path,
    timeout: int = 30,
    max_retries: int = 3,
    min_genes: int = 19000,
) -> str:
    """Download HGNC gene data from genenames.org with fallback to cached file.

    Fetches the latest HGNC custom download, validates that it contains at
    least ``min_genes`` gene entries, and updates the local cache on success.
    On any failure (network, HTTP, or too few genes), falls back to the
    cached static file.

    Args:
        url: genenames.org custom download endpoint URL.
        cache_path: Path to the local HGNCgenes.txt cache file.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of download attempts.
        min_genes: Minimum number of gene lines required (assertion guard).

    Returns:
        Raw TSV text content (header + gene lines).

    Raises:
        FileNotFoundError: If download fails and cache_path does not exist.
    """
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Downloading HGNC data (attempt %d/%d) from %s",
                attempt, max_retries, url,
            )
            response = requests.get(url, timeout=timeout, verify=False)
            response.raise_for_status()

            content = response.text
            # Count data lines (total lines minus header)
            n_lines = content.strip().count("\n")  # number of newlines = data lines
            assert n_lines >= min_genes, (
                f"HGNC download returned only {n_lines} genes "
                f"(minimum: {min_genes})"
            )

            # Success -- update the cache file
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(content, encoding="utf-8")
            logger.info(
                "HGNC download successful: %d gene lines, cache updated at %s",
                n_lines, cache_path,
            )
            return content

        except Exception as exc:
            logger.warning(
                "HGNC download attempt %d failed: %s", attempt, exc,
            )
            if attempt < max_retries:
                continue

            # All retries exhausted -- fall back to cache
            logger.warning(
                "All %d download attempts failed. "
                "Falling back to cached HGNC data at %s",
                max_retries, cache_path,
            )
            return _read_cache(cache_path)

    # Should not reach here, but guard against it
    return _read_cache(cache_path)


def _read_cache(cache_path: Path) -> str:
    """Read the cached HGNC file, raising FileNotFoundError if missing."""
    if not cache_path.exists():
        raise FileNotFoundError(
            f"HGNC download failed and no cache file found at {cache_path}. "
            f"Cannot proceed without gene data."
        )
    logger.info("Reading cached HGNC data from %s", cache_path)
    return cache_path.read_text(encoding="utf-8")
