"""CLI argparse -> PipelineConfig wiring tests for run_conversion.

These tests prove the --enable-iri-labels and --xml-file argparse surfaces
thread through to PipelineConfig. They assert on the constructed config only
and never invoke main() or run a real conversion -- build_config() parses args
and builds the config without reaching any network or file I/O, so no mocking
is required.
"""

import gzip

from pathlib import Path

from run_conversion import build_config

from aopwiki_rdf import pipeline
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


# --- _stage_parse byte-neutral branch (COMPAT-01, A1) ----------------------

_MINIMAL_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<data xmlns="http://www.aopkb.org/aop-xml">\n'
    "</data>\n"
)


def _stub_downstream_parse(monkeypatch, recorder):
    """Replace download + XML parsing with no-op recorders.

    Isolates _stage_parse so the test asserts only on the branch behavior
    (whether the network download was reached and what xml_path resolves to),
    never on full XML parsing and never on the network.
    """

    def _record_download(*args, **kwargs):
        recorder["download_called"] = True
        return True

    class _FakeTree:
        def getroot(self):
            return object()

    monkeypatch.setattr(pipeline, "_download_with_retry", _record_download)
    monkeypatch.setattr(pipeline, "parse", lambda path: _FakeTree())
    monkeypatch.setattr(
        pipeline, "parse_aopwiki_xml", lambda path, config=None: {}
    )


def test_xml_file_flag_off_neutral(tmp_path, monkeypatch):
    """xml_file None reaches the network download; a .gz fixture skips it.

    Asserts the default-None path is byte-neutral (still downloads) and the
    pinned-snapshot path reads the committed file with no network access.
    """
    filepath = str(tmp_path) + "/"

    # --- flag-off: download IS reached ---
    recorder_off = {"download_called": False}
    _stub_downstream_parse(monkeypatch, recorder_off)
    config_off = PipelineConfig(data_dir=tmp_path, xml_file=None)
    context_off = {"filepath": filepath}
    pipeline._stage_parse(config_off, context_off)
    assert recorder_off["download_called"] is True

    # --- pinned snapshot: build a tiny .gz fixture, download NOT reached ---
    gz_path = tmp_path / "aop-wiki-xml-2026-06-18.gz"
    with gzip.open(gz_path, "wb") as f:
        f.write(_MINIMAL_XML.encode("utf-8"))

    recorder_on = {"download_called": False}
    _stub_downstream_parse(monkeypatch, recorder_on)
    config_on = PipelineConfig(data_dir=tmp_path, xml_file=gz_path)
    context_on = {"filepath": filepath}
    pipeline._stage_parse(config_on, context_on)

    assert recorder_on["download_called"] is False
    extracted = Path(filepath) / "aop-wiki-xml-2026-06-18"
    assert extracted.exists()
    assert extracted.read_text() == _MINIMAL_XML
