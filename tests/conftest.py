"""Shared pytest fixtures for AOP-Wiki RDF tests."""

import os
import pytest


@pytest.fixture
def sample_xml_path():
    """Return path to the sample AOP-Wiki XML fixture."""
    return os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_aopwiki.xml')
