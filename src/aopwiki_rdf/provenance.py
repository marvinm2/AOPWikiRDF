"""Release identity for the generated dataset.

Two distinct things get versioned in this repo and conflating them is what
produced the six-year-stale ``pav:version "1.3"`` in the served RDF:

* the **dataset** -- a weekly snapshot, identified by the AOP-Wiki XML export it
  was built from. This is what ``pav:version`` describes.
* the **software** -- this repository, identified by git tag and CITATION.cff.
  This is what ``pav:createdWith`` points at, via the generating commit.

The dataset version is therefore *derived* from the XML filename rather than
hard-coded, so it cannot drift out of date again. It uses the same calendar
scheme as CITATION.cff, extended to the day because releases are weekly.
"""

import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

REPO_URL = "https://github.com/marvinm2/AOPWikiRDF"

# ``aop-wiki-xml-2026-08-01`` -> ``2026-08-01``. Anchored so a stray date
# elsewhere in the filename cannot be picked up instead.
_XML_DATE_PATTERN = re.compile(r"^aop-wiki-xml-(\d{4})-(\d{2})-(\d{2})$")

_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def derive_dataset_version(aopwikixmlfilename: str) -> str | None:
    """Return the calendar dataset version for an AOP-Wiki XML export.

    ``aop-wiki-xml-2026-08-01`` yields ``"2026.08.01"``.

    Returns ``None`` when the filename does not carry a parseable date, so the
    caller can omit ``pav:version`` entirely rather than assert a wrong one --
    no version is honest, a stale version is not.
    """
    if not aopwikixmlfilename:
        return None

    match = _XML_DATE_PATTERN.match(aopwikixmlfilename.strip())
    if not match:
        logger.warning(
            "Cannot derive dataset version: XML filename %r does not match the "
            "expected aop-wiki-xml-YYYY-MM-DD form; pav:version will be omitted",
            aopwikixmlfilename,
        )
        return None

    return ".".join(match.groups())


def resolve_source_commit() -> str | None:
    """Return the 40-char commit SHA this run was generated from, if knowable.

    Prefers ``GITHUB_SHA`` (set by Actions, and correct even when the runner
    checks out a detached merge commit), falling back to ``git rev-parse`` for
    local runs. Returns ``None`` outside a checkout -- an absent commit triple
    is better than a fabricated one.
    """
    env_sha = os.environ.get("GITHUB_SHA", "").strip().lower()
    if _SHA_PATTERN.match(env_sha):
        return env_sha

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("git rev-parse unavailable (%s); omitting source commit", e)
        return None

    if result.returncode != 0:
        logger.debug(
            "git rev-parse failed (%s); omitting source commit",
            result.stderr.strip(),
        )
        return None

    sha = result.stdout.strip().lower()
    return sha if _SHA_PATTERN.match(sha) else None


def source_commit_url(sha: str | None) -> str | None:
    """Return the GitHub commit URL for ``sha``, or ``None`` if there is none."""
    return f"{REPO_URL}/commit/{sha}" if sha else None


def release_metadata(aopwikixmlfilename: str) -> dict:
    """Return the VoID release-identity fields for this run.

    Bundles the dataset version and the generating commit so the orchestrator
    stays a wiring layer -- deciding what identifies a release belongs here, not
    in the pipeline. Either value may be ``None``, in which case the writer
    omits the corresponding triple.
    """
    metadata = {
        "dataset_version": derive_dataset_version(aopwikixmlfilename),
        "source_commit_url": source_commit_url(resolve_source_commit()),
    }
    logger.info(
        "Dataset version %s, generated from commit %s",
        metadata["dataset_version"] or "<underivable>",
        metadata["source_commit_url"] or "<unknown>",
    )
    return metadata
