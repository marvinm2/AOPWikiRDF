"""Tests for the two-sided gene-association delta guard.

The guard was originally one-directional: it failed on a drop and said nothing
about a rise. That meant a matcher regression admitting false positives shipped
silently, while a deliberate precision fix -- whose entire purpose is to remove
associations -- tripped the alarm and looked identical to a data-loss incident.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from qc_delta_guard import compare  # noqa: E402

PREFIXES = (
    '@prefix edam: <http://edamontology.org/> .\n'
    '@prefix ex: <http://e.org/> .\n'
)

GENES_FILE = 'AOPWikiRDF-Genes.ttl'
MAIN_FILE = 'AOPWikiRDF.ttl'


def write_ttl(path, gene_assocs, other=50):
    with open(path, 'w') as f:
        f.write(PREFIXES)
        for i in range(gene_assocs):
            f.write(f'ex:e{i} edam:data_1025 ex:g{i} .\n')
        for i in range(other):
            f.write(f'ex:e{i} ex:p ex:o{i} .\n')


@pytest.fixture
def pair(tmp_path):
    """Return a (baseline_path, make_new) pair for the Genes file."""
    base = tmp_path / 'base'
    new = tmp_path / 'new'
    base.mkdir()
    new.mkdir()
    write_ttl(base / GENES_FILE, 100)

    def make_new(gene_assocs, other=50):
        write_ttl(new / GENES_FILE, gene_assocs, other)
        return str(new / GENES_FILE)

    return str(base / GENES_FILE), make_new


def run(baseline, new_path, **kw):
    kw.setdefault('drop_pct', 0.05)
    kw.setdefault('check_genes', True)
    return compare(new_path, baseline, **kw)


# --- Ordinary weekly movement ---------------------------------------------

@pytest.mark.parametrize('count', [98, 100, 104])
def test_small_movement_passes(pair, count):
    baseline, make_new = pair
    assert run(baseline, make_new(count))['breached'] is False


# --- Drop: the BERN2-outage class -----------------------------------------

def test_large_drop_breaches(pair):
    baseline, make_new = pair
    result = run(baseline, make_new(60))

    assert result['breached'] is True
    assert any('dropped' in r for r in result['reasons'])


# --- Rise: the regression class the old guard missed -----------------------

def test_large_rise_breaches(pair):
    """A matcher admitting false positives is a quality failure too."""
    baseline, make_new = pair
    result = run(baseline, make_new(160))

    assert result['breached'] is True
    assert any('rose' in r for r in result['reasons'])


def test_rise_within_threshold_passes(pair):
    """Legitimate growth is asymmetric; the rise bar sits well above the drop bar."""
    baseline, make_new = pair
    assert run(baseline, make_new(120))['breached'] is False


# --- Declaring the change intentional --------------------------------------

def test_expected_drop_is_acknowledged_not_breached(pair):
    baseline, make_new = pair
    result = run(baseline, make_new(60), expect_gene_change='drop')

    assert result['breached'] is False
    assert any('dropped' in r for r in result['acknowledged'])


def test_expected_drop_also_covers_the_genes_file_total(pair):
    """Removing associations necessarily removes triples from -Genes.ttl.

    Without this, a declared precision fix still fails on the total-triple
    check it inevitably causes.
    """
    baseline, make_new = pair
    result = run(baseline, make_new(60), expect_gene_change='drop')

    assert result['breached'] is False
    assert any('total triples' in r for r in result['acknowledged'])


def test_declaring_a_drop_does_not_excuse_a_rise(pair):
    """The direction is the point -- this is the mistake worth catching."""
    baseline, make_new = pair
    result = run(baseline, make_new(160), expect_gene_change='drop')

    assert result['breached'] is True
    assert any('rose' in r for r in result['reasons'])


def test_expected_rise_is_acknowledged(pair):
    """For a deliberate recall improvement, e.g. enabling a new NER source."""
    baseline, make_new = pair
    result = run(baseline, make_new(160), expect_gene_change='rise')

    assert result['breached'] is False


def test_any_accepts_either_direction(pair):
    baseline, make_new = pair
    assert run(baseline, make_new(60), expect_gene_change='any')['breached'] is False
    assert run(baseline, make_new(160), expect_gene_change='any')['breached'] is False


# --- The real incident this was built from ---------------------------------

def test_the_2026_08_01_bern2_shortfall_is_still_only_a_pass(pair, tmp_path):
    """The 2026-08-01 run lost 3.1% of associations and passed silently.

    That is genuinely within the 5% band, so the guard should still pass -- the
    fix for that case is threshold tuning, not the two-sided change. Pinned so a
    later threshold edit is a deliberate decision rather than an accident.
    """
    baseline, make_new = pair
    result = run(baseline, make_new(97))

    assert result['breached'] is False
    assert result['gene_delta_pct'] == pytest.approx(-0.03, abs=0.005)


def test_report_records_the_direction_declared(pair):
    baseline, make_new = pair
    result = run(baseline, make_new(60), expect_gene_change='drop')

    assert result['gene_change_expected'] == 'drop'
    assert json.dumps(result)  # report must stay JSON-serialisable
