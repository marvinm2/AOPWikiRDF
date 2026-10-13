#!/bin/bash
#
# Virtuoso Loader Script (AOP-Wiki single-graph endpoint, tgx1 swarm)
#
# Ported from strato1 /home/MarvinMartens/AOP-Wiki-EP/db/data/load.sh.
# Only change vs strato1: ld_dir uses the absolute /database/data path (the
# swarm mount is /mnt/gluster/docker/aopwiki-snorql/virtuoso-data:/database),
# which is included in VIRT_Parameters_DirsAllowed.
#
# Usage: load.sh [log_file] [virtuoso_password]

args=("$@")

if [ $# -ne 2 ]; then
    echo "Wrong number of arguments. Correct usage: \"load.sh [log_file] [virtuoso_password]\""
    exit 1
fi

VAD=/database/data
LOGFILE=${args[0]}
VIRT_PSWD=${args[1]}

echo "Loading triples..."

isql_cmd="isql -U dba -P $VIRT_PSWD"
isql_cmd_check="isql -U dba -P $VIRT_PSWD exec=\"checkpoint;\""

reset="RDF_GLOBAL_RESET();"
cleanup1="DELETE FROM load_list WHERE ll_graph = 'http://aopwiki.org/';"
cleanup2="DELETE FROM load_list WHERE ll_graph IN ('servicedescription', 'http://aopwiki.org/void', 'http://aopwiki.org/servicedescription');"
cleanup3="DELETE FROM DB.DBA.SYS_XML_PERSISTENT_NS_DECL WHERE NS_PREFIX = 'go';"
setupgo1="INSERT INTO DB.DBA.SYS_XML_PERSISTENT_NS_DECL (NS_PREFIX, NS_URL) VALUES ('go', 'http://purl.obolibrary.org/obo/GO_');"
logenable2="log_enable(2);"

# Standard prefixes
prefix1="DB.DBA.XML_SET_NS_DECL ('dc', 'http://purl.org/dc/elements/1.1/',2);"
prefix2="DB.DBA.XML_SET_NS_DECL ('dcterms', 'http://purl.org/dc/terms/',2);"
prefix3="DB.DBA.XML_SET_NS_DECL ('rdfs', 'http://www.w3.org/2000/01/rdf-schema#',2);"
prefix4="DB.DBA.XML_SET_NS_DECL ('foaf', 'http://xmlns.com/foaf/0.1/',2);"
prefix5="DB.DBA.XML_SET_NS_DECL ('owl', 'http://www.w3.org/2002/07/owl#',2);"
prefix6="DB.DBA.XML_SET_NS_DECL ('skos', 'http://www.w3.org/2004/02/skos/core#',2);"
prefix7="DB.DBA.XML_SET_NS_DECL ('xsd', 'http://www.w3.org/2001/XMLSchema#',2);"
prefix8="DB.DBA.XML_SET_NS_DECL ('sh', 'http://www.w3.org/ns/shacl#',2);"
# AOP namespaces
prefix9="DB.DBA.XML_SET_NS_DECL ('aop', 'https://identifiers.org/aop/',2);"
prefix10="DB.DBA.XML_SET_NS_DECL ('aop.events', 'https://identifiers.org/aop.events/',2);"
prefix11="DB.DBA.XML_SET_NS_DECL ('aop.relationships', 'https://identifiers.org/aop.relationships/',2);"
prefix12="DB.DBA.XML_SET_NS_DECL ('aop.stressor', 'https://identifiers.org/aop.stressor/',2);"
prefix13="DB.DBA.XML_SET_NS_DECL ('aopo', 'http://aopkb.org/aop_ontology#',2);"
# Chemical identifiers
prefix14="DB.DBA.XML_SET_NS_DECL ('cas', 'https://identifiers.org/cas/',2);"
prefix15="DB.DBA.XML_SET_NS_DECL ('inchikey', 'https://identifiers.org/inchikey/',2);"
prefix16="DB.DBA.XML_SET_NS_DECL ('chebi', 'https://identifiers.org/chebi/',2);"
prefix17="DB.DBA.XML_SET_NS_DECL ('chebio', 'http://purl.obolibrary.org/obo/CHEBI_',2);"
prefix18="DB.DBA.XML_SET_NS_DECL ('cheminf', 'http://semanticscience.org/resource/CHEMINF_',2);"
prefix19="DB.DBA.XML_SET_NS_DECL ('chemspider', 'https://identifiers.org/chemspider/',2);"
prefix20="DB.DBA.XML_SET_NS_DECL ('chembl.compound', 'https://identifiers.org/chembl.compound/',2);"
prefix21="DB.DBA.XML_SET_NS_DECL ('pubchem.compound', 'https://identifiers.org/pubchem.compound/',2);"
prefix22="DB.DBA.XML_SET_NS_DECL ('drugbank', 'https://identifiers.org/drugbank/',2);"
prefix23="DB.DBA.XML_SET_NS_DECL ('kegg.compound', 'https://identifiers.org/kegg.compound/',2);"
prefix24="DB.DBA.XML_SET_NS_DECL ('lipidmaps', 'https://identifiers.org/lipidmaps/',2);"
prefix25="DB.DBA.XML_SET_NS_DECL ('hmdb', 'https://identifiers.org/hmdb/',2);"
prefix26="DB.DBA.XML_SET_NS_DECL ('wikidata', 'https://identifiers.org/wikidata/',2);"
prefix27="DB.DBA.XML_SET_NS_DECL ('comptox', 'https://identifiers.org/comptox/',2);"
# Biological ontologies
prefix28="DB.DBA.XML_SET_NS_DECL ('pato', 'http://purl.obolibrary.org/obo/PATO_',2);"
prefix29="DB.DBA.XML_SET_NS_DECL ('ncbitaxon', 'http://purl.bioontology.org/ontology/NCBITAXON/',2);"
prefix30="DB.DBA.XML_SET_NS_DECL ('cl', 'http://purl.obolibrary.org/obo/CL_',2);"
prefix31="DB.DBA.XML_SET_NS_DECL ('uberon', 'http://purl.obolibrary.org/obo/UBERON_',2);"
prefix32="DB.DBA.XML_SET_NS_DECL ('go', 'http://purl.obolibrary.org/obo/GO_',2);"
prefix33="DB.DBA.XML_SET_NS_DECL ('mi', 'http://purl.obolibrary.org/obo/MI_',2);"
prefix34="DB.DBA.XML_SET_NS_DECL ('mp', 'http://purl.obolibrary.org/obo/MP_',2);"
prefix35="DB.DBA.XML_SET_NS_DECL ('hp', 'http://purl.obolibrary.org/obo/HP_',2);"
prefix36="DB.DBA.XML_SET_NS_DECL ('pco', 'http://purl.obolibrary.org/obo/PCO_',2);"
prefix37="DB.DBA.XML_SET_NS_DECL ('nbo', 'http://purl.obolibrary.org/obo/NBO_',2);"
prefix38="DB.DBA.XML_SET_NS_DECL ('vt', 'http://purl.obolibrary.org/obo/VT_',2);"
prefix39="DB.DBA.XML_SET_NS_DECL ('pr', 'http://purl.obolibrary.org/obo/PR_',2);"
prefix40="DB.DBA.XML_SET_NS_DECL ('fma', 'http://purl.obolibrary.org/obo/FMA_',2);"
prefix41="DB.DBA.XML_SET_NS_DECL ('nci', 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#',2);"
prefix42="DB.DBA.XML_SET_NS_DECL ('mmo', 'http://purl.obolibrary.org/obo/MMO_',2);"
prefix43="DB.DBA.XML_SET_NS_DECL ('mesh', 'http://purl.org/commons/record/mesh/',2);"
prefix44="DB.DBA.XML_SET_NS_DECL ('rbo', 'http://purl.obolibrary.org/obo/RBO_',2);"
prefix45="DB.DBA.XML_SET_NS_DECL ('ido', 'http://purl.obolibrary.org/obo/IDO_',2);"
# Gene/protein identifiers
prefix46="DB.DBA.XML_SET_NS_DECL ('ensembl', 'https://identifiers.org/ensembl/',2);"
prefix47="DB.DBA.XML_SET_NS_DECL ('edam', 'http://edamontology.org/',2);"
prefix48="DB.DBA.XML_SET_NS_DECL ('hgnc', 'https://identifiers.org/hgnc/',2);"
prefix49="DB.DBA.XML_SET_NS_DECL ('ncbigene', 'https://identifiers.org/ncbigene/',2);"
prefix50="DB.DBA.XML_SET_NS_DECL ('uniprot', 'https://identifiers.org/uniprot/',2);"
# Metadata prefixes
prefix51="DB.DBA.XML_SET_NS_DECL ('void', 'http://rdfs.org/ns/void#',2);"
prefix52="DB.DBA.XML_SET_NS_DECL ('pav', 'http://purl.org/pav/',2);"
prefix53="DB.DBA.XML_SET_NS_DECL ('dcat', 'http://www.w3.org/ns/dcat#',2);"
prefix54="DB.DBA.XML_SET_NS_DECL ('freq', 'http://purl.org/cld/freq/',2);"
prefix55="DB.DBA.XML_SET_NS_DECL ('sd', 'http://www.w3.org/ns/sparql-service-description#',2);"

logenable1="log_enable(1);"
grant1="grant execute on \"DB.DBA.EXEC_AS\" to \"SPARQL\";"
grant2="grant select on \"DB.DBA.SPARQL_SINV_2\" to \"SPARQL\";"
grant3="grant execute on \"DB.DBA.SPARQL_SINV_IMP\" to \"SPARQL\";"
grant4="grant SPARQL_LOAD_SERVICE_DATA to \"SPARQL\";"
grant5="grant SPARQL_SPONGE to \"SPARQL\";"
load_func1="ld_dir('$VAD', 'AOPWikiRDF.ttl', 'http://aopwiki.org/');"
load_func2="ld_dir('$VAD', 'AOPWikiRDF-Enriched.ttl', 'http://aopwiki.org/');"
load_func3="ld_dir('$VAD', 'AOPWikiRDF-Genes.ttl', 'http://aopwiki.org/');"
# VoID and service description each get their own graph (marvinm2/AOPWikiRDF#125), so
# schema statistics and mined schemas see AOP-Wiki data only, and the URL-rewrite rules
# can serve either document by CONSTRUCTing one whole graph.
load_func4="ld_dir('$VAD', 'AOPWikiRDF-Void.ttl', 'http://aopwiki.org/void');"
load_func5="ld_dir('$VAD', 'ServiceDescription.ttl', 'http://aopwiki.org/servicedescription');"
run_func="rdf_loader_run();"
select_func="select * from DB.DBA.load_list;"

${isql_cmd} << EOF &> ${LOGFILE}
    $reset
    $cleanup1
    $cleanup2
    $cleanup3
    $setupgo1
    $logenable2
    $prefix1
    $prefix2
    $prefix3
    $prefix4
    $prefix5
    $prefix6
    $prefix7
    $prefix8
    $prefix9
    $prefix10
    $prefix11
    $prefix12
    $prefix13
    $prefix14
    $prefix15
    $prefix16
    $prefix17
    $prefix18
    $prefix19
    $prefix20
    $prefix21
    $prefix22
    $prefix23
    $prefix24
    $prefix25
    $prefix26
    $prefix27
    $prefix28
    $prefix29
    $prefix30
    $prefix31
    $prefix32
    $prefix33
    $prefix34
    $prefix35
    $prefix36
    $prefix37
    $prefix38
    $prefix39
    $prefix40
    $prefix41
    $prefix42
    $prefix43
    $prefix44
    $prefix45
    $prefix46
    $prefix47
    $prefix48
    $prefix49
    $prefix50
    $prefix51
    $prefix52
    $prefix53
    $prefix54
    $prefix55
    $logenable1
    $grant1
    $grant2
    $grant3
    $grant4
    $grant5
    $load_func1
    $load_func2
    $load_func3
    $load_func4
    $load_func5
    $run_func
    $select_func
    exit;
${isql_cmd_check}

EOF

echo "----------" >> ${LOGFILE}
echo "$load_func1 $load_func2 $load_func3 $load_func4 $load_func5" >> ${LOGFILE}
echo $run_func >> ${LOGFILE}
echo ${select_func} >> ${LOGFILE}
echo "----------" >> ${LOGFILE}

cat ${LOGFILE}
echo "Loading finished! Check ${LOGFILE} for details."
exit 0
