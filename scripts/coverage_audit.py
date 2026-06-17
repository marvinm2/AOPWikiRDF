"""XML→RDF coverage audit (XML-01).

Enumerates the namespace-qualified element/attribute universe of an AOP-Wiki XML
snapshot, derives the parser's *covered* set directly from the parser source
(elements via ``aopxml + '...'`` find/findall reads, attributes via
``.get('...')`` reads), diffs to an *actionable* gap set
(``instance − covered − allowlist``), ranks gaps by ``occurrences × semantic
weight``, optionally walks the historical quarterly snapshots for
snapshot-over-snapshot deltas (graceful skip when absent), and writes a
machine-readable ``scripts/coverage-report.json``.

Design notes
------------
* The covered set is read from ``src/aopwiki_rdf/parser/xml_parser.py`` via two
  regexes (elements + attributes). The parser is NOT imported — re-declaring the
  namespace constant avoids the parser's heavy transitive imports and a network
  HGNC download at import time.
* Gaps are computed from INSTANCE data (``instance − covered − allowlist``), not
  from bare XSD declarations. The XSD is an INFORMATIONAL axis only (D-01): it
  sets ``in_xsd`` per element and an ``xsd_only_count`` (declared-but-never-seen),
  never the actionable gap set.
* Only the latest snapshot is authoritative (D-05). The historical walk (D-04) is
  optional and degrades to a ``::warning::`` skip; the authoritative report never
  depends on it (Pitfall 6 — the sibling ``versions/`` dir is not a CI dependency).
* Security: stdlib ``ElementTree`` resolves no external entities by default and we
  do NOT enable custom entity resolution (T-09-03). ``iterparse`` + ``el.clear()``
  bounds memory on the ~48 MB snapshot. No new runtime dependency is added.

Mirrors the JSON-audit idiom of ``scripts/property_audit.py`` and the
``main(argv=None)`` → exit-code CLI shape of ``scripts/qc_delta_guard.py``.
"""

import argparse
import collections
import glob
import gzip
import json
import os
import re
import sys
import urllib.request
from xml.etree.ElementTree import iterparse, parse

# Re-declared verbatim from src/aopwiki_rdf/parser/xml_parser.py:25 (D-03).
# Do NOT import the parser just for this constant — that triggers its heavier
# transitive imports (and an HGNC network call path).
AOPXML_NS = "{http://www.aopkb.org/aop-xml}"
NAMESPACE = "http://www.aopkb.org/aop-xml"

# XML Schema namespace, for the informational XSD axis (D-01).
XS_NS = "{http://www.w3.org/2001/XMLSchema}"

SCHEMA_VERSION = "1.0"

# Default locations resolved relative to the repo root (this file lives in scripts/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PARSER_SRC = os.path.join(
    BASE_DIR, "src", "aopwiki_rdf", "parser", "xml_parser.py"
)
DEFAULT_ALLOWLIST = os.path.join(
    BASE_DIR, "data", "schema", "coverage-allowlist.json"
)
DEFAULT_XSD = os.path.join(BASE_DIR, "data", "schema", "aop-wiki-xml.xsd")
DEFAULT_XSD_SOURCE = DEFAULT_XSD + ".SOURCE"
DEFAULT_REPORT_PATH = os.path.join(BASE_DIR, "scripts", "coverage-report.json")

# aopwiki.org download template for the optional historical walk (D-04).
DOWNLOAD_URL_TEMPLATE = "https://aopwiki.org/downloads/aop-wiki-xml-{date}.gz"

# Snapshot filename pattern: aop-wiki-xml-YYYY-MM-DD (optionally .gz).
_SNAPSHOT_DATE_RE = re.compile(r"aop-wiki-xml-(\d{4}-\d{2}-\d{2})")


# ---------------------------------------------------------------------------
# Covered-set derivation (from parser source)
# ---------------------------------------------------------------------------
def derive_covered_sets(parser_src_path=DEFAULT_PARSER_SRC):
    """Derive the parser's covered element + attribute sets from its source.

    The covered ELEMENT set is every name the parser passes to ``find``/
    ``findall`` — these appear in the source as ``aopxml + 'NAME'``. The covered
    ATTRIBUTE set is every name the parser reads via ``.get('NAME')`` (e.g.
    ``id``, ``key-event-id``, ``taxonomy-id``). Walking BOTH axes is mandatory
    (D-03): omitting the ``.get()`` axis is the #1 false-gap source (Pitfall 1).

    Parameters
    ----------
    parser_src_path : str
        Path to ``xml_parser.py``.

    Returns
    -------
    tuple(set, set)
        ``(covered_elements, covered_attrs)``.
    """
    with open(parser_src_path) as fh:
        src = fh.read()
    covered_elements = set(re.findall(r"aopxml \+ '([^']+)'", src))
    covered_attrs = set(re.findall(r"\.get\('([^']+)'\)", src))
    return covered_elements, covered_attrs


# ---------------------------------------------------------------------------
# Instance enumeration (streaming)
# ---------------------------------------------------------------------------
def _open_snapshot(xml_path):
    """Open a snapshot for streaming, transparently handling ``.gz``."""
    if xml_path.endswith(".gz"):
        return gzip.open(xml_path, "rb")
    return open(xml_path, "rb")


def enumerate_instance(xml_path):
    """Stream a snapshot and count element local-names + (element, attr) pairs.

    Uses ``iterparse`` + ``el.clear()`` to bound memory on the ~48 MB snapshot.
    Custom entity resolution is NOT enabled (stdlib default only; T-09-03).

    Parameters
    ----------
    xml_path : str
        Path to an AOP-Wiki XML snapshot (plain or ``.gz``).

    Returns
    -------
    tuple(collections.Counter, collections.Counter)
        ``(element_counts, attribute_counts)`` where attribute keys are
        ``(local_name, attr_name)`` tuples.
    """
    element_counts = collections.Counter()
    attribute_counts = collections.Counter()
    with _open_snapshot(xml_path) as handle:
        for _event, el in iterparse(handle, events=("end",)):
            local = el.tag.replace(AOPXML_NS, "")
            element_counts[local] += 1
            for attr in el.attrib:
                attribute_counts[(local, attr)] += 1
            el.clear()
    return element_counts, attribute_counts


# ---------------------------------------------------------------------------
# XSD informational axis (D-01)
# ---------------------------------------------------------------------------
def parse_xsd_declared(xsd_path):
    """Collect declared element/attribute names from the XSD (info axis, D-01).

    The XSD is parsed AS XML via ElementTree (NOT via ``xmlschema`` — the
    structured-XSD library route is deliberately not taken; T-09-SC). We collect
    every ``xs:element``/``xs:attribute`` ``name=`` / ``ref=`` declaration. This
    is informational only: it sets ``in_xsd`` per element and feeds
    ``xsd_only_count`` (declared-but-never-seen). It never drives the actionable
    gap set.

    Parameters
    ----------
    xsd_path : str
        Path to the vendored XSD, or a path that may not exist.

    Returns
    -------
    set
        Declared element/attribute local names. Empty set when the XSD is absent.
    """
    if not xsd_path or not os.path.exists(xsd_path):
        return set()
    declared = set()
    tree = parse(xsd_path)
    for tag in ("element", "attribute"):
        for node in tree.iter(XS_NS + tag):
            name = node.get("name") or node.get("ref")
            if name:
                # ref may be prefix-qualified (e.g. "aop:foo"); take local part.
                declared.add(name.split(":")[-1])
    return declared


# ---------------------------------------------------------------------------
# Semantic weights (optional, editable — D-06)
# ---------------------------------------------------------------------------
def load_semantic_weights(weights_path):
    """Load an optional ``{element: weight}`` map. Missing/absent → empty."""
    if not weights_path or not os.path.exists(weights_path):
        return {}
    with open(weights_path) as fh:
        return json.load(fh)


def load_allowlist(allowlist_path):
    """Load the D-09 coverage allowlist ``{element: reason}``. Absent → empty."""
    if not allowlist_path or not os.path.exists(allowlist_path):
        return {}
    with open(allowlist_path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Historical snapshot walk (optional, graceful skip — D-04 / Pitfall 6)
# ---------------------------------------------------------------------------
def _snapshot_date(path):
    """Extract the YYYY-MM-DD date token from a snapshot path, or None."""
    match = _SNAPSHOT_DATE_RE.search(os.path.basename(path))
    return match.group(1) if match else None


def discover_snapshots(snapshots_dir):
    """Return ``[(date, path)]`` for snapshots in ``snapshots_dir``, sorted.

    Matches ``aop-wiki-xml-YYYY-MM-DD`` and ``aop-wiki-xml-YYYY-MM-DD.gz``.
    Returns an empty list when the directory is absent or empty.
    """
    if not snapshots_dir or not os.path.isdir(snapshots_dir):
        return []
    found = {}
    for pattern in ("aop-wiki-xml-*", "**/aop-wiki-xml-*"):
        for path in glob.glob(os.path.join(snapshots_dir, pattern), recursive=True):
            if not os.path.isfile(path):
                continue
            date = _snapshot_date(path)
            if date:
                # Prefer plain over .gz when both exist for the same date.
                if date not in found or not path.endswith(".gz"):
                    found[date] = path
    return sorted(found.items())


def walk_history(snapshots_dir, download_missing=False):
    """Walk historical snapshots → ``{date: element_counts}`` (D-04).

    Each quarter's coverage is computed against THAT quarter's own instance
    universe (Pitfall 3); we only record per-snapshot element occurrence maps
    here and let the caller compute deltas. Degrades gracefully: an absent dir
    yields ``{}`` and the caller prints the ``::warning::``.

    Parameters
    ----------
    snapshots_dir : str or None
        Directory of historical snapshots.
    download_missing : bool
        Reserved hook for on-demand ``.gz`` download (informational axis only;
        a failed download is skipped, never fatal — T-09-04).

    Returns
    -------
    dict
        ``{date: collections.Counter(element_counts)}``.
    """
    history = {}
    for date, path in discover_snapshots(snapshots_dir):
        try:
            element_counts, _attrs = enumerate_instance(path)
        except Exception as exc:  # noqa: BLE001 - historical axis is informational
            print(
                f"::warning::failed to parse historical snapshot {path}: {exc}",
                file=sys.stderr,
            )
            continue
        history[date] = element_counts
    return history


# ---------------------------------------------------------------------------
# Core audit
# ---------------------------------------------------------------------------
def run(
    xml_path,
    allowlist_path=DEFAULT_ALLOWLIST,
    report_path=DEFAULT_REPORT_PATH,
    snapshots_dir=None,
    parser_src_path=DEFAULT_PARSER_SRC,
    xsd_path=DEFAULT_XSD,
    semantic_weights_path=None,
    download_missing=False,
    generated_for_snapshot=None,
):
    """Run the coverage audit against ``xml_path`` and write the JSON report.

    Parameters
    ----------
    xml_path : str
        Latest (authoritative) snapshot to audit (D-05).
    allowlist_path : str
        D-09 coverage allowlist path.
    report_path : str
        Output JSON path.
    snapshots_dir : str or None
        Optional historical snapshot directory (D-04). Absent/empty → graceful
        ``::warning::`` skip; the report still stands on the latest snapshot.
    parser_src_path : str
        Parser source for covered-set derivation.
    xsd_path : str
        Vendored XSD for the informational ``in_xsd`` axis (D-01).
    semantic_weights_path : str or None
        Optional ``{element: weight}`` override for ranking (D-06).
    download_missing : bool
        Reserved on-demand download hook for the historical walk.
    generated_for_snapshot : str or None
        Explicit snapshot date label; inferred from ``xml_path`` when None.

    Returns
    -------
    dict
        The full report (also written to ``report_path``). Top-level keys:
        ``schema_version``, ``generated_for_snapshot``, ``namespace``,
        ``xsd_source``, ``elements``, ``attributes``, ``gaps``, ``summary``.
    """
    covered_elements, covered_attrs = derive_covered_sets(parser_src_path)
    allowlist = load_allowlist(allowlist_path)
    weights = load_semantic_weights(semantic_weights_path)
    declared_in_xsd = parse_xsd_declared(xsd_path)

    element_counts, attribute_counts = enumerate_instance(xml_path)

    # Optional historical walk (D-04). Graceful skip when absent (Pitfall 6).
    if snapshots_dir and os.path.isdir(snapshots_dir):
        history = walk_history(snapshots_dir, download_missing=download_missing)
    else:
        print(
            "::warning::historical snapshots dir absent; latest-snapshot report only"
        )
        history = {}

    snapshot_date = generated_for_snapshot or _snapshot_date(xml_path) or "latest"

    # --- Per-element records ------------------------------------------------
    elements = {}
    gaps = []
    for name, count in element_counts.items():
        covered = name in covered_elements
        allowlisted = name in allowlist
        weight = float(weights.get(name, 1.0))

        # Per-snapshot occurrences map (D-04): latest is always present; merge in
        # historical counts. Latest snapshot is authoritative (D-05).
        occ_map = {snapshot_date: count}
        for hist_date, hist_counts in history.items():
            if name in hist_counts:
                occ_map[hist_date] = hist_counts[name]

        # delta_vs_prev: latest minus the chronologically-previous snapshot.
        delta_vs_prev = None
        prev_dates = sorted(d for d in occ_map if d < snapshot_date)
        if prev_dates:
            delta_vs_prev = count - occ_map[prev_dates[-1]]

        is_gap = (not covered) and (not allowlisted)
        record = {
            "covered": covered,
            "emitted_by_parser": covered,
            "is_attribute": False,
            "allowlisted": allowlisted,
            "occurrences": count,
            "occurrences_by_snapshot": dict(sorted(occ_map.items())),
            "delta_vs_prev": delta_vs_prev,
            "in_xsd": name in declared_in_xsd,
            "is_gap": is_gap,
            "rank_score": round(count * weight, 1) if is_gap else 0.0,
        }
        elements[name] = record
        if is_gap:
            gaps.append(name)

    # --- Per-attribute records (D-03 attribute axis) ------------------------
    attributes = {}
    for (local, attr), count in attribute_counts.items():
        key = f"{local}@{attr}"
        covered = attr in covered_attrs
        attributes[key] = {
            "element": local,
            "attribute": attr,
            "covered": covered,
            "emitted_by_parser": covered,
            "is_attribute": True,
            "occurrences": count,
        }

    # Rank gaps by rank_score desc, then name for stable ties.
    gaps.sort(key=lambda n: (-elements[n]["rank_score"], n))

    covered_element_count = sum(1 for r in elements.values() if r["covered"])
    instance_element_count = len(elements)
    actionable_gap_count = len(gaps)
    coverage_pct = (
        round(covered_element_count / instance_element_count * 100, 1)
        if instance_element_count
        else 0.0
    )
    # XSD-only: declared in XSD but never seen in this instance (info only, D-01).
    seen_names = set(elements)
    xsd_only_count = len(declared_in_xsd - seen_names) if declared_in_xsd else 0

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_for_snapshot": snapshot_date,
        "namespace": NAMESPACE,
        "xsd_source": _read_xsd_source(),
        "elements": elements,
        "attributes": attributes,
        "gaps": gaps,
        "summary": {
            "instance_element_count": instance_element_count,
            "covered_element_count": covered_element_count,
            "actionable_gap_count": actionable_gap_count,
            "coverage_pct": coverage_pct,
            "xsd_only_count": xsd_only_count,
            "historical_snapshots_walked": len(history),
        },
    }

    if report_path:
        with open(report_path, "w") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)

    return report


def _read_xsd_source(source_path=DEFAULT_XSD_SOURCE):
    """Best-effort read of the vendored XSD provenance pin (.SOURCE → JSON).

    Returns a dict with whatever keys the .SOURCE file provides (repo/tag/
    sha256/url/retrieved). Absent or unreadable → an empty dict (the provenance
    block is documentary, never load-bearing for the audit result).
    """
    if not source_path or not os.path.exists(source_path):
        return {}
    try:
        with open(source_path) as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Snapshot selection
# ---------------------------------------------------------------------------
def find_latest_snapshot(data_dir=None):
    """Return the newest ``aop-wiki-xml-YYYY-MM-DD`` snapshot on disk, or None.

    Searches ``data/`` first, then the repo root. The latest by date token is
    authoritative (D-05).
    """
    data_dir = data_dir or os.path.join(BASE_DIR, "data")
    candidates = {}
    for directory in (data_dir, BASE_DIR):
        for path in glob.glob(os.path.join(directory, "aop-wiki-xml-*")):
            if not os.path.isfile(path) or path.endswith(".SOURCE"):
                continue
            date = _snapshot_date(path)
            if date:
                candidates.setdefault(date, path)
    if not candidates:
        return None
    latest = max(candidates)
    return candidates[latest]


def main(argv=None):
    """CLI entry point. Returns an exit code (0 on success)."""
    parser = argparse.ArgumentParser(
        description="XML→RDF coverage audit (XML-01): enumerate the AOP-Wiki "
        "element/attribute universe of the latest snapshot, derive the parser's "
        "covered set, diff to an actionable gap set, and write a JSON report."
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Path to the latest (authoritative) XML snapshot. "
        "Default: newest data/aop-wiki-xml-* on disk.",
    )
    parser.add_argument(
        "--report-path",
        default=DEFAULT_REPORT_PATH,
        help="Where to write coverage-report.json "
        "(default: scripts/coverage-report.json).",
    )
    parser.add_argument(
        "--allowlist",
        default=DEFAULT_ALLOWLIST,
        help="Path to data/schema/coverage-allowlist.json (D-09).",
    )
    parser.add_argument(
        "--snapshots-dir",
        default=None,
        help="Optional directory of historical snapshots for the per-snapshot "
        "delta walk (D-04). Absent → graceful ::warning:: skip.",
    )
    parser.add_argument(
        "--semantic-weights",
        default=None,
        help="Optional JSON {element: weight} override for gap ranking (D-06).",
    )
    parser.add_argument(
        "--download-missing",
        action="store_true",
        help="Reserved: allow on-demand .gz download for historical snapshots "
        "(informational axis only; failures are skipped, never fatal).",
    )
    args = parser.parse_args(argv)

    snapshot = args.snapshot or find_latest_snapshot()
    if not snapshot:
        print(
            "::error::no XML snapshot found (pass --snapshot or place an "
            "aop-wiki-xml-YYYY-MM-DD file under data/).",
            file=sys.stderr,
        )
        return 1
    if not os.path.exists(snapshot):
        print(f"::error::snapshot not found: {snapshot}", file=sys.stderr)
        return 1

    report = run(
        xml_path=snapshot,
        allowlist_path=args.allowlist,
        report_path=args.report_path,
        snapshots_dir=args.snapshots_dir,
        semantic_weights_path=args.semantic_weights,
        download_missing=args.download_missing,
    )
    summary = report["summary"]
    print(
        f"Coverage audit ({report['generated_for_snapshot']}): "
        f"{summary['covered_element_count']}/{summary['instance_element_count']} "
        f"elements covered ({summary['coverage_pct']}%); "
        f"{summary['actionable_gap_count']} actionable gaps. "
        f"Report → {args.report_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
