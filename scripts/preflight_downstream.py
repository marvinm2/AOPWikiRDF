#!/usr/bin/env python3
"""
Downstream SPARQL pre-flight harness (plan 12-02, D-04 / D-05).

Loads the curated downstream query corpora (the AOPWikiSNORQL ``*.rq`` library and
the AOP-Wiki-RDF-dashboard ``methodology_notes.json`` entries) and runs each query
against TWO local Virtuoso loads:

  * a baseline load of the current committed (pre-flip) ``data/*.ttl`` corpus, and
  * a load of the flags-on TTLs (BERN2-primary + IRI labels).

Each query is classified against the D-05 bar:
  * errored against flags-on data                                  -> FAIL
  * returned >=1 row pre-flip but 0 rows post-flip (row regression) -> FAIL
  * rising / equal counts (additive enrichment) and 0->0            -> PASS

A Markdown evidence report is emitted and the process exits nonzero on any breach,
so the report can gate / be linked in the Wave 2 flip PR.

The sibling corpora (``../AOPWikiSNORQL`` and
``../AOPWikiRDF-multiEndpoint/AOP-Wiki-RDF-dashboard``) are read STRICTLY READ-ONLY;
nothing is ever written into them.

No external SPARQL client library is used (none exists in this repo); SPARQL is
executed with the already-present ``requests`` dependency.
"""

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

import requests

# --------------------------------------------------------------------------- #
# Defaults (corpus roots point at the adjacent sibling repos; D-04)
# --------------------------------------------------------------------------- #
DEFAULT_SNORQL_ROOT = "../AOPWikiSNORQL"
DEFAULT_METHODOLOGY_NOTES = (
    "../AOPWikiRDF-multiEndpoint/AOP-Wiki-RDF-dashboard/"
    "static/data/methodology_notes.json"
)
DEFAULT_FLAGS_OFF_DIR = "data"
DEFAULT_FLAGS_ON_DIR = "/tmp/flagson"
DEFAULT_ENDPOINT = "http://localhost:8890/sparql/"
DEFAULT_REPORT_PATH = "preflight-downstream-report.md"
DEFAULT_WORKERS = 5
DEFAULT_TIMEOUT = 60


# --------------------------------------------------------------------------- #
# PURE helpers (Task 1 — network-free, fixture-testable)
# --------------------------------------------------------------------------- #

def _parse_param_defaults(lines):
    """Map param name -> declared default from ``# param: name|type|default|label`` headers."""
    defaults = {}
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        # tolerate "#param:" and "# param:"
        body = stripped.lstrip("#").strip()
        if not body.lower().startswith("param:"):
            continue
        spec = body[len("param:"):].strip()
        parts = spec.split("|")
        if len(parts) >= 3:
            name = parts[0].strip()
            default = parts[2].strip()
            if name:
                defaults[name] = default
    return defaults


def _strip_header_comments(text):
    """Drop every line whose first non-whitespace char is ``#`` (the .rq metadata header)."""
    kept = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(kept).strip()


def _substitute_mustache(query, defaults):
    """Replace each ``{{name}}`` placeholder with the param's declared default."""
    for name, default in defaults.items():
        query = query.replace("{{" + name + "}}", default)
    return query


def load_rq_corpus(root):
    """Discover ``*.rq`` files under ``root`` (read-only) and return query records.

    Each record is ``{source, name, query}`` with the ``# ...`` header comments
    stripped from the body and any ``{{param}}`` Mustache placeholders replaced by
    the matching ``# param:`` header's declared default.
    """
    root = Path(root)
    records = []
    for path in sorted(root.rglob("*.rq")):
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        defaults = _parse_param_defaults(lines)
        body = _strip_header_comments(raw)
        body = _substitute_mustache(body, defaults)
        records.append({
            "source": "SNORQL",
            "name": path.stem,
            "query": body,
        })
    return records


def load_json_corpus(path):
    """Load ``methodology_notes.json`` (read-only) and return one record per query.

    The dashboard's methodology notes come in two shapes:

      * single-query entries carry ``entry["sparql"]`` (one query), and
      * multi-query entries carry ``entry["queries"]`` — a list of
        ``{"caption": ..., "query": ...}`` sub-queries.

    Both shapes are emitted so the full downstream corpus is covered (D-04). A
    multi-query entry yields one record per sub-query, named
    ``"<entry>::<caption>"`` (falling back to a positional index). Entries with
    neither a ``sparql`` nor a usable ``queries`` payload are skipped.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue

        query = entry.get("sparql")
        if query:
            records.append({
                "source": "methodology_notes",
                "name": name,
                "query": query,
            })

        queries = entry.get("queries")
        if isinstance(queries, list):
            for idx, sub in enumerate(queries):
                if not isinstance(sub, dict):
                    continue
                sub_query = sub.get("query")
                if not sub_query:
                    continue
                caption = sub.get("caption") or f"q{idx}"
                records.append({
                    "source": "methodology_notes",
                    "name": f"{name}::{caption}",
                    "query": sub_query,
                })
    return records


def classify(pre_count, post_count, errored):
    """Apply the D-05 pass/fail bar.

    FAIL when the query errored against flags-on data, OR when it returned at least
    one row pre-flip but zero rows post-flip (no-row-regression bar). Otherwise PASS
    — rising counts (additive enrichment), equal counts, and 0->0 are all expected.
    """
    if errored:
        return "FAIL"
    if pre_count >= 1 and post_count == 0:
        return "FAIL"
    return "PASS"


def save_report(records, path):
    """Write a Markdown PASS/FAIL evidence table mirroring the save_*_report idiom.

    Each record is ``{source, name, pre_count, post_count, status, errored}``.
    """
    path = Path(path)
    total = len(records)
    fails = [r for r in records if r.get("status") == "FAIL"]
    n_fail = len(fails)
    n_pass = total - n_fail

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Downstream SPARQL Pre-flight Report\n\n")
        f.write(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
        f.write(f"**Total queries**: {total}\n\n")
        f.write(f"**PASS**: {n_pass}\n\n")
        f.write(f"**FAIL**: {n_fail}\n\n")
        f.write(f"**Result**: {'PASS' if n_fail == 0 else 'FAIL'} "
                f"(D-05 bar: no error, no >=1-row-to-0-row regression)\n\n")

        if fails:
            f.write("## Failures\n\n")
            f.write("| Source | Name | Pre | Post | Errored |\n")
            f.write("|---|---|---|---|---|\n")
            for r in fails:
                f.write(
                    f"| {r.get('source', '')} | {r.get('name', '')} "
                    f"| {r.get('pre_count', '')} | {r.get('post_count', '')} "
                    f"| {r.get('errored', '')} |\n"
                )
            f.write("\n")

        f.write("## All Queries\n\n")
        f.write("| Status | Source | Name | Pre | Post | Errored |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in sorted(records, key=lambda x: (x.get("status", ""),
                                                x.get("source", ""),
                                                x.get("name", ""))):
            f.write(
                f"| {r.get('status', '')} | {r.get('source', '')} "
                f"| {r.get('name', '')} | {r.get('pre_count', '')} "
                f"| {r.get('post_count', '')} | {r.get('errored', '')} |\n"
            )
        f.write("\n")


# --------------------------------------------------------------------------- #
# Network / Docker-facing layer (Task 2 — wired here, run operationally by a human)
# --------------------------------------------------------------------------- #

def run_query(endpoint, query, timeout=DEFAULT_TIMEOUT):
    """Execute a SPARQL query against a local Virtuoso endpoint.

    Returns ``(row_count, errored)``. On any HTTP/parse error, returns
    ``(0, True)`` so the classifier flags it. Uses raw ``requests`` (no external
    SPARQL client) with ``Accept: application/sparql-results+json``.
    """
    try:
        resp = requests.post(
            endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        bindings = resp.json()["results"]["bindings"]
        return len(bindings), False
    except (requests.exceptions.RequestException, ValueError, KeyError):
        return 0, True


def run_corpus(records, endpoint, workers=DEFAULT_WORKERS, timeout=DEFAULT_TIMEOUT):
    """Run every record's query against ``endpoint`` concurrently.

    Returns a dict keyed by ``(source, name)`` -> ``(row_count, errored)``.
    """
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_key = {
            executor.submit(run_query, endpoint, rec["query"], timeout):
                (rec["source"], rec["name"])
            for rec in records
        }
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception:  # noqa: BLE001 — defensive; treat as errored
                results[key] = (0, True)
    return results


def main(argv=None):
    """CLI entry point. Returns 0 only when every query passes the D-05 bar.

    Runs the combined corpus twice — once against the flags-off (baseline,
    pre-flip) Virtuoso load for ``pre_count`` and once against the flags-on load
    for ``post_count`` — then classifies, writes the Markdown report, and exits
    nonzero on any FAIL.

    NOTE: this entry point assumes the caller has already loaded the two TTL sets
    into Virtuoso (or points ``--flags-off-endpoint`` / ``--flags-on-endpoint`` at
    two running instances). It executes SPARQL but does not itself start Docker.
    """
    parser = argparse.ArgumentParser(
        description="Downstream SPARQL pre-flight harness (D-04/D-05): run the "
                    "curated ~90-query corpus against flags-off and flags-on "
                    "local Virtuoso loads and flag any error or row regression."
    )
    parser.add_argument("--flags-off-dir", default=DEFAULT_FLAGS_OFF_DIR,
                        help="Directory with the committed (pre-flip) TTLs for the "
                             "baseline load (default: data).")
    parser.add_argument("--flags-on-dir", default=DEFAULT_FLAGS_ON_DIR,
                        help="Directory with the LOCAL flags-on TTLs (BERN2-primary "
                             "+ IRI labels; NOT committed). Default: /tmp/flagson.")
    parser.add_argument("--snorql-root", default=DEFAULT_SNORQL_ROOT,
                        help="Read-only root of the AOPWikiSNORQL .rq library "
                             "(default: ../AOPWikiSNORQL).")
    parser.add_argument("--methodology-notes", default=DEFAULT_METHODOLOGY_NOTES,
                        help="Read-only path to the dashboard methodology_notes.json.")
    parser.add_argument("--flags-off-endpoint", default=DEFAULT_ENDPOINT,
                        help="SPARQL endpoint for the baseline (flags-off) load.")
    parser.add_argument("--flags-on-endpoint", default=DEFAULT_ENDPOINT,
                        help="SPARQL endpoint for the flags-on load.")
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH,
                        help=f"Markdown evidence report path "
                             f"(default: {DEFAULT_REPORT_PATH}).")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Concurrent SPARQL workers (default: {DEFAULT_WORKERS}).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-query HTTP timeout in seconds "
                             f"(default: {DEFAULT_TIMEOUT}).")
    args = parser.parse_args(argv)

    # Load both corpora (read-only).
    records = load_rq_corpus(args.snorql_root)
    records.extend(load_json_corpus(args.methodology_notes))
    print(f"Loaded {len(records)} downstream queries "
          f"({sum(1 for r in records if r['source'] == 'SNORQL')} .rq + "
          f"{sum(1 for r in records if r['source'] == 'methodology_notes')} "
          f"methodology_notes).")

    # Baseline (pre-flip) pass.
    print(f"Running baseline corpus against {args.flags_off_endpoint} ...")
    pre = run_corpus(records, args.flags_off_endpoint,
                     workers=args.workers, timeout=args.timeout)

    # Flags-on (post-flip) pass.
    print(f"Running flags-on corpus against {args.flags_on_endpoint} ...")
    post = run_corpus(records, args.flags_on_endpoint,
                      workers=args.workers, timeout=args.timeout)

    # Classify.
    report_records = []
    for rec in records:
        key = (rec["source"], rec["name"])
        pre_count, _pre_err = pre.get(key, (0, True))
        post_count, post_err = post.get(key, (0, True))
        status = classify(pre_count, post_count, post_err)
        report_records.append({
            "source": rec["source"],
            "name": rec["name"],
            "pre_count": pre_count,
            "post_count": post_count,
            "errored": post_err,
            "status": status,
        })

    save_report(report_records, args.report_path)
    n_fail = sum(1 for r in report_records if r["status"] == "FAIL")
    print(f"Report written to {args.report_path}: "
          f"{len(report_records) - n_fail} PASS, {n_fail} FAIL.")

    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
