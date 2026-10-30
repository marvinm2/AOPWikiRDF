"""Schema statistics for the VoID description (issue #121).

Computes the nested partition tree used by the SIB void-generator and read by
rdfsolve and the SPARQL editor:

    dataset  void:classPartition     [ void:class C ; void:entities n ;
      void:propertyPartition [ void:property P ; void:triples n ;
        void:classPartition       [ void:class O ; void:triples n ] ;
        void-ext:datatypePartition [ void-ext:datatype D ; void:triples n ] ] ]

plus dataset-level property partitions and the summary counts
(void:triples, void:entities, void:classes, void:properties,
void:distinctSubjects, void:distinctObjects, void:vocabulary).

The statistics describe the union of the three data files, which is what is
loaded into the data graph. Everything is returned sorted so the VoID is
byte-stable for identical input.
"""

import hashlib
import logging
import re
from collections import defaultdict

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

logger = logging.getLogger(__name__)

RDF_LANGSTRING = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")


def load_graph(filepaths):
    """Parse the given Turtle files into one rdflib Graph."""
    g = Graph()
    for path in filepaths:
        g.parse(path, format="turtle")
    return g


def data_file_void_stats(directory):
    """Compute VoID statistics over the three data files in ``directory``.

    These are the files loaded into the data graph; the VoID itself is
    excluded.
    """
    graph = load_graph([
        directory + "AOPWikiRDF.ttl",
        directory + "AOPWikiRDF-Enriched.ttl",
        directory + "AOPWikiRDF-Genes.ttl",
    ])
    return compute_void_stats(graph)


def namespace_of(iri):
    """Return the namespace part of an IRI (up to the last '#' or '/')."""
    iri = str(iri)
    cut = max(iri.rfind("#"), iri.rfind("/"))
    return iri[:cut + 1] if cut > 0 else iri


_IDENTIFIERS_ORG = re.compile(r"^https?://identifiers\.org/([^/:]+)[/:]")
_OBO = re.compile(r"^http://purl\.obolibrary\.org/obo/([A-Za-z]+)_")


def link_target(iri):
    """Return the external dataset an object IRI points into, or None.

    Covers identifiers.org collections (other than AOP-Wiki's own aop.*
    namespaces), UniProt PURLs and OBO ontology terms; those are the external
    datasets the data links to with stable IRIs. Used for the void:Linkset
    descriptions.
    """
    iri = str(iri)
    m = _IDENTIFIERS_ORG.match(iri)
    if m:
        collection = m.group(1)
        if collection == "aop" or collection.startswith("aop."):
            return None
        return "https://registry.identifiers.org/registry/" + collection
    if iri.startswith("http://purl.uniprot.org/uniprot/"):
        return "https://registry.identifiers.org/registry/uniprot"
    m = _OBO.match(iri)
    if m:
        return "http://purl.obolibrary.org/obo/" + m.group(1).lower() + ".owl"
    return None


def partition_id(*parts):
    """Stable short identifier for a partition, derived from its key."""
    key = "\x1f".join(str(p) for p in parts)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _literal_datatype(lit):
    if lit.datatype is not None:
        return lit.datatype
    return RDF_LANGSTRING if lit.language else XSD.string


def compute_void_stats(graph):
    """Compute VoID summary counts and the nested partition tree.

    Parameters
    ----------
    graph : rdflib.Graph
        The data triples (without the VoID itself).

    Returns
    -------
    dict
        ``triples``, ``entities``, ``classes``, ``properties``,
        ``distinct_subjects``, ``distinct_objects``: ints.
        ``vocabularies``: sorted list of namespace IRIs (str).
        ``class_partitions``: list of dicts ``{class, entities, properties}``
        where ``properties`` is a list of ``{property, triples,
        object_classes: [(class, n)], datatypes: [(datatype, n)]}``.
        ``property_partitions``: list of ``{property, triples,
        distinct_subjects, distinct_objects}``.
        ``linksets``: list of ``{target, property, triples}``, one per
        external dataset (see ``link_target``) and linking property.
        All lists sorted by IRI.
    """
    types = defaultdict(set)
    for s, o in graph.subject_objects(RDF.type):
        if isinstance(o, URIRef):
            types[s].add(o)

    class_entities = defaultdict(int)
    for s, classes in types.items():
        for c in classes:
            class_entities[c] += 1

    cp_triples = defaultdict(int)            # (class, property) -> n
    cp_objclass = defaultdict(int)           # (class, property, objclass) -> n
    cp_datatype = defaultdict(int)           # (class, property, datatype) -> n
    p_triples = defaultdict(int)
    p_subjects = defaultdict(set)
    p_objects = defaultdict(set)
    links = defaultdict(int)                 # (target, property) -> n
    subjects = set()
    objects = set()

    for s, p, o in graph:
        subjects.add(s)
        objects.add(o)
        p_triples[p] += 1
        p_subjects[p].add(s)
        p_objects[p].add(o)
        if isinstance(o, URIRef) and p != RDF.type:
            target = link_target(o)
            if target:
                links[(target, p)] += 1

        s_classes = types.get(s)
        if not s_classes:
            continue
        if isinstance(o, Literal):
            dt = _literal_datatype(o)
            for c in s_classes:
                cp_triples[(c, p)] += 1
                cp_datatype[(c, p, dt)] += 1
        else:
            o_classes = types.get(o, ())
            for c in s_classes:
                cp_triples[(c, p)] += 1
                for oc in o_classes:
                    cp_objclass[(c, p, oc)] += 1

    props_by_class = defaultdict(dict)
    for (c, p), n in cp_triples.items():
        props_by_class[c][p] = {
            "property": p, "triples": n, "object_classes": [], "datatypes": [],
        }
    for (c, p, oc), n in cp_objclass.items():
        props_by_class[c][p]["object_classes"].append((oc, n))
    for (c, p, dt), n in cp_datatype.items():
        props_by_class[c][p]["datatypes"].append((dt, n))

    class_partitions = []
    for c in sorted(class_entities, key=str):
        props = []
        for p in sorted(props_by_class[c], key=str):
            entry = props_by_class[c][p]
            entry["object_classes"].sort(key=lambda x: str(x[0]))
            entry["datatypes"].sort(key=lambda x: str(x[0]))
            props.append(entry)
        class_partitions.append(
            {"class": c, "entities": class_entities[c], "properties": props}
        )

    property_partitions = [
        {
            "property": p,
            "triples": p_triples[p],
            "distinct_subjects": len(p_subjects[p]),
            "distinct_objects": len(p_objects[p]),
        }
        for p in sorted(p_triples, key=str)
    ]

    vocabularies = sorted(
        {namespace_of(p) for p in p_triples} | {namespace_of(c) for c in class_entities}
    )

    stats = {
        "triples": len(graph),
        "entities": len(types),
        "classes": len(class_entities),
        "properties": len(p_triples),
        "distinct_subjects": len(subjects),
        "distinct_objects": len(objects),
        "vocabularies": vocabularies,
        "class_partitions": class_partitions,
        "property_partitions": property_partitions,
        "linksets": [
            {"target": t, "property": p, "triples": n}
            for (t, p), n in sorted(links.items(), key=lambda x: (x[0][0], str(x[0][1])))
        ],
    }
    logger.info(
        "VoID stats: %d triples, %d entities, %d classes, %d properties",
        stats["triples"], stats["entities"], stats["classes"], stats["properties"],
    )
    return stats
