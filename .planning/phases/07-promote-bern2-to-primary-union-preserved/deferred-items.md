# Deferred Items — Phase 07

Out-of-scope discoveries logged during execution. NOT fixed here (SCOPE BOUNDARY:
only auto-fix issues directly caused by the current task's changes).

## 07-01

- **Pre-existing failures in `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology`** (4 tests:
  `test_dual_predicate_chemicals`, `test_owl_only_chemicals`, `test_dual_predicate_protein_ontology`,
  `test_owl_only_protein_ontology`).
  These assert `skos:exactMatch` in the chemical / protein-ontology RDF emission. They fail on the
  clean base commit `14376e9` (verified by stashing the 07-01 change and re-running), so they are
  independent of the partial-chunk cache fix. The writer currently emits `cheminf:*` / `owl:sameAs`
  rather than `skos:exactMatch`, which is consistent with the Phase 3/4 predicate-correction decisions
  in STATE.md. Either the tests are stale relative to the current predicate policy or the writer
  regressed earlier. Surface to the writer/predicate owner; out of scope for the NER cache fix.
