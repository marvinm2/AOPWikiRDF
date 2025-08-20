#!/usr/bin/env python3
"""
Comprehensive URI validation for AOP-Wiki RDF output.
Validates all identifier patterns, namespace consistency, and URI quality.
"""

import re
import sys
from pathlib import Path
from collections import defaultdict, Counter
import csv

def load_expected_prefixes():
    """Load expected prefixes from prefixes.csv"""
    prefixes = {}
    
    prefix_file = Path('prefixes.csv')
    if not prefix_file.exists():
        prefix_file = Path('data/prefixes.csv')
    if not prefix_file.exists():
        print("⚠️  Warning: prefixes.csv not found, using built-in patterns")
        return {}
    
    try:
        with open(prefix_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    prefix = row[0].strip()
                    namespace = row[1].strip()
                    prefixes[prefix] = namespace
        print(f"📋 Loaded {len(prefixes)} expected prefixes from {prefix_file}")
    except Exception as e:
        print(f"❌ Error loading prefixes.csv: {e}")
    
    return prefixes

def get_uri_patterns():
    """Define expected URI patterns for validation"""
    return {
        # Chemical identifiers
        'chebi': {
            'pattern': r'^chebi:\d+$',
            'description': 'ChEBI identifier',
            'example': 'chebi:16842'
        },
        'kegg.compound': {
            'pattern': r'^kegg\.compound:[CD]\d{5}$',
            'description': 'KEGG Compound identifier', 
            'example': 'kegg.compound:C00067'
        },
        'pubchem.compound': {
            'pattern': r'^pubchem\.compound:\d+$',
            'description': 'PubChem Compound identifier',
            'example': 'pubchem.compound:712'
        },
        'chemspider': {
            'pattern': r'^chemspider:\d+$',
            'description': 'ChemSpider identifier',
            'example': 'chemspider:692'
        },
        'hmdb': {
            'pattern': r'^hmdb:HMDB\d+$',
            'description': 'HMDB identifier',
            'example': 'hmdb:HMDB0001426'
        },
        'wikidata': {
            'pattern': r'^wikidata:Q\d+$',
            'description': 'Wikidata identifier',
            'example': 'wikidata:Q161210'
        },
        'lipidmaps': {
            'pattern': r'^lipidmaps:LM[A-Z]{2}\d{8}$',
            'description': 'LIPID MAPS identifier',
            'example': 'lipidmaps:LMPK12060007'
        },
        'chembl.compound': {
            'pattern': r'^chembl\.compound:CHEMBL\d+$',
            'description': 'ChEMBL compound identifier',
            'example': 'chembl.compound:CHEMBL1255'
        },
        'comptox': {
            'pattern': r'^comptox:DTXSID\d+$',
            'description': 'EPA CompTox identifier',
            'example': 'comptox:DTXSID7020637'
        },
        'cas': {
            'pattern': r'^cas:\d{1,7}-\d{2}-\d$',
            'description': 'CAS Registry Number',
            'example': 'cas:50-00-0'
        },
        'inchikey': {
            'pattern': r'^inchikey:[A-Z]{14}-[A-Z]{10}-[A-Z]$',
            'description': 'InChI Key',
            'example': 'inchikey:WSFSSNUMVMOOMR-UHFFFAOYSA-N'
        },
        
        # Gene identifiers  
        'hgnc': {
            'pattern': r'^hgnc:[A-Za-z0-9@_.-]+$',
            'description': 'HGNC gene symbol',
            'example': 'hgnc:BRCA1'
        },
        'uniprot': {
            'pattern': r'^uniprot:[A-Z0-9]{6,10}(-\d+)?$',
            'description': 'UniProt identifier (with optional isoform)',
            'example': 'uniprot:P04637'
        },
        'ensembl': {
            'pattern': r'^ensembl:ENS[A-Z]*[GT]\d{11}$',
            'description': 'Ensembl identifier',
            'example': 'ensembl:ENSG00000141510'
        },
        'entrez': {
            'pattern': r'^entrez:\d+$',
            'description': 'Entrez Gene identifier',
            'example': 'entrez:672'
        },
        
        # Ontology identifiers
        'go': {
            'pattern': r'^go:\d{7}$',
            'description': 'Gene Ontology term',
            'example': 'go:0008150'
        },
        'pato': {
            'pattern': r'^pato:\d{7}$',
            'description': 'PATO quality term', 
            'example': 'pato:0000001'
        },
        'mesh': {
            'pattern': r'^mesh:[A-Z]\d{6}$|^mesh:[CD]\d{5,6}$',
            'description': 'MeSH descriptor (D-terms and C-terms)',
            'example': 'mesh:D001943'
        },
        
        # AOP ontology (flexible pattern for classes and properties)
        'aopo': {
            'pattern': r'^aopo:[A-Za-z][A-Za-z0-9_]*$',
            'description': 'AOP Ontology term',
            'example': 'aopo:AdverseOutcomePathway'
        },
        
        # Project-specific identifiers
        'aop.events': {
            'pattern': r'^aop\.events:\d+$',
            'description': 'AOP-Wiki Key Event',
            'example': 'aop.events:888'
        },
        'aop.relationships': {
            'pattern': r'^aop\.relationships:\d+$', 
            'description': 'AOP-Wiki Key Event Relationship',
            'example': 'aop.relationships:1234'
        },
        'aop.stressor': {
            'pattern': r'^aop\.stressor:\d+$',
            'description': 'AOP-Wiki Stressor',
            'example': 'aop.stressor:567'
        },
        
        # Standard ontology/vocabulary prefixes
        'rdf': {
            'pattern': r'^rdf:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'RDF vocabulary',
            'example': 'rdf:type'
        },
        'rdfs': {
            'pattern': r'^rdfs:[a-zA-Z][a-zA-Z0-9]*$', 
            'description': 'RDF Schema vocabulary',
            'example': 'rdfs:label'
        },
        'owl': {
            'pattern': r'^owl:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'OWL vocabulary',
            'example': 'owl:Class'
        },
        'dc': {
            'pattern': r'^dc:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'Dublin Core terms',
            'example': 'dc:title'
        },
        'dcterms': {
            'pattern': r'^dcterms:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'Dublin Core terms',
            'example': 'dcterms:modified'
        },
        'foaf': {
            'pattern': r'^foaf:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'Friend of a Friend vocabulary',
            'example': 'foaf:name'
        },
        'skos': {
            'pattern': r'^skos:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'SKOS vocabulary',
            'example': 'skos:prefLabel'
        },
        'void': {
            'pattern': r'^void:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'VoID vocabulary',
            'example': 'void:Dataset'
        },
        'dcat': {
            'pattern': r'^dcat:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'DCAT vocabulary',
            'example': 'dcat:Dataset'
        },
        'pav': {
            'pattern': r'^pav:[a-zA-Z][a-zA-Z0-9]*$',
            'description': 'PAV vocabulary',
            'example': 'pav:createdOn'
        },
        
        # Chemical/biological ontologies
        'cheminf': {
            'pattern': r'^cheminf:\d{6}$',
            'description': 'Chemical Information Ontology',
            'example': 'cheminf:000407'
        },
        'ncbitaxon': {
            'pattern': r'^ncbitaxon:\d+$',
            'description': 'NCBI Taxonomy',
            'example': 'ncbitaxon:9606'
        },
        'ncbigene': {
            'pattern': r'^ncbigene:\d+$',
            'description': 'NCBI Gene',
            'example': 'ncbigene:672'
        },
        'cl': {
            'pattern': r'^cl:\d{7}$',
            'description': 'Cell Ontology',
            'example': 'cl:0000000'
        },
        'uberon': {
            'pattern': r'^uberon:\d{7}$',
            'description': 'Uberon anatomy ontology',
            'example': 'uberon:0000001'
        },
        'pr': {
            'pattern': r'^pr:([A-Z0-9]{6,10}|\d{9})$',
            'description': 'Protein Ontology (PRO IDs or UniProt-style)',
            'example': 'pr:P33244'
        },
        
        # DrugBank variants
        'drugbank': {
            'pattern': r'^drugbank:(DB\d{5}|DBSALT\d{6})$',
            'description': 'DrugBank identifier (including salt forms)',
            'example': 'drugbank:DB00001'
        },
        
        # LIPID MAPS variants
        'lipidmaps': {
            'pattern': r'^lipidmaps:LM[A-Z]{2}\d{8,10}$',
            'description': 'LIPID MAPS identifier (flexible length)',
            'example': 'lipidmaps:LMPK12060007'
        },
        
        # Handle special cases
        'inchikey': {
            'pattern': r'^inchikey:([A-Z]{14}-[A-Z]{10}-[A-Z]|None)$',
            'description': 'InChI Key (including None values)',
            'example': 'inchikey:WSFSSNUMVMOOMR-UHFFFAOYSA-N'
        }
    }

def validate_rdf_file(file_path):
    """Validate URIs in a single RDF file"""
    
    if not Path(file_path).exists():
        return {
            'file': file_path,
            'status': 'not_found',
            'error': f"File not found: {file_path}"
        }
    
    print(f"\n📄 Validating {file_path}")
    
    patterns = get_uri_patterns()
    results = {
        'file': file_path,
        'status': 'success',
        'total_lines': 0,
        'uri_counts': defaultdict(int),
        'invalid_uris': defaultdict(list),
        'unknown_prefixes': set(),
        'malformed_lines': [],
        'statistics': {}
    }
    
    # Read and analyze file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                results['total_lines'] += 1
                line = line.strip()
                
                if not line or line.startswith('#') or line.startswith('@'):
                    continue
                
                # Extract URIs from RDF line
                uris = extract_uris_from_line(line)
                
                for uri in uris:
                    # Check if it matches a known pattern
                    prefix = uri.split(':')[0] if ':' in uri else None
                    
                    if prefix in patterns:
                        pattern_info = patterns[prefix]
                        if re.match(pattern_info['pattern'], uri):
                            results['uri_counts'][prefix] += 1
                        else:
                            results['invalid_uris'][prefix].append({
                                'uri': uri,
                                'line': line_num,
                                'expected_pattern': pattern_info['pattern'],
                                'example': pattern_info['example']
                            })
                    elif prefix and ':' in uri:
                        results['unknown_prefixes'].add(prefix)
                        results['uri_counts'][f'unknown:{prefix}'] += 1
                
    except Exception as e:
        results['status'] = 'error'
        results['error'] = str(e)
        return results
    
    # Calculate statistics
    total_uris = sum(count for prefix, count in results['uri_counts'].items() if not prefix.startswith('unknown:'))
    invalid_count = sum(len(invalid_list) for invalid_list in results['invalid_uris'].values())
    
    results['statistics'] = {
        'total_uris': total_uris,
        'valid_uris': total_uris - invalid_count,
        'invalid_uris': invalid_count,
        'unique_prefixes': len([p for p in results['uri_counts'].keys() if not p.startswith('unknown:')]),
        'unknown_prefixes': len(results['unknown_prefixes']),
        'validation_rate': (total_uris - invalid_count) / total_uris * 100 if total_uris > 0 else 0
    }
    
    return results

def extract_uris_from_line(line):
    """Extract URIs from an RDF line"""
    uris = []
    
    # Pattern to match namespace:identifier format
    uri_pattern = r'\b([a-z][a-z0-9]*(?:\.[a-z0-9]+)*):([A-Za-z0-9@_.-]+)\b'
    
    matches = re.findall(uri_pattern, line)
    for prefix, identifier in matches:
        uris.append(f"{prefix}:{identifier}")
    
    return uris

def generate_validation_report(results_list, output_file=None):
    """Generate comprehensive validation report"""
    
    print(f"\n" + "="*80)
    print(f"🔍 AOP-Wiki RDF URI Validation Report")
    print(f"="*80)
    
    total_files = len(results_list)
    successful_files = len([r for r in results_list if r['status'] == 'success'])
    
    print(f"\n📊 Summary:")
    print(f"  Files analyzed: {total_files}")
    print(f"  Successful: {successful_files}")
    print(f"  Failed: {total_files - successful_files}")
    
    # Aggregate statistics
    total_uris = sum(r['statistics'].get('total_uris', 0) for r in results_list if r['status'] == 'success')
    total_valid = sum(r['statistics'].get('valid_uris', 0) for r in results_list if r['status'] == 'success')
    total_invalid = sum(r['statistics'].get('invalid_uris', 0) for r in results_list if r['status'] == 'success')
    
    print(f"\n📈 URI Statistics:")
    print(f"  Total URIs analyzed: {total_uris:,}")
    print(f"  Valid URIs: {total_valid:,} ({total_valid/total_uris*100:.1f}%)" if total_uris > 0 else "  Valid URIs: 0")
    print(f"  Invalid URIs: {total_invalid:,} ({total_invalid/total_uris*100:.1f}%)" if total_uris > 0 else "  Invalid URIs: 0")
    
    # Prefix usage analysis
    all_prefixes = defaultdict(int)
    for result in results_list:
        if result['status'] == 'success':
            for prefix, count in result['uri_counts'].items():
                all_prefixes[prefix] += count
    
    print(f"\n🏷️  Prefix Usage (Top 15):")
    for prefix, count in Counter(all_prefixes).most_common(15):
        if not prefix.startswith('unknown:'):
            print(f"  {prefix}: {count:,} URIs")
    
    # Unknown prefixes
    unknown_prefixes = set()
    for result in results_list:
        if result['status'] == 'success':
            unknown_prefixes.update(result['unknown_prefixes'])
    
    if unknown_prefixes:
        print(f"\n⚠️  Unknown Prefixes Found:")
        for prefix in sorted(unknown_prefixes):
            print(f"  {prefix}")
    
    # Validation issues by file
    print(f"\n📋 File-by-File Results:")
    for result in results_list:
        file_name = Path(result['file']).name
        if result['status'] == 'success':
            stats = result['statistics']
            validation_rate = stats['validation_rate']
            status_icon = "✅" if validation_rate >= 99 else "⚠️" if validation_rate >= 95 else "❌"
            print(f"  {status_icon} {file_name}: {stats['valid_uris']:,}/{stats['total_uris']:,} valid ({validation_rate:.1f}%)")
            
            # Show validation issues
            if result['invalid_uris']:
                for prefix, invalid_list in result['invalid_uris'].items():
                    print(f"    ❌ {prefix}: {len(invalid_list)} invalid URIs")
                    for invalid in invalid_list[:3]:  # Show first 3 examples
                        print(f"      Example: {invalid['uri']} (line {invalid['line']})")
                    if len(invalid_list) > 3:
                        print(f"      ... and {len(invalid_list) - 3} more")
        else:
            print(f"  ❌ {file_name}: {result.get('error', 'Unknown error')}")
    
    # Save detailed report if requested
    if output_file:
        save_detailed_report(results_list, output_file)
        print(f"\n💾 Detailed report saved to: {output_file}")
    
    return {
        'total_files': total_files,
        'successful_files': successful_files, 
        'total_uris': total_uris,
        'valid_uris': total_valid,
        'invalid_uris': total_invalid,
        'validation_rate': total_valid/total_uris*100 if total_uris > 0 else 0,
        'unknown_prefixes': unknown_prefixes
    }

def save_detailed_report(results_list, output_file):
    """Save detailed validation report to file"""
    
    with open(output_file, 'w') as f:
        f.write("# AOP-Wiki RDF URI Validation Report\n\n")
        f.write(f"Generated: {Path().absolute()}\n\n")
        
        for result in results_list:
            f.write(f"## {result['file']}\n\n")
            
            if result['status'] == 'success':
                stats = result['statistics']
                f.write(f"- **Total URIs**: {stats['total_uris']:,}\n")
                f.write(f"- **Valid URIs**: {stats['valid_uris']:,} ({stats['validation_rate']:.1f}%)\n")
                f.write(f"- **Invalid URIs**: {stats['invalid_uris']:,}\n")
                f.write(f"- **Unique prefixes**: {stats['unique_prefixes']}\n\n")
                
                if result['invalid_uris']:
                    f.write("### Validation Issues\n\n")
                    for prefix, invalid_list in result['invalid_uris'].items():
                        f.write(f"**{prefix}** ({len(invalid_list)} invalid):\n")
                        for invalid in invalid_list:
                            f.write(f"- Line {invalid['line']}: `{invalid['uri']}`\n")
                            f.write(f"  Expected pattern: `{invalid['expected_pattern']}`\n")
                            f.write(f"  Example: `{invalid['example']}`\n")
                        f.write("\n")
            else:
                f.write(f"❌ Error: {result.get('error', 'Unknown error')}\n\n")

def main():
    """Main validation function"""
    
    print("🔍 AOP-Wiki RDF URI Validation")
    print("="*50)
    
    # Find RDF files to validate
    rdf_files = []
    
    # Check data directory
    data_dir = Path('data')
    if data_dir.exists():
        rdf_files.extend(data_dir.glob('*.ttl'))
    
    # Check current directory  
    rdf_files.extend(Path('.').glob('*.ttl'))
    
    # Check test directories
    test_dirs = [Path('data-test'), Path('.tests/validation')]
    for test_dir in test_dirs:
        if test_dir.exists():
            rdf_files.extend(test_dir.glob('*.ttl'))
    
    if not rdf_files:
        print("❌ No RDF (.ttl) files found to validate")
        print("   Searched in: data/, current directory, data-test/, .tests/validation/")
        return 1
    
    print(f"📄 Found {len(rdf_files)} RDF files to validate")
    
    # Load expected prefixes
    expected_prefixes = load_expected_prefixes()
    
    # Validate each file
    results = []
    for rdf_file in sorted(rdf_files):
        result = validate_rdf_file(rdf_file)
        results.append(result)
    
    # Generate report
    summary = generate_validation_report(results, 'uri_validation_report.md')
    
    # Exit with appropriate code
    if summary['validation_rate'] >= 99:
        print(f"\n✅ Validation PASSED: {summary['validation_rate']:.1f}% URI compliance")
        return 0
    elif summary['validation_rate'] >= 95:
        print(f"\n⚠️  Validation WARNING: {summary['validation_rate']:.1f}% URI compliance")
        return 0
    else:
        print(f"\n❌ Validation FAILED: {summary['validation_rate']:.1f}% URI compliance")
        return 1

if __name__ == "__main__":
    sys.exit(main())