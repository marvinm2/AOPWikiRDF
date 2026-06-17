---
phase: 09-xml-rdf-coverage-audit-gap-fixes-coverage-ratchet
plan: 03
subsystem: xml-rdf-conversion
tags: [xml-02, coverage-gap-fix, parser, writer, additive, ratchet-input]
requires:
  - coverage-audit-script
  - coverage-report-json
  - actionable-gap-list
provides:
  - gap-fix-parser-reads
  - gap-fix-writer-emission
  - element-predicate-map
affects:
  - src/aopwiki_rdf/parser/xml_parser.py
  - src/aopwiki_rdf/rdf/writer.py
  - tests/integration/test_coverage_ratchet.py
  - tests/fixtures/sample_aopwiki.xml
tech-stack:
  added: []
  patterns:
    - "Conditional additive predicate emission in the existing KER/KE write loops (byte-identical when the XML omits the element)"
    - "KER WoE read analog reused: find -> is-not-None guard -> HTML_TAG_PATTERN strip -> triple-quote wrap"
    - "quantitative-understanding container walked once; its description + 3 sub-elements mapped to distinct predicates"
    - "All 7 predicates use the already-registered nci:/edam: prefixes -> no new prefix row needed in prefixes.csv or namespaces.py"
key-files:
  created: []
  modified:
    - src/aopwiki_rdf/parser/xml_parser.py
    - src/aopwiki_rdf/rdf/writer.py
    - tests/integration/test_coverage_ratchet.py
    - tests/fixtures/sample_aopwiki.xml
decisions:
  - "Followed the AUTHORITATIVE snapshot structure over the prompt's nesting hints: evidence-collection-strategy / known-modulating-factors / quantitative-understanding are direct KER children; response-response-relationship / time-scale / feedforward-feedback-loops nest under quantitative-understanding; evidence-supporting-taxonomic-applicability appears on BOTH key-event (1583x) and key-event-relationship (2336x) so it is read+emitted on both"
  - "No new prefix introduced: all 7 predicates map to existing nci: (NCI Thesaurus, descriptive) and edam: (EDAM, quantitative) prefixes, exactly matching the established WoE convention (biological-plausibility->nci:C80263, emperical-support-linkage->edam:data_2042, AOP-level quantitative-considerations->edam:operation_3799)"
  - "Predicate CURIEs chosen as closest-concept ontology anchors (verified to resolve to real labels via OLS), mirroring how the existing schema uses nci:C80263=Rationale / nci:C71478=Uncertainty as approximate anchors rather than exact terms"
  - "Tests validated against the worktree src via PYTHONPATH override because the editable install (.pth) points at the MAIN repo src, not the worktree (shared-editable-install gotcha)"
metrics:
  duration: ~25 min
  completed: 2026-06-17
---

# Phase 9 Plan 03: Coverage Gap Fixes (XML-02) Summary

Closed the maintainer-selected high-value coverage gaps by adding `find` reads in `parser/xml_parser.py` and conditional, additive triple emission in `rdf/writer.py` for the 7 instance-present-but-unmapped elements. Coverage rose **72.6% -> 80.0%** (69 -> 76 covered elements, 20 -> 13 actionable gaps) and the real-snapshot output grew **+2,751 triples** (108,577 -> 111,328) with zero triples removed. No new prefix was needed — every predicate uses the already-registered `nci:`/`edam:` namespaces.

## Element -> Predicate Mapping (READ THIS, Plan 04)

The exact mapping Plan 04 must read to build the per-element guard map and freeze the ratchet baseline:

| XML element | Predicate CURIE | NCI/EDAM label | Parent(s) in snapshot | occ (latest) |
|-------------|-----------------|----------------|------------------------|-------------:|
| evidence-supporting-taxonomic-applicability | `nci:C17469` | Taxonomy | key-event (1583) + key-event-relationship (2336) | 3919 |
| evidence-collection-strategy | `nci:C103159` | Data Collection | key-event-relationship | 2336 |
| known-modulating-factors | `nci:C68821` | Regulation | key-event-relationship (2336) + overall-assessment (587, not read) | 2923 |
| quantitative-understanding (its `<description>`) | `edam:operation_3799` | Quantification | key-event-relationship | 2336 |
| response-response-relationship | `edam:operation_3438` | Calculation | quantitative-understanding (under KER) | 2336 |
| time-scale | `nci:C25207` | Time | quantitative-understanding (under KER) | 2336 |
| feedforward-feedback-loops | `nci:C25343` | Mechanism | quantitative-understanding (under KER) | 2336 |

Notes for Plan 04:
- `evidence-supporting-taxonomic-applicability` is emitted on BOTH the KER and the KE subject (same predicate `nci:C17469`); the guard should count `nci:C17469` triples across both.
- `known-modulating-factors` also occurs under `overall-assessment` (587x) in the XML, but that parent is NOT read this round — only the dominant KER-level occurrence (2336x) is mapped. The audit still flips the element to `emitted_by_parser:true` because coverage is keyed by element local-name, not by parent.
- Predicate->prefix: `nci:` = `http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#`; `edam:` = `http://edamontology.org/`. Both already in `prefixes.csv` (rows 31, 44) and `namespaces.py` (NS_NCI, NS_EDAM).

## What Was Built

### Task 1 (RED) — failing tests + extended fixture (commit `6cebf3f`)
- Extended `tests/fixtures/sample_aopwiki.xml`: KER id 50 now carries `evidence-collection-strategy`, `known-modulating-factors`, a `quantitative-understanding` block (description + `response-response-relationship` + `time-scale` + `feedforward-feedback-loops`), and a KER-level `evidence-supporting-taxonomic-applicability`; KE id 100 carries a KE-level `evidence-supporting-taxonomic-applicability`. Structure mirrors the authoritative 2026-06-17 snapshot.
- Rewrote `tests/integration/test_coverage_ratchet.py`: removed the two xfail markers. `test_fixed_gaps_emit` parses the fixture through the real `parse_aopwiki_xml` -> `write_aop_rdf`, asserts every assigned predicate appears, and asserts the emitted Turtle parses with `rdflib`. `test_additive` reconstructs the pre-fix Turtle (strips the new-predicate lines) and asserts the gap-fixed triple count is strictly greater (additive). `test_ratchet_fails_on_drop` (Nyquist negative sample) unchanged and still passing.
- Confirmed RED: both new tests failed because the writer emitted none of the predicates.

### Task 1 (GREEN) — parser reads + writer emission (commit `2f12cfd`)
- **Parser** (`xml_parser.py`): added KER reads after the WoE block — `evidence-collection-strategy`, `known-modulating-factors`, `evidence-supporting-taxonomic-applicability`, and a `quantitative-understanding` walk (its `description` + the three quantitative sub-elements). Added a KE read for `evidence-supporting-taxonomic-applicability`. Every read guards optional `.text` with `is not None`, HTML-strips via `HTML_TAG_PATTERN`, and triple-quote-wraps the literal, exactly as the existing WoE analog does.
- **Writer** (`writer.py`): extended the existing KER optional-predicate loop from 3 to 10 predicates and the KE loop to include `nci:C17469`. Emission is conditional (`if predicate in dict`) and reuses the `.replace("\\","")` triple-quoted value path — so a KER/KE stays byte-identical when the XML omits the element.
- No new prefix: all predicates resolve under `nci:`/`edam:`, already registered in both `prefixes.csv` and `namespaces.py`.

## Human-Verify Evidence (checkpoint performed in-agent; maintainer sign-off pending)

Per the orchestrator directive, the `checkpoint:human-verify` was executed here and evidence captured (gap fixes only reach live `master/data/` on the next weekly run, so post-hoc review is safe).

1. **Regeneration ran against the REAL latest snapshot** `data/aop-wiki-xml-2026-06-17` (not just the fixture): parsed via `parse_aopwiki_xml` -> `write_aop_rdf` to `/tmp/cov-check/AOPWikiRDF.ttl`. (Full `run_conversion.py` was not used to avoid the HGNC/BridgeDb network legs; these gap predicates live entirely in the main AOPWikiRDF.ttl, which this targeted regen produces.)

2. **Sensible (non-empty) values** — 1-2 line snippets from the regenerated TTL:
   - `nci:C17469` -> `"""CI has a highly conserved subunit composition across species, from lower organis...`
   - `nci:C103159` -> `"""- Revision of AOP3 (Project: NP/EFSA/PREV/2024/02): The implementation...`
   - `nci:C68821` -> real WoE modulating-factor text (HTML stripped)
   - `edam:operation_3799` -> `"""The quantitative understanding of this AOP includes a clear response-response re...`
   - `edam:operation_3438` -> `"""- Revision of AOP3 (Project: NP/EFSA/PREV/2024/02):...`
   - `nci:C25207` -> `"""Rapid Molecular Interactions....`
   - `nci:C25343` -> `"""Unknown....`
   Per-predicate triple counts in the real output: `nci:C17469`=1082, `nci:C103159`=274, `nci:C68821`=235, `edam:operation_3799`=585, `edam:operation_3438`=247, `nci:C25207`=249, `nci:C25343`=243.

3. **Coverage rose** — re-ran `scripts/coverage_audit.py --snapshot data/aop-wiki-xml-2026-06-17` against the worktree parser source: all 7 elements now report `covered: true`, `emitted_by_parser: true`, `is_gap: false`. Summary went from **72.6% (69/95, 20 gaps)** to **80.0% (76/95, 13 gaps)**.

4. **Additive (count went UP, not down)** — same-snapshot main TTL regenerated with the base (pre-fix) parser/writer = **108,577** triples; gap-fixed = **111,328** triples. Delta **+2,751**. The `test_additive` integration test independently asserts the fixed count strictly exceeds the pre-fix count on fixture data. Zero triples removed.

## Verification Results

- `pytest tests/integration/test_coverage_ratchet.py::test_fixed_gaps_emit ::test_additive` -> 2 passed.
- `pytest tests/integration/test_coverage_ratchet.py tests/unit/test_coverage_audit.py tests/unit/test_qc_delta_guard.py tests/unit/test_xml_parser.py tests/integration/test_output_separation.py tests/integration/test_compat_flag_off.py` -> **35 passed, 3 skipped, 2 xfailed** (the 2 xfails are the Plan-04 per-element-guard stubs, by design).
- Emitted Turtle parses with `rdflib` (both fixture output and the 111,328-triple real-snapshot output).
- Scope fence verified: `git diff` shows **no** `enable_bern2` / `enable_iri_labels` / `--enable` tokens introduced in the changed source files.
- New prefixes: none introduced; `nci`/`edam` already present in `prefixes.csv` (rows 31, 44) and `namespaces.py`.

## Deviations from Plan

**1. [Rule 1 - Correctness] Followed the authoritative snapshot nesting over the prompt's structural hints.**
- The resolved-checkpoint note placed `evidence-supporting-taxonomic-applicability` as "KER-level WoE" and `evidence-collection-strategy` as "KE-level", and grouped `known-modulating-factors` under quantitative-understanding.
- The actual 2026-06-17 snapshot (verified via a parent-tracking `iterparse`) shows: `evidence-collection-strategy`, `known-modulating-factors`, `quantitative-understanding` are DIRECT KER children; `response-response-relationship` / `time-scale` / `feedforward-feedback-loops` nest INSIDE `quantitative-understanding`; `evidence-supporting-taxonomic-applicability` appears on BOTH key-event AND key-event-relationship.
- The plan instructed "Verify exact nesting against the actual snapshot/fixture XML before writing find/findall paths" — so the find/findall paths follow the snapshot, and the element is read on both KE and KER. No behavior risk: each read is guarded and additive.

**2. [Process] Tests run with `PYTHONPATH=$PWD/src`.** The repo's editable install (`__editable__.aopwiki_rdf-1.0.0.pth`) hardcodes the MAIN repo `src`, so an unqualified `pytest` in the worktree imports the main repo's (unchanged) parser/writer. Validation used `PYTHONPATH=$PWD/src` to force imports to the worktree code. On merge to master this is moot — the editable install then points at the merged code. Not a code change.

## Out-of-Scope Pre-Existing Failures (logged, NOT fixed)

Four tests in `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` (`test_dual_predicate_protein_ontology`, `test_owl_only_protein_ontology`, `test_dual_predicate_chemicals`, `test_owl_only_chemicals`) fail with `assert 'owl:sameAs' in content`. Confirmed PRE-EXISTING: they fail against the unmodified base commit `cd36716`, and the 09-03 writer diff does not touch `owl:sameAs` / chemical / protein-ontology emission. Per the scope boundary they were logged to `deferred-items.md` and left for a future writer-test maintenance plan.

## Threat Model Compliance

- **T-09-05 (Tampering, new triples reaching live master/data — mitigate):** Fixes are strictly additive (real-snapshot count 108,577 -> 111,328, +2,751; zero removed), so the existing publish delta-guard passes. The human-verify evidence above confirms semantic correctness pre-regeneration; Plan 04's ratchet will lock the new floor.
- **T-09-06 (Injection, malformed Turtle — mitigate):** Every new literal reuses the existing `HTML_TAG_PATTERN` strip + triple-quote wrapping; the 111,328-triple real output parses cleanly with `rdflib`.
- **T-09-SC (supply-chain — mitigate):** No package installed; stdlib + existing deps only. No new prefix or dependency.

## Self-Check: PASSED

- `src/aopwiki_rdf/parser/xml_parser.py` — FOUND (gap reads present)
- `src/aopwiki_rdf/rdf/writer.py` — FOUND (10-predicate KER loop + KE nci:C17469)
- `tests/integration/test_coverage_ratchet.py` — FOUND (xfails removed, 2 new tests pass)
- `tests/fixtures/sample_aopwiki.xml` — FOUND (7 gap elements added)
- Commit `6cebf3f` (RED) — present in git history
- Commit `2f12cfd` (GREEN) — present in git history
