"""RDF/Turtle writer for AOP-Wiki data.

Extracted from pipeline.py — the ONLY module that builds RDF triples.
Mapping modules return plain data; this module converts to Turtle syntax.

The writer builds Turtle strings by concatenation (not rdflib Graph objects)
to preserve byte-identical output with the monolith.
"""

import datetime
import logging
import re

import pandas as pd

from aopwiki_rdf.rdf.namespaces import get_main_prefixes, GENES_PREFIXES, VOID_PREFIXES
from aopwiki_rdf.utils import clean_html_tags

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper functions (extracted from pipeline.py lines 1247-1278)
# ---------------------------------------------------------------------------


def _write_multivalue_triple(fh, predicate, values, quote=False):
    """Write multiple values for a single predicate."""
    if not values:
        return
    formatted = [f'"{v}"' if quote else v for v in values]
    fh.write(f' ;\n\t{predicate}\t' + ', '.join(formatted))


def _write_triple(fh, subject, predicate, obj, end_char=';'):
    """Write a single RDF triple."""
    fh.write(f'{subject}\t{predicate}\t{obj} {end_char}\n')


def _write_subject_start(fh, subject, rdf_type=None):
    """Start writing triples for a subject."""
    if rdf_type:
        fh.write(f'\n{subject}\ta\t{rdf_type}')
    else:
        fh.write(f'\n{subject}')


def _safe_write_description(fh, predicate, text):
    """Safely write description text, cleaning HTML tags."""
    if text and text.strip():
        cleaned_text = clean_html_tags(text.strip())
        if cleaned_text:
            fh.write(f' ;\n\t{predicate}\t"""' + cleaned_text + '"""')


def _safe_write_simple(fh, predicate, value, quote=True):
    """Safely write a simple property if value exists."""
    if value is not None and str(value).strip():
        formatted_value = f'"{value}"' if quote else str(value)
        fh.write(f' ;\n\t{predicate}\t{formatted_value}')


# ---------------------------------------------------------------------------
# Main RDF file writer (pipeline.py lines 1280-1812)
# ---------------------------------------------------------------------------


def write_aop_rdf(filepath, entities, prefix_csv_path, config=None):
    """Write AOPWikiRDF.ttl from entity dictionaries.

    Parameters
    ----------
    filepath : str
        Output file path (full path including filename).
    entities : dict
        Dict with keys: 'aopdict', 'kedict', 'kerdict', 'strdict',
        'chedict', 'taxdict', 'celldict', 'organdict', 'bioobjdict',
        'bioprodict', 'bioactdict', 'prodict',
        'hgnclist', 'ncbigenelist', 'uniprotlist',
        plus chemical identifier lists: 'listofcas', 'listofchebi', etc.
        Optional 'symbol_lookup' for gene rdfs:label generation.
    prefix_csv_path : str
        Path to prefixes.csv.
    config : PipelineConfig, optional
        Pipeline configuration. When None, only owl:sameAs is emitted.
        When config.emit_legacy_predicates is True, both skos:exactMatch
        and owl:sameAs are emitted.
    """
    # Unpack entities
    aopdict = entities['aopdict']
    kedict = entities['kedict']
    kerdict = entities['kerdict']
    strdict = entities['strdict']
    chedict = entities['chedict']
    taxdict = entities['taxdict']
    bioobjdict = entities['bioobjdict']
    bioprodict = entities['bioprodict']
    bioactdict = entities['bioactdict']
    prodict = entities['prodict']
    hgnclist = entities.get('hgnclist', [])
    ncbigenelist = entities.get('ncbigenelist', [])
    uniprotlist = entities.get('uniprotlist', [])

    # Chemical identifier lists
    listofcas = entities.get('listofcas', [])
    listofinchikey = entities.get('listofinchikey', [])
    listofcomptox = entities.get('listofcomptox', [])
    listofchebi = entities.get('listofchebi', [])
    listofchemspider = entities.get('listofchemspider', [])
    listofwikidata = entities.get('listofwikidata', [])
    listofchembl = entities.get('listofchembl', [])
    listofpubchem = entities.get('listofpubchem', [])
    listofdrugbank = entities.get('listofdrugbank', [])
    listofkegg = entities.get('listofkegg', [])
    listoflipidmaps = entities.get('listoflipidmaps', [])
    listofhmdb = entities.get('listofhmdb', [])

    logger.info(f"Writing main RDF file: {filepath}")

    with open(filepath, 'w', encoding='utf-8') as g:
        # --- Prefixes ---
        rdf_prefixes = get_main_prefixes(prefix_csv_path)
        g.write(rdf_prefixes + "\n")

        # SHACL declarations
        prefixes = pd.read_csv(prefix_csv_path)
        g.write('\n')
        for _, row in prefixes.iterrows():
            prefix = row['prefix']
            uri = row['uri']
            g.write(f'[] sh:declare [ sh:prefix "{prefix}" ; sh:namespace "{uri}"^^xsd:anyURI ] .\n')

        # --- AOP triples ---
        for aop in aopdict:
            g.write(
                aopdict[aop]['dc:identifier'] +
                '\n\ta\taopo:AdverseOutcomePathway ;' +
                '\n\tdc:identifier\t' + aopdict[aop]['dc:identifier'] +
                ' ;\n\trdfs:label\t' + aopdict[aop]['rdfs:label'] +
                ' ;\n\trdfs:seeAlso\t' + aopdict[aop]['foaf:page'] +
                ' ;\n\tfoaf:page\t' + aopdict[aop]['foaf:page'] +
                ' ;\n\tdc:title\t' + aopdict[aop]['dc:title'] +
                ' ;\n\tdcterms:alternative\t"' + aopdict[aop]['dcterms:alternative'] + '"' +
                ' ;\n\tdc:source\t"' + aopdict[aop]['dc:source'] + '"' +
                ' ;\n\tdcterms:created\t"' + aopdict[aop]['dcterms:created'] + '"' +
                ' ;\n\tdcterms:modified\t"' + aopdict[aop]['dcterms:modified'] + '"'
            )

            if 'dc:description' in aopdict[aop] and aopdict[aop]['dc:description']:
                _write_multivalue_triple(g, 'dc:description', aopdict[aop]['dc:description'], quote=False)

            for predicate in [
                    'nci:C25217', 'nci:C48192', 'aopo:AopContext', 'aopo:has_evidence',
                    'edam:operation_3799', 'nci:C25725', 'dc:creator',
                    'dcterms:accessRights', 'dcterms:abstract'
                ]:
                    if predicate in aopdict[aop]:
                        g.write(f' ;\n\t{predicate}\t' + aopdict[aop][predicate])

            if 'oecd-status' in aopdict[aop]:
                g.write(' ;\n\tnci:C25688\t' + aopdict[aop]['oecd-status'])
            if 'saaop-status' in aopdict[aop]:
                g.write(' ;\n\tnci:C25688\t' + aopdict[aop]['saaop-status'])

            _write_multivalue_triple(g, 'aopo:has_key_event', [aopdict[aop]['aopo:has_key_event'][ke]['dc:identifier'] for ke in aopdict[aop].get('aopo:has_key_event', {})])
            _write_multivalue_triple(g, 'aopo:has_key_event_relationship', [aopdict[aop]['aopo:has_key_event_relationship'][ker]['dc:identifier'] for ker in aopdict[aop].get('aopo:has_key_event_relationship', {})])
            _write_multivalue_triple(g, 'aopo:has_molecular_initiating_event', [aopdict[aop]['aopo:has_molecular_initiating_event'][mie]['dc:identifier'] for mie in aopdict[aop].get('aopo:has_molecular_initiating_event', {})])
            _write_multivalue_triple(g, 'aopo:has_adverse_outcome', [aopdict[aop]['aopo:has_adverse_outcome'][ao]['dc:identifier'] for ao in aopdict[aop].get('aopo:has_adverse_outcome', {})])
            _write_multivalue_triple(g, 'nci:C54571', [aopdict[aop]['nci:C54571'][s]['dc:identifier'] for s in aopdict[aop].get('nci:C54571', {})])

            if 'pato:0000047' in aopdict[aop]:
                _write_multivalue_triple(g, 'pato:0000047', [sex[1] for sex in aopdict[aop]['pato:0000047']], quote=True)
            if 'aopo:LifeStageContext' in aopdict[aop]:
                _write_multivalue_triple(g, 'aopo:LifeStageContext', [stage[1] for stage in aopdict[aop]['aopo:LifeStageContext']], quote=True)
            if 'ncbitaxon:131567' in aopdict[aop]:
                _write_multivalue_triple(g, 'ncbitaxon:131567', [tax[2] for tax in aopdict[aop]['ncbitaxon:131567']])

            g.write(' .\n\n')

        logger.info("Section completed")

        # --- KE triples ---
        cterm = {}
        oterm = {}
        bioevent_triples = []

        for ke in kedict:
            g.write(
                kedict[ke]['dc:identifier'] +
                '\n\ta\taopo:KeyEvent ;' +
                '\n\tdc:identifier\t' + kedict[ke]['dc:identifier'] +
                ' ;\n\trdfs:label\t' + kedict[ke]['rdfs:label'] +
                ' ;\n\tfoaf:page\t' + kedict[ke]['foaf:page'] +
                ' ;\n\trdfs:seeAlso\t' + kedict[ke]['foaf:page'] +
                ' ;\n\tdc:title\t' + kedict[ke]['dc:title'] +
                ' ;\n\tdcterms:alternative\t"' + kedict[ke]['dcterms:alternative'] + '"' +
                ' ;\n\tdc:source\t"' + kedict[ke]['dc:source'] + '"'
            )

            if 'dc:description' in kedict[ke]:
                g.write(' ;\n\tdc:description\t' + kedict[ke]['dc:description'])

            for predicate in ['mmo:0000000', 'nci:C25664']:
                if predicate in kedict[ke]:
                    g.write(f' ;\n\t{predicate}\t' + kedict[ke][predicate])

            if 'pato:0000047' in kedict[ke]:
                _write_multivalue_triple(g, 'pato:0000047', [sex[1] for sex in kedict[ke]['pato:0000047']], quote=True)
            if 'aopo:LifeStageContext' in kedict[ke]:
                _write_multivalue_triple(g, 'aopo:LifeStageContext', [stage[1] for stage in kedict[ke]['aopo:LifeStageContext']], quote=True)
            if 'ncbitaxon:131567' in kedict[ke]:
                _write_multivalue_triple(g, 'ncbitaxon:131567', [tax[2] for tax in kedict[ke]['ncbitaxon:131567']])
            if 'nci:C54571' in kedict[ke]:
                _write_multivalue_triple(g, 'nci:C54571', [kedict[ke]['nci:C54571'][s]['dc:identifier'] for s in kedict[ke]['nci:C54571']])

            if 'aopo:CellTypeContext' in kedict[ke]:
                cell_id = kedict[ke]['aopo:CellTypeContext']['dc:identifier'][0]
                g.write(' ;\n\taopo:CellTypeContext\t' + cell_id)
                if cell_id not in cterm:
                    cterm[cell_id] = {
                        'dc:source': kedict[ke]['aopo:CellTypeContext']['dc:source'],
                        'dc:title': kedict[ke]['aopo:CellTypeContext']['dc:title']
                    }

            if 'aopo:OrganContext' in kedict[ke]:
                organ_id = kedict[ke]['aopo:OrganContext']['dc:identifier'][0]
                g.write(' ;\n\taopo:OrganContext\t' + organ_id)
                if organ_id not in oterm:
                    oterm[organ_id] = {
                        'dc:source': kedict[ke]['aopo:OrganContext']['dc:source'],
                        'dc:title': kedict[ke]['aopo:OrganContext']['dc:title']
                    }

            if 'biological-events' in kedict[ke]:
                bioevent_uris = []
                for idx, be in enumerate(kedict[ke]['biological-events']):
                    be_uri = f'<{kedict[ke]["dc:identifier"].split(":")[1]}_bioevent_{idx}>'
                    bioevent_uris.append(be_uri)

                    triples = [f'{be_uri} a aopo:BiologicalEvent']
                    if 'process' in be:
                        triples.append(f'\taopo:hasProcess\t{be["process"]}')
                    if 'object' in be:
                        triples.append(f'\taopo:hasObject\t{be["object"]}')
                    if 'action' in be:
                        triples.append(f'\taopo:hasAction\t{be["action"]}')
                    bioevent_triples.append(' ;\n'.join(triples) + ' .\n\n')

                _write_multivalue_triple(g, 'aopo:hasBiologicalEvent', bioevent_uris)

            if 'biological-event' in kedict[ke]:
                for p in ['go:0008150', 'pato:0000001', 'pato:0001241']:
                    values = sorted(set(kedict[ke]['biological-event'].get(p, [])))
                    _write_multivalue_triple(g, p, values)

            aop_links = [
                aopdict[aop]['dc:identifier']
                for aop in aopdict
                if ke in aopdict[aop]['aopo:has_key_event']
            ]
            _write_multivalue_triple(g, 'dcterms:isPartOf', aop_links)

            g.write(' .\n\n')

        logger.info("Section completed")

        # Write biological events
        for triple_block in bioevent_triples:
            g.write(triple_block)

        # --- KER triples ---
        for ker in kerdict:
            g.write(
                kerdict[ker]['dc:identifier'] +
                '\n\ta\taopo:KeyEventRelationship ;' +
                '\n\tdc:identifier\t' + kerdict[ker]['dc:identifier'] +
                ' ;\n\trdfs:label\t' + kerdict[ker]['rdfs:label'] +
                ' ;\n\tfoaf:page\t' + kerdict[ker]['foaf:page'] +
                ' ;\n\trdfs:seeAlso\t' + kerdict[ker]['foaf:page'] +
                ' ;\n\tdcterms:created\t"' + kerdict[ker]['dcterms:created'] + '"' +
                ' ;\n\tdcterms:modified\t"' + kerdict[ker]['dcterms:modified'] + '"' +
                ' ;\n\taopo:has_upstream_key_event\t' + kerdict[ker]['aopo:has_upstream_key_event']['dc:identifier'] +
                ' ;\n\taopo:has_downstream_key_event\t' + kerdict[ker]['aopo:has_downstream_key_event']['dc:identifier']
            )

            if 'dc:description' in kerdict[ker]:
                g.write(' ;\n\tdc:description\t' + kerdict[ker]['dc:description'])

            for predicate in ['nci:C80263', 'edam:data_2042', 'nci:C71478']:
                if predicate in kerdict[ker]:
                    value = kerdict[ker][predicate].replace("\\", "")
                    g.write(f' ;\n\t{predicate}\t{value}')

            if 'pato:0000047' in kerdict[ker]:
                _write_multivalue_triple(g, 'pato:0000047', [sex[1] for sex in kerdict[ker]['pato:0000047']], quote=True)
            if 'aopo:LifeStageContext' in kerdict[ker]:
                _write_multivalue_triple(g, 'aopo:LifeStageContext', [stage[1] for stage in kerdict[ker]['aopo:LifeStageContext']], quote=True)
            if 'ncbitaxon:131567' in kerdict[ker]:
                _write_multivalue_triple(g, 'ncbitaxon:131567', [tax[2] for tax in kerdict[ker]['ncbitaxon:131567']])

            aop_links = [
                aopdict[aop]['dc:identifier']
                for aop in aopdict
                if ker in aopdict[aop]['aopo:has_key_event_relationship']
            ]
            _write_multivalue_triple(g, 'dcterms:isPartOf', aop_links)

            g.write(' .\n\n')

        logger.info("Section completed")

        # --- Taxonomy triples ---
        for tax in taxdict:
            if 'dc:identifier' in taxdict[tax]:
                if '"' not in taxdict[tax]['dc:identifier']:
                    g.write(taxdict[tax]['dc:identifier'] + '\n\ta\tncbitaxon:131567 ;\n\tdc:identifier\t' + taxdict[tax]['dc:identifier'] + ' ;\n\tdc:title\t"' + taxdict[tax]['dc:title'])
                    if taxdict[tax]['dc:source'] is not None:
                        g.write('" ;\n\tdc:source\t"' + taxdict[tax]['dc:source'])
                    g.write('" .\n\n')
        logger.info("Section completed")

        # --- Stressor triples ---
        for stressor in strdict:
            g.write(
                strdict[stressor]['dc:identifier'] +
                '\n\ta\tnci:C54571 ;' +
                '\n\tdc:identifier\t' + strdict[stressor]['dc:identifier'] +
                ' ;\n\trdfs:label\t' + strdict[stressor]['rdfs:label'] +
                ' ;\n\tfoaf:page\t' + strdict[stressor]['foaf:page'] +
                ' ;\n\tdc:title\t' + strdict[stressor]['dc:title'] +
                ' ;\n\tdcterms:created\t"' + strdict[stressor]['dcterms:created'] + '"' +
                ' ;\n\tdcterms:modified\t"' + strdict[stressor]['dcterms:modified'] + '"'
            )

            if 'dc:description' in strdict[stressor]:
                g.write(' ;\n\tdc:description\t' + strdict[stressor]['dc:description'])

            _write_multivalue_triple(g, 'aopo:has_chemical_entity', [chedict[chem]['dc:identifier'] for chem in strdict[stressor].get('linktochemical', [])])

            ke_ids = [
                kedict[ke]['dc:identifier']
                for ke in kedict
                if 'nci:C54571' in kedict[ke] and stressor in kedict[ke]['nci:C54571']
            ]

            aop_ids = set()
            for ke_id in ke_ids:
                for ke in kedict:
                    if kedict[ke]['dc:identifier'] == ke_id:
                        for aop in aopdict:
                            if ke in aopdict[aop]['aopo:has_key_event']:
                                aop_ids.add(aopdict[aop]['dc:identifier'])

            for aop in aopdict:
                if stressor in aopdict[aop].get('nci:C54571', {}):
                    aop_ids.add(aopdict[aop]['dc:identifier'])

            _write_multivalue_triple(g, 'dcterms:isPartOf', list(set(ke_ids + list(aop_ids))))

            g.write(' .\n\n')

        logger.info("Section completed")

        # --- Biological Process triples ---
        for pro in bioprodict:
            if pro is not None:
                g.write(bioprodict[pro]['dc:identifier'] + '\ta\tgo:0008150 ;\n\tdc:identifier\t' + bioprodict[pro]['dc:identifier'] + ' ;\n\tdc:title\t' + bioprodict[pro]['dc:title'] + ' ;\n\tdc:source\t' + bioprodict[pro]['dc:source'] + ' . \n\n')
        logger.info("Section completed")

        # --- Biological Object triples ---
        for obj in bioobjdict:
            if obj is not None and "N/A" not in bioobjdict[obj]['dc:identifier'] and 'TAIR' not in bioobjdict[obj]['dc:identifier']:
                g.write(bioobjdict[obj]['dc:identifier'] + '\ta\tpato:0001241 ;\n\tdc:identifier\t' + bioobjdict[obj]['dc:identifier'] + ' ;\n\tdc:title\t' + bioobjdict[obj]['dc:title'] + ' ;\n\tdc:source\t' + bioobjdict[obj]['dc:source'])
                if bioobjdict[obj]['dc:identifier'] in prodict:
                    identifiers = ','.join(prodict[bioobjdict[obj]['dc:identifier']])
                    if config and config.emit_legacy_predicates:
                        g.write(' ;\n\tskos:exactMatch\t' + identifiers)
                    g.write(' ;\n\towl:sameAs\t' + identifiers)
                g.write('. \n\n')
        logger.info("Section completed")

        # --- Biological Action triples ---
        for act in bioactdict:
            if act is not None:
                if '"' not in bioactdict[act]['dc:identifier']:
                    g.write(bioactdict[act]['dc:identifier'] + '\ta\tpato:0000001 ;\n\tdc:identifier\t' + bioactdict[act]['dc:identifier'] + ' ;\n\tdc:title\t' + bioactdict[act]['dc:title'] + ' ;\n\tdc:source\t' + bioactdict[act]['dc:source'] + ' . \n\n')
        logger.info("Section completed")

        # --- Cell term triples ---
        for item in cterm:
            if '"' not in item:
                g.write(item + '\ta\taopo:CellTypeContext ;\n\tdc:identifier\t' + item + ' ;\n\tdc:title\t' + cterm[item]['dc:title'] + ' ;\n\tdc:source\t' + cterm[item]['dc:source'] + ' .\n\n')
        logger.info("Section completed")

        # --- Organ term triples ---
        for item in oterm:
            if '"' not in item:
                g.write(item + '\ta\taopo:OrganContext ;\n\tdc:identifier\t' + item + ' ;\n\tdc:title\t' + oterm[item]['dc:title'] + ' ;\n\tdc:source\t' + oterm[item]['dc:source'] + ' .\n\n')
        logger.info("Section completed")

        # --- Chemical triples ---
        for che in chedict:
            che_data = chedict[che]
            if 'dc:identifier' not in che_data or '"' in che_data['dc:identifier']:
                continue

            g.write(f"{che_data['dc:identifier']}\n\tdc:identifier\t{che_data['dc:identifier']}")

            if 'cheminf:000446' in che_data:
                g.write(' ;\n\ta\tcheminf:000000, cheminf:000446')
                g.write(f' ;\n\tcheminf:000446\t{che_data["cheminf:000446"]}')

            if che_data.get('cheminf:000059') != 'inchikey:None':
                g.write(f' ;\n\tcheminf:000059\t{che_data["cheminf:000059"]}')

            if 'dc:title' in che_data:
                g.write(f' ;\n\tdc:title\t{che_data["dc:title"]}')

            if 'cheminf:000568' in che_data:
                g.write(f' ;\n\tcheminf:000568\t{che_data["cheminf:000568"]}')

            cheminf_keys = [
                'cheminf:000407', 'cheminf:000405', 'cheminf:000567', 'cheminf:000412',
                'cheminf:000140', 'cheminf:000406', 'cheminf:000408', 'cheminf:000409', 'cheminf:000564'
            ]
            exact_matches = []
            for key in cheminf_keys:
                exact_matches.extend(che_data.get(key, []))

            if config and config.emit_legacy_predicates:
                _write_multivalue_triple(g, 'skos:exactMatch', exact_matches)
            _write_multivalue_triple(g, 'owl:sameAs', exact_matches)

            if 'dcterms:alternative' in che_data:
                _write_multivalue_triple(g, 'dcterms:alternative', che_data['dcterms:alternative'], quote=True)

            part_of_stressors = [
                strdict[stressor]['dc:identifier']
                for stressor in strdict
                if 'aopo:has_chemical_entity' in strdict[stressor]
                and che in strdict[stressor]['linktochemical']
            ]
            _write_multivalue_triple(g, 'dcterms:isPartOf', part_of_stressors)

            g.write(' .\n\n')

        logger.info("Section completed")

        # --- Mapped Chemical identifiers ---
        n = 0
        for cas in listofcas:
            g.write(cas + '\tdc:source\t"CAS".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for inchikey in listofinchikey:
            g.write(inchikey + '\tdc:source\t"InChIKey".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")

        for comptox in listofcomptox:
            g.write(comptox + '\tdc:source\t"CompTox".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")

        for chebi in listofchebi:
            g.write(chebi + '\ta\tcheminf:000407 ;\n\tcheminf:000407\t"' + chebi[6:] + '";\n\tdc:identifier\t"' + chebi + '";\n\tdc:source\t"ChEBI".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for chemspider in listofchemspider:
            g.write(chemspider + '\ta\tcheminf:000405 ;\n\tcheminf:000405\t"' + chemspider[11:] + '";\n\tdc:identifier\t"' + chemspider + '";\n\tdc:source\t"ChemSpider".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for wd in listofwikidata:
            g.write(wd + '\ta\tcheminf:000567 ;\n\tcheminf:000567\t"' + wd[9:] + '";\n\tdc:identifier\t"' + wd + '";\n\tdc:source\t"Wikidata".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for chembl in listofchembl:
            g.write(chembl + '\ta\tcheminf:000412 ;\n\tcheminf:000412\t"' + chembl[16:] + '";\n\tdc:identifier\t"' + chembl + '";\n\tdc:source\t"ChEMBL".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for pubchem in listofpubchem:
            g.write(pubchem + '\ta\tcheminf:000140 ;\n\tcheminf:000140\t"' + pubchem[17:] + '";\n\tdc:identifier\t"' + pubchem + '";\n\tdc:source\t"PubChem".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for drugbank in listofdrugbank:
            g.write(drugbank + '\ta\tcheminf:000406 ;\n\tcheminf:000406\t"' + drugbank[9:] + '";\n\tdc:identifier\t"' + drugbank + '";\n\tdc:source\t"DrugBank".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for kegg in listofkegg:
            g.write(kegg + '\ta\tcheminf:000409 ;\n\tcheminf:000409\t"' + kegg[14:] + '";\n\tdc:identifier\t"' + kegg + '";\n\tdc:source\t"KEGG".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for lipidmaps in listoflipidmaps:
            g.write(lipidmaps + '\ta\tcheminf:000564 ;\n\tcheminf:000564\t"' + lipidmaps[10:] + '";\n\tdc:identifier\t"' + lipidmaps + '";\n\tdc:source\t"LIPID MAPS".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        for hmdb in listofhmdb:
            g.write(hmdb + '\ta\tcheminf:000408 ;\n\tcheminf:000408\t"' + hmdb[5:] + '";\n\tdc:identifier\t"' + hmdb + '";\n\tdc:source\t"HMDB".\n\n')
            n += 1
        logger.debug(f"Counter: {n}")
        logger.info("Section completed")

        # --- Mapped Gene identifiers ---
        symbol_lookup = entities.get('symbol_lookup', {})
        for hgnc in hgnclist:
            numeric_id = hgnc[5:]
            symbol = symbol_lookup.get(numeric_id, numeric_id)
            g.write(hgnc + '\ta\tedam:data_2298, edam:data_1025')
            g.write(f' ;\n\trdfs:label\t"{symbol}"')
            g.write(' ;\n\tedam:data_2298\t"' + numeric_id + '"')
            g.write(' ;\n\tdc:identifier\t"' + hgnc + '"')
            g.write(' ;\n\tdc:source\t"HGNC".\n\n')

        for entrez in ncbigenelist:
            g.write(entrez + '\ta\tedam:data_1027, edam:data_1025 ;\n\tedam:data_1027\t"' + entrez[9:] + '";\n\tdc:identifier\t"' + entrez + '";\n\tdc:source\t"Entrez Gene".\n\n')

        for uniprot in uniprotlist:
            g.write(uniprot + '\ta\tedam:data_2291, edam:data_1025 ;\n\trdfs:seeAlso <http://purl.uniprot.org/uniprot/' + uniprot[8:] + '>;\n\towl:sameAs <http://purl.uniprot.org/uniprot/' + uniprot[8:] + '>;\n\tedam:data_2291\t"' + uniprot[8:] + '";\n\tdc:identifier\t"' + uniprot + '";\n\tdc:source\t"UniProt".\n\n')

        logger.info("Section completed")

        # --- Class labels ---
        filepath_dir = str(filepath).rsplit('/', 1)[0] + '/' if '/' in str(filepath) else ''
        typelabels_path = filepath_dir + 'typelabels.txt'
        try:
            df = pd.read_csv(typelabels_path)
            for row, index in df.iterrows():
                g.write('\n\n' + index['URI'] + '\trdfs:label\t"' + index['label'])
                if index['description'] != '-':
                    g.write('";\n\tdc:description\t"""' + index['description'] + '""".')
                else:
                    g.write('".')
        except FileNotFoundError:
            logger.warning(f"typelabels.txt not found at {typelabels_path}, skipping class labels")

    logger.info("AOP-Wiki RDF conversion completed successfully!")
    logger.info("=== Conversion Summary ===")
    logger.info(f"Total AOPs processed: {len(aopdict)}")
    logger.info(f"Total Key Events processed: {len(kedict)}")
    logger.info(f"Total KERs processed: {len(kerdict)}")
    logger.info(f"Total Chemicals processed: {len(chedict)}")
    logger.info(f"RDF file created: {filepath}")


# ---------------------------------------------------------------------------
# Genes RDF file writer (pipeline.py lines 2159-2234)
# ---------------------------------------------------------------------------


def write_genes_rdf(filepath, gene_data, config=None):
    """Write AOPWikiRDF-Genes.ttl from gene mapping results.

    Parameters
    ----------
    filepath : str
        Output file path.
    gene_data : dict
        Dict with keys: 'kedict', 'kerdict', 'hgnclist',
        'geneiddict', 'listofentrez', 'listofensembl', 'listofuniprot'.
        Optional 'symbol_lookup' for gene rdfs:label generation.
    config : PipelineConfig, optional
        Pipeline configuration. When None, only owl:sameAs is emitted.
    """
    kedict = gene_data['kedict']
    kerdict = gene_data['kerdict']
    hgnclist = gene_data['hgnclist']
    geneiddict = gene_data['geneiddict']
    listofentrez = gene_data['listofentrez']
    listofensembl = gene_data['listofensembl']
    listofuniprot = gene_data['listofuniprot']

    logger.info(f"Writing genes RDF file: {filepath}")

    with open(filepath, 'w', encoding='utf-8') as g:
        g.write(GENES_PREFIXES + '\n')

        # KE gene mappings
        n = 0
        for ke in kedict:
            if 'edam:data_1025' in kedict[ke]:
                n += 1
                g.write(kedict[ke]['dc:identifier'] + '\tedam:data_1025\t' + ','.join(kedict[ke]['edam:data_1025']) + ' .\n\n')
        logger.info(f"Key Event gene mapping output: {n} events with mapped genes")

        # KER gene mappings
        n = 0
        for ker in kerdict:
            if 'edam:data_1025' in kerdict[ker]:
                n += 1
                g.write(kerdict[ker]['dc:identifier'] + '\tedam:data_1025\t' + ','.join(kerdict[ker]['edam:data_1025']) + ' .\n\n')
        logger.info(f"Key Event Relationship gene mapping output: {n} relationships with mapped genes")

        # Gene identifier triples
        symbol_lookup = gene_data.get('symbol_lookup', {})
        for hgnc in hgnclist:
            numeric_id = hgnc[5:]
            symbol = symbol_lookup.get(numeric_id, numeric_id)
            g.write(hgnc + '\ta\tedam:data_2298, edam:data_1025')
            g.write(f' ;\n\trdfs:label\t"{symbol}"')
            g.write(' ;\n\tedam:data_2298\t"' + numeric_id + '"')
            g.write(' ;\n\tdc:identifier\t"' + hgnc + '"')
            g.write(' ;\n\tdc:source\t"HGNC"')
            if not geneiddict[hgnc] == []:
                xrefs = ','.join(geneiddict[hgnc])
                if config and config.emit_legacy_predicates:
                    g.write(' ;\n\tskos:exactMatch\t' + xrefs)
                g.write(' ;\n\towl:sameAs\t' + xrefs)
            g.write('.\n\n')
        logger.info(f"{len(hgnclist)} HGNC triples written")

        for entrez in listofentrez:
            g.write(entrez + '\ta\tedam:data_1027, edam:data_1025 ;\n\tedam:data_1027\t"' + entrez[9:] + '";\n\tdc:identifier\t"' + entrez + '";\n\tdc:source\t"Entrez Gene".\n\n')
        logger.info(f"{len(listofentrez)} Entrez gene triples written")

        for ensembl in listofensembl:
            g.write(ensembl + '\ta\tedam:data_1033, edam:data_1025 ;\n\tedam:data_1033\t"' + ensembl[8:] + '";\n\tdc:identifier\t"' + ensembl + '";\n\tdc:source\t"Ensembl".\n\n')
        logger.info(f"{len(listofensembl)} Ensembl triples written")

        for uniprot in listofuniprot:
            g.write(uniprot + '\ta\tedam:data_2291, edam:data_1025 ;\n\tedam:data_2291\t"' + uniprot[8:] + '";\n\tdc:identifier\t"' + uniprot + '";\n\tdc:source\t"UniProt".\n\n')
        logger.info(f"{len(listofuniprot)} UniProt triples written")

    logger.info("AOP-Wiki RDF Genes file created successfully")


# ---------------------------------------------------------------------------
# VoID RDF file writer (pipeline.py lines 2237-2330)
# ---------------------------------------------------------------------------


def write_void_rdf(filepath, metadata):
    """Write AOPWikiRDF-Void.ttl and ServiceDescription.ttl.

    Parameters
    ----------
    filepath : str
        Output file path for VoID TTL.
    metadata : dict
        Dict with keys: 'aopwikixmlfilename', 'date', 'datetime_obj',
        'HGNCmodificationTime', 'PromodificationTime',
        'bridgedb_info', 'service_desc_filepath'.
    """
    aopwikixmlfilename = metadata['aopwikixmlfilename']
    x = metadata['datetime_obj']
    y = metadata['date']
    HGNCmodificationTime = metadata['HGNCmodificationTime']
    PromodificationTime = metadata['PromodificationTime']
    service_desc_filepath = metadata.get('service_desc_filepath')

    logger.info(f"Writing VoID RDF file: {filepath}")

    with open(filepath, 'w', encoding='utf-8') as g:
        g.write(VOID_PREFIXES)
        g.write('\n:AOPWikiRDF.ttl\ta\tvoid:Dataset ;\n\tdc:description\t"AOP-Wiki RDF data from the AOP-Wiki database" ;\n\tpav:createdOn\t"' + y + '"^^xsd:date;\n\tdcterms:modified\t"' + y + '"^^xsd:date ;\n\tpav:createdWith\t"' + str(aopwikixmlfilename) + '", :Promapping ;\n\tpav:createdBy\t<https://zenodo.org/badge/latestdoi/146466058> ;\n\tfoaf:homepage\t<https://aopwiki.org> ;\n\tdcterms:accuralPeriodicity  freq:quarterly ;\n\tdcat:downloadURL\t<https://aopwiki.org/downloads/' + str(aopwikixmlfilename) + '> .\n\n:AOPWikiRDF-Genes.ttl\ta\tvoid:Dataset ;\n\tdc:description\t"AOP-Wiki RDF extension with gene mappings based on approved names and symbols" ;\n\tpav:createdOn\t"' + str(x) + '" ;\n\tpav:createdWith\t"' + str(aopwikixmlfilename) + '", :HGNCgenes ;\n\tpav:createdBy\t<https://zenodo.org/badge/latestdoi/146466058> ;\n\tdcterms:accuralPeriodicity  freq:quarterly ;\n\tfoaf:homepage\t<https://aopwiki.org> ;\n\tdcat:downloadURL\t<https://aopwiki.org/downloads/' + str(aopwikixmlfilename) + '>, <https://www.genenames.org/download/custom/> . \n\n:HGNCgenes.txt\ta\tvoid:Dataset, void:Linkset ;\n\tdc:description\t"HGNC approved symbols and names for genes" ;\n\tdcat:downloadURL\t<https://www.genenames.org/download/custom/> ;\n\tpav:importedOn\t"' + HGNCmodificationTime + '" .\n\n<https://proconsortium.org/download/current/promapping.txt>\ta\tvoid:Dataset, void:Linkset;\n\tdc:description\t"PRotein ontology mappings to protein database identifiers";\n\tdcat:downloadURL\t<https://proconsortium.org/download/current/promapping.txt>;\n\tpav:importedOn\t"' + PromodificationTime + '".')

    logger.info("VoID file created successfully")

    # Generate ServiceDescription.ttl
    if service_desc_filepath:
        logger.info(f"Writing ServiceDescription.ttl file: {service_desc_filepath}")

        service_desc_content = f'''@prefix sd: <http://www.w3.org/ns/sparql-service-description#> .
    @prefix dcterms: <http://purl.org/dc/terms/> .
    @prefix void: <http://rdfs.org/ns/void#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

    <https://aopwiki.rdf.bigcat-bioinformatics.org/sparql/> a sd:Service ;
        sd:endpoint <https://aopwiki.rdf.bigcat-bioinformatics.org/sparql/> ;
        sd:supportedLanguage sd:SPARQL11Query ;
        sd:resultFormat
            <http://www.w3.org/ns/formats/SPARQL_Results_XML>,
            <http://www.w3.org/ns/formats/SPARQL_Results_JSON>,
            <http://www.w3.org/ns/formats/SPARQL_Results_CSV>,
            <http://www.w3.org/ns/formats/SPARQL_Results_TSV>,
            <http://www.w3.org/ns/formats/RDF_XML>,
            <http://www.w3.org/ns/formats/Turtle>,
            <http://www.w3.org/ns/formats/N-Triples>,
            <http://www.w3.org/ns/formats/RDF_JSON>,
            <http://www.w3.org/ns/formats/JSON-LD> ;
        sd:feature
            sd:DereferencesURIs,
            sd:UnionDefaultGraph,
            sd:BasicFederatedQuery ;
        sd:defaultDataset [
            a sd:Dataset ;
            sd:defaultGraph <http://aopwiki.org/> ;
            dcterms:title "AOP-Wiki RDF Dataset" ;
            dcterms:description "Adverse Outcome Pathway data in RDF format" ;
            dcterms:modified "{x.isoformat()}"^^xsd:dateTime
        ] ;
        dcterms:title "AOP-Wiki SPARQL Endpoint" ;
        dcterms:description "SPARQL endpoint for querying Adverse Outcome Pathway data" .
    '''

        with open(service_desc_filepath, 'w', encoding='utf-8') as f:
            f.write(service_desc_content)
        logger.info("ServiceDescription.ttl file created successfully")
