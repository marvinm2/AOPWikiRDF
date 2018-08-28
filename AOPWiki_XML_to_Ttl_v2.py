import xml.etree.ElementTree as ET
tree = ET.parse('C:\\Users\marvin.martens\Documents\AOPWiki RDF/aop-wiki-xml-2018-07-01') #double \\ after C: because python3 reads this as a character with one \
root = tree.getroot()


#AOPWIKI IDs to add for AOP, stressors and KEs
refs={}
refs['aop']={}
refs['KEs']={}
refs['KERs']={}
refs['stressor']={}
for ref in root.find('{http://www.aopkb.org/aop-xml}vendor-specific').findall('{http://www.aopkb.org/aop-xml}aop-reference'):
	refs['aop'][ref.get('id')]=ref.get('aop-wiki-id')
for ref in root.find('{http://www.aopkb.org/aop-xml}vendor-specific').findall('{http://www.aopkb.org/aop-xml}key-event-reference'):
	refs['KEs'][ref.get('id')]=ref.get('aop-wiki-id')
for ref in root.find('{http://www.aopkb.org/aop-xml}vendor-specific').findall('{http://www.aopkb.org/aop-xml}key-event-relationship-reference'):
	refs['KERs'][ref.get('id')]=ref.get('aop-wiki-id')
for ref in root.find('{http://www.aopkb.org/aop-xml}vendor-specific').findall('{http://www.aopkb.org/aop-xml}stressor-reference'):
	refs['stressor'][ref.get('id')]=ref.get('aop-wiki-id')

#ADVERSE OUTCOME PATHWAYS
aopdict={}
for AOP in root.findall('{http://www.aopkb.org/aop-xml}aop'):
	aopdict[AOP.get('id')]={}
#General info about the AOPs
	aopdict[AOP.get('id')]['dc:identifier'] = 'http://identifiers.org/aop/'+refs['aop'][AOP.get('id')]
	aopdict[AOP.get('id')]['dc:title'] = AOP.find('{http://www.aopkb.org/aop-xml}title').text
	aopdict[AOP.get('id')]['short-name'] = AOP.find('{http://www.aopkb.org/aop-xml}short-name').text
	if not AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}wiki-status')==None:
		aopdict[AOP.get('id')]['wiki-status'] = AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}wiki-status').text
	if not AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}oecd-status')==None:
		aopdict[AOP.get('id')]['oecd-status'] = AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}oecd-status').text
	if not AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}saaop-status')==None:
		aopdict[AOP.get('id')]['saaop-status'] = AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}saaop-status').text
	aopdict[AOP.get('id')]['oecd-project'] = AOP.find('{http://www.aopkb.org/aop-xml}oecd-project').text
	aopdict[AOP.get('id')]['dc:source'] = AOP.find('{http://www.aopkb.org/aop-xml}source').text
#timestamps
	aopdict[AOP.get('id')]['dcterms:created'] = AOP.find('{http://www.aopkb.org/aop-xml}creation-timestamp').text
	aopdict[AOP.get('id')]['dcterms:modified'] = AOP.find('{http://www.aopkb.org/aop-xml}last-modification-timestamp').text
#applicability
	for appl in AOP.findall('{http://www.aopkb.org/aop-xml}applicability'):
		for sex in appl.findall('{http://www.aopkb.org/aop-xml}sex'):
			if not 'sex' in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['sex']=[[sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text]]
			else:
				aopdict[AOP.get('id')]['sex'].append([sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text])
		for life in appl.findall('{http://www.aopkb.org/aop-xml}life-stage'):
			if not 'aopo:LifeStageContext' in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['aopo:LifeStageContext']=[[life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text]]
			else:
				aopdict[AOP.get('id')]['aopo:LifeStageContext'].append([life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text])
#Key Events
	aopdict[AOP.get('id')]['aopo:has_key_event']={}
	for KE in AOP.find('{http://www.aopkb.org/aop-xml}key-events').findall('{http://www.aopkb.org/aop-xml}key-event'):
		aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event'][KE.get('id')]['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][KE.get('id')]
#Key Event Relationships
	aopdict[AOP.get('id')]['aopo:has_key_event_relationship']={}
	for KER in AOP.find('{http://www.aopkb.org/aop-xml}key-event-relationships').findall('{http://www.aopkb.org/aop-xml}relationship'):
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['dc:identifier']='http://identifiers.org/aop.relationships/'+refs['KERs'][KER.get('id')]
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['adjacency']=KER.find('{http://www.aopkb.org/aop-xml}adjacency').text
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['quantitative-understanding-value']=KER.find('{http://www.aopkb.org/aop-xml}quantitative-understanding-value').text
		aopdict[AOP.get('id')]['aopo:has_key_event_relationship'][KER.get('id')]['evidence']=KER.find('{http://www.aopkb.org/aop-xml}evidence').text
#Molecular Initiating Events
	aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event']={}
	for MIE in AOP.findall('{http://www.aopkb.org/aop-xml}molecular-initiating-event'):
		aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_molecular_initiating_event'][MIE.get('key-event-id')]['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][MIE.get('key-event-id')]
		#question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event'][MIE.get('key-event-id')]['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][MIE.get('key-event-id')]
#Adverse Outcomes
	aopdict[AOP.get('id')]['aopo:has_adverse_outcome']={}
	for AO in AOP.findall('{http://www.aopkb.org/aop-xml}adverse-outcome'):
		aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_adverse_outcome'][AO.get('key-event-id')]['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][AO.get('key-event-id')]
		#question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')]={}
		aopdict[AOP.get('id')]['aopo:has_key_event'][AO.get('key-event-id')]['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][AO.get('key-event-id')]
#stressors
	aopdict[AOP.get('id')]['stressor']={}
	if not AOP.find('{http://www.aopkb.org/aop-xml}aop-stressors')==None:
		for stressor in AOP.find('{http://www.aopkb.org/aop-xml}aop-stressors').findall('{http://www.aopkb.org/aop-xml}aop-stressor'):
			aopdict[AOP.get('id')]['stressor'][stressor.get('stressor-id')]={}
			aopdict[AOP.get('id')]['stressor'][stressor.get('stressor-id')]['dc:identifier']='http://identifiers.org/aop.stressor/'+refs['stressor'][stressor.get('stressor-id')]
			aopdict[AOP.get('id')]['stressor'][stressor.get('stressor-id')]['evidence']=stressor.find('{http://www.aopkb.org/aop-xml}evidence').text


#CHEMICALS
chedict={}
for che in root.findall('{http://www.aopkb.org/aop-xml}chemical'):
	chedict[che.get('id')]={}
	if not che.find('{http://www.aopkb.org/aop-xml}chasrn')==None:#could elaborate here with BridgeDb calls
		chedict[che.get('id')]['casrn']='http://identifiers.org/cas/'+che.find('{http://www.aopkb.org/aop-xml}chasrn').text
	if not che.find('{http://www.aopkb.org/aop-xml}jchem-inchi-key')==None:
		chedict[che.get('id')]['jchem-inchi-key']='http://identifiers.org/inchikey/'+str(che.find('{http://www.aopkb.org/aop-xml}jchem-inchi-key').text)
	if not che.find('{http://www.aopkb.org/aop-xml}indigo-inchi-key')==None:
		chedict[che.get('id')]['indigo-inchi-key']='http://identifiers.org/inchikey/'+che.find('{http://www.aopkb.org/aop-xml}indigo-inchi-key').text[:-1]
	if not che.find('{http://www.aopkb.org/aop-xml}preferred-name')==None:
		chedict[che.get('id')]['preferred-name']=che.find('{http://www.aopkb.org/aop-xml}preferred-name').text[:-1]
	if not che.find('{http://www.aopkb.org/aop-xml}dsstox-id')==None:
		chedict[che.get('id')]['dsstox-id']=che.find('{http://www.aopkb.org/aop-xml}dsstox-id').text[:-1]
	if not che.find('{http://www.aopkb.org/aop-xml}synonyms')==None:
		chedict[che.get('id')]['synonyms']=[]
		for synonym in che.find('{http://www.aopkb.org/aop-xml}synonyms').findall('{http://www.aopkb.org/aop-xml}synonym'):
			chedict[che.get('id')]['synonyms'].append(synonym.text[:-1])


#STRESSORS, later to combine with CHEMICALS when writing file
strdict={}
for str in root.findall('{http://www.aopkb.org/aop-xml}stressor'):
	strdict[str.get('id')]={}
#General info about the stressors
	strdict[str.get('id')]['dc:identifier'] = 'http://identifiers.org/aop.stressor/'+refs['stressor'][str.get('id')]
	strdict[str.get('id')]['dc:title'] = str.find('{http://www.aopkb.org/aop-xml}name').text
	strdict[str.get('id')]['dcterms:created'] = str.find('{http://www.aopkb.org/aop-xml}creation-timestamp').text
	strdict[str.get('id')]['dcterms:modified'] = str.find('{http://www.aopkb.org/aop-xml}last-modification-timestamp').text
#Chemicals related to stressor
	strdict[str.get('id')]['chemicals']=[]
	if not str.find('{http://www.aopkb.org/aop-xml}chemicals')==None:
		for chemical in str.find('{http://www.aopkb.org/aop-xml}chemicals').findall('{http://www.aopkb.org/aop-xml}chemical-initiator'):
			strdict[str.get('id')]['chemicals'].append(chemical.get('chemical-id')) #user-term is not important

#TAXONOMY
taxdict={}
for tax in root.findall('{http://www.aopkb.org/aop-xml}taxonomy'):
	taxdict[tax.get('id')]={}
	#taxdict[tax.get('id')]['source-id']=tax.find('{http://www.aopkb.org/aop-xml}source-id').text
	taxdict[tax.get('id')]['dc:source']=tax.find('{http://www.aopkb.org/aop-xml}source').text
	taxdict[tax.get('id')]['dc:title']=tax.find('{http://www.aopkb.org/aop-xml}name').text
	if taxdict[tax.get('id')]['dc:source'] =='NCBI':
		taxdict[tax.get('id')]['dc:identifier']='http://identifiers.org/taxonomy/'+tax.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif not taxdict[tax.get('id')]['dc:source']==None:
		print ('The following ontology was not found for taxonomy: '+taxdict[tax.get('id')]['dc:source'])
		taxdict[tax.get('id')]['dc:identifier']=tax.find('{http://www.aopkb.org/aop-xml}source-id').text
	else:
		taxdict[tax.get('id')]['dc:identifier']=tax.find('{http://www.aopkb.org/aop-xml}source-id').text


#BIOLOGICAL EVENTS
bioactdict={}
bioactdict[None]={}
bioactdict[None]['dc:identifier']=None
bioactdict[None]['dc:source']=None
bioactdict[None]['dc:title']=None
for bioact in root.findall('{http://www.aopkb.org/aop-xml}biological-action'):
	bioactdict[bioact.get('id')]={}
	bioactdict[bioact.get('id')]['dc:source']=bioact.find('{http://www.aopkb.org/aop-xml}source').text
	bioactdict[bioact.get('id')]['dc:title']=bioact.find('{http://www.aopkb.org/aop-xml}name').text
	print ('The following ontology was not found for biological action: '+bioactdict[bioact.get('id')]['dc:source'])
	bioactdict[bioact.get('id')]['dc:identifier']=bioact.find('{http://www.aopkb.org/aop-xml}source-id').text

bioprodict={}
bioprodict[None]={}
bioprodict[None]['dc:identifier']=None
bioprodict[None]['dc:source']=None
bioprodict[None]['dc:title']=None
for biopro in root.findall('{http://www.aopkb.org/aop-xml}biological-process'):
	bioprodict[biopro.get('id')]={}
	bioprodict[biopro.get('id')]['dc:source']=biopro.find('{http://www.aopkb.org/aop-xml}source').text
	bioprodict[biopro.get('id')]['dc:title']=biopro.find('{http://www.aopkb.org/aop-xml}name').text
	if bioprodict[biopro.get('id')]['dc:source'] =='GO':
		bioprodict[biopro.get('id')]['dc:identifier']='http://identifiers.org/go/'+biopro.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] =='MI':
		bioprodict[biopro.get('id')]['dc:identifier']='http://identifiers.org/psimi/'+biopro.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] =='MP':
		bioprodict[biopro.get('id')]['dc:identifier']='http://identifiers.org/mp/'+biopro.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] =='MESH':
		bioprodict[biopro.get('id')]['dc:identifier']='http://identifiers.org/mesh/'+biopro.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioprodict[biopro.get('id')]['dc:source'] =='HP':
		bioprodict[biopro.get('id')]['dc:identifier']='http://identifiers.org/hp/'+biopro.find('{http://www.aopkb.org/aop-xml}source-id').text
	else:
		print('The following ontology was not found for biological process: '+biopro.find('{http://www.aopkb.org/aop-xml}source').text)
		bioprodict[biopro.get('id')]['dc:identifier']=biopro.find('{http://www.aopkb.org/aop-xml}source-id').text

bioobjdict={}
bioobjdict[None]={}
bioobjdict[None]['dc:identifier']=None
bioobjdict[None]['dc:source']=None
bioobjdict[None]['dc:title']=None
for bioobj in root.findall('{http://www.aopkb.org/aop-xml}biological-object'):
	bioobjdict[bioobj.get('id')]={}
	bioobjdict[bioobj.get('id')]['dc:source']=bioobj.find('{http://www.aopkb.org/aop-xml}source').text
	bioobjdict[bioobj.get('id')]['dc:title']=bioobj.find('{http://www.aopkb.org/aop-xml}name').text
	if bioobjdict[bioobj.get('id')]['dc:source']=='PR':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/pr/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='CL':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/cl/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='MESH':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/mesh/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='GO':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/go/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='UBERON':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/uberon/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='CHEBI':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/chebi/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	elif bioobjdict[bioobj.get('id')]['dc:source']=='MP':
		bioobjdict[bioobj.get('id')]['dc:identifier']='http://identifiers.org/mp/'+bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	else:
		print ('The following ontology was not found for biological object: '+bioobj.find('{http://www.aopkb.org/aop-xml}source').text)
		bioobjdict[bioobj.get('id')]['dc:identifier']=bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text


#KEY EVENTS, later to combine with TAXONOMY when writing file
kedict={}
for ke in root.findall('{http://www.aopkb.org/aop-xml}key-event'):
	kedict[ke.get('id')]={}
#General info about the KEs
	kedict[ke.get('id')]['dc:identifier'] = 'http://identifiers.org/aop.events/'+refs['KEs'][ke.get('id')]
	kedict[ke.get('id')]['dc:title'] = ke.find('{http://www.aopkb.org/aop-xml}title').text
	kedict[ke.get('id')]['short-name'] = ke.find('{http://www.aopkb.org/aop-xml}short-name').text
	kedict[ke.get('id')]['biological-organization-level'] = ke.find('{http://www.aopkb.org/aop-xml}biological-organization-level').text
	kedict[ke.get('id')]['dc:source'] = ke.find('{http://www.aopkb.org/aop-xml}source').text
#Applicability
	for appl in ke.findall('{http://www.aopkb.org/aop-xml}applicability'):
		for sex in appl.findall('{http://www.aopkb.org/aop-xml}sex'):
			if not 'sex' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['sex']=[[sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text]]
			else:
				kedict[ke.get('id')]['sex'].append([sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text])
		for life in appl.findall('{http://www.aopkb.org/aop-xml}life-stage'):
			if not 'aopo:LifeStageContext' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['aopo:LifeStageContext']=[[life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text]]
			else:
				kedict[ke.get('id')]['aopo:LifeStageContext'].append([life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text])
		for tax in appl.findall('{http://www.aopkb.org/aop-xml}taxonomy'):
			if not 'taxonomy' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['taxonomy']=[[tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']]]
			else:
				kedict[ke.get('id')]['taxonomy'].append([tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']])
#Biological Events
	if not ke.find('{http://www.aopkb.org/aop-xml}biological-events') ==None:
		for event in ke.find('{http://www.aopkb.org/aop-xml}biological-events').findall('{http://www.aopkb.org/aop-xml}biological-event'):
			if not 'biological-event'in kedict[ke.get('id')]:
				kedict[ke.get('id')]['biological-event']=[[event.get('object-id'),bioobjdict[event.get('object-id')],event.get('process-id'),bioprodict[event.get('process-id')],event.get('action-id'),bioactdict[event.get('action-id')]]]
			else:
				kedict[ke.get('id')]['biological-event'].append([event.get('object-id'),bioobjdict[event.get('object-id')],event.get('process-id'),bioprodict[event.get('process-id')],event.get('action-id'),bioactdict[event.get('action-id')]])
#cell term / Organ term
	if not ke.find('{http://www.aopkb.org/aop-xml}cell-term') ==None:
		kedict[ke.get('id')]['aopo:CellTypeContext']={}
		kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source']=ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}source').text
		kedict[ke.get('id')]['aopo:CellTypeContext']['dc:title']=ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}name').text
		if kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source']=='CL':
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier']='http://identifiers.org/cl/'+ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}source-id').text
		elif kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source']=='UBERON':
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier']='http://identifiers.org/uberon/'+ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}source-id').text
		else:
			print ('The following ontology was not found for cell term: '+kedict[ke.get('id')]['aopo:CellTypeContext']['dc:source'])
			kedict[ke.get('id')]['aopo:CellTypeContext']['dc:identifier']=ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}source-id').text
	if not ke.find('{http://www.aopkb.org/aop-xml}organ-term') ==None:
		kedict[ke.get('id')]['aopo:OrganContext']={}
		kedict[ke.get('id')]['aopo:OrganContext']['dc:source']=ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}source').text
		kedict[ke.get('id')]['aopo:OrganContext']['dc:title']=ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}name').text
		if kedict[ke.get('id')]['aopo:OrganContext']['dc:source']=='UBERON':
			kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier']='http://identifiers.org/uberon/'+ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}source-id').text
		else:
			print ('The following ontology was not found for organ term: '+kedict[ke.get('id')]['aopo:OrganContext']['dc:source'])
			kedict[ke.get('id')]['aopo:OrganContext']['dc:identifier']=ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}source-id').text
#Stressor related to KE
	if not ke.find('{http://www.aopkb.org/aop-xml}key-event-stressors')==None:
		kedict[ke.get('id')]['key-event-stressors']={}
		for stressor in ke.find('{http://www.aopkb.org/aop-xml}key-event-stressors').findall('{http://www.aopkb.org/aop-xml}key-event-stressor'):
			kedict[ke.get('id')]['key-event-stressors'][stressor.get('id')]={}
			kedict[ke.get('id')]['key-event-stressors'][stressor.get('id')]['evidence']=stressor.find('{http://www.aopkb.org/aop-xml}evidence').text



#KEY EVENT RELATIONSHIPS
kerdict={}
for ker in root.findall('{http://www.aopkb.org/aop-xml}key-event-relationship'):
	kerdict[ker.get('id')]={}
#General info about the KERs
	kerdict[ker.get('id')]['dc:identifier'] = 'http://identifiers.org/aop.relationships/'+refs['KERs'][ker.get('id')]
	kerdict[ker.get('id')]['dc:source'] = ker.find('{http://www.aopkb.org/aop-xml}source').text
	kerdict[ker.get('id')]['dcterms:created'] = ker.find('{http://www.aopkb.org/aop-xml}creation-timestamp').text
	kerdict[ker.get('id')]['dcterms:modified'] = ker.find('{http://www.aopkb.org/aop-xml}last-modification-timestamp').text
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']={}
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']['id']=ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}upstream-id').text
	kerdict[ker.get('id')]['aopo:has_upstream_key_event']['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}upstream-id').text]
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']={}
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']['id']=ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}downstream-id').text
	kerdict[ker.get('id')]['aopo:has_downstream_key_event']['dc:identifier']='http://identifiers.org/aop.events/'+refs['KEs'][ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}downstream-id').text]
#taxonomic applicability
	for appl in ker.findall('{http://www.aopkb.org/aop-xml}taxonomic-applicability'):
		for sex in appl.findall('{http://www.aopkb.org/aop-xml}sex'):
			if not 'sex' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['sex']=[[sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text]]
			else:
				kerdict[ker.get('id')]['sex'].append([sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text])
		for life in appl.findall('{http://www.aopkb.org/aop-xml}life-stage'):
			if not 'aopo:LifeStageContext' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['aopo:LifeStageContext']=[[life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text]]
			else:
				kerdict[ker.get('id')]['aopo:LifeStageContext'].append([life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text])
		for tax in appl.findall('{http://www.aopkb.org/aop-xml}taxonomy'):
			if not 'taxonomy' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['taxonomy']=[[tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']]]
			else:
				kerdict[ker.get('id')]['taxonomy'].append([tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['dc:identifier'],taxdict[tax.get('taxonomy-id')]['dc:source'],taxdict[tax.get('taxonomy-id')]['dc:title']])















#print (bioprodict)
#for item in aopdict:
#	if '2018'in aopdict[item]['last-modification-timestamp']:
#		print (aopdict[item])