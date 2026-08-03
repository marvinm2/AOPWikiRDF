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
            # Columns 4-5 ONLY (previous symbols, alias symbols). Columns 6-7 are
            # accession numbers and the Ensembl ID -- database identifiers, not
            # names anything in a Key Event description would ever be called by.
            # Scanning them added no true positives and a great deal of noise:
            # accessions are shared across genes, so e.g. 'AF250841' was claimed
            # by 71 different genes, every one of them a spurious ambiguity.
            for item in a[3:5]:
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


def build_token_owners(genedict1: dict, symbol_lookup: dict) -> dict:
    """Resolve which gene, if any, a given name token legitimately identifies.

    The matcher tests every gene independently, so a token claimed by several
    genes used to produce an association with *all* of them. ``AR`` is an alias
    or previous symbol of AR, FDXR and AREG, and the published RDF consequently
    asserted all three on 29 entities, where at most one can be correct.

    Ambiguity is resolved in favour of the gene whose **approved symbol** the
    token is -- the reading a curator would take. If a contested token is nobody's
    approved symbol (or, pathologically, more than one gene's), no reading is
    defensible and the token is retired for every gene.

    Parameters
    ----------
    genedict1 : dict
        Screening dictionary (numeric_hgnc_id -> [symbol, name, prev, aliases]).
    symbol_lookup : dict
        numeric_hgnc_id -> approved gene symbol.

    Returns
    -------
    dict
        token -> owning numeric HGNC ID, or ``None`` where the token is
        contested and has no approved-symbol owner. Tokens absent from the
        mapping are unambiguous by construction.
    """
    claims: dict[str, set] = {}
    for gene_key, tokens in genedict1.items():
        for token in tokens:
            stripped = token.strip()
            if stripped:
                claims.setdefault(stripped, set()).add(gene_key)

    owners = {}
    contested = 0
    retired = 0
    for token, gene_keys in claims.items():
        if len(gene_keys) == 1:
            continue  # unambiguous; absence from `owners` means "no contest"
        contested += 1
        symbol_owners = [
            key for key in gene_keys if symbol_lookup.get(key) == token
        ]
        if len(symbol_owners) == 1:
            owners[token] = symbol_owners[0]
        else:
            owners[token] = None
            retired += 1

    logger.info(
        f"Gene mapping setup: {contested} contested tokens; "
        f"{contested - retired} resolved to an approved-symbol owner, "
        f"{retired} retired as unresolvable"
    )
    return owners


# ---------------------------------------------------------------------------
# Section B: Gene mapping in entity text (three-stage algorithm)
# ---------------------------------------------------------------------------

# False-positive filter constants
SINGLE_LETTER_ALIASES = {
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
}

ROMAN_NUMERAL_PATTERN = re.compile(r'\b[IVX]+\b')

# Tokens HGNC lists as gene names that, in AOP-Wiki prose, essentially never
# denote the gene. Each was verified against the corpus before being added --
# every occurrence of these as a match was a false positive:
#
#   ROS      alias of ROS1; in AOP text always "reactive oxygen species"
#   ECM      alias of MMRN1; always "extracellular matrix"
#   spatial  alias of TBATA; an ordinary English adjective
#
# Deliberately NOT here: AR, TH, ER, T4 and friends. Those are genuinely
# ambiguous rather than always-wrong (AR is both androgen receptor and a
# previous symbol of two other genes; TH is both thyroid hormone and tyrosine
# hydroxylase), so they are handled by ownership resolution and the short-token
# rule below, which can still admit them where the context supports it.
DOMAIN_ABBREVIATION_STOPLIST = {
    'ROS',
    'ECM',
    'spatial',
}

# A short token is only read as a gene when the surrounding prose is talking
# about genes. Without a cue, "(ER)" is the endoplasmic reticulum and "T4" is
# thyroxine, not ESR1 and CD4.
#
# Matched on WORD BOUNDARIES, not as substrings. Substring matching would let
# "generation of reactive oxygen species" satisfy the 'gene' cue -- precisely
# the context the filter exists to reject -- and "in general" would do the same.
GENE_CONTEXT_CUES = (
    'gene', 'genes', 'genetic', 'mrna', 'transcript', 'transcripts',
    'transcription', 'expression', 'expressed', 'protein', 'proteins',
    'receptor', 'receptors', 'enzyme', 'enzymes', 'isoform', 'isoforms',
    'knockout', 'knockdown', 'polymorphism', 'allele', 'alleles', 'mutation',
    'mutations', 'promoter', 'agonist', 'antagonist', 'encoded', 'encodes',
)

_GENE_CONTEXT_PATTERN = re.compile(
    r'\b(?:' + '|'.join(GENE_CONTEXT_CUES) + r')\b', re.IGNORECASE
)

# Length at or below which a token is treated as an abbreviation first and a
# gene name second -- but the threshold depends on how strong the token is as
# evidence.
#
# An APPROVED SYMBOL is a deliberate, curated identifier: AHR, SHH, TPO, ITK and
# CD4 are how authors actually write those genes, and demanding a nearby cue word
# costs real mentions. Only 2-character approved symbols (TH, AR, ER) stay
# ambiguous enough with ordinary abbreviations to need one.
#
# An ALIAS or PREVIOUS SYMBOL is much weaker evidence -- it is whatever the gene
# used to be called, or is sometimes called -- so the bar stays at 3 characters.
# That is what catches ROS (alias of ROS1), ECM (alias of MMRN1), T4 (alias of
# CD4) and ER (alias of ESR1) without touching the approved symbols above.
SHORT_TOKEN_MAX_LEN_APPROVED_SYMBOL = 2
SHORT_TOKEN_MAX_LEN_ALIAS = 3


def _has_gene_context(context: str) -> bool:
    """True when the surrounding text reads as being about genes or proteins."""
    return bool(_GENE_CONTEXT_PATTERN.search(context))


def _is_false_positive(gene_key: str, matched_alias: str,
                       matched_text_context: str,
                       symbol_lookup: dict | None = None
                       ) -> tuple[bool, str | None]:
    """Filter out known false positive patterns.

    Parameters
    ----------
    gene_key : str
        Gene dictionary key (numeric HGNC ID, e.g. "1100").
    matched_alias : str
        The alias text that was matched.
    matched_text_context : str
        Surrounding text context for pattern analysis.
    symbol_lookup : dict, optional
        numeric_hgnc_id -> approved symbol. Only used for logging clarity; the
        filters below apply identically with or without it.
    """
    # Filter 1: Single letter aliases (too ambiguous)
    if matched_alias.strip() in SINGLE_LETTER_ALIASES:
        return True, f"single letter alias '{matched_alias.strip()}'"

    # Filter 2: Roman numerals
    if ROMAN_NUMERAL_PATTERN.fullmatch(matched_alias.strip()):
        return True, f"Roman numeral '{matched_alias.strip()}'"

    stripped = matched_alias.strip()

    # Filter 3: Domain abbreviations that never mean the gene in AOP prose.
    if stripped in DOMAIN_ABBREVIATION_STOPLIST:
        return True, f"domain abbreviation '{stripped}' (never a gene mention here)"

    # Filter 4: Short tokens need the prose to actually be about genes.
    #
    # This replaces an earlier rule that rejected short tokens only when a
    # bracket appeared anywhere in the +/-50 char window. That made the outcome
    # depend on unrelated punctuation -- 'TH' survived on 104 entities purely
    # because no bracket happened to fall nearby -- so it filtered arbitrarily
    # rather than meaningfully.
    #
    # The threshold is lower for approved symbols than for aliases: see the
    # constants above for why AHR/SHH/TPO are exempt but ROS/ECM/T4 are not.
    is_approved_symbol = bool(
        symbol_lookup and symbol_lookup.get(gene_key) == stripped
    )
    max_len = (
        SHORT_TOKEN_MAX_LEN_APPROVED_SYMBOL if is_approved_symbol
        else SHORT_TOKEN_MAX_LEN_ALIAS
    )
    if len(stripped) <= max_len and not _has_gene_context(matched_text_context):
        kind = 'approved symbol' if is_approved_symbol else 'alias'
        return True, (
            f"short {kind} '{stripped}' with no gene context in surrounding text"
        )

    # Filter 5: Gene-specific false positive patterns (match on alias, not key)
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
                       genedict2: dict | None = None,
                       token_owners: dict | None = None,
                       symbol_lookup: dict | None = None) -> list[str]:
    """Enhanced three-stage gene mapping algorithm with false positive filtering.

    Stage 1: Screen with genedict1 (basic gene names)
    Stage 2: Match with genedict2 (punctuation-delimited variants) with precision
    Stage 3: Resolve contested tokens, then apply false positive filters

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
    token_owners : dict, optional
        token -> owning HGNC ID (or None) from :func:`build_token_owners`. When
        omitted, contested tokens are left unresolved and every claiming gene
        matches -- the pre-existing behaviour, kept so callers that have not
        been updated still work.
    symbol_lookup : dict, optional
        numeric_hgnc_id -> approved symbol, passed through for log clarity.

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

                        # Every genedict2 variant is s1 + token + s2 with both
                        # sentinels non-empty, so it is always >= 3 chars and
                        # this strip is the only reachable case.
                        matched_alias = item.strip(' ()[],.')

                        owner = token_owners.get(matched_alias, gene_key) if token_owners else gene_key
                        if owner != gene_key:
                            logger.debug(
                                f"Skipped contested token '{matched_alias}' for "
                                f"{gene_key}: owned by {owner or 'no gene'}"
                            )
                            # Another variant of this gene may still match
                            # legitimately, so keep scanning rather than
                            # abandoning the gene.
                            continue

                        is_fp, fp_reason = _is_false_positive(
                            gene_key, matched_alias, context, symbol_lookup
                        )

                        if is_fp:
                            logger.debug(
                                f"Filtered false positive: {gene_key} "
                                f"(alias '{matched_alias}') - {fp_reason}"
                            )
                            # Only this variant is rejected. Abandoning the gene
                            # here (the previous behaviour) meant a text
                            # containing both 'ROS' and 'ROS1' could lose the
                            # legitimate ROS1 match, depending purely on which
                            # variant genedict2 happened to list first.
                            continue

                        found_genes.append(hgnc_id)
                        if hgnc_id not in hgnc_list:
                            hgnc_list.append(hgnc_id)
                        break
            else:
                # Fallback to genedict1-only matching
                owner = (
                    token_owners.get(stage1_matched_alias, gene_key)
                    if token_owners else gene_key
                )
                if owner != gene_key:
                    logger.debug(
                        f"Skipped contested token '{stage1_matched_alias}' for "
                        f"{gene_key}: owned by {owner or 'no gene'}"
                    )
                    continue

                is_fp, fp_reason = _is_false_positive(
                    gene_key, stage1_matched_alias, text, symbol_lookup
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
                          genedict2: dict, xml_root, aopxml_ns: str,
                          token_owners: dict | None = None,
                          symbol_lookup: dict | None = None
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
    token_owners : dict, optional
        Contested-token resolution map from :func:`build_token_owners`.
    symbol_lookup : dict, optional
        numeric_hgnc_id -> approved symbol.

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
                description_text, genedict1, hgnclist, genedict2,
                token_owners, symbol_lookup,
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
                genedict1, hgnclist, genedict2, token_owners, symbol_lookup,
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
    # Endpoints are appended directly to the base (e.g. + 'xrefsBatch/H'), so it
    # must end in '/'. A missing trailing slash yields '.../HumanxrefsBatch/H',
    # which 404s for every gene and silently drops all external xrefs. Normalize
    # here as ner_el_mapper already does for its own BridgeDb calls.
    bridgedb_url = bridgedb_url.rstrip('/') + '/'
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
