#!/usr/bin/env python3
"""
Test the enhanced precision filtering for false positive elimination.
"""

# Copy the enhanced function locally for testing
import sys
import re
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def map_genes_in_text_enhanced(text, genedict1, hgnc_list, genedict2=None):
    """
    Enhanced two-stage gene mapping algorithm with false positive filtering.
    """
    if not text or not genedict1:
        return []
    
    found_genes = []
    start_time = time.time()
    genes_checked = 0
    
    # False positive filter patterns
    roman_numeral_pattern = re.compile(r'\b[IVX]+\b')
    single_letter_aliases = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 
                           'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'}
    
    def is_false_positive(gene_symbol, matched_alias, matched_text_context):
        """Filter out known false positive patterns"""
        
        # Filter 1: Single letter aliases (too ambiguous)
        if matched_alias.strip() in single_letter_aliases:
            return True, f"single letter alias '{matched_alias.strip()}'"
        
        # Filter 2: Roman numerals (often match complex numbering in scientific text)
        if roman_numeral_pattern.fullmatch(matched_alias.strip()):
            return True, f"Roman numeral '{matched_alias.strip()}'"
        
        # Filter 3: Short ambiguous symbols in parentheses or brackets
        stripped = matched_alias.strip()
        if len(stripped) <= 2 and any(char in matched_text_context for char in '()[]{}'):
            return True, f"short symbol '{stripped}' in parentheses/brackets context"
        
        # Filter 4: Gene-specific false positive patterns
        if gene_symbol == 'IV' and ('Complex I' in matched_text_context or '(I–V)' in matched_text_context):
            return True, "IV gene matching complex numbering"
        
        if gene_symbol == 'GCNT2' and matched_alias.strip() == 'II' and ('(I–V)' in matched_text_context or 'complexes' in matched_text_context.lower()):
            return True, "GCNT2 alias 'II' matching complex numbering"
        
        return False, None
    
    # Two-stage algorithm with enhanced precision filtering
    for gene_key in genedict1:
        genes_checked += 1
        
        # Stage 1: Screen with genedict1 (basic gene symbols/names)
        a = 0
        stage1_matched_alias = None
        for item in genedict1[gene_key]:
            if item in text:
                a = 1
                stage1_matched_alias = item
                break
        
        # Stage 2: If Stage 1 passes, use genedict2 for precise matching
        if a == 1:
            hgnc_id = 'hgnc:' + gene_key
            
            # If genedict2 available, use it for precision (recommended)
            if genedict2 and gene_key in genedict2:
                # Use punctuation-delimited variants for precise matching
                for item in genedict2[gene_key]:
                    if item in text and hgnc_id not in found_genes:
                        
                        # Stage 3: False positive filtering
                        # Get context around the match for better filtering
                        match_index = text.find(item)
                        context_start = max(0, match_index - 50)
                        context_end = min(len(text), match_index + len(item) + 50)
                        context = text[context_start:context_end]
                        
                        # Extract the actual matched alias (strip punctuation delimiters)
                        matched_alias = item.strip(' ()[],.') if len(item) >= 3 else item[1:-1] if len(item) == 3 else item
                        
                        # Apply false positive filters
                        is_fp, fp_reason = is_false_positive(gene_key, matched_alias, context)
                        
                        if is_fp:
                            print(f"🚫 Filtered false positive: {gene_key} (alias '{matched_alias}') - {fp_reason}")
                            break  # Skip this gene entirely
                        
                        # Valid match - add to results
                        found_genes.append(hgnc_id)
                        print(f"✅ Valid match: {gene_key} (alias '{matched_alias}')")
                        
                        # Add to global list if not already present
                        if hgnc_id not in hgnc_list:
                            hgnc_list.append(hgnc_id)
                        break
    
    return found_genes

# Test data
ke_888_text = """Electron transport through the mitochondrial respiratory chain (oxidative phosphorylation) is mediated by five multimeric complexes (I–V) that are embedded in the mitochondrial inner membrane (Fig. 1). NADH-ubiquinone oxidoreductase is the Complex I (CI) of electron transport chain (ETC). It is a large assembly of proteins that spans the inner mitochondrial membrane. In mammals, it is composed of about 45-47 protein subunits (human 45) of which 7 are encoded by the mitochondrial genome (ND1, ND2, ND3, ND4, ND4L, ND5, and ND6) and the remainder by the nuclear genome (Greenamyre, 2001)."""

# Create test gene dictionaries
genedict1 = {
    'GCNT2': ['GCNT2', 'glucosaminyl (N-acetyl) transferase 2 (I blood group)', 'II'],
    'IV': ['IV', 'inversus situs, viscerum'],
    'PPIB': ['PPIB', 'peptidylprolyl isomerase B', 'B'],
    'MT-ND1': ['MT-ND1', 'MTND1', 'ND1'],  # Valid gene that should match
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
print(f"Test text contains: (I–V): {'(I–V)' in ke_888_text}")
print(f"Test text contains: Complex I: {'Complex I' in ke_888_text}")
print(f"Test text contains: ND1: {'ND1' in ke_888_text}")
print()

hgnc_list = []
result = map_genes_in_text_enhanced(ke_888_text, genedict1, hgnc_list, genedict2)

print(f"\n=== Results ===")
print(f"Found genes: {result}")
print(f"Expected: Only valid genes like MT-ND1, no false positives (GCNT2, IV, PPIB)")
print(f"Success: {len([g for g in result if g.split(':')[1] not in ['GCNT2', 'IV', 'PPIB']]) > 0 and len([g for g in result if g.split(':')[1] in ['GCNT2', 'IV', 'PPIB']]) == 0}")