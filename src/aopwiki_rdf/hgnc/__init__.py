"""HGNC gene data module: download and parsing."""

from aopwiki_rdf.hgnc.download import download_hgnc_data
from aopwiki_rdf.hgnc.parser import parse_hgnc_genes

__all__ = ["download_hgnc_data", "parse_hgnc_genes"]
