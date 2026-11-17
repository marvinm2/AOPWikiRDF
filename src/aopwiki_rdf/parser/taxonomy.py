"""Taxonomic-applicability terms: NCBI normalisation and a per-run count (#145).

AOP-Wiki taxonomy terms come from several sources. Only ``source == 'NCBI'``
terms are written as ``ncbitaxon:<id>`` IRIs by the parser; the rest become
plain strings. Two of the other sources still carry an NCBI taxid:

* "common ecological/toxicological species" terms, source-id ``WCS_<taxid>``;
* terms whose source is an NCBI Taxonomy Browser URL (``...wwwtax.cgi?...&id=<taxid>``).

``normalise_taxa`` turns those into ``ncbitaxon:<taxid>`` (behind
``PipelineConfig.normalise_taxa``). ``WikiUser_<n>`` terms were created by wiki
users without an external identifier ("mammals", "rodents", "human, mouse,
rat"), so they stay strings; with normalisation the string is the term's name
instead of its bare id (#149). ``taxonomy_report`` counts the applicability
references by kind on every run, flag or not.
"""

import json
import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

TAXON_PREDICATE = 'ncbitaxon:131567'
_WCS = re.compile(r'WCS_(\d+)')
_WIKI_USER = re.compile(r'WikiUser_\d+')
_NCBI_BROWSER = re.compile(r'ncbi\.nlm\.nih\.gov/Taxonomy/Browser/\S*[?&]id=(\d+)')

KINDS = ('ncbi', 'normalised', 'ncbi_resolvable', 'wiki_user', 'other')


def _source_id(entry):
    """The raw source-id of a taxdict entry (its identifier without the quotes)."""
    identifier = entry.get('dc:identifier') or ''
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier[1:-1]
    return identifier


def ncbi_taxid(source, source_id):
    """NCBI taxid carried by a non-NCBI-source term, or None."""
    match = _WCS.fullmatch(source_id or '')
    if match:
        return match.group(1)
    match = _NCBI_BROWSER.search(source or '')
    if match:
        return match.group(1)
    return None


def _literal(text):
    """Quoted Turtle literal for a term name (the writer emits identifiers verbatim)."""
    escaped = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
    return '"' + escaped + '"'


def classify(entry):
    """Kind of a taxdict entry: one of ``KINDS``."""
    if entry.get('_wiki_user_id'):
        return 'wiki_user'
    if entry.get('_normalised_from'):
        return 'normalised'
    if entry.get('dc:source') == 'NCBI':
        return 'ncbi'
    source_id = _source_id(entry)
    if ncbi_taxid(entry.get('dc:source'), source_id):
        return 'ncbi_resolvable'
    if _WIKI_USER.fullmatch(source_id):
        return 'wiki_user'
    return 'other'


def _entity_dicts(entities):
    return {'aop': entities.aopdict, 'key_event': entities.kedict, 'ker': entities.kerdict}


def normalise_taxa(entities):
    """Rewrite NCBI-resolvable taxonomy terms to ``ncbitaxon:<taxid>`` in place.

    Updates ``entities.taxdict`` (keeping the original source-id in
    ``_normalised_from``) and the identifier slot of every applicability entry
    on AOPs, KEs and KERs that points at a rewritten term. User-created
    ``WikiUser_<n>`` terms stay strings, but the string becomes the term's name
    (``"mammals"`` instead of ``"WikiUser_17"``, #149), with the id kept in
    ``_wiki_user_id``. Returns the number of terms rewritten to IRIs.
    """
    rewritten = {}
    named = {}
    for tax_id, entry in entities.taxdict.items():
        if entry.get('dc:source') == 'NCBI' or 'dc:identifier' not in entry:
            continue
        source_id = _source_id(entry)
        taxid = ncbi_taxid(entry.get('dc:source'), source_id)
        if taxid:
            entry['_normalised_from'] = source_id
            entry['dc:identifier'] = 'ncbitaxon:' + taxid
            rewritten[tax_id] = entry['dc:identifier']
        elif _WIKI_USER.fullmatch(source_id) and (entry.get('dc:title') or '').strip():
            entry['_wiki_user_id'] = source_id
            entry['dc:identifier'] = _literal(entry['dc:title'].strip())
            named[tax_id] = entry['dc:identifier']
    for entity_dict in _entity_dicts(entities).values():
        for entity in entity_dict.values():
            for applicability in entity.get(TAXON_PREDICATE, []):
                if applicability[0] in rewritten:
                    applicability[2] = rewritten[applicability[0]]
                elif applicability[0] in named:
                    applicability[2] = named[applicability[0]]
    logger.info('Taxonomy normalisation: %d terms rewritten to NCBITaxon IRIs, %d user-created '
                'terms written by name', len(rewritten), len(named))
    return len(rewritten)


def taxonomy_report(entities, report_path=None):
    """Count taxonomic-applicability references by kind; optionally write JSON.

    Counts each (entity, taxonomy term) reference on AOPs, KEs and KERs, so a
    term used by 40 AOPs counts 40 times. Also lists the WikiUser terms with
    their use counts, since those are what the AOP-Wiki team would need to fix.
    """
    taxdict = entities.taxdict
    by_entity = {}
    wiki_user_uses = Counter()
    for name, entity_dict in _entity_dicts(entities).items():
        counts = Counter({kind: 0 for kind in KINDS})
        for entity in entity_dict.values():
            for applicability in entity.get(TAXON_PREDICATE, []):
                entry = taxdict.get(applicability[0], {})
                kind = classify(entry)
                counts[kind] += 1
                if kind == 'wiki_user':
                    wiki_user_uses[applicability[0]] += 1
        by_entity[name] = dict(counts)
    totals = Counter()
    for counts in by_entity.values():
        totals.update(counts)
    report = {
        'references': by_entity,
        'total': {kind: totals[kind] for kind in KINDS},
        'wiki_user_terms': [
            {'taxonomy_id': tax_id,
             'source_id': taxdict[tax_id].get('_wiki_user_id') or _source_id(taxdict[tax_id]),
             'name': taxdict[tax_id].get('dc:title'), 'uses': uses}
            for tax_id, uses in sorted(wiki_user_uses.items(), key=lambda item: (-item[1], item[0]))
        ],
    }
    logger.info('Taxonomy references: %s', ', '.join(f'{k} {totals[k]}' for k in KINDS))
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as fh:
            json.dump(report, fh, indent=2, sort_keys=False)
            fh.write('\n')
    return report
