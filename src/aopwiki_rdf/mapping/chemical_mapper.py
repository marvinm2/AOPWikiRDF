"""Chemical mapper module.

Enriches chemical data with BridgeDb cross-references by batch-mapping
CAS numbers to ChEBI, ChemSpider, PubChem, DrugBank, HMDB, KEGG,
LIPID MAPS, ChEMBL, and Wikidata identifiers.

Extracted from AOP-Wiki_XML_to_RDF_conversion.py chemical mapping section.
"""

import logging

import requests

logger = logging.getLogger(__name__)


# --- BridgeDb batch chemical mapping ---

def _map_chemicals_batch(cas_numbers, batch_size=100, bridgedb_url=None, timeout=30):
    """Map multiple CAS numbers to chemical identifiers using BridgeDb batch API.

    Args:
        cas_numbers: List of CAS numbers to map.
        batch_size: Number of chemicals per batch request (default 100).
        bridgedb_url: BridgeDb service URL.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary mapping CAS numbers to their identifier dictionaries.
    """
    if bridgedb_url is None:
        bridgedb_url = 'https://webservice.bridgedb.org/Human/'

    batch_url = bridgedb_url.rstrip('/') + '/xrefsBatch/Ca'
    results = {}

    logger.info(f'Starting batch chemical mapping for {len(cas_numbers)} chemicals')

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

            batch_results = _parse_batch_chemical_response(response.text)
            results.update(batch_results)

        except requests.RequestException as e:
            logger.warning(f"Batch chemical mapping failed for batch {batch_num}: {e}")
            for cas in batch:
                try:
                    individual_result = _map_chemical_individual_fallback(cas, bridgedb_url, timeout)
                    if individual_result:
                        results[cas] = individual_result
                except Exception as individual_error:
                    logger.warning(f"Individual chemical mapping fallback failed for {cas}: {individual_error}")
                    results[cas] = {}

    logger.info(f'Completed batch chemical mapping: {len(results)} chemicals processed')
    return results


def _parse_batch_chemical_response(response_text):
    """Parse BridgeDb batch chemical response into structured format.

    Response format: ``CAS_NUMBER\\tCAS\\tCs:id,Ch:id,Dr:id,Ce:id,...``
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
            elif system_code in ('Gpl', 'Ik', 'Kl', 'Lb', 'Pgd', 'Cps', 'Sl', 'Td', 'Wi'):
                pass  # Not mapped in original
            elif system_code == 'Ck':  # KEGG Compound
                if 'cheminf:000409' not in chemical_dict:
                    chemical_dict['cheminf:000409'] = []
                chemical_dict['cheminf:000409'].append(f"kegg.compound:{identifier}")
            elif system_code == 'Kd':  # KEGG Drug
                if 'cheminf:000409' not in chemical_dict:
                    chemical_dict['cheminf:000409'] = []
                chemical_dict['cheminf:000409'].append(f"kegg.compound:{identifier}")
            elif system_code == 'Lm':  # LIPID MAPS
                if 'cheminf:000564' not in chemical_dict:
                    chemical_dict['cheminf:000564'] = []
                chemical_dict['cheminf:000564'].append(f"lipidmaps:{identifier}")
            elif system_code == 'Cpc':  # PubChem Compound
                if 'cheminf:000140' not in chemical_dict:
                    chemical_dict['cheminf:000140'] = []
                chemical_dict['cheminf:000140'].append(f"pubchem.compound:{identifier}")
            elif system_code == 'Wd':  # Wikidata
                if 'cheminf:000567' not in chemical_dict:
                    chemical_dict['cheminf:000567'] = []
                chemical_dict['cheminf:000567'].append(f"wikidata:{identifier}")

        results[cas_number] = chemical_dict

    return results


def _map_chemical_individual_fallback(cas_number, bridgedb_url, timeout):
    """Fall back to individual chemical mapping (original approach)."""
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


# --- Database key to list-name mapping ---

_DB_KEY_TO_LIST = {
    'cheminf:000407': 'listofchebi',
    'cheminf:000405': 'listofchemspider',
    'cheminf:000567': 'listofwikidata',
    'cheminf:000412': 'listofchembl',
    'cheminf:000140': 'listofpubchem',
    'cheminf:000406': 'listofdrugbank',
    'cheminf:000409': 'listofkegg',
    'cheminf:000564': 'listoflipidmaps',
    'cheminf:000408': 'listofhmdb',
}


# --- Public API ---

def map_chemicals(chedict, xml_root, aopxml_ns,
                  bridgedb_url, timeout=30):
    """Enrich chemical dict with BridgeDb cross-references.

    Iterates over ``<chemical>`` elements in *xml_root* to extract CAS numbers,
    calls BridgeDb batch API, and populates *chedict* entries with cheminf
    cross-reference properties.

    Args:
        chedict: Chemical dict from XML parser (keyed by chemical ID).
        xml_root: ElementTree root for iterating chemicals.
        aopxml_ns: XML namespace string (e.g. ``'{http://...}'``).
        bridgedb_url: BridgeDb service URL.
        timeout: Request timeout in seconds.

    Returns:
        dict with keys:
            ``'chedict'``: Enriched chemical dict with cross-reference properties.
            ``'listofchebi'``, ``'listofchemspider'``, ``'listofchembl'``,
            ``'listofdrugbank'``, ``'listofhmdb'``, ``'listofkegg'``,
            ``'listoflipidmaps'``, ``'listofpubchem'``, ``'listofwikidata'``:
            Deduplicated identifier lists.
    """
    # Initialize result lists
    result_lists = {name: [] for name in _DB_KEY_TO_LIST.values()}

    # Collect CAS numbers from chedict entries
    chemicals_to_map = []
    cas_to_chemical_id = {}

    for chem_id, chem_data in chedict.items():
        cas_prop = chem_data.get('cheminf:000446')
        if cas_prop is not None:
            # CAS stored as '"80-05-7"' -- strip quotes
            cas_number = cas_prop.strip('"')
            chemicals_to_map.append((chem_id, cas_number))
            if cas_number not in cas_to_chemical_id:
                cas_to_chemical_id[cas_number] = []
            cas_to_chemical_id[cas_number].append(chem_id)

    if not chemicals_to_map:
        logger.info("No chemicals with CAS numbers to map")
        return {'chedict': chedict, **result_lists}

    # Batch BridgeDb mapping
    logger.info(f"Starting batch chemical mapping for {len(chemicals_to_map)} chemicals with CAS numbers")
    cas_numbers_list = [cas for _, cas in chemicals_to_map]
    batch_results = _map_chemicals_batch(
        cas_numbers_list, bridgedb_url=bridgedb_url, timeout=timeout
    )

    # Apply batch results to chedict entries
    for cas_number, chemical_mappings in batch_results.items():
        if cas_number not in cas_to_chemical_id:
            continue
        for chemical_id in cas_to_chemical_id[cas_number]:
            for db_key, identifiers in chemical_mappings.items():
                if not identifiers:
                    continue
                chedict[chemical_id][db_key] = identifiers.copy()

                list_name = _DB_KEY_TO_LIST.get(db_key)
                if list_name is not None:
                    for identifier in identifiers:
                        if identifier not in result_lists[list_name]:
                            result_lists[list_name].append(identifier)

    return {'chedict': chedict, **result_lists}
