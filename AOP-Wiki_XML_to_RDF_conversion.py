#!/usr/bin/env python
# coding: utf-8

# # <b>AOP-Wiki XML conversion to RDF</b>
# Author: Marvin Martens
# 
# The [AOP-Wiki](https://aopwiki.org/) is the central repository for qualitative descriptions of AOPs, and releases its database every three months in XML format. This Jupyter notebook makes the conversion of the AOP-Wiki XML into RDF with Turtle (ttl) syntax. 
# 
# It downloads and parses the AOP-Wiki XML file with the ElementTree XML API Python library, and stores all its components in nested dictionaries for the all subjects which form the basis of the existing AOP-Wiki, being the AOPs, KEs,  KERs,  stressors,  chemicals,  taxonomy,  cell-terms,  organ-terms,  and  the  KE  components, which comprise of Biological Processes (BPs),  Biological Objects (BOs) and Biological Actions (BAs).  During the filling of those dictionaries, semantic annotations are being added for  the  subjects,  the  relationship  (predicate)  to  their  property  (object),  and  for  the  properties themselves when meant to represent an identifier or ontology term.
# 
# <img src="Overview AOP-Wiki RDF.svg" style="width: 650px;">

# ## <b>Step #1: imports and configuration</b>
# First, all required Python libraries are imported and configuration variables are set.


# --- Standard Library Imports ---
import sys
import os
import re
import time
import stat
import gzip
import shutil
import datetime
import logging
from xml.etree.ElementTree import parse
import urllib.request

# --- Third-Party Libraries ---
import requests
import pandas as pd

# --- Configuration ---
# URLs and endpoints
BRIDGEDB_URL = 'https://webservice.bridgedb.org/Human/'  # Alternative: 'http://localhost:8183/Human/'
AOPWIKI_XML_URL = 'https://aopwiki.org/downloads/aop-wiki-xml.gz'
PROMAPPING_URL = 'https://proconsortium.org/download/current/promapping.txt'

# File paths and settings
DATA_DIR = 'data/'
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# --- Constants / Compiled Patterns ---
TAG_RE = re.compile(r'<[^>]+>')

# Pre-compile frequently used patterns for performance
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')  # For HTML tag removal (used 1000+ times)

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('aop_conversion.log')
    ]
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def safe_get_text(element, default=''):
    """Safely extract text from XML element, returning default if None."""
    if element is not None and element.text is not None:
        return element.text.strip()
    return default

def clean_html_tags(text):
    """Remove HTML tags from text."""
    if text:
        return HTML_TAG_PATTERN.sub('', text)
    return text

def download_with_retry(url, filename, max_retries=MAX_RETRIES):
    """Download file with retry logic."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading {url} (attempt {attempt + 1}/{max_retries})")
            response = requests.get(url, verify=False, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                f.write(response.content)
            logger.info(f"Successfully downloaded {filename}")
            return True
            
        except requests.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to download {url} after {max_retries} attempts")
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    return False

# --- Performance Optimization Helper Functions ---

def compile_gene_patterns(gene_dict):
    """Pre-compile regex patterns for all gene names and variants for faster matching."""
    import re
    compiled_patterns = {}
    for gene_key, gene_names in gene_dict.items():
        # Create patterns for exact word matches to avoid partial matches
        patterns = []
        for name in gene_names:
            # Escape special regex characters and create word boundary pattern
            escaped_name = re.escape(name)
            # Use word boundaries to match whole words only
            pattern = r'\b' + escaped_name + r'\b'
            patterns.append(pattern)
        # Combine all patterns for this gene with OR operator
        if patterns:
            combined_pattern = '|'.join(patterns)
            compiled_patterns[gene_key] = re.compile(combined_pattern, re.IGNORECASE)
    return compiled_patterns

def find_genes_in_text_optimized(text, compiled_patterns, gene_dict):
    """
    Fast gene finding using pre-compiled regex patterns.
    Returns same results as original nested loop approach.
    """
    if not text:
        return []
    
    found_genes = []
    for gene_key, pattern in compiled_patterns.items():
        if pattern.search(text):
            # Found a match, add the HGNC ID (same format as original)
            hgnc_id = 'hgnc:' + gene_dict[gene_key][0]  # First item is the official symbol
            if hgnc_id not in found_genes:
                found_genes.append(hgnc_id)
    
    return found_genes

def convert_lists_to_sets_for_lookup(dict_of_lists):
    """Convert dictionary of lists to sets for O(1) membership testing."""
    return {key: set(values) for key, values in dict_of_lists.items()}

def convert_sets_to_lists_for_output(dict_of_sets):
    """Convert dictionary of sets back to lists for consistent output format."""
    return {key: list(values) for key, values in dict_of_sets.items()}

def map_genes_in_text_optimized(text, compiled_patterns, genedict1, hgnc_list):
    """
    Optimized gene mapping that replaces the nested loop approach.
    Uses pre-compiled regex patterns for much faster matching.
    
    Returns list of found HGNC IDs and updates the global hgnc_list.
    Maintains exact same output as original nested loop algorithm.
    """
    if not text or not compiled_patterns:
        return []
    
    found_genes = []
    
    # Use optimized pattern matching instead of nested loops
    for gene_key, pattern in compiled_patterns.items():
        if pattern.search(text):
            # Create HGNC ID in same format as original
            hgnc_id = 'hgnc:' + gene_key
            
            if hgnc_id not in found_genes:
                found_genes.append(hgnc_id)
            
            # Update global hgnc_list (same as original)
            if hgnc_id not in hgnc_list:
                hgnc_list.append(hgnc_id)
    
    return found_genes

# --- Validation Functions ---
def validate_xml_structure(root, expected_namespace):
    """Validate basic XML structure."""
    if root is None:
        raise ValueError("XML root is None")
    
    if root.tag != expected_namespace + 'data':
        logger.warning(f"Unexpected root tag: {root.tag}")
    
    # Check for required vendor-specific section
    vendor_section = root.find(expected_namespace + 'vendor-specific')
    if vendor_section is None:
        raise ValueError("Missing vendor-specific section in XML")
    
    logger.info("XML structure validation passed")
    return True

def validate_entity_counts(refs):
    """Validate that we have reasonable entity counts."""
    min_expected = {'AOP': 1, 'KE': 1, 'KER': 1, 'Stressor': 1}
    
    for entity_type, min_count in min_expected.items():
        actual_count = len(refs.get(entity_type, {}))
        if actual_count < min_count:
            logger.warning(f"Low count for {entity_type}: {actual_count} (expected >= {min_count})")
        else:
            logger.info(f"Entity count validation passed for {entity_type}: {actual_count}")
    
    return True

def validate_required_fields(entity_dict, entity_type, required_fields):
    """Validate that required fields are present in entities."""
    missing_fields = []
    for entity_id, entity_data in entity_dict.items():
        for field in required_fields:
            if field not in entity_data or not entity_data[field]:
                missing_fields.append(f"{entity_type} {entity_id} missing {field}")
    
    if missing_fields:
        logger.warning(f"Found {len(missing_fields)} missing required fields")
        for missing in missing_fields[:5]:  # Log first 5
            logger.warning(missing)
        if len(missing_fields) > 5:
            logger.warning(f"... and {len(missing_fields) - 5} more")
    else:
        logger.info(f"Required field validation passed for {entity_type}")
    
    return len(missing_fields) == 0

# This notebook includes the mapping of identifiers for chemicals and genes. To make this possible, the URL to the BridgeDb service is defined in the configuration section above.


# Use configuration variable
bridgedb = BRIDGEDB_URL


# ## <b>Step #2: Getting the AOP-Wiki XML</b>
# Download and extract the latest AOP-Wiki XML with proper error handling.


from datetime import date

today = date.today()
logger.info(f"Starting AOP-Wiki conversion for date: {today}")


# Download AOP-Wiki XML with retry logic
aopwikixmlfilename = f'aop-wiki-xml-{today}'
try:
    download_with_retry(AOPWIKI_XML_URL, aopwikixmlfilename)
except requests.RequestException as e:
    logger.error(f"Failed to download AOP-Wiki XML: {e}")
    raise SystemExit(1)


# Ensure data directory exists
filepath = DATA_DIR
os.makedirs(filepath, exist_ok=True)
logger.info(f"Using data directory: {filepath}")


# Extract gzipped XML file
try:
    with gzip.open(aopwikixmlfilename, 'rb') as f_in:
        with open(filepath + aopwikixmlfilename, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    logger.info(f"Successfully extracted XML to {filepath + aopwikixmlfilename}")
except (FileNotFoundError, gzip.BadGzipFile, IOError) as e:
    logger.error(f"Failed to extract XML file: {e}")
    raise SystemExit(1)


# Parse XML with validation
try:
    tree = parse(filepath + aopwikixmlfilename)
    root = tree.getroot()
    if root is None or len(root) == 0:
        raise ValueError("XML file appears to be empty or invalid")
    
    logger.info(f'AOP-Wiki XML parsed successfully, contains {len(root)} entities')
    
except Exception as e:
    logger.error(f"Failed to parse XML file: {e}")
    raise SystemExit(1)

aopxml = '{http://www.aopkb.org/aop-xml}'

# Validate XML structure
try:
    validate_xml_structure(root, aopxml)
except ValueError as e:
    logger.error(f"XML structure validation failed: {e}")
    raise SystemExit(1)

# ## <b>Step #3: extracting information from the XML</b>
# The next section extracts all information from the main 11 AOP-Wiki entities shown in Figure 1. These are stored in nested dictionaries, while using ontological annotations as keys for semantic mapping of the information. Note that the cell-terms and organ-terms are included in the KE block of code.
# 
# First, all reference identifiers for AOPs, KEs, KERs and stressors need to be extracted.



refs = {'AOP': {}, 'KE': {}, 'KER': {}, 'Stressor': {}}
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'aop-reference'):
    refs['AOP'][ref.get('id')] = ref.get('aop-wiki-id')
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'key-event-reference'):
    refs['KE'][ref.get('id')] = ref.get('aop-wiki-id')
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'key-event-relationship-reference'):
    refs['KER'][ref.get('id')] = ref.get('aop-wiki-id')
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'stressor-reference'):
    refs['Stressor'][ref.get('id')] = ref.get('aop-wiki-id')
for item in refs:
    logger.info(f'Found {len(refs[item])} identifiers for entity type: {item}')

# Validate entity counts
try:
    validate_entity_counts(refs)
except Exception as e:
    logger.error(f"Entity count validation failed: {e}")
    # Don't exit here since this is just a validation warning


# ### Adverse Outcome Pathways



aopdict = {}
kedict = {}
for AOP in root.findall(aopxml + 'aop'):
    aopdict[AOP.get('id')] = {}
    aopdict[AOP.get('id')]['dc:identifier'] = 'aop:' + refs['AOP'][AOP.get('id')]
    aopdict[AOP.get('id')]['rdfs:label'] = '"AOP ' + refs['AOP'][AOP.get('id')] + '"'
    aopdict[AOP.get('id')]['foaf:page'] = '<https://identifiers.org/aop/' + refs['AOP'][AOP.get('id')] + '>'
    aopdict[AOP.get('id')]['dc:title'] = '"' + AOP.find(aopxml + 'title').text + '"'
    aopdict[AOP.get('id')]['dcterms:alternative'] = AOP.find(aopxml + 'short-name').text
    aopdict[AOP.get('id')]['dc:description'] = []
    if AOP.find(aopxml + 'background') is not None:
        aopdict[AOP.get('id')]['dc:description'].append('"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'background').text) + '"""')
    if AOP.find(aopxml + 'authors').text is not None:
        aopdict[AOP.get('id')]['dc:creator'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'authors').text) + '"""'
    if AOP.find(aopxml + 'abstract').text is not None:
        aopdict[AOP.get('id')]['dcterms:abstract'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'abstract').text) + '"""'
    if AOP.find(aopxml + 'status').find(aopxml + 'wiki-status') is not None:
        aopdict[AOP.get('id')]['dcterms:accessRights'] = '"' + AOP.find(aopxml + 'status').find(aopxml + 'wiki-status').text + '"' 
    if AOP.find(aopxml + 'status').find(aopxml + 'oecd-status') is not None:
        aopdict[AOP.get('id')]['oecd-status'] =  '"' + AOP.find(aopxml + 'status').find(aopxml + 'oecd-status').text + '"' 
    if AOP.find(aopxml + 'status').find(aopxml + 'saaop-status') is not None:
        aopdict[AOP.get('id')]['saaop-status'] =  '"' + AOP.find(aopxml + 'status').find(aopxml + 'saaop-status').text + '"' 
    aopdict[AOP.get('id')]['oecd-project'] = AOP.find(aopxml + 'oecd-project').text
    aopdict[AOP.get('id')]['dc:source'] = AOP.find(aopxml + 'source').text
    aopdict[AOP.get('id')]['dcterms:created'] = AOP.find(aopxml + 'creation-timestamp').text
    aopdict[AOP.get('id')]['dcterms:modified'] = AOP.find(aopxml + 'last-modification-timestamp').text
    for appl in AOP.findall(aopxml + 'applicability'):
        for sex in appl.findall(aopxml + 'sex'):
            if 'pato:0000047' not in aopdict[AOP.get('id')]:
                aopdict[AOP.get('id')]['pato:0000047'] = [[sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text]]
            else:
                aopdict[AOP.get('id')]['pato:0000047'].append([sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text])
        for life in appl.findall(aopxml + 'life-stage'):
            if 'aopo:LifeStageContext' not in aopdict[AOP.get('id')]:
                aopdict[AOP.get('id')]['aopo:LifeStageContext'] = [[life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text]]
            else:
                aopdict[AOP.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text])
    aopdict[AOP.get('id')]['aopo:has_key_event'] = {}
    if AOP.find(aopxml + 'key-events') is not None:
        for KE in AOP.find(aopxml + 'key-events').findall(aopxml + 'key-event'):
            aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('key-event-id')] = {}
            aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KE'][KE.get('key-event-id')]
    aopdict[AOP.get('id')]['aopo:has_key_event_relationship'] = {}
    if AOP.find(aopxml + 'key-event-relationships') is not None:
        for KER in AOP.find(aopxml + 'key-event-relationships').findall(aopxml + 'relationship'):
            aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')] = {}
            aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['dc:identifier'] = 'aop.relationships:' + refs['KER'][KER.get('id')]
            aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['adjacency'] = KER.find(aopxml + 'adjacency').text
            aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['quantitative-understanding-value'] = KER.find(aopxml + 'quantitative-understanding-value').text
            aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['aopo:has_evidence'] = KER.find(aopxml + 'evidence').text
    aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'] = {}
    for MIE in AOP.findall(aopxml + 'molecular-initiating-event'):
        aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')] = {}
        aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KE'][MIE.get('key-event-id')]
        aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')] = {}
        aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KE'][MIE.get('key-event-id')]
        if MIE.find(aopxml + 'evidence-supporting-chemical-initiation').text is not None:
            kedict[MIE.get('key-event-id')] = {}
            aopdict[AOP.get('id')]['dc:description'].append('"""' + HTML_TAG_PATTERN.sub('', MIE.find(aopxml + 'evidence-supporting-chemical-initiation').text) + '"""')
    aopdict[AOP.get('id')]['aopo:has_adverse_outcome'] = {}
    for AO in AOP.findall(aopxml + 'adverse-outcome'):
        aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')] = {}
        aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KE'][AO.get('key-event-id')]
        aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')] = {}
        aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KE'][AO.get('key-event-id')]
        if AO.find(aopxml + 'examples').text is not None:
            kedict[AO.get('key-event-id')] = {}
            aopdict[AOP.get('id')]['dc:description'].append('"""' + HTML_TAG_PATTERN.sub('', AO.find(aopxml + 'examples').text) + '"""')
    aopdict[AOP.get('id')]['nci:C54571'] = {}
    if AOP.find(aopxml + 'aop-stressors') is not None:
        for stressor in AOP.find(aopxml + 'aop-stressors').findall(aopxml + 'aop-stressor'):
            aopdict[AOP.get('id')]['nci:C54571'][stressor.get('stressor-id')] = {}
            aopdict[AOP.get('id')]['nci:C54571'][stressor.get('stressor-id')]['dc:identifier'] = 'aop.stressor:' + refs['Stressor'][stressor.get('stressor-id')]
            aopdict[AOP.get('id')]['nci:C54571'][stressor.get('stressor-id')]['aopo:has_evidence'] = stressor.find(aopxml + 'evidence').text
    if AOP.find(aopxml + 'overall-assessment').find(aopxml + 'description').text is not None:
        aopdict[AOP.get('id')]['nci:C25217'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'overall-assessment').find(aopxml + 'description').text) + '"""'
    if AOP.find(aopxml + 'overall-assessment').find(aopxml + 'key-event-essentiality-summary').text is not None:
        aopdict[AOP.get('id')]['nci:C48192'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'overall-assessment').find(aopxml + 'key-event-essentiality-summary').text) + '"""'
    if AOP.find(aopxml + 'overall-assessment').find(aopxml + 'applicability').text is not None:
        aopdict[AOP.get('id')]['aopo:AopContext'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'overall-assessment').find(aopxml + 'applicability').text) + '"""'
    if AOP.find(aopxml + 'overall-assessment').find(aopxml + 'weight-of-evidence-summary').text is not None:
        aopdict[AOP.get('id')]['aopo:has_evidence'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'overall-assessment').find(aopxml + 'weight-of-evidence-summary').text) + '"""'
    if AOP.find(aopxml + 'overall-assessment').find(aopxml + 'quantitative-considerations').text is not None:
        aopdict[AOP.get('id')]['edam:operation_3799'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'overall-assessment').find(aopxml + 'quantitative-considerations').text) + '"""'
    if AOP.find(aopxml + 'potential-applications').text is not None:
        aopdict[AOP.get('id')]['nci:C25725'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'potential-applications').text) + '"""'
logger.info(f'Completed AOP parsing: {len(aopdict)} Adverse Outcome Pathways processed')

# Validate AOP required fields
try:
    validate_required_fields(aopdict, 'AOP', ['dc:identifier', 'dc:title'])
except Exception as e:
    logger.error(f"AOP required fields validation failed: {e}")
    # Don't exit here since this is just a validation warning


# ### Chemicals
# For the chemicals in the AOP-Wiki, we added BridgeDb mappings for increased coverage of chemical databases for which we used the already present CAS identifers. 



chedict = {}
listofchebi = []
listofchemspider = []
listofwikidata = []
listofchembl = []
listofdrugbank = []
listofpubchem = []
listoflipidmaps = []
listofhmdb = []
listofkegg = []
listofcas = []
listofinchikey = []
listofcomptox = []

for che in root.findall(aopxml + 'chemical'):
    chedict[che.get('id')] = {}
    if che.find(aopxml + 'casrn') is not None:
        if 'NOCAS' not in che.find(aopxml + 'casrn').text:  # all NOCAS ids are taken out, so no issues as subjects
            chedict[che.get('id')]['dc:identifier'] = 'cas:' + che.find(aopxml + 'casrn').text
            listofcas.append('cas:' + che.find(aopxml + 'casrn').text)
            chedict[che.get('id')]['cheminf:000446'] = '"' + che.find(aopxml + 'casrn').text + '"'
            # BridgeDb chemical mapping with error handling
            try:
                response = requests.get(bridgedb+'xrefs/Ca/'+che.find(aopxml + 'casrn').text, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                a = response.text.split('\n')
            except requests.RequestException as e:
                logger.warning(f"BridgeDb chemical mapping failed for CAS {che.find(aopxml + 'casrn').text}: {e}")
                a = ['html']  # Set to trigger fallback behavior
            dictionaryforchemical = {}
            if 'html' not in a:
                for item in a:
                    b = item.split('\t')
                    if len(b) == 2:
                        if b[1] not in dictionaryforchemical:
                            dictionaryforchemical[b[1]] = []
                            dictionaryforchemical[b[1]].append(b[0])
                        else:
                            dictionaryforchemical[b[1]].append(b[0])
            if 'ChEBI' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000407'] = []
                for chebi in dictionaryforchemical['ChEBI']:
                    # Remove "CHEBI:" prefix if it exists
                    formatted_chebi = "chebi:" + chebi.split("CHEBI:")[-1]
                    if formatted_chebi not in listofchebi:
                        listofchebi.append(formatted_chebi)
                    if formatted_chebi not in chedict[che.get('id')]['cheminf:000407']:
                        chedict[che.get('id')]['cheminf:000407'].append(formatted_chebi)
            if 'Chemspider' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000405'] = []
                for chemspider in dictionaryforchemical['Chemspider']:
                    if "chemspider:"+chemspider not in listofchemspider:
                        listofchemspider.append("chemspider:"+chemspider)
                    chedict[che.get('id')]['cheminf:000405'].append("chemspider:"+chemspider)
            if 'Wikidata' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000567'] = []
                for wd in dictionaryforchemical['Wikidata']:
                    if "wikidata:"+wd not in listofwikidata:
                        listofwikidata.append("wikidata:"+wd)
                    chedict[che.get('id')]['cheminf:000567'].append("wikidata:"+wd)
            if 'ChEMBL compound' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000412'] = []
                for chembl in dictionaryforchemical['ChEMBL compound']:
                    if "chembl.compound:"+chembl not in listofchembl:
                        listofchembl.append("chembl.compound:"+chembl)
                    chedict[che.get('id')]['cheminf:000412'].append("chembl.compound:"+chembl)
            if 'PubChem-compound' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000140'] = []
                for pub in dictionaryforchemical['PubChem-compound']:
                    if "pubchem.compound:"+pub not in listofpubchem:
                        listofpubchem.append("pubchem.compound:"+pub)
                    chedict[che.get('id')]['cheminf:000140'].append("pubchem.compound:"+pub)
            if 'DrugBank' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000406'] = []
                for drugbank in dictionaryforchemical['DrugBank']:
                    if "drugbank:"+drugbank not in listofdrugbank:
                        listofdrugbank.append("drugbank:"+drugbank)
                    chedict[che.get('id')]['cheminf:000406'].append("drugbank:"+drugbank)
            if 'KEGG Compound' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000409'] = []
                for kegg in dictionaryforchemical['KEGG Compound']:
                    if "kegg.compound:"+kegg not in listofkegg:
                        listofkegg.append("kegg.compound:"+kegg)
                    chedict[che.get('id')]['cheminf:000409'].append("kegg.compound:"+kegg)
            if 'LIPID MAPS' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000564'] = []
                for lipidmaps in dictionaryforchemical['LIPID MAPS']:
                    if "lipidmaps:"+lipidmaps not in listoflipidmaps:
                        listoflipidmaps.append("lipidmaps:"+lipidmaps)
                    chedict[che.get('id')]['cheminf:000564'].append("lipidmaps:"+lipidmaps)
            if 'HMDB' in dictionaryforchemical:
                chedict[che.get('id')]['cheminf:000408'] = []
                for hmdb in dictionaryforchemical['HMDB']:
                    if "hmdb:"+hmdb not in listofhmdb:
                        listofhmdb.append("hmdb:"+hmdb)
                    chedict[che.get('id')]['cheminf:000408'].append("hmdb:"+hmdb)
        else:
            chedict[che.get('id')]['dc:identifier'] = '"' + che.find(aopxml + 'casrn').text + '"'
    if che.find(aopxml + 'jchem-inchi-key') is not None:
        chedict[che.get('id')]['cheminf:000059'] = 'inchikey:' + str(che.find(aopxml + 'jchem-inchi-key').text)
        listofinchikey.append('inchikey:' + str(che.find(aopxml + 'jchem-inchi-key').text))
    if che.find(aopxml + 'preferred-name') is not None:
        chedict[che.get('id')]['dc:title'] = '"' + che.find(aopxml + 'preferred-name').text + '"'
    if che.find(aopxml + 'dsstox-id') is not None:
        chedict[che.get('id')]['cheminf:000568'] = 'comptox:' + che.find(aopxml + 'dsstox-id').text
        listofcomptox.append('comptox:' + che.find(aopxml + 'dsstox-id').text)
    if che.find(aopxml + 'synonyms') is not None:
        chedict[che.get('id')]['dcterms:alternative'] = []
        for synonym in che.find(aopxml + 'synonyms').findall(aopxml + 'synonym'):
            chedict[che.get('id')]['dcterms:alternative'].append(synonym.text[:-1])
logger.info(f'Completed chemical parsing: {len(chedict)} chemicals processed')


# ### Stressors



strdict = {}
for stressor in root.findall(aopxml + 'stressor'):
    strdict[stressor.get('id')] = {}
    strdict[stressor.get('id')]['dc:identifier'] = 'aop.stressor:' + refs['Stressor'][stressor.get('id')]
    strdict[stressor.get('id')]['rdfs:label'] = '"Stressor ' + refs['Stressor'][stressor.get('id')] + '"'
    strdict[stressor.get('id')]['foaf:page'] = '<https://identifiers.org/aop.stressor/' + refs['Stressor'][stressor.get('id')] + '>'
    strdict[stressor.get('id')]['dc:title'] = '"' + stressor.find(aopxml + 'name').text + '"'
    if stressor.find(aopxml + 'description').text is not None:
        strdict[stressor.get('id')]['dc:description'] = '"""' + HTML_TAG_PATTERN.sub('', stressor.find(aopxml + 'description').text) + '"""'
    strdict[stressor.get('id')]['dcterms:created'] = stressor.find(aopxml + 'creation-timestamp').text
    strdict[stressor.get('id')]['dcterms:modified'] = stressor.find(aopxml + 'last-modification-timestamp').text
    strdict[stressor.get('id')]['aopo:has_chemical_entity'] = []
    strdict[stressor.get('id')]['linktochemical'] = []
    if stressor.find(aopxml + 'chemicals') is not None:
        for chemical in stressor.find(aopxml + 'chemicals').findall(aopxml + 'chemical-initiator'):
            strdict[stressor.get('id')]['aopo:has_chemical_entity'].append('"' + chemical.get('user-term') + '"')
            strdict[stressor.get('id')]['linktochemical'].append(chemical.get('chemical-id'))
logger.info(f'Completed stressor parsing: {len(strdict)} stressors processed')


# ### Taxonomy



taxdict = {}
for tax in root.findall(aopxml + 'taxonomy'):
    taxdict[tax.get('id')] = {}
    taxdict[tax.get('id')]['dc:source'] = tax.find(aopxml + 'source').text
    taxdict[tax.get('id')]['dc:title'] = tax.find(aopxml + 'name').text
    if taxdict[tax.get('id')]['dc:source'] == 'NCBI':
        taxdict[tax.get('id')]['dc:identifier'] = 'ncbitaxon:' + tax.find(aopxml + 'source-id').text
    elif taxdict[tax.get('id')]['dc:source'] is not None:
        taxdict[tax.get('id')]['dc:identifier'] = '"' + tax.find(aopxml + 'source-id').text + '"'
    else:
        taxdict[tax.get('id')]['dc:identifier'] = '"' + tax.find(aopxml + 'source-id').text + '"'
logger.info(f'Taxonomy parsing completed: {len(taxdict)} taxonomies processed')


# ### Key Event Components
# Which comprise of the Biological Actions, Biological Processes, Biological Objects.



bioactdict = {None: {}}
bioactdict[None]['dc:identifier'] = None
bioactdict[None]['dc:source'] = None
bioactdict[None]['dc:title'] = None
for bioact in root.findall(aopxml + 'biological-action'):
    bioactdict[bioact.get('id')] = {}
    bioactdict[bioact.get('id')]['dc:source'] = '"' + bioact.find(aopxml + 'source').text + '"'
    bioactdict[bioact.get('id')]['dc:title'] = '"' + bioact.find(aopxml + 'name').text + '"'
    bioactdict[bioact.get('id')]['dc:identifier'] = '"' + bioact.find(aopxml + 'name').text + '"'
logger.info(f'Biological Activity parsing completed: {len(bioactdict)} annotations processed')




# Initialize bioprodict with default values
bioprodict = {
    None: {
        'dc:identifier': None,
        'dc:source': None,
        'dc:title': None
    }
}

# Mapping of source prefixes to their respective formats
source_prefix_map = {
    '"GO"': ('go:', 3),
    '"MI"': ('mi:', 0),
    '"MP"': ('mp:', 3),
    '"MESH"': ('mesh:', 0),
    '"HP"': ('hp:', 3),
    '"PCO"': ('pco:', 4),
    '"NBO"': ('nbo:', 4),
    '"VT"': ('vt:', 3),
    '"RBO"': ('rbo:', 4),
    '"NCI"': ('nci:', 4),
    '"IDO"': ('ido:', 4),
}

# Loop through biological processes and populate bioprodict
for biopro in root.findall(aopxml + 'biological-process'):
    biopro_id = biopro.get('id')
    bioprodict[biopro_id] = {}

    # Extract values
    source = f'"{biopro.find(aopxml + "source").text}"'
    name = f'"{biopro.find(aopxml + "name").text}"'
    source_id = biopro.find(aopxml + 'source-id').text

    # Populate source and title
    bioprodict[biopro_id]['dc:source'] = source
    bioprodict[biopro_id]['dc:title'] = name

    # Handle identifier based on source prefix
    if source in source_prefix_map:
        prefix, offset = source_prefix_map[source]
        identifier = prefix + source_id[offset:]
        bioprodict[biopro_id]['dc:identifier'] = identifier
    else:
        # Default case for unhandled sources
        bioprodict[biopro_id]['dc:identifier'] = source_id

logger.info(f'Biological Process parsing completed: {len(bioprodict)} annotations processed')




# Initialize bioobjdict with default values
bioobjdict = {
    None: {
        'dc:identifier': None,
        'dc:source': None,
        'dc:title': None
    }
}
objectstoskip = []
prolist = []

# Mapping of source prefixes to their respective formats
source_prefix_map = {
    '"PR"': ('pr:', 3),
    '"CL"': ('cl:', 3),
    '"MESH"': ('mesh:', 0),
    '"GO"': ('go:', 3),
    '"UBERON"': ('uberon:', 7),
    '"CHEBI"': ('chebio:', 6),
    '"MP"': ('mp:', 3),
    '"FMA"': ('fma:', 4),
    '"PCO"': ('pco:', 4),
}

# Loop through biological objects and populate bioobjdict
for bioobj in root.findall(aopxml + 'biological-object'):
    bioobj_id = bioobj.get('id')
    bioobjdict[bioobj_id] = {}

    # Extract values
    source = f'"{bioobj.find(aopxml + "source").text}"'
    name = f'"{bioobj.find(aopxml + "name").text}"'
    source_id = bioobj.find(aopxml + 'source-id').text

    # Populate source and title
    bioobjdict[bioobj_id]['dc:source'] = source
    bioobjdict[bioobj_id]['dc:title'] = name

    # Handle identifier based on source prefix
    if source in source_prefix_map:
        prefix, offset = source_prefix_map[source]
        identifier = prefix + source_id[offset:]
        bioobjdict[bioobj_id]['dc:identifier'] = identifier

        # Add to prolist if PR
        if source == '"PR"':
            prolist.append(identifier)
    else:
        # Default case for unhandled sources
        bioobjdict[bioobj_id]['dc:identifier'] = f'"{source_id}"'

logger.info(f'Biological Object parsing completed: {len(bioobjdict)} annotations processed')


# The Biological Objects containing terms from the Protein Ontology are mapped to protein identifiers with the PR mapping file `promapping.txt`, which was downloaded from the [Protein Consortium website](https://proconsortium.org/download/current/), which provides matching identifiers from Entrez Gene, HGNC and UniProt. The file location should be the `filepath` variable defined in Step #2.



pro = "promapping.txt"
# Download protein mapping file with error handling
try:
    logger.info("Downloading protein mapping file")
    urllib.request.urlretrieve(PROMAPPING_URL, filepath + pro)
    logger.info(f"Successfully downloaded {pro}")
except Exception as e:
    logger.error(f"Failed to download protein mapping file: {e}")
    raise SystemExit(1)




try:
    fileStatsObj = os.stat(filepath + pro)
    PromodificationTime = time.ctime(fileStatsObj[stat.ST_MTIME])
    logger.info(f"Protein mapping file last modified: {PromodificationTime}")
except OSError as e:
    logger.error(f"Could not get file stats for {pro}: {e}")
    PromodificationTime = "Unknown"




# Open promapping file with error handling
try:
    f = open(filepath+pro, "r", encoding='utf-8')
except IOError as e:
    logger.error(f"Failed to open promapping file {filepath+pro}: {e}")
    raise SystemExit(1)
prodict = {}
hgnclist = []
uniprotlist = []
ncbigenelist = []
for line in f:
    a = line.split('\t')
    key = 'pr:'+a[0][3:]
    if key in prolist:
        if not key in prodict:
            prodict[key] = []
        if 'HGNC:' in a[1]:
            prodict[key].append('hgnc:'+a[1][5:])
            hgnclist.append('hgnc:'+a[1][5:])
        if 'NCBIGene:' in a[1]:
            prodict[key].append('ncbigene:'+a[1][9:])
            ncbigenelist.append('ncbigene:'+a[1][9:])
        if 'UniProtKB:' in a[1]:
            prodict[key].append('uniprot:'+a[1].split(',')[0][10:])
            uniprotlist.append('uniprot:'+a[1].split(',')[0][10:])
        if prodict[key]==[]:
            del prodict[key]
f.close()
logger.info(f'Protein mapping completed: added {len(hgnclist)+len(ncbigenelist)+len(uniprotlist)} identifiers for {len(prodict)} Protein Ontology terms')


# ### Key Events
# The KEs also include the entities for cell-terms and organ-terms.



listofkedescriptions = []
for ke in root.findall(aopxml + 'key-event'):
    if not ke.get('id') in kedict:
        kedict[ke.get('id')] = {}
    kedict[ke.get('id')]['dc:identifier'] = 'aop.events:' + refs['KE'][ke.get('id')]
    kedict[ke.get('id')]['rdfs:label'] = '"KE ' + refs['KE'][ke.get('id')] + '"'
    kedict[ke.get('id')]['foaf:page'] = '<https://identifiers.org/aop.events/' + refs['KE'][ke.get('id')] + '>'
    kedict[ke.get('id')]['dc:title'] = '"' + ke.find(aopxml + 'title').text + '"'
    kedict[ke.get('id')]['dcterms:alternative'] = ke.find(aopxml + 'short-name').text
    kedict[ke.get('id')]['nci:C25664'] = '"""' + ke.find(aopxml + 'biological-organization-level').text + '"""'
    if ke.find(aopxml + 'description').text is not None:
        kedict[ke.get('id')]['dc:description'] = '"""' + HTML_TAG_PATTERN.sub('', ke.find(aopxml + 'description').text) + '"""'
#    if ke.find(aopxml + 'evidence-supporting-taxonomic-applicability').text is not None:
#        kedict[ke.get('id')]['dc:description'] = '"""' + HTML_TAG_PATTERN.sub('', ke.find(aopxml + 'evidence-supporting-taxonomic-applicability').text) + '"""'
    if ke.find(aopxml + 'measurement-methodology').text is not None:
        kedict[ke.get('id')]['mmo:0000000'] = '"""' + HTML_TAG_PATTERN.sub('', ke.find(aopxml + 'measurement-methodology').text) + '"""'
    kedict[ke.get('id')]['biological-organization-level'] = ke.find(aopxml + 'biological-organization-level').text
    kedict[ke.get('id')]['dc:source'] = ke.find(aopxml + 'source').text
    for appl in ke.findall(aopxml + 'applicability'):
        for sex in appl.findall(aopxml + 'sex'):
            if 'pato:0000047' not in kedict[ke.get('id')]:
                kedict[ke.get('id')]['pato:0000047'] = [[sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text]]
            else:
                kedict[ke.get('id')]['pato:0000047'].append([sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text])
        for life in appl.findall(aopxml + 'life-stage'):
            if 'aopo:LifeStageContext' not in kedict[ke.get('id')]:
                kedict[ke.get('id')]['aopo:LifeStageContext'] = [[life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text]]
            else:
                kedict[ke.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text])
        for tax in appl.findall(aopxml + 'taxonomy'):
            if 'ncbitaxon:131567' not in kedict[ke.get('id')]:
                if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
                    kedict[ke.get('id')]['ncbitaxon:131567'] = [[tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']]]
            else:
                if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
                    kedict[ke.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']])
    kedict[ke.get('id')]['biological-events'] = []
    kedict[ke.get('id')]['biological-event'] = {}
    kedict[ke.get('id')]['biological-event']['go:0008150'] = []
    kedict[ke.get('id')]['biological-event']['pato:0001241'] = []
    kedict[ke.get('id')]['biological-event']['pato:0000001'] = []
    bioevents = ke.find(aopxml + 'biological-events')
    if bioevents is not None:
        for event in bioevents.findall(aopxml + 'biological-event'):
            event_entry = {}
            if event.get('process-id') is not None:
                event_entry['process'] = bioprodict[event.get('process-id')]['dc:identifier']
                kedict[ke.get('id')]['biological-event']['go:0008150'].append(bioprodict[event.get('process-id')]['dc:identifier'])
            if event.get('object-id') is not None:
                event_entry['object'] = bioobjdict[event.get('object-id')]['dc:identifier']
                kedict[ke.get('id')]['biological-event']['pato:0001241'].append(bioobjdict[event.get('object-id')]['dc:identifier'])
            if event.get('action-id') is not None:
                event_entry['action'] = bioactdict[event.get('action-id')]['dc:identifier']
                kedict[ke.get('id')]['biological-event']['pato:0000001'].append(bioactdict[event.get('action-id')]['dc:identifier'])
            kedict[ke.get('id')]['biological-events'].append(event_entry)
    if ke.find(aopxml + 'cell-term') is not None:
        kedict[ke.get('id')]['aopo:CellTypeContext'] = {}
        kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'] = '"' + ke.find(aopxml + 'cell-term').find(aopxml + 'source').text + '"'
        kedict[ke.get('id')]['aopo:CellTypeContext']['dc:title'] = '"' + ke.find(aopxml + 'cell-term').find(aopxml + 'name').text + '"'
        if kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'] == '"CL"':
            kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier'] = ['cl:' + ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text[3:], ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text]
        elif kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'] == '"UBERON"':
            kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier'] = ['uberon:' + ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text[7:], ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text]
        else:
            kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier'] = ['"' + ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text + '"', 'placeholder']
    if ke.find(aopxml + 'organ-term') is not None:
        kedict[ke.get('id')]['aopo:OrganContext'] = {}
        kedict[ke.get('id')]['aopo:OrganContext']['dc:source'] = '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'source').text + '"'
        kedict[ke.get('id')]['aopo:OrganContext']['dc:title'] = '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'name').text + '"'
        if kedict[ke.get('id')]['aopo:OrganContext']['dc:source'] == '"UBERON"':
            kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier'] = ['uberon:' + ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text[7:], ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text]
        else:
            kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier'] = [
                '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text + '"', 'placeholder']
    if ke.find(aopxml + 'key-event-stressors') is not None:
        kedict[ke.get('id')]['nci:C54571'] = {}
        for stressor in ke.find(aopxml + 'key-event-stressors').findall(aopxml + 'key-event-stressor'):
            kedict[ke.get('id')]['nci:C54571'][stressor.get('stressor-id')] = {}
            kedict[ke.get('id')]['nci:C54571'][stressor.get('stressor-id')]['dc:identifier'] = strdict[stressor.get('stressor-id')]['dc:identifier']
            kedict[ke.get('id')]['nci:C54571'][stressor.get('stressor-id')]['aopo:has_evidence'] = stressor.find(aopxml + 'evidence').text
logger.info(f'Key Events parsing completed: {len(kedict)} events processed')


# ### Key Event Relationships



kerdict = {}
for ker in root.findall(aopxml + 'key-event-relationship'):
    kerdict[ker.get('id')] = {}
    kerdict[ker.get('id')]['dc:identifier'] = 'aop.relationships:' + refs['KER'][ker.get('id')]
    kerdict[ker.get('id')]['rdfs:label'] = '"KER ' + refs['KER'][ker.get('id')] + '"'
    kerdict[ker.get('id')]['foaf:page'] = '<https://identifiers.org/aop.relationships/' + refs['KER'][ker.get('id')] + '>'
    kerdict[ker.get('id')]['dc:source'] = ker.find(aopxml + 'source').text
    kerdict[ker.get('id')]['dcterms:created'] = ker.find(aopxml + 'creation-timestamp').text
    kerdict[ker.get('id')]['dcterms:modified'] = ker.find(aopxml + 'last-modification-timestamp').text
    if ker.find(aopxml + 'description').text is not None:
        kerdict[ker.get('id')]['dc:description'] = '"""' + HTML_TAG_PATTERN.sub('', ker.find(aopxml + 'description').text) + '"""'
    for weight in ker.findall(aopxml + 'weight-of-evidence'):
        if weight.find(aopxml + 'biological-plausibility').text is not None:
            kerdict[ker.get('id')]['nci:C80263'] = '"""' + HTML_TAG_PATTERN.sub('', weight.find(aopxml + 'biological-plausibility').text) + '"""'
        if weight.find(aopxml + 'emperical-support-linkage').text is not None:
            kerdict[ker.get('id')]['edam:data_2042'] = '"""' + HTML_TAG_PATTERN.sub('', weight.find(aopxml + 'emperical-support-linkage').text) + '"""'
        if weight.find(aopxml + 'uncertainties-or-inconsistencies').text is not None:
            kerdict[ker.get('id')]['nci:C71478'] = '"""' + HTML_TAG_PATTERN.sub('', weight.find(aopxml + 'uncertainties-or-inconsistencies').text) + '"""'
    kerdict[ker.get('id')]['aopo:has_upstream_key_event'] = {}
    kerdict[ker.get('id')]['aopo:has_upstream_key_event']['id'] = ker.find(aopxml + 'title').find(aopxml + 'upstream-id').text
    kerdict[ker.get('id')]['aopo:has_upstream_key_event']['dc:identifier'] = 'aop.events:' + refs['KE'][ker.find(aopxml + 'title').find(aopxml + 'upstream-id').text]
    kerdict[ker.get('id')]['aopo:has_downstream_key_event'] = {}
    kerdict[ker.get('id')]['aopo:has_downstream_key_event']['id'] = ker.find(aopxml + 'title').find(aopxml + 'downstream-id').text
    kerdict[ker.get('id')]['aopo:has_downstream_key_event']['dc:identifier'] = 'aop.events:' + refs['KE'][ker.find(aopxml + 'title').find(aopxml + 'downstream-id').text]
    for appl in ker.findall(aopxml + 'taxonomic-applicability'):
        for sex in appl.findall(aopxml + 'sex'):
            if 'pato:0000047' not in kerdict[ker.get('id')]:
                kerdict[ker.get('id')]['pato:0000047'] = [[sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text]]
            else:
                kerdict[ker.get('id')]['pato:0000047'].append([sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text])
        for life in appl.findall(aopxml + 'life-stage'):
            if 'aopo:LifeStageContext' not in kerdict[ker.get('id')]:
                kerdict[ker.get('id')]['aopo:LifeStageContext'] = [[life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text]]
            else:
                kerdict[ker.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text])
        for tax in appl.findall(aopxml + 'taxonomy'):
            if 'ncbitaxon:131567' not in kerdict[ker.get('id')]:
                if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
                    kerdict[ker.get('id')]['ncbitaxon:131567'] = [[tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']]]
            else:
                if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
                    kerdict[ker.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']])
logger.info(f'Key Event Relationships parsing completed: {len(kerdict)} relationships processed')


# ## <b>Step #4: Writing the AOP-Wiki RDF</b>
# This step involves the writing of the central RDF file, containing all information from the AOP-Wiki XML, written in Turtle (ttl) syntax.



# --- RDF Writing Helper Functions ---
def write_multivalue_triple(file_handle, predicate, values, quote=False):
    """Write multiple values for a single predicate."""
    if not values:
        return
    formatted = [f'"{v}"' if quote else v for v in values]
    file_handle.write(f' ;\n\t{predicate}\t' + ', '.join(formatted))

def write_triple(file_handle, subject, predicate, obj, end_char=';'):
    """Write a single RDF triple."""
    file_handle.write(f'{subject}\t{predicate}\t{obj} {end_char}\n')

def write_subject_start(file_handle, subject, rdf_type=None):
    """Start writing triples for a subject."""
    if rdf_type:
        file_handle.write(f'\n{subject}\ta\t{rdf_type}')
    else:
        file_handle.write(f'\n{subject}')

def safe_write_description(file_handle, predicate, text):
    """Safely write description text, cleaning HTML tags."""
    if text and text.strip():
        cleaned_text = clean_html_tags(text.strip())
        if cleaned_text:
            file_handle.write(f' ;\n\t{predicate}\t"""' + cleaned_text + '"""')

def safe_write_simple(file_handle, predicate, value, quote=True):
    """Safely write a simple property if value exists."""
    if value is not None and str(value).strip():
        formatted_value = f'"{value}"' if quote else str(value)
        file_handle.write(f' ;\n\t{predicate}\t{formatted_value}')

# Open main RDF output file with proper error handling
main_rdf_filename = filepath + 'AOPWikiRDF.ttl'
logger.info(f"Writing main RDF file: {main_rdf_filename}")

# Start main RDF file writing with error handling
try:
    main_rdf_file = open(main_rdf_filename, 'w', encoding='utf-8')
    g = main_rdf_file  # Keep existing variable name for compatibility
except IOError as e:
    logger.error(f"Failed to open main RDF output file: {e}")
    raise SystemExit(1)

# ### Writing prefixes
# The first thing is writing the Prefixes of all ontologies and database identifiers, which go in the top of the document. That is followed by the writing of all entities of the AOP-Wiki described in Figure 1.



# Load the prefixes from a CSV file
prefixes = pd.read_csv("prefixes.csv")

# Format the prefixes as RDF-compatible strings
prefix_strings = prefixes.apply(lambda row: f"@prefix {row['prefix']}: <{row['uri']}> .", axis=1)

# Join the strings with newlines
rdf_prefixes = "\n".join(prefix_strings)
logger.info("Writing RDF prefixes to file")




g.write(rdf_prefixes + "\n")




# Write SHACL declarations (assumes `g` is your open file object)
g.write('\n')  # newline after @prefixes
for _, row in prefixes.iterrows():
    prefix = row['prefix']
    uri = row['uri']
    g.write(f'[] sh:declare [ sh:prefix "{prefix}" ; sh:namespace "{uri}"^^xsd:anyURI ] .\n')


# ### Writing Adverse Outcome Pathway triples



for aop in aopdict:
    g.write(
        aopdict[aop]['dc:identifier'] +
        '\n\ta\taopo:AdverseOutcomePathway ;' +
        '\n\tdc:identifier\t' + aopdict[aop]['dc:identifier'] +
        ' ;\n\trdfs:label\t' + aopdict[aop]['rdfs:label'] +
        ' ;\n\trdfs:seeAlso\t' + aopdict[aop]['foaf:page'] +
        ' ;\n\tfoaf:page\t' + aopdict[aop]['foaf:page'] +
        ' ;\n\tdc:title\t' + aopdict[aop]['dc:title'] +
        ' ;\n\tdcterms:alternative\t"' + aopdict[aop]['dcterms:alternative'] + '"' +
        ' ;\n\tdc:source\t"' + aopdict[aop]['dc:source'] + '"' +
        ' ;\n\tdcterms:created\t"' + aopdict[aop]['dcterms:created'] + '"' +
        ' ;\n\tdcterms:modified\t"' + aopdict[aop]['dcterms:modified'] + '"'
    )

    if 'dc:description' in aopdict[aop] and aopdict[aop]['dc:description']:
        write_multivalue_triple(g, 'dc:description', aopdict[aop]['dc:description'], quote=False)

    for predicate in [
            'nci:C25217', 'nci:C48192', 'aopo:AopContext', 'aopo:has_evidence',
            'edam:operation_3799', 'nci:C25725', 'dc:creator',
            'dcterms:accessRights', 'dcterms:abstract'
        ]:
            if predicate in aopdict[aop]:
                g.write(f' ;\n\t{predicate}\t' + aopdict[aop][predicate])
                
    # OECD and SAAOP status are written as nci:C25688
    if 'oecd-status' in aopdict[aop]:
        g.write(' ;\n\tnci:C25688\t' + aopdict[aop]['oecd-status'])
    if 'saaop-status' in aopdict[aop]:
        g.write(' ;\n\tnci:C25688\t' + aopdict[aop]['saaop-status'])

    # has_key_event
    write_multivalue_triple(g,'aopo:has_key_event',[aopdict[aop]['aopo:has_key_event'][ke]['dc:identifier'] for ke in aopdict[aop].get('aopo:has_key_event', {})])

    # has_key_event_relationship
    write_multivalue_triple(g,'aopo:has_key_event_relationship',[aopdict[aop]['aopo:has_key_event_relationship'][ker]['dc:identifier'] for ker in aopdict[aop].get('aopo:has_key_event_relationship', {})])

    # has_molecular_initiating_event
    write_multivalue_triple(g,'aopo:has_molecular_initiating_event',[aopdict[aop]['aopo:has_molecular_initiating_event'][mie]['dc:identifier'] for mie in aopdict[aop].get('aopo:has_molecular_initiating_event', {})])

    # has_adverse_outcome
    write_multivalue_triple(g,'aopo:has_adverse_outcome',[aopdict[aop]['aopo:has_adverse_outcome'][ao]['dc:identifier'] for ao in aopdict[aop].get('aopo:has_adverse_outcome', {})])

    # stressors
    write_multivalue_triple(g,'nci:C54571',[aopdict[aop]['nci:C54571'][s]['dc:identifier'] for s in aopdict[aop].get('nci:C54571', {})])

    # sex
    if 'pato:0000047' in aopdict[aop]:
        write_multivalue_triple(g,'pato:0000047',[sex[1] for sex in aopdict[aop]['pato:0000047']],quote=True)

    # life stage
    if 'aopo:LifeStageContext' in aopdict[aop]:
        write_multivalue_triple(g,'aopo:LifeStageContext',[stage[1] for stage in aopdict[aop]['aopo:LifeStageContext']],quote=True)

    g.write(' .\n\n')

logger.info("Section completed")


# ### Writing Key Event triples
# This step also includes the extraction of the cell-terms and organ-terms, which are written to the file later.



cterm = {}
oterm = {}
bioevent_triples = []

for ke in kedict:
    g.write(
        kedict[ke]['dc:identifier'] +
        '\n\ta\taopo:KeyEvent ;' +
        '\n\tdc:identifier\t' + kedict[ke]['dc:identifier'] +
        ' ;\n\trdfs:label\t' + kedict[ke]['rdfs:label'] +
        ' ;\n\tfoaf:page\t' + kedict[ke]['foaf:page'] +
        ' ;\n\trdfs:seeAlso\t' + kedict[ke]['foaf:page'] +
        ' ;\n\tdc:title\t' + kedict[ke]['dc:title'] +
        ' ;\n\tdcterms:alternative\t"' + kedict[ke]['dcterms:alternative'] + '"' +
        ' ;\n\tdc:source\t"' + kedict[ke]['dc:source'] + '"'
    )

    if 'dc:description' in kedict[ke]:
        g.write(' ;\n\tdc:description\t' + kedict[ke]['dc:description'])

    for predicate in ['mmo:0000000', 'nci:C25664']:
        if predicate in kedict[ke]:
            g.write(f' ;\n\t{predicate}\t' + kedict[ke][predicate])

    if 'pato:0000047' in kedict[ke]:
        write_multivalue_triple(g,'pato:0000047',[sex[1] for sex in kedict[ke]['pato:0000047']],quote=True)

    if 'aopo:LifeStageContext' in kedict[ke]:
        write_multivalue_triple(g,'aopo:LifeStageContext',[stage[1] for stage in kedict[ke]['aopo:LifeStageContext']],quote=True)

    if 'ncbitaxon:131567' in kedict[ke]:
        write_multivalue_triple(g,'ncbitaxon:131567',[tax[2] for tax in kedict[ke]['ncbitaxon:131567']])

    if 'nci:C54571' in kedict[ke]:
        write_multivalue_triple(g,'nci:C54571',[kedict[ke]['nci:C54571'][s]['dc:identifier'] for s in kedict[ke]['nci:C54571']])

    if 'aopo:CellTypeContext' in kedict[ke]:
        cell_id = kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]
        g.write(' ;\n\taopo:CellTypeContext\t' + cell_id)
        if cell_id not in cterm:
            cterm[cell_id] = {
                'dc:source': kedict[ke]['aopo:CellTypeContext']['dc:source'],
                'dc:title': kedict[ke]['aopo:CellTypeContext']['dc:title']
            }

    if 'aopo:OrganContext' in kedict[ke]:
        organ_id = kedict[ke]['aopo:OrganContext']['dc:identifier'][0]
        g.write(' ;\n\taopo:OrganContext\t' + organ_id)
        if organ_id not in oterm:
            oterm[organ_id] = {
                'dc:source': kedict[ke]['aopo:OrganContext']['dc:source'],
                'dc:title': kedict[ke]['aopo:OrganContext']['dc:title']
            }

    if 'biological-events' in kedict[ke]:
        bioevent_uris = []
        for idx, be in enumerate(kedict[ke]['biological-events']):
            be_uri = f'<{kedict[ke]["dc:identifier"].split(":")[1]}_bioevent_{idx}>'
            bioevent_uris.append(be_uri)

            triples = [f'{be_uri} a aopo:BiologicalEvent']
            if 'process' in be:
                triples.append(f'\taopo:hasProcess\t{be["process"]}')
            if 'object' in be:
                triples.append(f'\taopo:hasObject\t{be["object"]}')
            if 'action' in be:
                triples.append(f'\taopo:hasAction\t{be["action"]}')
            bioevent_triples.append(' ;\n'.join(triples) + ' .\n\n')

        write_multivalue_triple(g, 'aopo:hasBiologicalEvent', bioevent_uris)

    if 'biological-event' in kedict[ke]:
        for p in ['go:0008150', 'pato:0000001', 'pato:0001241']:
            values = sorted(set(kedict[ke]['biological-event'].get(p, [])))
            write_multivalue_triple(g, p, values)

    # Link KE to AOP(s)
    aop_links = [
        aopdict[aop]['dc:identifier']
        for aop in aopdict
        if ke in aopdict[aop]['aopo:has_key_event']
    ]
    write_multivalue_triple(g, 'dcterms:isPartOf', aop_links)

    g.write(' .\n\n')

logger.info("Section completed")




# Write all biological events as separate RDF blocks
for triple_block in bioevent_triples:
    g.write(triple_block)


# ### Writing Key Event Relationship triples



for ker in kerdict:
    g.write(
        kerdict[ker]['dc:identifier'] +
        '\n\ta\taopo:KeyEventRelationship ;' +
        '\n\tdc:identifier\t' + kerdict[ker]['dc:identifier'] +
        ' ;\n\trdfs:label\t' + kerdict[ker]['rdfs:label'] +
        ' ;\n\tfoaf:page\t' + kerdict[ker]['foaf:page'] +
        ' ;\n\trdfs:seeAlso\t' + kerdict[ker]['foaf:page'] +
        ' ;\n\tdcterms:created\t"' + kerdict[ker]['dcterms:created'] + '"' +
        ' ;\n\tdcterms:modified\t"' + kerdict[ker]['dcterms:modified'] + '"' +
        ' ;\n\taopo:has_upstream_key_event\t' + kerdict[ker]['aopo:has_upstream_key_event']['dc:identifier'] +
        ' ;\n\taopo:has_downstream_key_event\t' + kerdict[ker]['aopo:has_downstream_key_event']['dc:identifier']
    )

    if 'dc:description' in kerdict[ker]:
        g.write(' ;\n\tdc:description\t' + kerdict[ker]['dc:description'])

    for predicate in ['nci:C80263', 'edam:data_2042', 'nci:C71478']:
        if predicate in kerdict[ker]:
            value = kerdict[ker][predicate].replace("\\", "")
            g.write(f' ;\n\t{predicate}\t{value}')

    if 'pato:0000047' in kerdict[ker]:
        write_multivalue_triple(g,'pato:0000047',[sex[1] for sex in kerdict[ker]['pato:0000047']],quote=True)

    if 'aopo:LifeStageContext' in kerdict[ker]:
        write_multivalue_triple(g,'aopo:LifeStageContext', [stage[1] for stage in kerdict[ker]['aopo:LifeStageContext']],quote=True)

    if 'ncbitaxon:131567' in kerdict[ker]:
        write_multivalue_triple(g,'ncbitaxon:131567',[tax[2] for tax in kerdict[ker]['ncbitaxon:131567']] )

    # Link KER to AOP(s)
    aop_links = [
        aopdict[aop]['dc:identifier']
        for aop in aopdict
        if ker in aopdict[aop]['aopo:has_key_event_relationship']
    ]
    write_multivalue_triple(g, 'dcterms:isPartOf', aop_links)

    g.write(' .\n\n')

logger.info("Section completed")


# ### Writing Taxonomy triples



for tax in taxdict:
    if 'dc:identifier' in taxdict[tax]:
        if '"' not in taxdict[tax]['dc:identifier']:
            g.write(taxdict[tax]['dc:identifier'] + '\n\ta\tncbitaxon:131567 ;\n\tdc:identifier\t' + taxdict[tax]['dc:identifier'] + ' ;\n\tdc:title\t"' + taxdict[tax]['dc:title'])
            if taxdict[tax]['dc:source'] is not None:
                g.write('" ;\n\tdc:source\t"' + taxdict[tax]['dc:source'])
            g.write('" .\n\n')
logger.info("Section completed")


# ### Writing Stressor triples



for stressor in strdict:
    g.write(
        strdict[stressor]['dc:identifier'] +
        '\n\ta\tnci:C54571 ;' +
        '\n\tdc:identifier\t' + strdict[stressor]['dc:identifier'] +
        ' ;\n\trdfs:label\t' + strdict[stressor]['rdfs:label'] +
        ' ;\n\tfoaf:page\t' + strdict[stressor]['foaf:page'] +
        ' ;\n\tdc:title\t' + strdict[stressor]['dc:title'] +
        ' ;\n\tdcterms:created\t"' + strdict[stressor]['dcterms:created'] + '"' +
        ' ;\n\tdcterms:modified\t"' + strdict[stressor]['dcterms:modified'] + '"'
    )

    if 'dc:description' in strdict[stressor]:
        g.write(' ;\n\tdc:description\t' + strdict[stressor]['dc:description'])

    # Link to chemicals
    write_multivalue_triple(g,'aopo:has_chemical_entity',[chedict[chem]['dc:identifier'] for chem in strdict[stressor].get('linktochemical', [])])

    # Link to KEs
    ke_ids = [
        kedict[ke]['dc:identifier']
        for ke in kedict
        if 'nci:C54571' in kedict[ke] and stressor in kedict[ke]['nci:C54571']
    ]

    # Extend to AOPs via linked KEs
    aop_ids = set()
    for ke_id in ke_ids:
        for ke in kedict:
            if kedict[ke]['dc:identifier'] == ke_id:
                for aop in aopdict:
                    if ke in aopdict[aop]['aopo:has_key_event']:
                        aop_ids.add(aopdict[aop]['dc:identifier'])

    # Direct links from AOPs
    for aop in aopdict:
        if stressor in aopdict[aop].get('nci:C54571', {}):
            aop_ids.add(aopdict[aop]['dc:identifier'])

    # Combine KE and AOP dcterms:isPartOf links
    write_multivalue_triple(g, 'dcterms:isPartOf', list(set(ke_ids + list(aop_ids))))

    g.write(' .\n\n')

logger.info("Section completed")


# ### Writing Biological Process triples



for pro in bioprodict:
    if pro is not None:
        g.write(bioprodict[pro]['dc:identifier'] + '\ta\tgo:0008150 ;\n\tdc:identifier\t' + bioprodict[pro]['dc:identifier'] + ' ;\n\tdc:title\t' + bioprodict[pro]['dc:title'] + ' ;\n\tdc:source\t' + bioprodict[pro]['dc:source'] + ' . \n\n')
logger.info("Section completed")


# ### Writing Biological Object triples



for obj in bioobjdict:
    if obj is not None and "N/A" not in bioobjdict[obj]['dc:identifier'] and 'TAIR' not in bioobjdict[obj]['dc:identifier']:
        g.write(bioobjdict[obj]['dc:identifier'] + '\ta\tpato:0001241 ;\n\tdc:identifier\t' + bioobjdict[obj]['dc:identifier'] + ' ;\n\tdc:title\t' + bioobjdict[obj]['dc:title'] + ' ;\n\tdc:source\t' + bioobjdict[obj]['dc:source'])
        if bioobjdict[obj]['dc:identifier'] in prodict:
            g.write(' ;\n\tskos:exactMatch\t'+','.join(prodict[bioobjdict[obj]['dc:identifier']]))
        g.write('. \n\n')
logger.info("Section completed")


# ### Writing Biological Action triples
# 



for act in bioactdict:
    if act is not None:
        if '"' not in bioactdict[act]['dc:identifier']:
            g.write(bioactdict[act]['dc:identifier'] + '\ta\tpato:0000001 ;\n\tdc:identifier\t' + bioactdict[act]['dc:identifier'] + ' ;\n\tdc:title\t' + bioactdict[act]['dc:title'] + ' ;\n\tdc:source\t' + bioactdict[act]['dc:source'] + ' . \n\n')
logger.info("Section completed")


# ### Writing Cell term triples



for item in cterm:
    if '"' not in item:
        g.write(item + '\ta\taopo:CellTypeContext ;\n\tdc:identifier\t' + item + ' ;\n\tdc:title\t' + cterm[item]['dc:title'] + ' ;\n\tdc:source\t' + cterm[item]['dc:source'] + ' .\n\n')
logger.info("Section completed")


# ### Writing Organ term triples



for item in oterm:
    if '"' not in item:
        g.write(item + '\ta\taopo:OrganContext ;\n\tdc:identifier\t' + item + ' ;\n\tdc:title\t' + oterm[item]['dc:title'] + ' ;\n\tdc:source\t' + oterm[item]['dc:source'] + ' .\n\n')
logger.info("Section completed")


# ### Writing Chemical triples



for che in chedict:
    che_data = chedict[che]
    if 'dc:identifier' not in che_data or '"' in che_data['dc:identifier']:
        continue

    g.write(f"{che_data['dc:identifier']}\n\tdc:identifier\t{che_data['dc:identifier']}")

    if 'cheminf:000446' in che_data:
        g.write(' ;\n\ta\tcheminf:000000, cheminf:000446')
        g.write(f' ;\n\tcheminf:000446\t{che_data["cheminf:000446"]}')

    if che_data.get('cheminf:000059') != 'inchikey:None':
        g.write(f' ;\n\tcheminf:000059\t{che_data["cheminf:000059"]}')

    if 'dc:title' in che_data:
        g.write(f' ;\n\tdc:title\t{che_data["dc:title"]}')

    if 'cheminf:000568' in che_data:
        g.write(f' ;\n\tcheminf:000568\t{che_data["cheminf:000568"]}')

    # Collect all cheminf properties for skos:exactMatch
    cheminf_keys = [
        'cheminf:000407', 'cheminf:000405', 'cheminf:000567', 'cheminf:000412',
        'cheminf:000140', 'cheminf:000406', 'cheminf:000408', 'cheminf:000409', 'cheminf:000564'
    ]
    exact_matches = []
    for key in cheminf_keys:
        exact_matches.extend(che_data.get(key, []))

    write_multivalue_triple(g, 'skos:exactMatch', exact_matches)

    if 'dcterms:alternative' in che_data:
        write_multivalue_triple(g, 'dcterms:alternative', che_data['dcterms:alternative'], quote=True)

    # Link chemical to stressors
    part_of_stressors = [
        strdict[stressor]['dc:identifier']
        for stressor in strdict
        if 'aopo:has_chemical_entity' in strdict[stressor]
        and che in strdict[stressor]['linktochemical']
    ]
    write_multivalue_triple(g, 'dcterms:isPartOf', part_of_stressors)

    g.write(' .\n\n')

logger.info("Section completed")




n = 0


# ### Writing mapped Chemical identifiers



for cas in listofcas:
    g.write(cas + '\tdc:source\t"CAS".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for inchikey in listofinchikey:
    g.write(inchikey + '\tdc:source\t"InChIKey".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
    
for comptox in listofcomptox:
    g.write(comptox + '\tdc:source\t"CompTox".\n\n')
    n += 1
logger.debug(f"Counter: {n}")

for chebi in listofchebi:
    g.write(chebi + '\ta\tcheminf:000407 ;\n\tcheminf:000407\t"'+chebi[6:]+'";\n\tdc:identifier\t"'+chebi+'";\n\tdc:source\t"ChEBI".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for chemspider in listofchemspider:
    g.write(chemspider + '\ta\tcheminf:000405 ;\n\tcheminf:000405\t"'+chemspider[11:]+'";\n\tdc:identifier\t"'+chemspider+'";\n\tdc:source\t"ChemSpider".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for wd in listofwikidata:
    g.write(wd + '\ta\tcheminf:000567 ;\n\tcheminf:000567\t"'+wd[9:]+'";\n\tdc:identifier\t"'+wd+'";\n\tdc:source\t"Wikidata".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for chembl in listofchembl:
    g.write(chembl + '\ta\tcheminf:000412 ;\n\tcheminf:000412\t"'+chembl[16:]+'";\n\tdc:identifier\t"'+chembl+'";\n\tdc:source\t"ChEMBL".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for pubchem in listofpubchem:
    g.write(pubchem + '\ta\tcheminf:000140 ;\n\tcheminf:000140\t"'+pubchem[17:]+'";\n\tdc:identifier\t"'+pubchem+'";\n\tdc:source\t"PubChem".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for drugbank in listofdrugbank:
    g.write(drugbank + '\ta\tcheminf:000406 ;\n\tcheminf:000406\t"'+drugbank[9:]+'";\n\tdc:identifier\t"'+drugbank+'";\n\tdc:source\t"DrugBank".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for kegg in listofkegg:
    g.write(kegg + '\ta\tcheminf:000409 ;\n\tcheminf:000409\t"'+kegg[14:]+'";\n\tdc:identifier\t"'+kegg+'";\n\tdc:source\t"KEGG".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for lipidmaps in listoflipidmaps:
    g.write(lipidmaps + '\ta\tcheminf:000564 ;\n\tcheminf:000564\t"'+lipidmaps[10:]+'";\n\tdc:identifier\t"'+lipidmaps+'";\n\tdc:source\t"LIPID MAPS".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
for hmdb in listofhmdb:
    g.write(hmdb + '\ta\tcheminf:000408 ;\n\tcheminf:000408\t"'+hmdb[5:]+'";\n\tdc:identifier\t"'+hmdb+'";\n\tdc:source\t"HMDB".\n\n')
    n += 1
logger.debug(f"Counter: {n}")
logger.info("Section completed")


# ### Writing mapped Gene identifiers



for hgnc in hgnclist:
    g.write(hgnc + '\ta\tedam:data_2298, edam:data_1025 ;\n\tedam:data_2298\t"'+hgnc[5:]+'";\n\tdc:identifier\t"'+hgnc+'";\n\tdc:source\t"HGNC".\n\n')

for entrez in ncbigenelist:
    g.write(entrez + '\ta\tedam:data_1027, edam:data_1025 ;\n\tedam:data_1027\t"'+entrez[9:]+'";\n\tdc:identifier\t"'+entrez+'";\n\tdc:source\t"Entrez Gene".\n\n')

for uniprot in uniprotlist:
    g.write(uniprot + '\ta\tedam:data_2291, edam:data_1025 ;\n\trdfs:seeAlso <http://purl.uniprot.org/uniprot/' + uniprot[8:] + '>;\n\towl:sameAs <http://purl.uniprot.org/uniprot/' + uniprot[8:] + '>;\n\tedam:data_2291\t"'+uniprot[8:]+'";\n\tdc:identifier\t"'+uniprot+'";\n\tdc:source\t"UniProt".\n\n')
    
logger.info("Section completed")


# ### Writing class labels



df = pd.read_csv(filepath + 'typelabels.txt')
df




for row,index in df.iterrows():
    g.write('\n\n'+index['URI']+'\trdfs:label\t"'+index['label'])
    if index['description'] != '-':
        g.write('";\n\tdc:description\t"""'+index['description']+'""".')
    else:
        g.write('".')


# Close the file.



main_rdf_file.close()
logger.info("AOP-Wiki RDF conversion completed successfully!")

# Final validation summary
logger.info("=== Conversion Summary ===")
logger.info(f"Total AOPs processed: {len(aopdict) if 'aopdict' in locals() else 'N/A'}")
logger.info(f"Total Key Events processed: {len(kedict) if 'kedict' in locals() else 'N/A'}")  
logger.info(f"Total KERs processed: {len(kerdict) if 'kerdict' in locals() else 'N/A'}")
logger.info(f"Total Chemicals processed: {len(chedict) if 'chedict' in locals() else 'N/A'}")
logger.info(f"RDF file created: {filepath}AOPWikiRDF.ttl")


# ## <b>Step #5: Gene ID text-mapping (HGNC)</b>
# In order to identify genes present in the textual descriptions of Key Events (KEs) and Key Event Relationships (KERs), HGNC identifier mapping was performed. [Genenames.org](https://www.genenames.org/) is the curated online repository for HGNC nomenclature, and it allows custom downloads for all HGNC entries, including approved symbols and names, previous symbols and synonyms. 
# 
# ## Step #5A - Parsing the custom HGNC file
# This starts with loading the custom download file, which was named `HGNCgenes.txt` and stored in the path defined in Step #2. Next, its contents are extracted and stored in a dictionary called `genedict1`, while variants are created for every gene name and gene symbol for more effective mapping of genes. These variants are stored in `genedict2`, which is used for more effective mapping of genes in Step #5B. 



HGNCfilename = 'HGNCgenes.txt'




fileStatsObj = os.stat (filepath + HGNCfilename)
HGNCmodificationTime = time.ctime ( fileStatsObj [ stat.ST_MTIME ] )
logger.info(f"HGNC data last modified: {HGNCmodificationTime}")




# Open HGNC genes file with error handling
try:
    HGNCgenes = open(filepath + HGNCfilename, 'r', encoding='utf-8')
except IOError as e:
    logger.error(f"Failed to open HGNC genes file {filepath + HGNCfilename}: {e}")
    raise SystemExit(1)
symbols = [' ','(',')','[',']',',','.']
genedict1 = {}
genedict2 = {}
b = 0
for line in HGNCgenes:
    if not 'HGNC ID	Approved symbol	Approved name	Previous symbols	Synonyms	Accession numbers	Ensembl ID(supplied by Ensembl)'in line:
        a = line[:-1].split('\t')
        if not '@' in a[1]: #gene clusters contain a '@' in their symbol, which are filtered out
            genedict1[a[1]] = []
            genedict2[a[1]] = []
            genedict1[a[1]].append(a[1])
            if not a[2] == '':
                genedict1[a[1]].append(a[2])
            for item in a[3:]:
                if not item == '':
                    for name in item.split(', '):
                        genedict1[a[1]].append(name)
            for item in genedict1[a[1]]:
                for s1 in symbols:
                    for s2 in symbols:
                        genedict2[a[1]].append((s1+item+s2))
HGNCgenes.close()
logger.info(f"Gene mapping setup: {len(genedict2)} genes included for mappings")

# Performance optimization: Pre-compile regex patterns for gene matching
logger.info("Pre-compiling gene regex patterns for optimized matching...")
compiled_gene_patterns = compile_gene_patterns(genedict1)
logger.info(f"Compiled {len(compiled_gene_patterns)} gene patterns for fast matching")


# ## Step #5B - HGNC identifier mapping
# Genes are mapped for descriptions of KEs and KERs, and for the biological plausibility and emperical support sections of KERs. First, these are screened for any overlap with all possible gene symbols and names captured in genedict1. Then, all positive matches are checked by mapping with all variants of those genes, ensuring the correct mapping. All matches are stored in the kedict and kerdict dictionaries. Also, all mapped genes are stored in a list called hgnclist.

# ### Key Events



hgnclist = []
keyhitcount = {}
logger.info("Starting gene mapping on Key Events (this may take a minute)...")
for ke in root.findall(aopxml + 'key-event'):
    if ke.find(aopxml + 'description').text is not None:
        # Use optimized gene mapping function
        description_text = kedict[ke.get('id')]['dc:description']
        found_genes = map_genes_in_text_optimized(description_text, compiled_gene_patterns, genedict1, hgnclist)
        
        if found_genes:
            kedict[ke.get('id')]['edam:data_1025'] = found_genes
logger.info(f"Key Event gene mapping completed: {len(hgnclist)} genes mapped to descriptions")




for gene, count in keyhitcount.items():
    if count > 10:
        logger.debug(f"Gene mapping hit: {gene}: {count} hits")


# ### Key Event Relationships



logger.info("Starting gene mapping on Key Events and KERs (this may take a couple of minutes)...")
for ker in root.findall(aopxml + 'key-event-relationship'):
    all_found_genes = []
    
    # Check description text
    if ker.find(aopxml + 'description').text is not None and 'dc:description' in kerdict[ker.get('id')]:
        description_genes = map_genes_in_text_optimized(kerdict[ker.get('id')]['dc:description'], compiled_gene_patterns, genedict1, hgnclist)
        all_found_genes.extend(description_genes)
    
    # Check biological plausibility and empirical support
    for weight in ker.findall(aopxml + 'weight-of-evidence'):
        if weight.find(aopxml + 'biological-plausibility').text is not None and 'nci:C80263' in kerdict[ker.get('id')]:
            bio_genes = map_genes_in_text_optimized(kerdict[ker.get('id')]['nci:C80263'], compiled_gene_patterns, genedict1, hgnclist)
            all_found_genes.extend(bio_genes)
            
        if weight.find(aopxml + 'emperical-support-linkage').text is not None and 'edam:data_2042' in kerdict[ker.get('id')]:
            emp_genes = map_genes_in_text_optimized(kerdict[ker.get('id')]['edam:data_2042'], compiled_gene_patterns, genedict1, hgnclist)
            all_found_genes.extend(emp_genes)
    
    # Remove duplicates while preserving order
    unique_genes = []
    for gene in all_found_genes:
        if gene not in unique_genes:
            unique_genes.append(gene)
    
    if unique_genes:
        kerdict[ker.get('id')]['edam:data_1025'] = unique_genes
logger.info(f"Gene mapping completed: {len(hgnclist)} genes mapped to Key Events and Key Event Relationships")


# ## Step #5C - Identifier mapping for other databases
# BridgeDb was used to additional identifiers from other databases, including Entrez gene, Ensembl, and UniProt IDs. By a request call, identifiers are returned, which are stored in the dictionary called `geneiddict`. The BridgeDb service URL has already been defined in Step #3.



geneiddict = {}
listofentrez = []
listofensembl = []
listofuniprot = []

for gene in hgnclist:
    # BridgeDb gene mapping with error handling
    try:
        response = requests.get(bridgedb + 'xrefs/H/' + gene[5:], timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        a = response.text.split('\n')
    except requests.RequestException as e:
        logger.warning(f"BridgeDb gene mapping failed for HGNC {gene[5:]}: {e}")
        a = ['html']  # Set to trigger fallback behavior
    dictionaryforgene = {}
    if 'html' not in a:
        for item in a:
            b = item.split('\t')
            if len(b) == 2:
                if b[1] not in dictionaryforgene:
                    dictionaryforgene[b[1]] = []
                    dictionaryforgene[b[1]].append(b[0])
                else:
                    dictionaryforgene[b[1]].append(b[0])
    geneiddict[gene] = []
    if 'Entrez Gene' in dictionaryforgene:
        for entrez in dictionaryforgene['Entrez Gene']:
            if 'ncbigene:'+entrez not in listofentrez:
                listofentrez.append("ncbigene:"+entrez)
            geneiddict[gene].append("ncbigene:"+entrez)
    if 'Ensembl' in dictionaryforgene:
        for ensembl in dictionaryforgene['Ensembl']:
            if 'ensembl:' + ensembl not in listofensembl:
                listofensembl.append("ensembl:"+ensembl)
            geneiddict[gene].append("ensembl:"+ensembl)
    if 'Uniprot-TrEMBL' in dictionaryforgene:
        for uniprot in dictionaryforgene['Uniprot-TrEMBL']:
            if 'uniprot:'+uniprot not in listofuniprot:
                listofuniprot.append("uniprot:"+uniprot)
            geneiddict[gene].append("uniprot:"+uniprot)
logger.info(f"Gene identifiers mapped: {len(listofentrez)} Entrez, {len(listofuniprot)} UniProt, {len(listofensembl)} Ensembl IDs")


# ## Step #5D - Writing output file
# The final step involves the writing of the RDF file in Turtle syntax. After writing the prefixes used for predicates and identifier types, all gene mapping links stored in the kedict and kerdict are written, followed by the HGNC IDs and matched IDs for other databases.



# Open genes RDF output file with proper error handling
genes_rdf_filename = filepath + 'AOPWikiRDF-Genes.ttl'
logger.info(f"Writing genes RDF file: {genes_rdf_filename}")

try:
    genes_rdf_file = open(genes_rdf_filename, 'w', encoding='utf-8')
    g = genes_rdf_file  # Keep existing variable name for compatibility
except IOError as e:
    logger.error(f"Failed to open genes RDF output file: {e}")
    raise SystemExit(1)

# ### Writing prefixes



g.write('@prefix dc: <http://purl.org/dc/elements/1.1/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix aop.events: <https://identifiers.org/aop.events/> .\n@prefix aop.relationships: <https://identifiers.org/aop.relationships/> .\n@prefix skos: <http://www.w3.org/2004/02/skos/core#> . \n@prefix ensembl: <https://identifiers.org/ensembl/> .\n@prefix edam: <http://edamontology.org/> .\n@prefix hgnc: <https://identifiers.org/hgnc/>.\n@prefix ncbigene: <https://identifiers.org/ncbigene/>.\n@prefix uniprot: <https://identifiers.org/uniprot/>.\n@prefix owl: <http://www.w3.org/2002/07/owl#>.\n\n')


# ### Writing Key Event triples
# These triples only contain the mappings with genes.



n = 0
for ke in kedict:
    if 'edam:data_1025' in kedict[ke]:
        n += 1
        g.write(kedict[ke]['dc:identifier']+'\tedam:data_1025\t' + ','.join(kedict[ke]['edam:data_1025'])+' .\n\n')
logger.info(f"Key Event gene mapping output: {n} events with mapped genes")


# ### Writing Key Event Relationship triples
# These triples only contain the mappings with genes.



n = 0
for ker in kerdict:
    if 'edam:data_1025' in kerdict[ker]:
        n += 1
        g.write(kerdict[ker]['dc:identifier']+'\tedam:data_1025\t' + ','.join(kerdict[ker]['edam:data_1025'])+' .\n\n')
logger.info(f"Key Event Relationship gene mapping output: {n} relationships with mapped genes")


# ### Writing Gene identifier triples



for hgnc in hgnclist:
    g.write(hgnc + '\ta\tedam:data_2298, edam:data_1025 ;\n\tedam:data_2298\t"'+hgnc[5:]+'";\n\tdc:identifier\t"'+hgnc+'";\n\tdc:source\t"HGNC"')
    if not geneiddict[hgnc] == []:
        g.write(' ;\n\tskos:exactMatch\t'+','.join(geneiddict[hgnc]))
    g.write('.\n\n')
logger.info(f"{len(hgnclist)} HGNC triples written")
for entrez in listofentrez:
    g.write(entrez + '\ta\tedam:data_1027, edam:data_1025 ;\n\tedam:data_1027\t"'+entrez[9:]+'";\n\tdc:identifier\t"'+entrez+'";\n\tdc:source\t"Entrez Gene".\n\n')
logger.info(f"{len(listofentrez)} Entrez gene triples written")
for ensembl in listofensembl:
    g.write(ensembl + '\ta\tedam:data_1033, edam:data_1025 ;\n\tedam:data_1033\t"'+ensembl[8:]+'";\n\tdc:identifier\t"'+ensembl+'";\n\tdc:source\t"Ensembl".\n\n')
logger.info(f"{len(listofensembl)} Ensembl triples written")
for uniprot in listofuniprot:
    g.write(uniprot + '\ta\tedam:data_2291, edam:data_1025 ;\n\tedam:data_2291\t"'+uniprot[8:]+'";\n\tdc:identifier\t"'+uniprot+'";\n\tdc:source\t"UniProt".\n\n')
logger.info(f"{len(listofuniprot)} UniProt triples written")


# Close the file.



genes_rdf_file.close()
logger.info("AOP-Wiki RDF Genes file created successfully")


# ## <b>Step #6: Creating the VoID file</b>
# The last file contains the metadata of the original data, script, and tools used for the creation of the AOP-Wiki RDF files. 



# BridgeDb properties request with error handling
try:
    response = requests.get(bridgedb + 'properties', timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    a = response.text.split('\n')
except requests.RequestException as e:
    logger.warning(f"BridgeDb properties request failed: {e}")
    a = []  # Empty list to prevent processing
info = {}
for item in a:
    if not item.split('\t')[0] in info:
        info[item.split('\t')[0]] = []
    if len(item.split('\t')) == 2:
        info[item.split('\t')[0]].append(item.split('\t')[1])
logger.info(f"BridgeDb mapping files version - Gene/Proteins: {info['DATASOURCENAME'][0]}:{info['DATASOURCEVERSION'][0]}, Chemicals: {info['DATASOURCENAME'][5]}:{info['DATASOURCEVERSION'][5]}")




x = datetime.datetime.now()
logger.info(f"VoID file generation date: {x}")
y = str(x)
y = y[:10]




# Open VoID RDF output file with proper error handling
void_rdf_filename = filepath + 'AOPWikiRDF-Void.ttl'
logger.info(f"Writing VoID RDF file: {void_rdf_filename}")

try:
    void_rdf_file = open(void_rdf_filename, 'w', encoding='utf-8')
    g = void_rdf_file  # Keep existing variable name for compatibility
except IOError as e:
    logger.error(f"Failed to open VoID RDF output file: {e}")
    raise SystemExit(1)
g.write('@prefix : <https://aopwiki.rdf.bigcat-bioinformatics.org/> .\n@prefix dc: <http://purl.org/dc/elements/1.1/> .\n@prefix dcterms: <http://purl.org/dc/terms/> .\n@prefix void:  <http://rdfs.org/ns/void#> .\n@prefix pav:   <http://purl.org/pav/> .\n@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix dcat:  <http://www.w3.org/ns/dcat#> .\n@prefix foaf:  <http://xmlns.com/foaf/0.1/> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n@prefix freq:  <http://purl.org/cld/freq/> .')
g.write('\n:AOPWikiRDF.ttl\ta\tvoid:Dataset ;\n\tdc:description\t"AOP-Wiki RDF data from the AOP-Wiki database" ;\n\tpav:createdOn\t"' + y + '"^^xsd:date;\n\tdcterms:modified\t"' + y +'"^^xsd:date ;\n\tpav:createdWith\t"' + str(aopwikixmlfilename) + '", :Promapping ;\n\tpav:createdBy\t<https://zenodo.org/badge/latestdoi/146466058> ;\n\tfoaf:homepage\t<https://aopwiki.org> ;\n\tdcterms:accuralPeriodicity  freq:quarterly ;\n\tdcat:downloadURL\t<https://aopwiki.org/downloads/' + str(aopwikixmlfilename) + '> .\n\n:AOPWikiRDF-Genes.ttl\ta\tvoid:Dataset ;\n\tdc:description\t"AOP-Wiki RDF extension with gene mappings based on approved names and symbols" ;\n\tpav:createdOn\t"' + str(x) + '" ;\n\tpav:createdWith\t"' + str(aopwikixmlfilename) + '", :HGNCgenes ;\n\tpav:createdBy\t<https://zenodo.org/badge/latestdoi/146466058> ;\n\tdcterms:accuralPeriodicity  freq:quarterly ;\n\tfoaf:homepage\t<https://aopwiki.org> ;\n\tdcat:downloadURL\t<https://aopwiki.org/downloads/' + str(aopwikixmlfilename) + '>, <https://www.genenames.org/download/custom/> . \n\n:HGNCgenes.txt\ta\tvoid:Dataset, void:Linkset ;\n\tdc:description\t"HGNC approved symbols and names for genes" ;\n\tdcat:downloadURL\t<https://www.genenames.org/download/custom/> ;\n\tpav:importedOn\t"'+HGNCmodificationTime+'" .\n\n<https://proconsortium.org/download/current/promapping.txt>\ta\tvoid:Dataset, void:Linkset;\n\tdc:description\t"PRotein ontology mappings to protein database identifiers";\n\tdcat:downloadURL\t<https://proconsortium.org/download/current/promapping.txt>;\n\tpav:importedOn\t"'+PromodificationTime+'".')
void_rdf_file.close()
logger.info("VoID file created successfully")

