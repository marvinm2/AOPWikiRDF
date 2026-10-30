"""Tests for VoID class/property partitions (issue #121) and the
ServiceDescription named-graph link (issue #124)."""

import datetime

from rdflib import Graph, URIRef
from rdflib.namespace import XSD

from aopwiki_rdf.rdf.void_stats import compute_void_stats, link_target, partition_id
from aopwiki_rdf.rdf.writer import write_void_rdf

FIXTURE = """
@prefix aopo: <http://aopkb.org/aop_ontology#> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix ex: <https://example.org/> .

ex:aop1 a aopo:AdverseOutcomePathway ;
    dc:title "AOP one" ;
    aopo:has_key_event ex:ke1, ex:ke2 .
ex:ke1 a aopo:KeyEvent ;
    dc:title "KE one", "KE eins"@de ;
    dcterms:isPartOf ex:aop1 .
ex:ke2 a aopo:KeyEvent ;
    dc:title "KE two" ;
    aopo:hasBiologicalEvent ex:untyped .
"""

AOPO = "http://aopkb.org/aop_ontology#"

# The pattern query rdfsolve runs against a provider VoID
# (rdfsolve/schema_models/readers/void.py).
RDFSOLVE_READER = """
PREFIX void: <http://rdfs.org/ns/void#>
PREFIX void-ext: <http://ldf.fi/void-ext#>
SELECT ?subjectClass ?property ?objectClass ?datatype ?count WHERE {
  ?dataset void:classPartition ?cp . ?cp void:class ?subjectClass .
  ?cp void:propertyPartition ?pp . ?pp void:property ?property .
  { ?pp void:classPartition ?objCp . ?objCp void:class ?objectClass .
    OPTIONAL { ?objCp void:triples ?count } }
  UNION
  { ?pp void-ext:datatypePartition ?dp . ?dp void-ext:datatype ?datatype .
    OPTIONAL { ?dp void:triples ?count } }
}
"""


def _stats():
    return compute_void_stats(Graph().parse(data=FIXTURE, format="turtle"))


def _write(tmp_path, stats):
    metadata = {
        "aopwikixmlfilename": "aop-wiki-xml-2026-10-10",
        "date": "2026-10-13",
        "datetime_obj": datetime.datetime(2026, 10, 13, 12, 0, 0),
        "HGNCmodificationTime": "2026-10-10T08:00:00",
        "PromodificationTime": "Unknown",
        "service_desc_filepath": str(tmp_path / "ServiceDescription.ttl"),
        "void_stats": stats,
    }
    path = tmp_path / "AOPWikiRDF-Void.ttl"
    write_void_rdf(str(path), metadata)
    return path


def _partition(stats, cls):
    return next(cp for cp in stats["class_partitions"] if str(cp["class"]) == AOPO + cls)


def _prop(cp, prop):
    return next(pp for pp in cp["properties"] if str(pp["property"]) == prop)


def test_summary_counts():
    stats = _stats()
    assert stats["triples"] == 11
    assert stats["entities"] == 3
    assert stats["classes"] == 2
    assert stats["properties"] == 5


def test_class_partition_entities():
    stats = _stats()
    assert _partition(stats, "KeyEvent")["entities"] == 2
    assert _partition(stats, "AdverseOutcomePathway")["entities"] == 1


def test_datatype_partitions_split_plain_and_language_literals():
    ke = _partition(_stats(), "KeyEvent")
    title = _prop(ke, "http://purl.org/dc/elements/1.1/title")
    assert title["triples"] == 3
    assert dict(title["datatypes"]) == {
        XSD.string: 2,
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"): 1,
    }
    assert title["object_classes"] == []


def test_object_class_partition_and_untyped_object():
    aop = _partition(_stats(), "AdverseOutcomePathway")
    assert dict(_prop(aop, AOPO + "has_key_event")["object_classes"]) == {
        URIRef(AOPO + "KeyEvent"): 2
    }
    # An IRI object with no rdf:type counts towards the property partition
    # but gets no nested class partition.
    ke = _partition(_stats(), "KeyEvent")
    bio = _prop(ke, AOPO + "hasBiologicalEvent")
    assert bio["triples"] == 1
    assert bio["object_classes"] == [] and bio["datatypes"] == []


def test_partition_ids_are_stable():
    assert partition_id("a", "b") == partition_id("a", "b")
    assert partition_id("a", "b") != partition_id("ab")


def test_void_output_is_byte_stable(tmp_path):
    first = _write(tmp_path, _stats()).read_bytes()
    second = _write(tmp_path, _stats()).read_bytes()
    assert first == second


def test_rdfsolve_reader_finds_patterns(tmp_path):
    void = Graph().parse(_write(tmp_path, _stats()), format="turtle")
    rows = {
        (str(r.subjectClass), str(r.property), str(r.objectClass or r.datatype), int(r["count"]))
        for r in void.query(RDFSOLVE_READER)
    }
    assert (AOPO + "AdverseOutcomePathway", AOPO + "has_key_event", AOPO + "KeyEvent", 2) in rows
    assert (AOPO + "KeyEvent", "http://purl.org/dc/terms/isPartOf",
            AOPO + "AdverseOutcomePathway", 1) in rows
    assert (AOPO + "KeyEvent", "http://purl.org/dc/elements/1.1/title", str(XSD.string), 2) in rows


def test_imported_on_is_typed_when_iso(tmp_path):
    text = _write(tmp_path, _stats()).read_text()
    assert 'pav:importedOn\t"2026-10-10T08:00:00"^^xsd:dateTime' in text
    assert 'pav:importedOn\t"Unknown"' in text


def test_service_description_links_data_graph_to_void(tmp_path):
    _write(tmp_path, _stats())
    sd = Graph().parse(tmp_path / "ServiceDescription.ttl", format="turtle")
    rows = list(sd.query("""
        PREFIX sd: <http://www.w3.org/ns/sparql-service-description#>
        SELECT ?name ?graph WHERE {
          ?service sd:defaultDataset/sd:namedGraph ?ng .
          ?ng sd:name ?name ; sd:graph ?graph . }
    """))
    assert [(str(r.name), str(r.graph)) for r in rows] == [
        ("http://aopwiki.org/", "https://aopwiki.rdf.bigcat-bioinformatics.org/AOPWikiRDF")
    ]
    names = {str(n) for n in sd.objects(None, URIRef(
        "http://www.w3.org/ns/sparql-service-description#name"))}
    assert names == {"http://aopwiki.org/", "http://aopwiki.org/void",
                     "http://aopwiki.org/servicedescription"}


def test_yummydata_triple_count_is_not_inflated(tmp_path):
    """YummyData's data_entry sums void:triples over every subject typed
    void:Dataset (umakadata_gem rdf/void.rb). Only the three file subsets may
    contribute, so partitions stay untyped and the parent carries no total."""
    stats = _stats()
    path = tmp_path / "AOPWikiRDF-Void.ttl"
    write_void_rdf(str(path), {
        "aopwikixmlfilename": "aop-wiki-xml-2026-10-10",
        "date": "2026-10-13",
        "datetime_obj": datetime.datetime(2026, 10, 13, 12, 0, 0),
        "HGNCmodificationTime": "Unknown",
        "PromodificationTime": "Unknown",
        "void_stats": stats,
        "triple_counts": {"main": 5, "enriched": 2, "genes": 4},
    })
    void = Graph().parse(path, format="turtle")
    rows = list(void.query("""
        SELECT ?s ?triples WHERE {
          ?s a ?type ; <http://rdfs.org/ns/void#triples> ?triples .
          FILTER(?type = <http://rdfs.org/ns/void#Dataset>
              || ?type = <http://www.w3.org/ns/sparql-service-description#Dataset>
              || ?type = <http://www.w3.org/ns/sparql-service-description#Graph>) }
    """))
    assert sum(int(r.triples) for r in rows) == 11
    assert len(rows) == 3


LINK_FIXTURE = """
@prefix aopo: <http://aopkb.org/aop_ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix edam: <http://edamontology.org/> .

<https://identifiers.org/aop.stressor/1> a aopo:Stressor ;
    aopo:has_chemical_entity <https://identifiers.org/cas/50-00-0> .
<https://identifiers.org/cas/50-00-0>
    owl:sameAs <https://identifiers.org/chebi/CHEBI:16842>, <https://identifiers.org/wikidata/Q161210> ;
    skos:exactMatch <https://identifiers.org/chebi/CHEBI:16842> .
<https://identifiers.org/aop.events/1> a aopo:KeyEvent ;
    edam:data_1025 <https://identifiers.org/hgnc/1100>, <https://identifiers.org/hgnc/1101> ;
    aopo:hasProcess <http://purl.obolibrary.org/obo/GO_0006915> ;
    aopo:has_key_event <https://identifiers.org/aop.events/2> .
"""

# umakadata_gem lib/umakadata/rdf/void.rb, Query::LINK_SETS and Query::PUBLISHERS.
YUMMYDATA_LINK_SETS = """
SELECT DISTINCT ?target WHERE {
  { ?s a <http://rdfs.org/ns/void#Linkset> ; <http://rdfs.org/ns/void#target> ?target }
  UNION
  { ?s a <http://rdfs.org/ns/void#Linkset> ; <http://rdfs.org/ns/void#objectsTarget> ?target } }
"""
YUMMYDATA_PUBLISHERS = """
SELECT DISTINCT ?publisher WHERE {
  ?s <http://purl.org/dc/terms/publisher> ?publisher ;
     <http://rdfs.org/ns/void#sparqlEndpoint> <https://aopwiki.rdf.bigcat-bioinformatics.org/sparql> . }
"""


def _link_stats():
    return compute_void_stats(Graph().parse(data=LINK_FIXTURE, format="turtle"))


def test_link_target():
    assert link_target("https://identifiers.org/hgnc/1100") == \
        "https://registry.identifiers.org/registry/hgnc"
    assert link_target("https://identifiers.org/chebi/CHEBI:16842") == \
        "https://registry.identifiers.org/registry/chebi"
    assert link_target("http://purl.uniprot.org/uniprot/P04637") == \
        "https://registry.identifiers.org/registry/uniprot"
    assert link_target("http://purl.obolibrary.org/obo/GO_0006915") == \
        "http://purl.obolibrary.org/obo/go.owl"
    # AOP-Wiki's own namespaces and anything unrecognised are not links out.
    assert link_target("https://identifiers.org/aop/1") is None
    assert link_target("https://identifiers.org/aop.events/1") is None
    assert link_target("https://example.org/x") is None


def test_linksets_counted_per_target_and_property():
    rows = {(ls["target"], str(ls["property"])): ls["triples"]
            for ls in _link_stats()["linksets"]}
    reg = "https://registry.identifiers.org/registry/"
    assert rows == {
        (reg + "cas", AOPO + "has_chemical_entity"): 1,
        (reg + "chebi", "http://www.w3.org/2002/07/owl#sameAs"): 1,
        (reg + "chebi", "http://www.w3.org/2004/02/skos/core#exactMatch"): 1,
        (reg + "hgnc", "http://edamontology.org/data_1025"): 2,
        (reg + "wikidata", "http://www.w3.org/2002/07/owl#sameAs"): 1,
        ("http://purl.obolibrary.org/obo/go.owl", AOPO + "hasProcess"): 1,
    }


def test_yummydata_reads_linksets_and_publisher(tmp_path):
    void = Graph().parse(_write(tmp_path, _link_stats()), format="turtle")
    targets = {str(r.target) for r in void.query(YUMMYDATA_LINK_SETS)}
    assert "https://registry.identifiers.org/registry/hgnc" in targets
    assert len(targets) == 5
    assert [str(r.publisher) for r in void.query(YUMMYDATA_PUBLISHERS)] == \
        ["https://ror.org/02jz4aj89"]


def test_linksets_do_not_inflate_yummydata_triple_count(tmp_path):
    """Linksets carry void:triples but are typed void:Linkset only."""
    void = Graph().parse(_write(tmp_path, _link_stats()), format="turtle")
    rows = list(void.query("""
        SELECT ?s WHERE { ?s a <http://rdfs.org/ns/void#Dataset> ;
                             <http://rdfs.org/ns/void#triples> ?n }"""))
    assert rows == []
