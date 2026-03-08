"""Tests for SHACL validation GitHub Actions workflow structure."""

import os

import yaml

WORKFLOW_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".github",
    "workflows",
    "shacl-validation.yml",
)


def _load_workflow():
    with open(WORKFLOW_PATH) as f:
        wf = yaml.safe_load(f)
    # PyYAML parses 'on' as boolean True; normalize to string key
    if True in wf and "on" not in wf:
        wf["on"] = wf.pop(True)
    return wf


def test_workflow_file_exists():
    assert os.path.exists(WORKFLOW_PATH), "shacl-validation.yml must exist"


def test_workflow_has_workflow_run_trigger():
    wf = _load_workflow()
    assert "workflow_run" in wf["on"], "workflow_run trigger must be present"


def test_workflow_triggers_on_rdf_generation():
    wf = _load_workflow()
    workflows = wf["on"]["workflow_run"]["workflows"]
    assert "RDF Generation" in workflows, "Must trigger on RDF Generation workflow"


def test_workflow_has_timeout():
    wf = _load_workflow()
    job = list(wf["jobs"].values())[0]
    timeout = job.get("timeout-minutes", None)
    assert timeout is not None, "timeout-minutes must be set"
    assert timeout <= 30, f"timeout must be <= 30, got {timeout}"


def test_workflow_runs_validation_script():
    wf = _load_workflow()
    job = list(wf["jobs"].values())[0]
    steps = job["steps"]
    found = any(
        "run_shacl_validation.py" in str(step.get("run", ""))
        for step in steps
    )
    assert found, "Must run scripts/run_shacl_validation.py"


def test_workflow_uploads_artifacts():
    wf = _load_workflow()
    job = list(wf["jobs"].values())[0]
    steps = job["steps"]
    found = any(
        "upload-artifact" in str(step.get("uses", ""))
        for step in steps
    )
    assert found, "Must have an upload-artifact step"


def test_workflow_has_manual_dispatch():
    wf = _load_workflow()
    assert "workflow_dispatch" in wf["on"], "workflow_dispatch trigger must be present"
