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
    emit_legacy_predicates: bool = True
    filter_arr_aops: bool = False

    # BERN2 NER+EL gene mapping (Phase A: code only, flag off).
    # When enable_bern2 is True, the pipeline supplements the regex
    # gene_mapper with BERN2-derived HGNC IDs from KE/KER descriptions.
    # See prototypes/ner_el_spike/REPORT.md for the feasibility evidence.
    enable_bern2: bool = False
    bern2_url: str = "http://bern2.korea.ac.kr/plain"
    ner_cache_dir: Path = field(default_factory=lambda: Path("data/cache/bern2/"))
    # Minimum BERN2 confidence (prob) for a gene annotation to be kept.
    # The low-prob tail is dominated by entity-linking errors (HTML
    # entities, drug names, generic-word mislinks); 0.70 removes ~3% of
    # NER-only gene associations at ~90% precision. Annotations with no
    # prob are kept. Set to 0.0 to disable filtering.
    ner_min_prob: float = 0.70

    def __post_init__(self):
        """Ensure path-typed fields are Path objects."""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.ner_cache_dir, str):
            self.ner_cache_dir = Path(self.ner_cache_dir)
