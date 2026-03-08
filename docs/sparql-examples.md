# SPARQL Example Queries for AOP-Wiki RDF

This document provides curated SPARQL queries for querying the AOP-Wiki RDF dataset. These queries are designed to work against the current schema using `owl:sameAs` cross-references and numeric HGNC identifiers.

## SPARQL Endpoint

The public SPARQL endpoint is available at:

```
https://aopwiki.rdf.bigcat-bioinformatics.org/sparql/
```

You can also run these queries against a local Virtuoso instance loaded with the AOP-Wiki RDF files. See the project README for local setup instructions.

## Prefix Declarations

Most queries below use these common prefixes:

```sparql
PREFIX aopo: <http://aopkb.org/aop_ontology#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX edam: <http://edamontology.org/>
PREFIX cheminf: <http://semanticscience.org/resource/CHEMINF_>
PREFIX nci: <http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#>
PREFIX ncbitaxon: <http://purl.bioontology.org/ontology/NCBITAXON/>
PREFIX hgnc: <https://identifiers.org/hgnc/>
PREFIX cas: <https://identifiers.org/cas/>
```

---

## 1. List All Adverse Outcome Pathways

Retrieve all AOPs with their titles and page links.

```sparql
SELECT ?aop ?title ?page
WHERE {
  ?aop a aopo:AdverseOutcomePathway ;
       dc:title ?title ;
       foaf:page ?page .
}
ORDER BY ?aop
```

## 2. Get Key Events for a Specific AOP

Find all Key Events belonging to AOP 12, including their titles.

```sparql
SELECT ?ke ?keTitle
WHERE {
  <https://identifiers.org/aop/12> aopo:has_key_event ?ke .
  ?ke dc:title ?keTitle .
}
ORDER BY ?ke
```

## 3. Find AOPs Associated with a Specific Chemical by CAS Number

Search for AOPs linked to Bisphenol A (CAS 80-05-7) through stressors.

```sparql
SELECT DISTINCT ?aop ?aopTitle ?stressor ?chemName
WHERE {
  ?chem a cheminf:000000 ;
        dc:title ?chemName ;
        cheminf:000446 cas:80-05-7 .
  ?stressor aopo:has_chemical_entity ?chem .
  ?aop a aopo:AdverseOutcomePathway ;
       nci:C54571 ?stressor ;
       dc:title ?aopTitle .
}
ORDER BY ?aop
```

## 4. Get Gene Associations for a Key Event

Find genes mapped to Key Event 888 from text mining of its description.

```sparql
SELECT ?gene ?geneLabel
WHERE {
  <https://identifiers.org/aop.events/888> edam:data_1025 ?gene .
  ?gene rdfs:label ?geneLabel .
}
ORDER BY ?geneLabel
```

## 5. List All Key Event Relationships with Upstream and Downstream Events

```sparql
SELECT ?ker ?upstreamKE ?upstreamTitle ?downstreamKE ?downstreamTitle
WHERE {
  ?ker a aopo:KeyEventRelationship ;
       aopo:has_upstream_key_event ?upstreamKE ;
       aopo:has_downstream_key_event ?downstreamKE .
  ?upstreamKE dc:title ?upstreamTitle .
  ?downstreamKE dc:title ?downstreamTitle .
}
ORDER BY ?ker
LIMIT 100
```

## 6. Find Chemicals with Cross-References to External Databases

List chemicals that have `owl:sameAs` links to external identifiers (from `AOPWikiRDF-Enriched.ttl`).

```sparql
SELECT ?chemical ?chemName (GROUP_CONCAT(DISTINCT ?xref; separator=", ") AS ?crossRefs)
WHERE {
  ?chemical a cheminf:000000 ;
            dc:title ?chemName .
  ?chemical owl:sameAs ?xref .
}
GROUP BY ?chemical ?chemName
ORDER BY ?chemName
LIMIT 50
```

## 7. Count Entities by Type

Get counts of all major entity types in the dataset.

```sparql
SELECT
  (COUNT(DISTINCT ?aop) AS ?AOPs)
  (COUNT(DISTINCT ?ke) AS ?KeyEvents)
  (COUNT(DISTINCT ?ker) AS ?KERs)
  (COUNT(DISTINCT ?stressor) AS ?Stressors)
  (COUNT(DISTINCT ?chemical) AS ?Chemicals)
WHERE {
  { ?aop a aopo:AdverseOutcomePathway }
  UNION { ?ke a aopo:KeyEvent }
  UNION { ?ker a aopo:KeyEventRelationship }
  UNION { ?stressor a nci:C54571 }
  UNION { ?chemical a cheminf:000000 }
}
```

## 8. Find AOPs by Taxonomic Applicability

Find AOPs applicable to a specific species (e.g., Homo sapiens, NCBI Taxon 9606).

```sparql
SELECT DISTINCT ?aop ?aopTitle ?speciesName
WHERE {
  ?aop a aopo:AdverseOutcomePathway ;
       dc:title ?aopTitle ;
       aopo:has_key_event ?ke .
  ?ke ncbitaxon:131567 ?taxon .
  ?taxon a ncbitaxon:131567 ;
         dc:title ?speciesName .
  FILTER(CONTAINS(?speciesName, "Homo sapiens"))
}
ORDER BY ?aop
```

## 9. Find HGNC Genes with Their Cross-Reference Identifiers

List HGNC genes and their mapped Entrez, Ensembl, and UniProt identifiers.

```sparql
SELECT ?gene ?symbol ?xrefId ?xrefSource
WHERE {
  ?gene a edam:data_2298 ;
        rdfs:label ?symbol ;
        owl:sameAs ?xref .
  ?xref dc:identifier ?xrefId ;
        dc:source ?xrefSource .
}
ORDER BY ?symbol
LIMIT 50
```

## 10. Find Key Events with Specific Biological Organization Level

List Key Events that have cell type or organ context annotations.

```sparql
SELECT ?ke ?keTitle ?cellType ?cellTitle ?organ ?organTitle
WHERE {
  ?ke a aopo:KeyEvent ;
      dc:title ?keTitle .
  OPTIONAL {
    ?ke aopo:CellTypeContext ?cellType .
    ?cellType dc:title ?cellTitle .
  }
  OPTIONAL {
    ?ke aopo:OrganContext ?organ .
    ?organ dc:title ?organTitle .
  }
  FILTER(BOUND(?cellType) || BOUND(?organ))
}
ORDER BY ?ke
LIMIT 50
```
