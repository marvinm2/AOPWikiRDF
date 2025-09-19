#!/usr/bin/env python3
"""
Analyze chemical processing volume and current performance bottleneck.
"""

import xml.etree.ElementTree as ET
import requests
import time
from pathlib import Path

def analyze_chemical_volume():
    """Analyze chemical processing requirements and current performance"""
    
    # Find the most recent XML file (with or without .xml extension)
    xml_files = list(Path('.').glob('aop-wiki-xml*'))
    xml_files.extend(list(Path('data').glob('aop-wiki-xml*')) if Path('data').exists() else [])
    
    if not xml_files:
        print("❌ No XML files found")
        return
    
    # Filter out empty files
    valid_xml_files = [f for f in xml_files if f.stat().st_size > 1000]
    if not valid_xml_files:
        print("❌ No valid XML files found")
        return
        
    xml_file = max(valid_xml_files, key=lambda x: x.stat().st_mtime)
    print(f"📄 Analyzing XML file: {xml_file} ({xml_file.stat().st_size:,} bytes)")
    
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        return
    
    # Try both possible namespaces
    try:
        # Try new namespace first
        aopxml = '{http://www.aopkb.org/aop-xml}'
        test_chemicals = root.findall(aopxml + 'chemical')
        if len(test_chemicals) == 0:
            # Fall back to old namespace
            aopxml = '{http://jrc.ec.europa.eu/aop-xml}'
            test_chemicals = root.findall(aopxml + 'chemical')
        print(f"  Using namespace: {aopxml}")
    except Exception as e:
        print(f"❌ Error determining namespace: {e}")
        return
    
    # Count total chemicals
    chemicals = root.findall(aopxml + 'chemical')
    total_chemicals = len(chemicals)
    
    # Count chemicals with CAS numbers (these need BridgeDb mapping)
    cas_chemicals = []
    for che in chemicals:
        if che.find(aopxml + 'casrn') is not None:
            casrn = che.find(aopxml + 'casrn').text
            if 'NOCAS' not in casrn:
                cas_chemicals.append(casrn)
    
    print(f"📊 Chemical Analysis:")
    print(f"  Total chemicals: {total_chemicals:,}")
    print(f"  Chemicals with CAS numbers: {len(cas_chemicals):,}")
    print(f"  Chemicals requiring BridgeDb mapping: {len(cas_chemicals):,}")
    
    if len(cas_chemicals) > 0:
        print(f"  Sample CAS numbers: {cas_chemicals[:5]}")
        
        # Estimate current performance
        estimated_time_sequential = len(cas_chemicals) * 2  # ~2 seconds per request (including network)
        print(f"\n⏱️  Current Sequential Performance Estimate:")
        print(f"  Estimated time: {estimated_time_sequential} seconds ({estimated_time_sequential/60:.1f} minutes)")
        print(f"  Request rate: {len(cas_chemicals)/estimated_time_sequential:.1f} chemicals/second")
        
        # Test batch API performance
        print(f"\n🧪 Testing Batch API Performance...")
        test_batch_performance(cas_chemicals[:20])  # Test with first 20 chemicals
        
        # Calculate batch optimization potential  
        batch_size = 100
        num_batches = (len(cas_chemicals) + batch_size - 1) // batch_size
        estimated_time_batch = num_batches * 2  # ~2 seconds per batch request
        
        print(f"\n🚀 Batch Processing Potential:")
        print(f"  Batch size: {batch_size} chemicals")
        print(f"  Number of batches: {num_batches}")
        print(f"  Estimated time: {estimated_time_batch} seconds ({estimated_time_batch/60:.1f} minutes)")
        print(f"  Performance improvement: {estimated_time_sequential/estimated_time_batch:.1f}x faster")

def test_batch_performance(cas_sample):
    """Test batch API performance with sample chemicals"""
    print(f"  Testing with {len(cas_sample)} sample chemicals...")
    
    batch_data = '\n'.join(cas_sample[:10])  # Test with first 10
    
    start_time = time.time()
    try:
        response = requests.post(
            "https://webservice.bridgedb.org/Human/xrefsBatch/Ca",
            data=batch_data,
            headers={'Content-Type': 'text/plain'},
            timeout=30
        )
        response.raise_for_status()
        end_time = time.time()
        
        duration = end_time - start_time
        lines = len([line for line in response.text.strip().split('\n') if line.strip()])
        
        print(f"  ✅ Batch API test successful:")
        print(f"    Duration: {duration:.2f} seconds")
        print(f"    Chemicals processed: {lines}")
        print(f"    Rate: {lines/duration:.1f} chemicals/second")
        
        # Show sample response
        print(f"  📝 Sample batch response:")
        for line in response.text.strip().split('\n')[:3]:
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 3:
                    cas_num = parts[0]
                    mappings = parts[2]
                    if mappings != 'N/A':
                        mapping_count = len(mappings.split(','))
                        print(f"    {cas_num}: {mapping_count} mappings")
                    else:
                        print(f"    {cas_num}: No mappings")
        
    except Exception as e:
        print(f"  ❌ Batch API test failed: {e}")

def analyze_current_system_codes():
    """Analyze what system codes are returned by batch API"""
    print(f"\n🔍 Analyzing System Codes...")
    
    # Test known chemicals
    test_cas = ["50-00-0", "71-43-2", "67-56-1"]  # Formaldehyde, benzene, methanol
    batch_data = '\n'.join(test_cas)
    
    try:
        response = requests.post(
            "https://webservice.bridgedb.org/Human/xrefsBatch/Ca",
            data=batch_data,
            headers={'Content-Type': 'text/plain'},
            timeout=30
        )
        response.raise_for_status()
        
        system_codes = set()
        system_code_mapping = {}
        
        for line in response.text.strip().split('\n'):
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 3 and parts[2] != 'N/A':
                    mappings = parts[2].split(',')
                    for mapping in mappings:
                        if ':' in mapping:
                            code = mapping.split(':', 1)[0]
                            system_codes.add(code)
        
        print(f"  📋 System codes found: {sorted(system_codes)}")
        
        # Map to expected chemical database names
        expected_mapping = {
            'Cs': 'Chemspider',
            'Ch': 'HMDB', 
            'Dr': 'DrugBank',
            'Ce': 'ChEBI',
            'Cl': 'ChEMBL compound',
            'Wd': 'Wikidata',
            'Cpc': 'PubChem-compound', 
            'Kd': 'KEGG Compound',
            'Ik': 'InChI Key',
            'Ect': 'EPA CompTox',
            'Gpl': 'Guide to Pharmacology'
        }
        
        print(f"  🗺️  System code mapping:")
        for code in sorted(system_codes):
            db_name = expected_mapping.get(code, f'Unknown ({code})')
            print(f"    {code}: → {db_name}")
            
    except Exception as e:
        print(f"  ❌ System code analysis failed: {e}")

if __name__ == "__main__":
    print("=== Chemical Processing Volume Analysis ===")
    analyze_chemical_volume()
    analyze_current_system_codes()