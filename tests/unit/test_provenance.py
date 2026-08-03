"""Tests for release-identity derivation (issue #101).

The defect these guard against: a hard-coded ``pav:version`` that silently goes
stale. Every assertion here is about the version tracking its input, or being
omitted rather than guessed.
"""

import pytest

from aopwiki_rdf.provenance import (
    derive_dataset_version,
    resolve_source_commit,
    source_commit_url,
)


# --- derive_dataset_version ------------------------------------------------

def test_derive_dataset_version_from_standard_filename():
    assert derive_dataset_version("aop-wiki-xml-2026-08-01") == "2026.08.01"


def test_derive_dataset_version_tracks_the_snapshot():
    """Two different exports must not produce the same version."""
    a = derive_dataset_version("aop-wiki-xml-2026-08-01")
    b = derive_dataset_version("aop-wiki-xml-2026-07-25")
    assert a != b
    assert (a, b) == ("2026.08.01", "2026.07.25")


def test_derive_dataset_version_tolerates_surrounding_whitespace():
    assert derive_dataset_version("  aop-wiki-xml-2026-08-01  ") == "2026.08.01"


@pytest.mark.parametrize("bad", [
    "",
    None,
    "aop-wiki-xml",
    "aop-wiki-xml-2026-08",
    "aop-wiki-xml-26-08-01",
    "some-other-file-2026-08-01",
    "aop-wiki-xml-2026-08-01.gz",
])
def test_derive_dataset_version_returns_none_when_underivable(bad):
    """No version is honest; a wrong version is what caused issue #101."""
    assert derive_dataset_version(bad) is None


def test_derive_dataset_version_is_not_the_stale_literal():
    """Regression: the value must never again be the hard-coded '1.3'."""
    assert derive_dataset_version("aop-wiki-xml-2026-08-01") != "1.3"


# --- resolve_source_commit -------------------------------------------------

def test_resolve_source_commit_prefers_github_sha(monkeypatch):
    sha = "a" * 40
    monkeypatch.setenv("GITHUB_SHA", sha)
    assert resolve_source_commit() == sha


def test_resolve_source_commit_lowercases_github_sha(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "A1B2C3D4E5" + "0" * 30)
    assert resolve_source_commit() == "a1b2c3d4e5" + "0" * 30


def test_resolve_source_commit_ignores_malformed_github_sha(monkeypatch):
    """A short/branch-name GITHUB_SHA must fall through to git, not be emitted."""
    monkeypatch.setenv("GITHUB_SHA", "refs/heads/master")
    result = resolve_source_commit()
    assert result != "refs/heads/master"
    assert result is None or len(result) == 40


def test_resolve_source_commit_returns_sha_or_none(monkeypatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    result = resolve_source_commit()
    assert result is None or (len(result) == 40 and result.islower())


# --- source_commit_url -----------------------------------------------------

def test_source_commit_url_builds_github_url():
    sha = "b" * 40
    assert source_commit_url(sha) == (
        f"https://github.com/marvinm2/AOPWikiRDF/commit/{sha}"
    )


def test_source_commit_url_passes_none_through():
    """An unknown commit must yield no triple, not a URL ending in 'None'."""
    assert source_commit_url(None) is None
