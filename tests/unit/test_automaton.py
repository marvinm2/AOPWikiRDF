"""Tests for the Aho-Corasick gene matcher (#104)."""

import pytest

from aopwiki_rdf.mapping.automaton import DELIMITERS, GeneAutomaton, _is_boundary
from aopwiki_rdf.mapping.gene_mapper import _context_window

SIMPLE = {'TP53': '11998', 'BRCA1': '1100', 'AR': '644'}


def matches(text, index=None):
    return {(t[2], text[t[0]:t[1]]) for t in GeneAutomaton(index or SIMPLE).find(text)}


# --- Boundary semantics ----------------------------------------------------

def test_start_of_text_is_a_boundary():
    """The gap the delimiter-expanded dictionary could not express."""
    assert ('11998', 'TP53') in matches('TP53 was induced.')


def test_end_of_text_is_a_boundary():
    assert ('11998', 'TP53') in matches('Induction of TP53')


def test_whole_text_is_a_single_token():
    assert ('11998', 'TP53') in matches('TP53')


def test_substring_of_a_longer_word_does_not_match():
    """The reason delimiters exist at all -- ARID1A must not yield AR."""
    assert matches('ARID1A was measured') == set()


@pytest.mark.parametrize('text', [
    'the TP53 gene', '(TP53)', '[TP53]', 'TP53, and others', 'TP53. Next',
])
def test_each_delimiter_bounds_a_match(text):
    assert ('11998', 'TP53') in matches(text)


def test_hyphen_is_not_a_boundary():
    """Deliberate: the delimiter set is unchanged from the old expansion.

    Widening it (to catch 'TP53-mediated') would alter recall and belongs in its
    own measured change, not in a structural swap.
    """
    assert matches('TP53-mediated apoptosis') == set()


def test_delimiter_set_is_the_documented_one():
    assert DELIMITERS == frozenset(' ()[],.')


def test_is_boundary_at_edges():
    assert _is_boundary('abc', -1)
    assert _is_boundary('abc', 3)
    assert not _is_boundary('abc', 1)


# --- Multiple and overlapping matches --------------------------------------

def test_all_occurrences_are_reported():
    found = list(GeneAutomaton(SIMPLE).find('TP53 and later TP53 again'))
    assert len(found) == 2


def test_multiple_distinct_genes_in_one_text():
    assert matches('TP53 and BRCA1 both respond') == {
        ('11998', 'TP53'), ('1100', 'BRCA1'),
    }


def test_shorter_token_ending_inside_a_longer_one_is_found():
    """Failure-link traversal: 'AR' ends inside 'RAR' at the same position."""
    auto = GeneAutomaton({'RAR': '1', 'AR': '2'})
    found = {(g, 'x') for _, _, g in auto.find('the RAR receptor')}
    assert ('1', 'x') in found  # RAR is delimiter-bounded; AR is not


# --- Construction ----------------------------------------------------------

def test_retired_tokens_are_not_added():
    """Contested tokens resolved to None cost nothing at scan time."""
    auto = GeneAutomaton({'TP53': '11998', 'XX': None})
    assert len(auto) == 1
    assert matches('XX was measured', {'TP53': '11998', 'XX': None}) == set()


def test_empty_index_matches_nothing():
    assert list(GeneAutomaton({}).find('TP53 and BRCA1')) == []


def test_empty_text_matches_nothing():
    assert list(GeneAutomaton(SIMPLE).find('')) == []


# --- Context window --------------------------------------------------------

def test_context_window_snaps_to_whole_words():
    """A fixed character window can sever a cue and flip the verdict.

    An observed match had 'over-expression' truncated to 'over-expressio',
    losing the cue on one character.
    """
    text = 'x' * 40 + ' over-expression of STZ diabetic mice was observed'
    start = text.index('STZ')
    window = _context_window(text, start, start + 3, radius=15)

    assert 'over-expression' in window
    assert not window.startswith('ression')


def test_context_window_respects_text_edges():
    text = 'TP53 induced'
    assert _context_window(text, 0, 4, radius=100) == text
