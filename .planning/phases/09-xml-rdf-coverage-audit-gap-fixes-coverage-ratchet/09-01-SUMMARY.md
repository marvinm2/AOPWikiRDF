---
phase: 09-xml-rdf-coverage-audit-gap-fixes-coverage-ratchet
plan: 01
subsystem: coverage-audit-scaffolding
tags: [scaffolding, vendored-schema, allowlist, test-stubs, nyquist-wave-0]
requires: []
provides:
  - vendored-aop-xml-xsd
  - coverage-allowlist
  - phase9-test-stubs
  - coverage-fixtures
affects:
  - .gitignore
  - data/schema/
  - tests/
tech-stack:
  added: []
  patterns:
    - "Vendored static input with .SOURCE provenance pin (url/repo/tag/sha256/retrieved)"
    - "!data/schema/ un-ignore exception (no git add -f for vendored schema)"
    - "xfail-gated green-on-red test stubs mapped one-to-one to 09-VALIDATION.md"
key-files:
  created:
    - data/schema/aop-wiki-xml.xsd
    - data/schema/aop-wiki-xml.xsd.SOURCE
    - data/schema/coverage-allowlist.json
    - tests/fixtures/sample_aopwiki_coverage.xml
    - tests/fixtures/sample_aopwiki_coverage_regression.xml
    - tests/unit/test_coverage_audit.py
    - tests/integration/test_coverage_ratchet.py
  modified:
    - .gitignore
    - tests/unit/test_qc_delta_guard.py
decisions:
  - "Highest stable XSD tag resolved to 2.7.0 (matches RESEARCH baseline; alpha and v1.0.x tags are lower)"
  - "Un-ignore via !data/schema/ exception following the !data/AOPWikiRDF.ttl idiom — never git add -f"
  - "Allowlist seeded with only the six structural/plumbing elements (data, link_source, references, url, url_link, value); semantic gap candidates deliberately excluded for Plan 03"
  - "Regression fixture drops the covered key-event-relationship description; comment text rewritten so even naive grep counts the element delta correctly (5 vs 4)"
  - "test_ratchet_fails_on_drop is a real, passing negative test in Wave 0 (reuses the existing relative-floor breach); gap-fix and per-element tests xfail until Plans 03/04"
metrics:
  duration: ~12 min
  completed: 2026-06-17
---

# Phase 9 Plan 01: Coverage-Audit Scaffolding Summary

Vendored the pinned AOP-XML XSD (swandle06/AopXml@2.7.0) with a sha256 provenance pin, fixed the `.gitignore` rule that silently swallowed it, seeded the D-09 coverage allowlist, and laid down xfail-gated test stubs plus happy/regression fixtures — the complete Nyquist Wave 0 substrate every later Phase-9 plan verifies against.

## What Was Built

### Task 1 — Vendored XSD + provenance, gitignore fix (commit `6017b60`)
- Resolved the highest stable tag via `git ls-remote --tags https://github.com/swandle06/AopXml` → `2.7.0` (alpha tags and `v1.0.x` are lower; matches the RESEARCH baseline).
- Downloaded `raw.githubusercontent.com/swandle06/AopXml/2.7.0/assets/schema/current.xsd` to `data/schema/aop-wiki-xml.xsd` (38 801 bytes, `targetNamespace="http://www.aopkb.org/aop-xml"` matching `AOPXML_NS`).
- Wrote `data/schema/aop-wiki-xml.xsd.SOURCE` with `url`/`repo`/`tag`/`sha256`/`retrieved` keys; recorded sha256 `28aa8425…cca535` equals `sha256sum` of the file.
- Fixed `.gitignore`: the line-14 `aop-wiki-xml*` rule matched the vendored XSD. Added a `!data/schema/` un-ignore exception (plus explicit file exceptions) following the existing `!data/AOPWikiRDF.ttl` idiom. Raw `data/aop-wiki-xml*` snapshot downloads stay ignored. No `git add -f` used.

### Task 2 — Coverage allowlist (commit `b46fd7d`)
- Wrote `data/schema/coverage-allowlist.json` as a sorted-key JSON object mapping element local-name → one-sentence reason.
- Seeded only the six intentionally-unmapped structural/plumbing elements RESEARCH classified: `data`, `link_source`, `references`, `url`, `url_link`, `value`.
- Deliberately excludes semantic gap candidates (`evidence-collection-strategy`, `known-modulating-factors`, `response-response-relationship`, `time-scale`, `exposure-characterization`) — those are Plan 03 maintainer decisions (D-06). The allowlist is the inverse of D-07: known-worthless, not pre-seeded suspicions.

### Task 3 — Test stubs + fixtures (commit `7023493`)
- Two fixtures derived from `sample_aopwiki.xml`, keeping the aop-xml namespace root and `<vendor-specific>` ID block:
  - `sample_aopwiki_coverage.xml` — covered `key-event-relationship/description`, allowlisted `references`, and gap candidates `evidence-collection-strategy` + `time-scale`.
  - `sample_aopwiki_coverage_regression.xml` — identical except the covered KER `description` is dropped (the critical negative Nyquist sample; 5→4 description elements, confirmed by both XML parsing and naive grep).
- `tests/unit/test_coverage_audit.py` — XML-01 stubs named exactly per 09-VALIDATION.md (`test_audit_emits_json`, `test_attribute_axis`, `test_covered_set`, `test_no_snapshots_dir_skips`, `test_allowlist`), each importing the not-yet-existing `scripts/coverage_audit.py` via `spec_from_file_location` with real assertions, module-level `xfail` until Plan 02.
- `tests/integration/test_coverage_ratchet.py` — `test_ratchet_fails_on_drop` is real and passing in Wave 0 (reuses the existing relative-floor breach in `qc_delta_guard.py`); `test_fixed_gaps_emit` and `test_additive` xfail until Plan 03.
- Extended `tests/unit/test_qc_delta_guard.py` (not rewritten) with `test_per_element_relative_floor` and `test_warn_only_exits_zero`, xfail until Plan 04. Pre-existing gene/total guard tests still pass.

## Verification Results

- `pytest tests/unit/test_coverage_audit.py tests/integration/test_coverage_ratchet.py tests/unit/test_qc_delta_guard.py -q` → **9 passed, 1 skipped, 9 xfailed** (exit 0; xfails do not fail the suite).
- `pytest tests/unit/test_qc_delta_guard.py -q` → pre-existing guard tests green.
- `git check-ignore` exits 1 for all three `data/schema/*` files (tracked) and exits 0 for `data/aop-wiki-xml-2026-06-17` (snapshot downloads still ignored).
- Recorded sha256 in `.SOURCE` equals `sha256sum data/schema/aop-wiki-xml.xsd`.
- Allowlist parses, all values non-empty strings, required keys present, no semantic gap candidates, keys sorted.
- Regression fixture has strictly fewer `description` elements than the happy fixture (5 → 4).
- No untracked files left behind.

## Deviations from Plan

None — plan executed as written. The only judgment call was rewording two comment lines in the regression fixture so a naive `grep -c '<description>'` (not just the XML-parser count) shows the 5→4 delta; the XML-element delta was correct throughout.

## Threat Model Compliance

- **T-09-01 (XSD tampering, mitigate):** XSD pinned by tag `2.7.0`; sha256 recorded in `.SOURCE` and verified equal to `sha256sum` of the vendored file.
- **T-09-SC (supply-chain, mitigate):** No new package installed — stdlib + already-pinned rdflib only. The `xmlschema` route was explicitly not taken. No legitimacy checkpoint required.
- No custom XML entity resolution enabled anywhere (XXE: stdlib default behavior only).

## Known Stubs

The three new test files are intentionally stub-and-xfail until their implementing plans (audit → Plan 02, gap-fix → Plan 03, per-element guard → Plan 04). This is the planned Nyquist Wave 0 green-on-red posture, not a defect: assertions are real and flip to xpass as each plan lands. Documented here for the verifier so the xfails are not misread as missing coverage.

## Self-Check: PASSED

All created files exist on disk and all three task commits (`6017b60`, `b46fd7d`, `7023493`) are present in git history.
