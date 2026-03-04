# Coding Conventions

**Analysis Date:** 2026-03-04

## Naming Patterns

**Files:**
- Snake case for all Python files: `AOP-Wiki_XML_to_RDF_conversion.py`, `run_conversion.py`
- Hyphenated names for major scripts: `AOP-Wiki_XML_to_RDF_conversion.py` (preserves original naming)
- Test files use `test_*.py` or `debug_*.py` prefix pattern: `test_enhanced_precision.py`, `debug_false_positives.py`

**Functions:**
- Snake case for all function names: `safe_get_text()`, `download_with_retry()`, `validate_xml_structure()`
- Verb-forward naming for action functions: `convert_lists_to_sets_for_lookup()`, `map_genes_in_text_simple()`, `validate_required_fields()`
- Helper functions prefixed descriptively: `is_false_positive()`, `parse_batch_chemical_response()`

**Variables:**
- Snake case for all variables: `found_genes`, `gene_key`, `genedict1`, `genedict2`, `stage1_matched_alias`
- Short numeric suffixes for related dictionaries: `genedict1`, `genedict2` (stage 1 vs stage 2 variations)
- Single-letter variables preserved for algorithm compatibility: `a` (used as flag in two-stage gene mapping), `s1`, `s2` (punctuation delimiters)
- Descriptive names for state variables: `batch_start`, `elapsed`, `all_match`, `copied`

**Types/Constants:**
- SCREAMING_SNAKE_CASE for configuration constants: `DATA_DIR`, `MAX_RETRIES`, `REQUEST_TIMEOUT`, `BRIDGEDB_URL`, `AOPWIKI_XML_URL`, `PROMAPPING_URL`
- Pattern names with underscore suffix: `HTML_TAG_PATTERN`, `TAG_RE`, `roman_numeral_pattern`
- Dictionary keys follow ontology namespacing: `'dc:identifier'`, `'aopo:has_key_event'`, `'cheminf:000405'`

## Code Style

**Formatting:**
- No explicit linter/formatter enforced (no `.flake8`, `.pylintrc`, or `pyproject.toml` found)
- Follows implicit PEP 8 conventions with 4-space indentation
- Line wrapping: Functions with multiple arguments break at `(` and use multi-line format
  ```python
  response = requests.post(
      batch_url,
      data=batch_data,
      headers={'Content-Type': 'text/plain'},
      timeout=timeout
  )
  ```
- Triple-quoted strings used for multi-line text preservation: `'"""' + text + '"""'`

**Linting:**
- No automated linting configured
- Manual adherence to PEP 8 style
- Type hints not extensively used (variables documented via docstrings instead)

## Import Organization

**Order:**
1. Standard library imports (grouped): `sys`, `os`, `re`, `time`, `stat`, `gzip`, `shutil`, `datetime`, `logging`, `xml.etree.ElementTree`, `urllib.request`
2. Third-party library imports (grouped): `requests`, `pandas`, `rdflib`
3. Local/relative imports: None (single-file scripts predominate)

**Pattern:**
```python
# --- Standard Library Imports ---
import sys
import os
import re
import time
# ... etc

# --- Third-Party Libraries ---
import requests
import pandas as pd

# --- Configuration ---
# Config constants follow imports
BRIDGEDB_URL = 'https://webservice.bridgedb.org/Human/'
```

**Path Aliases:**
- Not used; relative imports from current directory

## Error Handling

**Patterns:**
- Try-except blocks with specific exception types: `requests.RequestException`, `FileNotFoundError`, `gzip.BadGzipFile`, `IOError`, `ValueError`
- Exponential backoff for network retries:
  ```python
  for attempt in range(max_retries):
      try:
          # attempt operation
      except requests.RequestException as e:
          logger.warning(f"Attempt {attempt + 1} failed: {e}")
          if attempt == max_retries - 1:
              logger.error(f"Failed after {max_retries} attempts")
              raise
          time.sleep(2 ** attempt)  # Exponential backoff
  ```
- Validation functions return boolean + optional warning logs:
  ```python
  def validate_required_fields(entity_dict, entity_type, required_fields):
      missing_fields = []
      # ... validation logic
      if missing_fields:
          logger.warning(f"Found {len(missing_fields)} missing fields")
          # Log first 5, note if more exist
          return False
      return True
  ```
- Fallback strategies for batch operations:
  - Batch API fails → fall back to individual API calls (see `map_chemicals_batch()`)
  - Mega-regex compilation fails → log error and continue with fallback (see `compile_mega_pattern()`)
- System exit on critical failures: `raise SystemExit(1)` after logging error

## Logging

**Framework:** Python `logging` module with dual output

**Configuration:**
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('aop_conversion.log')
    ]
)
logger = logging.getLogger(__name__)
```

**Patterns:**
- INFO level for major operations: `logger.info(f"Starting AOP-Wiki conversion for date: {today}")`
- DEBUG level for detailed algorithm steps: `logger.debug(f"Filtered false positive: {gene_key} (alias '{matched_alias}') - {fp_reason}")`
- WARNING level for validation issues: `logger.warning(f"Low count for {entity_type}: {actual_count}")`
- ERROR level before critical failures: `logger.error(f"Failed to download {url} after {max_retries} attempts")`
- Performance logging for slow operations:
  ```python
  if elapsed > 1.0:  # Log anything taking more than 1 second
      logger.info(f"SLOW gene mapping: {elapsed:.2f}s, {genes_checked} genes, {len(found_genes)} genes found")
  elif found_genes:
      logger.debug(f"Gene mapping: {elapsed:.2f}s, {len(found_genes)} genes found")
  ```

## Comments

**When to Comment:**
- Complex algorithm explanation at function header (docstring)
- Stage markers for multi-stage algorithms: `# Stage 1:`, `# Stage 2:`, `# Stage 3:`
- Filter rationale for false positive detection: `# Roman numerals (I, II, III, IV, V, etc.) - common in scientific text`
- Fallback explanation: `# Fallback to genedict1-only matching (less precise)`
- Performance notes: `# Add timing for performance monitoring`

**JSDoc/TSDoc:**
- Not applicable (Python project)
- Use standard Python docstrings for functions

**Docstring Pattern:**
```python
def map_genes_in_text_simple(text, genedict1, hgnc_list, genedict2=None):
    """
    Enhanced two-stage gene mapping algorithm with false positive filtering.

    Stage 1: Screen with genedict1 (basic gene names)
    Stage 2: Match with genedict2 (punctuation-delimited variants) with precision filters
    Stage 3: Apply false positive filters to eliminate problematic matches

    Returns list of found HGNC IDs and updates the global hgnc_list.
    """
```

## Function Design

**Size:**
- Functions range from 5-20 lines for simple operations to 50+ lines for complex algorithms
- Long functions acceptable when algorithm requires multi-stage processing (see `map_genes_in_text_simple()`, ~120 lines)
- Helper/utility functions typically 3-10 lines: `safe_get_text()`, `clean_html_tags()`

**Parameters:**
- Most functions take 2-4 parameters
- Keyword arguments for optional parameters with defaults: `batch_size=100`, `bridgedb_url=None`, `timeout=REQUEST_TIMEOUT`
- Configuration passed as parameters rather than globals: `bridgedb_url=None` with fallback to global `bridgedb` inside function

**Return Values:**
- Functions return single values or simple data structures
- Multiple-value returns as tuples: `return False, None` (for `is_false_positive()`)
- Functions that modify global state also return primary result: `map_genes_in_text_simple()` returns found genes AND updates `hgnc_list`
- Validation functions return boolean; side effects (logging) handled separately

## Module Design

**Exports:**
- All functions defined at module level are effectively exported (no `__all__` used)
- Main script structure: configuration → helper functions → validation → main processing
- Wrapper script (`run_conversion.py`) imports and executes main script with `exec(compile(...))`

**Barrel Files:**
- Not used; single-file scripts predominate (`AOP-Wiki_XML_to_RDF_conversion.py` is main)

**Script Execution Pattern:**
```python
if __name__ == "__main__":
    main()
```
- Main scripts execute top-level code directly (not wrapped in `if __name__`)
- Test/debug scripts use `if __name__ == "__main__": main()` pattern
- Wrapper scripts (`run_conversion.py`) use `if __name__ == '__main__': main()` to handle argument parsing

---

*Convention analysis: 2026-03-04*
