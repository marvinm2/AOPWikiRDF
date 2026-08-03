"""Tests for detector-disagreement ranking and the stressor filter (#109)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from detector_disagreement import (  # noqa: E402
    parse_detector_sets,
    rank_candidates,
)
from aopwiki_rdf.mapping.gene_mapper import (  # noqa: E402
    _is_stressor_mention,
    _map_genes_in_text,
)

TTL = """
aop.events:1 a aopo:KeyEvent ;
\t:geneDetectedByRegex hgnc:10261, hgnc:1100 ;
\t:geneDetectedByNER hgnc:1100 .

aop.events:2 a aopo:KeyEvent ;
\t:geneDetectedByRegex hgnc:10261 ;
\t:geneDetectedByNER hgnc:1100 .

aop.relationships:3 a aopo:KeyEventRelationship ;
\t:geneDetectedByRegex hgnc:10261, hgnc:1100 ;
\t:geneDetectedByNER hgnc:1100 .
"""


# --- Parsing and ranking ---------------------------------------------------

def test_parse_separates_the_two_detectors():
    regex_hits, ner_hits = parse_detector_sets(TTL)

    assert regex_hits['10261'] == {
        'aop.events:1', 'aop.events:2', 'aop.relationships:3',
    }
    assert '10261' not in ner_hits
    assert len(ner_hits['1100']) == 3


def test_ranking_surfaces_the_unconfirmed_gene():
    regex_hits, ner_hits = parse_detector_sets(TTL)
    ranked = rank_candidates(regex_hits, ner_hits,
                             min_regex_entities=3, max_agreement=0.10)

    assert [c['gene'] for c in ranked] == ['hgnc:10261']
    assert ranked[0]['ner_confirmed'] == 0


def test_confirmed_gene_is_not_flagged():
    """A gene both detectors agree on is not a collision candidate."""
    regex_hits, ner_hits = parse_detector_sets(TTL)
    ranked = rank_candidates(regex_hits, ner_hits,
                             min_regex_entities=1, max_agreement=0.10)

    assert 'hgnc:1100' not in [c['gene'] for c in ranked]


def test_min_entity_threshold_filters_rare_genes():
    regex_hits, ner_hits = parse_detector_sets(TTL)
    assert rank_candidates(regex_hits, ner_hits,
                           min_regex_entities=10, max_agreement=0.10) == []


def test_ranking_is_ordered_by_regex_entity_count():
    regex_hits = {'a': {1, 2, 3}, 'b': {1, 2, 3, 4, 5}, 'c': {1}}
    ranked = rank_candidates(regex_hits, {'z': {1}},
                             min_regex_entities=1, max_agreement=0.10)
    assert [c['gene'] for c in ranked] == ['hgnc:b', 'hgnc:a', 'hgnc:c']


# --- Stressor filter -------------------------------------------------------

def stressor(text, token):
    start = text.index(token)
    return _is_stressor_mention(text, start, start + len(token))


@pytest.mark.parametrize('text,token', [
    ('BPA exposure altered receptor expression', 'BPA'),
    ('DBP treatment reduced testosterone', 'DBP'),
    ('Rats exposed to BPA showed effects', 'BPA'),
    ('following treatment with DBP', 'DBP'),
    ('altered in response to PFAS exposure', 'PFAS'),
])
def test_abbreviation_next_to_exposure_language_is_a_stressor(text, token):
    assert stressor(text, token)


@pytest.mark.parametrize('text,token', [
    # Modifier, not the administered thing -- this guard recovered 8 TPO matches.
    ('maternal administration of TPO inhibitors', 'TPO'),
    ('after exposure to TPO inhibitors and deiodinase', 'TPO'),
    ('exposure to AR antagonists', 'AR'),
    # Not exposure language at all.
    ('AR receptor antagonism reduces signalling', 'AR'),
    ('Hepatic TH gene expression fell', 'TH'),
])
def test_modifier_and_plain_mentions_are_not_stressors(text, token):
    assert not stressor(text, token)


def test_full_protein_names_are_exempt():
    """'leptin treatment' is about leptin; an earlier revision discarded it."""
    assert not stressor('leptin treatment increased satiety', 'leptin')
    assert not stressor('insulin treatment lowered glucose', 'insulin')


def test_only_the_stressor_is_dropped_from_a_mixed_sentence():
    """The positional test is what makes this safe.

    'exposure' is in range for both tokens, but only BPA is directly followed
    by it -- a window-wide test would discard the legitimate AR match too.
    """
    spec = {'644': ['AR', 'androgen receptor'], '1090': ['DST', 'dystonin', 'BPA']}
    found = set(_map_genes_in_text(
        'AR expression was measured after BPA exposure',
        spec, [], None, None, {'644': 'AR', '1090': 'DST'},
    ))
    assert found == {'hgnc:644'}
