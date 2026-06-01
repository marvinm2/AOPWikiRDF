"""COMPAT-01 byte-identity guard for the flag-off (production) output.

Phase 7 adds PROV-O activities + a primacy flag + a confidence-policy
assertion to the genes file, all gated behind ``enable_bern2``. The flag
stays ``False`` in production this phase, so the genes and main TTL files
MUST stay byte-identical to the last-known-good ``production-rdf-backup/``.

This test byte-compares the committed flag-off output in ``data/`` against
``production-rdf-backup/``. The backup is a gitignored, manually-refreshed
local snapshot, so the byte-diff is only meaningful when it was captured from
the *same* XML release as the current ``data/`` -- otherwise normal weekly
growth (new AOPs/genes) makes the files legitimately differ. The guard is
therefore **opt-in**: it runs only when the operator both has the backup on
disk AND sets ``COMPAT_CHECK_BACKUP=1`` to assert the backup is a current,
same-release snapshot. It skips (never spuriously fails) otherwise, matching
the repo's skipif convention for environment-dependent tests
(see ``tests/unit/test_qc_delta_guard.py``).

The always-on COMPAT-01 guarantee is enforced by
``test_flag_off_genes_write_emits_no_phase7_prov`` below: it re-derives a
flag-off genes file from the same gene data via ``write_genes_rdf``
(config=None) and asserts the new Phase-7 prov/primacy strings never leak
into a flag-off write. That part runs unconditionally (no backup needed), so
the code-level gate holds on every environment including CI.
"""

import os
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "production-rdf-backup")

# The flag-off files that production serves; both must match the backup.
COMPAT_FILES = ("AOPWikiRDF-Genes.ttl", "AOPWikiRDF.ttl")


# Opt-in: the byte-diff is valid only against a same-release backup snapshot.
# Require both the backup on disk AND an explicit operator opt-in, since the
# backup is gitignored local state that drifts from data/ on every weekly run.
_backup_present = os.path.exists(os.path.join(BACKUP_DIR, "AOPWikiRDF-Genes.ttl"))
_backup_opt_in = os.environ.get("COMPAT_CHECK_BACKUP") == "1"

requires_backup = pytest.mark.skipif(
    not (_backup_present and _backup_opt_in),
    reason=(
        "byte-diff guard is opt-in: set COMPAT_CHECK_BACKUP=1 with a current, "
        "same-release production-rdf-backup/ snapshot on disk to enable it"
    ),
)


@requires_backup
@pytest.mark.parametrize("fname", COMPAT_FILES)
def test_flag_off_data_is_byte_identical_to_backup(fname):
    """Each committed flag-off TTL must equal the backup byte-for-byte."""
    data_path = os.path.join(DATA_DIR, fname)
    backup_path = os.path.join(BACKUP_DIR, fname)

    assert os.path.exists(data_path), f"missing flag-off output {data_path}"
    assert os.path.exists(backup_path), f"missing backup {backup_path}"

    with open(data_path, "rb") as a, open(backup_path, "rb") as b:
        assert a.read() == b.read(), (
            f"{fname} drifted from production-rdf-backup/ (COMPAT-01 breach)"
        )


def test_flag_off_genes_write_emits_no_phase7_prov():
    """A flag-off genes write must contain none of the Phase-7 prov emission.

    Runs without the backup so the gate is enforced on every environment.
    """
    from aopwiki_rdf.rdf.writer import write_genes_rdf

    gene_data = {
        "kedict": {
            "100": {
                "dc:identifier": "aop.events:100",
                "edam:data_1025": ["hgnc:A", "hgnc:B"],
            }
        },
        "kerdict": {},
        "hgnclist": [],
        "geneiddict": {},
        "listofentrez": [],
        "listofensembl": [],
        "listofuniprot": [],
        "symbol_lookup": {},
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
        write_genes_rdf(out, gene_data)  # config=None -> flag off
        content = open(out).read()

    for forbidden in (
        "prov:Activity",
        "prov:wasGeneratedBy",
        ":isFeaturedMethod",
        ":minConfidence",
        "@prefix prov:",
        ":BERN2NERMapping",
        ":RegexGeneMapping",
    ):
        assert forbidden not in content, (
            f"flag-off genes write leaked Phase-7 token {forbidden!r}"
        )
