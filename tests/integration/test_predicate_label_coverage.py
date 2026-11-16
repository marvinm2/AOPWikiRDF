"""Every predicate in the committed production output has a label source.

Scans data/AOPWikiRDF.ttl (the weekly production build, made with
--enable-iri-labels) as a census of the predicates the writer emits, and checks
each one against the label sources: EXTERNAL_PREDICATE_LABELS, typelabels.txt
(class labels for dual-use IRIs) or a standard W3C vocabulary. A new predicate
without a label fails here instead of reaching the endpoint unlabelled.
"""

import csv
import os

import pytest
from rdflib import Graph

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN_TTL = os.path.join(PROJECT_ROOT, 'data', 'AOPWikiRDF.ttl')
STANDARD = (
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'http://www.w3.org/ns/shacl#',
    'http://www.w3.org/ns/prov#',
)


@pytest.mark.skipif(not os.path.exists(MAIN_TTL), reason='no production output in data/')
def test_every_predicate_in_the_main_file_has_a_label_source():
    from aopwiki_rdf.rdf.writer import EXTERNAL_PREDICATE_LABELS

    with open(os.path.join(PROJECT_ROOT, 'prefixes.csv')) as f:
        namespaces = {row['prefix']: row['uri'] for row in csv.DictReader(f)}
    with open(os.path.join(PROJECT_ROOT, 'data', 'typelabels.txt')) as f:
        labelled = {row['URI'].strip('<>') for row in csv.DictReader(f)}
    for curie in EXTERNAL_PREDICATE_LABELS:
        prefix, local = curie.split(':', 1)
        labelled.add(namespaces[prefix] + local)
    # Minted genes-file predicates carry their own labels (GENES_MINTED_PREDICATE_LABELS).
    labelled.add('https://aopwiki.rdf.bigcat-bioinformatics.org/geneDetectedByNER')
    labelled.add('https://aopwiki.rdf.bigcat-bioinformatics.org/geneDetectedByRegex')

    graph = Graph()
    graph.parse(MAIN_TTL, format='turtle')
    predicates = {str(p) for p in graph.predicates()}
    missing = sorted(p for p in predicates if p not in labelled and not p.startswith(STANDARD))
    assert missing == []
