---
phase: 10-enable-iri-labels-cli-flag-wiring
plan: 01
subsystem: cli-wiring
tags: [cli, argparse, pipeline-config, iri-labels]
requires:
  - PipelineConfig.enable_iri_labels (config.py, built Phase 8)
provides:
  - run_conversion.py --enable-iri-labels CLI flag
  - run_conversion.build_config(argv) testability helper
affects:
  - Phase 12 production flip (one-line workflow change unlocked)
tech-stack:
  added: []
  patterns:
    - "boolean opt-in argparse flag (action=store_true) threaded into PipelineConfig"
    - "testability-only build_config(argv) extraction; cli() delegates then calls main()"
key-files:
  created:
    - tests/unit/test_run_conversion_cli.py
  modified:
    - run_conversion.py
    - tests/unit/test_ner_el_mapper.py
decisions:
  - "build_config(argv) extracted so argparse->config is testable without invoking main() (D-01b)"
  - "strict flat copy of the --enable-bern2 wiring: no env vars, no workflow edits, no default flip (D-03)"
requirements: [LABEL-05]
metrics:
  duration: ~3m
  completed: 2026-06-18
---

# Phase 10 Plan 01: `--enable-iri-labels` CLI Flag Wiring Summary

Wired a `--enable-iri-labels` argparse flag on `run_conversion.py` through to `PipelineConfig.enable_iri_labels` (off by default), mirroring the existing `--enable-bern2` flag, plus a testability-only `build_config(argv)` helper and config-default + CLI-wiring tests proving the argparse->config plumbing directly.

## What Was Built

### Task 1 — Flag + build_config helper (commit ed21811)
- Added `--enable-iri-labels` (`action="store_true"`) immediately after the `--enable-bern2` block in `run_conversion.py`, with a multi-line `help=` sourced from `config.py:56-64`: emits a single untagged `rdfs:label` on external/component IRIs, no new network calls, OFF by default until the production flip, flag-off default run stays byte-identical.
- Threaded `enable_iri_labels=args.enable_iri_labels` into the existing `PipelineConfig(...)` constructor alongside `enable_bern2`.
- Extracted a testability-only `build_config(argv=None)` helper that builds the parser, calls `parser.parse_args(argv)`, and returns the constructed `PipelineConfig` without calling `main()`. `cli()` now delegates: `config = build_config(); main(config)`. Runtime behavior unchanged.
- The `--enable-bern2` argument block is byte-identical to the base (verified via `diff`); it simply now lives inside `build_config`.

### Task 2 — Tests (commit 698777a)
- Added `test_enable_iri_labels_defaults_false` to `TestPipelineConfigFields` in `tests/unit/test_ner_el_mapper.py`, mirroring `test_enable_bern2_defaults_false`.
- Created `tests/unit/test_run_conversion_cli.py` with three tests: flag-on => `enable_iri_labels is True`, flag-off => `False`, and bern2 default undisturbed. All assert on the constructed config only; none import or call `main()`, and none perform network/conversion I/O (`build_config` never reaches them).
- Confirmed (per `<criterion_3_resolution>`) that no pre-existing argparse-surface / forbidden-flag guard enumerating `--enable-bern2` exists to extend; the new CLI wiring test serves as the flag's CLI guard. No new guard invented (D-03).

## Verification

- `python -c "import run_conversion; assert run_conversion.build_config(['--enable-iri-labels']).enable_iri_labels is True; assert run_conversion.build_config([]).enable_iri_labels is False"` exits 0.
- Scoped test run: `pytest tests/unit/test_run_conversion_cli.py tests/unit/test_ner_el_mapper.py -k "iri_labels"` => 4 passed.
- `git diff --stat ae148a1 HEAD` touches only `run_conversion.py`, `tests/unit/test_ner_el_mapper.py`, and `tests/unit/test_run_conversion_cli.py` — NOT `src/aopwiki_rdf/config.py` and NO `.github/` workflow files.
- `tests/integration/test_compat_flag_off.py` is unchanged; the `--enable-bern2` argument block is byte-identical to base.

## Deviations from Plan

None — plan executed as written. Rules 1-4 not triggered; no auto-fixes required.

## Deferred Issues

**Pre-existing pytest basename collision (out of scope — scope boundary):**
A bare `python -m pytest -k "enable_iri_labels" -q` from the repo root aborts during *collection* with `import file mismatch` for `test_enhanced_precision.py`, because two files share that basename (root-level smoke test vs `tests/unit/`) and the test tree has no `__init__.py` packages. This is pre-existing and independent of this plan's changes: it reproduces identically with the untouched selector `-k "enable_bern2 or precision"`, and none of the three files this plan touches are involved. Not fixed here per the scope boundary (pre-existing failure in unrelated files). The plan's own success criteria are met when the selection is scoped to the relevant test files/dirs — all 4 `enable_iri_labels` tests pass. A future cleanup could rename the root-level smoke test or add `__init__.py` files / set pytest `importmode=importlib`.

## TDD Gate Compliance

Tasks carried `tdd="true"`, but the plan deliberately structures implementation in Task 1 and the test files in Task 2 (the bern2-parity pattern). MVP+TDD runtime gate was inactive (no `MVP_MODE`/`TDD_MODE` passed; `config.json` workflow flags unset), so the standard per-task flow applied. Resulting git history: `feat(10-01)` (wiring) followed by `test(10-01)` (config-default + CLI wiring tests), both green.

## Self-Check: PASSED

- FOUND: run_conversion.py (contains `--enable-iri-labels`, `build_config`, `enable_iri_labels=args.enable_iri_labels`)
- FOUND: tests/unit/test_ner_el_mapper.py (contains `test_enable_iri_labels_defaults_false`)
- FOUND: tests/unit/test_run_conversion_cli.py (contains `build_config`, `enable_iri_labels`)
- FOUND commit ed21811 (feat: flag + build_config)
- FOUND commit 698777a (test: config-default + CLI wiring)
