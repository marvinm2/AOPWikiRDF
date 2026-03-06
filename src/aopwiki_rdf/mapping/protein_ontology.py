"""Protein Ontology promapping.txt download and parsing.

Extracted from pipeline.py lines 1050-1102.

Downloads the promapping.txt file from the Protein Consortium website and
parses protein-to-identifier mappings (HGNC, UniProt, NCBIGene) for Protein
Ontology terms that appear in the AOP-Wiki biological objects.
"""

import logging
import os
import stat
import time
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)


def download_and_parse_promapping(
    promapping_url: str,
    data_dir: Path,
    prolist: list,
) -> dict:
    """Download promapping.txt and parse protein-to-identifier mappings.

    Parameters
    ----------
    promapping_url:
        URL to download promapping.txt (e.g.
        ``https://proconsortium.org/download/current/promapping.txt``).
    data_dir:
        Directory to save the downloaded file.
    prolist:
        List of protein ontology keys (e.g. ``['pr:000001', ...]``) used to
        filter which mappings are retained.

    Returns
    -------
    dict
        Keys:

        - ``prodict``: ``{pr_key: [identifier_list]}``
        - ``pro_hgnclist``: ``['hgnc:XXXX', ...]`` (protein ontology HGNC refs)
        - ``pro_uniprotlist``: ``['uniprot:XXXX', ...]``
        - ``pro_ncbigenelist``: ``['ncbigene:XXXX', ...]``
        - ``modification_time``: ``str`` (file modification time)

    Note
    ----
    The ``pro_hgnclist`` returned here contains HGNC references derived from
    the Protein Ontology mapping file.  These are *distinct* from the HGNC
    gene list used by the gene-mapping stage (built from HGNC download data).
    """
    data_dir = Path(data_dir)
    pro_filename = "promapping.txt"
    filepath = str(data_dir / pro_filename)

    # Download ------------------------------------------------------------------
    try:
        logger.info("Downloading protein mapping file from %s", promapping_url)
        urllib.request.urlretrieve(promapping_url, filepath)
        logger.info("Successfully downloaded %s", pro_filename)
    except Exception as exc:
        logger.error("Failed to download protein mapping file: %s", exc)
        raise SystemExit(1) from exc

    # File modification time ----------------------------------------------------
    try:
        file_stats = os.stat(filepath)
        modification_time = time.ctime(file_stats[stat.ST_MTIME])
        logger.info("Protein mapping file last modified: %s", modification_time)
    except OSError as exc:
        logger.error("Could not get file stats for %s: %s", pro_filename, exc)
        modification_time = "Unknown"

    # Parse ---------------------------------------------------------------------
    prodict: dict[str, list[str]] = {}
    hgnclist: list[str] = []
    uniprotlist: list[str] = []
    ncbigenelist: list[str] = []

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                key = "pr:" + parts[0][3:]
                if key not in prolist:
                    continue
                if key not in prodict:
                    prodict[key] = []

                col = parts[1]
                if "HGNC:" in col:
                    ident = "hgnc:" + col[5:]
                    prodict[key].append(ident)
                    hgnclist.append(ident)
                if "NCBIGene:" in col:
                    ident = "ncbigene:" + col[9:]
                    prodict[key].append(ident)
                    ncbigenelist.append(ident)
                if "UniProtKB:" in col:
                    ident = "uniprot:" + col.split(",")[0][10:]
                    prodict[key].append(ident)
                    uniprotlist.append(ident)

                if not prodict[key]:
                    del prodict[key]
    except IOError as exc:
        logger.error("Failed to open promapping file %s: %s", filepath, exc)
        raise SystemExit(1) from exc

    logger.info(
        "Protein mapping completed: added %d identifiers for %d Protein Ontology terms",
        len(hgnclist) + len(ncbigenelist) + len(uniprotlist),
        len(prodict),
    )

    return {
        "prodict": prodict,
        "pro_hgnclist": hgnclist,
        "pro_uniprotlist": uniprotlist,
        "pro_ncbigenelist": ncbigenelist,
        "modification_time": modification_time,
    }
