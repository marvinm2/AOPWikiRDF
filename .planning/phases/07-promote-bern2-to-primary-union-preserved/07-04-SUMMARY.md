---
phase: 07-promote-bern2-to-primary-union-preserved
plan: 04
subsystem: shacl-shapes
tags: [shacl, shape-generation, prov-o, gene-association, validation-gate, compat-01]
requires:
  - "07-02: KER NER genes + :geneDetectedByNER/:geneDetectedByRegex appear in the flag-on genes file"
  - "07-03: GENES_PROVENANCE_ACTIVITIES (prov:Activity block, :isFeaturedMethod, :minConfidence, prov:wasGeneratedBy)"
provides:
  - "data-test/gene-association-provenance-fixture.ttl: committed flag-on (enable_bern2=True) genes TTL audit input carrying every Phase-7 predicate"
  - "property_audit.py audits the fixture under key gene-association-provenance-fixture.ttl"
  - "generate_shapes.py: prov:/base : prefixes + generate_gene_association_shape (3 node shapes from the fixture audit)"
  - "shapes/gene-association-shape.ttl regenerated: GeneAssociationShape + GeneMethodProvenanceShape (sh:targetSubjectsOf) + MethodActivityShape (sh:targetClass prov:Activity)"
  - "SHACL integration test asserting the four new predicate paths + fixture conformance (T-07-07 guard)"
affects:
  - "scripts/generate_shapes.py (prefix maps + gene-association builder)"
  - "scripts/property_audit.py (audits the flag-on fixture)"
  - "scripts/audit-results.json (refreshed; now contains the fixture entry)"
  - "shapes/gene-association-shape.ttl (regenerated, multi-shape)"
  - "tests/integration/test_shacl_validation.py (two new tests)"
  - ".gitignore (exempts the committed fixture from data-test*/)"
tech-stack:
  added:
    - "PROV-O prefix in the shape generator's prefix maps (http://www.w3.org/ns/prov#)"
    - "base : namespace (https://aopwiki.rdf.bigcat-bioinformatics.org/) in the shape generator's prefix maps"
  patterns:
    - "Shapes are GENERATED, never hand-edited (CLAUDE.md / D-12): all shape changes come from property_audit.py -> generate_shapes.py"
    - "Audit input is a flag-ON fixture (RESEARCH Pitfall 5 / T-07-07): only data containing the new predicates lets them enter the shape"
    - "Untyped genes-file union subjects targeted via sh:targetSubjectsOf (EnrichedXref precedent), not sh:targetClass"
    - "prov:Activity primacy/confidence resources validated by sh:targetClass prov:Activity"
key-files:
  created:
    - data-test/gene-association-provenance-fixture.ttl
  modified:
    - scripts/generate_shapes.py
    - scripts/property_audit.py
    - scripts/audit-results.json
    - shapes/gene-association-shape.ttl
    - tests/integration/test_shacl_validation.py
    - .gitignore
decisions:
  - "Generate the gene-association shape against a committed flag-on fixture (not flag-off production data) so the BERN2 predicates are present to audit -- the only way the shape can cover them (Pitfall 5 / T-07-07)"
  - "Three node shapes in one file: typed edam:data_1025 (GeneAssociationShape), untyped union subjects via sh:targetSubjectsOf :geneDetectedByNER/Regex (GeneMethodProvenanceShape), and prov:Activity (MethodActivityShape) -- because the KE/KER union subjects carry no rdf:type in the genes file so sh:targetClass cannot reach them"
  - "Exempt the fixture from the data-test*/ gitignore via a !negation: it is a tracked source artifact (the shape's audit input), not temporary test output"
  - "Restored the six non-gene shapes that regeneration also rewrote (stale audit vs current production data) to HEAD -- pre-existing drift owned by another lineage, out of this plan's scope"
metrics:
  tasks: 2
  files: 6
  completed: 2026-06-01
requirements: [GENE-06, PROV-01]
---

# Phase 7 Plan 04: SHACL Shape Regeneration for BERN2 Provenance Predicates Summary

`gene-association-shape.ttl` is regenerated (via `property_audit.py` -> `generate_shapes.py`, never hand-edited) so SHACL now validates every predicate this phase introduced: `:geneDetectedByNER`, `:geneDetectedByRegex`, the `prov:*` activity predicates, and the `:isFeaturedMethod` primacy flag. Because the shape generator derives shapes from actual triples, the audit input is a committed flag-on (`enable_bern2=True`) genes fixture under `data-test/` that carries all of those predicates; the generator's prefix maps learned `prov:` and the base `:` namespace, and pyshacl validates the fixture green while the production runner stays green (0 violations).

## What Was Built

**Flag-on fixture (Task 1).** `data-test/gene-association-provenance-fixture.ttl` is produced by running the real genes writer (`write_genes_rdf` with `PipelineConfig(enable_bern2=True)`) over a tiny KE (regex ∪ NER union), a regex-only KER, and typed HGNC/Entrez/Ensembl/UniProt gene-identifier subjects — so the fixture matches real emission byte-for-byte, including the `GENES_PROVENANCE_ACTIVITIES` block (`:BERN2NERMapping a prov:Activity`, `:isFeaturedMethod true`, `:minConfidence "0.70"^^xsd:decimal`, `prov:wasGeneratedBy`). 61 triples, valid Turtle.

**Generator prefix maps (Task 1).** `generate_shapes.py` gained `prov:` (`http://www.w3.org/ns/prov#`) and the base `:` (`https://aopwiki.rdf.bigcat-bioinformatics.org/`) in both `COMMON_PREFIXES` and `prop_to_prefixed`, so the new predicates render prefixed (`:geneDetectedByNER`, `prov:wasGeneratedBy`, …) rather than as full `<URI>`.

**Audit of the fixture (Task 2).** `property_audit.py` now audits the fixture under the key `gene-association-provenance-fixture.ttl` (via an `extra_files` list, outside `data/`), so the Phase-7 predicates enter `scripts/audit-results.json`.

**Shape regeneration (Task 2).** A new `generate_gene_association_shape(fixture_audit)` emits three node shapes into `gene-association-shape.ttl`:
- `GeneAssociationShape` — `sh:targetClass edam:data_1025` (the typed gene-identifier subjects, the legacy shape's home).
- `GeneMethodProvenanceShape` — `sh:targetSubjectsOf :geneDetectedByRegex` / `:geneDetectedByNER` for the **untyped** KE/KER union subjects (which carry no `rdf:type` in the genes file, so `sh:targetClass` cannot reach them — mirroring the `EnrichedXref` `sh:targetSubjectsOf` precedent).
- `MethodActivityShape` — `sh:targetClass prov:Activity` covering `:isFeaturedMethod`, `:minConfidence`, `prov:used`, `prov:wasDerivedFrom`.

All four new predicate paths are present and prefixed. The generator falls back to the prior typed-only shape if the fixture audit is absent (older `audit-results.json`).

**Test (Task 2).** `tests/integration/test_shacl_validation.py` gained `test_gene_shape_covers_new_bern2_predicates` (the four paths are present and prefixed — the T-07-07 guard) and `test_flag_on_fixture_conforms_to_gene_shape` (pyshacl conforms green against the fixture).

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Flag-on genes fixture + prov/base prefixes in the shape generator | e4631ec | data-test/gene-association-provenance-fixture.ttl, scripts/generate_shapes.py, .gitignore |
| 2 | Audit the fixture + regenerate the multi-shape + prove it validates green | 97ea45e | scripts/property_audit.py, scripts/generate_shapes.py, scripts/audit-results.json, shapes/gene-association-shape.ttl, tests/integration/test_shacl_validation.py |

## Verification

- `python scripts/run_shacl_validation.py` exits 0 — `AOPWikiRDF.ttl` and `AOPWikiRDF-Enriched.ttl` conform with 0 violations / 0 warnings against the regenerated shape set (the `MethodActivityShape` `prov:Activity` targetClass has no instances in the production main file, so no new violations).
- pyshacl validates `data-test/gene-association-provenance-fixture.ttl` against the regenerated `gene-association-shape.ttl` green (0 violations).
- `pytest tests/integration/test_shacl_validation.py -x` → 5 passed (3 existing + 2 new).
- `pytest tests/unit/test_shacl_workflow.py tests/integration/test_shacl_validation.py` → 12 passed, no regression.
- Acceptance greps: `geneDetectedByNER` (×3), `geneDetectedByRegex` (×3), `isFeaturedMethod` (×3), `prov:` (×8) all present in `shapes/gene-association-shape.ttl`; `prov:` + base `:` present in `generate_shapes.py`.
- Idempotence: regenerating from the committed `audit-results.json` reproduces the committed `gene-association-shape.ttl` byte-for-byte.

All test/script runs used `PYTHONPATH=<worktree>/src` (see Deviations — editable-install gotcha).

## Deviations from Plan

### [Rule 3 - Blocking issue] data-test/ was gitignored; fixture exempted via negation

- **Found during:** Task 1 commit (staging failed — `data-test*/` ignores the directory).
- **Issue:** The plan declares `data-test/gene-association-provenance-fixture.ttl` as a required **committed** artifact (it is the audit input the shape and the SHACL test depend on), but `.gitignore` line 49 (`data-test*/`) ignores the whole directory as "temporary test directories".
- **Fix:** Added a scoped negation in `.gitignore` (`!data-test/` + `data-test/*` + `!data-test/gene-association-provenance-fixture.ttl`) so only this one tracked fixture is exempted; the rest of `data-test/` stays ignored. `git add` then staged the fixture.
- **Files modified:** `.gitignore`
- **Commit:** e4631ec

### [Rule 3 - Blocking issue] Stale committed audit-results.json caused 6 unrelated shapes to drift

- **Found during:** Task 2 (after running the audit + regenerating all shapes).
- **Issue:** Running `property_audit.py` re-reads the current `data/*.ttl`, but the committed `audit-results.json` was stale relative to current production data. Regenerating therefore rewrote six unrelated shapes (`aop-`, `chemical-`, `enriched-xref-`, `ker-`, `key-event-`, `stressor-`) reflecting pre-existing data drift — outside this plan's `files_modified`.
- **Fix:** `git checkout --` restored those six shapes to HEAD; only `gene-association-shape.ttl` and the (necessarily whole-file) `audit-results.json` are committed. Per the SCOPE BOUNDARY rule, the unrelated drift is left for the lineage that owns those shapes.
- **Files modified:** none beyond restoring to HEAD.
- **Commit:** n/a (restoration only).

### [Rule 3 - Blocking issue] Editable-install resolves to the main repo, not the worktree

- **Found during:** Task 1 fixture generation.
- **Issue:** Documented shared-editable-install gotcha — `aopwiki_rdf` resolves to the MAIN repo `src/`, so worktree edits are invisible without an override.
- **Fix:** All Python invocations prepend `PYTHONPATH=<worktree>/src`. Execution-environment workaround only; no source change. The orchestrator's merge makes the change live on main normally.
- **Files modified:** none (workflow-only).
- **Commit:** n/a.

## Known Stubs

None. The fixture is real byte-for-byte writer output; the shape is generated, not stubbed.

## Threat Flags

None. No new network endpoint, dependency, auth path, or production emission change — `rdflib`/`pyshacl` were already present, and the fixture/shape are validation-only artifacts. The plan **mitigates** T-07-07 (a shape generated against a flag-off genes file would omit the new predicates): the audit input is a flag-on fixture containing all new predicates, and the new SHACL test asserts their presence in the regenerated shape, so a future regen against flag-off output is caught.

## Deferred Issues

- The six non-gene shapes (`aop-`, `chemical-`, `enriched-xref-`, `ker-`, `key-event-`, `stressor-`) show drift between the committed `audit-results.json` and current production `data/*.ttl`. Out of scope for this plan (SCOPE BOUNDARY) — left to the lineage that owns the production-data shape set. Note: the committed `audit-results.json` here is refreshed (it had to be, to add the fixture entry), so a future full `generate_shapes.py` run will now rewrite those six shapes from the refreshed audit; that regeneration belongs to a dedicated shapes-refresh change, not this plan.
- The pre-existing `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` failures (noted in `deferred-items.md` from 07-01/07-03) remain untouched and out of scope.

## Self-Check: PASSED

- `data-test/gene-association-provenance-fixture.ttl` — FOUND (created, 61 triples, valid Turtle, all new predicates).
- `scripts/generate_shapes.py` — FOUND (prov:/base : prefixes + generate_gene_association_shape).
- `scripts/property_audit.py` — FOUND (audits the fixture under its basename key).
- `scripts/audit-results.json` — FOUND (refreshed; fixture entry present).
- `shapes/gene-association-shape.ttl` — FOUND (regenerated; 3 node shapes; four new predicate paths prefixed).
- `tests/integration/test_shacl_validation.py` — FOUND (two new tests).
- Commit `e4631ec` (Task 1) — FOUND.
- Commit `97ea45e` (Task 2) — FOUND.
