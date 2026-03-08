"""Generate SHACL shape files from audit-results.json.

This script reads the property population audit and generates
data-driven SHACL shapes with severity thresholds based on actual
population rates.
"""

import json
import os
import textwrap

# Common prefixes for all shape files
COMMON_PREFIXES = """\
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix aopo: <http://aopkb.org/aop_ontology#> .
@prefix nci: <http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#> .
@prefix cheminf: <http://semanticscience.org/resource/CHEMINF_> .
@prefix edam: <http://edamontology.org/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ncbitaxon: <http://purl.bioontology.org/ontology/NCBITAXON/> .
@prefix pato: <http://purl.obolibrary.org/obo/PATO_> .
@prefix go: <http://purl.obolibrary.org/obo/GO_> .
@prefix mmo: <http://purl.obolibrary.org/obo/MMO_> .
@prefix hgnc: <https://identifiers.org/hgnc/> .
@prefix uniprot: <https://identifiers.org/uniprot/> .
@prefix ncbigene: <https://identifiers.org/ncbigene/> .
@prefix ensembl: <https://identifiers.org/ensembl/> .
"""

# Shape namespace
SHAPES_NS = "https://aopwiki.rdf.bigcat-bioinformatics.org/shapes/"


def prop_to_prefixed(uri):
    """Convert a full URI to a prefixed form if possible."""
    prefix_map = {
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/2002/07/owl#": "owl:",
        "http://purl.org/dc/elements/1.1/": "dc:",
        "http://purl.org/dc/terms/": "dcterms:",
        "http://xmlns.com/foaf/0.1/": "foaf:",
        "http://aopkb.org/aop_ontology#": "aopo:",
        "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#": "nci:",
        "http://semanticscience.org/resource/CHEMINF_": "cheminf:",
        "http://edamontology.org/": "edam:",
        "http://www.w3.org/2004/02/skos/core#": "skos:",
        "http://purl.bioontology.org/ontology/NCBITAXON/": "ncbitaxon:",
        "http://purl.obolibrary.org/obo/PATO_": "pato:",
        "http://purl.obolibrary.org/obo/GO_": "go:",
        "http://purl.obolibrary.org/obo/MMO_": "mmo:",
        "http://www.w3.org/ns/shacl#": "sh:",
        "https://identifiers.org/hgnc/": "hgnc:",
        "https://identifiers.org/uniprot/": "uniprot:",
        "https://identifiers.org/ncbigene/": "ncbigene:",
        "https://identifiers.org/ensembl/": "ensembl:",
    }
    for ns, prefix in prefix_map.items():
        if uri.startswith(ns):
            return prefix + uri[len(ns):]
    return f"<{uri}>"


def generate_property_shapes(properties, exclude_rdf_type=True):
    """Generate sh:property blocks from audit property data."""
    lines = []
    for prop_uri, prop_data in sorted(
        properties.items(), key=lambda x: -x[1]["percentage"]
    ):
        # Skip rdf:type -- it's implicit in sh:targetClass
        if exclude_rdf_type and prop_uri == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type":
            continue

        prefixed = prop_to_prefixed(prop_uri)
        severity = prop_data["severity"]
        pct = prop_data["percentage"]

        lines.append(f"    sh:property [")
        lines.append(f"        sh:path {prefixed} ;")

        if severity == "sh:Violation" and pct >= 90.0:
            lines.append(f"        sh:minCount 1 ;")

        lines.append(f"        sh:severity {severity} ;")
        lines.append(f'        sh:name "{prefixed} ({pct}%)" ;')
        lines.append(f"    ] ;")

    return "\n".join(lines)


def write_shape_file(filepath, content):
    """Write a shape file with common prefixes."""
    with open(filepath, "w") as f:
        f.write(content)
    print(f"  Written: {filepath}")


def generate_typed_shape(shape_name, target_class_prefixed, type_uri, audit_data, label):
    """Generate a shape for a typed entity class."""
    if type_uri not in audit_data:
        return None

    type_data = audit_data[type_uri]
    props = generate_property_shapes(type_data["properties"])

    content = f"""{COMMON_PREFIXES}
@prefix shapes: <{SHAPES_NS}> .

# SHACL Shape for {label}
# Generated from property population audit
# Instances: {type_data['instances']}

shapes:{shape_name}
    a sh:NodeShape ;
    sh:targetClass {target_class_prefixed} ;
    sh:name "{label}" ;
{props}
    .
"""
    return content


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    audit_path = os.path.join(base_dir, "scripts", "audit-results.json")
    shapes_dir = os.path.join(base_dir, "shapes")
    os.makedirs(shapes_dir, exist_ok=True)

    with open(audit_path) as f:
        audit = json.load(f)

    main_audit = audit.get("AOPWikiRDF.ttl", {})
    enriched_audit = audit.get("AOPWikiRDF-Enriched.ttl", {})

    # 1. AOP Shape
    content = generate_typed_shape(
        "AOPShape", "aopo:AdverseOutcomePathway",
        "http://aopkb.org/aop_ontology#AdverseOutcomePathway",
        main_audit, "Adverse Outcome Pathway"
    )
    if content:
        write_shape_file(os.path.join(shapes_dir, "aop-shape.ttl"), content)

    # 2. Key Event Shape
    content = generate_typed_shape(
        "KeyEventShape", "aopo:KeyEvent",
        "http://aopkb.org/aop_ontology#KeyEvent",
        main_audit, "Key Event"
    )
    if content:
        write_shape_file(os.path.join(shapes_dir, "key-event-shape.ttl"), content)

    # 3. KER Shape
    content = generate_typed_shape(
        "KERShape", "aopo:KeyEventRelationship",
        "http://aopkb.org/aop_ontology#KeyEventRelationship",
        main_audit, "Key Event Relationship"
    )
    if content:
        write_shape_file(os.path.join(shapes_dir, "ker-shape.ttl"), content)

    # 4. Stressor Shape
    content = generate_typed_shape(
        "StressorShape", "nci:C54571",
        "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#C54571",
        main_audit, "Stressor"
    )
    if content:
        write_shape_file(os.path.join(shapes_dir, "stressor-shape.ttl"), content)

    # 5. Chemical Shape (CHEMINF_000000 is the main chemical class)
    content = generate_typed_shape(
        "ChemicalShape", "cheminf:000000",
        "http://semanticscience.org/resource/CHEMINF_000000",
        main_audit, "Chemical Substance"
    )
    if content:
        write_shape_file(os.path.join(shapes_dir, "chemical-shape.ttl"), content)

    # 6. Gene Association Shape (edam:data_1025)
    content = generate_typed_shape(
        "GeneAssociationShape", "edam:data_1025",
        "http://edamontology.org/data_1025",
        main_audit, "Gene Association"
    )
    if content:
        write_shape_file(os.path.join(shapes_dir, "gene-association-shape.ttl"), content)

    # 7. Enriched Cross-reference Shape (untyped subjects with owl:sameAs)
    enriched_untyped = enriched_audit.get("_untyped_subjects")
    if enriched_untyped:
        props = generate_property_shapes(enriched_untyped["properties"], exclude_rdf_type=False)
        content = f"""{COMMON_PREFIXES}
@prefix shapes: <{SHAPES_NS}> .

# SHACL Shape for Enriched Cross-References
# Generated from property population audit
# Instances: {enriched_untyped['instances']}
# Note: These subjects have no rdf:type; targeted by owl:sameAs predicate

shapes:EnrichedXrefShape
    a sh:NodeShape ;
    sh:targetSubjectsOf owl:sameAs ;
    sh:name "Enriched Cross-Reference" ;
{props}
    .
"""
        write_shape_file(os.path.join(shapes_dir, "enriched-xref-shape.ttl"), content)

    print("\nAll shape files generated successfully.")


if __name__ == "__main__":
    main()
