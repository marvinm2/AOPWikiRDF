"""Main pipeline entry point for AOP-Wiki RDF conversion.

Transitional module for Phase 1: presents a clean main(config) API
while internally delegating to the monolith script. The internal
exec() is removed in Phase 2 when all modules are extracted.
"""

import logging
import os
import sys
from pathlib import Path

from aopwiki_rdf.config import PipelineConfig

logger = logging.getLogger(__name__)

# Path to the monolith script (relative to repository root)
_MONOLITH_FILENAME = "AOP-Wiki_XML_to_RDF_conversion.py"


def _find_monolith() -> Path:
    """Locate the monolith script.

    Searches in order:
    1. Current working directory
    2. Directory of this file's parent package (repo root)
    """
    # Try cwd first
    cwd_path = Path.cwd() / _MONOLITH_FILENAME
    if cwd_path.is_file():
        return cwd_path

    # Try relative to package location (src/aopwiki_rdf/ -> repo root)
    pkg_root = Path(__file__).resolve().parent.parent.parent
    pkg_path = pkg_root / _MONOLITH_FILENAME
    if pkg_path.is_file():
        return pkg_path

    raise FileNotFoundError(
        f"Cannot find {_MONOLITH_FILENAME} in {Path.cwd()} or {pkg_root}"
    )


def _resolve_static_files(config: PipelineConfig) -> None:
    """Ensure static files are available in the data directory.

    Replicates the static file resolution logic from the old
    run_conversion.py (search data/, ./, data-test-local/).
    """
    import shutil

    static_files = ["typelabels.txt", "HGNCgenes.txt"]
    search_dirs = [Path("data/"), Path("./"), Path("data-test-local/")]

    data_dir = config.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    for static_file in static_files:
        dest_path = data_dir / static_file

        if not dest_path.exists():
            copied = False
            for search_dir in search_dirs:
                source_path = search_dir / static_file
                if source_path.exists():
                    logger.info(
                        f"Copying {static_file} from {search_dir} to {data_dir}"
                    )
                    shutil.copy2(str(source_path), str(dest_path))
                    copied = True
                    break

            if not copied:
                logger.warning(
                    f"Required file {static_file} not found in any of: "
                    f"{', '.join(str(d) for d in search_dirs)}"
                )


def main(config: PipelineConfig | None = None) -> None:
    """Run the full AOP-Wiki XML to RDF conversion pipeline.

    Parameters
    ----------
    config : PipelineConfig, optional
        Pipeline configuration. Uses defaults if not provided.
    """
    if config is None:
        config = PipelineConfig()

    # --- Setup logging (must be in main, not at module level) ---
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("aop_conversion.log"),
        ],
    )

    logger.info("Starting AOP-Wiki RDF pipeline")
    logger.info(f"Configuration: data_dir={config.data_dir}, log_level={config.log_level}")

    # --- Resolve static files ---
    _resolve_static_files(config)

    # --- Locate and execute the monolith ---
    monolith_path = _find_monolith()
    logger.info(f"Using monolith script: {monolith_path}")

    script_content = monolith_path.read_text(encoding="utf-8")

    # Replace module-level constants with config values.
    # This is the same string-replacement approach the old run_conversion.py
    # used, but it is now INTERNAL to the pipeline module. The public API
    # (run_conversion.py -> main(config)) is clean.
    replacements = {
        "DATA_DIR = 'data/'": f"DATA_DIR = '{config.data_dir}/'".replace("//", "/"),
        "BRIDGEDB_URL = 'https://webservice.bridgedb.org/Human/'": (
            f"BRIDGEDB_URL = '{config.bridgedb_url}'"
        ),
        "AOPWIKI_XML_URL = 'https://aopwiki.org/downloads/aop-wiki-xml.gz'": (
            f"AOPWIKI_XML_URL = '{config.aopwiki_xml_url}'"
        ),
        "PROMAPPING_URL = 'https://proconsortium.org/download/current/promapping.txt'": (
            f"PROMAPPING_URL = '{config.promapping_url}'"
        ),
        "MAX_RETRIES = 3": f"MAX_RETRIES = {config.max_retries}",
        "REQUEST_TIMEOUT = 30": f"REQUEST_TIMEOUT = {config.request_timeout}",
    }

    for old, new in replacements.items():
        script_content = script_content.replace(old, new)

    # Replace logging level
    script_content = script_content.replace(
        "level=logging.INFO",
        f"level=logging.{config.log_level}",
    )

    # Execute with the current global namespace
    exec(compile(script_content, str(monolith_path), "exec"), globals())

    logger.info("AOP-Wiki RDF pipeline completed successfully")
