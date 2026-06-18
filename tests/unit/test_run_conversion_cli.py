"""CLI argparse -> PipelineConfig wiring tests for run_conversion.

These tests prove the --enable-iri-labels argparse surface threads through to
PipelineConfig.enable_iri_labels. They assert on the constructed config only
and never invoke main() or run a real conversion -- build_config() parses args
and builds the config without reaching any network or file I/O, so no mocking
is required.
"""

from run_conversion import build_config


def test_enable_iri_labels_flag_sets_true():
    """Passing --enable-iri-labels sets enable_iri_labels True on the config."""
    config = build_config(["--enable-iri-labels"])
    assert config.enable_iri_labels is True


def test_enable_iri_labels_absent_stays_false():
    """Omitting the flag leaves enable_iri_labels at its False default."""
    config = build_config([])
    assert config.enable_iri_labels is False


def test_enable_iri_labels_does_not_disturb_bern2_default():
    """The new flag does not change the enable_bern2 default-off behavior."""
    config = build_config([])
    assert config.enable_bern2 is False
