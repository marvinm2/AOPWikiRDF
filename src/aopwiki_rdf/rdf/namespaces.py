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
