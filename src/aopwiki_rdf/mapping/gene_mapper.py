"""Gene mapper module: three-stage gene mapping with BridgeDb xref resolution.

Extracts genes mentioned in Key Event and Key Event Relationship text fields
using a three-stage algorithm (screening, precision matching, false positive
filtering) and resolves cross-references via the BridgeDb batch API.

This module operates on plain dicts and lists -- no rdflib dependency.
"""

import logging
import re
import time

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section A: Gene dictionary building
# ---------------------------------------------------------------------------

def build_gene_dicts(hgnc_file_path: str) -> tuple[dict, dict, dict]:
    """Parse HGNC file into genedict1 (screening), genedict2 (precision), and symbol_lookup.

    Parameters
    ----------
    hgnc_file_path : str
        Path to the HGNCgenes.txt file.

    Returns
    -------
    tuple[dict, dict, dict]
        (genedict1, genedict2, symbol_lookup) where:
        - genedict1 maps numeric_hgnc_id -> [symbol, name, prev_symbols, aliases]
        - genedict2 maps numeric_hgnc_id -> punctuation-delimited variants
        - symbol_lookup maps numeric_hgnc_id -> approved gene symbol
    """
    try:
        hgnc_file = open(hgnc_file_path, 'r', encoding='utf-8')
    except IOError as e:
        logger.error(f"Failed to open HGNC genes file {hgnc_file_path}: {e}")
        raise SystemExit(1)

    symbols = [' ', '(', ')', '[', ']', ',', '.']
    genedict1 = {}
    genedict2 = {}
    symbol_lookup = {}

    _hgnc_id_pattern = re.compile(r'^(?:HGNC:)?(\d+)$')

    for line in hgnc_file:
        # Skip header line
        if 'HGNC ID' in line and 'Approved symbol' in line:
            continue
        a = line[:-1].split('\t')

        # Validate column 0 is a numeric HGNC ID (with or without "HGNC:" prefix)
        m = _hgnc_id_pattern.match(a[0])
        if not m:
            logger.warning(f"Skipping line with invalid HGNC ID in column 0: {a[0]!r}")
            continue
        hgnc_id = m.group(1)  # numeric ID, e.g. "569"
        gene_symbol = a[1]

        if '@' not in gene_symbol:  # gene clusters contain '@', filter them out
            symbol_lookup[hgnc_id] = gene_symbol
            genedict1[hgnc_id] = []
            genedict2[hgnc_id] = []
            genedict1[hgnc_id].append(gene_symbol)
            if not a[2] == '':
                genedict1[hgnc_id].append(a[2])
            for item in a[3:]:
                if not item == '':
                    for name in item.split(', '):
                        genedict1[hgnc_id].append(name)
            for item in genedict1[hgnc_id]:
                for s1 in symbols:
                    for s2 in symbols:
                        genedict2[hgnc_id].append((s1 + item + s2))

    hgnc_file.close()
    logger.info(f"Gene mapping setup: {len(genedict2)} genes included for mappings")
    logger.info(f"Gene mapping setup: {len(genedict1)} genes included for mappings")
    return genedict1, genedict2, symbol_lookup


# ---------------------------------------------------------------------------
# Section B: Gene mapping in entity text (three-stage algorithm)
# ---------------------------------------------------------------------------

# False-positive filter constants
SINGLE_LETTER_ALIASES = {
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
}

ROMAN_NUMERAL_PATTERN = re.compile(r'\b[IVX]+\b')


def _is_false_positive(gene_key: str, matched_alias: str,
                       matched_text_context: str) -> tuple[bool, str | None]:
    """Filter out known false positive patterns.

    Parameters
    ----------
    gene_key : str
        Gene dictionary key (numeric HGNC ID, e.g. "1100").
    matched_alias : str
        The alias text that was matched.
    matched_text_context : str
        Surrounding text context for pattern analysis.
    """
    # Filter 1: Single letter aliases (too ambiguous)
    if matched_alias.strip() in SINGLE_LETTER_ALIASES:
        return True, f"single letter alias '{matched_alias.strip()}'"

    # Filter 2: Roman numerals
    if ROMAN_NUMERAL_PATTERN.fullmatch(matched_alias.strip()):
        return True, f"Roman numeral '{matched_alias.strip()}'"

    # Filter 3: Short ambiguous symbols in parentheses or brackets
    stripped = matched_alias.strip()
    if len(stripped) <= 2 and any(char in matched_text_context for char in '()[]{}'):
        return True, f"short symbol '{stripped}' in parentheses/brackets context"

    # Filter 4: Gene-specific false positive patterns (match on alias, not key)
    if stripped == 'IV' and (
        'Complex I' in matched_text_context or '(I\u2013V)' in matched_text_context
    ):
        return True, "IV alias matching complex numbering"

    if (stripped == 'II'
            and ('(I\u2013V)' in matched_text_context
                 or 'complexes' in matched_text_context.lower())):
        return True, "alias 'II' matching complex numbering"

    return False, None


def _map_genes_in_text(text: str, genedict1: dict, hgnc_list: list,
                       genedict2: dict | None = None) -> list[str]:
    """Enhanced three-stage gene mapping algorithm with false positive filtering.

    Stage 1: Screen with genedict1 (basic gene names)
    Stage 2: Match with genedict2 (punctuation-delimited variants) with precision
    Stage 3: Apply false positive filters to eliminate problematic matches

    Parameters
    ----------
    text : str
        Text to scan for gene mentions.
    genedict1 : dict
        Screening dictionary (numeric_hgnc_id -> [symbol, name, aliases...]).
    hgnc_list : list
        Global list of found HGNC IDs (mutated in place).
    genedict2 : dict, optional
        Precision dictionary (numeric_hgnc_id -> punctuation-delimited variants).

    Returns
    -------
    list[str]
        List of found HGNC IDs (e.g., ['hgnc:1100']).
    """
    if not text or not genedict1:
        return []

    found_genes = []
    start_time = time.time()
    genes_checked = 0

    for gene_key in genedict1:
        genes_checked += 1

        # Stage 1: Screen with genedict1
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

            if genedict2 and gene_key in genedict2:
                for item in genedict2[gene_key]:
                    if item in text and hgnc_id not in found_genes:
                        # Stage 3: False positive filtering
                        match_index = text.find(item)
                        context_start = max(0, match_index - 50)
                        context_end = min(len(text), match_index + len(item) + 50)
                        context = text[context_start:context_end]

                        matched_alias = (
                            item.strip(' ()[],.') if len(item) >= 3
                            else item[1:-1] if len(item) == 3
                            else item
                        )

                        is_fp, fp_reason = _is_false_positive(
                            gene_key, matched_alias, context
                        )

                        if is_fp:
                            logger.debug(
                                f"Filtered false positive: {gene_key} "
                                f"(alias '{matched_alias}') - {fp_reason}"
                            )
                            break  # Skip this gene entirely

                        found_genes.append(hgnc_id)
                        if hgnc_id not in hgnc_list:
                            hgnc_list.append(hgnc_id)
                        break
            else:
                # Fallback to genedict1-only matching
                is_fp, fp_reason = _is_false_positive(
                    gene_key, stage1_matched_alias, text
                )

                if not is_fp and hgnc_id not in found_genes:
                    found_genes.append(hgnc_id)
                    if hgnc_id not in hgnc_list:
                        hgnc_list.append(hgnc_id)
                elif is_fp:
                    logger.debug(
                        f"Filtered false positive: {gene_key} "
                        f"(alias '{stage1_matched_alias}') - {fp_reason}"
                    )

    elapsed = time.time() - start_time
    precision_note = (
        " (using enhanced precision filtering)" if genedict2
        else " (genedict1 fallback)"
    )
    if elapsed > 1.0:
        logger.info(
            f"SLOW gene mapping: {elapsed:.2f}s, {genes_checked} genes, "
            f"{len(found_genes)} genes found, text_len={len(text)}{precision_note}"
        )
    elif found_genes:
        logger.debug(
            f"Gene mapping: {elapsed:.2f}s, {len(found_genes)} genes found, "
            f"text_len={len(text)}{precision_note}"
        )

    return found_genes


def map_genes_in_entities(kedict: dict, kerdict: dict, genedict1: dict,
                          genedict2: dict, xml_root, aopxml_ns: str
                          ) -> tuple[dict, dict, list]:
    """Scan KE/KER text fields for gene mentions using three-stage algorithm.

    Parameters
    ----------
    kedict : dict
        Key Event dictionary (ke_id -> properties).
    kerdict : dict
        Key Event Relationship dictionary (ker_id -> properties).
    genedict1 : dict
        Screening gene dictionary.
    genedict2 : dict
        Precision gene dictionary.
    xml_root : Element
        XML root element of the AOP-Wiki XML.
    aopxml_ns : str
        AOP-Wiki XML namespace string (e.g., '{http://...}').

    Returns
    -------
    tuple[dict, dict, list]
        (updated kedict, updated kerdict, hgnclist)
    """
    hgnclist = []

    # --- Key Events ---
    logger.info("Starting gene mapping on Key Events (this may take a minute)...")
    ke_start_time = time.time()
    ke_list = xml_root.findall(aopxml_ns + 'key-event')
    total_kes = len(ke_list)
    logger.info(f"Processing {total_kes} Key Events for gene mapping...")

    for ke_idx, ke in enumerate(ke_list):
        if ke.find(aopxml_ns + 'description').text is not None:
            description_text = kedict[ke.get('id')]['dc:description']
            found_genes = _map_genes_in_text(
                description_text, genedict1, hgnclist, genedict2
            )
            if found_genes:
                kedict[ke.get('id')]['edam:data_1025'] = found_genes

        # Progress logging
        if (ke_idx + 1) % 100 == 0 or ke_idx + 1 in [10, 50, total_kes]:
            elapsed = time.time() - ke_start_time
            progress_pct = (ke_idx + 1) / total_kes * 100
            rate = (ke_idx + 1) / elapsed if elapsed > 0 else 0
            eta_seconds = (total_kes - ke_idx - 1) / rate if rate > 0 else 0
            logger.info(
                f"Key Event progress: {ke_idx + 1}/{total_kes} "
                f"({progress_pct:.1f}%) - {rate:.2f} KE/sec - "
                f"ETA: {eta_seconds:.0f}s - Found: {len(hgnclist)} genes"
            )

    ke_duration = time.time() - ke_start_time
    logger.info(
        f"Key Event gene mapping completed: {len(hgnclist)} genes "
        f"mapped to descriptions in {ke_duration:.1f} seconds"
    )

    # --- Key Event Relationships ---
    logger.info(
        "Starting gene mapping on Key Events and KERs "
        "(this may take a couple of minutes)..."
    )
    ker_start_time = time.time()
    ker_list = xml_root.findall(aopxml_ns + 'key-event-relationship')
    total_kers = len(ker_list)
    logger.info(f"Processing {total_kers} Key Event Relationships for gene mapping...")

    for ker_idx, ker in enumerate(ker_list):
        # Progress reporting
        if ker_idx % max(1, total_kers // 10) == 0 or ker_idx % 50 == 0:
            elapsed_ker = time.time() - ker_start_time
            progress_pct = (ker_idx / total_kers) * 100
            if ker_idx > 0:
                eta_seconds = (elapsed_ker / ker_idx) * (total_kers - ker_idx)
                eta_str = (
                    f", ETA: {eta_seconds/60:.1f}m" if eta_seconds > 60
                    else f", ETA: {eta_seconds:.0f}s"
                )
            else:
                eta_str = ""
            logger.info(
                f"KER gene mapping progress: {ker_idx}/{total_kers} "
                f"({progress_pct:.1f}%), elapsed: {elapsed_ker/60:.1f}m{eta_str}"
            )

        all_found_genes = []

        # Check description text
        if (ker.find(aopxml_ns + 'description').text is not None
                and 'dc:description' in kerdict[ker.get('id')]):
            description_genes = _map_genes_in_text(
                kerdict[ker.get('id')]['dc:description'],
                genedict1, hgnclist, genedict2,
            )
            all_found_genes.extend(description_genes)

        # Check biological plausibility and empirical support
        for weight in ker.findall(aopxml_ns + 'weight-of-evidence'):
            if (weight.find(aopxml_ns + 'biological-plausibility').text is not None
                    and 'nci:C80263' in kerdict[ker.get('id')]):
                bio_genes = _map_genes_in_text(
                    kerdict[ker.get('id')]['nci:C80263'],
                    genedict1, hgnclist, genedict2,
                )
                all_found_genes.extend(bio_genes)

            if (weight.find(aopxml_ns + 'emperical-support-linkage').text is not None
                    and 'edam:data_2042' in kerdict[ker.get('id')]):
                emp_genes = _map_genes_in_text(
                    kerdict[ker.get('id')]['edam:data_2042'],
                    genedict1, hgnclist, genedict2,
                )
                all_found_genes.extend(emp_genes)

        # Remove duplicates while preserving order
        unique_genes = []
        for gene in all_found_genes:
            if gene not in unique_genes:
                unique_genes.append(gene)

        if unique_genes:
            kerdict[ker.get('id')]['edam:data_1025'] = unique_genes

    ker_total_time = time.time() - ker_start_time
    logger.info(
        f"KER gene mapping completed: {total_kers} relationships "
        f"processed in {ker_total_time/60:.1f} minutes"
    )
    logger.info(
        f"Total gene mapping completed: {len(hgnclist)} genes "
        f"mapped to Key Events and Key Event Relationships"
    )

    return kedict, kerdict, hgnclist


# ---------------------------------------------------------------------------
# Section C: BridgeDb gene cross-references
# ---------------------------------------------------------------------------

def _batch_xrefs_bridgedb(gene_list: list[str], bridgedb_url: str,
                          timeout: int = 30,
                          chunk_size: int = 100,
                          symbol_lookup: dict | None = None) -> dict:
    """Map genes using BridgeDb batch xrefs API.

    Parameters
    ----------
    gene_list : list[str]
        List of HGNC gene IDs (e.g., ['hgnc:1100']).
    bridgedb_url : str
        Base URL for BridgeDb service.
    timeout : int
        Request timeout in seconds.
    chunk_size : int
        Number of genes per batch request.
    symbol_lookup : dict, optional
        Mapping of numeric HGNC ID -> gene symbol for BridgeDb queries.

    Returns
    -------
    dict
        Mapping of gene_id -> {db_name: [identifiers]}.
    """
    results = {}
    total_chunks = (len(gene_list) + chunk_size - 1) // chunk_size

    # Build reverse lookup: symbol -> numeric ID for response mapping
    reverse_lookup = {}
    if symbol_lookup:
        for numeric_id, sym in symbol_lookup.items():
            reverse_lookup[sym] = numeric_id

    for chunk_idx in range(0, len(gene_list), chunk_size):
        chunk = gene_list[chunk_idx:chunk_idx + chunk_size]
        chunk_num = chunk_idx // chunk_size + 1

        try:
            # Convert numeric IDs to symbols for BridgeDb H system code queries
            gene_symbols = []
            for gene in chunk:
                numeric = gene[5:]  # Remove 'hgnc:' prefix -> "1100"
                symbol = symbol_lookup.get(numeric, numeric) if symbol_lookup else numeric
                gene_symbols.append(symbol)

            batch_data = '\n'.join(gene_symbols)
            batch_url = bridgedb_url + 'xrefsBatch/H'
            headers = {'Content-Type': 'text/plain'}

            logger.debug(
                f"BridgeDb batch {chunk_num}/{total_chunks}: {len(chunk)} genes"
            )
            response = requests.post(
                batch_url, data=batch_data, headers=headers, timeout=timeout
            )
            response.raise_for_status()

            for line in response.text.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        gene_symbol = parts[0]
                        # Map response symbol back to numeric ID
                        numeric_id = reverse_lookup.get(gene_symbol, gene_symbol)
                        gene_id = f'hgnc:{numeric_id}'
                        xrefs_str = parts[2]

                        if xrefs_str != 'N/A':
                            dictionaryforgene = {}
                            xrefs = xrefs_str.split(',')

                            # System code -> database name mapping
                            system_code_map = {
                                'L': 'Entrez Gene',
                                'En': 'Ensembl',
                                'S': 'Uniprot-TrEMBL',
                                'H': 'HGNC',
                                'X': 'Affy',
                                'T': 'GeneOntology',
                                'Pd': 'PDB',
                                'Q': 'RefSeq',
                                'Om': 'OMIM',
                                'Uc': 'UCSC Genome Browser',
                                'Wg': 'WikiGenes',
                                'Ag': 'Agilent',
                                'Il': 'Illumina',
                                'Hac': 'HGNC Accession number',
                            }

                            for xref in xrefs:
                                if ':' in xref:
                                    system_code, value = xref.split(':', 1)
                                    db_name = system_code_map.get(system_code)
                                    if db_name is None:
                                        continue
                                    if db_name not in dictionaryforgene:
                                        dictionaryforgene[db_name] = []
                                    dictionaryforgene[db_name].append(value)

                            results[gene_id] = dictionaryforgene
                        else:
                            results[gene_id] = {}

        except requests.RequestException as e:
            logger.warning(
                f"BridgeDb batch {chunk_num} failed, "
                f"falling back to individual calls: {e}"
            )
            for gene in chunk:
                numeric = gene[5:]
                symbol = symbol_lookup.get(numeric, numeric) if symbol_lookup else numeric
                try:
                    response = requests.get(
                        bridgedb_url + 'xrefs/H/' + symbol,
                        timeout=timeout,
                    )
                    response.raise_for_status()
                    lines = response.text.split('\n')

                    dictionaryforgene = {}
                    for item in lines:
                        b = item.split('\t')
                        if len(b) == 2:
                            if b[1] not in dictionaryforgene:
                                dictionaryforgene[b[1]] = []
                            dictionaryforgene[b[1]].append(b[0])

                    results[gene] = dictionaryforgene
                except requests.RequestException:
                    logger.warning(f"Individual fallback also failed for {gene}")
                    results[gene] = {}

    return results


def build_gene_xrefs(hgnclist: list, bridgedb_url: str,
                     timeout: int = 30,
                     symbol_lookup: dict | None = None) -> dict:
    """Map HGNC IDs to Entrez/Ensembl/UniProt via BridgeDb.

    Parameters
    ----------
    hgnclist : list
        List of HGNC gene IDs (e.g., ['hgnc:1100', 'hgnc:11998']).
    bridgedb_url : str
        Base URL for BridgeDb service.
    timeout : int
        Request timeout in seconds.
    symbol_lookup : dict, optional
        Mapping of numeric HGNC ID -> gene symbol for BridgeDb queries.
        Required for converting numeric IDs back to symbols (system code H).

    Returns
    -------
    dict
        Keys: 'geneiddict', 'listofentrez', 'listofensembl', 'listofuniprot'.
    """
    logger.info(
        f"Starting BridgeDb identifier mapping for {len(hgnclist)} genes "
        f"using batch API (expecting 55x performance improvement)..."
    )
    bridgedb_start_time = time.time()
    total_genes = len(hgnclist)

    batch_results = _batch_xrefs_bridgedb(
        hgnclist, bridgedb_url, timeout=timeout, chunk_size=100,
        symbol_lookup=symbol_lookup,
    )

    geneiddict = {}
    listofentrez = []
    listofensembl = []
    listofuniprot = []
    successful_mappings = 0

    for gene in hgnclist:
        geneiddict[gene] = []
        dictionaryforgene = batch_results.get(gene, {})

        if dictionaryforgene:
            successful_mappings += 1

            if 'Entrez Gene' in dictionaryforgene:
                for entrez in dictionaryforgene['Entrez Gene']:
                    if 'ncbigene:' + entrez not in listofentrez:
                        listofentrez.append("ncbigene:" + entrez)
                    geneiddict[gene].append("ncbigene:" + entrez)
            if 'Ensembl' in dictionaryforgene:
                for ensembl in dictionaryforgene['Ensembl']:
                    if 'ensembl:' + ensembl not in listofensembl:
                        listofensembl.append("ensembl:" + ensembl)
                    geneiddict[gene].append("ensembl:" + ensembl)
            if 'Uniprot-TrEMBL' in dictionaryforgene:
                for uniprot in dictionaryforgene['Uniprot-TrEMBL']:
                    if 'uniprot:' + uniprot not in listofuniprot:
                        listofuniprot.append("uniprot:" + uniprot)
                    geneiddict[gene].append("uniprot:" + uniprot)

    bridgedb_total_time = time.time() - bridgedb_start_time

    if total_genes > 0:
        success_rate = (successful_mappings / total_genes) * 100
        failed_mappings = total_genes - successful_mappings
        logger.info(
            f"BridgeDb identifier mapping completed in "
            f"{bridgedb_total_time:.1f} seconds using batch API"
        )
        logger.info(
            f"Success rate: {success_rate:.1f}% "
            f"({successful_mappings}/{total_genes} genes), "
            f"{failed_mappings} failed mappings"
        )
        logger.info(
            f"Gene identifiers mapped: {len(listofentrez)} Entrez, "
            f"{len(listofuniprot)} UniProt, {len(listofensembl)} Ensembl IDs"
        )

        sequential_estimated_time = total_genes / 6.7
        if bridgedb_total_time > 0:
            speedup = sequential_estimated_time / bridgedb_total_time
            logger.info(
                f"Performance improvement: {speedup:.1f}x faster than "
                f"sequential approach (estimated)"
            )

    return {
        'geneiddict': geneiddict,
        'listofentrez': listofentrez,
        'listofensembl': listofensembl,
        'listofuniprot': listofuniprot,
    }
