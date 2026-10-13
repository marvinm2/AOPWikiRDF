-- AOP-Wiki RDF endpoint — restore /.well-known/void.
--
-- REGRESSION, not a new feature. strato1 served this and still does: its aopwiki.sh
-- downloaded the VoID a second time under the extensionless name `void` (line 24) and copied
-- it into the Snorql UI's document root (line 47, `cp ./void ./aopwiki-snorql-extended/
-- .well-known/`), where the bind-mounted Apache served it. The 2026-07-16 cluster port
-- dropped both steps: reload.sh has no `void` download, its staging step only moves *.ttl,
-- and the cluster's Snorql UI runs from a GHCR image with no bind mount at all. So
-- /.well-known/void has 404'd here since 16 July, which is why YummyData records
-- `void: false` and an empty `license` for this endpoint.
--
-- Restored by CONSTRUCTing the VoID back out of the store rather than by re-copying a file:
-- the VoID is already loaded weekly as one of the five TTLs, so this needs no loader change,
-- no bind mount and no container restart. Verified to reproduce strato1's served document
-- exactly — 58 triples, zero difference, compared at the same generation vintage.
--
-- Since marvinm2/AOPWikiRDF#125 the VoID has its own graph, http://aopwiki.org/void, so the
-- rule CONSTRUCTs that whole graph. Before, it shared http://aopwiki.org/ with the data and
-- the rule had to pick out subjects typed void:Dataset or void:Linkset.
--
-- Traefik maps /.well-known/void onto /void-full. It is deliberately NOT mapped onto
-- Virtuoso's own `/.well-known` vhost, which already carries url_rewrite
-- `well_known_host_meta_rules` — a nested lpath there would interact with Virtuoso's
-- built-in host-meta handling for no benefit.
--
-- > One rule, no `accept_pattern`, no `format`. An earlier attempt used two rules gated on
-- > URR_ACCEPT_PATTERN — an RDF Accept negotiating, anything else defaulting to Turtle. The
-- > gate never fired: `application/rdf+xml` 406'd whether the pattern spelled the plus as `.`
-- > (which is how OpenLink's own documented example writes it) or as `[+]`. Every request was
-- > falling through to the Turtle-forcing rule and then 406ing when Turtle was not in the
-- > client's Accept. Rather than keep guessing at Virtuoso's regex semantics, the Accept
-- > handling now lives in Traefik, which is verifiable: an RDF Accept goes to this rule and
-- > content-negotiates, and anything else is rewritten with `Accept: text/turtle` injected, so
-- > a bare curl still gets the document exactly as strato1's static file did.
--
-- target_compose is an sprintf format string, hence the doubled %.
--
-- Revert:
--   DB.DBA.VHOST_REMOVE (lpath=>'/void-full');
--   DELETE FROM DB.DBA.URL_REWRITE_RULE_LIST WHERE URRL_LIST = 'aopwiki_void_rule_list1';
--   DELETE FROM DB.DBA.URL_REWRITE_RULE WHERE URR_RULE LIKE 'aopwiki_void_rule%';

DELETE FROM DB.DBA.URL_REWRITE_RULE_LIST WHERE URRL_LIST = 'aopwiki_void_rule_list1';
DELETE FROM DB.DBA.URL_REWRITE_RULE WHERE URR_RULE IN ('aopwiki_void_rule_neg', 'aopwiki_void_rule_ttl');

DB.DBA.URLREWRITE_CREATE_REGEX_RULE (
    'aopwiki_void_rule1',
    1,
    '/void-full',
    vector (),
    0,
    '/sparql?query=CONSTRUCT+%%7B+%%3Fs+%%3Fp+%%3Fo+%%7D+WHERE+%%7B+GRAPH+%%3Chttp%%3A%%2F%%2Faopwiki.org%%2Fvoid%%3E+%%7B+%%3Fs+%%3Fp+%%3Fo+%%7D+%%7D',
    vector (),
    null,
    null,
    2,
    null
);

DB.DBA.URLREWRITE_CREATE_RULELIST (
    'aopwiki_void_rule_list1',
    1,
    vector ('aopwiki_void_rule1')
);

DB.DBA.VHOST_REMOVE (lpath=>'/void-full');

DB.DBA.VHOST_DEFINE (
    lpath=>'/void-full',
    ppath=>'/DAV/',
    is_dav=>1,
    vsp_user=>'dba',
    opts=>vector ('url_rewrite', 'aopwiki_void_rule_list1')
);

SELECT HP_LPATH FROM DB.DBA.HTTP_PATH WHERE HP_LPATH = '/void-full';
SELECT URR_RULE, URR_ACCEPT_PATTERN FROM DB.DBA.URL_REWRITE_RULE WHERE URR_RULE LIKE 'aopwiki_void_rule%';
