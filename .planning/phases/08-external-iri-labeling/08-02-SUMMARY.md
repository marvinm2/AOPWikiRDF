---
phase: 08-external-iri-labeling
plan: 02
subsystem: rdf-writer
tags: [rdfs-label, turtle, writer, iri-labelling, byte-stability, shacl]

requires:
  - phase: 08-external-iri-labeling (Plan 08-01, parallel wave 1)
    provides: "config.enable_iri_labels flag + chem_label_by_iri / gene_label_by_iri maps threaded into the writer entities/gene_data dicts"
provides:
  - "flag-gated rdfs:label emission on every external xref IRI (chemical xrefs ChEBI..HMDB, CAS/InChIKey/CompTox, gene xrefs Entrez/UniProt/Ensembl in BOTH writers)"
  - "component-IRI rdfs:label fill (taxonomy, go:, pato: object/action, CellTypeContext, OrganContext) derived from local dc:title (D-04)"
  - "Turtle-escaping of all emitted label values (T-08-04) and no-all-digit-pseudo-label guarantee (D-02)"
  - "always-on flag-off COMPAT-01 guard test + flag-on label assertions"
affects: [08-03 (predicate labels / namespaces), SHACL shape generation gaining rdfs:label constraint]

tech-stack:
  added: []
  patterns:
    - "byte-stable triple splice: optional clause returned by a helper, '' when off, spliced before the terminal '.' so flag-off bytes are identical"
    - "value-only Turtle escaping helper for label literals"

key-files:
  created: []
  modified:
    - src/aopwiki_rdf/rdf/writer.py
    - tests/integration/test_compat_flag_off.py
    - tests/unit/test_rdf_writer.py

key-decisions:
  - "Two label-clause helpers: _iri_label_clause (xref IRIs, map lookup, D-02 unmapped->no label) and _component_label_clause (components, mirror local dc:title, strip one pair of surrounding quotes)"
  - "emit_labels read via null-safe bool(config and getattr(config,'enable_iri_labels',False)) so config=None tests and the not-yet-present 08-01 config field both work"
  - "flag-on unit tests use a duck-typed SimpleNamespace config (enable_iri_labels=True) to avoid coupling this worktree's tests to the enable_iri_labels field that parallel Plan 08-01 adds to PipelineConfig"
  - "did NOT touch the typelabels.txt unconditional class-label loop, the HGNC label blocks, or prefixes.csv (Pitfall 2 / already-labeled)"

patterns-established:
  - "Pattern: gated label splice co-located with dc:source, byte-identical flag-off"
  - "Pattern: component label sourced verbatim from the local dc:title literal"

requirements-completed: [LABEL-01, LABEL-03]

duration: 22min
completed: 2026-06-01
---

# Phase 8 Plan 02: External-IRI Labeling (writer emission) Summary

**Both RDF writers now emit a single untagged, Turtle-escaped `rdfs:label` co-located with `dc:source` on every external xref IRI and every component IRI when `enable_iri_labels` is on — while flag-off output stays byte-identical, proven by an always-on guard test.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-06-01 (worktree wave 1)
- **Completed:** 2026-06-01
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

### Task 1 — flag-gated label emission in both writers (commit 23dff61)
- Added three module-level helpers to `writer.py`:
  - `_turtle_escape(value)` — escapes `\`, `"`, `\n`, `\r`, `\t` in label values only (T-08-04).
  - `_iri_label_clause(emit_labels, iri, label_map)` — returns `' ;\n\trdfs:label\t"<name>"'` when on and the IRI has a non-empty name in the map; `''` otherwise (D-02: unmapped IRIs stay unlabeled, no all-digit pseudo-label).
  - `_component_label_clause(emit_labels, title_literal)` — mirrors the local `dc:title` (stripping one pair of surrounding quotes when present) for component IRIs (D-04).
- Read `emit_labels = bool(config and getattr(config, 'enable_iri_labels', False))` at the top of BOTH `write_aop_rdf` and `write_genes_rdf`, and unpacked `chem_label_by_iri` / `gene_label_by_iri` from the entities/gene_data dicts (defaulting to `{}`).
- Spliced the gated label clause immediately before the terminal `.` (after `dc:source`) on:
  - **Main file (`write_aop_rdf`):** CAS, InChIKey, CompTox, ChEBI, ChemSpider, Wikidata, ChEMBL, PubChem, DrugBank, KEGG, LIPID MAPS, HMDB (`chem_label_by_iri`); Entrez + UniProt gene xrefs (`gene_label_by_iri`); taxonomy, biological-process (go:), biological-object (pato:), biological-action (pato:), cell-term, organ-term components (local `dc:title`).
  - **Genes file (`write_genes_rdf`):** Entrez, Ensembl, UniProt gene xrefs (`gene_label_by_iri`) — Pitfall 3, this writer emits its own gene xrefs separately.
- Left untouched: HGNC blocks (already labeled), the unconditional `typelabels.txt` class-label loop (Pitfall 2), and `prefixes.csv`.

### Task 2 — tests (commit ff6ad36)
- `tests/integration/test_compat_flag_off.py::test_flag_off_emits_no_iri_labels` — always-on (backup-free) guard: writes main + genes files with `config=None` over entities that populate only subjects unlabeled-when-off (no hgnclist, no typelabels.txt, no stressors), asserts zero `rdfs:label` in either output.
- `tests/unit/test_rdf_writer.py::TestExternalIriLabelsFlagOn` — flag-on:
  - exactly one `rdfs:label` with the expected name on a mapped ChEBI, a mapped Entrez, and a GO component subject;
  - none on an unmapped ChEBI IRI (D-02);
  - genes-file Entrez/Ensembl/UniProt each labeled (Pitfall 3);
  - a quote-bearing label round-trips through `rdflib.Graph().parse` (T-08-04 escaping).

## Verification

- `pytest tests/unit/test_rdf_writer.py tests/integration/test_compat_flag_off.py tests/integration/test_output_separation.py` → **31 passed, 2 skipped, 4 pre-existing failures** (see Deferred Issues). The 4 failures predate this plan and are unrelated.
- The 5 new tests all pass; all previously-passing tests still pass (flag-off byte-identity intact).
- The opt-in byte-diff guard (`COMPAT_CHECK_BACKUP`) skips cleanly when no backup is present.
- Tests run with `PYTHONPATH=<worktree>/src` to override the shared editable install whose `.pth` hardcodes the main-repo `src` (see MEMORY: shared editable-install gotcha).

## Deviations from Plan

### Deviation 1 (Rule 3 — blocking): flag-on tests use a duck-typed config, not PipelineConfig
- **Found during:** Task 2.
- **Issue:** The plan's Task 2 action says "construct `PipelineConfig(enable_iri_labels=True)`". That field is added by the **parallel** Plan 08-01 in a separate worktree and is NOT present in this worktree's `config.py`, so `PipelineConfig(enable_iri_labels=True)` raises `TypeError` here and would make this plan's tests un-runnable pre-merge.
- **Fix:** Flag-on tests construct a `types.SimpleNamespace(enable_iri_labels=True, ...)`. The writer reads the flag via the null-safe `getattr(config, 'enable_iri_labels', False)` idiom, so the duck-typed object exercises the exact label path without coupling to the config change. Documented inline in the test helper.
- **Files modified:** tests/unit/test_rdf_writer.py
- **Commit:** ff6ad36
- **Post-merge note:** once 08-01 lands `enable_iri_labels` on `PipelineConfig`, these tests continue to pass unchanged; they could optionally be switched to the real config in a later cleanup, but it is not required.

### Deviation 2 (Rule 3 — blocking): missing `chedict` key in a test fixture
- **Found during:** Task 2 (first test run raised `KeyError: 'chedict'`).
- **Fix:** Added `'chedict': {}` to the `_label_entities()` helper (`write_aop_rdf` requires the key).
- **Commit:** ff6ad36

## Deferred Issues

Four tests in `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` (`test_dual_predicate_protein_ontology`, `test_owl_only_protein_ontology`, `test_dual_predicate_chemicals`, `test_owl_only_chemicals`) **fail on the clean base commit `a0dca7f`**, before any 08-02 edit. They assert `owl:sameAs`/`skos:exactMatch` in the **main** file produced by `write_aop_rdf`, but the Phase 4 output-separation work moved those triples to `write_enriched_rdf` (`AOPWikiRDF-Enriched.ttl`). The tests were never repointed at the enriched writer and are stale. Out of scope for plan 08-02; logged in `deferred-items.md`, left untouched.

## Integration Notes for Wave Merge

- New writer parameters are read from the entities/gene_data dicts under the keys **`chem_label_by_iri`** and **`gene_label_by_iri`** — exactly the names Plan 08-01 threads in. No further wiring needed on this side post-merge.
- `emit_labels` keys off `config.enable_iri_labels`; until 08-01 lands that flag on `PipelineConfig`, production runs (which use real `PipelineConfig`) see the attribute via 08-01's change, and the writer defaults to off if it is ever absent.
- The byte-identity contract (flag off → byte-identical output, COMPAT-01) is enforced by the always-on `test_flag_off_emits_no_iri_labels` plus the opt-in backup byte-diff.

## Self-Check: PASSED

- All modified files exist on disk: writer.py, test_compat_flag_off.py, test_rdf_writer.py, 08-02-SUMMARY.md.
- All task commits present in git history: 23dff61 (Task 1), ff6ad36 (Task 2).
