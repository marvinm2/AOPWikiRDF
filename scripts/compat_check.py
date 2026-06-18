"""COMPAT closing gate: full-corpus flag-off byte-identity proof (COMPAT-01).

What this proves
----------------
The Phase 12 production flip turns the ``enable_bern2`` / ``enable_iri_labels``
flags ON. This gate proves that doing so does NOT silently mutate or drop any
subject the *current* (flag-off) production output emits: it regenerates the
pipeline TWICE against the SAME pinned XML snapshot -- once flags-off, once
flags-on -- masks the four run-varying date-token families, and compares.

Dual comparison (D-01)
----------------------
1. off-vs-on  -- the HARD gate. Both runs happen back-to-back in ONE invocation
   against the same snapshot, so they hit the same BridgeDb/HGNC state; the
   comparison is therefore IMMUNE to upstream service drift. It is an
   ADDITIVE-SUBSET check: flags-on may legitimately ADD subjects (e.g.
   ``prov:Activity`` blocks) and ADD predicates to existing subjects (e.g.
   ``rdfs:label``); it BREACHES only when a subject block present in the
   flag-off output is ABSENT or CHANGED in the flag-on output. This alone
   decides the exit code.
2. off-vs-golden -- ADVISORY/safety only. A full byte-identity compare of the
   fresh flag-off corpus against the committed golden (a prior flag-off run).
   It MAY legitimately differ on BridgeDb drift between the golden's capture and
   now (RESEARCH Pitfall 2), so it never fails the gate on its own.

Masking method (D-03)
---------------------
Exactly FOUR run-varying token families are masked, line/predicate-anchored
(NOT a bare ``\\d{4}-\\d{2}-\\d{2}``, which would clobber stable XML dates). The
mask regexes are kept in sync with the writer's date emitters --
``src/aopwiki_rdf/rdf/writer.py`` lines 794 (Enriched header), 1006/1017/1031/
1040 (Void ``pav:createdOn``^^xsd:date), 1051/1058 (Void ``pav:importedOn``
ctime), 1094 (ServiceDescription ``dcterms:modified``^^xsd:dateTime). The
XML-sourced bare ``dcterms:created``/``dcterms:modified`` literals (no datatype
tag) are left UNTOUCHED -- the datatype-anchored masks #2/#4 do not match them.

No canonicalization (D-05)
--------------------------
The gate relies ONLY on date-masking plus the writer's existing ``sorted()``
iteration order. There is NO blank-node canonicalization and NO
``rdflib.serialize`` round-trip -- the comparison is on the masked raw bytes,
chunked per subject block.

Complements, does not duplicate (D-07)
--------------------------------------
This gate provides full-corpus byte-identity + per-subject ``difflib`` diffs. It
does NOT re-implement the token-leak unit checks in
``tests/integration/test_compat_flag_off.py`` -- those stay the code-level guard;
this is the corpus-level proof.

Exit-code contract
------------------
``main`` returns 0 when the HARD off-vs-on comparison is clean, 1 on any breach.
A missing golden file or missing fresh output is a HARD breach (cannot prove
safety) -- mirrors the missing-file idiom of ``scripts/qc_delta_guard.py``.
"""

import argparse
import difflib
import os
import re
import sys
import tempfile

# Module constants -------------------------------------------------------------

DEFAULT_GOLDEN_DIR = "data/compat-golden"
DEFAULT_REPORT_PATH = "compat-diff-report.txt"

# Cap the number of differing subject blocks rendered into the diff report so a
# pathological run cannot emit a 16 MB blob (T-11-08).
DEFAULT_MAX_BLOCKS = 50

# The flag-off corpus files the gate compares. ServiceDescription.ttl carries
# the dcterms:modified^^xsd:dateTime token (family #4); the others carry the
# header/pav tokens (families #1-#3).
CORPUS_FILES = (
    "AOPWikiRDF.ttl",
    "AOPWikiRDF-Genes.ttl",
    "AOPWikiRDF-Enriched.ttl",
    "AOPWikiRDF-Void.ttl",
    "ServiceDescription.ttl",
)

# The FOUR run-varying date-token families (D-03). Each pattern is
# line/predicate-anchored so it matches ONLY the writer-emitted wall-clock
# token, never an XML-sourced bare literal. Kept in sync with
# src/aopwiki_rdf/rdf/writer.py date emitters:
#   1. writer.py:794         "# Generated: {datetime.date.today()}"   (Enriched header)
#   2. writer.py:1006/1017/1031/1040  pav:createdOn "{y}"^^xsd:date   (Void x4)
#   3. writer.py:1051/1058   pav:importedOn "{ctime}"                 (Void x2: HGNC + promapping)
#   4. writer.py:1094        dcterms:modified "{x.isoformat()}"^^xsd:dateTime (ServiceDescription)
# MUST NOT mask AOPWikiRDF.ttl dcterms:created/dcterms:modified bare literals:
# masks #2/#4 are datatype-anchored (^^xsd:date / ^^xsd:dateTime) so they cannot
# match the bare quoted XML dates.
MASK_PATTERNS = (
    # 1. Enriched header line.
    (re.compile(rb"^# Generated: .*$", re.MULTILINE), b"# Generated: <MASKED>"),
    # 2. Void pav:createdOn typed date (x4).
    (
        re.compile(rb'pav:createdOn\t"[^"]*"\^\^xsd:date'),
        b'pav:createdOn\t"<MASKED>"^^xsd:date',
    ),
    # 3. Void pav:importedOn ctime (x2: HGNC + promapping). Untyped quoted
    #    literal -- still safe because the predicate name anchors it.
    (
        re.compile(rb'pav:importedOn\t"[^"]*"'),
        b'pav:importedOn\t"<MASKED>"',
    ),
    # 4. ServiceDescription dcterms:modified typed dateTime (ServiceDescription
    #    ONLY -- the ^^xsd:dateTime tag is what distinguishes it from the bare
    #    XML-sourced dcterms:modified in AOPWikiRDF.ttl).
    (
        re.compile(rb'dcterms:modified "[^"]*"\^\^xsd:dateTime'),
        b'dcterms:modified "<MASKED>"^^xsd:dateTime',
    ),
)


# Pure helpers -----------------------------------------------------------------

def mask(raw):
    """Mask the four run-varying date-token families in a TTL byte string.

    Byte-in / byte-out. Applies each of the four anchored regexes via
    ``re.sub`` (NO rdflib -- D-05). Idempotent: ``mask(mask(x)) == mask(x)``
    because every replacement target is itself non-matching once masked.

    Parameters
    ----------
    raw : bytes
        Raw TTL file content.

    Returns
    -------
    bytes
        The content with all four families replaced by ``<MASKED>`` and every
        XML-sourced bare literal left untouched.
    """
    out = raw
    for pattern, replacement in MASK_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def subject_blocks(masked):
    """Split a masked TTL byte string into per-subject blocks.

    The writer emits subject blocks separated by blank lines (``\\n\\n``;
    RESEARCH Pattern 3). Empty/whitespace-only chunks are dropped.

    Parameters
    ----------
    masked : bytes

    Returns
    -------
    list of bytes
        One entry per non-empty subject block.
    """
    return [b for b in masked.split(b"\n\n") if b.strip()]


def first_subject(block):
    """Return the leading subject IRI token of a subject block.

    The first whitespace-delimited token of the first non-comment line is the
    subject. Falls back to the first token of the block when no non-comment
    line exists.
    """
    for line in block.split(b"\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(b"#"):
            continue
        return stripped.split()[0]
    tokens = block.split()
    return tokens[0] if tokens else b""


def diff_report(golden, fresh, fname, max_blocks=DEFAULT_MAX_BLOCKS):
    """Build a per-subject unified-diff report for two masked corpora.

    Chunks both inputs into subject blocks keyed by subject IRI and emits a
    ``difflib.unified_diff`` body for every subject that is missing from one
    side or whose block content differs (D-07). Truncated after ``max_blocks``
    differing subjects.

    Parameters
    ----------
    golden, fresh : bytes
        Masked TTL byte strings (golden/expected vs fresh/actual).
    fname : str
        File name, used as the diff header label.
    max_blocks : int
        Maximum number of differing subjects to render.

    Returns
    -------
    str
        Human-readable diff; empty string when the two are byte-identical.
    """
    if golden == fresh:
        return ""

    golden_by_subj = {}
    for block in subject_blocks(golden):
        golden_by_subj.setdefault(first_subject(block), block)
    fresh_by_subj = {}
    for block in subject_blocks(fresh):
        fresh_by_subj.setdefault(first_subject(block), block)

    all_subjects = list(golden_by_subj)
    for subj in fresh_by_subj:
        if subj not in golden_by_subj:
            all_subjects.append(subj)

    lines = []
    rendered = 0
    for subj in all_subjects:
        g_block = golden_by_subj.get(subj)
        f_block = fresh_by_subj.get(subj)
        if g_block == f_block:
            continue
        if rendered >= max_blocks:
            lines.append(
                f"... (diff truncated after {max_blocks} differing subjects)"
            )
            break
        subj_label = subj.decode("utf-8", "replace")
        g_text = (g_block or b"").decode("utf-8", "replace").splitlines()
        f_text = (f_block or b"").decode("utf-8", "replace").splitlines()
        diff = difflib.unified_diff(
            g_text,
            f_text,
            fromfile=f"{fname}::golden::{subj_label}",
            tofile=f"{fname}::fresh::{subj_label}",
            lineterm="",
        )
        lines.append(f"=== subject {subj_label} ===")
        lines.extend(diff)
        lines.append("")
        rendered += 1

    return "\n".join(lines)


# Regeneration -----------------------------------------------------------------

def regenerate(xml_file, out_dir, enable_flags):
    """Run the pipeline once into ``out_dir`` against the pinned ``xml_file``.

    Stable, monkeypatchable seam: tests replace this with a fixture writer so
    the gate stays offline and fast. The production path builds a
    ``PipelineConfig`` with ``xml_file`` pinned (Plan 11-01's ``--xml-file``
    knob) and the flag pair set per ``enable_flags``, then calls the pipeline
    ``main``. ``out_dir`` is created if absent.

    Parameters
    ----------
    xml_file : str
        Path to the committed XML snapshot (.xml or .gz).
    out_dir : str
        Directory to write the regenerated TTLs into.
    enable_flags : bool
        ``False`` -> flags-off run; ``True`` -> enable_bern2 + enable_iri_labels.

    Returns
    -------
    str
        ``out_dir`` (for chaining).
    """
    # Imported lazily so the masker/diff helpers + tests load without the
    # pipeline (and its heavy deps) being importable.
    from pathlib import Path

    from aopwiki_rdf.config import PipelineConfig
    from aopwiki_rdf.pipeline import main as pipeline_main

    os.makedirs(out_dir, exist_ok=True)
    config = PipelineConfig(
        data_dir=Path(out_dir),
        xml_file=Path(xml_file),
        enable_bern2=enable_flags,
        enable_iri_labels=enable_flags,
    )
    pipeline_main(config)
    return out_dir


def _read_masked(directory, filename):
    """Read+mask a corpus file; return None when it does not exist."""
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return mask(fh.read())


def _compare_dirs(expected_dir, actual_dir, mode, max_blocks):
    """Compare two TTL dirs per ``mode``; return (breached, reasons, report_text).

    ``mode`` is one of ``"identity"`` (full byte-identity per file -- used for
    off-vs-golden) or ``"additive"`` (subject-subset; ``actual`` may add
    subjects/predicates but must not drop or change a subject present in
    ``expected`` -- used for off-vs-on).
    """
    reasons = []
    report_chunks = []

    for filename in CORPUS_FILES:
        expected = _read_masked(expected_dir, filename)
        actual = _read_masked(actual_dir, filename)

        if expected is None:
            reasons.append(f"missing expected file: {os.path.join(expected_dir, filename)}")
            continue
        if actual is None:
            reasons.append(f"missing actual file: {os.path.join(actual_dir, filename)}")
            continue

        if mode == "identity":
            if expected != actual:
                reasons.append(f"byte-identity mismatch in {filename}")
                report_chunks.append(diff_report(expected, actual, filename, max_blocks))
        elif mode == "additive":
            changed = _additive_violations(expected, actual)
            if changed:
                for subj in changed:
                    reasons.append(
                        f"{filename}: subject {subj.decode('utf-8', 'replace')} "
                        f"absent or changed in flags-on output"
                    )
                report_chunks.append(diff_report(expected, actual, filename, max_blocks))
        else:  # pragma: no cover - guarded by argparse choices
            raise ValueError(f"unknown compare mode: {mode}")

    breached = bool(reasons)
    report_text = "\n".join(c for c in report_chunks if c)
    return breached, reasons, report_text


def _additive_violations(expected, actual):
    """Return the subjects from ``expected`` missing-or-changed in ``actual``.

    Additive-subset semantics: a subject in ``actual`` but not ``expected`` is
    fine (a flag-gated addition); a subject in ``expected`` is a violation when
    it is ABSENT from ``actual`` or its block CHANGED. Returns the list of
    offending subject IRIs (empty when additive-only).
    """
    expected_by_subj = {}
    for block in subject_blocks(expected):
        expected_by_subj.setdefault(first_subject(block), block)
    actual_by_subj = {}
    for block in subject_blocks(actual):
        actual_by_subj.setdefault(first_subject(block), block)

    violations = []
    for subj, block in expected_by_subj.items():
        actual_block = actual_by_subj.get(subj)
        if actual_block is None or actual_block != block:
            violations.append(subj)
    return violations


def run(golden_dir, xml_file, mode="both", report_path=DEFAULT_REPORT_PATH,
        max_blocks=DEFAULT_MAX_BLOCKS, off_dir=None, on_dir=None):
    """Regenerate (off+on) and run the dual comparison; write the diff report.

    Parameters
    ----------
    golden_dir : str
        Directory holding the committed golden (flag-off) TTLs.
    xml_file : str
        Pinned XML snapshot fed to both regen runs.
    mode : str
        ``"off-vs-on"`` (HARD only), ``"off-vs-golden"`` (advisory only), or
        ``"both"`` (default). The HARD comparison alone sets ``breached``.
    report_path : str
        Where to write the per-subject diff report.
    max_blocks : int
        Diff truncation cap.
    off_dir, on_dir : str, optional
        Pre-built flag-off / flag-on TTL dirs. When provided, regeneration is
        SKIPPED for that side (test seam -- lets a test supply fixture corpora
        without running the pipeline). When None, ``regenerate`` produces them
        in temp dirs.

    Returns
    -------
    dict
        ``{"breached": bool, "reasons": [...], "advisory_reasons": [...],
        "report_text": str, "mode": str}``. ``breached`` reflects ONLY the HARD
        off-vs-on comparison.
    """
    need_off = off_dir is None
    need_on = on_dir is None and mode in ("off-vs-on", "both")

    tmp = None
    if need_off or need_on:
        tmp = tempfile.mkdtemp(prefix="compat-regen-")

    if need_off:
        off_dir = os.path.join(tmp, "off")
        regenerate(xml_file, off_dir, enable_flags=False)
    if need_on:
        on_dir = os.path.join(tmp, "on")
        regenerate(xml_file, on_dir, enable_flags=True)

    reasons = []
    advisory_reasons = []
    report_chunks = []

    # HARD gate: off-vs-on additive-subset (D-01). Decides the exit code.
    if mode in ("off-vs-on", "both"):
        breached, hard_reasons, hard_report = _compare_dirs(
            off_dir, on_dir, mode="additive", max_blocks=max_blocks
        )
        reasons.extend(hard_reasons)
        if hard_report:
            report_chunks.append("# off-vs-on (HARD) diff\n" + hard_report)

    # Advisory: off-vs-golden full byte-identity (D-01). Never sets breached.
    if mode in ("off-vs-golden", "both"):
        _, adv_reasons, adv_report = _compare_dirs(
            golden_dir, off_dir, mode="identity", max_blocks=max_blocks
        )
        advisory_reasons.extend(adv_reasons)
        if adv_report:
            report_chunks.append("# off-vs-golden (ADVISORY) diff\n" + adv_report)

    report_text = "\n\n".join(report_chunks)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_text)

    return {
        "breached": bool(reasons),
        "reasons": reasons,
        "advisory_reasons": advisory_reasons,
        "report_text": report_text,
        "mode": mode,
    }


def print_report(report):
    """Print a human-readable summary of the dual comparison to stdout."""
    print("=" * 78)
    print(f"COMPAT closing gate (mode={report['mode']})")
    print("=" * 78)

    if report["reasons"]:
        print("\nHARD (off-vs-on) breaches:")
        for reason in report["reasons"]:
            print(f"  BREACH: {reason}")
    else:
        print("\nHARD (off-vs-on): clean (flags-on output is an additive superset).")

    if report["advisory_reasons"]:
        print("\nADVISORY (off-vs-golden) differences (non-blocking):")
        for reason in report["advisory_reasons"]:
            print(f"  NOTE: {reason}")

    print()
    if report["breached"]:
        print("RESULT: FAIL (COMPAT gate breached)")
    else:
        print("RESULT: PASS (flag-off byte-identity preserved)")


def main(argv=None):
    """CLI entry point. Returns 0 when the HARD comparison is clean, else 1."""
    parser = argparse.ArgumentParser(
        description="COMPAT closing gate: prove flags-on regeneration adds to "
                    "but never mutates/drops the flag-off corpus (COMPAT-01)."
    )
    parser.add_argument("--golden-dir", default=DEFAULT_GOLDEN_DIR,
                        help="Directory with the committed flag-off golden TTLs "
                             "(default: data/compat-golden)")
    parser.add_argument("--xml-file", required=True,
                        help="Pinned XML snapshot fed to both regen runs.")
    parser.add_argument("--mode", default="both",
                        choices=["off-vs-on", "off-vs-golden", "both"],
                        help="Which comparison(s) to run; only off-vs-on sets "
                             "the exit code (default: both).")
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH,
                        help="Path to write the per-subject diff report "
                             "(default: compat-diff-report.txt)")
    parser.add_argument("--max-blocks", type=int, default=DEFAULT_MAX_BLOCKS,
                        help="Max differing subjects rendered into the diff "
                             "report (default: 50)")
    args = parser.parse_args(argv)

    report = run(
        golden_dir=args.golden_dir,
        xml_file=args.xml_file,
        mode=args.mode,
        report_path=args.report_path,
        max_blocks=args.max_blocks,
    )
    print_report(report)

    return 1 if report["breached"] else 0


if __name__ == "__main__":
    sys.exit(main())
