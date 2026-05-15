"""Unit tests for the XML parser module.

Tests cover:
1. Import safety (no side effects)
2. Return type (ParsedEntities dataclass)
3. All 13 entity dictionary attributes present
4. Reference extraction (refs dict keys)
5. AOP extraction from fixture
6. Graceful handling of missing/empty optional elements
"""

import pytest


def test_import_no_side_effects():
    """parse_aopwiki_xml and ParsedEntities can be imported without side effects."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml, ParsedEntities
    assert callable(parse_aopwiki_xml)
    assert ParsedEntities is not None


def test_returns_parsed_entities(sample_xml_path):
    """parse_aopwiki_xml(fixture_path) returns a ParsedEntities instance."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml, ParsedEntities
    result = parse_aopwiki_xml(sample_xml_path)
    assert isinstance(result, ParsedEntities)


def test_parsed_entities_has_all_attributes(sample_xml_path):
    """ParsedEntities has all 13 expected attributes."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    result = parse_aopwiki_xml(sample_xml_path)
    expected_attrs = [
        'refs', 'aopdict', 'kedict', 'kerdict', 'stressordict',
        'chemicaldict', 'taxdict', 'celldict', 'organdict',
        'bpdict', 'bodict', 'badict', 'prodict',
    ]
    for attr in expected_attrs:
        assert hasattr(result, attr), f"Missing attribute: {attr}"


def test_refs_dict_keys(sample_xml_path):
    """refs dict contains expected keys ('AOP', 'KE', 'KER', 'Stressor')."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    result = parse_aopwiki_xml(sample_xml_path)
    for key in ('AOP', 'KE', 'KER', 'Stressor'):
        assert key in result.refs, f"Missing refs key: {key}"


def test_parser_extracts_aops(sample_xml_path):
    """Parser extracts at least 1 AOP from the fixture."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    result = parse_aopwiki_xml(sample_xml_path)
    assert len(result.aopdict) >= 1, "Expected at least 1 AOP"
    assert len(result.refs['AOP']) >= 1, "Expected at least 1 AOP reference"


def test_handles_empty_optional_elements(sample_xml_path):
    """Parser handles empty/missing optional elements gracefully."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    result = parse_aopwiki_xml(sample_xml_path)
    # KE 101 has empty applicability and biological-events;
    # parser should not crash and should still have basic fields
    assert '101' in result.kedict
    assert 'dc:identifier' in result.kedict['101']


def test_parses_wiki_license_by_sa(sample_xml_path):
    """AOP with <wiki-license>BY-SA</wiki-license> populates _wiki_license."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    result = parse_aopwiki_xml(sample_xml_path)
    assert result.aopdict['1'].get('_wiki_license') == 'BY-SA'


def test_parses_wiki_license_arr(sample_xml_path):
    """AOP with <wiki-license>ARR</wiki-license> populates _wiki_license."""
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml
    result = parse_aopwiki_xml(sample_xml_path)
    assert result.aopdict['2'].get('_wiki_license') == 'ARR'


def test_missing_wiki_license_absent(sample_xml_path, tmp_path):
    """AOP without <wiki-license> does not populate _wiki_license (no KeyError)."""
    import shutil
    from aopwiki_rdf.parser.xml_parser import parse_aopwiki_xml

    src = tmp_path / "no_licence.xml"
    text = open(sample_xml_path).read()
    text = text.replace('<wiki-license>BY-SA</wiki-license>', '')
    text = text.replace('<wiki-license>ARR</wiki-license>', '')
    src.write_text(text)
    result = parse_aopwiki_xml(str(src))
    assert '_wiki_license' not in result.aopdict['1']
    assert '_wiki_license' not in result.aopdict['2']
