"""CLI argparse -> PipelineConfig wiring tests for run_conversion.

These tests prove the --enable-iri-labels and --xml-file argparse surfaces
thread through to PipelineConfig. They assert on the constructed config only
and never invoke main() or run a real conversion -- build_config() parses args
and builds the config without reaching any network or file I/O, so no mocking
is required.
"""

from pathlib import Path

from run_conversion import build_config

from aopwiki_rdf.config import PipelineConfig


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


# --- --xml-file knob (COMPAT-01, D-04) -------------------------------------


def test_config_xml_file_defaults_none():
    """PipelineConfig() with no args has xml_file None (byte-neutral default)."""
    assert PipelineConfig().xml_file is None


def test_config_xml_file_str_coerced_to_path():
    """A str xml_file is coerced to a pathlib.Path in __post_init__."""
    config = PipelineConfig(xml_file="some/path.gz")
    assert isinstance(config.xml_file, Path)
    assert str(config.xml_file) == "some/path.gz"


def test_build_config_xml_file_absent_is_none():
    """build_config([]) returns a config whose xml_file is None."""
    config = build_config([])
    assert config.xml_file is None


def test_build_config_xml_file_set_coerced_to_path():
    """--xml-file PATH yields a Path-typed xml_file equal to PATH."""
    config = build_config(
        ["--xml-file", "data/compat-golden/aop-wiki-xml-2026-06-18.gz"]
    )
    assert isinstance(config.xml_file, Path)
    assert str(config.xml_file) == "data/compat-golden/aop-wiki-xml-2026-06-18.gz"


def test_build_config_xml_file_coexists_with_enable_flags():
    """--xml-file and the --enable-* flags set independently and coexist."""
    config = build_config(
        ["--xml-file", "x.gz", "--enable-bern2", "--enable-iri-labels"]
    )
    assert str(config.xml_file) == "x.gz"
    assert config.enable_bern2 is True
    assert config.enable_iri_labels is True
