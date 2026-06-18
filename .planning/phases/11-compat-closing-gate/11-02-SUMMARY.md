---
phase: 11-compat-closing-gate
plan: 02
subsystem: infra
tags: [compat, golden, gitignore, xml-snapshot, fixture, flag-off]

# Dependency graph
requires:
  - phase: 11-compat-closing-gate
    plan: 01
    provides: "the --xml-file PATH knob (run_conversion -> PipelineConfig.xml_file -> _stage_parse) that regenerates the pipeline against a committed XML snapshot"
provides:
  - "data/compat-golden/ populated with the 5-file flag-off COMPAT golden (~22 MB) regenerated from the committed snapshot"
  - "data/compat-golden/aop-wiki-xml-2026-06-18.gz — the pinned gzipped XML snapshot the golden was built from"
  - ".gitignore allowlist exempting data/compat-golden/ (+ *.ttl + the .gz) from the data/*.ttl and aop-wiki-xml* blanket ignores"
affects: [11-03 compat_check gate, 12 production flip]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "gitignore blanket-ignore + directory/glob/explicit-file ! allowlist (mirrors data/schema/ and the 5 live data/*.ttl exceptions)"
    - "Golden frozen ONCE from a known-good state (RESEARCH option c): live BridgeDb + fresh HGNC at freeze time; off-vs-on is the Plan 03 hard gate, off-vs-golden is the advisory drift check"

key-files:
  created:
    - data/compat-golden/AOPWikiRDF.ttl
    - data/compat-golden/AOPWikiRDF-Genes.ttl
    - data/compat-golden/AOPWikiRDF-Enriched.ttl
    - data/compat-golden/AOPWikiRDF-Void.ttl
    - data/compat-golden/ServiceDescription.ttl
    - data/compat-golden/aop-wiki-xml-2026-06-18.gz
  modified:
    - .gitignore

key-decisions:
  - "Golden frozen 2026-06-18 from that day's HGNC dump + live BridgeDb (RESEARCH option c) — embedded wall-clock dates are masked by the Plan 03 gate, so the fresh-run timestamps need not match the golden"
  - "The .gz snapshot gets its OWN explicit ! line because the more-specific aop-wiki-xml* rule is not overridden by a bare directory exception in all git versions (same reason data/schema/aop-wiki-xml.xsd is listed explicitly)"

requirements-completed: [COMPAT-01]

# Metrics
duration: ~12min
completed: 2026-06-18
golden-freeze-date: 2026-06-18
---

# Phase 11 Plan 02: Pinned Flag-Off COMPAT Golden Summary

**Froze the in-repo flag-off COMPAT golden — the full 5-file flag-off TTL set (~22 MB) regenerated from a committed gzipped XML snapshot, plus that snapshot itself, with a `.gitignore` allowlist that keeps git from silently swallowing them — replacing the stale `production-rdf-backup/` anti-pattern with a reproducible, reviewable Wave-0 fixture the Plan 03 gate reads.**

## Golden Freeze

- **Freeze date:** 2026-06-18
- **Built from:** `data/compat-golden/aop-wiki-xml-2026-06-18.gz` (committed pinned snapshot) via `run_conversion.py --xml-file ... --output-dir /tmp/compat-golden-build` — confirmed in the run log (`Read pinned XML snapshot data/compat-golden/aop-wiki-xml-2026-06-18.gz`), never from `production-rdf-backup/` (D-04).
- **Flags:** OFF — no `--enable-bern2`, no `--enable-iri-labels`.
- **Embedded wall-clock dates** in the golden (`# Generated`, `pav:createdOn`, `pav:importedOn`, ServiceDescription `dcterms:modified`) reflect the 2026-06-18 freeze run. The Plan 03 gate masks these four token families, so a fresh gate run on a later calendar day does not need to match the golden's timestamps.

## Performance

- **Duration:** ~12 min wall (conversion itself ~8.5 min / 511.8s)
- **Tasks:** 2 (both `type=auto`)
- **Files created:** 6 (5 TTLs + 1 .gz); **modified:** 1 (`.gitignore`)

## Task Commits

1. **Task 1: gitignore allowlist + pinned XML snapshot** — `a72b181` (chore)
2. **Task 2: regenerate + freeze the 5 flag-off golden TTLs** — `2e384e4` (feat)

_Plan metadata commit (this SUMMARY) follows._

## Files Created/Modified

- `.gitignore` — appended a COMPAT golden allowlist block (`!data/compat-golden/`, `!data/compat-golden/*.ttl`, `!data/compat-golden/aop-wiki-xml-2026-06-18.gz`) with an explanatory comment, mirroring the `data/schema/` directory+explicit-file pattern.
- `data/compat-golden/aop-wiki-xml-2026-06-18.gz` — pinned gzipped XML snapshot (~9.7 MB); gunzips to a byte (SHA-256)-identical copy of the source uncompressed XML.
- `data/compat-golden/AOPWikiRDF.ttl` (~19 MB), `AOPWikiRDF-Genes.ttl` (~2.1 MB), `AOPWikiRDF-Enriched.ttl` (~188 KB), `AOPWikiRDF-Void.ttl` (~3.5 KB), `ServiceDescription.ttl` (~1.5 KB) — the 5-file flag-off golden; all parse cleanly as Turtle and carry zero flag-on tokens.

## Verification Results

- `git check-ignore` returns rc=1 (NOT ignored) for all 6 committed paths — the Phase 9 gitignore-swallow bug class is avoided. (See "Acceptance-criteria nuance" below for why `check-ignore -v` prints the negation line rather than literally nothing.)
- All 5 golden TTLs are committed (`git ls-files data/compat-golden/` lists all 6 artifacts) and staged as new tracked files.
- The 5 TTLs parse cleanly via rdflib (no syntax error).
- Flag-off cleanliness: `prov:wasGeneratedBy`, `prov:Activity`, `:isFeaturedMethod`, `:BERN2NERMapping`, `:RegexGeneMapping`, `@prefix prov:` all return 0 in the golden — no BERN2/iri-label leakage.
- The `.gz` round-trips to the source uncompressed XML (SHA-256 PASS).

## Acceptance-criteria nuance (documented, not a deviation)

The plan's Task 1/Task 2 acceptance text says `git check-ignore -v <path>` should "print NOTHING (rc=1)". In practice, for a freshly-allowlisted path that is **not yet tracked**, `git check-ignore -v` prints the matching negation line (`.gitignore:NN:!data/compat-golden/...`) with rc=0 — git reports the last matching pattern, and the `!` un-ignore rule IS a match. The live tracked TTL `data/AOPWikiRDF.ttl` only prints "nothing, rc=1" because `check-ignore` skips files already in the index by default; with `--no-index` it prints the identical `.gitignore:47:!data/AOPWikiRDF.ttl` negation line and rc=0. The semantically meaningful, swallow-detecting check — `git check-ignore <path>` WITHOUT `-v` — returns rc=1 (NOT ignored) for every golden artifact, and `git add` tracks them (`A` in `git status`). The acceptance criterion's intent (no swallow; artifacts trackable) is fully met; the literal "rc=1 from `-v`" only holds once the files are committed (which they now are).

## Genes-file size note (expected, BridgeDb/HGNC drift)

The frozen `AOPWikiRDF-Genes.ttl` (~2.1 MB, 67,038 lines) is smaller than the current live `data/AOPWikiRDF-Genes.ttl` (~4.5 MB, 131,780 lines) and the RESEARCH ~4.3 MB footprint estimate. This is the expected consequence of RESEARCH option (c): the golden is frozen once from the freeze-day HGNC dump + live BridgeDb response, which differs from whatever populated the older live file. It is not a regression — the Plan 03 hard gate compares flags-off vs flags-on within a SINGLE invocation (BridgeDb-immune); the off-vs-golden comparison is the advisory drift-sensitive check. The main `AOPWikiRDF.ttl` (~19 MB) is in the expected order of magnitude.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Copied the gitignored uncompressed XML snapshot into the worktree**
- **Found during:** Task 1 (gzip the on-disk uncompressed XML)
- **Issue:** The plan's input `data/aop-wiki-xml-2026-06-18` (47 MB, gitignored) was present in the main checkout but NOT carried into the git worktree, because `.git`-ignored files are not part of the branch the worktree checks out. Task 1 gzips this exact on-disk snapshot.
- **Fix:** Copied the identical pinned snapshot from the main checkout (`/home/marvin/.../AOPWikiRDF/data/aop-wiki-xml-2026-06-18`, SHA-256 `0ef77cf2...`) into the worktree before gzipping. The `.gz` round-trip SHA-256 confirms byte-identity.
- **Files modified:** none committed (the uncompressed XML stays gitignored by design; only the `.gz` is committed)
- **Committed in:** N/A (input staging only)

---

**Total deviations:** 1 auto-fixed (1 blocking, input staging only — no behavior or output change)
**Impact on plan:** None on output. The golden is built from the byte-identical pinned snapshot the plan intended.

## Issues Encountered

- **Shared editable-install path:** `import aopwiki_rdf` resolves to the *main checkout* `src/` via the shared `.pth`, not the worktree (documented in project MEMORY). The worktree already carries the `--xml-file` knob (merged at base `c02fc93`), and the conversion log confirms the pinned-snapshot branch ran, so the resolution did not affect output; rdflib parse checks were run with `PYTHONPATH="$(pwd)/src"` to bind the worktree package.
- **Local BridgeDb down:** `http://localhost:8183/Human/` unreachable; the pipeline's `webservice.bridgedb.org` fallback was used (versions logged: `Ensembl:108`, `HMDB-CHEBI-WIKIDATA`). This is the freeze-time live state the golden captures (RESEARCH option c).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The Wave-0 fixture for the COMPAT gate is frozen: Plan 11-03 (`scripts/compat_check.py`) can now read `data/compat-golden/` directly and regenerate fresh flags-off / flags-on passes against `data/compat-golden/aop-wiki-xml-2026-06-18.gz` for its two-comparison gate.
- The gate MUST mask the four wall-clock token families (`# Generated`, `pav:createdOn`, `pav:importedOn`, ServiceDescription `dcterms:modified`) so the golden does not false-fail across calendar days.

## Self-Check: PASSED

- All 6 created files exist under `data/compat-golden/` and are committed (`git ls-files data/compat-golden/` lists all 6).
- `.gitignore` modified and committed.
- Both task commits exist in git: `a72b181` (Task 1), `2e384e4` (Task 2).

---
*Phase: 11-compat-closing-gate*
*Completed: 2026-06-18*
*Golden frozen: 2026-06-18*
