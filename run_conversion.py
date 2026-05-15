#!/usr/bin/env python3
"""Wrapper script for AOP-Wiki RDF conversion.

Constructs a PipelineConfig from CLI arguments and calls the pipeline
main() function. No exec(), no string replacement.
"""

import argparse
from pathlib import Path

from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.pipeline import main


def cli():
    parser = argparse.ArgumentParser(
        description="Run AOP-Wiki XML to RDF conversion"
    )
    parser.add_argument(
        "--output-dir",
        default="data/",
        help="Output directory for generated files (default: data/)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--enable-bern2",
        action="store_true",
        help=(
            "Enable BERN2 NER+EL gene enrichment of Key Event descriptions. "
            "Requires a warm cache at data/cache/bern2/ (see "
            "scripts/warm_bern2_cache.py) -- without one the first run "
            "annotates the full corpus inline over the hosted API."
        ),
    )

    args = parser.parse_args()

    config = PipelineConfig(
        data_dir=Path(args.output_dir),
        log_level=args.log_level,
        enable_bern2=args.enable_bern2,
    )
    main(config)


if __name__ == "__main__":
    cli()
