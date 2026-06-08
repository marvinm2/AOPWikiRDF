"""All RDF namespace/prefix constants used by the AOP-Wiki RDF outputs.

Extracted from pipeline.py:
- Main RDF prefixes (line 1297, loaded from prefixes.csv)
- Genes RDF prefixes (line 2179, hardcoded)
- VoID RDF prefixes (line 2279, hardcoded)

The prefix strings are kept exactly as they appear in the monolith output
to guarantee byte-identical RDF files during the migration.
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Individual namespace URI constants (useful for SHACL, validation, etc.)
# ---------------------------------------------------------------------------

NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DCTERMS = "http://purl.org/dc/terms/"
NS_RDFS = "http://www.w3.org/2000/01/rdf-schema#"
NS_OWL = "http://www.w3.org/2002/07/owl#"
NS_FOAF = "http://xmlns.com/foaf/0.1/"
NS_AOP = "https://identifiers.org/aop/"
NS_AOP_EVENTS = "https://identifiers.org/aop.events/"
NS_AOP_RELATIONSHIPS = "https://identifiers.org/aop.relationships/"
NS_AOP_STRESSOR = "https://identifiers.org/aop.stressor/"
NS_AOPO = "http://aopkb.org/aop_ontology#"
NS_SKOS = "http://www.w3.org/2004/02/skos/core#"
NS_CAS = "https://identifiers.org/cas/"
NS_INCHIKEY = "https://identifiers.org/inchikey/"
NS_PATO = "http://purl.obolibrary.org/obo/PATO_"
NS_NCBITAXON = "http://purl.bioontology.org/ontology/NCBITAXON/"
NS_CL = "http://purl.obolibrary.org/obo/CL_"
NS_UBERON = "http://purl.obolibrary.org/obo/UBERON_"
NS_GO = "http://purl.obolibrary.org/obo/GO_"
NS_MI = "http://purl.obolibrary.org/obo/MI_"
NS_MP = "http://purl.obolibrary.org/obo/MP_"
NS_MESH = "http://purl.org/commons/record/mesh/"
NS_HP = "http://purl.obolibrary.org/obo/HP_"
NS_PCO = "http://purl.obolibrary.org/obo/PCO_"
NS_NBO = "http://purl.obolibrary.org/obo/NBO_"
NS_VT = "http://purl.obolibrary.org/obo/VT_"
NS_PR = "http://purl.obolibrary.org/obo/PR_"
NS_CHEBIO = "http://purl.obolibrary.org/obo/CHEBI_"
NS_FMA = "http://purl.obolibrary.org/obo/FMA_"
NS_CHEMINF = "http://semanticscience.org/resource/CHEMINF_"
NS_NCI = "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#"
NS_COMPTOX = "https://identifiers.org/comptox/"
NS_MMO = "http://purl.obolibrary.org/obo/MMO_"
NS_CHEBI = "https://identifiers.org/chebi/"
NS_CHEMSPIDER = "https://identifiers.org/chemspider/"
NS_WIKIDATA = "https://identifiers.org/wikidata/"
NS_CHEMBL_COMPOUND = "https://identifiers.org/chembl.compound/"
NS_PUBCHEM_COMPOUND = "https://identifiers.org/pubchem.compound/"
NS_DRUGBANK = "https://identifiers.org/drugbank/"
NS_KEGG_COMPOUND = "https://identifiers.org/kegg.compound/"
NS_LIPIDMAPS = "https://identifiers.org/lipidmaps/"
NS_HMDB = "https://identifiers.org/hmdb/"
NS_ENSEMBL = "https://identifiers.org/ensembl/"
NS_EDAM = "http://edamontology.org/"
NS_HGNC = "https://identifiers.org/hgnc/"
NS_NCBIGENE = "https://identifiers.org/ncbigene/"
NS_UNIPROT = "https://identifiers.org/uniprot/"
NS_RBO = "http://purl.obolibrary.org/obo/RBO_"
NS_IDO = "http://purl.obolibrary.org/obo/IDO_"
NS_SH = "http://www.w3.org/ns/shacl#"
NS_XSD = "http://www.w3.org/2001/XMLSchema#"
NS_VOID = "http://rdfs.org/ns/void#"
NS_PAV = "http://purl.org/pav/"
NS_DCAT = "http://www.w3.org/ns/dcat#"
NS_FREQ = "http://purl.org/cld/freq/"


# ---------------------------------------------------------------------------
# Main RDF prefixes (loaded from prefixes.csv)
# ---------------------------------------------------------------------------

def get_main_prefixes(prefix_csv_path: str) -> str:
    """Load prefixes from CSV and format as Turtle prefix block.

    Parameters
    ----------
    prefix_csv_path:
        Path to ``prefixes.csv`` (two columns: ``prefix``, ``uri``).

    Returns
    -------
    str
        Newline-joined ``@prefix ... .`` declarations ready to write to a
        Turtle file.
    """
    prefixes = pd.read_csv(prefix_csv_path)
    prefix_strings = prefixes.apply(
        lambda row: f"@prefix {row['prefix']}: <{row['uri']}> .", axis=1,
    )
    return "\n".join(prefix_strings)


# ---------------------------------------------------------------------------
# Genes RDF prefixes (hardcoded, matching pipeline.py line 2179)
# ---------------------------------------------------------------------------

GENES_PREFIXES = (
    "@prefix dc: <http://purl.org/dc/elements/1.1/> .\n"
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
    "@prefix aop.events: <https://identifiers.org/aop.events/> .\n"
    "@prefix aop.relationships: <https://identifiers.org/aop.relationships/> .\n"
    "@prefix skos: <http://www.w3.org/2004/02/skos/core#> . \n"
    "@prefix ensembl: <https://identifiers.org/ensembl/> .\n"
    "@prefix edam: <http://edamontology.org/> .\n"
    "@prefix hgnc: <https://identifiers.org/hgnc/>.\n"
    "@prefix ncbigene: <https://identifiers.org/ncbigene/>.\n"
    "@prefix uniprot: <https://identifiers.org/uniprot/>.\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#>.\n"
)

# Base namespace declaration for the BERN2 provenance predicates
# (:geneDetectedByRegex, :geneDetectedByNER). Prepended to the genes
# RDF header only when config.enable_bern2 is True, so the file is
# byte-identical to the pre-Phase-B output when the flag is off.
GENES_PROVENANCE_PREFIX = (
    "@prefix : <https://aopwiki.rdf.bigcat-bioinformatics.org/> .\n"
)

# PROV-O activity layer + machine-readable method primacy + confidence policy.
# Emitted into the genes RDF header ONLY when config.enable_bern2 is True,
# immediately after GENES_PROVENANCE_PREFIX, so the file stays byte-identical
# to the pre-Phase-7 output when the flag is off (COMPAT-01).
#
# Design (Phase 7 / 07-03, D-01..D-07):
#   * Two prov:Activity resources declared ONCE in the header (activity-level
#     provenance only -- never per KE/KER subject, never reified associations).
#   * BERN2 marked :isFeaturedMethod true (machine-readable, GENE-05/07).
#     SEMANTICS (important, see WR-02): "featured" denotes the
#     recall-EXTENDING / featured-for-discovery method, NOT a precedence that
#     overrides regex in the edam:data_1025 union. The union in
#     union_ner_into_entities is deliberately regex-baseline + NER-additive
#     (graceful degradation: a BERN2 outage never thins the regex genes), so
#     regex genes seed and order the list and NER can only ADD members. A
#     SPARQL consumer must read :isFeaturedMethod as "the canonical method to
#     surface/discover new gene links," not as "the method whose detections win
#     on conflict" (there is no conflict-resolution step -- the union is purely
#     additive). The rdfs:label on each activity spells this out.
#   * :minConfidence "0.70"^^xsd:decimal records the 0.70 NER threshold in the
#     RDF itself (GENE-08), not only in docs. IMPORTANT: this is the floor
#     applied to *scored* annotations only. BERN2 emits bare NaN (collapsed to
#     None by _loads_bern2) for some neural-normalised entities, and those
#     unscored annotations are deliberately RETAINED (a missing score is not
#     evidence of error -- see extract_ncbi_gene_ids). The activity rdfs:label
#     spells out this carve-out so a SPARQL consumer reading :minConfidence is
#     not misled into believing EVERY retained link scored >= 0.70.
#   * prov:wasGeneratedBy attached to the :geneDetectedBy* PREDICATES so a
#     SPARQL consumer can resolve the canonical method without reading docs.
#   * All literals are static -- no wall-clock timestamp, no runtime version
#     lookup -- to preserve byte-stable diffs against production-rdf-backup/.
#
# COMPAT carve-out: the prov: prefix lives ONLY here, NOT in prefixes.csv.
# prefixes.csv is iterated into unconditional sh:declare lines in the MAIN
# AOPWikiRDF.ttl, so adding prov there would break flag-off byte-identity.
# The xsd: prefix is declared here too because GENES_PREFIXES does not carry
# it and "0.70"^^xsd:decimal must parse.
GENES_PROVENANCE_ACTIVITIES = (
    "@prefix prov: <http://www.w3.org/ns/prov#> .\n"
    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
    "\n"
    ":BERN2NERMapping a prov:Activity ;\n"
    '\trdfs:label "BERN2 NER+EL gene mapping -- featured recall-extending '
    'method (additive to the regex baseline, not an override; scored '
    'annotations filtered at minConfidence, unscored neural-normalised '
    'entities retained)" ;\n'
    "\t:isFeaturedMethod true ;\n"
    '\t:minConfidence "0.70"^^xsd:decimal ;\n'
    "\tprov:used <http://bern2.korea.ac.kr/plain> ;\n"
    "\tprov:wasDerivedFrom :AOPWikiXMLSource .\n"
    "\n"
    ":RegexGeneMapping a prov:Activity ;\n"
    '\trdfs:label "HGNC dictionary regex gene mapping -- baseline method that '
    'seeds and orders the edam:data_1025 union (never thinned on BERN2 '
    'outage)" ;\n'
    "\t:isFeaturedMethod false ;\n"
    "\tprov:used <https://www.genenames.org/> ;\n"
    "\tprov:wasDerivedFrom :AOPWikiXMLSource .\n"
    "\n"
    ":AOPWikiXMLSource a prov:Entity ;\n"
    '\trdfs:label "AOP-Wiki XML export" .\n'
    "\n"
    ":geneDetectedByNER prov:wasGeneratedBy :BERN2NERMapping .\n"
    ":geneDetectedByRegex prov:wasGeneratedBy :RegexGeneMapping .\n"
    "\n"
)

# D-06 (genes file): rdfs:label rows for the MINTED ':' PREDICATES. The block
# above labels the prov:Activity RESOURCES (:BERN2NERMapping etc.) but NOT the
# minted predicates themselves. These rows are DOUBLE-gated -- emitted only when
# enable_bern2 AND enable_iri_labels are both on (RESEARCH Open Q2) -- so both
# the bern2-off byte-identity (the ':' predicates do not exist without bern2)
# AND the labels-off byte-identity (production runs with bern2 on but labels off
# stay unchanged) contracts hold. Co-located with GENES_PROVENANCE_ACTIVITIES so
# the prov:/xsd:/rdfs: prefixes it relies on are already declared; rdfs: is
# carried by GENES_PREFIXES. The prov: prefix carve-out (NOT in prefixes.csv) is
# preserved -- this constant adds no prefixes.
GENES_MINTED_PREDICATE_LABELS = (
    ":geneDetectedByNER rdfs:label "
    '"gene detected by BERN2 NER+EL (featured recall-extending method)" .\n'
    ":geneDetectedByRegex rdfs:label "
    '"gene detected by HGNC dictionary regex (baseline method)" .\n'
    ":isFeaturedMethod rdfs:label "
    '"is featured method (BERN2 primacy flag)" .\n'
    ":minConfidence rdfs:label "
    '"minimum BERN2 annotation confidence retained" .\n'
    "\n"
)

# ---------------------------------------------------------------------------
# Enriched RDF prefixes (cross-reference triples for AOPWikiRDF-Enriched.ttl)
# ---------------------------------------------------------------------------

ENRICHED_PREFIXES = (
    "# AOPWikiRDF-Enriched.ttl\n"
    "# Cross-reference enrichment triples for AOP-Wiki RDF\n"
    "#\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
    "@prefix cas: <https://identifiers.org/cas/> .\n"
    "@prefix pr: <http://purl.obolibrary.org/obo/PR_> .\n"
    "@prefix chebi: <https://identifiers.org/chebi/> .\n"
    "@prefix chemspider: <https://identifiers.org/chemspider/> .\n"
    "@prefix wikidata: <https://identifiers.org/wikidata/> .\n"
    "@prefix chembl.compound: <https://identifiers.org/chembl.compound/> .\n"
    "@prefix pubchem.compound: <https://identifiers.org/pubchem.compound/> .\n"
    "@prefix drugbank: <https://identifiers.org/drugbank/> .\n"
    "@prefix kegg.compound: <https://identifiers.org/kegg.compound/> .\n"
    "@prefix lipidmaps: <https://identifiers.org/lipidmaps/> .\n"
    "@prefix hmdb: <https://identifiers.org/hmdb/> .\n"
    "@prefix hgnc: <https://identifiers.org/hgnc/> .\n"
    "@prefix uniprot: <https://identifiers.org/uniprot/> .\n"
    "@prefix ncbigene: <https://identifiers.org/ncbigene/> .\n"
    "@prefix cheminf: <http://semanticscience.org/resource/CHEMINF_> .\n"
    "@prefix inchikey: <https://identifiers.org/inchikey/> .\n"
    "@prefix comptox: <https://identifiers.org/comptox/> .\n"
)

# ---------------------------------------------------------------------------
# VoID RDF prefixes (hardcoded, matching pipeline.py line 2279)
# ---------------------------------------------------------------------------

VOID_PREFIXES = (
    "@prefix : <https://aopwiki.rdf.bigcat-bioinformatics.org/> .\n"
    "@prefix dc: <http://purl.org/dc/elements/1.1/> .\n"
    "@prefix dcterms: <http://purl.org/dc/terms/> .\n"
    "@prefix void:  <http://rdfs.org/ns/void#> .\n"
    "@prefix pav:   <http://purl.org/pav/> .\n"
    "@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .\n"
    "@prefix dcat:  <http://www.w3.org/ns/dcat#> .\n"
    "@prefix foaf:  <http://xmlns.com/foaf/0.1/> .\n"
    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
    "@prefix freq:  <http://purl.org/cld/freq/> .\n"
    "@prefix aop: <https://identifiers.org/aop/> .\n"
    "@prefix aop.events: <https://identifiers.org/aop.events/> .\n"
    "@prefix aop.relationships: <https://identifiers.org/aop.relationships/> .\n"
    "@prefix aop.stressor: <https://identifiers.org/aop.stressor/> .\n"
    "@prefix cas: <https://identifiers.org/cas/> .\n"
    "@prefix owl: <http://www.w3.org/2002/07/owl#> ."
)
