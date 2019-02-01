print ('Parsing XML file. . ', end ="")
import xml.etree.ElementTree as ET
tree = ET.parse('C:\\Users\\marvin.martens\\ownCloud\\Documents\\Documents\\AOPWiki RDF/aop-wiki-xml-2018-07-01') #double \\ after C: because python3 reads this as a character with one \
root = tree.getroot()
print ('. . Done ')
aopxml='{http://www.aopkb.org/aop-xml}'

#import re for html cleanup. TAG_RE is defining all tags to remove from text files with cleanup
import re
TAG_RE = re.compile(r'<[^>]+>')

#Create a dictionary for all genes that were mapped through HGNC identifiers for KEs
genedict={}
genes=open('C:\\Users\\marvin.martens\\ownCloud\\Documents\\Documents\\AOPWiki RDF/aopgenes.txt','r')
for line in genes:
	a=line[:-1].split('\t')
	if len(a[1])>2:
		genedict[a[0]]='"'+a[1]+'"'


#AOPWIKI IDs to add for AOP, stressors and KEs
print('Creating AOP-Wiki ID dictionaries. . ', end ="")
refs={}
refs['aop']={}
refs['KEs']={}
refs['KERs']={}
refs['stressor']={}
for ref in root.find(aopxml+'vendor-specific').findall(aopxml+'aop-reference'):
	refs['aop'][ref.get('id')]=ref.get('aop-wiki-id')
for ref in root.find(aopxml+'vendor-specific').findall(aopxml+'key-event-reference'):
	refs['KEs'][ref.get('id')]=ref.get('aop-wiki-id')
for ref in root.find(aopxml+'vendor-specific').findall(aopxml+'key-event-relationship-reference'):
	refs['KERs'][ref.get('id')]=ref.get('aop-wiki-id')
for ref in root.find(aopxml+'vendor-specific').findall(aopxml+'stressor-reference'):
	refs['stressor'][ref.get('id')]=ref.get('aop-wiki-id')
print('. . Done ')

#ADVERSE OUTCOME PATHWAYS
print('Parsing and organizing AOP information. . ', end ="")
aopdict={}
for AOP in root.findall(aopxml+'aop'):
	aopdict[AOP.get('id')]={}
#General info about the AOPs
	aopdict[AOP.get('id')]['dc:identifier'] = 'aop:'+refs['aop'][AOP.get('id')]
	aopdict[AOP.get('id')]['rdfs:label'] = '"AOP '+refs['aop'][AOP.get('id')]+'"'
	aopdict[AOP.get('id')]['foaf:page'] = '<http://identifiers.org/aop/'+refs['aop'][AOP.get('id')]+'>'
	aopdict[AOP.get('id')]['dc:title'] = '"'+AOP.find(aopxml+'title').text+'"'
	aopdict[AOP.get('id')]['dcterms:alternative'] = AOP.find(aopxml+'short-name').text
	if not AOP.find(aopxml+'abstract').text==None:
		aopdict[AOP.get('id')]['dcterms:description'] = '"""'+TAG_RE.sub('', AOP.find(aopxml+'abstract').text)+'"""'
	if not AOP.find(aopxml+'status').find(aopxml+'wiki-status')==None:
		aopdict[AOP.get('id')]['wiki-status'] = AOP.find(aopxml+'status').find(aopxml+'wiki-status').text
	if not AOP.find(aopxml+'status').find(aopxml+'oecd-status')==None:
		aopdict[AOP.get('id')]['oecd-status'] = AOP.find(aopxml+'status').find(aopxml+'oecd-status').text
	if not AOP.find(aopxml+'status').find(aopxml+'saaop-status')==None:
		aopdict[AOP.get('id')]['saaop-status'] = AOP.find(aopxml+'status').find(aopxml+'saaop-status').text
	aopdict[AOP.get('id')]['oecd-project'] = AOP.find(aopxml+'oecd-project').text
	aopdict[AOP.get('id')]['dc:source'] = AOP.find(aopxml+'source').text
#timestamps
	aopdict[AOP.get('id')]['dcterms:created'] = AOP.find(aopxml+'creation-timestamp').text
	aopdict[AOP.get('id')]['dcterms:modified'] = AOP.find(aopxml+'last-modification-timestamp').text
#applicability
	for appl in AOP.findall(aopxml+'applicability'):
		for sex in appl.findall(aopxml+'sex'):
			if not 'pato:PATO_0000047' in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['pato:PATO_0000047']=[[sex.find(aopxml+'evidence').text,sex.find(aopxml+'sex').text]]
			else:
				aopdict[AOP.get('id')]['pato:PATO_0000047'].append([sex.find(aopxml+'evidence').text,sex.find(aopxml+'sex').text])
		for life in appl.findall(aopxml+'life-stage'):
			if not 'aopo:LifeStageContext' in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['aopo:LifeStageContext']=[[life.find(aopxml+'evidence').text,life.find(aopxml+'life-stage').text]]
			else:
				aopdict[AOP.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml+'evidence').text,life.find(aopxml+'life-stage').text])
#Key Events
	aopdict[AOP.get('id')]['aopo:has_key_event']={}
	for KE in AOP.find(aopxml+'key-events').findall(aopxml+'key-event'):
		aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('id')]['dc:identifier']='ke:'+refs['KEs'][KE.get('id')]
#Key Event Relationships
	aopdict[AOP.get('id')]['aopo:has_key_event_relationship']={}
	for KER in AOP.find(aopxml+'key-event-relationships').findall(aopxml+'relationship'):
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['dc:identifier']='ker:'+refs['KERs'][KER.get('id')]
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['adjacency']=KER.find(aopxml+'adjacency').text
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['quantitative-understanding-value']=KER.find(aopxml+'quantitative-understanding-value').text
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['aopo:has_evidence']=KER.find(aopxml+'evidence').text
#Molecular Initiating Events
	aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event']={}
	for MIE in AOP.findall(aopxml+'molecular-initiating-event'):
		aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')]['dc:identifier']='ke:'+refs['KEs'][MIE.get('key-event-id')]
		#question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')]['dc:identifier']='ke:'+refs['KEs'][MIE.get('key-event-id')]
#Adverse Outcomes
	aopdict[AOP.get('id')]['aopo:has_adverse_outcome']={}
	for AO in AOP.findall(aopxml+'adverse-outcome'):
		aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')]['dc:identifier']='ke:'+refs['KEs'][AO.get('key-event-id')]
		#question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')]['dc:identifier']='ke:'+refs['KEs'][AO.get('key-event-id')]
#stressors
	aopdict[AOP.get('id')]['ncit:C54571']={}
	if not AOP.find(aopxml+'aop-stressors')==None:
		for stressor in AOP.find(aopxml+'aop-stressors').findall(aopxml+'aop-stressor'):
			aopdict[AOP.get('id')]['ncit:C54571'][stressor.get('stressor-id')]={}
			aopdict[AOP.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['dc:identifier']='stressor:'+refs['stressor'][stressor.get('stressor-id')]
			aopdict[AOP.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['aopo:has_evidence']=stressor.find(aopxml+'evidence').text
print('. . Done ')

#CHEMICALS
print('Parsing and organizing chemical information. . ', end ="")
chedict={}
for che in root.findall(aopxml+'chemical'):
	chedict[che.get('id')]={}
	if not che.find(aopxml+'casrn')==None:
		if not 'NOCAS' in che.find(aopxml+'casrn').text: #all NOCAS ids are out, so no issues as subjects
			chedict[che.get('id')]['dc:identifier']='casrn:'+che.find(aopxml+'casrn').text
			chedict[che.get('id')]['cheminf:CHEMINF_000446']='"'+che.find(aopxml+'casrn').text+'"'
		else: 
			chedict[che.get('id')]['dc:identifier']='"'+che.find(aopxml+'casrn').text+'"'
	if not che.find(aopxml+'jchem-inchi-key')==None:
		chedict[che.get('id')]['cheminf:CHEMINF_000059']='inchi:'+str(che.find(aopxml+'jchem-inchi-key').text)
	if not che.find(aopxml+'preferred-name')==None:
		chedict[che.get('id')]['dc:title']='"'+che.find(aopxml+'preferred-name').text+'"'
	if not che.find(aopxml+'dsstox-id')==None:
		chedict[che.get('id')]['cheminf:CHEMINF_000568']='dss:'+che.find(aopxml+'dsstox-id').text[:-1]
	if not che.find(aopxml+'synonyms')==None:
		chedict[che.get('id')]['dcterms:alternative']=[]
		for synonym in che.find(aopxml+'synonyms').findall(aopxml+'synonym'):
			chedict[che.get('id')]['dcterms:alternative'].append(synonym.text[:-1])
print('. . Done ')

#STRESSORS, later to combine with CHEMICALS when writing file
print('Parsing and organizing stressor information. . ', end ="")
strdict={}
for str in root.findall(aopxml+'stressor'):
	strdict[str.get('id')]={}
#General info about the stressors
	strdict[str.get('id')]['dc:identifier'] = 'stressor:'+refs['stressor'][str.get('id')]
	strdict[str.get('id')]['rdfs:label'] = '"Stressor '+refs['stressor'][str.get('id')]+'"'
	strdict[str.get('id')]['foaf:page'] = '<http://identifiers.org/aop.stressor/'+refs['stressor'][str.get('id')]+'>'
	strdict[str.get('id')]['dc:title'] = '"'+str.find(aopxml+'name').text+'"'
	if not str.find(aopxml+'description').text == None:
		strdict[str.get('id')]['dcterms:description'] = '"""'+TAG_RE.sub('', str.find(aopxml+'description').text)+'"""'
	strdict[str.get('id')]['dcterms:created'] = str.find(aopxml+'creation-timestamp').text
	strdict[str.get('id')]['dcterms:modified'] = str.find(aopxml+'last-modification-timestamp').text
#Chemicals related to stressor
	strdict[str.get('id')]['aopo:has_chemical_entity']=[]
	strdict[str.get('id')]['linktochemical']=[]
	if not str.find(aopxml+'chemicals')==None:
		for chemical in str.find(aopxml+'chemicals').findall(aopxml+'chemical-initiator'):
			strdict[str.get('id')]['aopo:has_chemical_entity'].append('"'+chemical.get('user-term')+'"')
			strdict[str.get('id')]['linktochemical'].append(chemical.get('chemical-id'))#user-term is not important
print('. . Done ')

#TAXONOMY
print('Parsing and organizing taxonomy information. . ', end ="")
taxdict={}
for tax in root.findall(aopxml+'taxonomy'):
	taxdict[tax.get('id')]={}
	taxdict[tax.get('id')]['dc:source']=tax.find(aopxml+'source').text
	taxdict[tax.get('id')]['dc:title']=tax.find(aopxml+'name').text
	if taxdict[tax.get('id')]['dc:source'] =='NCBI':
		taxdict[tax.get('id')]['dc:identifier']='ncbitaxon:'+tax.find(aopxml+'source-id').text
	#The following lines cause issues, as the subjects will be literals
	elif not taxdict[tax.get('id')]['dc:source']==None:
		taxdict[tax.get('id')]['dc:identifier']='"'+tax.find(aopxml+'source-id').text+'"'
	else:
		taxdict[tax.get('id')]['dc:identifier']='"'+tax.find(aopxml+'source-id').text+'"'
print('. . Done ')

#BIOLOGICAL EVENTS
print('Parsing and organizing biological event information. . ', end ="")
bioactdict={}
bioactdict[None]={}
bioactdict[None]['dc:identifier']=None
bioactdict[None]['dc:source']=None
bioactdict[None]['dc:title']=None
for bioact in root.findall(aopxml+'biological-action'):
	bioactdict[bioact.get('id')]={}
	bioactdict[bioact.get('id')]['dc:source']='"'+bioact.find(aopxml+'source').text+'"'
	bioactdict[bioact.get('id')]['dc:title']='"'+bioact.find(aopxml+'name').text+'"'
	bioactdict[bioact.get('id')]['dc:identifier']='"WIKI:'+bioact.find(aopxml+'source-id').text+'"'

bioprodict={}
bioprodict[None]={}
bioprodict[None]['dc:identifier']=None
bioprodict[None]['dc:source']=None
bioprodict[None]['dc:title']=None
for biopro in root.findall(aopxml+'biological-process'):
	bioprodict[biopro.get('id')]={}
	bioprodict[biopro.get('id')]['dc:source']='"'+biopro.find(aopxml+'source').text+'"'
	bioprodict[biopro.get('id')]['dc:title']='"'+biopro.find(aopxml+'name').text+'"'
	if bioprodict[biopro.get('id')]['dc:source'] =='"GO"':
		bioprodict[biopro.get('id')]['dc:identifier']='go:'+biopro.find(aopxml+'source-id').text[3:]#predicate go:trerm possible
	elif bioprodict[biopro.get('id')]['dc:source'] =='"MI"':
		bioprodict[biopro.get('id')]['dc:identifier']='mi:'+biopro.find(aopxml+'source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] =='"MP"':
		bioprodict[biopro.get('id')]['dc:identifier']='mp:'+biopro.find(aopxml+'source-id').text[3:]
	elif bioprodict[biopro.get('id')]['dc:source'] =='"MESH"':
		bioprodict[biopro.get('id')]['dc:identifier']='mesh:'+biopro.find(aopxml+'source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] =='"HP"':
		bioprodict[biopro.get('id')]['dc:identifier']='hp:'+biopro.find(aopxml+'source-id').text[3:]
	elif bioprodict[biopro.get('id')]['dc:source'] =='"PCO"':
		bioprodict[biopro.get('id')]['dc:identifier']='pco:'+biopro.find(aopxml+'source-id').text[4:]
	elif bioprodict[biopro.get('id')]['dc:source'] =='"NBO"':
		bioprodict[biopro.get('id')]['dc:identifier']='nbo:'+biopro.find(aopxml+'source-id').text[4:]
	elif bioprodict[biopro.get('id')]['dc:source'] =='"VT"':
		bioprodict[biopro.get('id')]['dc:identifier']='vt:'+biopro.find(aopxml+'source-id').text[3:]
	else:
		#print('The following ontology was not found for biological process: '+biopro.find(aopxml+'source').text)
		bioprodict[biopro.get('id')]['dc:identifier']=biopro.find(aopxml+'source-id').text

bioobjdict={}
bioobjdict[None]={}
bioobjdict[None]['dc:identifier']=None
bioobjdict[None]['dc:source']=None
bioobjdict[None]['dc:title']=None
for bioobj in root.findall(aopxml+'biological-object'):
	bioobjdict[bioobj.get('id')]={}
	bioobjdict[bioobj.get('id')]['dc:source']='"'+bioobj.find(aopxml+'source').text+'"'
	bioobjdict[bioobj.get('id')]['dc:title']='"'+bioobj.find(aopxml+'name').text+'"'
	if bioobjdict[bioobj.get('id')]['dc:source']=='"PR"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='pr:'+bioobj.find(aopxml+'source-id').text[3:]
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"CL"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='cl:'+bioobj.find(aopxml+'source-id').text[3:]
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"MESH"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='mesh:'+bioobj.find(aopxml+'source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"GO"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='go:'+bioobj.find(aopxml+'source-id').text[3:]#predicate go:trerm possible
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"UBERON"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='uberon:'+bioobj.find(aopxml+'source-id').text[7:]
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"CHEBI"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='chebi:'+bioobj.find(aopxml+'source-id').text[6:]
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"MP"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='mp:'+bioobj.find(aopxml+'source-id').text[3:]
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"FMA"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='fma:'+bioobj.find(aopxml+'source-id').text[4:]
	elif bioobjdict[bioobj.get('id')]['dc:source']=='"PCO"':
		bioobjdict[bioobj.get('id')]['dc:identifier']='pco:'+bioobj.find(aopxml+'source-id').text[4:]
	else:
		#print ('The following ontology was not found for biological object: '+bioobj.find(aopxml+'source').text)
		bioobjdict[bioobj.get('id')]['dc:identifier']=bioobj.find(aopxml+'source-id').text
print('. . Done ')

#KEY EVENTS, later to combine with TAXONOMY when writing file
print('Parsing and organizing Key Event information. . ', end ="")
kedict={}
for ke in root.findall(aopxml+'key-event'):
	kedict[ke.get('id')]={}
#General info about the KEs
	kedict[ke.get('id')]['dc:identifier'] = 'ke:'+refs['KEs'][ke.get('id')]
	kedict[ke.get('id')]['rdfs:label'] = '"KE '+refs['KEs'][ke.get('id')]+'"'
	kedict[ke.get('id')]['foaf:page'] = '<http://identifiers.org/aop.events/'+refs['KEs'][ke.get('id')]+'>'
	kedict[ke.get('id')]['dc:title'] = '"'+ke.find(aopxml+'title').text+'"'
	kedict[ke.get('id')]['dcterms:alternative'] = ke.find(aopxml+'short-name').text
	if not ke.find(aopxml+'description').text==None:
		kedict[ke.get('id')]['dcterms:description'] = '"""'+TAG_RE.sub('', ke.find(aopxml+'description').text)+'"""'
	if not ke.find(aopxml+'measurement-methodology').text==None:
		kedict[ke.get('id')]['mmo:0000000'] = '"""'+TAG_RE.sub('', ke.find(aopxml+'measurement-methodology').text)+'"""'
	if refs['KEs'][ke.get('id')] in genedict:
		kedict[ke.get('id')]['dcterms:contributor'] = genedict[refs['KEs'][ke.get('id')]].split(';')
	kedict[ke.get('id')]['biological-organization-level'] = ke.find(aopxml+'biological-organization-level').text
	kedict[ke.get('id')]['dc:source'] = ke.find(aopxml+'source').text
#Applicability
	for appl in ke.findall(aopxml+'applicability'):
		for sex in appl.findall(aopxml+'sex'):
			if not 'pato:PATO_0000047' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['pato:PATO_0000047']=[[sex.find(aopxml+'evidence').text,sex.find(aopxml+'sex').text]]
			else:
				kedict[ke.get('id')]['pato:PATO_0000047'].append([sex.find(aopxml+'evidence').text,sex.find(aopxml+'sex').text])
		for life in appl.findall(aopxml+'life-stage'):
			if not 'aopo:LifeStageContext' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['aopo:LifeStageContext']=[[life.find(aopxml+'evidence').text,life.find(aopxml+'life-stage').text]]
			else:
				kedict[ke.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml+'evidence').text,life.find(aopxml+'life-stage').text])
		for tax in appl.findall(aopxml+'taxonomy'):
			if not 'ncbitaxon:131567' in kedict[ke.get('id')]:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kedict[ke.get('id')]['ncbitaxon:131567']=[[tax.get('taxonomy-id'),tax.find(aopxml+'evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']]]
			else:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kedict[ke.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'),tax.find(aopxml+'evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']])
#Biological Events
	if not ke.find(aopxml+'biological-events') ==None:
		for event in ke.find(aopxml+'biological-events').findall(aopxml+'biological-event'):
			if not 'biological-event'in kedict[ke.get('id')]:
				kedict[ke.get('id')]['biological-event']={}
				kedict[ke.get('id')]['biological-event']['process']=[]
				kedict[ke.get('id')]['biological-event']['object']=[]
				kedict[ke.get('id')]['biological-event']['action']=[]
			kedict[ke.get('id')]['biological-event']['process'].append(bioprodict[event.get('process-id')]['dc:identifier'])

			kedict[ke.get('id')]['biological-event']['object'].append(bioobjdict[event.get('object-id')]['dc:identifier'])
			kedict[ke.get('id')]['biological-event']['action'].append(bioactdict[event.get('action-id')]['dc:identifier'])
#cell term / Organ term
	if not ke.find(aopxml+'cell-term') ==None:
		kedict[ke.get('id')]['aopo:CellTypeContext']={}
		kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source']='"'+ke.find(aopxml+'cell-term').find(aopxml+'source').text+'"'
		kedict[ke.get('id')]['aopo:CellTypeContext']['dc:title']='"'+ke.find(aopxml+'cell-term').find(aopxml+'name').text+'"'
		if kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source']=='"CL"':
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier']=['cl:'+ke.find(aopxml+'cell-term').find(aopxml+'source-id').text[3:],ke.find(aopxml+'cell-term').find(aopxml+'source-id').text]
		elif kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source']=='"UBERON"':
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier']=['uberon:'+ke.find(aopxml+'cell-term').find(aopxml+'source-id').text[7:],ke.find(aopxml+'cell-term').find(aopxml+'source-id').text]
		else:
			#print ('The following ontology was not found for cell term: '+kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'])
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier']=['"'+ke.find(aopxml+'cell-term').find(aopxml+'source-id').text+'"','placeholder']
	if not ke.find(aopxml+'organ-term') ==None:
		kedict[ke.get('id')]['aopo:OrganContext']={}
		kedict[ke.get('id')]['aopo:OrganContext']['dc:source']='"'+ke.find(aopxml+'organ-term').find(aopxml+'source').text+'"'
		kedict[ke.get('id')]['aopo:OrganContext']['dc:title']='"'+ke.find(aopxml+'organ-term').find(aopxml+'name').text+'"'
		if kedict[ke.get('id')]['aopo:OrganContext']['dc:source']=='"UBERON"':
			kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier']=['uberon:'+ke.find(aopxml+'organ-term').find(aopxml+'source-id').text[7:],ke.find(aopxml+'organ-term').find(aopxml+'source-id').text]
		else:
			#print ('The following ontology was not found for organ term: '+kedict[ke.get('id')]['aopo:OrganContext']['dc:source'])
			kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier']=['"'+ke.find(aopxml+'organ-term').find(aopxml+'source-id').text+'"','placeholder']
#Stressor related to KE
	if not ke.find(aopxml+'key-event-stressors')==None:
		kedict[ke.get('id')]['ncit:C54571']={}
		for stressor in ke.find(aopxml+'key-event-stressors').findall(aopxml+'key-event-stressor'):
			kedict[ke.get('id')]['ncit:C54571'][stressor.get('stressor-id')]={}
			kedict[ke.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['dc:identifier']=strdict[stressor.get('stressor-id')]['dc:identifier']
			kedict[ke.get('id')]['ncit:C54571'][stressor.get('stressor-id')]['aopo:has_evidence']=stressor.find(aopxml+'evidence').text
print('. . Done ')

#KEY EVENT RELATIONSHIPS
print('Parsing and organizing Key Event Relationship information. . ', end ="")
kerdict={}
for ker in root.findall(aopxml+'key-event-relationship'):
	kerdict[ker.get('id')]={}
#General info about the KERs
	kerdict[ker.get('id')]['dc:identifier'] = 'ker:'+refs['KERs'][ker.get('id')]
	kerdict[ker.get('id')]['rdfs:label'] = '"KER '+refs['KERs'][ker.get('id')]+'"'
	kerdict[ker.get('id')]['foaf:page'] = '<http://identifiers.org/aop.relationships/'+refs['KERs'][ker.get('id')]+'>'
	kerdict[ker.get('id')]['dc:source'] = ker.find(aopxml+'source').text
	kerdict[ker.get('id')]['dcterms:created'] = ker.find(aopxml+'creation-timestamp').text
	kerdict[ker.get('id')]['dcterms:modified'] = ker.find(aopxml+'last-modification-timestamp').text
	if not ker.find(aopxml+'description').text==None:
		kerdict[ker.get('id')]['dcterms:description'] = '"""'+TAG_RE.sub('', ker.find(aopxml+'description').text)+'"""'
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']={}
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']['id']=ker.find(aopxml+'title').find(aopxml+'upstream-id').text
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']['dc:identifier']='ke:'+refs['KEs'][ker.find(aopxml+'title').find(aopxml+'upstream-id').text]
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']={}
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']['id']=ker.find(aopxml+'title').find(aopxml+'downstream-id').text
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']['dc:identifier']='ke:'+refs['KEs'][ker.find(aopxml+'title').find(aopxml+'downstream-id').text]
#taxonomic applicability
	for appl in ker.findall(aopxml+'taxonomic-applicability'):
		for sex in appl.findall(aopxml+'sex'):
			if not 'pato:PATO_0000047' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['pato:PATO_0000047']=[[sex.find(aopxml+'evidence').text,sex.find(aopxml+'sex').text]]
			else:
				kerdict[ker.get('id')]['pato:PATO_0000047'].append([sex.find(aopxml+'evidence').text,sex.find(aopxml+'sex').text])
		for life in appl.findall(aopxml+'life-stage'):
			if not 'aopo:LifeStageContext' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['aopo:LifeStageContext']=[[life.find(aopxml+'evidence').text,life.find(aopxml+'life-stage').text]]
			else:
				kerdict[ker.get('id')]['aopo:LifeStageContext'].append([life.find(aopxml+'evidence').text,life.find(aopxml+'life-stage').text])
		for tax in appl.findall(aopxml+'taxonomy'):
			if not 'ncbitaxon:131567' in kerdict[ker.get('id')]:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kerdict[ker.get('id')]['ncbitaxon:131567']=[[tax.get('taxonomy-id'),tax.find(aopxml+'evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']]]
			else:
				if 'dc:identifier' in taxdict[tax.get('taxonomy-id')]:
					kerdict[ker.get('id')]['ncbitaxon:131567'].append([tax.get('taxonomy-id'),tax.find(aopxml+'evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']])
print('. . Done \n')


#Creating output file
print('Creating output TTL file. . ', end ="")
g = open('C:\\Users\\marvin.martens\\ownCloud\\Documents\\Documents\\AOPWiki RDF/TestTurtle.ttl', 'w', encoding='utf-8')
print('. . Done ')
#Writing prefixes
print('Writing rdf prefixes. . ', end ="")
g.write('@prefix dc: <http://purl.org/dc/elements/1.1/> .\n@prefix dcterms: <http://purl.org/dc/terms/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n@prefix aop: <http://identifiers.org/aop/> .\n@prefix ke: <http://identifiers.org/aop.events/> .\n@prefix ker: <http://identifiers.org/aop.relationships/> .\n@prefix stressor: <http://identifiers.org/aop.stressor/> .\n@prefix aopo: <http://aopkb.org/aop_ontology#> .\n@prefix casrn: <http://identifiers.org/cas/> .\n@prefix inchi: <http://identifiers.org/inchikey/> .\n@prefix pato: <http://purl.obolibrary.org/obo/> .\n@prefix ncbitaxon: <http://purl.bioontology.org/ontology/NCBITAXON/> .\n@prefix cl: <http://purl.obolibrary.org/obo/CL_> .\n@prefix uberon: <http://purl.obolibrary.org/obo/UBERON_> .\n@prefix go: <http://purl.obolibrary.org/obo/GO_> .\n@prefix mi: <http://purl.obolibrary.org/obo/MI_> .\n@prefix mp: <http://purl.obolibrary.org/obo/MP_> .\n@prefix mesh: <http://purl.bioontology.org/ontology/MESH/> .\n@prefix hp: <http://purl.obolibrary.org/obo/HP_> .\n@prefix pco: <http://purl.obolibrary.org/obo/PCO_> .\n@prefix nbo: <http://purl.obolibrary.org/obo/NBO_> .\n@prefix vt: <http://purl.obolibrary.org/obo/VT_> .\n@prefix pr: <http://purl.obolibrary.org/obo/PR_> .\n@prefix chebi: <http://purl.obolibrary.org/obo/CHEBI_> .\n@prefix fma: <http://purl.org/sig/ont/fma/fma> .\n@prefix cheminf: <http://semanticscience.org/resource/> .\n@prefix ncit: <http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#> .\n@prefix dss: <https://comptox.epa.gov/dashboard/> .\n@prefix mmo: <http://purl.obolibrary.org/obo/MMO_> .\n\n')
print('. . Done ')

#Writing AOP triples
print('Writing AOP triples. . ', end ="")
for aop in aopdict:
	g.write(aopdict[aop]['dc:identifier']+'\n\ta\taopo:AdverseOutcomePathway ;\n\tdc:identifier\t'+aopdict[aop]['dc:identifier']+' ;\n\trdfs:label\t'+aopdict[aop]['rdfs:label']+' ;\n\tfoaf:page\t'+aopdict[aop]['foaf:page']+' ;\n\tdc:title\t'+aopdict[aop]['dc:title']+' ;\n\tdcterms:alternative\t"'+aopdict[aop]['dcterms:alternative']+'" ;\n\tdc:source\t"'+aopdict[aop]['dc:source']+'" ;\n\tdcterms:created\t"'+aopdict[aop]['dcterms:created']+'" ;\n\tdcterms:modified\t"'+aopdict[aop]['dcterms:modified']+'"')
	if 'dcterms:description' in aopdict[aop]: 
		g.write(' ;\n\tdcterms:description\t'+aopdict[aop]['dcterms:description'])
	list=[]
	for KE in aopdict[aop]['aopo:has_key_event']:
		list.append(aopdict[aop]['aopo:has_key_event'][KE]['dc:identifier'])
	if not list == []:
		g.write(' ;\n\taopo:has_key_event\t'+ (','.join(list)))
	list=[]
	for KER in aopdict[aop]['aopo:has_key_event_relationship']:
		list.append(aopdict[aop]['aopo:has_key_event_relationship'][KER]['dc:identifier'])
	if not list == []: 
		g.write(' ;\n\taopo:has_key_event_relationship\t'+(','.join(list)))
	list=[]
	for mie in aopdict[aop]['aopo:has_molecular_initiating_event']:
		list.append(aopdict[aop]['aopo:has_molecular_initiating_event'][mie]['dc:identifier'])
	if not list == []: 
		g.write(' ;\n\taopo:has_molecular_initiating_event\t'+(','.join(list)))
	list=[]
	for ao in aopdict[aop]['aopo:has_adverse_outcome']:
		list.append(aopdict[aop]['aopo:has_adverse_outcome'][ao]['dc:identifier'])
	if not list == []: 
		g.write(' ;\n\taopo:has_adverse_outcome\t'+(','.join(list)))
	list=[]
	for stressor in aopdict[aop]['ncit:C54571']:
		list.append(aopdict[aop]['ncit:C54571'][stressor]['dc:identifier'])
	if not list == []: 
		g.write(' ;\n\tncit:C54571\t'+(','.join(list)))
	list=[]
	if 'pato:PATO_0000047' in aopdict[aop]:
		for sex in aopdict[aop]['pato:PATO_0000047']:
			list.append('"'+sex[1]+'"')
		if not list == []: 
			g.write(' ;\n\tpato:PATO_0000047\t'+(','.join(list)))
	list=[]
	if 'aopo:LifeStageContext' in aopdict[aop]:
		for lifestage in aopdict[aop]['aopo:LifeStageContext']:
			list.append('"'+lifestage[1]+'"')
		if not list == []: 
			g.write(' ;\n\taopo:LifeStageContext\t'+(','.join(list)))
	g.write(' .\n\n')
print('. . Done ')

#Creating cell term and organ term dictionary
cterm={}
oterm={}
#Writing KE triples
print('Writing KE triples. . ', end ="")
for ke in kedict:
	g.write(kedict[ke]['dc:identifier']+'\n\ta\taopo:KeyEvent ;\n\tdc:identifier\t'+kedict[ke]['dc:identifier']+' ;\n\trdfs:label\t'+kedict[ke]['rdfs:label']+' ;\n\tfoaf:page\t'+kedict[ke]['foaf:page']+' ;\n\tdc:title\t'+kedict[ke]['dc:title']+' ;\n\tdcterms:alternative\t"'+kedict[ke]['dcterms:alternative']+'" ;\n\tdc:source\t"'+kedict[ke]['dc:source']+'"')
	if 'dcterms:description' in kedict[ke]: 
		g.write(' ;\n\tdcterms:description\t'+kedict[ke]['dcterms:description'])
	if 'mmo:0000000' in kedict[ke]:
		g.write(' ;\n\tmmo:0000000\t'+kedict[ke]['mmo:0000000'])
	if 'dcterms:contributor' in kedict[ke]:
		g.write(' ;\n\tdcterms:contributor\t'+('","'.join(kedict[ke]['dcterms:contributor'])))
	list=[]
	if 'pato:PATO_0000047' in kedict[ke]:
		for sex in kedict[ke]['pato:PATO_0000047']:
			list.append('"'+sex[1]+'"')
		if not list == []: 
			g.write(' ;\n\tpato:PATO_0000047\t'+(','.join(list)))
	list=[]
	if 'aopo:LifeStageContext' in kedict[ke]:
		for lifestage in kedict[ke]['aopo:LifeStageContext']:
			list.append('"'+lifestage[1]+'"')
		if not list == []: 
			g.write(' ;\n\taopo:LifeStageContext\t'+(','.join(list)))
	list=[]
	if 'ncbitaxon:131567' in kedict[ke]:
		for taxonomy in kedict[ke]['ncbitaxon:131567']:
			list.append(taxonomy[2])
		if not list == []: 
			g.write(' ;\n\tncbitaxon:131567\t'+(','.join(list)))
	list=[]
	if 'ncit:C54571' in kedict[ke]:
		for stressor in kedict[ke]['ncit:C54571']:
			list.append(kedict[ke]['ncit:C54571'][stressor]['dc:identifier'])
		if not list == []: 
			g.write(' ;\n\tncit:C54571\t'+(','.join(list)))
	list=[]
	if 'aopo:CellTypeContext' in kedict[ke]:
		g.write(' ;\n\taopo:CellTypeContext\t'+kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0])
		if not kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0] in cterm:
			cterm[kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]]={}
			cterm[kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]]['dc:source']=kedict[ke]['aopo:CellTypeContext']['dc:source']
			cterm[kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]]['dc:title']=kedict[ke]['aopo:CellTypeContext']['dc:title']
	if 'aopo:OrganContext' in kedict[ke]:
		g.write(' ;\n\taopo:OrganContext\t'+kedict[ke]['aopo:OrganContext']['dc:identifier'][0])
		if not kedict[ke]['aopo:OrganContext']['dc:identifier'][0] in oterm:
			oterm[kedict[ke]['aopo:OrganContext']['dc:identifier'][0]]={}
			oterm[kedict[ke]['aopo:OrganContext']['dc:identifier'][0]]['dc:source']=kedict[ke]['aopo:OrganContext']['dc:source']
			oterm[kedict[ke]['aopo:OrganContext']['dc:identifier'][0]]['dc:title']=kedict[ke]['aopo:OrganContext']['dc:title']
	# if 'biological-event' in kedict[ke]:
		# list=[]
		# for pro in kedict[ke]['biological-event']['process']:
			# if not pro == None:
				# list.append(pro)
		# if not list == []:
			# g.write(' ;\n\tBiologicalProcess\t'+(','.join(list)))
		# list=[]
		# for obj in kedict[ke]['biological-event']['object']:
			# if not obj == None:
				# list.append(obj)
		# if not list == []:
			# g.write(' ;\n\tBiologicalObject\t'+(','.join(list)))
		# list=[]
		# for act in kedict[ke]['biological-event']['action']:
			# if not act == None:
				# list.append(act)
		# if not list == []:
			# g.write(' ;\n\tBiologicalAction\t'+(','.join(list)))
	list = []
	for aop in aopdict:
		if ke in aopdict[aop]['aopo:has_key_event']:
			list.append(aopdict[aop]['dc:identifier'])
	if not list==[]:
		g.write(' ;\n\tdcterms:isPartOf\t'+(','.join(list)))
			
	g.write(' .\n\n')
print('. . Done ')

#Writing KER triples
print('Writing KER triples. . ', end ="")
for ker in kerdict:
	g.write(kerdict[ker]['dc:identifier']+'\n\ta\taopo:KeyEventRelationship ;\n\tdc:identifier\t'+kerdict[ker]['dc:identifier']+' ;\n\trdfs:label\t'+kerdict[ker]['rdfs:label']+' ;\n\tfoaf:page\t'+kerdict[ker]['foaf:page']+' ;\n\tdcterms:created\t"'+kerdict[ker]['dcterms:created']+'" ;\n\tdcterms:modified\t"'+kerdict[ker]['dcterms:modified']+'" ;\n\taopo:has_upstream_key_event\t'+kerdict[ker]['aopo:has_upstream_key_event']['dc:identifier']+' ;\n\taopo:has_downstream_key_event\t'+kerdict[ker]['aopo:has_downstream_key_event']['dc:identifier'])
	if 'dcterms:description' in kerdict[ker]: 
		g.write(' ;\n\tdcterms:description\t'+kerdict[ker]['dcterms:description'])
	list=[]
	if 'pato:PATO_0000047' in kerdict[ker]:
		for sex in kerdict[ker]['pato:PATO_0000047']:
			list.append('"'+sex[1]+'"')
		if not list == []: 
			g.write(' ;\n\tpato:PATO_0000047\t'+(','.join(list)))
	list=[]
	if 'aopo:LifeStageContext' in kerdict[ker]:
		for lifestage in kerdict[ker]['aopo:LifeStageContext']:
			list.append('"'+lifestage[1]+'"')
		if not list == []: 
			g.write(' ;\n\taopo:LifeStageContext\t'+(','.join(list)))
	list=[]
	if 'ncbitaxon:131567' in kerdict[ker]:
		for taxonomy in kerdict[ker]['ncbitaxon:131567']:
			list.append(taxonomy[2])
		if not list == []: 
			g.write(' ;\n\tncbitaxon:131567\t'+(','.join(list)))
	list = []
	for aop in aopdict:
		if ker in aopdict[aop]['aopo:has_key_event_relationship']:
			list.append(aopdict[aop]['dc:identifier'])
	if not list==[]:
		g.write(' ;\n\tdcterms:isPartOf\t'+(','.join(list)))
	g.write(' .\n\n')
print('. . Done ')

#Writing Taxonomy triples
print('Writing Taxonomy triples. . ', end ="")
for tax in taxdict:
	if 'dc:identifier' in taxdict[tax]:
		if not '"'in taxdict[tax]['dc:identifier']:
			g.write(taxdict[tax]['dc:identifier']+'\n\ta\tncbitaxon:131567 ;\n\tdc:identifier\t'+taxdict[tax]['dc:identifier']+' ;\n\tdc:title\t"'+taxdict[tax]['dc:title'])
			if not taxdict[tax]['dc:source'] ==None:
				g.write('" ;\n\tdc:source\t"'+taxdict[tax]['dc:source'])
			g.write('" .\n\n')
print('. . Done ')

#Writing Stressor triples
print('Writing Stressor triples. . ', end ="")
for str in strdict:
	g.write(strdict[str]['dc:identifier']+'\n\ta\tncit:C54571 ;\n\tdc:identifier\t'+strdict[str]['dc:identifier']+' ;\n\trdfs:label\t'+strdict[str]['rdfs:label']+' ;\n\tfoaf:page\t'+strdict[str]['foaf:page']+' ;\n\tdc:title\t'+strdict[str]['dc:title']+' ;\n\tdcterms:created\t"'+strdict[str]['dcterms:created']+'" ;\n\tdcterms:modified\t"'+strdict[str]['dcterms:modified']+'"')
	if 'dcterms:description' in strdict[str]: 
		g.write(' ;\n\tdcterms:description\t'+strdict[str]['dcterms:description'])
	list=[]
	for chem in strdict[str]['aopo:has_chemical_entity']:
		list.append(chem)
	if not list ==[]:
		g.write(' ;\n\taopo:has_chemical_entity\t' + ','.join(list))
	list = []
	for aop in aopdict:
		if str in aopdict[aop]['ncit:C54571']:
			list.append(aopdict[aop]['dc:identifier'])
	for ke in kedict:
		if 'ncit:C54571' in kedict[ke]:
			if str in kedict[ke]['ncit:C54571']:
				list.append(kedict[ke]['dc:identifier'])
	if not list==[]:
		g.write(' ;\n\tdcterms:isPartOf\t'+(','.join(list)))
	g.write(' .\n\n')
print('. . Done ')

#Writing Chemical triples
print('Writing Chemical triples. . ', end ="")
for che in chedict:
	if 'dc:identifier' in chedict[che]:
		if not '"'in chedict[che]['dc:identifier']:
			g.write(chedict[che]['dc:identifier']+'\n\tdc:identifier\t'+chedict[che]['dc:identifier'])
			if 'cheminf:CHEMINF_000446' in chedict[che]:
				g.write(' ;\n\ta\tcheminf:CHEMINF_000000 ;\n\tcheminf:CHEMINF_000446\t'+chedict[che]['cheminf:CHEMINF_000446'])
			if not chedict[che]['cheminf:CHEMINF_000059']=='inchi:None':
				g.write(' ;\n\tcheminf:CHEMINF_000059\t'+chedict[che]['cheminf:CHEMINF_000059'])
			if 'dc:title' in chedict[che]:
				g.write(' ;\n\tdc:title\t'+chedict[che]['dc:title'])
			if 'cheminf:CHEMINF_000568' in chedict[che]:
				g.write(' ;\n\tcheminf:CHEMINF_000568\t'+chedict[che]['cheminf:CHEMINF_000568'])
			list=[]
			if 'dcterms:alternative' in chedict[che]:
				for alt in chedict[che]['dcterms:alternative']:
					list.append('"'+alt+'"')
				g.write(' ;\n\tdcterms:alternative\t'+','.join(list))
			list=[]
			for str in strdict:
				if 'aopo:has_chemical_entity' in strdict[str]:
					if che in strdict[str]['linktochemical']:
						list.append(strdict[str]['dc:identifier'])
			if not list==[]:
				g.write(' ;\n\tdcterms:isPartOf\t'+(','.join(list)))
			g.write(' .\n\n')
print('. . Done ')

#Writing Biological Process triples
print('Writing Biological Process triples. . ', end ="")
for pro in bioprodict:
	if not pro == None:
		g.write(bioprodict[pro]['dc:identifier']+'\n\tdc:identifier\t'+bioprodict[pro]['dc:identifier']+' ;\n\tdc:title\t'+bioprodict[pro]['dc:title']+' ;\n\tdc:source\t'+bioprodict[pro]['dc:source']+' . \n\n')
print('. . Done ')

#Writing Biological Object triples
print('Writing Biological Object triples. . ', end ="")
for obj in bioobjdict:
	if not obj == None and not 'TAIR'in bioobjdict[obj]['dc:identifier']:
		g.write(bioobjdict[obj]['dc:identifier']+'\n\tdc:identifier\t'+bioobjdict[obj]['dc:identifier']+' ;\n\tdc:title\t'+bioobjdict[obj]['dc:title']+' ;\n\tdc:source\t'+bioobjdict[obj]['dc:source']+' . \n\n')
print('. . Done ')

#Writing Biological Action triples
print('Writing Biological Action triples. . ', end ="")
for act in bioactdict:
	if not act == None:
		if not '"'in bioactdict[act]['dc:identifier']:
			g.write(bioactdict[act]['dc:identifier']+'\n\tdc:identifier\t'+bioactdict[act]['dc:identifier']+' ;\n\tdc:title\t'+bioactdict[act]['dc:title']+' ;\n\tdc:source\t'+bioactdict[act]['dc:source']+' . \n\n')
print('. . Done ')

#Writing Cell term triples
print('Writing Cell term triples. . ', end ="")
for item in cterm:
	if not '"'in item:
		g.write(item+'\n\tdc:identifier\t'+item+' ;\n\tdc:title\t'+cterm[item]['dc:title']+' ;\n\tdc:source\t'+cterm[item]['dc:source']+' .\n\n')
print('. . Done ')

#Writing Organ term triples
print('Writing Organ term triples. . ', end ="")
for item in oterm:
	if not '"'in item:
		g.write(item+'\n\tdc:identifier\t'+item+' ;\n\tdc:title\t'+oterm[item]['dc:title']+' ;\n\tdc:source\t'+oterm[item]['dc:source']+' .\n\n')
print('. . Done ')
#Close output file
g.close()
