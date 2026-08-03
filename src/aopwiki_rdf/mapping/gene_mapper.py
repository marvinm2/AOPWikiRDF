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

from aopwiki_rdf.mapping.automaton import GeneAutomaton
from aopwiki_rdf.mapping.bridgedb import batch_xrefs_gene

logger = logging.getLogger(__name__)

# Floor below which the BridgeDb resolution rate is treated as a service
# failure rather than a data characteristic. Healthy runs sit far above this
# (>90%); the three recorded incidents all produced ~0%. Deliberately generous
# so only a genuine collapse trips it.
MIN_BRIDGEDB_SUCCESS_RATE = 50.0


# ---------------------------------------------------------------------------
# Section A: Gene dictionary building
# ---------------------------------------------------------------------------

def build_gene_dicts(hgnc_file_path: str,
                     build_precision_dict: bool = False
                     ) -> tuple[dict, dict, dict]:
    """Parse HGNC file into genedict1 (screening), genedict2 (precision), and symbol_lookup.

    Parameters
    ----------
    hgnc_file_path : str
        Path to the HGNCgenes.txt file.
    build_precision_dict : bool
        Whether to materialise ``genedict2``, the delimiter-expanded variants.
        Defaults to False: the automaton expresses those boundaries directly, so
        production no longer reads it, and building it meant holding 7.4 million
        strings (~0.5 GB) that nothing consumed. Kept as an opt-in because the
        shape is still part of the published return signature.

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
            if build_precision_dict:
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


def build_token_index(genedict1: dict, symbol_lookup: dict) -> dict:
    """Return ``{token: gene_key}`` for every token, contests already resolved.

    The automaton needs one owner per token up front, where the old loop
    resolved contests per match. Uncontested tokens map to their only claimant;
    contested ones go to their approved-symbol owner, or are dropped entirely
    when no reading is defensible -- the same rule :func:`build_token_owners`
    applies, just materialised for the whole dictionary.
    """
    claims: dict[str, set] = {}
    for gene_key, tokens in genedict1.items():
        for token in tokens:
            stripped = token.strip()
            if stripped:
                claims.setdefault(stripped, set()).add(gene_key)

    index = {}
    retired = 0
    for token, gene_keys in claims.items():
        if len(gene_keys) == 1:
            index[token] = next(iter(gene_keys))
            continue
        symbol_owners = [k for k in gene_keys if symbol_lookup.get(k) == token]
        if len(symbol_owners) == 1:
            index[token] = symbol_owners[0]
        else:
            retired += 1

    logger.info(
        f"Gene mapping setup: {len(index)} tokens indexed, "
        f"{retired} contested tokens retired as unresolvable"
    )
    return index


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
#
# Second batch, added after a survey of the published 97191db release. Each was
# found by ranking genes on regex-vs-NER disagreement (see issue #109) and then
# read in context across the 1,360 KE/KER texts; the counts below are
# occurrences in that corpus, every one of which was the non-gene reading:
#
#   T3       188x  triiodothyronine        alias of SLC25A5
#   T2        15x  diiodothyronine         alias of SLC25A5
#   LPS       19x  lipopolysaccharide      previous symbol of IRF6
#   HCC       31x  hepatocellular carcinoma  alias of HYCC1
#   PND        9x  postnatal day           alias of NPPA
#   CCL        6x  C-C chemokine family prefix  alias of CRYGEP
#   BPA        5x  bisphenol A             alias of DST
#
# These seven are the ones that ownership resolution cannot reach, because each
# is claimed by exactly ONE gene and so is never contested. Tokens with several
# claimants and no approved-symbol owner -- E2, EMT, ERK, p38, ALP, G2, AP-1 --
# are already retired by build_token_owners and are deliberately left out rather
# than listed redundantly.
#
# Also deliberately NOT here, having been checked and rejected:
#   TPO, CA1, DBP  approved symbols of real genes; stoplisting them would drop
#                  legitimate mentions. CA1 (carbonic anhydrase 1 vs the
#                  hippocampal CA1 field) is genuinely ambiguous and needs a
#                  context rule, not a stoplist. DBP does not occur in the
#                  corpus at all.
DOMAIN_ABBREVIATION_STOPLIST = {
    'ROS',
    'ECM',
    'spatial',
    'T3',
    'T2',
    'LPS',
    'HCC',
    'PND',
    'CCL',
    'BPA',
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


# Language that marks the token as the thing being ADMINISTERED rather than
# measured. Chemical stressor abbreviations collide with gene aliases often --
# BPA (bisphenol A) is an alias of DST, DBP (dibutyl phthalate) is the approved
# symbol of D-box binding protein -- and both were being read as gene mentions.
#
# Matched POSITIONALLY, immediately around the token, not anywhere in the window.
# That distinction is what makes it safe: in "AR expression was measured after
# BPA exposure", 'exposure' is present for both tokens, but only BPA is directly
# followed by it. A window-wide test would discard the legitimate AR match too.
_STRESSOR_AFTER = re.compile(
    r'^[\s\-]*(?:exposure|exposures|exposed|treatment|treated|administration|'
    r'administered|dosing|dosed|injection|injected)\b',
    re.IGNORECASE,
)
_STRESSOR_BEFORE = re.compile(
    r'\b(?:exposure|exposed|treatment|treated|administration|administered|'
    r'dosing|dosed|injection|injected)\s+(?:to|with|of)\s*$',
    re.IGNORECASE,
)

# How far either side to look for that positional evidence. Deliberately short:
# it must catch "BPA exposure" without reaching an unrelated clause.
STRESSOR_PROXIMITY = 24


# Only ABBREVIATIONS are treated this way. A full protein name next to exposure
# language is usually still a real mention of that gene product -- "leptin
# treatment" and "insulin treatment" are about leptin and insulin, and an
# earlier revision of this rule discarded exactly those. An abbreviation next to
# the same words is far more often a chemical: BPA, DBP, TCDD.
STRESSOR_MAX_TOKEN_LEN = 4


# When one of these follows the token, the token is MODIFYING it rather than
# being the administered substance itself. "exposure to TPO inhibitors" is about
# thyroid peroxidase -- the inhibitor is what was administered, and TPO is a
# perfectly good gene mention. Without this guard the rule discarded 8 such TPO
# matches and read the gene out of its own sentence.
_STRESSOR_HEAD_NOUN = re.compile(
    r'^[\s\-]*(?:inhibitor|inhibitors|inhibition|agonist|agonists|antagonist|'
    r'antagonists|activity|activities|level|levels|protein|proteins|enzyme|'
    r'enzymes|receptor|receptors|expression|mrna|signalling|signaling|'
    r'deficien\w*|knockout|null)\b',
    re.IGNORECASE,
)


def _is_stressor_mention(text: str, start: int, end: int) -> bool:
    """True when the token reads as an administered substance, not a gene."""
    if end - start > STRESSOR_MAX_TOKEN_LEN:
        return False

    after = text[end:end + STRESSOR_PROXIMITY]
    if _STRESSOR_HEAD_NOUN.match(after):
        return False

    if _STRESSOR_AFTER.match(after):
        return True
    before = text[max(0, start - STRESSOR_PROXIMITY):start]
    return bool(_STRESSOR_BEFORE.search(before))


CONTEXT_RADIUS = 50


def _context_window(text: str, start: int, end: int,
                    radius: int = CONTEXT_RADIUS) -> str:
    """Return roughly ``radius`` characters either side, snapped to whole words.

    A fixed character window can sever a cue word and flip the verdict on one
    character: an observed match had "over-expression" truncated to
    "over-expressio", losing the `expression` cue and with it the decision.
    Extending to the nearest whitespace outside the window means a cue either
    falls in range or does not, rather than depending on where the arithmetic
    happened to land.
    """
    left = max(0, start - radius)
    right = min(len(text), end + radius)

    # Walk outward to whitespace so partially-included words are made whole.
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    while right < len(text) and not text[right].isspace():
        right += 1

    return text[left:right]


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
                       symbol_lookup: dict | None = None,
                       automaton=None) -> list[str]:
    """Find gene mentions in a text and return their HGNC IDs.

    Scans the text once with an Aho-Corasick automaton, then applies the
    false-positive filters to each delimiter-bounded match. Replaces a loop that
    tested every gene in the dictionary against every text.

    Parameters
    ----------
    text : str
        Text to scan for gene mentions.
    genedict1 : dict
        Screening dictionary (numeric_hgnc_id -> [symbol, name, aliases...]).
        Used to build an automaton when one is not supplied.
    hgnc_list : list
        Global list of found HGNC IDs (mutated in place).
    genedict2 : dict, optional
        Accepted and ignored. The delimiter-expanded dictionary it held is what
        the automaton makes unnecessary; the parameter remains so existing
        callers keep working.
    token_owners : dict, optional
        Contested-token resolution, applied when building an automaton here.
    symbol_lookup : dict, optional
        numeric_hgnc_id -> approved symbol, used by the short-token filter.
    automaton : GeneAutomaton, optional
        Prebuilt automaton. Pass this in loops -- constructing one per text
        rebuilds the whole dictionary and is far slower than the code it
        replaced.

    Returns
    -------
    list[str]
        List of found HGNC IDs (e.g., ['hgnc:1100']).
    """
    if not text or (automaton is None and not genedict1):
        return []

    if automaton is None:
        # Convenience path for callers holding only the raw dicts (tests,
        # ad-hoc use). Production builds the automaton once per run.
        index = build_token_index(genedict1, symbol_lookup or {})
        if token_owners:
            for token, owner in token_owners.items():
                if owner is None:
                    index.pop(token, None)
                else:
                    index[token] = owner
        automaton = GeneAutomaton(index)

    found_genes = []
    start_time = time.time()

    for start, end, gene_key in automaton.find(text):
        hgnc_id = 'hgnc:' + gene_key
        if hgnc_id in found_genes:
            continue

        matched_alias = text[start:end]

        # Checked before the general filters: this needs the token's position in
        # the text, which _is_false_positive deliberately does not receive.
        if _is_stressor_mention(text, start, end):
            logger.debug(
                f"Filtered stressor mention: {gene_key} "
                f"(token '{matched_alias}' reads as an administered substance)"
            )
            continue

        context = _context_window(text, start, end)

        is_fp, fp_reason = _is_false_positive(
            gene_key, matched_alias, context, symbol_lookup
        )
        if is_fp:
            # Only this occurrence is rejected. Another mention of the same gene
            # elsewhere in the text may still carry the context it needs.
            logger.debug(
                f"Filtered false positive: {gene_key} "
                f"(alias '{matched_alias}') - {fp_reason}"
            )
            continue

        found_genes.append(hgnc_id)
        if hgnc_id not in hgnc_list:
            hgnc_list.append(hgnc_id)

    elapsed = time.time() - start_time
    if elapsed > 1.0:
        logger.info(
            f"SLOW gene mapping: {elapsed:.2f}s, {len(found_genes)} genes "
            f"found, text_len={len(text)}"
        )
    elif found_genes:
        logger.debug(
            f"Gene mapping: {elapsed:.2f}s, {len(found_genes)} genes found, "
            f"text_len={len(text)}"
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

    # One automaton for the whole corpus. Building it per text would rebuild the
    # entire dictionary each time and be far slower than the loop this replaces.
    index = build_token_index(genedict1, symbol_lookup or {})
    if token_owners:
        for token, owner in token_owners.items():
            if owner is None:
                index.pop(token, None)
            else:
                index[token] = owner
    automaton = GeneAutomaton(index)

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
                token_owners, symbol_lookup, automaton,
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
                automaton,
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

def build_gene_xrefs(hgnclist: list, bridgedb_url: str,
                     timeout: int = 30,
                     symbol_lookup: dict | None = None,
                     min_success_rate: float = MIN_BRIDGEDB_SUCCESS_RATE) -> dict:
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
    min_success_rate : float
        Percentage of genes that must resolve before the result is trusted.
        Below it, a RuntimeError is raised rather than returning empty
        cross-references. Set to 0 to disable.

    Returns
    -------
    dict
        Keys: 'geneiddict', 'listofentrez', 'listofensembl', 'listofuniprot'.

    Raises
    ------
    RuntimeError
        When the BridgeDb resolution rate falls below ``min_success_rate``.
    """
    logger.info(
        f"Starting BridgeDb identifier mapping for {len(hgnclist)} genes "
        f"using batch API (expecting 55x performance improvement)..."
    )
    bridgedb_start_time = time.time()
    total_genes = len(hgnclist)

    batch_results = batch_xrefs_gene(
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

        # Fail loudly on a collapse instead of publishing xref-less genes.
        #
        # This exact failure has now occurred three times (PR #100's missing
        # trailing slash, the multiEndpoint 2026-07-01 quarter, and the
        # 2026-07-25 BridgeDb 2.1.8 wire-format change). Every time BridgeDb
        # returned HTTP 200 with something unparseable, every gene resolved to
        # {}, and nothing raised -- the success rate was logged at INFO and the
        # pipeline carried on. It was caught late, or by the publish gate, or
        # by luck. A hard failure here stops the run at the cause rather than
        # several steps downstream at a symptom.
        if success_rate < min_success_rate:
            raise RuntimeError(
                f"BridgeDb resolved only {success_rate:.1f}% of genes "
                f"({successful_mappings}/{total_genes}), below the "
                f"{min_success_rate:.0f}% floor. This normally means the "
                f"service returned an unparseable response rather than that "
                f"the genes are unmappable -- check the wire format and the "
                f"base URL before rerunning. Pass min_success_rate=0 to "
                f"override if the low rate is genuinely expected."
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
