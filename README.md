# AOP-Wiki XML to RDF conversion

[![DOI](https://zenodo.org/badge/146466058.svg)](https://zenodo.org/badge/latestdoi/146466058)


This GitHub repository accompanies the publication linked to the AOP-Wiki RDF, and contains the conversion Jupyter notebook, guidelines to use the RDF in a local SPARQL endpoint, and an additional Jupyter notebook to extract statistics. 

## Set up a Virtuoso SPARQL endpoint with AOP-Wiki RDF (on linux):

### Step 1 - Create folder to mount
Enter the terminal and create a local folder to map to the docker container. Note the path to the folder to enter it at step 3. In this example, the folder '/aopwikirdf' was created and entered it by using:
```
mkdir -p aopwikirdf
```

### Step 2 - Move the RDF (.ttl) files into the newly created folder

### Step 3 - Run the Docker image
Be sure to use ports 8890:8890 and 1111:1111. In this case, the container was named "AOPWiki". Also, this step configures the mapped local folder with the data, which is in this example "/aopwikirdf". The Docker image used is openlink/virtuoso-opensource-7. Run the Docker image by entering:
```
sudo docker run -d --env DBA_PASSWORD=dba -p 8890:8890 -p 1111:1111 --name AOPWiki --volume `pwd`/aopwikirdf/:/database/data/  openlink/virtuoso-opensource-7
```

### Step 4 - Enter the running container
The SPARQL endpoint should already be accessible through [localhost:8890/sparql/](http://localhost:8890/sparql/). However, while the Docker image is running, the data is not yet loaded. Therefore you need to enter the it by using:
```
sudo docker exec -it AOPWiki  bash
```

### Step 5 - Move the .ttl files
First, enter the "/data" folder and move the Turtle file(s) to the folder upstream by using:
```
mv data/AOPWikiRDF.ttl .
mv data/AOPWikiRDF-Void.ttl .
mv data/AOPWikiRDF-genes.ttl .
exit
```

### Step 6 - Enter the container SQL and reset
Enter the running docker container SQL by using: 
```
sudo docker exec -i AOPWiki isql 1111
```
In case the service is already active and contains older RDF, be sure to perform a global reset and delete the old RDF files from the load_list, using the following commands:
```
RDF_GLOBAL_RESET();
DELETE FROM load_list WHERE ll_graph = 'aopwiki.org';
```
The presence of files in the load_list can be viewed using the following command:
```
select * from DB.DBA.load_list;
```

### Step 7 - Load the RDF
Use the following commands to complete the loading of RDF. If errors occur, try again within a few seconds (which often works), or look at http://docs.openlinksw.com/virtuoso/errorcodes/ to find out what they mean. 
```
log_enable(2);
DB.DBA.XML_SET_NS_DECL ('dc', 'http://purl.org/dc/elements/1.1/',2);
DB.DBA.XML_SET_NS_DECL ('dcterms', 'http://purl.org/dc/terms/',2);
DB.DBA.XML_SET_NS_DECL ('rdfs', 'http://www.w3.org/2000/01/rdf-schema#',2);
DB.DBA.XML_SET_NS_DECL ('foaf', 'http://xmlns.com/foaf/0.1/',2);
DB.DBA.XML_SET_NS_DECL ('aop', 'http://identifiers.org/aop/',2);
DB.DBA.XML_SET_NS_DECL ('aop.events', 'http://identifiers.org/aop.events/',2);
DB.DBA.XML_SET_NS_DECL ('aop.relationships', 'http://identifiers.org/aop.relationships/',2);
DB.DBA.XML_SET_NS_DECL ('aop.stressor', 'http://identifiers.org/aop.stressor/',2);
DB.DBA.XML_SET_NS_DECL ('aopo', 'http://aopkb.org/aop_ontology#',2);
DB.DBA.XML_SET_NS_DECL ('cas', 'http://identifiers.org/cas/',2);
DB.DBA.XML_SET_NS_DECL ('inchikey', 'http://identifiers.org/inchikey/',2);
DB.DBA.XML_SET_NS_DECL ('pato', 'http://purl.obolibrary.org/obo/PATO_',2);
DB.DBA.XML_SET_NS_DECL ('ncbitaxon', 'http://purl.bioontology.org/ontology/NCBITAXON/',2);
DB.DBA.XML_SET_NS_DECL ('cl', 'http://purl.obolibrary.org/obo/CL_',2);
DB.DBA.XML_SET_NS_DECL ('uberon', 'http://purl.obolibrary.org/obo/UBERON_',2);
DB.DBA.XML_SET_NS_DECL ('go', 'http://purl.obolibrary.org/obo/GO_',2);
DB.DBA.XML_SET_NS_DECL ('mi', 'http://purl.obolibrary.org/obo/MI_',2);
DB.DBA.XML_SET_NS_DECL ('mp', 'http://purl.obolibrary.org/obo/MP_',2);
DB.DBA.XML_SET_NS_DECL ('hp', 'http://purl.obolibrary.org/obo/HP_',2);
DB.DBA.XML_SET_NS_DECL ('pco', 'http://purl.obolibrary.org/obo/PCO_',2);
DB.DBA.XML_SET_NS_DECL ('nbo', 'http://purl.obolibrary.org/obo/NBO_',2);
DB.DBA.XML_SET_NS_DECL ('vt', 'http://purl.obolibrary.org/obo/VT_',2);
DB.DBA.XML_SET_NS_DECL ('pr', 'http://purl.obolibrary.org/obo/PR_',2);
DB.DBA.XML_SET_NS_DECL ('chebio', 'http://purl.obolibrary.org/obo/CHEBI_',2);
DB.DBA.XML_SET_NS_DECL ('fma', 'http://purl.org/sig/ont/fma/fma',2);
DB.DBA.XML_SET_NS_DECL ('cheminf', 'http://semanticscience.org/resource/CHEMINF_',2);
DB.DBA.XML_SET_NS_DECL ('ncit', 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#',2);
DB.DBA.XML_SET_NS_DECL ('comptox', 'https://comptox.epa.gov/dashboard/',2);
DB.DBA.XML_SET_NS_DECL ('mmo', 'http://purl.obolibrary.org/obo/MMO_',2);
DB.DBA.XML_SET_NS_DECL ('chebi', 'https://identifiers.org/chebi/',2);
DB.DBA.XML_SET_NS_DECL ('chemspider', 'https://identifiers.org/chemspider/',2);
DB.DBA.XML_SET_NS_DECL ('wikidata', 'https://identifiers.org/wikidata/',2);
DB.DBA.XML_SET_NS_DECL ('chembl.compound', 'https://identifiers.org/chembl.compound/',2);
DB.DBA.XML_SET_NS_DECL ('pubchem.compound', 'https://identifiers.org/pubchem.compound/',2);
DB.DBA.XML_SET_NS_DECL ('drugbank', 'https://identifiers.org/drugbank/',2);
DB.DBA.XML_SET_NS_DECL ('kegg.compound', 'https://identifiers.org/kegg.compound/',2);
DB.DBA.XML_SET_NS_DECL ('lipidmaps', 'https://identifiers.org/lipidmaps/',2);
DB.DBA.XML_SET_NS_DECL ('hmdb', 'https://identifiers.org/hmdb/',2);
DB.DBA.XML_SET_NS_DECL ('ensembl', 'http://identifiers.org/ensembl/',2);
DB.DBA.XML_SET_NS_DECL ('edam', 'http://edamontology.org/',2);
DB.DBA.XML_SET_NS_DECL ('hgnc', 'https://identifiers.org/hgnc/',2);
DB.DBA.XML_SET_NS_DECL ('ncbigene', 'https://identifiers.org/ncbigene/',2);
DB.DBA.XML_SET_NS_DECL ('uniprot', 'https://identifiers.org/uniprot/',2);
DB.DBA.XML_SET_NS_DECL ('void', 'http://rdfs.org/ns/void#',2);
DB.DBA.XML_SET_NS_DECL ('pav', 'http://purl.org/pav/',2);
DB.DBA.XML_SET_NS_DECL ('dcat', 'http://www.w3.org/ns/dcat#',2);
log_enable(1);
grant select on "DB.DBA.SPARQL_SINV_2" to "SPARQL";
grant execute on "DB.DBA.SPARQL_SINV_IMP" to "SPARQL";
ld_dir('.', 'AOPWikiRDF.ttl', 'aopwiki.org');
ld_dir('.', 'AOPWikiRDF-Void.ttl', 'aopwiki.org');
ld_dir('.', 'AOPWikiRDF-genes.ttl', 'aopwiki.org');
```

To finalize the loading of data, use:
```
rdf_loader_run();
```

Check the status and look if the all.ttl file is loaded by entering:
```
select * from DB.DBA.load_list;
```

If the "il_state" = 2, the loading is complete. If issues occurred in this step, have a look at http://vos.openlinksw.com/owiki/wiki/VOS/VirtBulkRDFLoader. 
Quit the SQL by entering:
```
quit;
```

### Step 8 - Enter the Virtuoso service with loaded AOP-Wiki RDF
The container is running with loaded RDF, available through http://localhost:8890, or enter the SPARQL endpoint directly through http://localhost:8890/sparql/.
