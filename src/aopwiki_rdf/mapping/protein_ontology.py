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
    max_retries: int = 3,
    fallback_paths: list | None = None,
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
    max_retries:
        Number of download attempts before degrading to a local copy. The
        proconsortium.org host is an unreliable external dependency; a single
        transient failure (e.g. ``Errno 111 Connection refused``) must not
        abort the whole conversion.
    fallback_paths:
        Ordered list of local copies to fall back to when every download
        attempt fails. Defaults to the bundled ``data/promapping.txt`` shipped
        in the repository. The output-dir copy (a cached prior download) is
        always tried first. Only when no usable local copy exists does the run
        hard-fail.

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

    if fallback_paths is None:
        # Bundled copy committed in the repository (resolved from the cwd, which
        # is the repo root in every workflow). Used as the last-known-good
        # source when the live download is unreachable.
        fallback_paths = [Path("data") / pro_filename]

    # Download (retry, then degrade to a local copy) ----------------------------
    downloaded = False
    last_exc: Exception | None = None
    for attempt in range(1, max(1, max_retries) + 1):
        try:
            logger.info(
                "Downloading protein mapping file from %s (attempt %d/%d)",
                promapping_url,
                attempt,
                max(1, max_retries),
            )
            urllib.request.urlretrieve(promapping_url, filepath)
            logger.info("Successfully downloaded %s", pro_filename)
            downloaded = True
            break
        except Exception as exc:  # noqa: BLE001 -- network errors are heterogeneous
            last_exc = exc
            logger.warning(
                "Protein mapping download attempt %d/%d failed: %s",
                attempt,
                max(1, max_retries),
                exc,
            )
            if attempt < max(1, max_retries):
                time.sleep(2 * attempt)

    if not downloaded:
        # Degrade to an existing local copy: the output-dir cache first (a
        # prior good download), then any explicit fallback (the bundled repo
        # file). Hard-fail only when no usable copy exists anywhere.
        candidates = [Path(filepath)] + [Path(p) for p in fallback_paths]
        fallback = next(
            (p for p in candidates if p.is_file() and p.stat().st_size > 0),
            None,
        )
        if fallback is None:
            logger.error(
                "Failed to download protein mapping file and no local fallback "
                "available: %s",
                last_exc,
            )
            raise SystemExit(1) from last_exc
        logger.error(
            "Protein mapping download failed (%s); degrading to local copy %s",
            last_exc,
            fallback,
        )
        filepath = str(fallback)

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
