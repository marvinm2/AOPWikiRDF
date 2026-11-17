"""Taxon normalisation and the taxonomy reference count (#145)."""

import json
import os
import shutil
import types

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DC, RDFS

from aopwiki_rdf.parser.taxonomy import classify, ncbi_taxid, normalise_taxa, taxonomy_report
from aopwiki_rdf.rdf.writer import write_aop_rdf
from run_conversion import build_config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAXON = URIRef('http://purl.bioontology.org/ontology/NCBITAXON/131567')
HUMAN = URIRef('http://purl.bioontology.org/ontology/NCBITAXON/9606')
ZEBRAFISH = URIRef('http://purl.bioontology.org/ontology/NCBITAXON/7955')
INSECTA = URIRef('http://purl.bioontology.org/ontology/NCBITAXON/50557')
AOP1 = URIRef('https://identifiers.org/aop/1')
BROWSER = 'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?command=show&mode=node&id=50557&lvl='


def _taxdict():
    # As parsed by xml_parser: NCBI terms are IRIs, everything else is quoted.
    return {
        't-hs': {'dc:source': 'NCBI', 'dc:title': 'Homo sapiens', 'dc:identifier': 'ncbitaxon:9606'},
        't-human': {'dc:source': 'common toxicological species', 'dc:title': 'human', 'dc:identifier': '"WCS_9606"'},
        't-zf': {'dc:source': 'common ecological species', 'dc:title': 'zebrafish', 'dc:identifier': '"WCS_7955"'},
        't-ins': {'dc:source': BROWSER, 'dc:title': 'Insecta', 'dc:identifier': '"50557"'},
        't-wu': {'dc:source': 'ApacheUser', 'dc:title': 'all species', 'dc:identifier': '"WikiUser_22"'},
        't-odd': {'dc:source': 'something else', 'dc:title': 'odd', 'dc:identifier': '"X1"'},
    }


def _appl(taxdict, *tax_ids):
    return [[t, 'High', taxdict[t]['dc:identifier'], taxdict[t]['dc:source'], taxdict[t]['dc:title']] for t in tax_ids]


def _parsed():
    taxdict = _taxdict()
    return types.SimpleNamespace(
        taxdict=taxdict,
        aopdict={'1': {'ncbitaxon:131567': _appl(taxdict, 't-hs', 't-human', 't-zf', 't-wu')}},
        kedict={'1': {'ncbitaxon:131567': _appl(taxdict, 't-ins', 't-wu')}},
        kerdict={'1': {'ncbitaxon:131567': _appl(taxdict, 't-odd')}},
    )


def test_ncbi_taxid_from_wcs_and_browser_urls():
    assert ncbi_taxid('common ecological species', 'WCS_7955') == '7955'
    assert ncbi_taxid(BROWSER, '50557') == '50557'
    # The taxid is in the URL even when the source-id field says something else.
    assert ncbi_taxid(BROWSER.replace('50557', '8504'), 'NCBI') == '8504'
    assert ncbi_taxid('ApacheUser', 'WikiUser_22') is None
    assert ncbi_taxid('something else', 'WCS_12a') is None


def test_classify_before_normalisation():
    kinds = {k: classify(v) for k, v in _taxdict().items()}
    assert kinds == {'t-hs': 'ncbi', 't-human': 'ncbi_resolvable', 't-zf': 'ncbi_resolvable',
                     't-ins': 'ncbi_resolvable', 't-wu': 'wiki_user', 't-odd': 'other'}


def test_normalise_rewrites_terms_and_entity_references():
    parsed = _parsed()
    assert normalise_taxa(parsed) == 3
    assert parsed.taxdict['t-human']['dc:identifier'] == 'ncbitaxon:9606'
    assert parsed.taxdict['t-human']['_normalised_from'] == 'WCS_9606'
    assert parsed.taxdict['t-ins']['dc:identifier'] == 'ncbitaxon:50557'
    assert parsed.taxdict['t-wu']['dc:identifier'] == '"WikiUser_22"'
    assert [a[2] for a in parsed.aopdict['1']['ncbitaxon:131567']] == [
        'ncbitaxon:9606', 'ncbitaxon:9606', 'ncbitaxon:7955', '"WikiUser_22"']
    assert [a[2] for a in parsed.kedict['1']['ncbitaxon:131567']] == ['ncbitaxon:50557', '"WikiUser_22"']


def test_report_counts_references_by_kind_and_lists_wiki_users(tmp_path):
    parsed = _parsed()
    before = taxonomy_report(parsed)
    assert before['total'] == {'ncbi': 1, 'normalised': 0, 'ncbi_resolvable': 3, 'wiki_user': 2, 'other': 1}
    normalise_taxa(parsed)
    path = tmp_path / 'taxonomy-report.json'
    after = taxonomy_report(parsed, report_path=str(path))
    assert after['total'] == {'ncbi': 1, 'normalised': 3, 'ncbi_resolvable': 0, 'wiki_user': 2, 'other': 1}
    assert after['references']['key_event'] == {'ncbi': 0, 'normalised': 1, 'ncbi_resolvable': 0, 'wiki_user': 1, 'other': 0}
    assert after['wiki_user_terms'] == [{'taxonomy_id': 't-wu', 'source_id': 'WikiUser_22', 'name': 'all species', 'uses': 2}]
    assert json.loads(path.read_text()) == after


def _entities(parsed):
    lists = {k: [] for k in (
        'hgnclist', 'ncbigenelist', 'uniprotlist', 'listofcas', 'listofinchikey', 'listofcomptox', 'listofchebi',
        'listofchemspider', 'listofwikidata', 'listofchembl', 'listofpubchem', 'listofdrugbank', 'listofkegg',
        'listoflipidmaps', 'listofhmdb')}
    aop = {
        'dc:identifier': 'aop:1', 'rdfs:label': '"AOP 1"', 'foaf:page': '<https://aopwiki.org/aops/1>',
        'dc:title': '"Test AOP"', 'dcterms:alternative': 'Short', 'dc:source': 'AOPWiki',
        'dcterms:created': '2016-11-29T18:41:50', 'dcterms:modified': '2024-01-01T09:30:00',
        'aopo:has_key_event': {}, 'aopo:has_key_event_relationship': {},
        'ncbitaxon:131567': parsed.aopdict['1']['ncbitaxon:131567'],
    }
    return {
        'aopdict': {'1': aop}, 'kedict': {}, 'kerdict': {}, 'strdict': {}, 'taxdict': parsed.taxdict,
        'bioactdict': {}, 'bioobjdict': {}, 'prodict': {}, 'chedict': {}, 'bioprodict': {},
        'symbol_lookup': {}, 'chem_label_by_iri': {}, 'gene_label_by_iri': {}, **lists,
    }


def _write(tmp_path, name, normalise, labels=True, config=True):
    parsed = _parsed()
    if normalise:
        normalise_taxa(parsed)
    shutil.copy(os.path.join(PROJECT_ROOT, 'data', 'typelabels.txt'), tmp_path / 'typelabels.txt')
    cfg = types.SimpleNamespace(normalise_taxa=normalise, enable_iri_labels=labels,
                                emit_legacy_predicates=False, enable_bern2=False) if config else None
    out = tmp_path / name
    write_aop_rdf(str(out), _entities(parsed), os.path.join(PROJECT_ROOT, 'prefixes.csv'), config=cfg)
    return out


def _graph(path):
    graph = Graph()
    graph.parse(str(path), format='turtle')
    return graph


def test_normalised_output_has_iris_and_one_node_per_taxon(tmp_path):
    path = _write(tmp_path, 'on.ttl', normalise=True)
    graph = _graph(path)
    assert set(graph.objects(AOP1, TAXON)) == {HUMAN, ZEBRAFISH, Literal('WikiUser_22')}
    assert sorted(str(t) for t in graph.objects(HUMAN, DC.title)) == ['Homo sapiens', 'human']
    assert list(graph.objects(HUMAN, RDFS.label)) == [Literal('Homo sapiens')]
    assert list(graph.objects(ZEBRAFISH, RDFS.label)) == [Literal('zebrafish')]
    assert list(graph.objects(INSECTA, DC.source)) == [Literal(BROWSER)]
    text = path.read_text()
    assert text.count('ncbitaxon:9606\n\ta\tncbitaxon:131567') == 1
    assert 'ncbitaxon:9606, ncbitaxon:9606' not in text


def test_flag_off_output_is_unchanged(tmp_path):
    off = _write(tmp_path, 'off.ttl', normalise=False, labels=False).read_bytes()
    default = _write(tmp_path, 'default.ttl', normalise=False, config=False).read_bytes()
    assert off == default
    assert b'"WCS_9606"' in off


def test_cli_flag():
    assert build_config(['--normalise-taxa']).normalise_taxa is True
    assert build_config([]).normalise_taxa is False
