"""AOP-Wiki XML parser module.

Extracted from AOP-Wiki_XML_to_RDF_conversion.py (lines 347-1201).
Parses AOP-Wiki XML into typed entity dictionaries.

No module-level side effects. No logging.basicConfig(). No network calls at import.
"""

import logging
import os
import re
import stat
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from xml.etree.ElementTree import parse

import requests

from aopwiki_rdf.config import PipelineConfig
from aopwiki_rdf.utils import clean_html_tags, validate_entity_counts, validate_required_fields, validate_xml_structure

logger = logging.getLogger(__name__)

# --- Constants ---
AOPXML_NS = '{http://www.aopkb.org/aop-xml}'
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')


@dataclass
class ParsedEntities:
    """Container for all entity dictionaries extracted from AOP-Wiki XML."""
    refs: Dict[str, Dict[str, str]]
    aopdict: Dict[str, dict]
    kedict: Dict[str, dict]
    kerdict: Dict[str, dict]
    stressordict: Dict[str, dict]
    chemicaldict: Dict[str, dict]
    taxdict: Dict[str, dict]
    celldict: Dict[str, dict]
    organdict: Dict[str, dict]
    bpdict: Dict[str, dict]
    bodict: Dict[str, dict]
    badict: Dict[str, dict]
    prodict: Dict[str, list]


# --- Chemical mapping functions (tightly coupled to parsing) ---

def map_chemicals_batch(cas_numbers, batch_size=100, bridgedb_url=None, timeout=30):
    """
    Map multiple CAS numbers to chemical identifiers using BridgeDb batch API.

    Args:
        cas_numbers: List of CAS numbers to map
        batch_size: Number of chemicals per batch request (default 100)
        bridgedb_url: BridgeDb service URL
        timeout: Request timeout in seconds

    Returns:
        Dictionary mapping CAS numbers to their identifier dictionaries
    """
    if bridgedb_url is None:
        bridgedb_url = 'https://webservice.bridgedb.org/Human/'

    batch_url = bridgedb_url.rstrip('/') + '/xrefsBatch/Ca'
    results = {}

    logger.info(f'Starting batch chemical mapping for {len(cas_numbers)} chemicals')

    # Process in batches
    for i in range(0, len(cas_numbers), batch_size):
        batch = cas_numbers[i:i + batch_size]
        batch_data = '\n'.join(batch)

        batch_num = i // batch_size + 1
        total_batches = (len(cas_numbers) + batch_size - 1) // batch_size
        logger.info(f"Processing chemical batch {batch_num}/{total_batches} ({len(batch)} chemicals)")

        try:
            response = requests.post(
                batch_url,
                data=batch_data,
                headers={'Content-Type': 'text/plain'},
                timeout=timeout
            )
            response.raise_for_status()

            # Parse batch response
            batch_results = parse_batch_chemical_response(response.text)
            results.update(batch_results)

        except requests.RequestException as e:
            logger.warning(f"Batch chemical mapping failed for batch {batch_num}: {e}")
            # Fall back to individual requests for this batch
            for cas in batch:
                try:
                    individual_result = map_chemical_individual_fallback(cas, bridgedb_url, timeout)
                    if individual_result:
                        results[cas] = individual_result
                except Exception as individual_error:
                    logger.warning(f"Individual chemical mapping fallback failed for {cas}: {individual_error}")
                    results[cas] = {}

    logger.info(f'Completed batch chemical mapping: {len(results)} chemicals processed')
    return results


def parse_batch_chemical_response(response_text):
    """
    Parse BridgeDb batch chemical response into structured format.
    Response format: "CAS_NUMBER\\tCAS\\tCs:id,Ch:id,Dr:id,Ce:id,..."
    """
    results = {}

    for line in response_text.strip().split('\n'):
        if not line.strip():
            continue

        parts = line.split('\t')
        if len(parts) < 3:
            continue

        cas_number = parts[0]
        xrefs_str = parts[2]

        if xrefs_str == 'N/A':
            results[cas_number] = {}
            continue

        # Parse system codes
        chemical_dict = {}
        xrefs = xrefs_str.split(',')

        for xref in xrefs:
            if ':' not in xref:
                continue

            system_code, identifier = xref.split(':', 1)

            if system_code == 'Ca':  # CAS
                pass
            elif system_code == 'Ce':  # ChEBI
                if 'cheminf:000407' not in chemical_dict:
                    chemical_dict['cheminf:000407'] = []
                formatted_chebi = f"chebi:{identifier.split('CHEBI:')[-1]}"
                chemical_dict['cheminf:000407'].append(formatted_chebi)
            elif system_code == 'Cs':  # ChemSpider
                if 'cheminf:000405' not in chemical_dict:
                    chemical_dict['cheminf:000405'] = []
                chemical_dict['cheminf:000405'].append(f"chemspider:{identifier}")
            elif system_code == 'Cl':  # ChEMBL compound
                if 'cheminf:000412' not in chemical_dict:
                    chemical_dict['cheminf:000412'] = []
                chemical_dict['cheminf:000412'].append(f"chembl.compound:{identifier}")
            elif system_code == 'Dr':  # DrugBank
                if 'cheminf:000406' not in chemical_dict:
                    chemical_dict['cheminf:000406'] = []
                chemical_dict['cheminf:000406'].append(f"drugbank:{identifier}")
            elif system_code == 'Ch':  # HMDB
                if 'cheminf:000408' not in chemical_dict:
                    chemical_dict['cheminf:000408'] = []
                chemical_dict['cheminf:000408'].append(f"hmdb:{identifier}")
            elif system_code == 'Gpl':  # Guide to Pharmacology Ligand ID
                pass
            elif system_code == 'Ik':  # InChIKey
                pass
            elif system_code == 'Ck':  # KEGG Compound
                if 'cheminf:000409' not in chemical_dict:
                    chemical_dict['cheminf:000409'] = []
                chemical_dict['cheminf:000409'].append(f"kegg.compound:{identifier}")
            elif system_code == 'Kd':  # KEGG Drug
                if 'cheminf:000409' not in chemical_dict:
                    chemical_dict['cheminf:000409'] = []
                chemical_dict['cheminf:000409'].append(f"kegg.compound:{identifier}")
            elif system_code == 'Kl':  # KEGG Glycan
                pass
            elif system_code == 'Lm':  # LIPID MAPS
                if 'cheminf:000564' not in chemical_dict:
                    chemical_dict['cheminf:000564'] = []
                chemical_dict['cheminf:000564'].append(f"lipidmaps:{identifier}")
            elif system_code == 'Lb':  # LipidBank
                pass
            elif system_code == 'Pgd':  # PharmGKB Drug
                pass
            elif system_code == 'Cpc':  # PubChem Compound
                if 'cheminf:000140' not in chemical_dict:
                    chemical_dict['cheminf:000140'] = []
                chemical_dict['cheminf:000140'].append(f"pubchem.compound:{identifier}")
            elif system_code == 'Cps':  # PubChem Substance
                pass
            elif system_code == 'Sl':  # SwissLipids
                pass
            elif system_code == 'Td':  # TTD Drug
                pass
            elif system_code == 'Wd':  # Wikidata
                if 'cheminf:000567' not in chemical_dict:
                    chemical_dict['cheminf:000567'] = []
                chemical_dict['cheminf:000567'].append(f"wikidata:{identifier}")
            elif system_code == 'Wi':  # Wikipedia
                pass

        results[cas_number] = chemical_dict

    return results


def map_chemical_individual_fallback(cas_number, bridgedb_url, timeout):
    """
    Fall back to individual chemical mapping (original approach).
    """
    individual_url = bridgedb_url.rstrip('/') + f'/xrefs/Ca/{cas_number}'

    try:
        response = requests.get(individual_url, timeout=timeout)
        response.raise_for_status()

        chemical_dict = {}
        for line in response.text.split('\n'):
            if not line.strip():
                continue

            parts = line.split('\t')
            if len(parts) == 2:
                identifier, database = parts

                if database == 'Chemspider':
                    if 'cheminf:000405' not in chemical_dict:
                        chemical_dict['cheminf:000405'] = []
                    chemical_dict['cheminf:000405'].append(f"chemspider:{identifier}")
                elif database == 'HMDB':
                    if 'cheminf:000408' not in chemical_dict:
                        chemical_dict['cheminf:000408'] = []
                    chemical_dict['cheminf:000408'].append(f"hmdb:{identifier}")
                elif database == 'DrugBank':
                    if 'cheminf:000406' not in chemical_dict:
                        chemical_dict['cheminf:000406'] = []
                    chemical_dict['cheminf:000406'].append(f"drugbank:{identifier}")
                elif database == 'ChEBI':
                    if 'cheminf:000407' not in chemical_dict:
                        chemical_dict['cheminf:000407'] = []
                    formatted_chebi = f"chebi:{identifier.split('CHEBI:')[-1]}"
                    chemical_dict['cheminf:000407'].append(formatted_chebi)
                elif database == 'ChEMBL compound':
                    if 'cheminf:000412' not in chemical_dict:
                        chemical_dict['cheminf:000412'] = []
                    chemical_dict['cheminf:000412'].append(f"chembl.compound:{identifier}")
                elif database == 'Wikidata':
                    if 'cheminf:000567' not in chemical_dict:
                        chemical_dict['cheminf:000567'] = []
                    chemical_dict['cheminf:000567'].append(f"wikidata:{identifier}")
                elif database == 'PubChem-compound':
                    if 'cheminf:000140' not in chemical_dict:
                        chemical_dict['cheminf:000140'] = []
                    chemical_dict['cheminf:000140'].append(f"pubchem.compound:{identifier}")
                elif database == 'KEGG Compound':
                    if 'cheminf:000409' not in chemical_dict:
                        chemical_dict['cheminf:000409'] = []
                    chemical_dict['cheminf:000409'].append(f"kegg.compound:{identifier}")
                elif database == 'LIPID MAPS':
                    if 'cheminf:000564' not in chemical_dict:
                        chemical_dict['cheminf:000564'] = []
                    chemical_dict['cheminf:000564'].append(f"lipidmaps:{identifier}")

        return chemical_dict

    except requests.RequestException as e:
        logger.warning(f"Individual chemical mapping failed for {cas_number}: {e}")
        return {}


# --- Main parser function ---

def parse_aopwiki_xml(xml_path: str, config: PipelineConfig = None) -> ParsedEntities:
    """Parse AOP-Wiki XML file and return all entity dictionaries.

    Args:
        xml_path: Path to the AOP-Wiki XML file.
        config: Optional PipelineConfig for network-dependent operations
                (BridgeDb chemical mapping, promapping.txt download).
                If None, chemical BridgeDb mapping and protein mapping are skipped.

    Returns:
        ParsedEntities dataclass with all 13 entity dictionaries.
    """
    aopxml = AOPXML_NS

    # Resolve config values
    if config is not None:
        bridgedb_url = config.bridgedb_url
        request_timeout = config.request_timeout
        max_retries = config.max_retries
        promapping_url = config.promapping_url
        filepath = str(config.data_dir) + '/'
    else:
        bridgedb_url = None
        request_timeout = 30
        max_retries = 3
        promapping_url = None
        filepath = None

    # Parse XML
    tree = parse(xml_path)
    root = tree.getroot()

    # Validate XML structure
    try:
        validate_xml_structure(root, aopxml)
    except ValueError as e:
        logger.error(f"XML structure validation failed: {e}")
        raise

    # ---------------------------------------------------------------
    # Reference extraction (monolith lines 354-365)
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # AOP extraction (monolith lines 374-464)
    # ---------------------------------------------------------------
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
            if AOP.find(aopxml + 'background').text is not None:
                aopdict[AOP.get('id')]['dc:description'].append('"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'background').text) + '"""')
        if AOP.find(aopxml + 'authors').text is not None:
            aopdict[AOP.get('id')]['dc:creator'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'authors').text) + '"""'
        if AOP.find(aopxml + 'abstract').text is not None:
            aopdict[AOP.get('id')]['dcterms:abstract'] = '"""' + HTML_TAG_PATTERN.sub('', AOP.find(aopxml + 'abstract').text) + '"""'
        if AOP.find(aopxml + 'status').find(aopxml + 'wiki-status') is not None:
            aopdict[AOP.get('id')]['dcterms:accessRights'] = '"' + AOP.find(aopxml + 'status').find(aopxml + 'wiki-status').text + '"'
        if AOP.find(aopxml + 'status').find(aopxml + 'oecd-status') is not None:
            aopdict[AOP.get('id')]['oecd-status'] = '"' + AOP.find(aopxml + 'status').find(aopxml + 'oecd-status').text + '"'
        if AOP.find(aopxml + 'status').find(aopxml + 'saaop-status') is not None:
            aopdict[AOP.get('id')]['saaop-status'] = '"' + AOP.find(aopxml + 'status').find(aopxml + 'saaop-status').text + '"'
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

    # ---------------------------------------------------------------
    # Chemical extraction (monolith lines 474-823)
    # ---------------------------------------------------------------
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

    # First pass: collect all chemical information and CAS numbers for batch processing
    chemicals_to_map = []
    cas_to_chemical_id = {}

    for che in root.findall(aopxml + 'chemical'):
        chedict[che.get('id')] = {}
        if che.find(aopxml + 'casrn') is not None:
            if 'NOCAS' not in che.find(aopxml + 'casrn').text:
                cas_number = che.find(aopxml + 'casrn').text
                chedict[che.get('id')]['dc:identifier'] = 'cas:' + cas_number
                listofcas.append('cas:' + cas_number)
                chedict[che.get('id')]['cheminf:000446'] = '"' + cas_number + '"'

                # Collect for batch processing
                chemicals_to_map.append((che.get('id'), cas_number))
                if cas_number not in cas_to_chemical_id:
                    cas_to_chemical_id[cas_number] = []
                cas_to_chemical_id[cas_number].append(che.get('id'))
            else:
                chedict[che.get('id')]['dc:identifier'] = '"' + che.find(aopxml + 'casrn').text + '"'

    # Batch BridgeDb chemical mapping (only when config is provided)
    if chemicals_to_map and bridgedb_url is not None:
        logger.info(f"Starting batch chemical mapping for {len(chemicals_to_map)} chemicals with CAS numbers")
        cas_numbers_list = [cas for _, cas in chemicals_to_map]
        batch_results = map_chemicals_batch(cas_numbers_list, bridgedb_url=bridgedb_url, timeout=request_timeout)

        # Apply batch results to chemical dictionaries
        for cas_number, chemical_mappings in batch_results.items():
            if cas_number in cas_to_chemical_id:
                for chemical_id in cas_to_chemical_id[cas_number]:
                    for db_key, identifiers in chemical_mappings.items():
                        if identifiers:
                            chedict[chemical_id][db_key] = identifiers.copy()

                            for identifier in identifiers:
                                if db_key == 'cheminf:000407' and identifier not in listofchebi:
                                    listofchebi.append(identifier)
                                elif db_key == 'cheminf:000405' and identifier not in listofchemspider:
                                    listofchemspider.append(identifier)
                                elif db_key == 'cheminf:000567' and identifier not in listofwikidata:
                                    listofwikidata.append(identifier)
                                elif db_key == 'cheminf:000412' and identifier not in listofchembl:
                                    listofchembl.append(identifier)
                                elif db_key == 'cheminf:000140' and identifier not in listofpubchem:
                                    listofpubchem.append(identifier)
                                elif db_key == 'cheminf:000406' and identifier not in listofdrugbank:
                                    listofdrugbank.append(identifier)
                                elif db_key == 'cheminf:000409' and identifier not in listofkegg:
                                    listofkegg.append(identifier)
                                elif db_key == 'cheminf:000564' and identifier not in listoflipidmaps:
                                    listoflipidmaps.append(identifier)
                                elif db_key == 'cheminf:000408' and identifier not in listofhmdb:
                                    listofhmdb.append(identifier)

    # Continue with other chemical properties (InChI keys, names, etc.)
    for che in root.findall(aopxml + 'chemical'):
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

    # ---------------------------------------------------------------
    # Stressor extraction (monolith lines 826-847)
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # Taxonomy extraction (monolith lines 850-865)
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # AOP Taxonomy second pass (monolith lines 868-880)
    # ---------------------------------------------------------------
    for AOP in root.findall(aopxml + 'aop'):
        for appl in AOP.findall(aopxml + 'applicability'):
            for tax in appl.findall(aopxml + 'taxonomy'):
                if 'ncbitaxon:131567' not in aopdict[AOP.get('id')]:
                    if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
                        aopdict[AOP.get('id')]['ncbitaxon:131567'] = [[tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']]]
                else:
                    if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
                        aopdict[AOP.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']])
    logger.info(f'AOP taxonomy second pass completed')

    # ---------------------------------------------------------------
    # KE components: biological actions (monolith lines 883-897)
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # KE components: biological processes (monolith lines 902-949)
    # ---------------------------------------------------------------
    bioprodict = {
        None: {
            'dc:identifier': None,
            'dc:source': None,
            'dc:title': None
        }
    }

    source_prefix_map_bp = {
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

    for biopro in root.findall(aopxml + 'biological-process'):
        biopro_id = biopro.get('id')
        bioprodict[biopro_id] = {}

        source = f'"{biopro.find(aopxml + "source").text}"'
        name = f'"{biopro.find(aopxml + "name").text}"'
        source_id = biopro.find(aopxml + 'source-id').text

        bioprodict[biopro_id]['dc:source'] = source
        bioprodict[biopro_id]['dc:title'] = name

        if source in source_prefix_map_bp:
            prefix, offset = source_prefix_map_bp[source]
            identifier = prefix + source_id[offset:]
            bioprodict[biopro_id]['dc:identifier'] = identifier
        else:
            bioprodict[biopro_id]['dc:identifier'] = source_id

    logger.info(f'Biological Process parsing completed: {len(bioprodict)} annotations processed')

    # ---------------------------------------------------------------
    # KE components: biological objects (monolith lines 954-1005)
    # ---------------------------------------------------------------
    bioobjdict = {
        None: {
            'dc:identifier': None,
            'dc:source': None,
            'dc:title': None
        }
    }
    objectstoskip = []
    prolist = []

    source_prefix_map_bo = {
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

    for bioobj in root.findall(aopxml + 'biological-object'):
        bioobj_id = bioobj.get('id')
        bioobjdict[bioobj_id] = {}

        source = f'"{bioobj.find(aopxml + "source").text}"'
        name = f'"{bioobj.find(aopxml + "name").text}"'
        source_id = bioobj.find(aopxml + 'source-id').text

        bioobjdict[bioobj_id]['dc:source'] = source
        bioobjdict[bioobj_id]['dc:title'] = name

        if source in source_prefix_map_bo:
            prefix, offset = source_prefix_map_bo[source]
            identifier = prefix + source_id[offset:]
            bioobjdict[bioobj_id]['dc:identifier'] = identifier

            if source == '"PR"':
                prolist.append(identifier)
        else:
            bioobjdict[bioobj_id]['dc:identifier'] = f'"{source_id}"'

    logger.info(f'Biological Object parsing completed: {len(bioobjdict)} annotations processed')

    # ---------------------------------------------------------------
    # Protein ontology mapping (monolith lines 1008-1063)
    # ---------------------------------------------------------------
    prodict = {}
    hgnclist = []
    uniprotlist = []
    ncbigenelist = []

    if prolist and promapping_url is not None and filepath is not None:
        pro = "promapping.txt"
        try:
            logger.info("Downloading protein mapping file")
            urllib.request.urlretrieve(promapping_url, filepath + pro)
            logger.info(f"Successfully downloaded {pro}")
        except Exception as e:
            logger.error(f"Failed to download protein mapping file: {e}")
            # Don't raise -- continue without protein mapping
            prolist = []

        if prolist:
            try:
                fileStatsObj = os.stat(filepath + pro)
                PromodificationTime = time.ctime(fileStatsObj[stat.ST_MTIME])
                logger.info(f"Protein mapping file last modified: {PromodificationTime}")
            except OSError as e:
                logger.error(f"Could not get file stats for {pro}: {e}")

            try:
                f = open(filepath + pro, "r", encoding='utf-8')
            except IOError as e:
                logger.error(f"Failed to open promapping file {filepath + pro}: {e}")
                f = None

            if f is not None:
                for line in f:
                    a = line.split('\t')
                    key = 'pr:' + a[0][3:]
                    if key in prolist:
                        if key not in prodict:
                            prodict[key] = []
                        if 'HGNC:' in a[1]:
                            prodict[key].append('hgnc:' + a[1][5:])
                            hgnclist.append('hgnc:' + a[1][5:])
                        if 'NCBIGene:' in a[1]:
                            prodict[key].append('ncbigene:' + a[1][9:])
                            ncbigenelist.append('ncbigene:' + a[1][9:])
                        if 'UniProtKB:' in a[1]:
                            prodict[key].append('uniprot:' + a[1].split(',')[0][10:])
                            uniprotlist.append('uniprot:' + a[1].split(',')[0][10:])
                        if prodict[key] == []:
                            del prodict[key]
                f.close()
            logger.info(f'Protein mapping completed: added {len(hgnclist) + len(ncbigenelist) + len(uniprotlist)} identifiers for {len(prodict)} Protein Ontology terms')

    # ---------------------------------------------------------------
    # Key Event extraction (monolith lines 1067-1152)
    # ---------------------------------------------------------------
    celldict = {}
    organdict = {}
    listofkedescriptions = []
    for ke in root.findall(aopxml + 'key-event'):
        if ke.get('id') not in kedict:
            kedict[ke.get('id')] = {}
        kedict[ke.get('id')]['dc:identifier'] = 'aop.events:' + refs['KE'][ke.get('id')]
        kedict[ke.get('id')]['rdfs:label'] = '"KE ' + refs['KE'][ke.get('id')] + '"'
        kedict[ke.get('id')]['foaf:page'] = '<https://identifiers.org/aop.events/' + refs['KE'][ke.get('id')] + '>'
        kedict[ke.get('id')]['dc:title'] = '"' + ke.find(aopxml + 'title').text + '"'
        kedict[ke.get('id')]['dcterms:alternative'] = ke.find(aopxml + 'short-name').text
        kedict[ke.get('id')]['nci:C25664'] = '"""' + ke.find(aopxml + 'biological-organization-level').text + '"""'
        if ke.find(aopxml + 'description').text is not None:
            kedict[ke.get('id')]['dc:description'] = '"""' + HTML_TAG_PATTERN.sub('', ke.find(aopxml + 'description').text) + '"""'
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
            # Also store in celldict for standalone access
            celldict[ke.get('id')] = kedict[ke.get('id')]['aopo:CellTypeContext']
        if ke.find(aopxml + 'organ-term') is not None:
            kedict[ke.get('id')]['aopo:OrganContext'] = {}
            kedict[ke.get('id')]['aopo:OrganContext']['dc:source'] = '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'source').text + '"'
            kedict[ke.get('id')]['aopo:OrganContext']['dc:title'] = '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'name').text + '"'
            if kedict[ke.get('id')]['aopo:OrganContext']['dc:source'] == '"UBERON"':
                kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier'] = ['uberon:' + ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text[7:], ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text]
            else:
                kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier'] = [
                    '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text + '"', 'placeholder']
            # Also store in organdict for standalone access
            organdict[ke.get('id')] = kedict[ke.get('id')]['aopo:OrganContext']
        if ke.find(aopxml + 'key-event-stressors') is not None:
            kedict[ke.get('id')]['nci:C54571'] = {}
            for stressor in ke.find(aopxml + 'key-event-stressors').findall(aopxml + 'key-event-stressor'):
                kedict[ke.get('id')]['nci:C54571'][stressor.get('stressor-id')] = {}
                kedict[ke.get('id')]['nci:C54571'][stressor.get('stressor-id')]['dc:identifier'] = strdict[stressor.get('stressor-id')]['dc:identifier']
                kedict[ke.get('id')]['nci:C54571'][stressor.get('stressor-id')]['aopo:has_evidence'] = stressor.find(aopxml + 'evidence').text
    logger.info(f'Key Events parsing completed: {len(kedict)} events processed')

    # ---------------------------------------------------------------
    # KER extraction (monolith lines 1155-1201)
    # ---------------------------------------------------------------
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

    # ---------------------------------------------------------------
    # Return ParsedEntities
    # ---------------------------------------------------------------
    return ParsedEntities(
        refs=refs,
        aopdict=aopdict,
        kedict=kedict,
        kerdict=kerdict,
        stressordict=strdict,
        chemicaldict=chedict,
        taxdict=taxdict,
        celldict=celldict,
        organdict=organdict,
        bpdict=bioprodict,
        bodict=bioobjdict,
        badict=bioactdict,
        prodict=prodict,
    )
