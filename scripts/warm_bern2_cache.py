"""Warm the BERN2 NER+EL response cache (Phase C cold start).

Runs BERN2 + BridgeDb over every Key Event description in an AOP-Wiki XML
export, populating data/cache/bern2/ so the weekly pipeline only ever
hits the network for KE descriptions that changed since the last run.

This is a one-time operational step. It must be run before flipping
config.enable_bern2 on in production, otherwise the first weekly run
would do the full-corpus annotation inline.

The run is RESUMABLE: every BERN2 and BridgeDb response is cached on
disk keyed by the SHA of its input, so re-running after an interruption
skips everything already done. Safe to Ctrl-C and restart.

Crucially, this script drives the *exact* production code path
(parse_aopwiki_xml -> map_ner_genes_in_kes), so the cache keys it writes
match what the pipeline will look up.

Usage:
    python scripts/warm_bern2_cache.py [--xml PATH] [--sleep SECONDS]
                                       [--limit N]

    --xml    AOP-Wiki XML file. Default: newest data/aop-wiki-xml-* file.
    --sleep  Per-call delay, seconds (politeness to the hosted API).
             Default 0.5.
    --limit  Process at most N KE descriptions (for a smoke test).
"""

import argparse
import glob
import logging
import os
import sys
import time
from pathlib import Path

# Ensure the package is importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
from aopwiki_rdf.mapping.ner_el_mapper import map_ner_genes_in_kes


def _newest_xml() -> str | None:
    """Return the path to the newest data/aop-wiki-xml-* file, if any."""
    candidates = sorted(glob.glob("data/aop-wiki-xml-*"))
    return candidates[-1] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", default=None, help="AOP-Wiki XML file path")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Per-call delay in seconds (default 0.5)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N KE descriptions")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    log = logging.getLogger("warm_bern2_cache")

    xml_path = args.xml or _newest_xml()
    if not xml_path or not os.path.isfile(xml_path):
        log.error("XML file not found: %s "
                  "(pass --xml or place one under data/)", xml_path)
        return 1

    config = PipelineConfig(enable_bern2=True)
    log.info("Cold start: warming BERN2 cache at %s", config.ner_cache_dir)
    log.info("XML: %s", xml_path)

    log.info("Parsing XML ...")
    entities = parse_aopwiki_xml(xml_path, config=None)
    kedict = entities.kedict

    if args.limit is not None:
        # Keep only the first N KEs that have a description.
        kept = {}
        for ke_id, props in kedict.items():
            if props.get("dc:description"):
                kept[ke_id] = props
            if len(kept) >= args.limit:
                break
        kedict = kept
        log.info("Limited to %d KE descriptions (--limit)", len(kedict))

    n_with_desc = sum(1 for p in kedict.values() if p.get("dc:description"))
    log.info("%d Key Events, %d with a description to annotate",
             len(kedict), n_with_desc)

    t0 = time.time()
    results = map_ner_genes_in_kes(kedict, config, sleep_after=args.sleep)
    elapsed = time.time() - t0

    total_hgnc = sum(len(v) for v in results.values())
    log.info("=" * 60)
    log.info("Cold start complete in %.1f min", elapsed / 60)
    log.info("KEs with gene detections: %d / %d", len(results), n_with_desc)
    log.info("Total HGNC IDs detected (with duplicates across KEs): %d",
             total_hgnc)
    log.info("Cache directory: %s", config.ner_cache_dir)
    log.info("=" * 60)
    log.info("Next step: commit the warmed cache, then flip "
             "enable_bern2 on in the weekly workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
