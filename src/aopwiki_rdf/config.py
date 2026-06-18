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
    # When a BERN2 lookup fails for a KE description (the hosted API is
    # unreachable / all retries exhausted), degrade gracefully to the regex
    # genes already present in edam:data_1025 rather than unioning an empty
    # NER set (NER-04). The degraded KE keeps its regex genes intact, is
    # flagged _ner_degraded for audit, and the run logs a loud ERROR plus a
    # coverage metric. INERT unless enable_bern2 is True -- and enable_bern2
    # itself defaults False, so the default production run is byte-identical
    # regardless of this flag. Set False to restore the prior union-with-empty
    # behaviour on failure.
    ner_fallback_on_failure: bool = True

    # External-IRI labeling (Phase 8: infrastructure first, flag off).
    # When enable_iri_labels is True, the writer emits a single untagged
    # rdfs:label co-located with dc:source on external/component IRIs and on
    # minted+external predicates, sourced from the in-memory label maps
    # (no new network calls -- LABEL-02), and the pipeline writes the honest
    # label-coverage-report.json artifact (LABEL-04 / D-07). Default False
    # reproduces the prior output bytes exactly (COMPAT-01) and is NOT flipped
    # in production this phase.
    enable_iri_labels: bool = False

    # Pinned-snapshot knob (COMPAT-01). When set, _stage_parse reads this XML
    # file (gunzip if .gz) instead of downloading config.aopwiki_xml_url, so the
    # COMPAT gate can regenerate the pipeline deterministically against a
    # committed snapshot rather than date.today() + a live network fetch.
    # Default None keeps the current network download path -- byte-identical to
    # prior production output (A1).
    xml_file: Path | None = None

    def __post_init__(self):
        """Ensure path-typed fields are Path objects."""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.ner_cache_dir, str):
            self.ner_cache_dir = Path(self.ner_cache_dir)
        if isinstance(self.xml_file, str):
            self.xml_file = Path(self.xml_file)
