# Deferred items — Phase 07

Out-of-scope discoveries logged during plan execution. NOT fixed here (SCOPE
BOUNDARY: only auto-fix issues directly caused by the current task's changes).

## 07-01 (partial-chunk cache integrity)

- **Pre-existing failures in `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology`** (4 tests:
  `test_dual_predicate_chemicals`, `test_owl_only_chemicals`, `test_dual_predicate_protein_ontology`,
  `test_owl_only_protein_ontology`).
  These assert `skos:exactMatch` in the chemical / protein-ontology RDF emission. They fail on the
  clean base commit `14376e9` (verified by stashing the 07-01 change and re-running), so they are
  independent of the partial-chunk cache fix. The writer currently emits `cheminf:*` / `owl:sameAs`
  rather than `skos:exactMatch`, which is consistent with the Phase 3/4 predicate-correction decisions
  in STATE.md. Either the tests are stale relative to the current predicate policy or the writer
  regressed earlier. Surface to the writer/predicate owner; out of scope for the NER cache fix.

## 07-03 (PROV-O activity layer)

- **`tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` — same 4 pre-existing failures.**
  - Tests: `test_dual_predicate_chemicals`, `test_owl_only_chemicals`,
    `test_dual_predicate_protein_ontology`, `test_owl_only_protein_ontology`.
  - Symptom: `assert 'skos:exactMatch' in content` fails — the `write_aop_rdf`
    chemical/protein-ontology blocks no longer emit `skos:exactMatch` (or the
    `emit_legacy_predicates` wiring for chemicals/PRO differs from what these
    tests expect).
  - Scope: exercises `write_aop_rdf` (MAIN file) chemical + protein-ontology
    emission. 07-03 only touched the genes-file header
    (`GENES_PROVENANCE_ACTIVITIES`) — these paths were never modified.
  - Verified pre-existing: failing on the worktree base commit before any
    07-03 source edit (confirmed via `git stash` of the two edited files).
  - Action: leave for the owning phase/plan (predicate-correction lineage,
    Phase 03 / chemical+PRO dual-predicate work). Do NOT fix in 07-03.
