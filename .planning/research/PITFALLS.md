# Domain Pitfalls

**Domain:** Biomedical RDF pipeline modernization — AOP-Wiki XML-to-RDF ETL
**Researched:** 2026-03-04
**Scope:** Refactoring monolith, RDF predicate changes, gene mapping, ShEx/SHACL adoption

---

## Critical Pitfalls

Mistakes that cause production regressions, downstream breakage, or require rewrites.

---

### Pitfall 1: Refactoring breaks the implicit state contract between pipeline stages

**What goes wrong:** The monolithic script in `AOP-Wiki_XML_to_RDF_conversion.py` relies on shared mutable state: `aopdict`, `kedict`, `kerdict`, `chedict`, `strdict`, `hgnclist`, and accumulator lists (`listofchebi`, `listofpubchem`, etc.) are all global and populated sequentially. When refactoring into modules, the natural instinct is to make each module self-contained — but if modules return copies rather than updating the same structure, the gene mapping stage (Step 5B) that reads `kedict` after the RDF output stage (Step 4) has already written it will silently produce fewer or no gene annotations.

**Why it happens:** The pipeline is not a clean ETL where each stage hands off a complete artifact. The RDF output stage and gene mapping stage both read the same `kedict` and write to different outputs. The two stages are temporally ordered but not causally separated. In the current code, the gene mapping step calls `ke.find(aopxml + 'key-event')` against the *original XML root*, but writes into `kedict[ke_id]['edam:data_1025']` which is then serialised in Step 5D. Moving the gene mapper into a separate module that takes a snapshot of `kedict` as input rather than mutating the same object will silently disconnect the mapping results from the output writer.

**Consequences:** Gene annotations missing from `AOPWikiRDF-Genes.ttl` without any error raised. The rdflib QC step will still pass because the file is valid Turtle — just empty of gene triples. Weekly production run commits a regressed file.

**Prevention:**
- Define explicit data contracts for each module: input type, output type, which dict keys are required and which are written.
- Write a post-refactor regression test that counts gene triples in the output and compares to a baseline snapshot (e.g., "must have at least 400 KEs with gene mappings").
- After each module extraction, run the full pipeline end-to-end on the current AOP-Wiki XML before merging, and diff the triple counts against the pre-refactor baseline.

**Detection:** Post-run log line "Key Event gene mapping output: N events with mapped genes" where N drops unexpectedly. Add a minimum threshold check here (current runs produce ~400+ mapped KEs).

**Phase:** Modularization phase (issue #64 / monolith refactor). Address during module boundary design, before any code moves.

---

### Pitfall 2: `skos:exactMatch` misuse causes a semantic correctness regression that is invisible to syntax validators

**What goes wrong:** The codebase already uses `skos:exactMatch` in two places for identifier cross-references: (1) chemical cross-references (`chedict` ChEBI/PubChem/etc. links at line 1654) and (2) gene cross-references (`hgnc → ncbigene/uniprot` links at line 2165). Issue #67 ("Review how ID mapping is described") signals that these uses are semantically incorrect — `skos:exactMatch` asserts concept-level equivalence between SKOS concepts, not identifier-to-identifier mappings across databases. The correct predicates are `owl:sameAs` (same real-world entity) or `skos:closeMatch` (near equivalence) or a custom property for "has cross-reference in database X".

**Why it happens:** `skos:exactMatch` was a pragmatic choice and is widely misused in biomedical linked data for this pattern. It produces syntactically valid Turtle and SPARQL queries that look for `skos:exactMatch` will still work — but SPARQL reasoners that apply SKOS inference rules will treat the two endpoints as interchangeable concept labels, which is not the intent. Downstream tools that follow SKOS semantics may produce unexpected results.

**Consequences if changed without care:** Every SPARQL query in `aopwiki-snorql-extended` (the downstream consumer) that currently queries `skos:exactMatch` to find cross-database identifiers will return zero results after the predicate is changed. This is a silent breakage — the query runs, returns nothing, no error is raised.

**Prevention:**
- Before changing any predicate, audit all SPARQL queries in the repository (`SPARQLQueries/`) and the downstream `aopwiki-snorql-extended` repository for use of the current predicate.
- Change predicates in a new TTL file first, keep the old predicate as well (`skos:exactMatch` and new predicate both present) during a transition period, then drop the old one after the downstream consumer is updated.
- Add a SPARQL-based regression test that asserts a known gene-to-ncbigene cross-reference is reachable via the new predicate.

**Detection:** After the change, run the SPARQL query "SELECT ?gene ?ncbi WHERE { ?gene <new_predicate> ?ncbi . FILTER(STRSTARTS(STR(?ncbi), 'https://identifiers.org/ncbigene/')) }" — it should return thousands of results. Zero means predicate change was not applied consistently.

**Phase:** Gene mapping rework phase (issue #65). The predicate fix and the gene mapping rework should be one coordinated change, not sequential.

---

### Pitfall 3: HGNC static file drift causes silent false negatives in gene mapping

**What goes wrong:** The gene mapping system depends on a static `HGNCgenes.txt` file. This file was downloaded at some point and is not automatically refreshed. HGNC is actively curated: gene symbols are deprecated (e.g., `SEPT` family renamed to `SEPTIN`), new symbols are approved, and synonym lists change. If the static file is 12+ months old, a proportion of text-mined gene mentions in KE descriptions will no longer match any entry — they produce no match rather than a wrong match, making them invisible to any precision metric.

**Concrete evidence:** The code at line 1798 logs the HGNCgenes.txt modification time but does not compare it to any maximum acceptable age. The CONCERNS.md entry "Gene dictionary loading not validated" confirms there is no size assertion for genedict1 (should have ~20,000+ entries for a current HGNC download).

**Why it happens:** The file is committed to the repository as a static asset. The weekly workflow does not re-download it. When modularizing the gene mapping pipeline, the temptation will be to inject the pre-loaded gene dicts as parameters — which is correct — but the question of where the file comes from is left as a configuration concern and never addressed.

**Consequences:** Genes mentioned in KE descriptions by recently-renamed symbols produce no match. `AOPWikiRDF-Genes.ttl` becomes progressively less complete over time without any error signal. Because gene mapping is measured in precision (false positives) but rarely in recall (false negatives), the problem is not visible in the existing test suite.

**Prevention:**
- Add HGNC download as a step in the weekly GitHub Actions workflow, pulling the latest from `https://www.genenames.org/download/custom/`. Cache it as a workflow artifact so local runs can still use a fallback.
- Add a `genedict1` size assertion after loading: if `len(genedict1) < 19000`, fail loudly with "HGNC file appears truncated or outdated".
- In the gene mapping module, accept the HGNC file path as a parameter with a documented expected version date.

**Detection:** `len(genedict1) < 19000` after loading is the earliest signal. Alternatively, track the count of unique genes found per run in VoID metadata and alert if it drops by more than 5% week-over-week.

**Phase:** Gene mapping rework phase (issue #65). Incorporate dynamic HGNC download into the redesign explicitly.

---

### Pitfall 4: Splitting pure vs enriched RDF into separate files breaks SPARQL queries that join across both

**What goes wrong:** The planned separation (issue #64) of pure AOP-Wiki content from enriched/associated content into distinct TTL files is semantically correct, but it will break any SPARQL query that currently joins AOP entities with their gene or chemical annotations in a single query — because these will now live in separate named graphs or separate files. The downstream SNORQL interface and any local Virtuoso endpoints loaded from all three TTL files will need the join to work across files. If files are loaded into a SPARQL endpoint as separate named graphs, queries using the default graph union will work; but if users have loaded only one file, gene annotation joins silently fail.

**Why it happens:** The current output architecture mixes pure AOP triples and enriched annotation triples into `AOPWikiRDF.ttl`. The split will create a cleaner design but introduces a new assumption: consumers must load both files to get full functionality. This assumption is currently undocumented and unenforceable.

**Consequences:** Queries like "find all AOPs linked to gene BRCA1" require joining `aopo:AdverseOutcomePathway` (in the pure file) with `edam:data_1025` gene link triples (in the enriched file). If the enriched file is not loaded, the query returns no results — correctly from the data perspective, but silently wrong from the user perspective.

**Prevention:**
- Document the multi-file loading requirement explicitly in the VoID metadata of each file, including `void:subset` relationships.
- Provide a Docker Compose or Virtuoso bulk-load script that loads all files together.
- Add an example SPARQL federated query that demonstrates the cross-file join.
- In the file separation design, consider whether `AOPWikiRDF.ttl` should use `owl:imports` or VoID subset declarations to signal its dependency on the enrichment file.

**Detection:** A SPARQL integration test that queries for "AOPs with gene links" and expects at least one result. If the enriched file is not loaded, this test returns zero.

**Phase:** Pure vs enriched separation phase (issue #64). Design the VoID metadata structure before implementing the file split.

---

### Pitfall 5: Modular refactor introduces an `exec()`-inherited state leak that is hard to reproduce

**What goes wrong:** The current `run_conversion.py` wrapper runs the entire conversion script via `exec(compile(script_content, ...), globals())` (line 67). This means all variables from the conversion script — `aopdict`, `kedict`, `g` (the open file handle), etc. — land in the `run_conversion.py` global namespace. When refactoring replaces `exec()` with a proper module import or subprocess call, any code that relied on this namespace pollution (e.g., test scripts that import `run_conversion` and then inspect `aopdict`) will break in ways that may not surface until CI runs.

**Why it happens:** The `exec()` pattern was used to allow `run_conversion.py` to inject `DATA_DIR` via string replacement before execution. This is documented in CONCERNS.md as "brittle" but it also creates an invisible coupling: the globals() injection means the main script never actually defines a `main()` function boundary.

**Consequences:** During refactoring, if tests or validation scripts import any part of the current monolith by loading `run_conversion.py` as a module, they will inherit the old `exec()` behaviour. After refactoring to a proper module, these scripts silently change behaviour. Also, the string-replacement config injection (`DATA_DIR = 'data/'` → custom path) must be replaced simultaneously — doing it in two steps leaves the pipeline in an intermediate broken state.

**Prevention:**
- Replace `exec()` with a proper module function call in a single commit that also moves `DATA_DIR` into an argument or environment variable.
- After the change, run the full pipeline once and verify the output directory is correctly used before tagging it as ready.
- Add a `__main__` guard and a `run(config)` function signature to the new module design before any of the existing logic moves.

**Detection:** `grep -r 'exec(compile' .` in the repo. Any remaining use after the refactor phase is a code review blocker.

**Phase:** Modularization phase, addressed as the very first step before any other module extractions.

---

## Moderate Pitfalls

Mistakes that degrade output quality or increase maintenance burden without immediately breaking production.

---

### Pitfall 6: ShEx/SHACL shapes over-constrain optional AOP fields and cause false failures

**What goes wrong:** AOP-Wiki entities have many optional fields — `dc:description` is present on most but not all AOPs, `dcterms:abstract` is populated only for published AOPs, and many KEs have no `edam:data_1025` gene annotations. If ShEx shapes are written with `+` (one-or-more) cardinality for fields that are optional in practice, the validation will report violations for every AOP or KE that lacks the field — producing hundreds or thousands of violations that obscure real structural errors.

**Concrete evidence:** The code at line 1303 already handles the `dc:description` absence with a conditional: `if 'dc:description' in aopdict[aop]`. This pattern exists for at least six fields. SHACL shapes that use `sh:minCount 1` for any of these will produce false failures.

**Prevention:**
- Before writing any shape, run SPARQL queries against the current output to determine the actual population rate of each property. Use `SELECT ?prop (COUNT(?s) AS ?n) WHERE { ?s ?prop ?o } GROUP BY ?prop ORDER BY DESC(?n)` to get a property population matrix.
- Use `sh:minCount 0 ; sh:maxCount 1` (optional-single) for fields that appear in fewer than 100% of entities of a given type.
- Separate "must-have" shapes (structural integrity) from "should-have" shapes (quality warnings) and run them as different severity levels.

**Detection:** Run the shape validator and check the violation count on the first pass. If more than 5% of entities of any type have violations, the shapes are likely over-constrained on optional fields.

**Phase:** ShEx/SHACL adoption phase (issue #52). Audit actual property populations before writing any shape definition.

---

### Pitfall 7: ShEx/SHACL validation on 3.3M-triple graph causes GitHub Actions timeout

**What goes wrong:** Full SHACL validation with `pyshacl` on the main `AOPWikiRDF.ttl` file (16MB, ~3.3M triples) can take 30-90 minutes depending on shape complexity and inference mode. The GitHub Actions workflow has a 120-minute total budget. If the SHACL step runs after RDF generation, the combined time budget will be exceeded on complex shapes, causing a workflow timeout that leaves the run in an ambiguous state — the RDF files may or may not have been committed.

**Prevention:**
- Run SHACL validation in a separate workflow triggered after the RDF generation workflow completes and commits files. Do not block the commit on SHACL.
- Use `sh:deactivated true` on computationally expensive shapes initially; add them one at a time and measure the time impact.
- Consider validating a sample of entities (e.g., first 100 AOPs, first 100 KEs) as a quick sanity check in the generation workflow, and full validation in a nightly or weekly separate job.
- Set `inference='none'` in pyshacl unless OWL inference is explicitly needed — this alone can reduce validation time by 10x.

**Detection:** Add a timing wrapper around the SHACL validation step. If it exceeds 10 minutes in isolation, the shape is too expensive for inline workflow execution.

**Phase:** ShEx/SHACL adoption phase (issue #52). Run time benchmarks before integrating into the main workflow.

---

### Pitfall 8: AOP-Wiki XML schema changes break the parser without any warning signal

**What goes wrong:** The XML extraction code uses hardcoded element path lookups like `ke.find(aopxml + 'description')` and attribute names like `ke.get('id')`. The AOP-Wiki XML schema is updated quarterly alongside data releases. A schema change — even renaming one element from `<description>` to `<detailed-description>` or adding a namespace prefix — causes the field to silently return `None` rather than raising an exception. Because the code uses `safe_get_text()` with a default of `''`, the missing data propagates forward as empty strings.

**Concrete evidence:** CONCERNS.md explicitly documents this: "If AOP-Wiki changes XML structure... parser breaks silently." The entity count validation (minimum thresholds for AOP/KE/KER counts) would catch a catastrophic schema break, but not a partial one that only affects one optional element.

**Prevention:**
- Keep a copy of the XML schema or a small representative XML fragment in the test fixtures. When a new quarterly XML is downloaded, diff the element structure before parsing.
- Add field-level population checks after parsing: if `dc:description` is populated for fewer than 50% of KEs, log a warning and halt. Document the expected population rates as constants.
- On the modularization branch, add schema validation at the XML parser module boundary using `xml.etree.ElementTree.XMLSchema` or a lightweight custom validator.

**Detection:** After each weekly run, check that `kedict` entry counts and populated-field rates match expectations. A sudden drop in, e.g., average description length across all KEs signals a schema change.

**Phase:** Modularization phase. The XML parser module boundary is the natural place to add schema guards.

---

### Pitfall 9: Gene symbol ambiguity across species — the Human-only BridgeDb endpoint assumption

**What goes wrong:** The BridgeDb endpoint is hardcoded as `/Human/` (line 36). HGNC is human-specific. But AOP-Wiki KE descriptions are written for biological processes that apply across species, and the text may reference rat or mouse gene names (e.g., `Cyp1a1` lowercase, or `Nr3c1`). These will be matched against the human HGNC dictionary if the human symbol happens to overlap (e.g., `CYP1A1` is a valid human gene), producing a human gene annotation for a description that may describe a rat study.

**Why it happens:** The pipeline was designed as human-centric from the start. The Taxonomy support added in the most recent commit (commit b8f9b1d) adds taxonomy triples to AOP entities, but the gene mapping step does not check whether the KE context suggests a non-human organism before doing human-only mapping.

**Consequences:** Gene annotations may be semantically wrong for cross-species KEs. Any downstream biomedical reasoning that uses `edam:data_1025` gene links to infer human gene-AOP associations will over-count or mis-attribute.

**Prevention:**
- In the gene mapping rework (issue #65), add a "species context" check: if a KE's taxonomy indicates non-human (via `taxdict`), skip the HGNC mapping or annotate with a species qualifier.
- Document the current limitation explicitly in the VoID metadata: "Gene annotations in AOPWikiRDF-Genes.ttl are mapped to human HGNC symbols regardless of the KE's primary organism."
- This is an acceptable known limitation for now, but it must be recorded so it does not get treated as a feature.

**Detection:** Query for KEs that have both a non-human taxonomy annotation and `edam:data_1025` gene links. If non-zero, manually review a sample for correctness.

**Phase:** Gene mapping rework phase (issue #65). Document explicitly in the redesign specification.

---

### Pitfall 10: Output file atomicity — partial write is committed as valid RDF

**What goes wrong:** The three output files (`AOPWikiRDF.ttl`, `AOPWikiRDF-Genes.ttl`, `AOPWikiRDF-Void.ttl`) are written sequentially to disk. If the process crashes after writing the first file but before completing the third, the GitHub Actions workflow QC step will parse each file independently and the partial state will pass — because `AOPWikiRDF.ttl` is syntactically valid even if `AOPWikiRDF-Genes.ttl` was never created or is truncated. The workflow will then commit the inconsistent set.

**Concrete evidence:** CONCERNS.md documents this: "Three separate RDF files generated sequentially without atomic operations... current workaround: GitHub Actions workflow validates all three files before committing." But if `AOPWikiRDF-Genes.ttl` is missing entirely, the QC step may fail only on that file — but the git commit step may have already staged `AOPWikiRDF.ttl`.

**Prevention:**
- Write all output to temp files first (`AOPWikiRDF.ttl.tmp`, etc.), then do a single `os.rename()` to the final names after all three are complete. This is an atomic swap on Linux.
- In the GitHub Actions workflow, explicitly check that all three files exist and have non-zero size before the commit step.

**Detection:** After any failed workflow run, check the sizes of all three output files. If any is zero bytes or missing, roll back.

**Phase:** Modularization phase. The temp-file pattern is easy to add when restructuring the output writer module.

---

## Minor Pitfalls

Issues that are annoying but recoverable without pipeline downtime.

---

### Pitfall 11: BridgeDb system code map is incomplete and silently drops new identifier types

**What goes wrong:** The batch gene mapping parser in `map_genes_batch_bridgedb()` (lines 1992-2025) maps BridgeDb system codes to database names using a hardcoded dictionary (e.g., `'L'` → Entrez Gene, `'En'` → Ensembl). BridgeDb may return additional system codes for databases added after the code was written. Unrecognised codes fall through to an `else` branch that assigns a generic name or skips the entry. New identifier types are silently lost.

**Prevention:** Add an `else: logger.warning(f"Unknown BridgeDb system code: {system_code}")` branch and accumulate unknown codes in a counter. Log a summary at the end of the batch run.

**Phase:** Gene mapping rework phase (issue #65). Review and extend the system code map.

---

### Pitfall 12: Prefix declarations in the main TTL file include SHACL namespace declarations that bloat downstream loading

**What goes wrong:** Every AOP entity block in `AOPWikiRDF.ttl` is preceded by a block of `sh:declare` triples (lines 52-74 of the output file). These SHACL namespace declaration triples are not part of the AOP ontology — they are tooling metadata for SHACL processors. Loading `AOPWikiRDF.ttl` into a Virtuoso or Fuseki triple store will import these blank-node triples into the default graph, polluting it with ~50 extra triples per prefix that have no semantic meaning for AOP queries.

**Prevention:** Move SHACL namespace declarations to a separate file (`AOPWikiRDF-SHACL-Prefixes.ttl`) that is only needed when running shape validation. Do not include them in the main data file.

**Phase:** Modularization or ShEx/SHACL adoption phase. Low priority but should be cleaned up before the ShEx work.

---

### Pitfall 13: String-concatenation triple writing breaks on literal values containing special Turtle characters

**What goes wrong:** RDF triple writing is done via direct string concatenation (e.g., line 1297: `'\n\tdcterms:alternative\t"' + aopdict[aop]['dcterms:alternative'] + '"'`). If an AOP title or description contains a double quote, backslash, or newline — all of which appear in scientific text — the resulting Turtle file is syntactically invalid. The current code relies on the AOP-Wiki data being well-behaved.

**Prevention:** When refactoring the output writer module, use rdflib's `Graph` object and `Literal()` for all string values rather than string concatenation. rdflib handles escaping automatically.

**Detection:** The rdflib validation step will catch this — but only after the file is written. If it occurs, the weekly commit produces an invalid file and the QC step fails.

**Phase:** Modularization phase. Use rdflib `Graph` for RDF writing in the new `core/rdf_writer.py` module.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Module extraction (monolith split) | State contract breakage between stages (Pitfall 1) | Define explicit data contracts before moving any code |
| Module extraction (monolith split) | `exec()` namespace leak in tests (Pitfall 5) | Replace `exec()` in the very first commit of this phase |
| Module extraction (monolith split) | String concatenation breaks on special chars (Pitfall 13) | Switch to rdflib Graph in the output writer module |
| Module extraction (monolith split) | Non-atomic output write (Pitfall 10) | Use temp-file-and-rename in the output writer module |
| Predicate rework (issue #67) | Downstream SPARQL query breakage (Pitfall 2) | Audit downstream SPARQL before changing any predicate; run in parallel for a transition period |
| Pure/enriched split (issue #64) | Cross-file join breaks for single-file consumers (Pitfall 4) | Document VoID subset relationships; provide multi-file load instructions |
| Gene mapping rework (issue #65) | HGNC file staleness causes false negatives (Pitfall 3) | Add dynamic HGNC download to workflow |
| Gene mapping rework (issue #65) | BridgeDb system code map incomplete (Pitfall 11) | Log unknown codes; extend map |
| Gene mapping rework (issue #65) | Species ambiguity in human-only mapping (Pitfall 9) | Document limitation; add taxonomy context check |
| ShEx/SHACL adoption (issue #52) | Over-constraining optional fields (Pitfall 6) | Property population audit before writing any shape |
| ShEx/SHACL adoption (issue #52) | Workflow timeout on full graph validation (Pitfall 7) | Separate validation workflow; test timing before integrating |
| ShEx/SHACL adoption (issue #52) | SHACL prefix declarations bloating main TTL (Pitfall 12) | Move to separate file |
| All phases | AOP-Wiki XML schema change breaks parser (Pitfall 8) | Add XML schema validation at parser module boundary |

---

## Sources

All findings are verified directly from the codebase:

- `AOP-Wiki_XML_to_RDF_conversion.py` — lines 108-231, 1292-1320, 1582-1586, 1644-1654, 1793-1837, 1942-2107, 2162-2167
- `run_conversion.py` — lines 49-67 (exec/string-replacement config pattern)
- `.planning/codebase/CONCERNS.md` — documented concerns audit (2026-03-04)
- `.planning/codebase/ARCHITECTURE.md` — layer and data flow analysis
- `.planning/PROJECT.md` — active requirements and constraints
- `data/AOPWikiRDF.ttl` — lines 52-74 (SHACL namespace declarations in main data file)
- `data/AOPWikiRDF-Genes.ttl` — line 5 (`skos:exactMatch` usage for gene cross-references)
- `prefixes.csv` — namespace declarations confirming SHACL and SKOS are in scope
- GitHub issues #52, #64, #65, #67 — scope and rationale for the four active modernization threads

**Confidence:** HIGH — all pitfalls are grounded in code line references or architecture documentation. No claims rely on training data alone.
