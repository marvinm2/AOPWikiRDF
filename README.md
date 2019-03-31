# AOPWikiRDF
This repository will contain code and information about AOP Wiki RDF creation



 
 
# Guideline to set up a Virtuoso SPARQL endpoint with AOP-Wiki RDF (on linux):

# Step 1 - Create folder to mount
Enter the terminal and create a local folder to map to the docker container. Note the path to the folder to enter it at step 3. In this example, the folder '/dataload/data' was created and entered it by using:
```
mkdir -p aopwikirdf
```

# Step 2 - Move the RDF (.ttl) in the newly created folder

# Step 3 - Run the Docker image
Use 'sudo' if necessary. Be sure to use ports 8890:8890 and 1111:1111. In this case, the container was named "loadVirtuoso". Also, this step configures the mapped local folder with the data, which is in this example "/dataload". The Docker image used  is openlink/virtuoso-opensource-7. Do this by entering:
```
sudo docker run -d --env DBA_PASSWORD=dba -p 8890:8890 -p 1111:1111 --name AOPwiki --volume `pwd`/aopwikirdf/:/database/data/  openlink/virtuoso-opensource-7
```

# Step 4 - Enter the running container
While the docker image is running in a container, the data is not yet loaded. Therefore you need to enter the it by using:

```
sudo docker exec -it AOPwiki  bash
```

# Step 5 - Move the all.ttl file and create a .graph file.
First, enter the "/data" folder and move the "all.ttl" file to the folder upstream by using:
```
cd data
mv aopwiki.ttl ../
cd ../
```

Second, create a ".graph" file and add the graph.iri in that file, which is "aopwiki.org". Prior to that, a text editing tool needs to be installed, such as "nano". Use the commands:
```
touch aopwiki.ttl.graph
apt-get update
apt-get install nano
nano aopwiki.ttl.graph 
```

When the file is entered, write "aopwiki.org" (without ") and exit the file by pressing Ctrl+X, followed by "Y" and Enter to save and return. Exit the docker container by:
```
exit
```

# Step 6 - Enter the container SQL to configure RDF loading
Enter the running docker container SQL by using: 
```
sudo docker exec -i AOPwiki isql 1111
```

Use the following commands to complete the loading of RDF. If errors occur, try again within a few seconds (which often works), or look at http://docs.openlinksw.com/virtuoso/errorcodes/ to find out what they mean. 
```
log_enable(2);
DB.DBA.XML_SET_NS_DECL ('dc', 'http://purl.org/dc/elements/1.1/',2);
DB.DBA.XML_SET_NS_DECL ('dcterms', 'http://purl.org/dc/terms/',2);
DB.DBA.XML_SET_NS_DECL ('rdfs', 'http://www.w3.org/2000/01/rdf-schema#',2);
DB.DBA.XML_SET_NS_DECL ('foaf', 'http://xmlns.com/foaf/0.1/',2);
DB.DBA.XML_SET_NS_DECL ('aop', 'http://identifiers.org/aop/',2);
DB.DBA.XML_SET_NS_DECL ('ke', 'http://identifiers.org/aop.events/',2);
DB.DBA.XML_SET_NS_DECL ('ker', 'http://identifiers.org/aop.relationships/',2);
DB.DBA.XML_SET_NS_DECL ('stressor', 'http://identifiers.org/aop.stressor/',2);
DB.DBA.XML_SET_NS_DECL ('aopo', 'http://aopkb.org/aop_ontology#',2);
DB.DBA.XML_SET_NS_DECL ('casrn', 'http://identifiers.org/cas/',2);
DB.DBA.XML_SET_NS_DECL ('inchi', 'http://identifiers.org/inchikey/',2);
DB.DBA.XML_SET_NS_DECL ('pato', 'http://purl.obolibrary.org/obo/',2);
DB.DBA.XML_SET_NS_DECL ('ncbitaxon', 'http://purl.bioontology.org/ontology/NCBITAXON/',2);
DB.DBA.XML_SET_NS_DECL ('cl', 'http://purl.obolibrary.org/obo/CL_',2);
DB.DBA.XML_SET_NS_DECL ('uberon', 'http://purl.obolibrary.org/obo/UBERON_',2);
DB.DBA.XML_SET_NS_DECL ('go', 'http://purl.obolibrary.org/obo/GO_',2);
DB.DBA.XML_SET_NS_DECL ('mi', 'http://purl.obolibrary.org/obo/MI_',2);
DB.DBA.XML_SET_NS_DECL ('mp', 'http://purl.obolibrary.org/obo/MP_',2);
DB.DBA.XML_SET_NS_DECL ('mesh', 'http://purl.bioontology.org/ontology/MESH/',2);
DB.DBA.XML_SET_NS_DECL ('hp', 'http://purl.obolibrary.org/obo/HP_',2);
DB.DBA.XML_SET_NS_DECL ('pco', 'http://purl.obolibrary.org/obo/PCO_',2);
DB.DBA.XML_SET_NS_DECL ('nbo', 'http://purl.obolibrary.org/obo/NBO_',2);
DB.DBA.XML_SET_NS_DECL ('vt', 'http://purl.obolibrary.org/obo/VT_',2);
DB.DBA.XML_SET_NS_DECL ('pr', 'http://purl.obolibrary.org/obo/PR_',2);
DB.DBA.XML_SET_NS_DECL ('chebi', 'http://purl.obolibrary.org/obo/CHEBI_',2);
DB.DBA.XML_SET_NS_DECL ('fma', 'http://purl.org/sig/ont/fma/fma',2);
DB.DBA.XML_SET_NS_DECL ('cheminf', 'http://semanticscience.org/resource/',2);
DB.DBA.XML_SET_NS_DECL ('ncit', 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#',2);
DB.DBA.XML_SET_NS_DECL ('dss', 'https://comptox.epa.gov/dashboard/',2);
DB.DBA.XML_SET_NS_DECL ('mmo', 'http://purl.obolibrary.org/obo/MMO_',2);
log_enable(1);
grant select on "DB.DBA.SPARQL_SINV_2" to "SPARQL";
grant execute on "DB.DBA.SPARQL_SINV_IMP" to "SPARQL";
ld_dir('.', 'aopwiki.ttl', 'aopwiki.org');
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

# Step 7 - Enter the Virtuoso service with loaded AOP-Wiki RDF
The container is running with loaded RDF, available through http://localhost:8890, or enter the SPARQL endpoint directly through http://localhost:8890/sparql/.
