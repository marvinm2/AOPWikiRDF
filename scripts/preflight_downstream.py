#!/usr/bin/env python3
"""
Downstream SPARQL pre-flight harness (plan 12-02, D-04 / D-05).

This module loads the curated downstream query corpora (the AOPWikiSNORQL ``*.rq``
library and the AOP-Wiki-RDF-dashboard ``methodology_notes.json`` entries) and
classifies each query against the D-05 pass/fail bar:
  * errored against flags-on data                                  -> FAIL
  * returned >=1 row pre-flip but 0 rows post-flip (row regression) -> FAIL
  * rising / equal counts (additive enrichment) and 0->0            -> PASS

The sibling corpora (``../AOPWikiSNORQL`` and
``../AOPWikiRDF-multiEndpoint/AOP-Wiki-RDF-dashboard``) are read STRICTLY READ-ONLY;
nothing is ever written into them.

This file currently provides the PURE, network-free helpers (corpus loaders, the
``classify`` bar, and the Markdown ``save_report`` writer). The SPARQL-execution
and CLI ``main()`` layer is wired in a follow-up.
"""

import json
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Defaults (corpus roots point at the adjacent sibling repos; D-04)
# --------------------------------------------------------------------------- #
DEFAULT_SNORQL_ROOT = "../AOPWikiSNORQL"
DEFAULT_METHODOLOGY_NOTES = (
    "../AOPWikiRDF-multiEndpoint/AOP-Wiki-RDF-dashboard/"
    "static/data/methodology_notes.json"
)
DEFAULT_REPORT_PATH = "preflight-downstream-report.md"


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
    """Load ``methodology_notes.json`` (read-only) and return one record per entry.

    Each value is a dict; the SPARQL is pulled from ``entry["sparql"]``. Entries
    without a ``sparql`` key are skipped.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        query = entry.get("sparql")
        if not query:
            continue
        records.append({
            "source": "methodology_notes",
            "name": name,
            "query": query,
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
