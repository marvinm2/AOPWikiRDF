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


def test_bern2_on_labels_off_emits_no_minted_predicate_labels():
    """bern2-ON / labels-OFF: the provenance block is emitted but the minted
    predicate rdfs:label rows are NOT (double-gate, WR-03).

    GENES_MINTED_PREDICATE_LABELS is double-gated (``if genes_provenance:``
    then ``if emit_labels:``). A production run with ``enable_bern2=True`` but
    ``enable_iri_labels=False`` must stay byte-identical to the bern2-on/labels-off
    baseline: the provenance activity block (``:BERN2NERMapping`` etc.) is present,
    but none of the minted-predicate label rows leak in. Guards against a future
    edit that accidentally un-nests the ``emit_labels`` check.
    """
    import types

    from aopwiki_rdf.rdf.writer import write_genes_rdf

    config = types.SimpleNamespace(
        enable_bern2=True,
        enable_iri_labels=False,
        emit_legacy_predicates=False,
    )

    gene_data = {
        "kedict": {}, "kerdict": {}, "hgnclist": [],
        "geneiddict": {}, "listofentrez": [], "listofensembl": [],
        "listofuniprot": [], "symbol_lookup": {},
    }

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
        write_genes_rdf(out, gene_data, config=config)
        content = open(out).read()

    # The provenance activity layer IS emitted (bern2 is on).
    assert ":BERN2NERMapping" in content, (
        "bern2-on genes write must still emit the PROV-O activity block"
    )

    # The minted-PREDICATE rdfs:label rows must NOT appear (labels flag is off).
    for forbidden in (
        ":geneDetectedByNER rdfs:label",
        ":geneDetectedByRegex rdfs:label",
        ":isFeaturedMethod rdfs:label",
        ":minConfidence rdfs:label",
    ):
        assert forbidden not in content, (
            f"bern2-on/labels-off genes write leaked minted predicate label "
            f"{forbidden!r} (double-gate breach, WR-03)"
        )


def test_flag_off_emits_no_iri_labels():
    """A flag-off write must emit NO new external-IRI rdfs:label (Phase 8).

    Always-on COMPAT-01 guard (no backup needed): builds small literal
    entities/gene_data whose chemical-xref, gene-xref, and component lists are
    populated, writes both the main and genes files with ``config=None`` (flag
    off), and asserts that NO ``rdfs:label`` appears on any external-xref or
    component subject. The pre-existing HGNC/Stressor/typelabels labels
    legitimately exist when the flag is off; this test populates ONLY subjects
    that must stay unlabeled when off (no HGNC list, no typelabels.txt, no
    stressors), so the flag-off baseline for these subjects is exactly zero
    ``rdfs:label`` occurrences. The byte-identity invariant is therefore a
    clean ``rdfs:label`` count of 0 on the produced output.
    """
    from aopwiki_rdf.rdf.writer import write_aop_rdf, write_genes_rdf

    with tempfile.TemporaryDirectory() as tmp:
        prefix_csv = os.path.join(tmp, "prefixes.csv")
        with open(prefix_csv, "w") as f:
            f.write("prefix,uri\n")
            for p, u in (
                ("dc", "http://purl.org/dc/elements/1.1/"),
                ("dcterms", "http://purl.org/dc/terms/"),
                ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
                ("owl", "http://www.w3.org/2002/07/owl#"),
                ("cheminf", "http://semanticscience.org/resource/CHEMINF_"),
                ("chebi", "https://identifiers.org/chebi/"),
                ("cas", "https://identifiers.org/cas/"),
                ("edam", "http://edamontology.org/"),
                ("ncbigene", "https://identifiers.org/ncbigene/"),
                ("uniprot", "https://identifiers.org/uniprot/"),
                ("ncbitaxon", "http://purl.obolibrary.org/obo/NCBITaxon_"),
                ("go", "http://purl.obolibrary.org/obo/GO_"),
                ("aopo", "http://aopkb.org/aop_ontology#"),
                ("sh", "http://www.w3.org/ns/shacl#"),
                ("xsd", "http://www.w3.org/2001/XMLSchema#"),
            ):
                f.write(f"{p},{u}\n")

        # Main file: chemical + gene xrefs + a taxonomy + a biological-process
        # component, but NO hgnclist (whose rdfs:label is always-on) and no
        # typelabels.txt on disk (its class labels are always-on).
        entities = {
            "aopdict": {}, "kedict": {}, "kerdict": {}, "strdict": {},
            "taxdict": {
                "9606": {
                    "dc:identifier": "ncbitaxon:9606",
                    "dc:title": "Homo sapiens",
                    "dc:source": "NCBI",
                }
            },
            "bioprodict": {
                "p1": {
                    "dc:identifier": "go:0008150",
                    "dc:title": '"biological_process"',
                    "dc:source": '"GO"',
                }
            },
            "bioobjdict": {}, "bioactdict": {}, "prodict": {}, "chedict": {},
            "hgnclist": [], "ncbigenelist": ["ncbigene:7157"],
            "uniprotlist": ["uniprot:P04637"],
            "listofcas": ["cas:50-00-0"], "listofinchikey": [], "listofcomptox": [],
            "listofchebi": ["chebi:16842"], "listofchemspider": [], "listofwikidata": [],
            "listofchembl": [], "listofpubchem": [], "listofdrugbank": [],
            "listofkegg": [], "listoflipidmaps": [], "listofhmdb": [],
            "symbol_lookup": {},
            # Maps present but the flag is OFF -> must be ignored entirely.
            "chem_label_by_iri": {"chebi:16842": "Formaldehyde", "cas:50-00-0": "Formaldehyde"},
            "gene_label_by_iri": {"ncbigene:7157": "TP53", "uniprot:P04637": "TP53"},
        }
        main_out = os.path.join(tmp, "AOPWikiRDF.ttl")
        write_aop_rdf(main_out, entities, prefix_csv)  # config=None -> flag off
        main_content = open(main_out).read()

        gene_data = {
            "kedict": {}, "kerdict": {}, "hgnclist": [],
            "geneiddict": {}, "listofentrez": ["ncbigene:7157"],
            "listofensembl": ["ensembl:ENSG00000141510"],
            "listofuniprot": ["uniprot:P04637"],
            "symbol_lookup": {},
            "gene_label_by_iri": {
                "ncbigene:7157": "TP53",
                "ensembl:ENSG00000141510": "TP53",
                "uniprot:P04637": "TP53",
            },
        }
        genes_out = os.path.join(tmp, "AOPWikiRDF-Genes.ttl")
        write_genes_rdf(genes_out, gene_data)  # config=None -> flag off
        genes_content = open(genes_out).read()

    # These outputs populate ONLY subjects that are unlabeled when the flag is
    # off (no hgnclist, no typelabels.txt, no stressors). So the flag-off
    # baseline is exactly zero rdfs:label occurrences.
    assert "rdfs:label" not in main_content, (
        "flag-off main write leaked an rdfs:label on an external/component subject"
    )
    assert "rdfs:label" not in genes_content, (
        "flag-off genes write leaked an rdfs:label on a gene-xref subject"
    )
