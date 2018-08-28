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
	aopdict[AOP.get('id')]['wiki-id'] = refs['aop'][AOP.get('id')]
	aopdict[AOP.get('id')]['title'] = AOP.find('{http://www.aopkb.org/aop-xml}title').text
	aopdict[AOP.get('id')]['short-name'] = AOP.find('{http://www.aopkb.org/aop-xml}short-name').text
	if not AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}wiki-status')==None:
		aopdict[AOP.get('id')]['wiki-status'] = AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}wiki-status').text
	if not AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}oecd-status')==None:
		aopdict[AOP.get('id')]['oecd-status'] = AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}oecd-status').text
	if not AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}saaop-status')==None:
		aopdict[AOP.get('id')]['saaop-status'] = AOP.find('{http://www.aopkb.org/aop-xml}status').find('{http://www.aopkb.org/aop-xml}saaop-status').text
	aopdict[AOP.get('id')]['oecd-project'] = AOP.find('{http://www.aopkb.org/aop-xml}oecd-project').text
	aopdict[AOP.get('id')]['source'] = AOP.find('{http://www.aopkb.org/aop-xml}source').text
#timestamps
	aopdict[AOP.get('id')]['creation-timestamp'] = AOP.find('{http://www.aopkb.org/aop-xml}creation-timestamp').text
	aopdict[AOP.get('id')]['last-modification-timestamp'] = AOP.find('{http://www.aopkb.org/aop-xml}last-modification-timestamp').text
#applicability
	for appl in AOP.findall('{http://www.aopkb.org/aop-xml}applicability'):
		for sex in appl.findall('{http://www.aopkb.org/aop-xml}sex'):
			if not 'sex' in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['sex']=[[sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text]]
			else:
				aopdict[AOP.get('id')]['sex'].append([sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text])
		for life in appl.findall('{http://www.aopkb.org/aop-xml}life-stage'):
			if not 'life' in aopdict[AOP.get('id')]:
				aopdict[AOP.get('id')]['life']=[[life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text]]
			else:
				aopdict[AOP.get('id')]['life'].append([life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text])
#Key Events
	aopdict[AOP.get('id')]['KEs']={}
	for KE in AOP.find('{http://www.aopkb.org/aop-xml}key-events').findall('{http://www.aopkb.org/aop-xml}key-event'):
		aopdict[AOP.get('id')]['KEs'][KE.get('id')]={}
		aopdict[AOP.get('id')]['KEs'][KE.get('id')]['wiki-id']=refs['KEs'][KE.get('id')]
#Key Event Relationships
	aopdict[AOP.get('id')]['KERs']={}
	for KER in AOP.find('{http://www.aopkb.org/aop-xml}key-event-relationships').findall('{http://www.aopkb.org/aop-xml}relationship'):
		aopdict[AOP.get('id')]['KERs'][KER.get('id')]={}
		aopdict[AOP.get('id')]['KERs'][KER.get('id')]['wiki-id']=refs['KERs'][KER.get('id')]
		aopdict[AOP.get('id')]['KERs'][KER.get('id')]['adjacency']=KER.find('{http://www.aopkb.org/aop-xml}adjacency').text
		aopdict[AOP.get('id')]['KERs'][KER.get('id')]['quantitative-understanding-value']=KER.find('{http://www.aopkb.org/aop-xml}quantitative-understanding-value').text
		aopdict[AOP.get('id')]['KERs'][KER.get('id')]['evidence']=KER.find('{http://www.aopkb.org/aop-xml}evidence').text
#Molecular Initiating Events
	aopdict[AOP.get('id')]['MIE']={}
	for MIE in AOP.findall('{http://www.aopkb.org/aop-xml}molecular-initiating-event'):
		aopdict[AOP.get('id')]['MIE'][MIE.get('key-event-id')]={}
		aopdict[AOP.get('id')]['MIE'][MIE.get('key-event-id')]['wiki-id']=refs['KEs'][MIE.get('key-event-id')]
		#question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['KEs'][MIE.get('key-event-id')]={}
		aopdict[AOP.get('id')]['KEs'][MIE.get('key-event-id')]['wiki-id']=refs['KEs'][MIE.get('key-event-id')]
#Adverse Outcomes
	aopdict[AOP.get('id')]['AO']={}
	for AO in AOP.findall('{http://www.aopkb.org/aop-xml}adverse-outcome'):
		aopdict[AOP.get('id')]['AO'][AO.get('key-event-id')]={}
		aopdict[AOP.get('id')]['AO'][AO.get('key-event-id')]['wiki-id']=refs['KEs'][AO.get('key-event-id')]
		#question: do you want ALL KEs in an AOP (so add MIE and AO also in list of KEs?)? If yes, following lines:
		aopdict[AOP.get('id')]['KEs'][AO.get('key-event-id')]={}
		aopdict[AOP.get('id')]['KEs'][AO.get('key-event-id')]['wiki-id']=refs['KEs'][AO.get('key-event-id')]
#stressors
	aopdict[AOP.get('id')]['stressor']={}
	if not AOP.find('{http://www.aopkb.org/aop-xml}aop-stressors')==None:
		for stressor in AOP.find('{http://www.aopkb.org/aop-xml}aop-stressors').findall('{http://www.aopkb.org/aop-xml}aop-stressor'):
			aopdict[AOP.get('id')]['stressor'][stressor.get('stressor-id')]={}
			aopdict[AOP.get('id')]['stressor'][stressor.get('stressor-id')]['wiki-id']=refs['stressor'][stressor.get('stressor-id')]
			aopdict[AOP.get('id')]['stressor'][stressor.get('stressor-id')]['evidence']=stressor.find('{http://www.aopkb.org/aop-xml}evidence').text


#CHEMICALS
chedict={}
for che in root.findall('{http://www.aopkb.org/aop-xml}chemical'):
	chedict[che.get('id')]={}
	if not che.find('{http://www.aopkb.org/aop-xml}chasrn')==None:#could elaborate here with BridgeDb calls
		chedict[che.get('id')]['casrn']=che.find('{http://www.aopkb.org/aop-xml}chasrn').text
	if not che.find('{http://www.aopkb.org/aop-xml}jchem-inchi-key')==None:
		chedict[che.get('id')]['jchem-inchi-key']=che.find('{http://www.aopkb.org/aop-xml}jchem-inchi-key').text
	if not che.find('{http://www.aopkb.org/aop-xml}indigo-inchi-key')==None:
		chedict[che.get('id')]['indigo-inchi-key']=che.find('{http://www.aopkb.org/aop-xml}indigo-inchi-key').text[:-1]
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
	strdict[str.get('id')]['wiki-id'] = refs['stressor'][str.get('id')]
	strdict[str.get('id')]['name'] = str.find('{http://www.aopkb.org/aop-xml}name').text
	strdict[str.get('id')]['creation-timestamp'] = str.find('{http://www.aopkb.org/aop-xml}creation-timestamp').text
	strdict[str.get('id')]['last-modification-timestamp'] = str.find('{http://www.aopkb.org/aop-xml}last-modification-timestamp').text
#Chemicals related to stressor
	strdict[str.get('id')]['chemicals']=[]
	if not str.find('{http://www.aopkb.org/aop-xml}chemicals')==None:
		for chemical in str.find('{http://www.aopkb.org/aop-xml}chemicals').findall('{http://www.aopkb.org/aop-xml}chemical-initiator'):
			strdict[str.get('id')]['chemicals'].append(chemical.get('chemical-id')) #user-term is not important

#TAXONOMY
taxdict={}
for tax in root.findall('{http://www.aopkb.org/aop-xml}taxonomy'):
	taxdict[tax.get('id')]={}
	taxdict[tax.get('id')]['source-id']=tax.find('{http://www.aopkb.org/aop-xml}source-id').text
	taxdict[tax.get('id')]['source']=tax.find('{http://www.aopkb.org/aop-xml}source').text
	taxdict[tax.get('id')]['name']=tax.find('{http://www.aopkb.org/aop-xml}name').text


#BIOLOGICAL EVENTS
bioactdict={}
bioactdict[None]={}
bioactdict[None]['source-id']=None
bioactdict[None]['source']=None
bioactdict[None]['name']=None
for bioact in root.findall('{http://www.aopkb.org/aop-xml}biological-action'):
	bioactdict[bioact.get('id')]={}
	bioactdict[bioact.get('id')]['source-id']=bioact.find('{http://www.aopkb.org/aop-xml}source-id').text
	bioactdict[bioact.get('id')]['source']=bioact.find('{http://www.aopkb.org/aop-xml}source').text
	bioactdict[bioact.get('id')]['name']=bioact.find('{http://www.aopkb.org/aop-xml}name').text
bioprodict={}
bioprodict[None]={}
bioprodict[None]['source-id']=None
bioprodict[None]['source']=None
bioprodict[None]['name']=None
for biopro in root.findall('{http://www.aopkb.org/aop-xml}biological-process'):
	bioprodict[biopro.get('id')]={}
	bioprodict[biopro.get('id')]['source-id']=biopro.find('{http://www.aopkb.org/aop-xml}source-id').text
	bioprodict[biopro.get('id')]['source']=biopro.find('{http://www.aopkb.org/aop-xml}source').text
	bioprodict[biopro.get('id')]['name']=biopro.find('{http://www.aopkb.org/aop-xml}name').text
bioobjdict={}
bioobjdict[None]={}
bioobjdict[None]['source-id']=None
bioobjdict[None]['source']=None
bioobjdict[None]['name']=None
for bioobj in root.findall('{http://www.aopkb.org/aop-xml}biological-object'):
	bioobjdict[bioobj.get('id')]={}
	bioobjdict[bioobj.get('id')]['source-id']=bioobj.find('{http://www.aopkb.org/aop-xml}source-id').text
	bioobjdict[bioobj.get('id')]['source']=bioobj.find('{http://www.aopkb.org/aop-xml}source').text
	bioobjdict[bioobj.get('id')]['name']=bioobj.find('{http://www.aopkb.org/aop-xml}name').text



#KEY EVENTS, later to combine with TAXONOMY when writing file
kedict={}
for ke in root.findall('{http://www.aopkb.org/aop-xml}key-event'):
	kedict[ke.get('id')]={}
#General info about the KEs
	kedict[ke.get('id')]['wiki-id'] = refs['KEs'][ke.get('id')]
	kedict[ke.get('id')]['title'] = ke.find('{http://www.aopkb.org/aop-xml}title').text
	kedict[ke.get('id')]['short-name'] = ke.find('{http://www.aopkb.org/aop-xml}short-name').text
	kedict[ke.get('id')]['biological-organization-level'] = ke.find('{http://www.aopkb.org/aop-xml}biological-organization-level').text
	kedict[ke.get('id')]['source'] = ke.find('{http://www.aopkb.org/aop-xml}source').text
#Applicability
	for appl in ke.findall('{http://www.aopkb.org/aop-xml}applicability'):
		for sex in appl.findall('{http://www.aopkb.org/aop-xml}sex'):
			if not 'sex' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['sex']=[[sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text]]
			else:
				kedict[ke.get('id')]['sex'].append([sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text])
		for life in appl.findall('{http://www.aopkb.org/aop-xml}life-stage'):
			if not 'life-stage' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['life-stage']=[[life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text]]
			else:
				kedict[ke.get('id')]['life-stage'].append([life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text])
		for tax in appl.findall('{http://www.aopkb.org/aop-xml}taxonomy'):
			if not 'taxonomy' in kedict[ke.get('id')]:
				kedict[ke.get('id')]['taxonomy']=[[tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['source-id'],taxdict[tax.get('taxonomy-id')]['source'],taxdict[tax.get('taxonomy-id')]['name']]]
			else:
				kedict[ke.get('id')]['taxonomy'].append([tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['source-id'],taxdict[tax.get('taxonomy-id')]['source'],taxdict[tax.get('taxonomy-id')]['name']])
#Biological Events
	if not ke.find('{http://www.aopkb.org/aop-xml}biological-events') ==None:
		for event in ke.find('{http://www.aopkb.org/aop-xml}biological-events').findall('{http://www.aopkb.org/aop-xml}biological-event'):
			if not 'biological-event'in kedict[ke.get('id')]:
				kedict[ke.get('id')]['biological-event']=[[event.get('object-id'),bioobjdict[event.get('object-id')],event.get('process-id'),bioprodict[event.get('process-id')],event.get('action-id'),bioactdict[event.get('action-id')]]]
			else:
				kedict[ke.get('id')]['biological-event'].append([event.get('object-id'),bioobjdict[event.get('object-id')],event.get('process-id'),bioprodict[event.get('process-id')],event.get('action-id'),bioactdict[event.get('action-id')]])
#cell term / Organ term
	if not ke.find('{http://www.aopkb.org/aop-xml}cell-term') ==None:
		kedict[ke.get('id')]['cell-term']={}
		kedict[ke.get('id')]['cell-term']['source-id']=ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}source-id').text
		kedict[ke.get('id')]['cell-term']['source']=ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}source').text
		kedict[ke.get('id')]['cell-term']['name']=ke.find('{http://www.aopkb.org/aop-xml}cell-term').find('{http://www.aopkb.org/aop-xml}name').text
	if not ke.find('{http://www.aopkb.org/aop-xml}organ-term') ==None:
		kedict[ke.get('id')]['organ-term']={}
		kedict[ke.get('id')]['organ-term']['source-id']=ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}source-id').text
		kedict[ke.get('id')]['organ-term']['source']=ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}source').text
		kedict[ke.get('id')]['organ-term']['name']=ke.find('{http://www.aopkb.org/aop-xml}organ-term').find('{http://www.aopkb.org/aop-xml}name').text
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
	kerdict[ker.get('id')]['wiki-id'] = refs['KERs'][ker.get('id')]
	kerdict[ker.get('id')]['source'] = ker.find('{http://www.aopkb.org/aop-xml}source').text
	kerdict[ker.get('id')]['creation-timestamp'] = ker.find('{http://www.aopkb.org/aop-xml}creation-timestamp').text
	kerdict[ker.get('id')]['last-modification-timestamp'] = ker.find('{http://www.aopkb.org/aop-xml}last-modification-timestamp').text
	kerdict[ker.get('id')]['upstream-key-event']={}
	kerdict[ker.get('id')]['upstream-key-event']['id']=ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}upstream-id').text
	kerdict[ker.get('id')]['upstream-key-event']['wiki-id']=refs['KEs'][ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}upstream-id').text]
	kerdict[ker.get('id')]['downstream-key-event']={}
	kerdict[ker.get('id')]['downstream-key-event']['id']=ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}downstream-id').text
	kerdict[ker.get('id')]['downstream-key-event']['wiki-id']=refs['KEs'][ker.find('{http://www.aopkb.org/aop-xml}title').find('{http://www.aopkb.org/aop-xml}downstream-id').text]
#taxonomic applicability
	for appl in ker.findall('{http://www.aopkb.org/aop-xml}taxonomic-applicability'):
		for sex in appl.findall('{http://www.aopkb.org/aop-xml}sex'):
			if not 'sex' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['sex']=[[sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text]]
			else:
				kerdict[ker.get('id')]['sex'].append([sex.find('{http://www.aopkb.org/aop-xml}evidence').text,sex.find('{http://www.aopkb.org/aop-xml}sex').text])
		for life in appl.findall('{http://www.aopkb.org/aop-xml}life-stage'):
			if not 'life-stage' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['life-stage']=[[life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text]]
			else:
				kerdict[ker.get('id')]['life-stage'].append([life.find('{http://www.aopkb.org/aop-xml}evidence').text,life.find('{http://www.aopkb.org/aop-xml}life-stage').text])
		for tax in appl.findall('{http://www.aopkb.org/aop-xml}taxonomy'):
			if not 'taxonomy' in kerdict[ker.get('id')]:
				kerdict[ker.get('id')]['taxonomy']=[[tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['source-id'],taxdict[tax.get('taxonomy-id')]['source'],taxdict[tax.get('taxonomy-id')]['name']]]
			else:
				kerdict[ker.get('id')]['taxonomy'].append([tax.get('taxonomy-id'),tax.find('{http://www.aopkb.org/aop-xml}evidence').text,taxdict[tax.get('taxonomy-id')]['source-id'],taxdict[tax.get('taxonomy-id')]['source'],taxdict[tax.get('taxonomy-id')]['name']])















print (kerdict)
#for item in aopdict:
#	if '2018'in aopdict[item]['last-modification-timestamp']:
#		print (aopdict[item])
