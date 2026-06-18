---
phase: 11-compat-closing-gate
plan: 03
subsystem: ci-gate
tags: [compat, gate, masking, difflib, workflow-dispatch, byte-identity]

# Dependency graph
requires:
  - phase: 11-compat-closing-gate
    plan: 01
    provides: "the --xml-file pinned-snapshot knob (run_conversion -> PipelineConfig.xml_file -> _stage_parse) that compat_check.regenerate() drives"
provides:
  - "scripts/compat_check.py: the COMPAT closing gate (mask 4 date families, dual off-vs-on HARD + off-vs-golden advisory comparison, per-subject difflib diff, 0/1 exit)"
  - "tests/unit/test_compat_check.py: masker coverage+survival+idempotency, two-dates no-drift, negative injected-diff fail path, off-vs-on additive-only"
  - ".github/workflows/compat-gate.yml: workflow_dispatch-only milestone gate (120-min timeout, diff artifact on failure)"
affects: [12-production-flip]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone-gate house style mirrored from qc_delta_guard.py (docstring -> constants -> pure helpers -> run() returns dict -> print_report -> main(argv) 0/1 -> sys.exit(main()))"
    - "Line/predicate-anchored date masking (stdlib re only) instead of bnode canonicalization / rdflib round-trip (D-05)"
    - "Monkeypatchable regenerate() seam so unit tests drive run()/main() on fixture corpora offline"
    - "Additive-subset comparison: flag-on may ADD subjects/predicates but must not drop/change a flag-off subject"

key-files:
  created:
    - scripts/compat_check.py
    - tests/unit/test_compat_check.py
    - .github/workflows/compat-gate.yml
  modified: []

key-decisions:
  - "off-vs-on is the HARD gate (BridgeDb-immune, both runs back-to-back on same snapshot); off-vs-golden is advisory only (may drift on BridgeDb) -- only off-vs-on sets the exit code (D-01)"
  - "Mask exactly four families datatype/predicate-anchored so XML-sourced bare dcterms:created/dcterms:modified literals survive (D-03); masks #2/#4 anchored on ^^xsd:date / ^^xsd:dateTime"
  - "No rdflib.serialize / isomorphic / canonicalization -- comparison on masked raw bytes chunked per subject block (D-05)"
  - "subject_blocks strips per-block whitespace so an end-of-file block compares EQUAL to the same block followed by another (positional split is not a content diff)"

requirements-completed: [COMPAT-01]

# Metrics
duration: ~30min
completed: 2026-06-18
---

# Phase 11 Plan 03: COMPAT Closing Gate Summary

**`scripts/compat_check.py` regenerates the pipeline flags-off and flags-on against the pinned committed snapshot, masks the four run-varying date-token families, runs the dual comparison (off-vs-on HARD additive-subset + off-vs-golden advisory byte-identity), emits a per-subject `difflib` diff on mismatch and exits 0/1 — the COMPAT-01 byte-identity safety proof that must be green before the Phase 12 flip.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3 (Tasks 1 & 2 TDD; Task 3 config)
- **Files created:** 3

## Accomplishments

- **Task 1 — `scripts/compat_check.py`:** built the gate mirroring `qc_delta_guard.py`'s standalone shape (module docstring stating WHAT it proves + masking method + dual-comparison policy + no-canonicalization note + exit-code contract -> constants -> pure helpers -> `run()` -> `print_report` -> `main(argv)`). `mask(raw)->bytes` applies the FOUR line/predicate-anchored regexes (idempotent, stdlib `re` only, with a cross-ref comment to `writer.py` 794/1006/1051/1094). `subject_blocks` / `first_subject` chunk per subject; `diff_report` renders a truncated per-subject `difflib.unified_diff`. `regenerate(...)` is the monkeypatchable regen seam (drives `run_conversion` `PipelineConfig` flags-off then flags-on into temp dirs against the same `--xml-file`). `run(...)` performs the dual comparison and `main(argv)` returns 0/1.
- **Task 2 — fail-proof + additive-only tests:** `test_gate_fails_on_injected_diff` (the mandatory negative sample — a mutated SHARED subject breaches, `main()` returns 1, the report names the mutated subject IRI), `test_identical_inputs_pass`, and `test_off_vs_on_delta_is_additive_only` (a flag-gated `prov:Activity` addition does NOT breach). All offline via a monkeypatched `regenerate`.
- **Task 3 — `.github/workflows/compat-gate.yml`:** `workflow_dispatch`-only milestone job, `timeout-minutes: 120`, `pip install -r requirements.txt && pip install -e .`, runs `compat_check.py` against `data/compat-golden/`, `if: failure()` uploads `compat-diff-report.txt` (retention 30d). No badge/commit/push steps.

## Task Commits

1. **Task 1: compat_check.py (masker + subject-diff + dual comparison)** — `a7b311d` (test, RED), `842d578` (feat, GREEN)
2. **Task 2: negative-sample + additive-only tests (+ block-strip fix)** — `e60ef0c` (test + Rule 1 fix)
3. **Task 3: compat-gate.yml workflow** — `e9e19e7` (ci)

_Plan metadata commit follows this SUMMARY._

## Files Created

- `scripts/compat_check.py` — the COMPAT gate: four-family masker, per-subject difflib diff, dual off-vs-on HARD / off-vs-golden advisory comparison, monkeypatchable `regenerate()` seam, `main()` 0/1.
- `tests/unit/test_compat_check.py` — masker coverage + XML-date survival + idempotency, two-dates no-drift, identical-inputs pass, negative injected-diff fail path, off-vs-on additive-only.
- `.github/workflows/compat-gate.yml` — workflow_dispatch-only milestone gate (120-min timeout, diff artifact on failure).

## Decisions Made

- The HARD off-vs-on comparison alone sets the exit code; off-vs-golden is advisory because BridgeDb drift between the golden's capture and now can legitimately differ (RESEARCH Pitfall 2). This keeps the gate BridgeDb-immune (T-11-06: a poisoned golden cannot green a real flag-gated regression).
- Masks #2 (`pav:createdOn`^^xsd:date) and #4 (`dcterms:modified`^^xsd:dateTime) are datatype-anchored so they cannot match the bare quoted XML-sourced `dcterms:created`/`dcterms:modified` literals (verified by `test_mask_covers_all_runvarying`'s survival assertion).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `subject_blocks` did not normalize per-block trailing whitespace**
- **Found during:** Task 2 (`test_off_vs_on_delta_is_additive_only`)
- **Issue:** Splitting on `b"\n\n"` left an end-of-file subject block carrying a trailing `\n` while the SAME block followed by another block did not, so an additive-only flag-on corpus spuriously reported the last flag-off subject as "changed". This would have produced false-positive breaches on every real run (the flag-on corpus always appends subjects).
- **Fix:** `subject_blocks` now `b.strip()`s each retained block so the positional split is not mistaken for a content difference. Off-vs-golden identity mode still uses full-byte equality, so masking coverage is unaffected.
- **Files modified:** `scripts/compat_check.py`
- **Verification:** `tests/unit/test_compat_check.py` — 6 passed; additive-only no longer breaches, the injected-diff negative sample still breaches.
- **Committed in:** `e60ef0c` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Correctness fix to the additive-subset comparison; no scope change. The four-family masking spec (D-03) and no-canonicalization rule (D-05) are unaffected.

## Threat Model Coverage

- **T-11-05 (incomplete mask):** `test_mask_covers_all_runvarying` asserts all four families become `<MASKED>` AND the XML bare dates survive; mask kept in sync with `writer.py` via a source-cross-ref comment (D-03). Mitigated.
- **T-11-06 (poisoned golden):** the HARD off-vs-on comparison is independent of the golden (D-01). Mitigated.
- **T-11-07 (DoS via mis-triggered 28-90 min regen):** `compat-gate.yml` is `workflow_dispatch` only, never push/schedule/weekly pytest, 120-min timeout cap (D-06). Mitigated.
- **T-11-08 (16 MB diff blob):** per-subject diff truncated to `DEFAULT_MAX_BLOCKS=50` (D-07). Accepted-low, bounded.

## Known Stubs

None. The gate consumes the pinned snapshot + golden paths exactly as the plan specifies; golden TTL materialization is Plan 11-02's job (sibling worktree) and was deliberately not regenerated or committed here.

## Verification

- `python -m pytest tests/unit/test_compat_check.py -q` — 6 passed (masker coverage + survival + idempotency, two-dates no-drift, negative injected-diff, off-vs-on additive-only), <1s, no network.
- `python -m pytest tests/unit/test_compat_check.py tests/integration/test_compat_flag_off.py -q` — 9 passed, 2 skipped (the gate complements, does not break, the existing flag-off contract — D-07).
- `compat-gate.yml` parses, `on:` has exactly `workflow_dispatch`, `timeout-minutes: 120`, `if: failure()` upload-artifact@v7 of `compat-diff-report.txt`, no badge/push (verify one-liner prints PASS).
- All test runs used `PYTHONPATH="$(pwd)/src"` to bind the worktree package (shared editable-install gotcha; see project MEMORY).

**Outstanding (manual, by design):** the full-corpus `compat-gate.yml` `workflow_dispatch` green run (28-90 min) is the PHASE GATE before Phase 12 and is recorded as a manual verification — it is not run in this plan.

## User Setup Required

None for this plan. The manual `compat-gate.yml` run (Phase gate) requires the maintainer to trigger the workflow once Plan 11-02's `data/compat-golden/` golden corpus is committed on `master`.

## Self-Check: PASSED

All three created files present on disk; all five task commits exist in git (verified below).

---
*Phase: 11-compat-closing-gate*
*Completed: 2026-06-18*
