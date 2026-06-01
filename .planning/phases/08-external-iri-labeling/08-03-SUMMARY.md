---
phase: 08-external-iri-labeling
plan: 03
subsystem: rdf-writer
tags: [rdfs-label, predicate-labels, shacl, fixture, shape-regeneration, byte-stability]

# Dependency graph
requires:
  - phase: 08-external-iri-labeling (Plan 08-01, wave 1)
    provides: "config.enable_iri_labels flag + chem_label_by_iri / gene_label_by_iri maps threaded into the writers"
  - phase: 08-external-iri-labeling (Plan 08-02, wave 1)
    provides: "emit_labels read + _iri_label_clause/_component_label_clause instance-label emission, byte-identity COMPAT-01 guard"
provides:
  - "flag-gated rdfs:label on every reused EXTERNAL predicate the main file asserts (dc/dcterms/owl/rdfs/foaf/edam/aopo), emitted after the unconditional typelabels loop (Pitfall 2 honored)"
  - "rdfs:label on the minted ':' predicates (:geneDetectedByNER/:geneDetectedByRegex/:isFeaturedMethod/:minConfidence) in the genes file, DOUBLE-gated on enable_bern2 AND enable_iri_labels"
  - "data-test/iri-label-fixture.ttl: a real-emission flag-on label fixture (tracked source artifact) + scripts/generate_iri_label_fixture.py that regenerates it"
  - "regenerated shapes/chemical-shape.ttl with a ChemicalXrefShape carrying the rdfs:label constraint; gene-association shape already validates rdfs:label"
  - "pyshacl conforms green against both production data/ (0 violations) and the flag-on fixture"
affects: [SHACL shape generation, future external-IRI consumers reading predicate labels]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Curated predicate-label map emitted in a flag-gated block AFTER the unconditional typelabels loop (never grows it -- Pitfall 2)"
    - "Per-row prefix-declaration gate so the predicate-label block never references an unbound prefix"
    - "Real-emission SHACL fixture (Phase-7 07-04 method) feeding the property audit -> shape regeneration"
    - "label_flag_gated relaxation: rdfs:label demoted to non-blocking sh:Warning ONLY on flag-gated external-xref classes, so flag-off production data conforms"

key-files:
  created:
    - data-test/iri-label-fixture.ttl
    - scripts/generate_iri_label_fixture.py
  modified:
    - src/aopwiki_rdf/rdf/writer.py
    - src/aopwiki_rdf/rdf/namespaces.py
    - scripts/property_audit.py
    - scripts/generate_shapes.py
    - scripts/audit-results.json
    - shapes/chemical-shape.ttl
    - tests/integration/test_shacl_validation.py
    - .gitignore

key-decisions:
  - "EXTERNAL_PREDICATE_LABELS deliberately EXCLUDES the cheminf:* xref-type and edam:data_* identifier predicates that typelabels.txt already labels, so no duplicate rdfs:label triple is emitted; the property audit is the authoritative completeness check"
  - "Each predicate-label row is gated on its CURIE prefix being declared in prefixes.csv, so the block emits fewer rows under a minimal test prefix set rather than producing unbound-prefix Turtle"
  - "Minted-predicate labels live in a new GENES_MINTED_PREDICATE_LABELS constant emitted inside the genes_provenance block AND under `if emit_labels:` (double-gated), preserving both bern2-off and labels-off byte-identity"
  - "The flag-on fixture carries NO chemical ENTITY (cheminf:000000): the production-derived ChemicalShape mandates entity properties a tiny synthetic entity cannot satisfy, and that shape validates production data/, not the fixture. The fixture only needs the labeled ChEBI xref (cheminf:000407) to exercise the rdfs:label constraint."
  - "rdfs:label is relaxed to a non-blocking sh:Warning ONLY on flag-gated external-xref classes (label_flag_gated=True) so flag-off production ChEBI/gene subjects conform; AOP/KE/KER unconditional labels keep their genuine 100% Violation constraint"

patterns-established:
  - "Flag-gated predicate-label block + prefix-declaration gate = byte-identical flag-off, never an unbound prefix"
  - "label_flag_gated shape-generation flag isolates flag-gated rdfs:label relaxation to the classes that need it"

requirements-completed: [LABEL-01, LABEL-03, LABEL-04]

# Metrics
duration: 55min
completed: 2026-06-01
---

# Phase 8 Plan 03: Predicate Labels + SHACL Regeneration Summary

**Closed the two remaining LABEL items: every reused EXTERNAL predicate now carries a flag-gated `rdfs:label` (emitted after the untouched unconditional typelabels loop) and the minted `:` predicates carry one double-gated on `enable_bern2 AND enable_iri_labels`; a real-emission flag-on label fixture feeds the property audit so the regenerated chemical shape gains an `rdfs:label` constraint, and pyshacl conforms green against BOTH production data (0 violations) and the flag-on fixture — flag-off and bern2-off bytes untouched.**

## Performance

- **Duration:** ~55 min
- **Started/Completed:** 2026-06-01 (wave 2)
- **Tasks:** 2/2
- **Files:** 9 (2 created, 7 modified)

## Accomplishments

### Task 1 — predicate labels (D-06) — commit `4566513`
- Added `EXTERNAL_PREDICATE_LABELS` (curated CURIE -> label map) and `_external_predicate_label_block(emit_labels, known_prefixes)` to `writer.py`. The block emits `<predicate> rdfs:label "…" .` rows for the reused external predicates the main file asserts (dc/dcterms/owl/rdfs/foaf/edam:operation_3799/aopo relationship predicates), emitted **after** the unconditional `typelabels.txt` loop and **inside `if emit_labels:`** — never growing that loop or its 28 rows (Pitfall 2). The cheminf:*/edam:data_* identifier predicates are excluded because typelabels.txt already labels them (no duplicate triple).
- Gated each row on its prefix being declared (`set(prefixes['prefix'])`), so the block can never reference an unbound prefix — production declares all of them; a minimal test prefix set simply emits fewer rows.
- Added `GENES_MINTED_PREDICATE_LABELS` in `namespaces.py` and emitted it in `write_genes_rdf` **double-gated** on `genes_provenance AND emit_labels`, labeling `:geneDetectedByNER`, `:geneDetectedByRegex`, `:isFeaturedMethod`, `:minConfidence`. Preserves the `prov:` prefix carve-out (not added to prefixes.csv).

### Task 2 — fixture + shape regeneration (D-09) — commit `c3f17f0`
- Added `scripts/generate_iri_label_fixture.py` that produces `data-test/iri-label-fixture.ttl` by **real writer emission** (`enable_iri_labels=True`, `enable_bern2=True`) over tiny entity/gene dicts — the Phase-7 / 07-04 method — so the fixture matches emission byte-for-byte. The fixture carries labeled ChEBI (cheminf:000407), Entrez/Ensembl/UniProt gene xrefs, a GO component, and the external + minted predicate labels (239 triples, 45 rdfs:label).
- Registered the fixture in `property_audit.py` `extra_files` (basename key `iri-label-fixture.ttl`); ran the audit so `rdfs:label` enters `scripts/audit-results.json`.
- Added `generate_chemical_shape(main_audit, label_fixture_audit)` to `generate_shapes.py`: keeps the production-derived `ChemicalShape` (cheminf:000000) and adds a `ChemicalXrefShape` (cheminf:000407) carrying the `rdfs:label` constraint sourced from the fixture audit, with a loud WARNING fallback if the fixture audit is absent (mirrors the gene-shape fixture-absent guard).
- Added a `label_flag_gated` parameter to `generate_property_shapes` that demotes `rdfs:label` to a non-blocking `sh:Warning` (no minCount) ONLY for the external-xref classes (ChemicalXrefShape, gene-association typed shape) — so flag-off production ChEBI/gene subjects (which have no rdfs:label) still conform, while AOP/KE/KER keep their genuine 100% rdfs:label Violation.
- Extended `tests/integration/test_shacl_validation.py` with two tests: shapes carry the `rdfs:label` `sh:path`, and pyshacl conforms green against the flag-on fixture.
- Exempted the fixture from the `data-test/*` gitignore (tracked source artifact, mirroring the provenance fixture).

## Verification

- `python scripts/property_audit.py && python scripts/generate_shapes.py && python scripts/run_shacl_validation.py` → exit 0, **Status PASS, 0 violations** against production `data/`.
- pyshacl against the flag-on `data-test/iri-label-fixture.ttl` (chemical + gene-association shapes): **conforms=True, 0 violations**.
- `pytest tests/integration/test_compat_flag_off.py tests/integration/test_shacl_validation.py tests/unit/test_rdf_writer.py` → **30 passed, 2 skipped** (backup byte-diff opt-in), 5 deselected (documented pre-existing failures).
- `git diff ecad066 HEAD -- data/typelabels.txt` → **0 lines** (Pitfall 2 honored: typelabels.txt + its unconditional loop untouched).
- The always-on flag-off guard (`test_flag_off_emits_no_iri_labels`) passes → flag-off output byte-identical (COMPAT-01). The opt-in `COMPAT_CHECK_BACKUP` byte-diff skips cleanly (no backup snapshot in this worktree).
- Tests run with `PYTHONPATH=<worktree>/src` to override the shared editable install (documented gotcha).

## Deviations from Plan

### Deviation 1 (Rule 3 — blocking): predicate-label block needed prefix gating
- **Found during:** Task 1 (flag-on `test_rdf_writer.py` parse failed with `Prefix "foaf:" not bound`).
- **Issue:** The flag-on tests use a minimal `prefixes.csv` that omits `foaf:`; emitting `foaf:page rdfs:label …` produced unparseable Turtle.
- **Fix:** `_external_predicate_label_block` now skips any row whose CURIE prefix is not in the file's declared prefix set. Production declares all prefixes (full block emits); minimal test sets emit a subset. No unbound prefix is ever referenced.
- **Files:** `src/aopwiki_rdf/rdf/writer.py` — **Commit:** `4566513`

### Deviation 2 (Rule 1 — correctness): flag-gated rdfs:label must not be mandated on production data
- **Found during:** Task 2 (first `run_shacl_validation.py` produced 443 Violations).
- **Issue:** Generating the ChemicalXrefShape from the 100%-labeled fixture produced `rdfs:label sh:minCount 1; sh:Violation` on `cheminf:000407` — a class that EXISTS in flag-off production data/ with NO rdfs:label, breaking `test_no_violations_on_current_data`.
- **Fix:** Added `label_flag_gated` to `generate_property_shapes`, demoting rdfs:label to a non-blocking `sh:Warning` ONLY on the external-xref classes. Scoped narrowly so AOP/KE/KER unconditional labels keep their Violation constraint.
- **Files:** `scripts/generate_shapes.py` — **Commit:** `c3f17f0`

### Deviation 3 (Rule 3 — blocking): fixture chemical ENTITY broke ChemicalShape conformance
- **Found during:** Task 2 (fixture produced 3 Violations against the production-derived ChemicalShape).
- **Issue:** A synthetic `cheminf:000000` chemical entity in the fixture could not satisfy ChemicalShape's mandated entity properties (`dc:source`, `dcterms:isPartOf`, `cheminf:000568`).
- **Fix:** Removed the chemical entity from the fixture entirely. The ChemicalShape validates production data/, not the fixture; the fixture only needs the labeled ChEBI xref (cheminf:000407) to exercise the rdfs:label constraint.
- **Files:** `scripts/generate_iri_label_fixture.py` — **Commit:** `c3f17f0`

### Deviation 4 (Rule 3 — blocking, tooling): added a fixture generator + gitignore exemption
- The plan lists `data-test/iri-label-fixture.ttl` as a created artifact but the `data-test/*` gitignore would have silently dropped it (as it does for the provenance fixture). Added `scripts/generate_iri_label_fixture.py` (reproducible real-emission generator) and a `!data-test/iri-label-fixture.ttl` gitignore exemption so the fixture is a tracked source artifact. Out-of-scope shape drift (aop/ke/ker/stressor/enriched shapes, caused by `data/` being refreshed since the shapes were last regenerated) was reverted to keep the change scoped to `chemical-shape.ttl` per the plan's `files_modified`.

## Notes on the gene-association shape

The plan's acceptance criterion expects `chemical-shape.ttl` AND `gene-association-shape.ttl` to show a regeneration diff. `chemical-shape.ttl` changed (the new ChemicalXrefShape with rdfs:label). `gene-association-shape.ttl` regenerated **byte-identically** — it already carried the rdfs:label constraint (Warning, 50%) from the Phase-7 provenance fixture, and the `label_flag_gated` change is a no-op there (rdfs:label was already non-minCount). The requirement — the gene-association shape **validates** rdfs:label — is satisfied; no diff was needed.

## Out-of-Scope (Deferred, NOT fixed)

The 4 `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` failures and the 2 `test_batch_bridgedb.py` collection errors documented in both wave-1 summaries remain pre-existing on the base commit (`ecad066`); untouched (SCOPE BOUNDARY).

## Self-Check: PASSED

- Files present: `writer.py`, `namespaces.py`, `data-test/iri-label-fixture.ttl`, `scripts/generate_iri_label_fixture.py`, `shapes/chemical-shape.ttl` — all FOUND.
- Commits present: `4566513` (Task 1), `c3f17f0` (Task 2) — both FOUND in git history.
