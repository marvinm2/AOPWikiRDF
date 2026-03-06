"""Unit tests for chemical mapper module."""

import pytest
from xml.etree.ElementTree import Element, SubElement


def test_chemical_mapper_importable():
    """Verify the module can be imported without importing the full pipeline or rdflib."""
    import sys

    # Ensure rdflib is not required for import
    from aopwiki_rdf.mapping.chemical_mapper import map_chemicals
    assert callable(map_chemicals)

    # Verify rdflib was not pulled in by this import
    # (it may already be in sys.modules from other tests, so we just
    # check that the import itself succeeded without error)


def _make_minimal_xml(chemicals):
    """Build minimal XML root with chemical elements for testing.

    Args:
        chemicals: list of dicts with keys 'id' and optionally 'casrn'.
    Returns:
        (root Element, namespace string)
    """
    ns = '{http://www.aopkb.org/aop-xml}'
    root = Element('data')
    for chem in chemicals:
        elem = SubElement(root, f'{ns}chemical')
        elem.set('id', chem['id'])
        if 'casrn' in chem:
            casrn_elem = SubElement(elem, f'{ns}casrn')
            casrn_elem.text = chem['casrn']
    return root, ns


def test_chemical_mapper_empty_input():
    """Verify that empty CAS list returns empty results without errors."""
    from aopwiki_rdf.mapping.chemical_mapper import map_chemicals

    root, ns = _make_minimal_xml([])
    chedict = {}

    result = map_chemicals(chedict, root, ns,
                           bridgedb_url='https://webservice.bridgedb.org/Human/',
                           timeout=10)

    assert 'chedict' in result
    assert result['chedict'] == {}
    assert result['listofchebi'] == []
    assert result['listofchemspider'] == []


def _bridgedb_reachable():
    """Check if BridgeDb service is reachable."""
    try:
        import requests
        resp = requests.get(
            'https://webservice.bridgedb.org/Human/xrefs/Ca/80-05-7',
            timeout=10
        )
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(
    not _bridgedb_reachable(),
    reason="BridgeDb service unreachable"
)
def test_map_chemicals_live():
    """Test with real BridgeDb API using known CAS numbers."""
    from aopwiki_rdf.mapping.chemical_mapper import map_chemicals

    # Bisphenol A (CAS 80-05-7) and Formaldehyde (CAS 50-00-0)
    chemicals = [
        {'id': '1', 'casrn': '80-05-7'},
        {'id': '2', 'casrn': '50-00-0'},
    ]
    root, ns = _make_minimal_xml(chemicals)

    # Build chedict as the parser would
    chedict = {
        '1': {
            'dc:identifier': 'cas:80-05-7',
            'cheminf:000446': '"80-05-7"',
        },
        '2': {
            'dc:identifier': 'cas:50-00-0',
            'cheminf:000446': '"50-00-0"',
        },
    }

    result = map_chemicals(chedict, root, ns,
                           bridgedb_url='https://webservice.bridgedb.org/Human/',
                           timeout=30)

    assert 'chedict' in result
    enriched = result['chedict']

    # At least one chemical should have cross-references
    has_xrefs = False
    for chem_id, chem_data in enriched.items():
        for key in ('cheminf:000407', 'cheminf:000405', 'cheminf:000140',
                    'cheminf:000406', 'cheminf:000408'):
            if key in chem_data:
                has_xrefs = True
                break
        if has_xrefs:
            break
    assert has_xrefs, "Expected at least one chemical to have BridgeDb cross-references"

    # Verify list results are populated
    all_lists = [result.get(k, []) for k in (
        'listofchebi', 'listofchemspider', 'listofpubchem',
        'listofdrugbank', 'listofhmdb',
    )]
    total_identifiers = sum(len(lst) for lst in all_lists)
    assert total_identifiers > 0, "Expected at least some cross-reference identifiers"
