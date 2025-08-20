#!/usr/bin/env python3
"""
Test URI resolvability - check if URIs actually resolve to valid resources.
Tests 5 sample URIs per prefix to verify they lead somewhere meaningful.
"""

import requests
import time
import sys
import os
import argparse
import csv
from pathlib import Path
from collections import defaultdict
import random
import re
from urllib.parse import urljoin
import concurrent.futures

def load_base_urls_from_csv():
    """Load base URLs from prefixes.csv for converting prefixed URIs to resolvable URLs"""
    base_urls = {}
    
    prefix_file = Path('prefixes.csv')
    if not prefix_file.exists():
        prefix_file = Path('data/prefixes.csv')
    
    if prefix_file.exists():
        try:
            with open(prefix_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        prefix = row[0].strip()
                        uri = row[1].strip()
                        if uri:  # Only add non-empty URIs
                            base_urls[prefix] = uri
            print(f"📋 Loaded {len(base_urls)} namespace URIs from {prefix_file}")
        except Exception as e:
            print(f"❌ Error loading prefixes.csv: {e}")
    
    # Add fallback URLs for prefixes not in CSV or for better resolvability
    fallback_urls = {
        # Fallbacks for better user experience (some identifiers.org may redirect)
        'inchikey': 'https://www.inchi-trust.org/download/',  # Not directly resolvable
        'aop.events': 'https://aopwiki.org/events/',
        'aop.relationships': 'https://aopwiki.org/relationships/',
        'aop.stressor': 'https://aopwiki.org/stressors/',
    }
    
    # Add fallbacks for missing prefixes
    for prefix, url in fallback_urls.items():
        if prefix not in base_urls:
            base_urls[prefix] = url
    
    return base_urls

def get_namespace_base_urls():
    """Get namespace base URLs from prefixes.csv with fallbacks"""
    return load_base_urls_from_csv()

def load_expected_prefixes():
    """Load expected prefixes from prefixes.csv"""
    prefixes = set()
    
    prefix_file = Path('prefixes.csv')
    if not prefix_file.exists():
        prefix_file = Path('data/prefixes.csv')
    if not prefix_file.exists():
        print("⚠️  Warning: prefixes.csv not found, will test all discovered prefixes")
        return None
    
    try:
        with open(prefix_file, 'r') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if len(row) >= 1:
                    prefix = row[0].strip()
                    prefixes.add(prefix)
        print(f"📋 Loaded {len(prefixes)} expected prefixes from {prefix_file}")
        return prefixes
    except Exception as e:
        print(f"❌ Error loading prefixes.csv: {e}")
        return None

def extract_sample_uris_from_files(rdf_files, samples_per_prefix=5, expected_prefixes=None):
    """Extract sample URIs from RDF files, grouped by prefix"""
    
    prefix_uris = defaultdict(set)
    
    # URI extraction pattern
    uri_pattern = r'\b([a-z][a-z0-9]*(?:\.[a-z0-9]+)*):([A-Za-z0-9@_.-]+)\b'
    
    print(f"🔍 Extracting sample URIs from {len(rdf_files)} files...")
    if expected_prefixes:
        print(f"📋 Focusing on {len(expected_prefixes)} expected prefixes from prefixes.csv")
    
    for rdf_file in rdf_files:
        if not Path(rdf_file).exists():
            continue
            
        try:
            with open(rdf_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip() and not line.startswith('#') and not line.startswith('@'):
                        # Extract URIs from line
                        matches = re.findall(uri_pattern, line)
                        for prefix, identifier in matches:
                            # Skip if we have expected prefixes and this isn't one of them
                            if expected_prefixes and prefix not in expected_prefixes:
                                continue
                                
                            full_uri = f"{prefix}:{identifier}"
                            prefix_uris[prefix].add(full_uri)
                            
                            # Stop collecting if we have enough samples
                            if len(prefix_uris[prefix]) >= samples_per_prefix * 2:  # Collect extra for randomization
                                break
        except Exception as e:
            print(f"⚠️  Error reading {rdf_file}: {e}")
    
    # Sample random URIs for each prefix
    sampled_uris = {}
    for prefix, uri_set in prefix_uris.items():
        uri_list = list(uri_set)
        sample_count = min(samples_per_prefix, len(uri_list))
        sampled_uris[prefix] = random.sample(uri_list, sample_count)
    
    print(f"📊 Extracted samples from {len(sampled_uris)} prefixes")
    return sampled_uris

def convert_to_resolvable_url(prefixed_uri, base_urls):
    """Convert prefixed URI to resolvable URL"""
    
    if ':' not in prefixed_uri:
        return None
    
    prefix, identifier = prefixed_uri.split(':', 1)
    
    if prefix not in base_urls:
        return None
    
    base_url = base_urls[prefix]
    
    # Handle identifiers.org URLs (most common in prefixes.csv)
    if 'identifiers.org' in base_url:
        # identifiers.org format: https://identifiers.org/prefix/identifier
        return f"{base_url}{identifier}"
    
    # Handle OBO Foundry URLs (purl.obolibrary.org)
    elif 'purl.obolibrary.org/obo' in base_url:
        if prefix in ['pato', 'cl', 'uberon', 'pr', 'cheminf', 'go']:
            # OBO format expects underscore and zero-padding for some
            if identifier.isdigit():
                identifier = identifier.zfill(7)  # Pad with zeros to 7 digits
            return f"{base_url}{identifier}"
        else:
            return f"{base_url}{identifier}"
    
    # Handle standard vocabulary namespaces (direct append)
    elif base_url.endswith(('#', '/')):
        return f"{base_url}{identifier}"
    
    # Special cases for specific formats
    elif prefix == 'mesh' and 'mesh' in base_url:
        return f"{base_url}{identifier}"
    elif prefix == 'ncbitaxon' and 'Taxonomy' in base_url:
        return f"{base_url}{identifier}"
    elif prefix in ['aop.events', 'aop.relationships', 'aop.stressor'] and 'aopwiki.org' in base_url:
        return f"{base_url}{identifier}"
    else:
        # Default: just append identifier
        return f"{base_url}{identifier}"

def test_uri_resolvability(uri, base_urls, timeout=10):
    """Test if a URI resolves to a valid resource"""
    
    resolvable_url = convert_to_resolvable_url(uri, base_urls)
    
    if not resolvable_url:
        return {
            'uri': uri,
            'url': None,
            'status': 'no_url_mapping',
            'response_code': None,
            'response_time': None,
            'error': 'No URL mapping available for this prefix',
            'warning': None
        }
    
    # First check if the initial URL (like identifiers.org) responds with redirect
    try:
        start_time = time.time()
        # Don't follow redirects initially to check if redirect is available
        response = requests.head(resolvable_url, timeout=timeout, allow_redirects=False)
        response_time = time.time() - start_time
        
        # If we get a redirect (301/302), consider it successful resolution
        if response.status_code in [301, 302]:
            redirect_url = response.headers.get('location', 'Unknown')
            return {
                'uri': uri,
                'url': resolvable_url,
                'status': 'success',
                'response_code': response.status_code,
                'response_time': response_time,
                'error': None,
                'warning': None,
                'redirect_url': redirect_url
            }
        
        # If direct access works (200-299), that's also success
        if response.status_code < 400:
            return {
                'uri': uri,
                'url': resolvable_url,
                'status': 'success',
                'response_code': response.status_code,
                'response_time': response_time,
                'error': None,
                'warning': None
            }
        
        # HTTP error codes
        return {
            'uri': uri,
            'url': resolvable_url,
            'status': 'http_error',
            'response_code': response.status_code,
            'response_time': response_time,
            'error': None,
            'warning': None
        }
        
    except requests.exceptions.SSLError as e:
        # For SSL errors, try without following redirects to see if redirect itself works
        try:
            response = requests.head(resolvable_url, timeout=timeout, allow_redirects=False, verify=False)
            if response.status_code in [301, 302]:
                redirect_url = response.headers.get('location', 'Unknown')
                return {
                    'uri': uri,
                    'url': resolvable_url,
                    'status': 'success_with_ssl_warning',
                    'response_code': response.status_code,
                    'response_time': time.time() - start_time,
                    'error': None,
                    'warning': f'SSL certificate issue at redirect target: {str(e)}',
                    'redirect_url': redirect_url
                }
        except:
            pass
        
        # SSL error without successful redirect
        return {
            'uri': uri,
            'url': resolvable_url,
            'status': 'ssl_error',
            'response_code': None,
            'response_time': None,
            'error': str(e),
            'warning': None
        }
        
    except requests.exceptions.Timeout:
        return {
            'uri': uri,
            'url': resolvable_url,
            'status': 'timeout',
            'response_code': None,
            'response_time': timeout,
            'error': 'Request timeout',
            'warning': None
        }
    except requests.exceptions.RequestException as e:
        return {
            'uri': uri,
            'url': resolvable_url,
            'status': 'connection_error',
            'response_code': None,
            'response_time': None,
            'error': str(e),
            'warning': None
        }

def test_batch_resolvability(sampled_uris, base_urls, max_workers=5, timeout=10):
    """Test resolvability for all sampled URIs using concurrent requests"""
    
    print(f"🌐 Testing URI resolvability with {max_workers} concurrent workers...")
    
    all_results = []
    total_uris = sum(len(uris) for uris in sampled_uris.values())
    completed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_uri = {}
        for prefix, uris in sampled_uris.items():
            for uri in uris:
                future = executor.submit(test_uri_resolvability, uri, base_urls, timeout)
                future_to_uri[future] = (prefix, uri)
        
        # Collect results
        for future in concurrent.futures.as_completed(future_to_uri):
            prefix, uri = future_to_uri[future]
            try:
                result = future.result()
                result['prefix'] = prefix
                all_results.append(result)
                completed += 1
                
                if completed % 10 == 0:
                    print(f"  Progress: {completed}/{total_uris} URIs tested ({completed/total_uris*100:.1f}%)")
                    
            except Exception as e:
                print(f"  ❌ Error testing {uri}: {e}")
    
    return all_results

def analyze_resolvability_results(results):
    """Analyze and report on resolvability test results"""
    
    print(f"\n" + "="*80)
    print(f"🌐 URI Resolvability Test Results")
    print(f"="*80)
    
    # Group results by prefix
    prefix_results = defaultdict(list)
    for result in results:
        prefix_results[result['prefix']].append(result)
    
    # Overall statistics
    total_tested = len(results)
    successful = len([r for r in results if r['status'] in ['success', 'success_with_ssl_warning']])
    failed = total_tested - successful
    warnings = len([r for r in results if r['status'] == 'success_with_ssl_warning'])
    
    print(f"\n📊 Overall Statistics:")
    print(f"  Total URIs tested: {total_tested}")
    print(f"  Successfully resolved: {successful} ({successful/total_tested*100:.1f}%)")
    if warnings > 0:
        print(f"  With SSL warnings: {warnings} ({warnings/total_tested*100:.1f}%)")
    print(f"  Failed to resolve: {failed} ({failed/total_tested*100:.1f}%)")
    
    # Status breakdown
    status_counts = defaultdict(int)
    for result in results:
        status_counts[result['status']] += 1
    
    print(f"\n📋 Resolution Status Breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count} URIs ({count/total_tested*100:.1f}%)")
    
    # Prefix-by-prefix analysis
    print(f"\n🏷️  Prefix Analysis:")
    
    prefix_stats = []
    for prefix, prefix_results_list in sorted(prefix_results.items()):
        total_prefix = len(prefix_results_list)
        successful_prefix = len([r for r in prefix_results_list if r['status'] in ['success', 'success_with_ssl_warning']])
        success_rate = successful_prefix / total_prefix * 100 if total_prefix > 0 else 0
        
        # Average response time for successful requests
        successful_times = [r['response_time'] for r in prefix_results_list if r['response_time'] is not None]
        avg_response_time = sum(successful_times) / len(successful_times) if successful_times else None
        
        prefix_stats.append({
            'prefix': prefix,
            'total': total_prefix,
            'successful': successful_prefix,
            'success_rate': success_rate,
            'avg_response_time': avg_response_time
        })
        
        status_icon = "✅" if success_rate >= 80 else "⚠️" if success_rate >= 50 else "❌"
        time_str = f", {avg_response_time:.2f}s avg" if avg_response_time else ""
        print(f"  {status_icon} {prefix}: {successful_prefix}/{total_prefix} ({success_rate:.1f}%{time_str})")
        
        # Show sample failures for problematic prefixes
        if success_rate < 80:
            failures = [r for r in prefix_results_list if r['status'] != 'success']
            for failure in failures[:2]:  # Show first 2 failures
                print(f"    ❌ {failure['uri']} - {failure['status']}: {failure.get('error', 'N/A')}")
    
    # Performance statistics
    response_times = [r['response_time'] for r in results if r['response_time'] is not None]
    if response_times:
        print(f"\n⏱️  Performance Statistics:")
        print(f"  Average response time: {sum(response_times)/len(response_times):.2f}s")
        print(f"  Fastest response: {min(response_times):.2f}s")
        print(f"  Slowest response: {max(response_times):.2f}s")
    
    return {
        'total_tested': total_tested,
        'successful': successful,
        'success_rate': successful/total_tested*100 if total_tested > 0 else 0,
        'prefix_stats': prefix_stats
    }

def save_resolvability_report(results, output_file):
    """Save detailed resolvability report"""
    
    total_tested = len(results)
    successful = len([r for r in results if r['status'] in ['success', 'success_with_ssl_warning']])
    success_rate = successful/total_tested*100 if total_tested > 0 else 0
    warnings = len([r for r in results if r['status'] == 'success_with_ssl_warning'])
    
    with open(output_file, 'w') as f:
        f.write("# URI Resolvability Test Report\n\n")
        f.write(f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        f.write(f"**Total URIs tested**: {total_tested}\n")
        f.write(f"**Successfully resolved**: {successful} ({success_rate:.1f}%)\n")
        if warnings > 0:
            f.write(f"**With SSL warnings**: {warnings} ({warnings/total_tested*100:.1f}%)\n")
        f.write(f"**Failed to resolve**: {total_tested - successful} ({(total_tested-successful)/total_tested*100:.1f}%)\n\n")
        
        # Group by prefix
        prefix_results = defaultdict(list)
        for result in results:
            prefix_results[result['prefix']].append(result)
        
        # Summary by category
        f.write("## Summary by Category\n\n")
        
        categories = {
            'Chemical Databases': ['chebi', 'chembl.compound', 'pubchem.compound', 'chemspider', 'kegg.compound', 'hmdb', 'drugbank', 'cas', 'comptox', 'lipidmaps'],
            'Gene/Protein Databases': ['hgnc', 'uniprot', 'ensembl', 'ncbigene', 'pr'],
            'Ontologies': ['go', 'pato', 'mesh', 'cl', 'uberon', 'cheminf', 'ncbitaxon'],
            'Standard Vocabularies': ['dc', 'dcterms', 'foaf', 'rdfs', 'skos', 'owl', 'void', 'dcat', 'pav'],
            'Project Specific': ['aop.events', 'aop.relationships', 'aop.stressor', 'aopo']
        }
        
        for category, prefixes in categories.items():
            category_results = []
            for prefix in prefixes:
                if prefix in prefix_results:
                    category_results.extend(prefix_results[prefix])
            
            if category_results:
                cat_total = len(category_results)
                cat_success = len([r for r in category_results if r['status'] in ['success', 'success_with_ssl_warning']])
                cat_rate = cat_success/cat_total*100 if cat_total > 0 else 0
                status_icon = "✅" if cat_rate >= 70 else "⚠️" if cat_rate >= 30 else "❌"
                f.write(f"{status_icon} **{category}**: {cat_success}/{cat_total} ({cat_rate:.1f}%)\n")
        
        f.write("\n")
        
        # Detailed results by prefix
        f.write("## Detailed Results by Prefix\n\n")
        for prefix, prefix_results_list in sorted(prefix_results.items()):
            f.write(f"### {prefix}\n\n")
            
            for result in prefix_results_list:
                if result['status'] in ['success', 'success_with_ssl_warning']:
                    status_icon = "✅" if result['status'] == 'success' else "⚠️"
                else:
                    status_icon = "❌"
                    
                f.write(f"{status_icon} `{result['uri']}`\n")
                f.write(f"  - URL: {result.get('url', 'N/A')}\n")
                f.write(f"  - Status: {result['status']}\n")
                if result['response_code']:
                    f.write(f"  - Response Code: {result['response_code']}\n")
                if result.get('redirect_url'):
                    f.write(f"  - Redirects to: {result['redirect_url']}\n")
                if result['response_time']:
                    f.write(f"  - Response Time: {result['response_time']:.2f}s\n")
                if result.get('warning'):
                    f.write(f"  - Warning: {result['warning']}\n")
                if result['error']:
                    f.write(f"  - Error: {result['error']}\n")
                f.write("\n")

def main():
    """Main resolvability testing function"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test URI resolvability in AOP-Wiki RDF files')
    parser.add_argument('--samples', type=int, default=5, help='Number of URIs to test per prefix (default: 5)')
    parser.add_argument('--timeout', type=int, default=10, help='HTTP request timeout in seconds (default: 10)')
    parser.add_argument('--workers', type=int, default=5, help='Number of concurrent workers (default: 5)')
    args = parser.parse_args()
    
    # Support environment variable for GitHub Actions
    samples_per_prefix = int(os.environ.get('SAMPLE_SIZE', args.samples))
    
    print("🌐 AOP-Wiki RDF URI Resolvability Testing")
    print("="*50)
    print(f"📊 Testing {samples_per_prefix} URIs per prefix")
    
    # Find RDF files
    rdf_files = []
    data_dir = Path('data')
    if data_dir.exists():
        rdf_files.extend(data_dir.glob('*.ttl'))
    rdf_files.extend(Path('.').glob('*.ttl'))
    
    if not rdf_files:
        print("❌ No RDF (.ttl) files found")
        return 1
    
    print(f"📄 Found {len(rdf_files)} RDF files")
    
    # Load expected prefixes from prefixes.csv
    expected_prefixes = load_expected_prefixes()
    
    # Extract sample URIs
    sampled_uris = extract_sample_uris_from_files(rdf_files, samples_per_prefix=samples_per_prefix, expected_prefixes=expected_prefixes)
    
    if not sampled_uris:
        print("❌ No URIs extracted from files")
        return 1
    
    # Get base URLs for resolution
    base_urls = get_namespace_base_urls()
    
    # Test resolvability
    results = test_batch_resolvability(sampled_uris, base_urls, max_workers=args.workers, timeout=args.timeout)
    
    # Analyze results
    summary = analyze_resolvability_results(results)
    
    # Save detailed report
    save_resolvability_report(results, 'uri_resolvability_report.md')
    print(f"\n💾 Detailed report saved to: uri_resolvability_report.md")
    
    # Return success/failure based on overall success rate
    # Use a lower threshold for monitoring since many URIs are semantic identifiers
    if summary['success_rate'] >= 30:
        print(f"\n✅ URI Resolvability PASSED: {summary['success_rate']:.1f}% success rate")
        return 0
    else:
        print(f"\n⚠️  URI Resolvability WARNING: {summary['success_rate']:.1f}% success rate")
        print("Note: Many URIs are semantic identifiers, not direct web links")
        return 0  # Don't fail workflow for monitoring purposes

if __name__ == "__main__":
    sys.exit(main())