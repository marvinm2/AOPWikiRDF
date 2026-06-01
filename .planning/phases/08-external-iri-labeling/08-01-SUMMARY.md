---
phase: 08-external-iri-labeling
plan: 01
subsystem: rdf
tags: [rdf, labeling, iri, coverage-report, feature-flag, determinism]

# Dependency graph
requires:
  - phase: 07-promote-bern2-to-primary-union-preserved
    provides: "symbol_lookup build-store-thread lifecycle, report_cache_coverage probe pattern, enable_bern2 flag convention"
provides:
  - "enable_iri_labels config flag (default False, byte-neutral when off)"
  - "build_gene_label_map / build_chem_label_map inverted xref_iri -> name maps (deterministic, network-free)"
  - "report_label_coverage + report_label_coverage_from_results (honest per-source coverage + JSON artifact)"
  - "gene_label_by_iri / chem_label_by_iri threaded into both writers via pipeline context"
affects: [08-02-writer-label-emission, 08-03-shacl-regen]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inverted xref_iri -> name map with alphabetically-first collision tiebreak (Pattern 3)"
    - "Coverage report mirroring report_cache_coverage + JSON artifact"
    - "Thin-orchestrator wrapper (report_label_coverage_from_results) to keep pipeline.py under the 600-line guard"

key-files:
  created:
    - src/aopwiki_rdf/mapping/iri_labels.py
    - tests/unit/test_iri_label_collision.py
    - tests/unit/test_iri_labels_no_network.py
    - tests/unit/test_label_coverage_report.py
  modified:
    - src/aopwiki_rdf/config.py
    - src/aopwiki_rdf/pipeline.py

key-decisions:
  - "Map keys are the exact prefixed xref IRI strings the writer iterates (chebi:, ncbigene:, cas:, ...) so the writer consumes them by loop variable"
  - "gene label = symbol_lookup.get(hgnc_key[5:], hgnc_key[5:]) — geneiddict keys are hgnc:<numeric>, NOT hgnc:<symbol> (corrected per plan interfaces over PATTERNS.md)"
  - "Label maps built unconditionally (cheap, side-effect-free); only EMISSION + coverage artifact are flag-gated, so flag-off output stays byte-identical"
  - "Coverage report assembly factored into report_label_coverage_from_results to keep pipeline.py thin (600-line orchestrator guard)"

patterns-established:
  - "Pattern 3 inverted label map: sorted() iteration + 'name < existing' tiebreak = order-independent byte-stable winner"
  - "Network-free helper: AST-level import guard test forbids importing requests / bridgedb (prose mentions allowed)"

requirements-completed: [LABEL-01, LABEL-02, LABEL-04]

# Metrics
duration: 35min
completed: 2026-06-01
---

# Phase 8 Plan 01: External-IRI Labeling Infrastructure Summary

**Built the Phase 8 label infrastructure — the `enable_iri_labels` flag, two deterministic network-free inverted `xref_iri -> name` label maps threaded into both RDF writers, and an honest per-source coverage report with JSON artifact — producing no `rdfs:label` triples itself but defining the contract Plans 08-02 (writer) and 08-03 (SHACL) consume.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-01
- **Completed:** 2026-06-01
- **Tasks:** 2 (both TDD)
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- Added `enable_iri_labels: bool = False` to `PipelineConfig`, mirroring the `enable_bern2` flag block (D-08); default off reproduces prior bytes exactly (COMPAT-01).
- Created `mapping/iri_labels.py` with `build_gene_label_map` and `build_chem_label_map`: byte-stable, order-independent (alphabetically-first collision tiebreak, D-03), network-free (LABEL-02 / D-01), keyed by the exact prefixed xref IRI strings the writer iterates.
- Added `report_label_coverage` mirroring `report_cache_coverage` (dict-return + sorted miss list + one INFO summary + truncated-to-50 miss line) AND writing the honest `data/label-coverage-report.json` artifact (LABEL-04 / D-07) — opaque IRIs are recorded, never silently dropped (D-02).
- Threaded `gene_label_by_iri` / `chem_label_by_iri` into BOTH writers (`write_aop_rdf` entities + `write_genes_rdf` gene_data — 4 thread sites) exactly like `symbol_lookup`; the coverage report runs only when the flag is on.
- Three Wave-0 unit-test scaffolds (collision/determinism, no-network, coverage report) all pass.

## Task Commits

1. **Task 1 (RED): failing tests for label-map builders** - `7570b3a` (test)
2. **Task 1 (GREEN): flag + inverted label-map builders** - `6e33447` (feat)
3. **Task 2 (RED): coverage-report test** - `eaf335c` (test)
4. **Task 2 (GREEN): coverage report + pipeline threading** - `88a0cbb` (feat)

_TDD gate sequence intact for both tasks: test() commit precedes feat() commit._

## Files Created/Modified

- `src/aopwiki_rdf/config.py` - added `enable_iri_labels: bool = False` flag block (no `__post_init__` change — bool field).
- `src/aopwiki_rdf/mapping/iri_labels.py` (NEW) - `build_gene_label_map`, `build_chem_label_map`, `report_label_coverage`, `report_label_coverage_from_results`, plus per-source IRI classification.
- `src/aopwiki_rdf/pipeline.py` - builds both maps once after the gene-xref stage, stores in context, threads into both writers, and calls the coverage report when the flag is on.
- `tests/unit/test_iri_label_collision.py` (NEW) - alphabetically-first tiebreak, order-independence, CAS/InChIKey/CompTox singleton coverage.
- `tests/unit/test_iri_labels_no_network.py` (NEW) - HTTP-explode monkeypatch + AST import guard.
- `tests/unit/test_label_coverage_report.py` (NEW) - per-source counts, sorted opaque-IRI record, JSON re-parse equality, determinism, flat-iterable acceptance.

## Key Interfaces for Plan 08-02 (writer)

The writer must consume these EXACT names (do not rename):

- `gene_label_by_iri: dict[str, str]` — `{xref_iri: hgnc_symbol}`, keyed by `ncbigene:…` / `ensembl:…` / `uniprot:…`.
- `chem_label_by_iri: dict[str, str]` — `{xref_iri: chemical_name}`, keyed by `chebi:…` / `cas:…` / `inchikey:…` / `comptox:…` / `chemspider:…` / `wikidata:…` / `chembl.compound:…` / `pubchem.compound:…` / `drugbank:…` / `kegg.compound:…` / `lipidmaps:…` / `hmdb:…`.

Both are present in `writer_entities` (main file) and `gene_data` (genes file). Values are bare names (chem `dc:title` surrounding quotes already stripped; gene symbols HGNC-controlled). Per T-08-01, values are byte-faithful to source and NOT pre-escaped — Turtle-literal escaping is the writer's emission-boundary job (Plan 08-02, T-08-04).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pipeline.py exceeded the 600-line orchestrator guard**
- **Found during:** Task 2 (after threading the maps and inlining the coverage-report assembly).
- **Issue:** `tests/unit/test_orchestrator.py::test_orchestrator_line_count` asserts `pipeline.py < 600` lines; the inlined per-source IRI list assembly pushed it to 623.
- **Fix:** Extracted the assembly into `report_label_coverage_from_results(...)` in `iri_labels.py` and condensed verbose comments, bringing `pipeline.py` to 598 lines while preserving the exact contract.
- **Files modified:** `src/aopwiki_rdf/mapping/iri_labels.py`, `src/aopwiki_rdf/pipeline.py`
- **Commit:** `88a0cbb`

**2. [Rule 1 - Test correctness] over-strict no-network prose check**
- **Found during:** Task 1 GREEN.
- **Issue:** The initial no-network test scanned the module text for the substring `"bridgedb"`, which false-positived on a legitimate docstring explaining why BridgeDb is not read.
- **Fix:** Rewrote the guard to parse the module AST and forbid importing `requests` / any `bridgedb` module (prose mentions allowed) — this tests the actual no-network intent.
- **Files modified:** `tests/unit/test_iri_labels_no_network.py`
- **Commit:** `6e33447`

## Out-of-Scope (Deferred, NOT fixed)

Four `tests/unit/test_rdf_writer.py::TestDualPredicateChemicalsAndProteinOntology` tests fail on the **unmodified base commit** (`a0dca7f`) against the main-repo package — they assert `skos:exactMatch` in chemical/protein-ontology xref output, predicate behaviour this plan does not touch. Verified pre-existing (fail with no 08-01 code on the path). Logged to `deferred-items.md`. Not addressed here (SCOPE BOUNDARY).

## TDD Gate Compliance

Both tasks followed RED → GREEN. RED commits (`7570b3a`, `eaf335c`) precede GREEN commits (`6e33447`, `88a0cbb`). No REFACTOR commit was needed beyond the line-count fix folded into the GREEN commit.

## Verification

- `pytest tests/unit/test_iri_label_collision.py tests/unit/test_iri_labels_no_network.py tests/unit/test_label_coverage_report.py -x` — 13 passed.
- `PipelineConfig().enable_iri_labels is False` — PASS (default off).
- `from aopwiki_rdf.mapping.iri_labels import build_gene_label_map, build_chem_label_map, report_label_coverage` — PASS.
- `tests/integration/test_compat_flag_off.py` — 1 passed, 2 skipped (no behaviour change with flag off).
- `tests/unit/test_orchestrator.py` (line-count guard) + `tests/unit/test_pipeline_no_exec.py` — all pass.

Note: tests were run with `PYTHONPATH=<worktree>/src` to override the shared editable install (`.pth` points at the main-repo `src` — the documented shared editable-install gotcha for this worktree).

## Self-Check: PASSED

All created files present and all 5 commits (4 task + 1 docs) verified in git history.
