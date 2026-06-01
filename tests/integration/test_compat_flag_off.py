"""COMPAT-01 byte-identity guard for the flag-off (production) output.

Phase 7 adds PROV-O activities + a primacy flag + a confidence-policy
assertion to the genes file, all gated behind ``enable_bern2``. The flag
stays ``False`` in production this phase, so the genes and main TTL files
MUST stay byte-identical to the last-known-good ``production-rdf-backup/``.

This test byte-compares the committed flag-off output in ``data/`` against
``production-rdf-backup/``. It is skipped (not failed) when the backup
directory is absent, matching the repo's skipif convention for
environment-dependent tests (see ``tests/unit/test_qc_delta_guard.py``).

It also re-derives a flag-off genes file from the same gene data via
``write_genes_rdf`` (config=None) and asserts the new Phase-7 prov/primacy
strings never leak into a flag-off write -- this part runs unconditionally
(no backup needed) so the gate is enforced even on CI without the backup.
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


requires_backup = pytest.mark.skipif(
    not os.path.exists(os.path.join(BACKUP_DIR, "AOPWikiRDF-Genes.ttl")),
    reason="production-rdf-backup/ absent; byte-diff guard is environment-dependent",
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
