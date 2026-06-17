---
phase: 09-xml-rdf-coverage-audit-gap-fixes-coverage-ratchet
plan: 02
subsystem: coverage-audit
tags: [xml-01, coverage-audit, json-report, attribute-axis, gap-ranking, ratchet-input]
requires:
  - vendored-aop-xml-xsd
  - coverage-allowlist
  - phase9-test-stubs
  - coverage-fixtures
provides:
  - coverage-audit-script
  - coverage-report-json
  - actionable-gap-list
affects:
  - scripts/
  - tests/unit/test_coverage_audit.py
tech-stack:
  added: []
  patterns:
    - "iterparse + el.clear() streaming enumeration (namespace-stripped, attribute axis walked)"
    - "Covered set derived from parser source via two regexes (aopxml elements + .get() attributes) — never re-import the parser"
    - "instance − covered − allowlist actionable gap diff; XSD is an informational in_xsd axis only (D-01)"
    - "Optional --snapshots-dir historical walk that degrades to a ::warning:: skip (authoritative report never depends on it)"
key-files:
  created:
    - scripts/coverage_audit.py
    - scripts/coverage-report.json
  modified:
    - tests/unit/test_coverage_audit.py
decisions:
  - "Covered ATTRIBUTE axis collected via .get('...') regex so id/key-event-id/stressor-id/taxonomy-id/process-id are never false gaps (Pitfall 1)"
  - "XSD parsed AS XML via ElementTree (xs:element/xs:attribute name/ref); xmlschema route deliberately not taken (no new dependency, T-09-SC)"
  - "Latest 2026-06-17 snapshot is authoritative (D-05); historical walk optional and informational (D-04)"
  - "Per-element record carries an int `occurrences` (latest count, what the unit test asserts) PLUS `occurrences_by_snapshot` map + `delta_vs_prev` for the richer report shape"
  - "Idempotent JSON via json.dump(indent=2, sort_keys=True) — byte-identical re-runs for stable CI/ratchet baselines"
metrics:
  duration: ~3 min
  completed: 2026-06-17
---

# Phase 9 Plan 02: Coverage Audit (XML-01) Summary

Built the re-runnable `scripts/coverage_audit.py` that enumerates the namespace-qualified element/attribute universe of an AOP-Wiki snapshot, derives the parser's covered set straight from `xml_parser.py` source (both the `aopxml + '...'` element reads AND the `.get('...')` attribute reads, killing the #1 false-gap source), diffs to an actionable gap set (`instance − covered − allowlist`), ranks gaps by `occurrences × weight`, and writes the committed `scripts/coverage-report.json`. On the authoritative 2026-06-17 snapshot: **69/95 elements covered (72.6%), 20 actionable gaps** surfaced for the Plan-03 maintainer hand-pick.

## What Was Built

### Task 1 — `coverage_audit.py`: instance universe, covered set, gap diff (commit `01e2c38`)
- **Instance enumeration** (`enumerate_instance`): `iterparse(events=('end',))` + `el.clear()` over the snapshot (`.gz` transparently handled), stripping `AOPXML_NS` and counting element local-names AND `(local, attr)` pairs. Bounded memory on the ~48 MB file. No custom XML entity resolution enabled (stdlib default — T-09-03).
- **Covered set** (`derive_covered_sets`): two regexes over the parser source — `aopxml \+ '([^']+)'` (74 elements) and `\.get\('([^']+)'\)` (10 attributes: id, key-event-id, stressor-id, taxonomy-id, process-id, object-id, action-id, chemical-id, aop-wiki-id, user-term). The parser is NOT imported (avoids its heavy transitive imports / HGNC network path); the namespace constant is re-declared verbatim.
- **Gap diff**: `gaps = instance_elements − covered_elements − allowlist`, ranked by `occurrences × semantic_weight` (weight default 1.0, overridable via `--semantic-weights`).
- **Informational XSD axis** (`parse_xsd_declared`, D-01): the vendored XSD is parsed AS XML via ElementTree to set `in_xsd` per element and an `xsd_only_count` (declared-but-never-seen). It never drives the actionable gap set.
- **Report shape** mirrors the RESEARCH proposal: per-element `covered`/`emitted_by_parser`, `is_attribute`, `allowlisted`, `occurrences` (int, latest), `occurrences_by_snapshot`, `delta_vs_prev`, `in_xsd`, `is_gap`, `rank_score`; a per-attribute `attributes` block keyed `elem@attr`; a `gaps` list; and a `summary` block.
- Removed the module-level xfail from `test_coverage_audit.py`; the four XML-01 tests (`test_audit_emits_json`, `test_attribute_axis`, `test_covered_set`, `test_allowlist`) now pass.

### Task 2 — committed report + graceful historical walk (commit `5fc553b`)
- **Optional historical walk** (`discover_snapshots`, `walk_history`, `--snapshots-dir`, `--download-missing`): when supplied and populated, enumerates each `aop-wiki-xml-YYYY-MM-DD[.gz]` snapshot and records per-snapshot `occurrences_by_snapshot` + `delta_vs_prev`. When absent/empty, prints `::warning::historical snapshots dir absent; latest-snapshot report only` and still produces the full report — the authoritative report **never depends on the historical walk** (Pitfall 6: the sibling `versions/` dir is not a CI dependency). Each quarter's coverage is computed against that quarter's own instance universe (Pitfall 3).
- **Generated the committed `scripts/coverage-report.json`** from the real latest on-disk snapshot (`data/aop-wiki-xml-2026-06-17`) with `generated_for_snapshot: 2026-06-17` and `namespace: http://www.aopkb.org/aop-xml`. **Idempotent**: two consecutive runs to separate paths produce byte-identical files (`diff` exit 0).
- Removed the last xfail (`test_no_snapshots_dir_skips`); all 5 unit tests in the file now pass. Dropped the now-unused `pytest` import.

## Ranked Actionable Gap List (maintainer hand-pick input for Plan 03 — D-06)

From `scripts/coverage-report.json` (snapshot 2026-06-17, 20 gaps ranked by `occurrences × weight`):

| rank_score | element | occ | in_xsd |
|-----------:|---------|----:|:------:|
| 3919.0 | evidence-supporting-taxonomic-applicability | 3919 | yes |
| 2923.0 | known-modulating-factors | 2923 | yes |
| 2336.0 | evidence-collection-strategy | 2336 | yes |
| 2336.0 | feedforward-feedback-loops | 2336 | yes |
| 2336.0 | quantitative-understanding | 2336 | yes |
| 2336.0 | response-response-relationship | 2336 | yes |
| 2336.0 | time-scale | 2336 | yes |
|  738.0 | exposure-characterization | 738 | yes |
|  587.0 | coaches | 587 | yes |
|  587.0 | external_links | 587 | yes |
|  587.0 | handbook-version | 587 | yes |
|  587.0 | point-of-contact | 587 | yes |
|  558.0 | biological-process-reference | 558 | no |
|  494.0 | biological-object-reference | 494 | no |
|  421.0 | chemical-reference | 421 | no |
|  421.0 | indigo-inchi-key | 421 | yes |
|  359.0 | taxonomy-reference | 359 | no |
|  128.0 | coach | 128 | yes |
|  124.0 | development-strategy | 124 | yes |
|   11.0 | biological-action-reference | 11 | no |

The high-value semantic candidates RESEARCH/D-06 flagged — `evidence-collection-strategy`, `known-modulating-factors`, `response-response-relationship`, `time-scale`, `exposure-characterization` — all surface near the top, confirming the audit is trustworthy. The `*-reference` entries (`in_xsd: false`) are vendor-specific ID-resolution plumbing the parser consumes via `.get()` on the *parent*; the maintainer should weigh whether they merit the allowlist (a Plan-03 D-06 call) rather than a mapping.

## Verification Results

- `pytest tests/unit/test_coverage_audit.py -q` → **5 passed** (all xfails removed).
- Task 1 verify (`test_audit_emits_json`, `test_attribute_axis`, `test_covered_set`, `test_allowlist`) → 4 passed.
- Task 2 verify (`test_no_snapshots_dir_skips` + report assertion) → passed; `actionable_gap_count` (20) > 0 and `generated_for_snapshot` set.
- Broader regression (`test_coverage_audit.py` + `test_coverage_ratchet.py` + `test_qc_delta_guard.py`) → **14 passed, 1 skipped, 4 xfailed** (the 4 remaining xfails are the Plan-03 gap-fix and Plan-04 per-element-guard stubs, as designed — not a defect).
- CLI on fixture exits 0; report has top-level `elements` + `summary` keys.
- Parser-consumed attributes (`id`, `key-event-id`, `stressor-id`, `taxonomy-id`) are NOT in the gap set; allowlisted `references` is `allowlisted: true` and absent from gaps.
- `git check-ignore scripts/coverage-report.json` exits 1 (tracked, not ignored).
- Idempotence: two runs → byte-identical JSON (`diff` exit 0).
- No untracked files left behind.

## Deviations from Plan

None — both tasks executed as written. Two minor judgment calls, neither a behavior change:
1. **Per-element record carries both an int `occurrences` and an `occurrences_by_snapshot` map.** The unit test asserts `rec["occurrences"] >= 1` (an int), while the RESEARCH report shape shows `occurrences` as a per-snapshot map. Rather than break either contract, the int `occurrences` is the latest-snapshot count and the per-snapshot detail lives under `occurrences_by_snapshot` + `delta_vs_prev`. Satisfies the test and the D-04 per-snapshot requirement.
2. **Removed the now-unused `pytest` import** from the test file after the last xfail marker was deleted (cleanliness; no lint hook is configured but F401 would otherwise be latent).

## Threat Model Compliance

- **T-09-03 (DoS / info disclosure via snapshot XML, mitigate):** stdlib `ElementTree` resolves no external entities by default and no custom entity resolution is enabled anywhere; `iterparse` + `el.clear()` bounds memory on the ~48 MB file.
- **T-09-04 (tampering via optional .gz download, accept):** the `--download-missing` hook feeds only the informational historical axis; a failed/corrupt historical parse degrades to a `::warning::` skip (`walk_history` try/except) and never writes the authoritative output or fails the run.
- **T-09-SC (supply-chain, mitigate):** no new package installed — stdlib only (`argparse`/`collections`/`glob`/`gzip`/`json`/`os`/`re`/`sys`/`urllib`/`xml.etree.ElementTree`). The `xmlschema` route was explicitly not taken; the XSD is parsed as plain XML. No legitimacy checkpoint required.

## Self-Check: PASSED

- `scripts/coverage_audit.py` — FOUND
- `scripts/coverage-report.json` — FOUND (not gitignored)
- `tests/unit/test_coverage_audit.py` — FOUND (5 tests pass, 0 xfail)
- Commit `01e2c38` (Task 1) — present in git history
- Commit `5fc553b` (Task 2) — present in git history
