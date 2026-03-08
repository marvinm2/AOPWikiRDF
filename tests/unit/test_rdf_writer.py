"""Unit tests for the RDF writer module."""

import datetime
import os
import tempfile

import pytest


def test_writer_importable():
    """Writer module imports without running the full pipeline."""
    from aopwiki_rdf.rdf.writer import write_aop_rdf, write_genes_rdf, write_void_rdf
    assert callable(write_aop_rdf)
    assert callable(write_genes_rdf)
    assert callable(write_void_rdf)


def test_write_genes_rdf_minimal():
    """Write a minimal genes RDF file and validate Turtle syntax."""
    from aopwiki_rdf.rdf.writer import write_genes_rdf
    from rdflib import Graph

    gene_data = {
        'kedict': {
            '1': {
                'dc:identifier': 'aop.events:1',
                'edam:data_1025': ['hgnc:TP53'],
            }
        },
        'kerdict': {},
        'hgnclist': ['hgnc:TP53'],
        'geneiddict': {'hgnc:TP53': ['ncbigene:7157']},
        'listofentrez': ['ncbigene:7157'],
        'listofensembl': ['ensembl:ENSG00000141510'],
        'listofuniprot': ['uniprot:P04637'],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, 'AOPWikiRDF-Genes.ttl')
        write_genes_rdf(out, gene_data)

        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

        g = Graph()
        g.parse(out, format='turtle')
        assert len(g) > 0


def test_write_void_rdf_minimal():
    """Write a minimal VoID file and validate Turtle syntax."""
    from aopwiki_rdf.rdf.writer import write_void_rdf
    from rdflib import Graph

    now = datetime.datetime.now()
    metadata = {
        'aopwikixmlfilename': 'aop-wiki-xml-2025-01-01.gz',
        'date': now.strftime('%Y-%m-%d'),
        'datetime_obj': now,
        'HGNCmodificationTime': '2025-01-01',
        'PromodificationTime': '2025-01-01',
        'bridgedb_info': {},
        'service_desc_filepath': None,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        out = os.path.join(tmpdir, 'AOPWikiRDF-Void.ttl')
        write_void_rdf(out, metadata)

        assert os.path.exists(out)
        content = open(out).read()
        assert 'void:Dataset' in content

        g = Graph()
        g.parse(out, format='turtle')
        assert len(g) > 0


def test_write_void_rdf_with_service_desc():
    """Write VoID with ServiceDescription and verify both files."""
    from aopwiki_rdf.rdf.writer import write_void_rdf

    now = datetime.datetime.now()
    with tempfile.TemporaryDirectory() as tmpdir:
        void_path = os.path.join(tmpdir, 'AOPWikiRDF-Void.ttl')
        sd_path = os.path.join(tmpdir, 'ServiceDescription.ttl')

        metadata = {
            'aopwikixmlfilename': 'aop-wiki-xml-2025-01-01.gz',
            'date': now.strftime('%Y-%m-%d'),
            'datetime_obj': now,
            'HGNCmodificationTime': '2025-01-01',
            'PromodificationTime': '2025-01-01',
            'bridgedb_info': {},
            'service_desc_filepath': sd_path,
        }

        write_void_rdf(void_path, metadata)
        assert os.path.exists(sd_path)
        assert os.path.getsize(sd_path) > 0


# ---------------------------------------------------------------------------
# Predicate correction tests (Plan 03-02)
# ---------------------------------------------------------------------------

def _make_gene_data_numeric():
    """Helper: minimal gene_data with numeric HGNC IDs and symbol_lookup."""
    return {
        'kedict': {
            '1': {
                'dc:identifier': 'aop.events:1',
                'edam:data_1025': ['hgnc:1100'],
            }
        },
        'kerdict': {},
        'hgnclist': ['hgnc:1100'],
        'geneiddict': {'hgnc:1100': ['ncbigene:672', 'ensembl:ENSG00000012048']},
        'listofentrez': ['ncbigene:672'],
        'listofensembl': ['ensembl:ENSG00000012048'],
        'listofuniprot': ['uniprot:P38398'],
        'symbol_lookup': {'1100': 'BRCA1'},
    }


class TestEmitLegacyPredicatesConfig:
    """Tests for the emit_legacy_predicates config flag."""

    def test_config_has_emit_legacy_predicates(self):
        """PipelineConfig has emit_legacy_predicates field defaulting to True."""
        from aopwiki_rdf.config import PipelineConfig
        config = PipelineConfig()
        assert hasattr(config, 'emit_legacy_predicates')
        assert config.emit_legacy_predicates is True

    def test_config_emit_legacy_predicates_overridable(self):
        """emit_legacy_predicates can be set to False."""
        from aopwiki_rdf.config import PipelineConfig
        config = PipelineConfig(emit_legacy_predicates=False)
        assert config.emit_legacy_predicates is False


class TestDualPredicateGenes:
    """Tests for dual-predicate emission in write_genes_rdf."""

    def test_dual_predicate_mode_genes(self):
        """With emit_legacy_predicates=True, both skos:exactMatch AND owl:sameAs present."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=True)
        gene_data = _make_gene_data_numeric()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'Genes.ttl')
            write_genes_rdf(out, gene_data, config=config)
            content = open(out).read()
            assert 'skos:exactMatch' in content
            assert 'owl:sameAs' in content

    def test_owl_sameAs_only_genes(self):
        """With emit_legacy_predicates=False, only owl:sameAs emitted (no skos:exactMatch)."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=False)
        gene_data = _make_gene_data_numeric()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'Genes.ttl')
            write_genes_rdf(out, gene_data, config=config)
            content = open(out).read()
            assert 'skos:exactMatch' not in content
            assert 'owl:sameAs' in content

    def test_no_config_genes_owl_sameAs_only(self):
        """When config=None (backward compat), emit only owl:sameAs."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf

        gene_data = _make_gene_data_numeric()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'Genes.ttl')
            write_genes_rdf(out, gene_data)
            content = open(out).read()
            assert 'skos:exactMatch' not in content
            assert 'owl:sameAs' in content


class TestGeneLabels:
    """Tests for rdfs:label on gene nodes."""

    def test_gene_rdfs_label(self):
        """Gene nodes have rdfs:label with the gene symbol."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=False)
        gene_data = _make_gene_data_numeric()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'Genes.ttl')
            write_genes_rdf(out, gene_data, config=config)
            content = open(out).read()
            assert 'rdfs:label\t"BRCA1"' in content

    def test_numeric_hgnc_uris(self):
        """Gene URIs use numeric HGNC IDs (hgnc:1100 not hgnc:BRCA1)."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=False)
        gene_data = _make_gene_data_numeric()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'Genes.ttl')
            write_genes_rdf(out, gene_data, config=config)
            content = open(out).read()
            assert 'hgnc:1100' in content
            assert 'hgnc:BRCA1' not in content

    def test_genes_turtle_valid(self):
        """Generated Genes Turtle is syntactically valid."""
        from aopwiki_rdf.rdf.writer import write_genes_rdf
        from aopwiki_rdf.config import PipelineConfig
        from rdflib import Graph

        config = PipelineConfig(emit_legacy_predicates=True)
        gene_data = _make_gene_data_numeric()

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, 'Genes.ttl')
            write_genes_rdf(out, gene_data, config=config)
            g = Graph()
            g.parse(out, format='turtle')
            assert len(g) > 0


class TestDualPredicateChemicalsAndProteinOntology:
    """Tests for dual-predicate emission on chemical and protein ontology sites."""

    def _make_minimal_entities(self, include_prodict=True, include_chemicals=True):
        """Build minimal entities dict for write_aop_rdf."""
        entities = {
            'aopdict': {}, 'kedict': {}, 'kerdict': {}, 'strdict': {},
            'taxdict': {}, 'bioprodict': {}, 'bioactdict': {},
            'hgnclist': [], 'ncbigenelist': [], 'uniprotlist': [],
            'listofcas': [], 'listofinchikey': [], 'listofcomptox': [],
            'listofchebi': [], 'listofchemspider': [], 'listofwikidata': [],
            'listofchembl': [], 'listofpubchem': [], 'listofdrugbank': [],
            'listofkegg': [], 'listoflipidmaps': [], 'listofhmdb': [],
        }
        if include_prodict:
            entities['bioobjdict'] = {
                'obj1': {
                    'dc:identifier': 'pr:000001',
                    'dc:title': '"Test Protein"',
                    'dc:source': '"PRO"',
                }
            }
            entities['prodict'] = {
                'pr:000001': ['hgnc:1100', 'uniprot:P38398'],
            }
        else:
            entities['bioobjdict'] = {}
            entities['prodict'] = {}

        if include_chemicals:
            entities['chedict'] = {
                'chem1': {
                    'dc:identifier': 'cas:50-00-0',
                    'cheminf:000446': 'chebi:16842',
                    'dc:title': '"Formaldehyde"',
                    'cheminf:000059': 'inchikey:WSFSSNUMVMOOMR-UHFFFAOYSA-N',
                    'cheminf:000407': ['chebi:16842'],
                }
            }
        else:
            entities['chedict'] = {}

        return entities

    def test_dual_predicate_protein_ontology(self):
        """With emit_legacy_predicates=True, protein ontology links have both predicates."""
        from aopwiki_rdf.rdf.writer import write_aop_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=True)
        entities = self._make_minimal_entities(include_chemicals=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            prefix_csv = os.path.join(tmpdir, 'prefixes.csv')
            # Minimal prefixes.csv
            with open(prefix_csv, 'w') as f:
                f.write('prefix,uri\n')
                f.write('dc,http://purl.org/dc/elements/1.1/\n')
                f.write('rdfs,http://www.w3.org/2000/01/rdf-schema#\n')
                f.write('skos,http://www.w3.org/2004/02/skos/core#\n')
                f.write('owl,http://www.w3.org/2002/07/owl#\n')
                f.write('pato,http://purl.obolibrary.org/obo/PATO_\n')
                f.write('pr,http://purl.obolibrary.org/obo/PR_\n')
                f.write('hgnc,https://identifiers.org/hgnc/\n')
                f.write('uniprot,https://identifiers.org/uniprot/\n')
                f.write('sh,http://www.w3.org/ns/shacl#\n')
                f.write('xsd,http://www.w3.org/2001/XMLSchema#\n')

            out = os.path.join(tmpdir, 'AOPWikiRDF.ttl')
            write_aop_rdf(out, entities, prefix_csv, config=config)
            content = open(out).read()
            assert 'skos:exactMatch' in content
            assert 'owl:sameAs' in content

    def test_owl_only_protein_ontology(self):
        """With emit_legacy_predicates=False, only owl:sameAs for protein ontology."""
        from aopwiki_rdf.rdf.writer import write_aop_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=False)
        entities = self._make_minimal_entities(include_chemicals=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            prefix_csv = os.path.join(tmpdir, 'prefixes.csv')
            with open(prefix_csv, 'w') as f:
                f.write('prefix,uri\n')
                f.write('dc,http://purl.org/dc/elements/1.1/\n')
                f.write('rdfs,http://www.w3.org/2000/01/rdf-schema#\n')
                f.write('skos,http://www.w3.org/2004/02/skos/core#\n')
                f.write('owl,http://www.w3.org/2002/07/owl#\n')
                f.write('pato,http://purl.obolibrary.org/obo/PATO_\n')
                f.write('pr,http://purl.obolibrary.org/obo/PR_\n')
                f.write('hgnc,https://identifiers.org/hgnc/\n')
                f.write('uniprot,https://identifiers.org/uniprot/\n')
                f.write('sh,http://www.w3.org/ns/shacl#\n')
                f.write('xsd,http://www.w3.org/2001/XMLSchema#\n')

            out = os.path.join(tmpdir, 'AOPWikiRDF.ttl')
            write_aop_rdf(out, entities, prefix_csv, config=config)
            content = open(out).read()
            assert 'skos:exactMatch' not in content
            assert 'owl:sameAs' in content

    def test_dual_predicate_chemicals(self):
        """With emit_legacy_predicates=True, chemical identifiers have both predicates."""
        from aopwiki_rdf.rdf.writer import write_aop_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=True)
        entities = self._make_minimal_entities(include_prodict=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            prefix_csv = os.path.join(tmpdir, 'prefixes.csv')
            with open(prefix_csv, 'w') as f:
                f.write('prefix,uri\n')
                f.write('dc,http://purl.org/dc/elements/1.1/\n')
                f.write('rdfs,http://www.w3.org/2000/01/rdf-schema#\n')
                f.write('skos,http://www.w3.org/2004/02/skos/core#\n')
                f.write('owl,http://www.w3.org/2002/07/owl#\n')
                f.write('cheminf,http://semanticscience.org/resource/CHEMINF_\n')
                f.write('chebi,https://identifiers.org/chebi/\n')
                f.write('cas,https://identifiers.org/cas/\n')
                f.write('inchikey,https://identifiers.org/inchikey/\n')
                f.write('sh,http://www.w3.org/ns/shacl#\n')
                f.write('xsd,http://www.w3.org/2001/XMLSchema#\n')

            out = os.path.join(tmpdir, 'AOPWikiRDF.ttl')
            write_aop_rdf(out, entities, prefix_csv, config=config)
            content = open(out).read()
            assert 'skos:exactMatch' in content
            assert 'owl:sameAs' in content

    def test_owl_only_chemicals(self):
        """With emit_legacy_predicates=False, only owl:sameAs for chemicals."""
        from aopwiki_rdf.rdf.writer import write_aop_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=False)
        entities = self._make_minimal_entities(include_prodict=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            prefix_csv = os.path.join(tmpdir, 'prefixes.csv')
            with open(prefix_csv, 'w') as f:
                f.write('prefix,uri\n')
                f.write('dc,http://purl.org/dc/elements/1.1/\n')
                f.write('rdfs,http://www.w3.org/2000/01/rdf-schema#\n')
                f.write('skos,http://www.w3.org/2004/02/skos/core#\n')
                f.write('owl,http://www.w3.org/2002/07/owl#\n')
                f.write('cheminf,http://semanticscience.org/resource/CHEMINF_\n')
                f.write('chebi,https://identifiers.org/chebi/\n')
                f.write('cas,https://identifiers.org/cas/\n')
                f.write('inchikey,https://identifiers.org/inchikey/\n')
                f.write('sh,http://www.w3.org/ns/shacl#\n')
                f.write('xsd,http://www.w3.org/2001/XMLSchema#\n')

            out = os.path.join(tmpdir, 'AOPWikiRDF.ttl')
            write_aop_rdf(out, entities, prefix_csv, config=config)
            content = open(out).read()
            assert 'skos:exactMatch' not in content
            assert 'owl:sameAs' in content

    def test_main_rdf_gene_rdfs_label(self):
        """Gene nodes in main RDF have rdfs:label when symbol_lookup available."""
        from aopwiki_rdf.rdf.writer import write_aop_rdf
        from aopwiki_rdf.config import PipelineConfig

        config = PipelineConfig(emit_legacy_predicates=False)
        entities = self._make_minimal_entities(include_prodict=False, include_chemicals=False)
        entities['hgnclist'] = ['hgnc:1100']
        entities['symbol_lookup'] = {'1100': 'BRCA1'}

        with tempfile.TemporaryDirectory() as tmpdir:
            prefix_csv = os.path.join(tmpdir, 'prefixes.csv')
            with open(prefix_csv, 'w') as f:
                f.write('prefix,uri\n')
                f.write('dc,http://purl.org/dc/elements/1.1/\n')
                f.write('rdfs,http://www.w3.org/2000/01/rdf-schema#\n')
                f.write('edam,http://edamontology.org/\n')
                f.write('hgnc,https://identifiers.org/hgnc/\n')
                f.write('sh,http://www.w3.org/ns/shacl#\n')
                f.write('xsd,http://www.w3.org/2001/XMLSchema#\n')

            out = os.path.join(tmpdir, 'AOPWikiRDF.ttl')
            write_aop_rdf(out, entities, prefix_csv, config=config)
            content = open(out).read()
            assert 'rdfs:label\t"BRCA1"' in content
