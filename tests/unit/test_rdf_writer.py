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
