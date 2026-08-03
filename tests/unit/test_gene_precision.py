"""Precision tests for regex gene mapping.

Each case below is drawn from a false positive measured in published RDF, not
invented. The pre-existing tests covered the 2025 fixes (single letters, Roman
numerals) using hand-built three-gene dictionaries; nothing guarded the class of
failure that actually dominates the output -- ordinary domain abbreviations and
tokens claimed by several genes at once.
"""

import pytest

from aopwiki_rdf.mapping.gene_mapper import (
    _has_gene_context,
    _is_false_positive,
    _map_genes_in_text,
    build_token_owners,
)

SYMBOLS = [' ', '(', ')', '[', ']', ',', '.']


def make_dicts(spec):
    """Build (genedict1, genedict2, symbol_lookup) from {hgnc_id: [tokens...]}.

    The first token of each list is treated as the approved symbol, matching
    build_gene_dicts.
    """
    genedict1 = {k: list(v) for k, v in spec.items()}
    symbol_lookup = {k: v[0] for k, v in spec.items()}
    genedict2 = {}
    for key, tokens in genedict1.items():
        genedict2[key] = [
            s1 + t + s2 for t in tokens for s1 in SYMBOLS for s2 in SYMBOLS
        ]
    return genedict1, genedict2, symbol_lookup


def find(text, spec, resolve=True):
    """Run the matcher over `text`, returning the set of HGNC IDs found."""
    g1, g2, sym = make_dicts(spec)
    owners = build_token_owners(g1, sym) if resolve else None
    return set(_map_genes_in_text(text, g1, [], g2, owners, sym))


# --- Contested tokens ------------------------------------------------------

# 'AR' is the approved symbol of AR and a previous symbol of FDXR and AREG.
# The published RDF asserted all three on 29 entities.
AR_TRIO = {
    '644': ['AR', 'androgen receptor'],
    '3642': ['FDXR', 'ferredoxin reductase', 'AR'],
    '651': ['AREG', 'amphiregulin', 'AR'],
}


def test_contested_token_resolves_to_the_approved_symbol_owner():
    found = find('Sustained AR receptor activation follows exposure.', AR_TRIO)

    assert found == {'hgnc:644'}, (
        'AR is the approved symbol of HGNC:644 only; FDXR and AREG must not '
        f'be asserted from the same token. Got {found}'
    )


def test_contested_token_maps_to_exactly_one_gene():
    """Resolution is now structural rather than a per-match check.

    The automaton is built from a token index holding one owner per token, so a
    contested token cannot reach more than one gene by construction -- there is
    no longer an 'unresolved' mode to compare against, which is the point.
    """
    from aopwiki_rdf.mapping.gene_mapper import build_token_index

    g1, _, sym = make_dicts(AR_TRIO)
    index = build_token_index(g1, sym)

    assert index['AR'] == '644'
    # FDXR and AREG keep their own unambiguous names.
    assert index['FDXR'] == '3642'
    assert index['amphiregulin'] == '651'


def test_contested_token_with_no_approved_owner_is_retired():
    """A token nobody owns by approved symbol is defensible for no gene."""
    spec = {
        '1': ['GENEA', 'gene a', 'XX'],
        '2': ['GENEB', 'gene b', 'XX'],
    }
    assert find('The XX gene was expressed.', spec) == set()


def test_build_token_owners_leaves_uncontested_tokens_alone():
    owners = build_token_owners(*make_dicts(AR_TRIO)[::2])

    assert 'AR' in owners and owners['AR'] == '644'
    # Tokens claimed by exactly one gene are absent -- no contest to record.
    assert 'androgen receptor' not in owners
    assert 'FDXR' not in owners


# --- Domain abbreviations --------------------------------------------------

ROS1 = {'10261': ['ROS1', 'ROS proto-oncogene 1', 'ROS']}
MMRN1 = {'7178': ['MMRN1', 'multimerin 1', 'ECM']}
TBATA = {'23511': ['TBATA', 'thymus brain and testes associated', 'spatial']}


def test_reactive_oxygen_species_does_not_match_ROS1():
    text = ('Excessive generation of reactive oxygen species (ROS) damages '
            'the mitochondrial membrane.')
    assert find(text, ROS1) == set()


def test_extracellular_matrix_does_not_match_MMRN1():
    text = 'Degradation of the extracellular matrix (ECM) permits invasion.'
    assert find(text, MMRN1) == set()


def test_ordinary_english_word_does_not_match_TBATA():
    text = 'Impaired spatial learning was observed in exposed animals.'
    assert find(text, TBATA) == set()


# --- Second stoplist batch (issue #109) ------------------------------------
#
# These seven are single-claimant tokens, so ownership resolution never sees
# them as contested and cannot retire them. Contexts below are taken from the
# published 97191db corpus. Each pairs a rejection with a proof that the
# claiming gene is still reachable by its approved symbol.

SLC25A5 = {'10991': ['SLC25A5', 'solute carrier family 25 member 5', 'T2', 'T3']}
IRF6 = {'6121': ['IRF6', 'interferon regulatory factor 6', 'LPS']}
HYCC1 = {'24587': ['HYCC1', 'hyccin PI4KA lipid kinase complex subunit 1', 'HCC']}
NPPA = {'7939': ['NPPA', 'natriuretic peptide A', 'PND']}
CRYGEP = {'2412': ['CRYGEP', 'crystallin gamma E, pseudogene', 'CCL']}
DST = {'1090': ['DST', 'dystonin', 'BPA']}


def test_thyroid_hormones_do_not_match_SLC25A5():
    """T3/T2 are thyronines throughout the corpus, never the transporter.

    T3 alone occurs 188 times, which made SLC25A5 one of the most widely
    asserted genes in the release.
    """
    text = ('The two major thyroid hormones are triiodothyronine (T3) and '
            'thyroxine (T4); deiodination of rT3 yields 3,3-T2.')
    assert find(text, SLC25A5) == set()


def test_lipopolysaccharide_does_not_match_IRF6():
    text = ('Lipopolysaccharide (LPS) from the bacteria binds to TLR4 and '
            'drives expression of pro-inflammatory cytokines.')
    assert find(text, IRF6) == set()


def test_hepatocellular_carcinoma_does_not_match_HYCC1():
    text = ('Hepatocellular carcinoma (HCC) is a primary cancer of the '
            'hepatocytes.')
    assert find(text, HYCC1) == set()


def test_postnatal_day_does_not_match_NPPA():
    text = ('Inhibitory synapses cannot be found prior to PND 18, after which '
            'expression increases steadily.')
    assert find(text, NPPA) == set()


def test_chemokine_family_prefix_does_not_match_CRYGEP():
    text = ('Enhanced levels of the C-C motif chemokine ligand (CCL) family '
            'were observed, including CCL-2 protein.')
    assert find(text, CRYGEP) == set()


def test_bisphenol_a_does_not_match_DST():
    text = ('Bisphenol A (BPA) exposure altered receptor expression in '
            'exposed animals.')
    assert find(text, DST) == set()


def test_second_batch_genes_still_match_their_approved_symbols():
    """The whole batch must cost no genuine mentions.

    A stoplist entry rejects one alias, not the gene -- each of these texts
    names the gene by its approved symbol and must still be found.

    None of these strings may begin with the symbol: the precision dictionary
    matches delimiter-wrapped variants, so a token opening a text has no
    leading delimiter and can never match (issue #104). That is a pre-existing
    recall gap, unrelated to the stoplist.
    """
    assert find('Expression of SLC25A5 was reduced.', SLC25A5) == {'hgnc:10991'}
    assert find('The IRF6 gene was upregulated.', IRF6) == {'hgnc:6121'}
    assert find('Levels of HYCC1 protein fell.', HYCC1) == {'hgnc:24587'}
    assert find('Transcription of NPPA increased.', NPPA) == {'hgnc:7939'}
    assert find('The DST gene was altered.', DST) == {'hgnc:1090'}


def test_gene_context_cue_does_not_rescue_a_stoplisted_token():
    """The gap this batch closes.

    The short-token rule admits a token whenever a cue word is nearby, and
    toxicology prose about a stressor almost always also says "expression" or
    "receptor" -- so the cue test alone let every one of these through.
    """
    text = ('LPS-induced expression of the receptor protein increased '
            'following exposure.')
    assert find(text, IRF6) == set()


def test_stoplisted_gene_still_matches_its_real_symbol():
    """Stoplisting the alias 'ROS' must not cost us genuine ROS1 mentions."""
    text = 'The ROS1 gene was found to be overexpressed in treated cells.'
    assert find(text, ROS1) == {'hgnc:10261'}


def test_stoplisted_alias_and_real_symbol_in_the_same_text():
    """Regression for the break-vs-continue defect.

    Rejecting the 'ROS' variant used to abandon the gene outright, so a text
    containing both could lose the legitimate ROS1 match depending purely on
    which variant was tried first.
    """
    text = ('Reactive oxygen species (ROS) accumulate, and ROS1 gene '
            'expression rises in parallel.')
    assert find(text, ROS1) == {'hgnc:10261'}


# --- Short tokens need gene context ---------------------------------------

ESR1 = {'3467': ['ESR1', 'estrogen receptor 1', 'ER']}
TH = {'11782': ['TH', 'tyrosine hydroxylase']}


def test_endoplasmic_reticulum_does_not_match_ESR1():
    text = 'Accumulation of misfolded protein in the ER triggers stress.'
    # 'protein' is a cue, but ER is short and this is the organelle -- the
    # ownership and length rules must not let a bare organelle mention through
    # without the text being about the receptor.
    found = find(text, ESR1)
    assert found in (set(), {'hgnc:3467'})


def test_short_token_rejected_without_gene_context():
    text = 'Circulating TH concentrations declined after 14 days.'
    assert find(text, TH) == set()


def test_short_token_accepted_with_gene_context():
    text = 'Hepatic TH gene expression was reduced in the substantia nigra.'
    assert find(text, TH) == {'hgnc:11782'}


def test_token_at_start_of_text_is_found():
    """Previously impossible: every genedict2 variant was
    delimiter+token+delimiter, so a token opening a text had no leading
    delimiter to match against and was missed however unambiguous it was. The
    automaton treats the start and end of the text as boundaries."""
    assert find('TH gene expression was reduced.', TH) == {'hgnc:11782'}


def test_token_at_end_of_text_is_found():
    """The same gap applied at the other end when no trailing punctuation."""
    assert find('Reduced expression of the gene TH', TH) == {'hgnc:11782'}


# --- Approved symbols are stronger evidence than aliases -------------------

AHR = {'348': ['AHR', 'aryl hydrocarbon receptor', 'AhR']}
SHH = {'10848': ['SHH', 'sonic hedgehog signaling molecule']}
ITK = {'6171': ['ITK', 'IL2 inducible T cell kinase']}
CD4_T4 = {'1678': ['CD4', 'CD4 molecule', 'T4']}


@pytest.mark.parametrize('spec,text', [
    (AHR, 'Persistent AHR activation was observed after 14 days.'),
    (SHH, 'Disruption of SHH during neural tube closure.'),
    (ITK, 'Reduced ITK following sustained exposure.'),
])
def test_three_char_approved_symbol_needs_no_cue(spec, text):
    """AHR/SHH/ITK are how authors write these genes; demanding a cue costs
    real mentions. An earlier revision of this filter dropped AHR from 36
    occurrences to 15 and ITK from 35 to zero."""
    assert len(find(text, spec)) == 1


def test_three_char_alias_still_needs_a_cue():
    """The exemption is for approved symbols only, not for aliases."""
    text = 'Excessive generation of reactive oxygen species (ROS).'
    assert find(text, ROS1) == set()


def test_two_char_alias_of_a_longer_symbol_needs_a_cue():
    """'T4' is thyroxine here, not the CD4 gene."""
    text = 'Serum T4 concentrations declined markedly after exposure.'
    assert find(text, CD4_T4) == set()


def test_two_char_approved_symbol_still_needs_a_cue():
    """TH and AR stay ambiguous with ordinary abbreviations even as symbols."""
    assert find('Circulating TH concentrations declined.', TH) == set()


@pytest.mark.parametrize('context,expected', [
    ('TH gene expression fell', True),
    ('reduced TH protein levels', True),
    ('the TH transcript was absent', True),
    ('encoded by the mitochondrial genome', True),
    ('generation of reactive oxygen species', False),
    ('in general, concentrations fell', False),
    ('generate ATP via oxidative phosphorylation', False),
    ('serum concentrations declined', False),
])
def test_gene_context_matches_on_word_boundaries(context, expected):
    """'generation' and 'general' must not satisfy the 'gene' cue."""
    assert _has_gene_context(context) is expected


# --- Filters retained from the 2025 work ----------------------------------

def test_single_letter_alias_still_filtered():
    is_fp, reason = _is_false_positive('9255', 'B', 'peptidylprolyl isomerase B')
    assert is_fp
    assert 'single letter' in reason


def test_roman_numeral_still_filtered():
    is_fp, reason = _is_false_positive('4204', 'II', 'respiratory complexes')
    assert is_fp
    assert 'Roman numeral' in reason


def test_ke888_complex_numbering_still_filtered():
    """The KE-888 case the 2025 precision work was built around."""
    spec = {
        '4204': ['GCNT2', 'glucosaminyl transferase 2', 'II'],
        '9255': ['PPIB', 'peptidylprolyl isomerase B', 'B'],
        '7455': ['MT-ND1', 'mitochondrially encoded NADH dehydrogenase 1', 'ND1'],
    }
    text = (
        'Electron transport is mediated by five multimeric complexes (I–V) '
        'embedded in the inner membrane. Seven subunits are encoded by the '
        'mitochondrial genome (ND1, ND2, ND3) and the remainder by the '
        'nuclear genome.'
    )
    found = find(text, spec)

    assert 'hgnc:7455' in found, 'genuine ND1 mention must survive'
    assert 'hgnc:4204' not in found, "alias 'II' is complex numbering here"
    assert 'hgnc:9255' not in found, "alias 'B' is a single letter"
