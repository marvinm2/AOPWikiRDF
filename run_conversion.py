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

    args = parser.parse_args()

    config = PipelineConfig(
        data_dir=Path(args.output_dir),
        log_level=args.log_level,
    )
    main(config)


if __name__ == "__main__":
    cli()
