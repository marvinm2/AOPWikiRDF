"""Triple-for-triple regression test: modularized pipeline vs monolith.

Runs both pipelines against the same AOP-Wiki XML and compares sorted
NTriples output for all three TTL files. Blank node labels are normalized
before comparison.

Usage:
    python -m pytest tests/integration/test_regression.py -x -s
    # or standalone:
    python tests/integration/test_regression.py
"""

import glob
import re
import shutil
import tempfile
from pathlib import Path

import pytest
from rdflib import Graph

from aopwiki_rdf.config import PipelineConfig


# Date/time patterns that vary between runs
_DATE_RE = re.compile(r'"?\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}[^"]*)?("|\^\^)', re.ASCII)
_BLANK_RE = re.compile(r'_:\w+')


def normalize_ntriples(nt_text: str) -> list[str]:
    """Normalize NTriples for comparison: sort lines, normalize blank nodes and dates."""
    lines = nt_text.strip().split('\n')
    normalized = []
    for line in lines:
        if not line.strip():
            continue
        # Normalize blank node labels
        line = _BLANK_RE.sub('_:BLANK', line)
        # Normalize date/time literals so VoID timestamps don't cause false diffs
        line = _DATE_RE.sub('"NORMALIZED-DATE\\2', line)
        normalized.append(line)
    return sorted(normalized)


def compare_ttl_files(file_a: str, file_b: str) -> tuple[bool, list[str]]:
    """Compare two TTL files via sorted NTriples.

    Returns (match: bool, diffs: list of diff descriptions).
    """
    g_a = Graph()
    g_a.parse(file_a, format='turtle')
    g_b = Graph()
    g_b.parse(file_b, format='turtle')

    nt_a = normalize_ntriples(g_a.serialize(format='nt'))
    nt_b = normalize_ntriples(g_b.serialize(format='nt'))

    if nt_a == nt_b:
        return True, []

    set_a = set(nt_a)
    set_b = set(nt_b)
    only_in_a = sorted(set_a - set_b)
    only_in_b = sorted(set_b - set_a)

    total_unique = len(set_a | set_b)
    diff_count = len(only_in_a) + len(only_in_b)
    diff_pct = (diff_count / total_unique * 100) if total_unique > 0 else 0

    diffs = [f"Diff: {diff_count} triples differ out of {total_unique} unique ({diff_pct:.2f}%)"]
    diffs.append(f"Only in monolith ({len(only_in_a)} total):")
    diffs += [f"  {t}" for t in only_in_a[:20]]
    if len(only_in_a) > 20:
        diffs.append(f"  ... and {len(only_in_a) - 20} more")
    diffs.append(f"Only in modular ({len(only_in_b)} total):")
    diffs += [f"  {t}" for t in only_in_b[:20]]
    if len(only_in_b) > 20:
        diffs.append(f"  ... and {len(only_in_b) - 20} more")

    return False, diffs


def _copy_cached_data(src_dir: Path, dst_dir: Path) -> None:
    """Copy downloaded data files from monolith run to modular run directory.

    Copies XML, HGNC, and promapping files so both pipelines use identical
    input and avoid redundant network downloads.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Copy XML files (aop-wiki-xml* pattern)
    for xml_file in src_dir.glob("aop-wiki-xml*"):
        shutil.copy2(xml_file, dst_dir / xml_file.name)

    # Copy HGNC gene data
    hgnc_file = src_dir / "HGNCgenes.txt"
    if hgnc_file.exists():
        shutil.copy2(hgnc_file, dst_dir / "HGNCgenes.txt")

    # Copy protein ontology mapping
    promapping_file = src_dir / "promapping.txt"
    if promapping_file.exists():
        shutil.copy2(promapping_file, dst_dir / "promapping.txt")

    # Copy static files (prefixes.csv, typelabels.txt) if present
    for name in ("prefixes.csv", "typelabels.txt"):
        f = src_dir / name
        if f.exists():
            shutil.copy2(f, dst_dir / name)


FILES_TO_COMPARE = ['AOPWikiRDF.ttl', 'AOPWikiRDF-Genes.ttl', 'AOPWikiRDF-Void.ttl']


@pytest.mark.slow
def test_regression_triple_parity():
    """Run both pipelines and compare output triple-for-triple."""
    from aopwiki_rdf.pipeline_monolith import main as main_monolith
    from aopwiki_rdf.pipeline import main as main_modular

    with tempfile.TemporaryDirectory(prefix="regression_mono_") as dir_monolith, \
         tempfile.TemporaryDirectory(prefix="regression_mod_") as dir_modular:

        dir_mono_path = Path(dir_monolith)
        dir_mod_path = Path(dir_modular)

        # --- Stage 1: Run monolith pipeline ---
        print("\n=== Running MONOLITH pipeline ===")
        config_mono = PipelineConfig(data_dir=dir_mono_path)
        main_monolith(config_mono)

        # Verify monolith produced output files
        for filename in FILES_TO_COMPARE:
            mono_file = dir_mono_path / filename
            assert mono_file.exists(), f"Monolith did not produce {filename}"
            assert mono_file.stat().st_size > 0, f"Monolith {filename} is empty"

        # --- Stage 2: Copy cached data to avoid re-downloading ---
        print("\n=== Copying cached data for modular pipeline ===")
        _copy_cached_data(dir_mono_path, dir_mod_path)

        # --- Stage 3: Run modularized pipeline ---
        print("\n=== Running MODULAR pipeline ===")
        config_mod = PipelineConfig(data_dir=dir_mod_path)
        main_modular(config_mod)

        # Verify modular produced output files
        for filename in FILES_TO_COMPARE:
            mod_file = dir_mod_path / filename
            assert mod_file.exists(), f"Modular did not produce {filename}"
            assert mod_file.stat().st_size > 0, f"Modular {filename} is empty"

        # --- Stage 4: Compare outputs ---
        print("\n=== Comparing outputs ===")
        all_diffs = []
        for filename in FILES_TO_COMPARE:
            match, diffs = compare_ttl_files(
                str(dir_mono_path / filename),
                str(dir_mod_path / filename)
            )
            if match:
                print(f"  {filename}: MATCH")
            else:
                print(f"  {filename}: DIFFERS")
                for d in diffs:
                    print(f"    {d}")
                all_diffs.append((filename, diffs))

        if all_diffs:
            # Check if differences are within BridgeDb tolerance (< 0.1%)
            msg_parts = []
            for filename, diffs in all_diffs:
                msg_parts.append(f"\n--- {filename} ---")
                msg_parts.extend(diffs)
            assert False, "Triple parity failed:\n" + '\n'.join(msg_parts)

        print("\nAll three files match triple-for-triple.")


if __name__ == '__main__':
    test_regression_triple_parity()
