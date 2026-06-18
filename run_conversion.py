#!/usr/bin/env python3
"""Wrapper script for AOP-Wiki RDF conversion.

Constructs a PipelineConfig from CLI arguments and calls the pipeline
main() function. No exec(), no string replacement.
"""

import argparse
from pathlib import Path

from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.pipeline import main


def build_config(argv=None):
    """Parse CLI arguments and construct a PipelineConfig.

    Testability-only helper: builds the argument parser, parses ``argv``
    (or ``sys.argv`` when None), and returns the constructed PipelineConfig.
    Does NOT run the pipeline -- callers that want to run it should pass the
    returned config to ``main()`` (see ``cli()``).
    """
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
    parser.add_argument(
        "--enable-iri-labels",
        action="store_true",
        help=(
            "Enable external-IRI labeling: emit a single untagged rdfs:label "
            "co-located with dc:source on external/component IRIs, sourced "
            "from in-memory label maps (no new network calls). OFF by default "
            "until the production flip -- the default (flag-off) run stays "
            "byte-identical to current output."
        ),
    )

    args = parser.parse_args(argv)

    return PipelineConfig(
        data_dir=Path(args.output_dir),
        log_level=args.log_level,
        enable_bern2=args.enable_bern2,
        enable_iri_labels=args.enable_iri_labels,
    )


def cli():
    config = build_config()
    main(config)


if __name__ == "__main__":
    cli()
