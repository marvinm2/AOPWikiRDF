-- AOP-Wiki RDF endpoint — serve the curated service description.
-- marvinm2/AOP-Wiki-Snorql-UI#9
--
-- Maps /sparql-sd-full onto a CONSTRUCT over the `servicedescription` graph, so the
-- endpoint serves the 23 curated triples (dcterms:modified, dcterms:description,
-- sd:defaultDataset/defaultGraph, https:// endpoint URI) instead of Virtuoso's
-- generated /sparql-sd (~4.5 KB of virtrdf: internals with no modified date).
--
-- No `format=` parameter on purpose: the bare /sparql already content-negotiates a
-- CONSTRUCT on the request's own Accept header (verified: text/turtle,
-- application/rdf+xml, application/ld+json and text/n3 each return 200 with a
-- matching Content-Type). Passing format=%U with *accept* would break as soon as a
-- client sends a multi-type Accept list, which the YummyData crawler does.
--
-- target_compose is an sprintf format string, hence every literal % is doubled.
--
-- Revert:
--   DB.DBA.VHOST_REMOVE (lpath=>'/sparql-sd-full');
--   DELETE FROM DB.DBA.URL_REWRITE_RULE_LIST WHERE URRL_LIST = 'aopwiki_sd_rule_list1';
--   DELETE FROM DB.DBA.URL_REWRITE_RULE WHERE URR_RULE = 'aopwiki_sd_rule1';

DB.DBA.URLREWRITE_CREATE_REGEX_RULE (
    'aopwiki_sd_rule1',
    1,
    '/sparql-sd-full',
    vector (),
    0,
    '/sparql?query=CONSTRUCT+%%7B+%%3Fs+%%3Fp+%%3Fo+%%7D+WHERE+%%7B+GRAPH+%%3Cservicedescription%%3E+%%7B+%%3Fs+%%3Fp+%%3Fo+%%7D+%%7D',
    vector (),
    null,
    null,
    2,
    null
);

DB.DBA.URLREWRITE_CREATE_RULELIST (
    'aopwiki_sd_rule_list1',
    1,
    vector ('aopwiki_sd_rule1')
);

DB.DBA.VHOST_REMOVE (lpath=>'/sparql-sd-full');

DB.DBA.VHOST_DEFINE (
    lpath=>'/sparql-sd-full',
    ppath=>'/DAV/',
    is_dav=>1,
    vsp_user=>'dba',
    opts=>vector ('url_rewrite', 'aopwiki_sd_rule_list1')
);

SELECT HP_LPATH, HP_PPATH FROM DB.DBA.HTTP_PATH WHERE HP_LPATH = '/sparql-sd-full';
SELECT URR_RULE, URR_NICE_FORMAT, URR_TARGET_FORMAT FROM DB.DBA.URL_REWRITE_RULE WHERE URR_RULE = 'aopwiki_sd_rule1';
