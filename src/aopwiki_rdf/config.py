"""Pipeline configuration dataclass."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineConfig:
    """Pipeline configuration with production defaults.

    All fields have sensible defaults matching the current production
    constants in AOP-Wiki_XML_to_RDF_conversion.py (lines 36-43).
    """

    data_dir: Path = field(default_factory=lambda: Path("data/"))
    bridgedb_url: str = "https://webservice.bridgedb.org/Human/"
    aopwiki_xml_url: str = "https://aopwiki.org/downloads/aop-wiki-xml.gz"
    promapping_url: str = "https://proconsortium.org/download/current/promapping.txt"
    hgnc_download_url: str = (
        "https://www.genenames.org/cgi-bin/download/custom"
        "?col=gd_hgnc_id&col=gd_app_sym&col=gd_app_name"
        "&col=gd_prev_sym&col=gd_aliases&col=gd_pub_acc_ids"
        "&col=md_ensembl_id&status=Approved&format=text&submit=submit"
    )
    max_retries: int = 3
    request_timeout: int = 30
    log_level: str = "INFO"
    hgnc_min_genes: int = 19000

    def __post_init__(self):
        """Ensure data_dir is a Path object."""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
