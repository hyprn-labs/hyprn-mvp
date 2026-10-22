"""One exact original-source native proof, and its strictly read-only recovery."""
# P2 live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, live docker names, live entry points and foreign signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
live_runtime_fence = live_fence.pytest_fixture('baseline')
import base64
import json
import math

import findings_native_fixture as fixture


def assert_science(proof):
    source, detail = proof["source"], proof["downstream"]
    history = detail["history"]
    assert source["run_id"] == fixture.ORIGINAL.source_run
    assert history["history_schema_version"] == "4" and history["errors"] == []
    assert source["history"]["configuration"]["approach_binding"] is None
    pin = history["configuration"]["approach_binding"]
    assert pin == proof["saved"]["configuration"]["approach_binding"]
    assert pin["approach_version_id"] == proof["version"]["version"]["approach_version_id"]
    assert history["configuration"]["model_revision_id"] == fixture.ORIGINAL.downstream_revision
    value = history["configuration"]["inputs"][0]
    binding = value["result_binding"]
    assert binding["source_run_id"] == fixture.ORIGINAL.source_run
    assert binding["results_digest"] == source["retained_integrity"]["results_digest"] == fixture.ORIGINAL.source_results_digest
    assert binding["original_value"] == 1 and binding["original_units"] == "MJ/kg"
    assert value["value"] == 1 and value["units"] == "MJ/kg"
    assert binding["conversion"]["factor"] == 1000000
    assert binding["conversion"]["destination_value"] == 1000000
    assert binding["conversion"]["destination_units"] == "J/kg"
    for detail, expected, criteria in [(source, 3, ["met"]*4+["violated"]), (detail, 1, ["met"]*2)]:
        results = detail["history"]["results"]
        assert results["execution"]["state"] == "finished" and results["execution"]["exit_code"] == 0
        assert results["convergence"] == {"state":"not_applicable","diagnostics_ref":None}
        assert results["optimization"] == {"termination":"not_applicable","feasibility":"not_applicable"}
        assert results["completeness"] == dict(expected=expected, available=expected, failed=0, unavailable=0)
        assert results["applicability"] == {"state":"unassessed","evidence_refs":[]}
        assert sorted(c["outcome"] for c in results["criteria"]) == criteria
        assert detail["retained_integrity"]["results_digest"]
    assert next(c for c in source["history"]["results"]["criteria"] if c["criterion_id"] == fixture.ORIGINAL.violated_criterion)["outcome"] == "violated"
    output = history["results"]["outputs"][0]
    assert output["units"] == "J/kg" and output["assigned"] and output["producer_completed"]
    assert math.isclose(output["value"], 1000000, rel_tol=1e-12, abs_tol=1e-9)
    assert proof["process_count"] == 8 and proof["uncached"] and proof["source_result_link"]
    assert proof["prepared_process_count"] == 7 and proof["inert_canary"]
    bundle = proof["payload"]["bundle"]
    assert bundle["manifest"]["schema_version"] == "6"
    assert proof["payload"]["frozen"]["schema_version"] == "5"
    files = {p:base64.b64decode(raw) for p,raw in bundle["files"].items()}
    prepared = json.loads(files["preparation.json"])
    assert prepared["entrypoint"]["protocol"] == "hyprn_mvp.openmdao.program/1"
    assert any(p.startswith("generated/base/") for p in files)
    assert "app/lib/whats_opt/openmdao_generator.rb" in files["provenance/generator.json"].decode()
    for row in bundle["manifest"]["files"]:
        assert fixture.sha(files[row["path"]]) == row["sha256"]
    for row in prepared["files"]:
        assert fixture.sha(files[row["path"]]) == row["sha256"]
    assert proof["browser"]["online"]["tests"] == proof["browser"]["offline"]["tests"] == 1
    assert proof["browser"]["scientific_rows_unchanged"] and proof["browser"]["model_stopped"]
    assert proof["preservation"]["passed"]


def test_new_downstream_run_pins_retained_source_and_approach():
    with fixture.NativeContinuation(*fixture.ACTIVE) as journey:
        proof = journey.execute_once()
        assert_science(proof)


def test_recorded_findings_read_only():
    with fixture.read_only_veto():
        with fixture.NativeContinuation(*fixture.ACTIVE, read_only=True) as journey:
            proof = journey.read_recorded()
            assert_science(proof)
