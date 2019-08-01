from xml.etree.ElementTree import parse
import re
import requests
filename = 'aop-wiki-xml-2019-07-01'
print('Parsing AOP-Wiki XML file. . ', end="")
tree = parse('/home/marvin.martens/Documents/AOPWikiRDF/' + filename)  # double \\ after C: because python3 reads this as a character with one \
root = tree.getroot()
print('. . Done ')
aopxml = '{http://www.aopkb.org/aop-xml}'

# Import re for html cleanup. TAG_RE is defining all tags to remove from text files with cleanup

TAG_RE = re.compile(r'<[^>]+>')

# Create a dictionary for all genes that were mapped through HGNC identifiers for KEs
# Create a dictionary with all gene names to map to KE and KER descriptions
# The HGNC gene name file from the HGNC database
HGNC = open('/home/marvin.martens/Documents/AOPWikiRDF/HGNCgenes2.txt', 'r')
genedict = {}
# A dictionary to contain all variants of all genes provided by the HGNC file
for line in HGNC:
	if not 'HGNC ID	Approved Symbol	Approved Name	Previous Symbols	Synonyms	Ensembl ID(supplied by Ensembl)'in line:  # To avoid the first line to be added to the dictionary
		a = line.split('\t')
		genedict[a[0]] = []
		if not a[5][:-1] == '':
			genedict[a[0]].append(a[5][:-1])
		genedict[a[0]].extend((' '+a[1]+' ', '('+a[1]+',', ' '+a[1]+',', '('+a[1]+')', ' '+a[1]+')', '['+a[1]+']', '['+a[1]+',', ' '+a[1]+']', ' '+a[1]+'.', '('+a[1]+' ', '['+a[1]+' ', ' '+a[2]+' ', '('+a[2]+',', ' '+a[2]+',', '('+a[2]+')', ' '+a[2]+')', '['+a[2]+']', '['+a[2]+',', ' '+a[2]+']', ' '+a[2]+'.', '('+a[2]+' ', '['+a[2]+' '))
# From all variants of gene names and synonyms, a range of written varieties are stored in the dictionary
		for item in a[3].split(', '):
			if not item == '':
				genedict[a[0]].extend((' '+item+' ', '('+item+',', ' '+item+',', '('+item+')', ' '+item+')', '['+item+']', '['+item+',', ' '+item+']', ' '+item+'.', '('+item+' ', '['+item+' '))
		for item in a[4].split(', '):
			if not item == '':
				genedict[a[0]].extend((' '+item+' ', '('+item+',', ' '+item+',', '('+item+')', ' '+item+')', '['+item+']', '['+item+',', ' '+item+']', ' '+item+'.', '('+item+' ', '['+item+' '))
HGNC.close()

# AOPWIKI IDs to add for AOP, stressors and KEs
print('Creating AOP-Wiki ID dictionaries. . ', end="")
refs = {'aop': {}, 'KEs': {}, 'KERs': {}, 'stressor': {}}
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'aop-reference'):
	refs['aop'][ref.get('id')] = ref.get('aop-wiki-id')
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'key-event-reference'):
	refs['KEs'][ref.get('id')] = ref.get('aop-wiki-id')
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'key-event-relationship-reference'):
	refs['KERs'][ref.get('id')] = ref.get('aop-wiki-id')
for ref in root.find(aopxml + 'vendor-specific').findall(aopxml + 'stressor-reference'):
	refs['stressor'][ref.get('id')] = ref.get('aop-wiki-id')
print('. . Done ')

# ADVERSE OUTCOME PATHWAYS
print('Parsing and organizing AOP information. . ', end="")
aopdict = {}
kedict = {}
for AOP in root.findall(aopxml + 'aop'):
	aopdict[AOP.get('id')] = {}
	# General info about the AOPs
	aopdict[AOP.get('id')]['dc:identifier'] = 'aop:' + refs['aop'][AOP.get('id')]
	aopdict[AOP.get('id')]['rdfs:label'] = '"AOP ' + refs['aop'][AOP.get('id')] + '"'
	aopdict[AOP.get('id')]['foaf:page'] = '<http://identifiers.org/aop/' + refs['aop'][AOP.get('id')] + '>'
	aopdict[AOP.get('id')]['dc:title'] = '"' + AOP.find(aopxml + 'title').text + '"'
	aopdict[AOP.get('id')]['dcterms:alternative'] = AOP.find(aopxml + 'short-name').text
	if AOP.find(aopxml + 'authors').text is not None:
		aopdict[AOP.get('id')]['dc:creator'] = '"""' + TAG_RE.sub('', AOP.find(aopxml + 'authors').text) + '"""'
	if AOP.find(aopxml + 'abstract').text is not None:
		aopdict[AOP.get('id')]['dcterms:abstract'] = '"""' + TAG_RE.sub('', AOP.find(aopxml + 'abstract').text) + '"""'
	if AOP.find(aopxml + 'status').find(aopxml + 'wiki-status') is not None:
		aopdict[AOP.get('id')]['dc:accessRights'] = AOP.find(aopxml + 'status').find(aopxml + 'wiki-status').text  # dc:accessRights = wiki-status
	if AOP.find(aopxml + 'status').find(aopxml + 'oecd-status') is not None:
		aopdict[AOP.get('id')]['oecd-status'] = AOP.find(aopxml + 'status').find(aopxml + 'oecd-status').text
	if AOP.find(aopxml + 'status').find(aopxml + 'saaop-status') is not None:
		aopdict[AOP.get('id')]['saaop-status'] = AOP.find(aopxml + 'status').find(aopxml + 'saaop-status').text
	aopdict[AOP.get('id')]['oecd-project'] = AOP.find(aopxml + 'oecd-project').text
	aopdict[AOP.get('id')]['dc:source'] = AOP.find(aopxml + 'source').text
	# timestamps
	aopdict[AOP.get('id')]['dcterms:created'] = AOP.find(aopxml + 'creation-timestamp').text
	aopdict[AOP.get('id')]['dcterms:modified'] = AOP.find(aopxml + 'last-modification-timestamp').text
	# applicability
	for appl in AOP.findall(aopxml + 'applicability'):
		for sex in appl.findall(aopxml + 'sex'):
			if 'pato:PATO_0000047' not in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['pato:PATO_0000047'] = [[sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text]]
			else:
				aopdict[AOP.get('id')]['pato:PATO_0000047'].append([sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text])
		for life in appl.findall(aopxml + 'life-stage'):
			if 'aopo:LifeStageContext' not in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['aopo:LifeStageContext'] = [[life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text]]
			else:
				aopdict[AOP.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text])
	# Key Events
	aopdict[AOP.get('id')]['aopo:has_key_event'] = {}
	for KE in AOP.find(aopxml + 'key-events').findall(aopxml + 'key-event'):
		aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('id')] = {}
		aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('id')]['dc:identifier'] = 'aop.events:' + refs['KEs'][KE.get('id')]
	# Key Event Relationships
	aopdict[AOP.get('id')]['aopo:has_key_event_relationship'] = {}
	for KER in AOP.find(aopxml + 'key-event-relationships').findall(aopxml + 'relationship'):
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')] = {}
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['dc:identifier'] = 'aop.relationships:' + refs['KERs'][KER.get('id')]
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['adjacency'] = KER.find(aopxml + 'adjacency').text
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['quantitative-understanding-value'] = KER.find(aopxml + 'quantitative-understanding-value').text
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['aopo:has_evidence'] = KER.find(aopxml + 'evidence').text
	# Molecular Initiating Events
	aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'] = {}
	for MIE in AOP.findall(aopxml + 'molecular-initiating-event'):
		aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')] = {}
		aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KEs'][MIE.get('key-event-id')]
		# question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')] = {}
		aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KEs'][MIE.get('key-event-id')]
		if MIE.find(aopxml + 'evidence-supporting-chemical-initiation').text is not None:
			kedict[MIE.get('key-event-id')] = {}
			kedict[MIE.get('key-event-id')]['dc:description'] = MIE.find(aopxml + 'evidence-supporting-chemical-initiation').text
	# Adverse Outcomes
	aopdict[AOP.get('id')]['aopo:has_adverse_outcome'] = {}
	for AO in AOP.findall(aopxml + 'adverse-outcome'):
		aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')] = {}
		aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KEs'][AO.get('key-event-id')]
		# question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')] = {}
		aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')]['dc:identifier'] = 'aop.events:' + refs['KEs'][AO.get('key-event-id')]
		if AO.find(aopxml + 'examples').text is not None:
			kedict[AO.get('key-event-id')] = {}
			kedict[AO.get('key-event-id')]['dc:description'] = AO.find(aopxml + 'examples').text
	# stressors
	aopdict[AOP.get('id')]['ncit:C54571'] = {}
	if AOP.find(aopxml + 'aop-stressors') is not None:
		for stressor in AOP.find(aopxml + 'aop-stressors').findall(aopxml + 'aop-stressor'):
			aopdict[AOP.get('id')]['ncit:C54571'][stressor.get('stressor-id')] = {}
			aopdict[AOP.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['dc:identifier'] = 'aop.stressor:' + refs['stressor'][stressor.get('stressor-id')]
			aopdict[AOP.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['aopo:has_evidence'] = stressor.find(aopxml + 'evidence').text

print('. . Done ')

# CHEMICALS
print('Parsing and organizing chemical information. . ', end="")
chedict = {}
listofchebi = []
listofchemspider = []
listofwikidata = []
listofchembl = []
listofdrugbank = []
listofpubchem = []
listoflipidmaps = []
listofhmdb = []
listofkegg = []

for che in root.findall(aopxml + 'chemical'):
	chedict[che.get('id')] = {}
	if che.find(aopxml + 'casrn') is not None:
		if 'NOCAS' not in che.find(aopxml + 'casrn').text:  # all NOCAS ids are out, so no issues as subjects
			chedict[che.get('id')]['dc:identifier'] = 'cas:' + che.find(aopxml + 'casrn').text
			chedict[che.get('id')]['cheminf:CHEMINF_000446'] = '"' + che.find(aopxml + 'casrn').text + '"'
			a = requests.get('http://localhost:8080/Human/xrefs/Ca/'+che.find(aopxml + 'casrn').text).text.split('\n')
			dictionaryforchemical = {}
			if 'html' not in a:
				for item in a:
					b = item.split('\t')
					if len(b) == 2:
						if b[1] not in dictionaryforchemical:
							dictionaryforchemical[b[1]] = []
							dictionaryforchemical[b[1]].append(b[0])
						else:
							dictionaryforchemical[b[1]].append(b[0])
			if 'ChEBI' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000407'] = []
				for chebi in dictionaryforchemical['ChEBI']:
					if 'chebi:'+chebi not in listofchebi:
						listofchebi.append('chebi:'+chebi)
					chedict[che.get('id')]['cheminf:CHEMINF_000407'].append('chebi:'+chebi)
			if 'Chemspider' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000405'] = []
				for chemspider in dictionaryforchemical['Chemspider']:
					if 'chemspider:'+chemspider not in listofchemspider:
						listofchemspider.append('chemspider:'+chemspider)
					chedict[che.get('id')]['cheminf:CHEMINF_000405'].append('chemspider:'+chemspider)
			if 'Wikidata' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000567'] = []
				for wd in dictionaryforchemical['Wikidata']:
					if 'wikidata:'+wd not in listofwikidata:
						listofwikidata.append('wikidata:'+wd)
					chedict[che.get('id')]['cheminf:CHEMINF_000567'].append('wikidata:'+wd)
			if 'ChEMBL compound' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000412'] = []
				for chembl in dictionaryforchemical['ChEMBL compound']:
					if 'chembl.compound:'+chembl not in listofchembl:
						listofchembl.append('chembl.compound:'+chembl)
					chedict[che.get('id')]['cheminf:CHEMINF_000412'].append('chembl.compound:'+chembl)
			if 'PubChem-compound' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000140'] = []
				for pub in dictionaryforchemical['PubChem-compound']:
					if 'pubchem.compound:'+pub not in listofpubchem:
						listofpubchem.append('pubchem.compound:'+pub)
					chedict[che.get('id')]['cheminf:CHEMINF_000140'].append('pubchem.compound:'+pub)
			if 'DrugBank' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000406'] = []
				for drugbank in dictionaryforchemical['DrugBank']:
					if 'drugbank:'+drugbank not in listofdrugbank:
						listofdrugbank.append('drugbank:'+drugbank)
					chedict[che.get('id')]['cheminf:CHEMINF_000406'].append('drugbank:'+drugbank)
			if 'KEGG Compound' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000409'] = []
				for kegg in dictionaryforchemical['KEGG Compound']:
					if 'kegg.compound:'+kegg not in listofkegg:
						listofkegg.append('kegg.compound:'+kegg)
					chedict[che.get('id')]['cheminf:CHEMINF_000409'].append('kegg.compound:'+kegg)
			if 'LIPID MAPS' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000564'] = []
				for lipidmaps in dictionaryforchemical['LIPID MAPS']:
					if 'lipidmaps:'+lipidmaps not in listoflipidmaps:
						listoflipidmaps.append('lipidmaps:'+lipidmaps)
					chedict[che.get('id')]['cheminf:CHEMINF_000564'].append('lipidmaps:'+lipidmaps)
			if 'HMDB' in dictionaryforchemical:
				chedict[che.get('id')]['cheminf:CHEMINF_000408'] = []
				for hmdb in dictionaryforchemical['HMDB']:
					if 'hmdb:'+hmdb not in listofhmdb:
						listofhmdb.append('hmdb:'+hmdb)
					chedict[che.get('id')]['cheminf:CHEMINF_000408'].append('hmdb:'+hmdb)
		else:
			chedict[che.get('id')]['dc:identifier'] = '"' + che.find(aopxml + 'casrn').text + '"'
	if che.find(aopxml + 'jchem-inchi-key') is not None:
		chedict[che.get('id')]['cheminf:CHEMINF_000059'] = 'inchikey:' + str(che.find(aopxml + 'jchem-inchi-key').text)
	if che.find(aopxml + 'preferred-name') is not None:
		chedict[che.get('id')]['dc:title'] = '"' + che.find(aopxml + 'preferred-name').text + '"'
	if che.find(aopxml + 'dsstox-id') is not None:
		chedict[che.get('id')]['cheminf:CHEMINF_000568'] = 'comptox:' + che.find(aopxml + 'dsstox-id').text
	if che.find(aopxml + 'synonyms') is not None:
		chedict[che.get('id')]['dcterms:alternative'] = []
		for synonym in che.find(aopxml + 'synonyms').findall(aopxml + 'synonym'):
			chedict[che.get('id')]['dcterms:alternative'].append(synonym.text[:-1])
print('. . Done ')

# STRESSORS, later to combine with CHEMICALS when writing file
print('Parsing and organizing stressor information. . ', end="")
strdict = {}
for stressor in root.findall(aopxml + 'stressor'):
	strdict[stressor.get('id')] = {}
	# General info about the stressors
	strdict[stressor.get('id')]['dc:identifier'] = 'aop.stressor:' + refs['stressor'][stressor.get('id')]
	strdict[stressor.get('id')]['rdfs:label'] = '"Stressor ' + refs['stressor'][stressor.get('id')] + '"'
	strdict[stressor.get('id')]['foaf:page'] = '<http://identifiers.org/aop.stressor/' + refs['stressor'][stressor.get('id')] + '>'
	strdict[stressor.get('id')]['dc:title'] = '"' + stressor.find(aopxml + 'name').text + '"'
	if stressor.find(aopxml + 'description').text is not None:
		strdict[stressor.get('id')]['dc:description'] = '"""' + TAG_RE.sub('', stressor.find(aopxml + 'description').text) + '"""'
	strdict[stressor.get('id')]['dcterms:created'] = stressor.find(aopxml + 'creation-timestamp').text
	strdict[stressor.get('id')]['dcterms:modified'] = stressor.find(aopxml + 'last-modification-timestamp').text
	# Chemicals related to stressor
	strdict[stressor.get('id')]['aopo:has_chemical_entity'] = []
	strdict[stressor.get('id')]['linktochemical'] = []
	if stressor.find(aopxml + 'chemicals') is not None:
		for chemical in stressor.find(aopxml + 'chemicals').findall(aopxml + 'chemical-initiator'):
			strdict[stressor.get('id')]['aopo:has_chemical_entity'].append('"' + chemical.get('user-term') + '"')
			strdict[stressor.get('id')]['linktochemical'].append(chemical.get('chemical-id'))  # user-term is not important
print('. . Done ')

# TAXONOMY
print('Parsing and organizing taxonomy information. . ', end="")
taxdict = {}
for tax in root.findall(aopxml + 'taxonomy'):
	taxdict[tax.get('id')] = {}
	taxdict[tax.get('id')]['dc:source'] = tax.find(aopxml + 'source').text
	taxdict[tax.get('id')]['dc:title'] = tax.find(aopxml + 'name').text
	if taxdict[tax.get('id')]['dc:source'] == 'NCBI':
		taxdict[tax.get('id')]['dc:identifier'] = 'ncbitaxon:' + tax.find(aopxml + 'source-id').text
	# The following lines cause issues, as the subjects will be literals
	elif taxdict[tax.get('id')]['dc:source'] is not None:
		taxdict[tax.get('id')]['dc:identifier'] = '"' + tax.find(aopxml + 'source-id').text + '"'
	else:
		taxdict[tax.get('id')]['dc:identifier'] = '"' + tax.find(aopxml + 'source-id').text + '"'
print('. . Done ')

# BIOLOGICAL EVENTS
print('Parsing and organizing biological event information. . ', end="")
bioactdict = {None: {}}
bioactdict[None]['dc:identifier'] = None
bioactdict[None]['dc:source'] = None
bioactdict[None]['dc:title'] = None
for bioact in root.findall(aopxml + 'biological-action'):
	bioactdict[bioact.get('id')] = {}
	bioactdict[bioact.get('id')]['dc:source'] = '"' + bioact.find(aopxml + 'source').text + '"'
	bioactdict[bioact.get('id')]['dc:title'] = '"' + bioact.find(aopxml + 'name').text + '"'
	bioactdict[bioact.get('id')]['dc:identifier'] = '"WIKI:' + bioact.find(aopxml + 'source-id').text + '"'

bioprodict = {None: {}}
bioprodict[None]['dc:identifier'] = None
bioprodict[None]['dc:source'] = None
bioprodict[None]['dc:title'] = None
for biopro in root.findall(aopxml + 'biological-process'):
	bioprodict[biopro.get('id')] = {}
	bioprodict[biopro.get('id')]['dc:source'] = '"' + biopro.find(aopxml + 'source').text + '"'
	bioprodict[biopro.get('id')]['dc:title'] = '"' + biopro.find(aopxml + 'name').text + '"'
	if bioprodict[biopro.get('id')]['dc:source'] == '"GO"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'go:' + biopro.find(aopxml + 'source-id').text[3:]  # predicate go:trerm possible
	elif bioprodict[biopro.get('id')]['dc:source'] == '"MI"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'mi:' + biopro.find(aopxml + 'source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] == '"MP"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'mp:' + biopro.find(aopxml + 'source-id').text[3:]
	elif bioprodict[biopro.get('id')]['dc:source'] == '"MESH"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'mesh:' + biopro.find(aopxml + 'source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] == '"HP"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'hp:' + biopro.find(aopxml + 'source-id').text[3:]
	elif bioprodict[biopro.get('id')]['dc:source'] == '"PCO"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'pco:' + biopro.find(aopxml + 'source-id').text[4:]
	elif bioprodict[biopro.get('id')]['dc:source'] == '"NBO"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'nbo:' + biopro.find(aopxml + 'source-id').text[4:]
	elif bioprodict[biopro.get('id')]['dc:source'] == '"VT"':
		bioprodict[biopro.get('id')]['dc:identifier'] = 'vt:' + biopro.find(aopxml + 'source-id').text[3:]
	else:
		# print('The following ontology was not found for biological process: '+biopro.find(aopxml+'source').text)
		bioprodict[biopro.get('id')]['dc:identifier'] = biopro.find(aopxml + 'source-id').text

bioobjdict = {None: {}}
bioobjdict[None]['dc:identifier'] = None
bioobjdict[None]['dc:source'] = None
bioobjdict[None]['dc:title'] = None
objectstoskip = []
for bioobj in root.findall(aopxml + 'biological-object'):
	bioobjdict[bioobj.get('id')] = {}
	bioobjdict[bioobj.get('id')]['dc:source'] = '"' + bioobj.find(aopxml + 'source').text + '"'
	bioobjdict[bioobj.get('id')]['dc:title'] = '"' + bioobj.find(aopxml + 'name').text + '"'
	if bioobjdict[bioobj.get('id')]['dc:source'] == '"PR"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'pr:' + bioobj.find(aopxml + 'source-id').text[3:]
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"CL"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'cl:' + bioobj.find(aopxml + 'source-id').text[3:]
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"MESH"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'mesh:' + bioobj.find(aopxml + 'source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"GO"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'go:' + bioobj.find(aopxml + 'source-id').text[3:]  # predicate go:trerm possible
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"UBERON"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'uberon:' + bioobj.find(aopxml + 'source-id').text[7:]
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"CHEBI"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'chebio:' + bioobj.find(aopxml + 'source-id').text[6:]
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"MP"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'mp:' + bioobj.find(aopxml + 'source-id').text[3:]
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"FMA"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'fma:' + bioobj.find(aopxml + 'source-id').text[4:]
	elif bioobjdict[bioobj.get('id')]['dc:source'] == '"PCO"':
		bioobjdict[bioobj.get('id')]['dc:identifier'] = 'pco:' + bioobj.find(aopxml + 'source-id').text[4:]
	else:
		# print ('The following ontology was not found for biological object: '+bioobj.find(aopxml + 'source-id').text)
		bioobjdict[bioobj.get('id')]['dc:identifier'] = '"' + bioobj.find(aopxml + 'source-id').text + '"'
print('. . Done ')

# KEY EVENTS, later to combine with TAXONOMY when writing file
print('Parsing and organizing Key Event information. . ', end="")
hgnclist = []
listofkedescriptions = []
for ke in root.findall(aopxml + 'key-event'):
	geneoverlapdict = {}
	if not ke.get('id') in kedict:
		kedict[ke.get('id')] = {}
	# General info about the KEs
	kedict[ke.get('id')]['dc:identifier'] = 'aop.events:' + refs['KEs'][ke.get('id')]
	kedict[ke.get('id')]['rdfs:label'] = '"KE ' + refs['KEs'][ke.get('id')] + '"'
	kedict[ke.get('id')]['foaf:page'] = '<http://identifiers.org/aop.events/' + refs['KEs'][ke.get('id')] + '>'
	kedict[ke.get('id')]['dc:title'] = '"' + ke.find(aopxml + 'title').text + '"'
	kedict[ke.get('id')]['dcterms:alternative'] = ke.find(aopxml + 'short-name').text
	if ke.find(aopxml + 'description').text is not None:
		if 'dc:description' not in kedict[ke.get('id')]:
			kedict[ke.get('id')]['dc:description'] = '"""' + TAG_RE.sub('', ke.find(aopxml + 'description').text) + '"""'
		else:
			kedict[ke.get('id')]['dc:description'] = '"""' + TAG_RE.sub('', ke.find(aopxml + 'description').text) + '\n' + TAG_RE.sub('', kedict[ke.get('id')]['dc:description']) + '"""'
		geneoverlapdict[ke.get('id')] = []
		for key in genedict:
			if genedict[key][1][1:-1] in ke.find(aopxml + 'description').text:
				for item in genedict[key]:
					if item in ke.find(aopxml + 'description').text and not 'hgnc:' + genedict[key][1][1:-1] in geneoverlapdict[ke.get('id')]:
						geneoverlapdict[ke.get('id')].append('hgnc:' + genedict[key][1][1:-1])
						if 'hgnc:' + genedict[key][1][1:-1] not in hgnclist:
							hgnclist.append('hgnc:' + genedict[key][1][1:-1])
		if not geneoverlapdict[ke.get('id')]:
			del geneoverlapdict[ke.get('id')]
	if ke.get('id') in geneoverlapdict:
		kedict[ke.get('id')]['dc:contributor'] = geneoverlapdict[ke.get('id')]
	if ke.find(aopxml + 'measurement-methodology').text is not None:
		kedict[ke.get('id')]['mmo:0000000'] = '"""' + TAG_RE.sub('', ke.find(aopxml + 'measurement-methodology').text) + '"""'
	kedict[ke.get('id')]['biological-organization-level'] = ke.find(aopxml + 'biological-organization-level').text
	kedict[ke.get('id')]['dc:source'] = ke.find(aopxml + 'source').text
	# Applicability
	for appl in ke.findall(aopxml + 'applicability'):
		for sex in appl.findall(aopxml + 'sex'):
			if 'pato:PATO_0000047' not in kedict[ke.get('id')]:
				kedict[ke.get('id')]['pato:PATO_0000047'] = [[sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text]]
			else:
				kedict[ke.get('id')]['pato:PATO_0000047'].append([sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text])
		for life in appl.findall(aopxml + 'life-stage'):
			if 'aopo:LifeStageContext' not in kedict[ke.get('id')]:
				kedict[ke.get('id')]['aopo:LifeStageContext'] = [[life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text]]
			else:
				kedict[ke.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text])
		for tax in appl.findall(aopxml + 'taxonomy'):
			if 'ncbitaxon:131567' not in kedict[ke.get('id')]:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kedict[ke.get('id')]['ncbitaxon:131567'] = [[tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']]]
			else:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kedict[ke.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']])
	# Biological Events
	if ke.find(aopxml + 'biological-events') is not None:
		kedict[ke.get('id')]['biological-event'] = {}
		kedict[ke.get('id')]['biological-event']['go:0008150'] = []
		kedict[ke.get('id')]['biological-event']['pato:PATO_0001241'] = []
		kedict[ke.get('id')]['biological-event']['pato:PATO_0000001'] = []
		for event in ke.find(aopxml + 'biological-events').findall(aopxml + 'biological-event'):

			if event.get('process-id') is not None:
				kedict[ke.get('id')]['biological-event']['go:0008150'].append(bioprodict[event.get('process-id')]['dc:identifier'])
			if event.get('object-id') is not None:
				kedict[ke.get('id')]['biological-event']['pato:PATO_0001241'].append(bioobjdict[event.get('object-id')]['dc:identifier'])
			if event.get('action-id') is not None:
				kedict[ke.get('id')]['biological-event']['pato:PATO_0000001'].append(bioactdict[event.get('action-id')]['dc:identifier'])
	# cell term / Organ term
	if ke.find(aopxml + 'cell-term') is not None:
		kedict[ke.get('id')]['aopo:CellTypeContext'] = {}
		kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'] = '"' + ke.find(aopxml + 'cell-term').find(aopxml + 'source').text + '"'
		kedict[ke.get('id')]['aopo:CellTypeContext']['dc:title'] = '"' + ke.find(aopxml + 'cell-term').find(aopxml + 'name').text + '"'
		if kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'] == '"CL"':
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier'] = ['cl:' + ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text[3:], ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text]
		elif kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'] == '"UBERON"':
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier'] = ['uberon:' + ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text[7:], ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text]
		else:
			# print ('The following ontology was not found for cell term: '+kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'])
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier'] = ['"' + ke.find(aopxml + 'cell-term').find(aopxml + 'source-id').text + '"', 'placeholder']
	if ke.find(aopxml + 'organ-term') is not None:
		kedict[ke.get('id')]['aopo:OrganContext'] = {}
		kedict[ke.get('id')]['aopo:OrganContext']['dc:source'] = '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'source').text + '"'
		kedict[ke.get('id')]['aopo:OrganContext']['dc:title'] = '"' + ke.find(aopxml + 'organ-term').find(aopxml + 'name').text + '"'
		if kedict[ke.get('id')]['aopo:OrganContext']['dc:source'] == '"UBERON"':
			kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier'] = ['uberon:' + ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text[7:], ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text]
		else:
			# print ('The following ontology was not found for organ term: '+kedict[ke.get('id')]['aopo:OrganContext']['dc:source'])
			kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier'] = [
				'"' + ke.find(aopxml + 'organ-term').find(aopxml + 'source-id').text + '"', 'placeholder']
	# Stressor related to KE
	if ke.find(aopxml + 'key-event-stressors') is not None:
		kedict[ke.get('id')]['ncit:C54571'] = {}
		for stressor in ke.find(aopxml + 'key-event-stressors').findall(aopxml + 'key-event-stressor'):
			kedict[ke.get('id')]['ncit:C54571'][stressor.get('stressor-id')] = {}
			kedict[ke.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['dc:identifier'] = strdict[stressor.get('stressor-id')]['dc:identifier']
			kedict[ke.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['aopo:has_evidence'] = stressor.find(aopxml + 'evidence').text
print('. . Done ')
print('Number of unique genes identified after KEs: ', len(hgnclist))

# KEY EVENT RELATIONSHIPS
print('Parsing and organizing Key Event Relationship information. . ', end="")
kerdict = {}
for ker in root.findall(aopxml + 'key-event-relationship'):
	kerdict[ker.get('id')] = {}
	geneoverlapdict = {}
	# General info about the KERs
	kerdict[ker.get('id')]['dc:identifier'] = 'aop.relationships:' + refs['KERs'][ker.get('id')]
	kerdict[ker.get('id')]['rdfs:label'] = '"KER ' + refs['KERs'][ker.get('id')] + '"'
	kerdict[ker.get('id')]['foaf:page'] = '<http://identifiers.org/aop.relationships/' + refs['KERs'][ker.get('id')] + '>'
	kerdict[ker.get('id')]['dc:source'] = ker.find(aopxml + 'source').text
	kerdict[ker.get('id')]['dcterms:created'] = ker.find(aopxml + 'creation-timestamp').text
	kerdict[ker.get('id')]['dcterms:modified'] = ker.find(aopxml + 'last-modification-timestamp').text
	geneoverlapdict[ker.get('id')] = []
	if ker.find(aopxml + 'description').text is not None:
		kerdict[ker.get('id')]['dc:description'] = '"""' + TAG_RE.sub('', ker.find(aopxml + 'description').text) + '"""'
		for key in genedict:
			if genedict[key][1][1:-1] in ker.find(aopxml + 'description').text:
				for item in genedict[key]:
					if item in ker.find(aopxml + 'description').text and not 'hgnc:' + genedict[key][1][1:-1] in geneoverlapdict[ker.get('id')]:
						geneoverlapdict[ker.get('id')].append('hgnc:' + genedict[key][1][1:-1])
						if 'hgnc:' + genedict[key][1][1:-1] not in hgnclist:
							hgnclist.append('hgnc:' + genedict[key][1][1:-1])
	for weight in ker.findall(aopxml + 'weight-of-evidence'):
		if weight.find(aopxml + 'biological-plausibility').text is not None:
			kerdict[ker.get('id')]['ncit:C80263'] = '"""' + TAG_RE.sub('', weight.find(aopxml + 'biological-plausibility').text) + '"""'
			for key in genedict:
				if genedict[key][1][1:-1] in weight.find(aopxml + 'biological-plausibility').text:
					for item in genedict[key]:
						if item in weight.find(aopxml + 'biological-plausibility').text and not 'hgnc:' + genedict[key][1][1:-1] in geneoverlapdict[ker.get('id')]:
							geneoverlapdict[ker.get('id')].append('hgnc:' + genedict[key][1][1:-1])
							if 'hgnc:' + genedict[key][1][1:-1] not in hgnclist:
								hgnclist.append('hgnc:' + genedict[key][1][1:-1])
		if weight.find(aopxml + 'emperical-support-linkage').text is not None:
			kerdict[ker.get('id')]['edam:data_2042'] = '"""' + TAG_RE.sub('', weight.find(aopxml + 'emperical-support-linkage').text) + '"""'
			for key in genedict:
				if genedict[key][1][1:-1] in weight.find(aopxml + 'emperical-support-linkage').text:
					for item in genedict[key]:
						if item in weight.find(aopxml + 'emperical-support-linkage').text and not 'hgnc:' + genedict[key][1][1:-1] in geneoverlapdict[ker.get('id')]:
							geneoverlapdict[ker.get('id')].append('hgnc:' + genedict[key][1][1:-1])
							if 'hgnc:' + genedict[key][1][1:-1] not in hgnclist:
								hgnclist.append('hgnc:' + genedict[key][1][1:-1])
		if weight.find(aopxml + 'uncertainties-or-inconsistencies').text is not None:
			kerdict[ker.get('id')]['ncit:C71478'] = '"""' + TAG_RE.sub('', weight.find(aopxml + 'uncertainties-or-inconsistencies').text) + '"""'
	if not geneoverlapdict[ker.get('id')]:
		del geneoverlapdict[ker.get('id')]
	if ker.get('id') in geneoverlapdict:
		kerdict[ker.get('id')]['dc:contributor'] = geneoverlapdict[ker.get('id')]

	kerdict[ker.get('id')]['aopo:has_upstream_key_event'] = {}
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']['id'] = ker.find(aopxml + 'title').find(aopxml + 'upstream-id').text
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']['dc:identifier'] = 'aop.events:' + refs['KEs'][ker.find(aopxml + 'title').find(aopxml + 'upstream-id').text]
	kerdict[ker.get('id')]['aopo:has_downstream_key_event'] = {}
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']['id'] = ker.find(aopxml + 'title').find(aopxml + 'downstream-id').text
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']['dc:identifier'] = 'aop.events:' + refs['KEs'][ker.find(aopxml + 'title').find(aopxml + 'downstream-id').text]
	# taxonomic applicability
	for appl in ker.findall(aopxml + 'taxonomic-applicability'):
		for sex in appl.findall(aopxml + 'sex'):
			if 'pato:PATO_0000047' not in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['pato:PATO_0000047'] = [[sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text]]
			else:
				kerdict[ker.get('id')]['pato:PATO_0000047'].append([sex.find(aopxml + 'evidence').text, sex.find(aopxml + 'sex').text])
		for life in appl.findall(aopxml + 'life-stage'):
			if 'aopo:LifeStageContext' not in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['aopo:LifeStageContext'] = [[life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text]]
			else:
				kerdict[ker.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml + 'evidence').text, life.find(aopxml + 'life-stage').text])
		for tax in appl.findall(aopxml + 'taxonomy'):
			if 'ncbitaxon:131567' not in kerdict[ker.get('id')]:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kerdict[ker.get('id')]['ncbitaxon:131567'] = [[tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']]]
			else:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kerdict[ker.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'), tax.find(aopxml + 'evidence').text, taxdict[tax.get('taxonomy-id')]['dc:identifier'], taxdict[tax.get('taxonomy-id')]['dc:source'], taxdict[tax.get('taxonomy-id')]['dc:title']])
print('. . Done ')
print('Number of unique genes identified after KEs and KERs: ', len(hgnclist), '\n')

# Gene identifiers:
geneiddict = {}
listofentrez = []
listofensembl = []
listofuniprot = []
for gene in hgnclist:
	a = requests.get('http://localhost:8080//Human/xrefs/H/' + gene[5:]).text.split('\n')
	dictionaryforgene = {}
	if 'html' not in a:
		for item in a:
			b = item.split('\t')
			if len(b) == 2:
				if b[1] not in dictionaryforgene:
					dictionaryforgene[b[1]] = []
					dictionaryforgene[b[1]].append(b[0])
				else:
					dictionaryforgene[b[1]].append(b[0])
	geneiddict[gene] = []
	if 'Entrez Gene' in dictionaryforgene:
		for entrez in dictionaryforgene['Entrez Gene']:
			if 'ncbigene:'+entrez not in listofentrez:
				listofentrez.append('ncbigene:'+entrez)
			geneiddict[gene].append('ncbigene:'+entrez)
	if 'Ensembl' in dictionaryforgene:
		for ensembl in dictionaryforgene['Ensembl']:
			if 'ensembl:' + ensembl not in listofensembl:
				listofensembl.append('ensembl:'+ensembl)
			geneiddict[gene].append('ensembl:'+ensembl)
	if 'Uniprot-TrEMBL' in dictionaryforgene:
		for uniprot in dictionaryforgene['Uniprot-TrEMBL']:
			if 'uniprot:'+uniprot not in listofuniprot:
				listofuniprot.append('uniprot:'+uniprot)
			geneiddict[gene].append('uniprot:'+uniprot)


# Creating output file
print('Creating output TTL file. . ', end="")
g = open('/home/marvin.martens/Documents/AOPWikiRDF/AOPWikiRDF.ttl', 'w', encoding='utf-8')
print('. . Done ')

# Writing prefixes
print('Writing rdf prefixes. . ', end="")
g.write('@prefix dc: <http://purl.org/dc/elements/1.1/> .\n@prefix dcterms: <http://purl.org/dc/terms/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n@prefix aop: <http://identifiers.org/aop/> .\n@prefix aop.events: <http://identifiers.org/aop.events/> .\n@prefix aop.relationships: <http://identifiers.org/aop.relationships/> .\n@prefix aop.stressor: <http://identifiers.org/aop.stressor/> .\n@prefix aopo: <http://aopkb.org/aop_ontology#> .\n@prefix skos: <http://www.w3.org/2004/02/skos/core#> . \n@prefix cas: <http://identifiers.org/cas/> .\n@prefix inchikey: <http://identifiers.org/inchikey/> .\n@prefix pato: <http://purl.obolibrary.org/obo/> .\n@prefix ncbitaxon: <http://purl.bioontology.org/ontology/NCBITAXON/> .\n@prefix cl: <http://purl.obolibrary.org/obo/CL_> .\n@prefix uberon: <http://purl.obolibrary.org/obo/UBERON_> .\n@prefix go: <http://purl.obolibrary.org/obo/GO_> .\n@prefix mi: <http://purl.obolibrary.org/obo/MI_> .\n@prefix mp: <http://purl.obolibrary.org/obo/MP_> .\n@prefix mesh: <http://purl.bioontology.org/ontology/MESH/> .\n@prefix hp: <http://purl.obolibrary.org/obo/HP_> .\n@prefix pco: <http://purl.obolibrary.org/obo/PCO_> .\n@prefix nbo: <http://purl.obolibrary.org/obo/NBO_> .\n@prefix vt: <http://purl.obolibrary.org/obo/VT_> .\n@prefix pr: <http://purl.obolibrary.org/obo/PR_> .\n@prefix chebio: <http://purl.obolibrary.org/obo/CHEBI_> .\n@prefix fma: <http://purl.org/sig/ont/fma/fma> .\n@prefix cheminf: <http://semanticscience.org/resource/> .\n@prefix ncit: <http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#> .\n@prefix comptox: <https://identifiers.org/comptox/> .\n@prefix mmo: <http://purl.obolibrary.org/obo/MMO_> .\n@prefix chebi: <https://identifiers.org/chebi/> .\n@prefix chemspider: <https://identifiers.org/chemspider/> .\n@prefix wikidata: <https://identifiers.org/wikidata/> .\n@prefix chembl.compound: <https://identifiers.org/chembl.compound/> .\n@prefix pubchem.compound: <https://identifiers.org/pubchem.compound/> .\n@prefix drugbank: <https://identifiers.org/drugbank/> .\n@prefix kegg.compound: <https://identifiers.org/kegg.compound/> .\n@prefix lipidmaps: <https://identifiers.org/lipidmaps/> .\n@prefix hmdb: <https://identifiers.org/hmdb/> .\n@prefix ensembl: <http://identifiers.org/ensembl/> .\n@prefix edam: <http://edamontology.org/> .\n@prefix hgnc: <https://identifiers.org/hgnc/>.\n@prefix ncbigene: <https://identifiers.org/ncbigene/>.\n@prefix uniprot: <https://identifiers.org/uniprot/>.\n\n')
print('. . Done ')

# Writing AOP triples
print('Writing AOP triples. . ', end="")
naopo = 0
naopohaschem = 0
naopohaske = 0
naopohasker = 0
naopohasmie = 0
naopohasao = 0
naopolife = 0
naopocell = 0
naopoorgan = 0
naopoupke = 0
naopodownke = 0
naop = 0
naopa = 0
for aop in aopdict:
	g.write(aopdict[aop]['dc:identifier'] + '\n\ta\taopo:AdverseOutcomePathway ;\n\tdc:identifier\t' + aopdict[aop]['dc:identifier'] + ' ;\n\trdfs:label\t' + aopdict[aop]['rdfs:label'] + ' ;\n\tfoaf:page\t' + aopdict[aop]['foaf:page'] + ' ;\n\tdc:title\t' + aopdict[aop]['dc:title'] + ' ;\n\tdcterms:alternative\t"' + aopdict[aop]['dcterms:alternative'] + '" ;\n\tdc:source\t"' + aopdict[aop]['dc:source'] + '" ;\n\tdcterms:created\t"' + aopdict[aop]['dcterms:created'] + '" ;\n\tdcterms:modified\t"' + aopdict[aop]['dcterms:modified'] + '"')
	naop += 1
	naopa += 9
	if 'dc:creator' in aopdict[aop]:
		g.write(' ;\n\tdc:creator\t' + aopdict[aop]['dc:creator'])
		naopa += 1
	if 'dcterms:abstract' in aopdict[aop]:
		g.write(' ;\n\tdcterms:abstract\t' + aopdict[aop]['dcterms:abstract'])
		naopa += 1
	listofthings = []
	for KE in aopdict[aop]['aopo:has_key_event']:
		listofthings.append(aopdict[aop]['aopo:has_key_event'][KE]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\taopo:has_key_event\t' + (','.join(listofthings)))
		naopa += 1
		naopo += 1
		naopohaske += 1
	listofthings = []
	for KER in aopdict[aop]['aopo:has_key_event_relationship']:
		listofthings.append(aopdict[aop]['aopo:has_key_event_relationship'][KER]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\taopo:has_key_event_relationship\t' + (','.join(listofthings)))
		naopo += 1
		naopohasker += 1
		naopa += 1
	listofthings = []
	for mie in aopdict[aop]['aopo:has_molecular_initiating_event']:
		listofthings.append(aopdict[aop]['aopo:has_molecular_initiating_event'][mie]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\taopo:has_molecular_initiating_event\t' + (','.join(listofthings)))
		naopo += 1
		naopohasmie += 1
		naopa += 1
	listofthings = []
	for ao in aopdict[aop]['aopo:has_adverse_outcome']:
		listofthings.append(aopdict[aop]['aopo:has_adverse_outcome'][ao]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\taopo:has_adverse_outcome\t' + (','.join(listofthings)))
		naopo += 1
		naopohasao += 1
		naopa += 1
	listofthings = []
	for stressor in aopdict[aop]['ncit:C54571']:
		listofthings.append(aopdict[aop]['ncit:C54571'][stressor]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\tncit:C54571\t' + (','.join(listofthings)))
		naopa += 1
	listofthings = []
	if 'pato:PATO_0000047' in aopdict[aop]:
		for sex in aopdict[aop]['pato:PATO_0000047']:
			listofthings.append('"' + sex[1] + '"')
		if not listofthings == []:
			g.write(' ;\n\tpato:PATO_0000047\t' + (','.join(listofthings)))
			naopa += 1
	listofthings = []
	if 'aopo:LifeStageContext' in aopdict[aop]:
		for lifestage in aopdict[aop]['aopo:LifeStageContext']:
			listofthings.append('"' + lifestage[1] + '"')
		if not listofthings == []:
			g.write(' ;\n\taopo:LifeStageContext\t' + (','.join(listofthings)))
			naopo += 1
			naopolife += 1
			naopa += 1
	if 'dc:accessRights' in aopdict[aop]:
		g.write(' ;\n\tdc:accessRights\t"' + aopdict[aop]['dc:accessRights'] + '"')
		naopa += 1
	g.write(' .\n\n')
print('. . Done \nNumber of AOPs: '+str(naop))
print('Number of attributes for AOPs: '+str(naopa)+'\n')

# Creating cell term and organ term dictionary
cterm = {}
oterm = {}
# Writing KE triples
print('Writing KE triples. . ', end="")
nke = 0
for ke in kedict:
	g.write(kedict[ke]['dc:identifier'] + '\n\ta\taopo:KeyEvent ;\n\tdc:identifier\t' + kedict[ke]['dc:identifier'] + ' ;\n\trdfs:label\t' + kedict[ke]['rdfs:label'] + ' ;\n\tfoaf:page\t' + kedict[ke]['foaf:page'] + ' ;\n\tdc:title\t' + kedict[ke]['dc:title'] + ' ;\n\tdcterms:alternative\t"' + kedict[ke]['dcterms:alternative'] + '" ;\n\tdc:source\t"' + kedict[ke]['dc:source'] + '"')
	nke += 1
	if 'dc:description' in kedict[ke]:
		g.write(' ;\n\tdc:description\t' + kedict[ke]['dc:description'])
	if 'mmo:0000000' in kedict[ke]:
		g.write(' ;\n\tmmo:0000000\t' + kedict[ke]['mmo:0000000'])
	if 'dc:contributor' in kedict[ke]:
		g.write(' ;\n\tdc:contributor\t' + ','.join(kedict[ke]['dc:contributor']))
	listofthings = []
	if 'pato:PATO_0000047' in kedict[ke]:
		for sex in kedict[ke]['pato:PATO_0000047']:
			listofthings.append('"' + sex[1] + '"')
		if not listofthings == []:
			g.write(' ;\n\tpato:PATO_0000047\t' + (','.join(listofthings)))
	listofthings = []
	if 'aopo:LifeStageContext' in kedict[ke]:
		for lifestage in kedict[ke]['aopo:LifeStageContext']:
			listofthings.append('"' + lifestage[1] + '"')
		if not listofthings == []:
			g.write(' ;\n\taopo:LifeStageContext\t' + (','.join(listofthings)))
			naopo += 1
			naopolife += 1
	listofthings = []
	if 'ncbitaxon:131567' in kedict[ke]:
		for taxonomy in kedict[ke]['ncbitaxon:131567']:
			listofthings.append(taxonomy[2])
		if not listofthings == []:
			g.write(' ;\n\tncbitaxon:131567\t' + (','.join(listofthings)))
	listofthings = []
	if 'ncit:C54571' in kedict[ke]:
		for stressor in kedict[ke]['ncit:C54571']:
			listofthings.append(kedict[ke]['ncit:C54571'][stressor]['dc:identifier'])
		if not listofthings == []:
			g.write(' ;\n\tncit:C54571\t' + (','.join(listofthings)))

	if 'aopo:CellTypeContext' in kedict[ke]:
		g.write(' ;\n\taopo:CellTypeContext\t' + kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0])
		naopo += 1
		naopocell += 1
		if not kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0] in cterm:
			cterm[kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]] = {}
			cterm[kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]]['dc:source'] = kedict[ke]['aopo:CellTypeContext']['dc:source']
			cterm[kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]]['dc:title'] = kedict[ke]['aopo:CellTypeContext']['dc:title']
	if 'aopo:OrganContext' in kedict[ke]:
		g.write(' ;\n\taopo:OrganContext\t' + kedict[ke]['aopo:OrganContext']['dc:identifier'][0])
		naopo += 1
		naopoorgan += 1
		if not kedict[ke]['aopo:OrganContext']['dc:identifier'][0] in oterm:
			oterm[kedict[ke]['aopo:OrganContext']['dc:identifier'][0]] = {}
			oterm[kedict[ke]['aopo:OrganContext']['dc:identifier'][0]]['dc:source'] = kedict[ke]['aopo:OrganContext']['dc:source']
			oterm[kedict[ke]['aopo:OrganContext']['dc:identifier'][0]]['dc:title'] = kedict[ke]['aopo:OrganContext']['dc:title']
	if 'biological-event' in kedict[ke]:
		if len(kedict[ke]['biological-event']['go:0008150']) > 0:
			g.write(' ;\n\tgo:0008150\t' + (','.join(kedict[ke]['biological-event']['go:0008150'])))
		if len(kedict[ke]['biological-event']['pato:PATO_0000001']) > 0:
			g.write(' ;\n\tpato:PATO_0000001\t' + (','.join(kedict[ke]['biological-event']['pato:PATO_0000001'])))
		if len(kedict[ke]['biological-event']['pato:PATO_0001241']) > 0:
			g.write(' ;\n\tpato:PATO_0001241\t' + (','.join(kedict[ke]['biological-event']['pato:PATO_0001241'])))

	listofthings = []
	for aop in aopdict:
		if ke in aopdict[aop]['aopo:has_key_event']:
			listofthings.append(aopdict[aop]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\tdcterms:isPartOf\t' + (','.join(listofthings)))

	g.write(' .\n\n')
print('. . Done \nNumber of KEs: '+str(nke)+'\n')

# Writing KER triples
print('Writing KER triples. . ', end="")
nker = 0
for ker in kerdict:
	g.write(kerdict[ker]['dc:identifier'] + '\n\ta\taopo:KeyEventRelationship ;\n\tdc:identifier\t' + kerdict[ker]['dc:identifier'] + ' ;\n\trdfs:label\t' + kerdict[ker]['rdfs:label'] + ' ;\n\tfoaf:page\t' + kerdict[ker]['foaf:page'] + ' ;\n\tdcterms:created\t"' + kerdict[ker]['dcterms:created'] + '" ;\n\tdcterms:modified\t"' + kerdict[ker]['dcterms:modified'] + '" ;\n\taopo:has_upstream_key_event\t' + kerdict[ker]['aopo:has_upstream_key_event']['dc:identifier'] + ' ;\n\taopo:has_downstream_key_event\t' + kerdict[ker]['aopo:has_downstream_key_event']['dc:identifier'])
	naopo += 2
	naopoupke += 1
	naopodownke += 1
	nker += 1
	if 'dc:description' in kerdict[ker]:
		g.write(' ;\n\tdc:description\t' + kerdict[ker]['dc:description'])
	if 'ncit:C80263' in kerdict[ker]:
		g.write(' ;\n\tncit:C80263\t' + kerdict[ker]['ncit:C80263'])
	if 'edam:data_2042' in kerdict[ker]:
		g.write(' ;\n\tedam:data_2042\t' + kerdict[ker]['edam:data_2042'].replace("\\",""))
	if 'ncit:C71478' in kerdict[ker]:
		g.write(' ;\n\tncit:C71478\t' + kerdict[ker]['ncit:C71478'])
	if 'dc:contributor' in kerdict[ker]:
		if kerdict[ker]['dc:contributor'] is not None:
			g.write(' ;\n\tdc:contributor\t' + ','.join(kerdict[ker]['dc:contributor']))
	listofthings = []
	if 'pato:PATO_0000047' in kerdict[ker]:
		for sex in kerdict[ker]['pato:PATO_0000047']:
			listofthings.append('"' + sex[1] + '"')
		if not listofthings == []:
			g.write(' ;\n\tpato:PATO_0000047\t' + (','.join(listofthings)))
	listofthings = []
	if 'aopo:LifeStageContext' in kerdict[ker]:
		for lifestage in kerdict[ker]['aopo:LifeStageContext']:
			listofthings.append('"' + lifestage[1] + '"')
		if not listofthings == []:
			g.write(' ;\n\taopo:LifeStageContext\t' + (','.join(listofthings)))
			naopo += 1
			naopolife += 1
	listofthings = []
	if 'ncbitaxon:131567' in kerdict[ker]:
		for taxonomy in kerdict[ker]['ncbitaxon:131567']:
			listofthings.append(taxonomy[2])
		if not listofthings == []:
			g.write(' ;\n\tncbitaxon:131567\t' + (','.join(listofthings)))
	listofthings = []
	for aop in aopdict:
		if ker in aopdict[aop]['aopo:has_key_event_relationship']:
			listofthings.append(aopdict[aop]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\tdcterms:isPartOf\t' + (','.join(listofthings)))
	g.write(' .\n\n')
print('. . Done \nNumber of KERs: '+str(nker)+'\n')

# Writing Taxonomy triples
print('Writing Taxonomy triples. . ', end="")
ntax = 0
for tax in taxdict:
	if 'dc:identifier' in taxdict[tax]:
		if '"' not in taxdict[tax]['dc:identifier']:
			g.write(taxdict[tax]['dc:identifier'] + '\n\ta\tncbitaxon:131567 ;\n\tdc:identifier\t' + taxdict[tax]['dc:identifier'] + ' ;\n\tdc:title\t"' + taxdict[tax]['dc:title'])
			ntax += 1
			if taxdict[tax]['dc:source'] is not None:
				g.write('" ;\n\tdc:source\t"' + taxdict[tax]['dc:source'])
			g.write('" .\n\n')
print('. . Done \nNumber of taxonomies: '+str(ntax)+'\n')

# Writing Stressor triples
print('Writing Stressor triples. . ', end="")

nstr = 0
nhaschem = 0
for stressor in strdict:
	g.write(strdict[stressor]['dc:identifier'] + '\n\ta\tncit:C54571 ;\n\tdc:identifier\t' + strdict[stressor]['dc:identifier'] + ' ;\n\trdfs:label\t' + strdict[stressor]['rdfs:label'] + ' ;\n\tfoaf:page\t' + strdict[stressor]['foaf:page'] + ' ;\n\tdc:title\t' + strdict[stressor]['dc:title'] + ' ;\n\tdcterms:created\t"' + strdict[stressor]['dcterms:created'] + '" ;\n\tdcterms:modified\t"' + strdict[stressor]['dcterms:modified'] + '"')
	nstr += 1
	if 'dc:description' in strdict[stressor]:
		g.write(' ;\n\tdc:description\t' + strdict[stressor]['dc:description'])
	listofthings = []
	for chem in strdict[stressor]['linktochemical']:
		listofthings.append(chedict[chem]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\taopo:has_chemical_entity\t' + ','.join(listofthings))
		nhaschem += 1
		naopo += 1
		naopohaschem += 1
	listofthings = []
	for ke in kedict:
		if 'ncit:C54571' in kedict[ke]:
			if stressor in kedict[ke]['ncit:C54571']:
				listofthings.append(kedict[ke]['dc:identifier'])
	for item in listofthings:
		for ke in kedict:
			if kedict[ke]['dc:identifier'] == item:
				for aop in aopdict:
					if ke in aopdict[aop]['aopo:has_key_event'] and aopdict[aop]['dc:identifier'] not in listofthings:
						listofthings.append(aopdict[aop]['dc:identifier'])
	for aop in aopdict:
		if stressor in aopdict[aop]['ncit:C54571']:
			if not aopdict[aop]['dc:identifier'] in listofthings:
				listofthings.append(aopdict[aop]['dc:identifier'])
	if not listofthings == []:
		g.write(' ;\n\tdcterms:isPartOf\t' + (','.join(listofthings)))
	g.write(' .\n\n')
print('. . Done \nNumber of stressors: '+str(nstr))
print('Number of stressors with at least one chemical linked to it: '+str(nhaschem)+'\n')

# Writing Chemical triples
print('Writing Chemical triples. . ', end="")
nchem = 0
ninchi = 0
ndsstox = 0
for che in chedict:
	if 'dc:identifier' in chedict[che] and '"' not in chedict[che]['dc:identifier']:
		g.write(chedict[che]['dc:identifier'] + '\n\tdc:identifier\t' + chedict[che]['dc:identifier'])
		nchem += 1
		if 'cheminf:CHEMINF_000446' in chedict[che]:
			g.write(' ;\n\ta\tcheminf:CHEMINF_000000 ;\n\tcheminf:CHEMINF_000446\t' + chedict[che]['cheminf:CHEMINF_000446'])
		if not chedict[che]['cheminf:CHEMINF_000059'] == 'inchikey:None':
			g.write(' ;\n\tcheminf:CHEMINF_000059\t' + chedict[che]['cheminf:CHEMINF_000059'])
			ninchi += 1
		if 'dc:title' in chedict[che]:
			g.write(' ;\n\tdc:title\t' + chedict[che]['dc:title'])
		if 'cheminf:CHEMINF_000568' in chedict[che]:
			g.write(' ;\n\tcheminf:CHEMINF_000568\t' + str(chedict[che]['cheminf:CHEMINF_000568']))
			ndsstox += 1
		listofexactmatches = []
		if 'cheminf:CHEMINF_000407' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000407']))
		if 'cheminf:CHEMINF_000405' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000405']))
		if 'cheminf:CHEMINF_000567' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000567']))
		if 'cheminf:CHEMINF_000412' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000412']))
		if 'cheminf:CHEMINF_0001408' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000140']))
		if 'cheminf:CHEMINF_000406' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000406']))
		if 'cheminf:CHEMINF_000408' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000408']))
		if 'cheminf:CCHEMINF_000409' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000409']))
		if 'cheminf:CHEMINF_000564' in chedict[che]:
			listofexactmatches.append(','.join(chedict[che]['cheminf:CHEMINF_000564']))
		if 'cheminf:CHEMINF_000407' in chedict[che] or 'cheminf:CHEMINF_000405' in chedict[che] or 'cheminf:CHEMINF_000567' in chedict[che] or 'cheminf:CHEMINF_000412' in chedict[che] or 'cheminf:CHEMINF_0001408' in chedict[che] or 'cheminf:CHEMINF_000406' in chedict[che] or 'cheminf:CHEMINF_000408' in chedict[che] or 'cheminf:CCHEMINF_000409' in chedict[che] or 'cheminf:CHEMINF_000564' in chedict[che]:
			g.write(' ;\n\tskos:exactMatch\t'+','.join(listofexactmatches))
		listofthings = []
		if 'dcterms:alternative' in chedict[che]:
			for alt in chedict[che]['dcterms:alternative']:
				listofthings.append('"' + alt + '"')
			g.write(' ;\n\tdcterms:alternative\t' + ','.join(listofthings))
		listofthings = []
		for stressor in strdict:
			if 'aopo:has_chemical_entity' in strdict[stressor]:
				if che in strdict[stressor]['linktochemical']:
					listofthings.append(strdict[stressor]['dc:identifier'])
		if not listofthings == []:
			g.write(' ;\n\tdcterms:isPartOf\t' + (','.join(listofthings)))
		g.write(' .\n\n')
print('. . Done \nNumber of chemicals: '+str(nchem))
print('Number of InchiKeys: '+str(ninchi))
print('Number of CompTox identifiers: '+str(ndsstox)+'\n')

print('Writing chemical identifiers. . ', end="")
ntot = 0
ncheb = 0
nchems = 0
nwd = 0
nchembl = 0
npub = 0
ndrug = 0
nkegg = 0
nlip = 0
nhmdb = 0
for chebi in listofchebi:
	g.write(chebi + '\tcheminf:CHEMINF_000407\t"'+chebi[6:]+'".\n\n')
	ntot += 1
	ncheb += 1
for chemspider in listofchemspider:
	g.write(chemspider + '\tcheminf:CHEMINF_000405\t"'+chemspider[11:]+'".\n\n')
	ntot += 1
	nchems += 1
for wd in listofwikidata:
	g.write(wd + '\tcheminf:CHEMINF_000567\t"'+wd[9:]+'".\n\n')
	ntot += 1
	nwd += 1
for chembl in listofchembl:
	g.write(chembl + '\tcheminf:CHEMINF_000412\t"'+chembl[16:]+'".\n\n')
	ntot += 1
	nchembl += 1
for pubchem in listofpubchem:
	g.write(pubchem + '\tcheminf:CHEMINF_000140\t"'+pubchem[17:]+'".\n\n')
	ntot += 1
	npub += 1
for drugbank in listofdrugbank:
	g.write(drugbank + '\tcheminf:CHEMINF_000412\t"'+drugbank[9:]+'".\n\n')
	ntot += 1
	ndrug += 1
for kegg in listofkegg:
	g.write(kegg + '\tcheminf:CHEMINF_000409\t"'+kegg[14:]+'".\n\n')
	ntot += 1
	nkegg += 1
for lipidmaps in listoflipidmaps:
	g.write(lipidmaps + '\tcheminf:CHEMINF_000564\t"'+lipidmaps[10:]+'".\n\n')
	ntot += 1
	nlip += 1
for hmdb in listofhmdb:
	g.write(hmdb + '\tcheminf:CHEMINF_000408\t"'+hmdb[5:]+'".\n\n')
	ntot += 1
	nhmdb += 1
print('. . Done \nTotal number of chemical identifiers: '+str(ntot))
print('Number of ChEBI chemical identifiers: '+str(ncheb))
print('Number of Chemspider chemical identifiers: '+str(nchems))
print('Number of Wikidata chemical identifiers: '+str(nwd))
print('Number of Chembl chemical identifiers: '+str(nchembl))
print('Number of Pubchem chemical identifiers: '+str(npub))
print('Number of Drugbank chemical identifiers: '+str(ndrug))
print('Number of Kegg chemical identifiers: '+str(nkegg))
print('Number of Lipidmaps chemical identifiers: '+str(nlip))
print('Number of HMDB chemical identifiers: '+str(nhmdb)+'\n')

print('Writing gene identifiers. . ', end="")
ngen = 0
numens = 0
nentrez = 0
nhgnc = 0
nuniprot = 0
for hgnc in hgnclist:
	g.write(hgnc + '\tedam:data_2298\t"'+hgnc[5:]+'"')
	nhgnc += 1
	ngen += 1
	if not geneiddict[hgnc] == []:
		g.write(' ;\n\tskos:exactMatch\t'+','.join(geneiddict[hgnc]))
	g.write('.\n\n')
print('. . Done \nTotal number of gene identifiers: '+str(ngen)+'\n')

for entrez in listofentrez:
	g.write(entrez + '\tedam:data_1027\t"'+entrez[9:]+'".\n\n')
	ngen += 1
	nentrez += 1
for ensembl in listofensembl:
	g.write(ensembl + '\tedam:data_1033\t"'+ensembl[8:]+'".\n\n')
	ngen += 1
	numens += 1
for uniprot in listofuniprot:
	g.write(uniprot + '\tedam:data_2291\t"'+uniprot[8:]+'".\n\n')
	ngen += 1
	nuniprot += 1

print('Number of HGNC identifiers: '+str(nhgnc))
print('Number of Ensembl identifiers: '+str(numens))
print('Number of Entrez Gene / NCBI Gene identifiers: '+str(nentrez))
print('Number of Uniprot identifiers: '+str(nuniprot)+'\n')

# Writing Biological Process triples
print('Writing Biological Process triples. . ', end="")
numbiopro = 0
for pro in bioprodict:
	if pro is not None:
		g.write(bioprodict[pro]['dc:identifier'] + '\n\tdc:identifier\t' + bioprodict[pro]['dc:identifier'] + ' ;\n\tdc:title\t' + bioprodict[pro]['dc:title'] + ' ;\n\tdc:source\t' + bioprodict[pro]['dc:source'] + ' . \n\n')
		numbiopro += 1
print('. . Done \nNumber of biological processes: '+str(numbiopro)+'\n')

# Writing Biological Object triples
print('Writing Biological Object triples. . ', end="")
numbioobj = 0
for obj in bioobjdict:
	if obj is not None and 'TAIR' not in bioobjdict[obj]['dc:identifier']:
		g.write(bioobjdict[obj]['dc:identifier'] + '\n\tdc:identifier\t' + bioobjdict[obj]['dc:identifier'] + ' ;\n\tdc:title\t' + bioobjdict[obj]['dc:title'] + ' ;\n\tdc:source\t' + bioobjdict[obj]['dc:source'] + ' . \n\n')
		numbioobj += 1
print('. . Done \nNumber of biological objects: '+str(numbioobj)+'\n')

# Writing Biological Action triples
print('Writing Biological Action triples. . ', end="")
numbioact = 0
for act in bioactdict:
	if act is not None:
		if '"' not in bioactdict[act]['dc:identifier']:
			g.write(bioactdict[act]['dc:identifier'] + '\n\tdc:identifier\t' + bioactdict[act]['dc:identifier'] + ' ;\n\tdc:title\t' + bioactdict[act]['dc:title'] + ' ;\n\tdc:source\t' + bioactdict[act]['dc:source'] + ' . \n\n')
			numbioact += 1
print('. . Done \nNumber of biological actions: '+str(numbioact)+'\n')

# Writing Cell term triples
print('Writing Cell term triples. . ', end="")
numcterm = 0
for item in cterm:
	if '"' not in item:
		g.write(item + '\n\tdc:identifier\t' + item + ' ;\n\tdc:title\t' + cterm[item]['dc:title'] + ' ;\n\tdc:source\t' + cterm[item]['dc:source'] + ' .\n\n')
		numcterm += 1
print('. . Done \nNumber of cell terms: '+str(numcterm)+'\n')

# Writing Organ term triples
print('Writing Organ term triples. . ', end="")
numoterm = 0
for item in oterm:
	if '"' not in item:
		g.write(item + '\n\tdc:identifier\t' + item + ' ;\n\tdc:title\t' + oterm[item]['dc:title'] + ' ;\n\tdc:source\t' + oterm[item]['dc:source'] + ' .\n\n')
		numoterm += 1
print('. . Done \nNumber of organ terms: '+str(numoterm)+'\n')
# Close output file
g.close()

persistent = ntot + numens + naop + nke + nstr + nker + (nchem * 3)
print('Total number of identifiers with identifiers.org: ' + str(persistent))
print('Total number of AOPO predicates: ' + str(naopo))
print("Total number of 'aopo:has_chemical_entity': " + str(naopohaschem))
print("Total number of 'aopo:has_key_event': " + str(naopohaske))
print("Total number of 'aopo:has_key_event_relationship': " + str(naopohasker))
print("Total number of 'aopo:has_molecular_initiating_event': " + str(naopohasmie))
print("Total number of 'aopo:has_adverse_outcome': " + str(naopohasao))
print("Total number of 'aopo:LifeStageContext': " + str(naopolife))
print("Total number of 'aopo:CellTypeContext': " + str(naopocell))
print("Total number of 'aopo:OrganContext': " + str(naopoorgan))
print("Total number of 'aopo:has_upstream_key_event': " + str(naopoupke))
print("Total number of 'aopo:has_downstream_key_event': " + str(naopodownke))

import datetime

x = datetime.datetime.now()
g = open('/home/marvin.martens/Documents/AOPWikiRDF/AOPWikiRDF-Void.ttl', 'w', encoding='utf-8')
g.write('@prefix : <#> .\n@prefix dc: <http://purl.org/dc/elements/1.1/> .\n@prefix void:  <http://rdfs.org/ns/void#> .\n@prefix pav:   <http://purl.org/pav/> .\n@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix dcat:  <http://www.w3.org/ns/dcat#> .\n@prefix foaf:  <http://xmlns.com/foaf/0.1/> .')
g.write('\n:AOPWikiRDF\ta\tvoid:Dataset ;\n\tdc:description\t"AOP-Wiki RDF data from the AOP-Wiki database" ;\n\tpav:createdOn\t"' + str(x) + '" ;\n\tpav:createdWith\t"' + str(filename) + '" ;\n\tpav:createdBy\t<https://zenodo.org/badge/latestdoi/146466058> ;\n\tfoaf:homepage\t<https://aopwiki.org> ;\n\tdcat:downloadURL\t<https://aopwiki.org/downloads/' + str(filename) + '> .')
g.close()
