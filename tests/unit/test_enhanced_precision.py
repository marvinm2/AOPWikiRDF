#!/usr/bin/env python3
"""
Test the enhanced precision filtering for false positive elimination.

Uses the actual module's _map_genes_in_text function with numeric HGNC ID
keyed dictionaries (matching production format).
"""

import sys
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from aopwiki_rdf.mapping.gene_mapper import _map_genes_in_text

# Test data
ke_888_text = """Electron transport through the mitochondrial respiratory chain (oxidative phosphorylation) is mediated by five multimeric complexes (I\u2013V) that are embedded in the mitochondrial inner membrane (Fig. 1). NADH-ubiquinone oxidoreductase is the Complex I (CI) of electron transport chain (ETC). It is a large assembly of proteins that spans the inner mitochondrial membrane. In mammals, it is composed of about 45-47 protein subunits (human 45) of which 7 are encoded by the mitochondrial genome (ND1, ND2, ND3, ND4, ND4L, ND5, and ND6) and the remainder by the nuclear genome (Greenamyre, 2001)."""

# Create test gene dictionaries keyed by numeric HGNC ID
genedict1 = {
    '4204': ['GCNT2', 'glucosaminyl (N-acetyl) transferase 2 (I blood group)', 'II'],
    '100': ['IV', 'inversus situs, viscerum'],
    '9255': ['PPIB', 'peptidylprolyl isomerase B', 'B'],
    '7455': ['MT-ND1', 'MTND1', 'ND1'],  # Valid gene that should match
}

genedict2 = {}
symbols = [' ', '(', ')', '[', ']', ',', '.']
for gene_key, aliases in genedict1.items():
    genedict2[gene_key] = []
    for alias in aliases:
        for s1 in symbols:
            for s2 in symbols:
                genedict2[gene_key].append(s1 + alias + s2)

print("=== Testing Enhanced Precision Filtering ===")
print(f"Test text contains: (I\u2013V): {'(I\u2013V)' in ke_888_text}")
print(f"Test text contains: Complex I: {'Complex I' in ke_888_text}")
print(f"Test text contains: ND1: {'ND1' in ke_888_text}")
print()

hgnc_list = []
result = _map_genes_in_text(ke_888_text, genedict1, hgnc_list, genedict2)

# Expected: hgnc:7455 (MT-ND1) found; hgnc:4204 (GCNT2), hgnc:100 (IV), hgnc:9255 (PPIB) filtered
false_positive_ids = {'hgnc:4204', 'hgnc:100', 'hgnc:9255'}

print(f"\n=== Results ===")
print(f"Found genes: {result}")
print(f"Expected: Only valid genes like hgnc:7455 (MT-ND1), no false positives")
has_valid = 'hgnc:7455' in result
has_fp = bool(false_positive_ids.intersection(result))
print(f"Valid gene found: {has_valid}")
print(f"False positives found: {has_fp}")
print(f"Success: {has_valid and not has_fp}")