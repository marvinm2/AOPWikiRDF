# Testing Patterns

**Analysis Date:** 2026-03-04

## Test Framework

**Runner:**
- No formal test framework (pytest, unittest, nose) configured
- All tests are standalone Python scripts
- Run tests directly: `python tests/unit/test_enhanced_precision.py`

**Assertion Library:**
- No assertion library; tests use conditional checks and print statements
- Manual assertions via comparison: `if set(old_result) == set(mega_result):`

**Run Commands:**
```bash
python tests/unit/test_enhanced_precision.py           # Run unit test
python tests/integration/test_precision_fix.py         # Run integration test
python tests/integration/test_scaling.py               # Run performance test
python tests/debug/debug_false_positives.py            # Run debug script
python tests/validation/validate_gene_mapping.py       # Run validation
```

## Test File Organization

**Location:**
- Tests co-located in `/tests/` directory structure
- Organized into categories: `unit/`, `integration/`, `debug/`, `validation/`
- Test files parallel main script structure but separate from source

**Naming:**
- Pattern: `test_*.py` for test files, `debug_*.py` for debug/exploratory scripts
- Examples: `test_enhanced_precision.py`, `test_batch_bridgedb.py`, `debug_false_positives.py`

**Directory Structure:**
```
tests/
├── unit/              # Unit tests for isolated functions
│   ├── test_enhanced_precision.py
│   ├── test_batch_bridgedb.py
│   └── test_batch_chemical_mapping.py
├── integration/       # Integration tests for workflows
│   ├── test_precision_fix.py
│   ├── test_ke888_current.py
│   ├── test_mega_simple.py
│   ├── test_mega_regex.py
│   ├── test_scaling.py
│   └── test_chemical_batch_integration.py
├── debug/            # Debug scripts for troubleshooting
│   ├── debug_false_positives.py
│   ├── debug_jupyter_algorithm.py
│   ├── debug_batch_response.py
│   ├── debug_fmn1.py
│   ├── debug_missing_genes.py
│   └── analyze_chemical_volume.py
├── validation/       # Validation and analysis tools
│   └── validate_gene_mapping.py
└── README.md         # Testing framework documentation
```

## Test Structure

**Suite Organization:**
Test scripts follow a test-first pattern with helper functions, then execution:

```python
#!/usr/bin/env python3
"""Test description."""

import logging
import sys

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Helper/utility functions
def helper_function():
    """Reusable test helper."""
    pass

# Test data setup
test_genes = ["BRCA2", "BRCA1", "TP53"]
test_text = "Sample text with genes..."

# Main test function
def main():
    print("=== Test Name ===")
    # Test logic here
    print(f"Results: {result}")

if __name__ == "__main__":
    main()
```

**Patterns:**
- Setup: Test data created at module level or in `main()`
- Execution: Direct function calls without framework assertions
- Output: Print statements with visual markers (✅, ❌, ⚠️)
- Teardown: Implicit (no cleanup needed for in-memory tests)

## Mocking

**Framework:**
- No mocking library used (unittest.mock, pytest-mock, etc.)
- Manual mocking via test data and function parameters

**Patterns:**
Test functions accept data structures as parameters rather than making real calls:

```python
# Instead of mocking requests.get(), pass test data
def test_batch_api(gene_symbols, bridgedb_url="https://webservice.bridgedb.org/"):
    """Test batch API format"""
    # Uses real API; no mocks
    response = requests.post(bridgedb_url + '/xrefsBatch/H', ...)
```

Alternative approach: Create test fixtures inline:

```python
def create_test_gene_dicts():
    """Create simplified test gene dictionaries similar to the real ones"""
    genedict1 = {
        'FMN1': ['FMN1', 'formin 1'],
        'MT-ND1': ['MT-ND1', 'MTND1', 'ND1'],
    }
    return genedict1, genedict2
```

**What to Mock:**
- External API calls when testing algorithm logic (create test data instead)
- Network operations in isolated unit tests

**What NOT to Mock:**
- Actual BridgeDb API calls (see `test_batch_bridgedb.py` - uses real API for validation)
- File I/O for integration tests (use real data files from `data/` directory)
- Core algorithm implementations (test with realistic data)

## Fixtures and Factories

**Test Data:**
Inline factory patterns for creating test data:

```python
def create_test_genes(count):
    """Create test gene dictionary with realistic gene names."""
    genes = {}

    # Add some real genes that will match
    real_genes = {
        'HGNC:11998': ['TP53', 'p53', 'tumor protein p53'],
        'HGNC:1100': ['BRCA1', 'breast cancer 1'],
    }

    genes.update(real_genes)

    # Fill remaining with synthetic genes
    for i in range(len(real_genes), count):
        gene_id = f'HGNC:{20000 + i}'
        genes[gene_id] = [f'GENE{i}', f'TestGene{i}']

    return genes
```

Realistic test text blocks:

```python
ke_888_text = """Electron transport through the mitochondrial respiratory chain...
Contains 7 proteins (ND1, ND2, ND3, ND4, ND4L, ND5, and ND6) and
references to Complex I (CI) and roman numerals (I–V)..."""
```

**Location:**
- Test data defined at module level in each test file
- Realistic text samples provide context for algorithm testing
- Generator functions create synthetic test data for scaling tests

## Coverage

**Requirements:**
- No formal coverage targets enforced
- Manual focus on testing critical algorithms and edge cases

**View Coverage:**
- No built-in coverage reporting
- Manual review via test output and visual inspection

## Test Types

**Unit Tests:**
- Scope: Individual algorithm functions with isolated inputs
- Approach: Test-specific inputs, verify output correctness
- Example: `test_enhanced_precision.py` tests `map_genes_in_text_enhanced()` with curated gene lists and text
- No mocking: Uses real function implementations with test data

```python
# test_enhanced_precision.py pattern
genedict1 = {
    'GCNT2': ['GCNT2', 'glucosaminyl (N-acetyl) transferase 2', 'II'],
    'IV': ['IV', 'inversus situs, viscerum'],
}
genedict2 = {}  # Built from genedict1

result = map_genes_in_text_enhanced(ke_888_text, genedict1, hgnc_list, genedict2)
print(f"Found genes: {result}")
```

**Integration Tests:**
- Scope: Multi-stage workflows and cross-component interactions
- Approach: Test realistic scenarios with complex data
- Examples:
  - `test_precision_fix.py`: Tests single-stage vs two-stage gene mapping algorithms
  - `test_mega_regex.py`: Tests performance of mega-regex vs individual pattern compilation
  - `test_ke888_current.py`: Validates gene mappings for specific Key Event (KE 888)

```python
# test_precision_fix.py pattern
single_results = single_stage_algorithm(test_description, genedict1, hgnc_list_single)
two_results = two_stage_algorithm(test_description, genedict1, hgnc_list_two, genedict2)

precision_single, recall_single = analyze_results("Single-Stage", single_results, expected_genes)
precision_two, recall_two = analyze_results("Two-Stage", two_results, expected_genes)

# Compare improvements
if precision_two > precision_single:
    print("✅ Fix successful")
```

**E2E Tests:**
- Not formally implemented
- Production validation via GitHub Actions workflows (RDF generation, quality control)
- Manual validation via SPARQL queries on generated RDF data

## Common Patterns

**Async Testing:**
- Not applicable (no async code in codebase)

**Error Testing:**
Pattern for testing error conditions and fallbacks:

```python
def test_batch_api_with_fallback():
    """Test batch API with fallback to individual requests"""
    try:
        response = requests.post(batch_url, ...)
        response.raise_for_status()
        # Process batch
    except requests.RequestException as e:
        print(f"❌ Batch request failed: {e}")
        # Fall back to individual requests
        for cas in batch:
            try:
                individual_result = map_chemical_individual(cas, ...)
            except Exception as error:
                print(f"❌ Individual fallback failed: {error}")
```

**Performance Testing:**
Compare algorithm performance with timing instrumentation:

```python
# test_scaling.py pattern
for size in test_sizes:
    logger.info(f"Testing with {size:,} genes")

    # Test old algorithm
    start_time = time.time()
    old_patterns = compile_old_patterns(genes)
    old_compile_time = time.time() - start_time

    start_time = time.time()
    old_result = map_genes_old(test_text, old_patterns)
    old_search_time = time.time() - start_time

    # Test new algorithm
    start_time = time.time()
    mega_pattern, gene_mapping, success = compile_mega_pattern(genes)
    mega_compile_time = time.time() - start_time

    if success:
        start_time = time.time()
        mega_result = map_genes_mega(test_text, mega_pattern, gene_mapping)
        mega_search_time = time.time() - start_time

        # Compare results and performance
        if set(old_result) == set(mega_result):
            speedup = total_old_time / total_mega_time
            logger.info(f"✅ Results match! Speedup: {speedup:.1f}x")
```

**Validation Pattern:**
Comprehensive correctness checking with precision/recall metrics:

```python
def analyze_results(algorithm_name, found_genes, expected_core_genes):
    """Analyze quality of gene mapping results"""
    print(f"=== {algorithm_name} Results ===")

    found_gene_symbols = set(g.replace('hgnc:', '') for g in found_genes)

    # Check core genes
    core_found = expected_core_genes & found_gene_symbols
    core_missing = expected_core_genes - found_gene_symbols

    # Check for false positives
    questionable_genes = found_gene_symbols - expected_core_genes

    # Calculate metrics
    precision = len(core_found) / len(found_genes) if found_genes else 0
    recall = len(core_found) / len(expected_core_genes) if expected_core_genes else 0

    print(f"Precision: {precision:.1%}")
    print(f"Recall: {recall:.1%}")

    return precision, recall
```

## Test Execution Examples

**Running unit tests:**
```bash
cd /home/marvin/Documents/Services/AOPWikiRDF
python tests/unit/test_enhanced_precision.py

# Output:
# === Testing Enhanced Precision Filtering ===
# Test text contains: (I–V): True
# Test text contains: Complex I: True
# ✅ Filtered false positive: GCNT2 (alias 'II')
# Found genes: ['hgnc:MT-ND1', 'hgnc:MT-ND2', ...]
```

**Running integration tests:**
```bash
python tests/integration/test_precision_fix.py

# Output:
# === Gene Mapping Precision Fix Test ===
# === Single-Stage (Current) Results ===
# Total genes found: 10
# Precision: 70.0%
# === Two-Stage (Fixed) Results ===
# Total genes found: 7
# Precision: 100.0%
# ✅ Fix successful: Better precision with same or better recall!
```

**Running performance tests:**
```bash
python tests/integration/test_scaling.py

# Output:
# === Testing with 1,000 genes ===
# Old: compile=0.050s, search=0.010s, total=0.060s, found=8
# Mega: compile=0.045s, search=0.002s, total=0.047s, found=8
# ✅ Results match! Total speedup: 1.3x
```

---

*Testing analysis: 2026-03-04*
