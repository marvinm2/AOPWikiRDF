---
phase: 07-promote-bern2-to-primary-union-preserved
plan: 03
subsystem: rdf-writer
tags: [prov-o, provenance, primacy, confidence-policy, compat-01, gated-emission]
requires:
  - genes_provenance gate (enable_bern2) — Phase 6
  - GENES_PROVENANCE_PREFIX + :geneDetectedBy* predicates — Phase 6
provides:
  - GENES_PROVENANCE_ACTIVITIES constant (gated PROV-O activity block)
  - machine-readable method primacy (:isFeaturedMethod true on BERN2)
  - 0.70 confidence policy asserted in RDF (:minConfidence xsd:decimal)
  - predicate-level prov:wasGeneratedBy links (canonical method discoverable)
affects:
  - AOPWikiRDF-Genes.ttl header (flag-on only)
tech-stack:
  added:
    - PROV-O vocabulary (prefix only — http://www.w3.org/ns/prov#)
  patterns:
    - byte-stable hand-written TTL emission (no rdflib serialize)
    - flag-gated emission (COMPAT-01): all new triples behind enable_bern2
    - activity-level provenance only (no per-subject prov, no reification)
key-files:
  created:
    - tests/unit/test_prov_activities.py
    - tests/integration/test_compat_flag_off.py
  modified:
    - src/aopwiki_rdf/rdf/namespaces.py
    - src/aopwiki_rdf/rdf/writer.py
    - tests/unit/test_bern2_pipeline.py
decisions:
  - "prov: prefix lives ONLY in the gated genes header, NOT in prefixes.csv (COMPAT-01 carve-out)"
  - "primacy modeled as :isFeaturedMethod boolean on the activity resource (D-02 discretion)"
  - "all activity metadata static (no timestamp/version lookup) for byte-stability"
metrics:
  tasks-completed: 2
  files-created: 2
  files-modified: 3
  completed: 2026-06-01
---

# Phase 7 Plan 03: PROV-O Activity Layer + Method Primacy Summary

Added a gated PROV-O activity layer to the genes file that makes "canonical = BERN2" and the 0.70 confidence policy discoverable straight from the RDF — two `prov:Activity` resources with a machine-readable `:isFeaturedMethod` primacy flag, a `:minConfidence "0.70"^^xsd:decimal` assertion, and predicate-level `prov:wasGeneratedBy` links, all behind the existing `enable_bern2` gate so flag-off output stays byte-identical to production.

## What Was Built

- **`GENES_PROVENANCE_ACTIVITIES`** (`namespaces.py`): a static TTL constant declaring
  `:BERN2NERMapping a prov:Activity` (`:isFeaturedMethod true`, `:minConfidence "0.70"^^xsd:decimal`,
  `prov:used <http://bern2.korea.ac.kr/plain>`, `prov:wasDerivedFrom :AOPWikiXMLSource`),
  `:RegexGeneMapping a prov:Activity` (`:isFeaturedMethod false`, `prov:used <https://www.genenames.org/>`),
  `:AOPWikiXMLSource a prov:Entity`, and the two predicate-level links
  `:geneDetectedByNER prov:wasGeneratedBy :BERN2NERMapping` / `:geneDetectedByRegex prov:wasGeneratedBy :RegexGeneMapping`.
  Carries the `prov:` and `xsd:` `@prefix` lines inline (neither is in `GENES_PREFIXES`).
- **`writer.py write_genes_rdf`**: emits the block inside the existing `if genes_provenance:`
  branch, immediately after `GENES_PREFIXES` (so `rdfs:` — used by the activity labels — is
  already declared). No `_write_gene_block` change needed.
- **`tests/unit/test_prov_activities.py`**: flag-on emits activities/primacy/`minConfidence`/links
  and parses as valid Turtle; a SPARQL `:isFeaturedMethod true` + `prov:wasGeneratedBy` query
  resolves the BERN2 method; `:minConfidence` is a decimal literal; flag-off emits none; no `prov:*`
  predicate on any KE/KER subject (D-01).
- **`tests/integration/test_compat_flag_off.py`**: byte-diffs `data/AOPWikiRDF-Genes.ttl` and
  `data/AOPWikiRDF.ttl` against `production-rdf-backup/` (skips when backup absent), plus an
  unconditional flag-off prov-leak guard that runs on every environment.

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 (RED) | Wave-0 tests: prov activities + COMPAT byte-diff | `ae7bf73` | tests/unit/test_prov_activities.py, tests/integration/test_compat_flag_off.py |
| 2 (GREEN) | Gated PROV-O block + primacy + 0.70 policy | `a8cee82` | src/aopwiki_rdf/rdf/namespaces.py, src/aopwiki_rdf/rdf/writer.py, tests/unit/test_bern2_pipeline.py |

TDD gate sequence satisfied: `test(...)` RED commit (`ae7bf73`) precedes the `feat(...)` GREEN commit (`a8cee82`).

## Verification

- `pytest tests/unit/test_prov_activities.py tests/integration/test_compat_flag_off.py` — 6 passed, 2 skipped (backup absent).
- `pytest tests/unit/test_bern2_pipeline.py` — passes (no Phase 6 regression after assertion tightening).
- `grep -c prov prefixes.csv` == 0 (prov NOT in prefixes.csv).
- Flag-on genes file parses as valid Turtle (rdflib) and contains the activity block, primacy flag, `minConfidence`, and predicate-level prov links; flag-off contains none; no per-subject prov.

NOTE on test execution: the editable install (`.pth`) resolves `aopwiki_rdf` to the MAIN repo `src/`, not this worktree's `src/` (documented shared-editable-install gotcha). Tests in this worktree MUST be run with `PYTHONPATH=<worktree>/src` so the worktree's modified modules take precedence. Without the override, the worktree edits are invisible to pytest and the prov tests appear to "fail GREEN".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test correctness] Tightened two Phase-6 regression assertions to the block form**
- **Found during:** Task 2 (GREEN run).
- **Issue:** `test_flag_on_ker_omits_empty_ner_predicate` and `test_flag_on_ke_with_only_ner_genes`
  asserted bare `":geneDetectedByNER" not in content` / `":geneDetectedByRegex" not in content`.
  The new header now ALWAYS carries the predicate-level link
  `:geneDetectedByNER prov:wasGeneratedBy :BERN2NERMapping .` (and the regex counterpart),
  so the bare-substring checks tripped on a legitimate, intended header link.
- **Fix:** Changed both to the tab-delimited subject-block form
  (`"\t:geneDetectedByNER\t" not in content` / `"\t:geneDetectedByRegex\t" not in content`),
  preserving the original intent (no per-subject block emitted for an empty method list)
  while accommodating the new predicate-level header link.
- **Files modified:** `tests/unit/test_bern2_pipeline.py`
- **Commit:** `a8cee82`

### Plan-anticipated deviation (documented, as instructed by Task 2)

**`prov` deliberately NOT added to `prefixes.csv`.** `prefixes.csv` is iterated into unconditional
`sh:declare` lines in the MAIN `AOPWikiRDF.ttl` (writer.py ~L172-177), so a `prov` row there would
change the main file even when `enable_bern2=False` — a COMPAT-01 byte-identity violation. The `prov:`
prefix therefore lives ONLY in the gated `GENES_PROVENANCE_ACTIVITIES` header. This realizes
CONTEXT D-04's intent ("prov added as a prefix") via the gated header, within the D-02 location-discretion
clause (RESEARCH Open Q1 resolution, threat T-07-03 mitigation).

## Deferred Issues (out of scope)

`tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` — 4 failing tests
(`test_dual_predicate_chemicals`, `test_owl_only_chemicals`, `test_dual_predicate_protein_ontology`,
`test_owl_only_protein_ontology`). They assert `skos:exactMatch` in the MAIN-file chemical/protein-ontology
emission (`write_aop_rdf`), a code path 07-03 never touched. Verified pre-existing on the worktree base
commit (via `git stash` of the two edited source files — still 4 failed). Logged to
`deferred-items.md`; left for the predicate-correction lineage to own. NOT fixed here per the SCOPE BOUNDARY rule.

## Known Stubs

None. All emission is intentional and gated; no placeholder/empty-value stubs introduced.

## Self-Check: PASSED

- `src/aopwiki_rdf/rdf/namespaces.py` — FOUND (GENES_PROVENANCE_ACTIVITIES defined)
- `src/aopwiki_rdf/rdf/writer.py` — FOUND (constant imported + written in gate)
- `tests/unit/test_prov_activities.py` — FOUND
- `tests/integration/test_compat_flag_off.py` — FOUND
- Commit `ae7bf73` (RED) — FOUND
- Commit `a8cee82` (GREEN) — FOUND
