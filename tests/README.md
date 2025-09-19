# AOPWikiRDF Testing Framework

This hidden directory contains development and testing scripts for the AOPWikiRDF project.

## Directory Structure

### `unit/`
Unit tests for individual functions and components:
- `test_enhanced_precision.py` - Tests the false positive filtering system
- `test_batch_bridgedb.py` - Tests batch BridgeDb API functionality

### `integration/`
Integration tests for complete workflows:
- `test_precision_fix.py` - Tests two-stage gene mapping precision
- `test_ke888_current.py` - Validates specific KE gene mappings
- `test_mega_regex.py` - Tests mega-regex optimization performance
- `test_mega_simple.py` - Simplified mega-regex validation
- `test_scaling.py` - Performance scaling tests

### `debug/`
Debug scripts for troubleshooting issues:
- `debug_false_positives.py` - Analyzes false positive gene mappings
- `debug_jupyter_algorithm.py` - Compares Jupyter vs Python algorithms
- `debug_batch_response.py` - Debug BridgeDb batch API responses
- `debug_fmn1.py` - Investigates specific gene mapping issues
- `debug_missing_genes.py` - Analyzes missing gene mappings

### `validation/`
Validation and comparison tools:
- `validate_gene_mapping.py` - Comprehensive gene mapping validation

## Running Tests

### Prerequisites
Make sure you have the required dependencies installed:
```bash
pip install -r requirements.txt
```

### Unit Tests
```bash
python .tests/unit/test_enhanced_precision.py
python .tests/unit/test_batch_bridgedb.py
```

### Integration Tests
```bash
python .tests/integration/test_precision_fix.py
python .tests/integration/test_ke888_current.py
python .tests/integration/test_mega_regex.py
```

### Debug Scripts
```bash
python .tests/debug/debug_false_positives.py
python .tests/debug/debug_jupyter_algorithm.py
```

### Validation Scripts
```bash
python .tests/validation/validate_gene_mapping.py
```

## Development Guidelines

- **Unit tests**: Focus on testing individual functions with isolated inputs
- **Integration tests**: Test complete workflows and cross-component functionality
- **Debug scripts**: Use for investigating specific issues or comparing implementations
- **Validation scripts**: Comprehensive analysis of system behavior and correctness

## Notes

- This directory is excluded from git tracking via `.gitignore`
- Tests require access to the `data/` directory with HGNC gene data
- Some tests may require internet connectivity for BridgeDb API calls
- Performance tests may take several minutes to complete