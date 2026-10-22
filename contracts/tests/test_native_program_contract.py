"""Schema and data-only semantic conformance vectors; never import candidate bytes.

JSON Schema handles closed wire shapes. The small reference checks below specify
cross-file/hash/identity obligations for producer and consumer integration tests;
they are NOT a production validator or evidence of deployed enforcement.
"""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema
import copy
import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest
import rfc8785
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = authored_schema()
MODEL_SCHEMA = authored_schema()
PROTOCOL = "hyprn_mvp.openmdao.program/1"


def uid(n):
    return str(UUID(int=n))


def raw_hash(value):
    return hashlib.sha256(value).hexdigest()


def digest(value):
    return raw_hash(rfc8785.dumps(value))


def validate(kind, value, schema=SCHEMA):
    Draft202012Validator({**schema, "$ref": "#/$defs/" + kind},
                         format_checker=FormatChecker()).validate(value)


def content_digest(artifact):
    return digest(dict(protocol=artifact["entrypoint"]["protocol"],
                       model_digest=artifact["model_digest"],
                       configuration_digest=artifact["configuration_digest"],
                       generator_identity=artifact["generator_identity"],
                       files=sorted([{k: f[k] for k in ("path", "size", "sha256")}
                                     for f in artifact["files"]
                                     if f["path"].startswith("generated/")],
                                    key=lambda f: f["path"])))


def seal(artifact, files):
    artifact["files"] = [dict(file_id=uid(100 + i), path=p, size=len(b),
                              sha256=raw_hash(b), media_type="application/json" if p.endswith(".json") else
                              "text/x-python" if p.endswith(".py") else "text/plain",
                              role="source" if p.startswith("sources/") else
                              "license" if p.startswith("licenses/") else
                              "provenance" if p.startswith("provenance/") else
                              "generated" if p.startswith("generated/") else "model")
                         for i, (p, b) in enumerate(sorted(files.items()))]
    artifact["executable_content_digest"] = content_digest(artifact)
    artifact["prepared_digest"] = digest({k: v for k, v in artifact.items() if k != "prepared_digest"})


def fixture():
    source = b"\xef\xbb\xbfoutputs['y'] = inputs['_x'] * 2\r\n# caf\xc3\xa9"
    sha = raw_hash(source)
    sp = "sources/" + sha + ".py"
    target = dict(instance_id=uid(1), port_id=uid(2))
    bindings = dict(schema_version="1", inputs=[dict(target=target, path="comp.x", units="m", component_id=uid(3))],
                    outputs=[dict(target=dict(instance_id=uid(1), port_id=uid(4)), path="comp.y", units="m", component_id=uid(3))],
                    components=[dict(component_id=uid(3), instance_id=uid(1), path="comp")])
    source_map = dict(schema_version="1", transform_version="1", entries=[dict(instance_id=uid(1),
                      definition_version_id=uid(5), source_path=sp, source_sha256=sha,
                      generated_path="generated/component.py", generated_line_start=2,
                      generated_line_end=4, transforms=["utf8_bom_decode", "line_endings", "indent",
                                                        "source_symbol_view", "availability_observer"])])
    # Inert byte fixtures, deliberately never imported or run by this suite.
    files = {sp: source, "model.json": b"{}", "generated/component.py": b"# generated fixture\n# body\n# body\n# end\n",
             "generated/entry.py": b"# fixed factory byte fixture\n", "generated/support.py": b"# observation support\n",
             "generated/bindings.json": rfc8785.dumps(bindings), "generated/source-map.json": rfc8785.dumps(source_map),
             "provenance/generator.json": b'{"fixture":true}', "provenance/source.tar": b"source archive fixture",
             "licenses/author.txt": b"author notice", "licenses/generator.txt": b"template notice"}
    generator = dict(name="fixture-native-generator", version="2.1.1", source_commit="a" * 40,
                     source_archive_sha256=raw_hash(files["provenance/source.tar"]), generator_digest="b" * 64,
                     template_digest="c" * 64, adapter_version="1", adapter_digest="d" * 64,
                     provenance_path="provenance/generator.json")
    package = dict(schema_version="1", source_service="fixture://modeling", model_id=uid(6), model_revision_id=uid(7),
                   revisions=[], files=[], required_capabilities=["flat_explicit_scalar"], license_notices=["author notice"], digest="e" * 64)
    artifact = dict(schema_version="2", preparation_id=uid(8), model_id=uid(6), model_revision_id=uid(7),
                    model_digest="f" * 64, configuration_revision_id=uid(9), configuration_digest="1" * 64,
                    required_capabilities=["flat_explicit_scalar"], generator_identity=generator,
                    dependency_requirements=[dict(name="openmdao", version="3.45.1")], model_package_manifest=package,
                    entrypoint=dict(protocol=PROTOCOL, module_path="generated/entry.py", factory="build_model",
                                    bindings_path="generated/bindings.json", source_map_path="generated/source-map.json"),
                    result_protocol_version="1", license_notices=[dict(kind="model_author", path="licenses/author.txt"),
                                                                  dict(kind="generated_code", path="licenses/generator.txt")])
    seal(artifact, files)
    return artifact, files


def check_program(artifact, files, expected_digest):
    """Reference semantic checks after shape validation, without executing code.

    Full model ancestry/configuration compatibility is intentionally still owned
    by existing model validation and the later production consumer, not this
    small program-format oracle.
    """
    validate("PreparedModelArtifact3" if artifact["schema_version"] == "3" else "PreparedModelArtifact", artifact)
    assert artifact["prepared_digest"] == expected_digest == digest({k: v for k, v in artifact.items() if k != "prepared_digest"})
    descriptors = artifact["files"]
    assert len({f["file_id"] for f in descriptors}) == len(descriptors)
    assert [f["path"] for f in descriptors] == sorted(files)
    assert sum(f["size"] for f in descriptors) <= 32 * 1024 * 1024
    for f in descriptors:
        assert len(files[f["path"]]) == f["size"] and raw_hash(files[f["path"]]) == f["sha256"]
    assert artifact["executable_content_digest"] == content_digest(artifact)
    entry = artifact["entrypoint"]
    for key in ("module_path", "bindings_path", "source_map_path"):
        assert entry[key] in files
    assert artifact["generator_identity"]["provenance_path"] in files
    for notice in artifact["license_notices"]:
        assert notice["path"] in files
    bindings = json.loads(files[entry["bindings_path"]])
    validate("ProgramBindings", bindings)
    components = bindings["components"]
    for key in ("component_id", "instance_id", "path"):
        assert len({c[key] for c in components}) == len(components)
    lookup = {c["component_id"]: c for c in components}
    rows = bindings["inputs"] + bindings["outputs"]
    assert len({(r["target"]["instance_id"], r["target"]["port_id"]) for r in rows}) == len(rows)
    assert len({r["path"] for r in rows}) == len(rows)
    for row in rows:
        component = lookup[row["component_id"]]
        assert row["target"]["instance_id"] == component["instance_id"]
        assert row["path"].rsplit(".", 1)[0] == component["path"]
    source_map = json.loads(files[entry["source_map_path"]])
    validate("ProgramSourceMap", source_map)
    assert {e["instance_id"] for e in source_map["entries"]} == {c["instance_id"] for c in components}
    for e in source_map["entries"]:
        assert e["source_path"] in files and e["generated_path"] in files
        assert raw_hash(files[e["source_path"]]) == e["source_sha256"]
        assert e["generated_line_start"] <= e["generated_line_end"] <= len(files[e["generated_path"]].splitlines())


def bundle(artifact, files):
    result = dict(schema_version="2", bundle_id=uid(20), run_id=uid(21), prepared_digest=artifact["prepared_digest"],
                  **{k: artifact[k] for k in ("model_revision_id", "configuration_revision_id", "model_digest", "configuration_digest",
                                              "entrypoint", "executable_content_digest", "required_capabilities", "result_protocol_version")},
                  generator=artifact["generator_identity"], files=[{k: v for k, v in f.items() if k != "file_id"} for f in artifact["files"]],
                  dependencies=[dict(name="openmdao", version="3.45.1", lock_path="locks/runtime.json")],
                  runtime=dict(image_digest="sha256:" + "2" * 64, architecture="linux/arm64", python_version="3.12.15",
                               worker_entrypoint="hyprn_mvp_integration.worker", policy_digest="3" * 64),
                  licenses=[*artifact["license_notices"], dict(kind="runtime", path="licenses/runtime.txt")])
    result["bundle_digest"] = digest(result)
    return result


def test_closed_new_and_explicit_historical_versions():
    artifact, files = fixture()
    validate("PreparedModelArtifact", artifact)
    validate("ExecutionBundle", bundle(artifact, files))
    check_program(artifact, files, artifact["prepared_digest"])
    old = copy.deepcopy(artifact)
    old["schema_version"] = "1"
    for k in ("entrypoint", "executable_content_digest", "result_protocol_version"):
        del old[k]
    old["generator_identity"] = {k: old["generator_identity"][k] for k in ("name", "version", "source_commit", "template_digest")}
    old["license_notices"] = ["historical author notice"]
    old["files"] = [f for f in old["files"] if f["role"] != "provenance"]
    validate("HistoricalPreparedModelArtifactV1", old)
    validate("PreparedModelArtifactRead", old)
    validate("PreparedModelArtifactRead", artifact)
    with pytest.raises(ValidationError):
        validate("PreparedModelArtifact", old)
    previous_bundle = bundle(artifact, files)
    previous_bundle["schema_version"] = "1"
    for k in ("entrypoint", "executable_content_digest"):
        del previous_bundle[k]
    previous_bundle["generator"] = old["generator_identity"]
    previous_bundle["licenses"] = ["licenses/model-notices.json"]
    validate("HistoricalExecutionBundleV1", previous_bundle)
    validate("ExecutionBundleRead", previous_bundle)
    with pytest.raises(ValidationError):
        validate("ExecutionBundle", previous_bundle)


@pytest.mark.parametrize("kind", ["PreparedModelArtifact", "ExecutionBundle", "ProgramBindings", "ProgramSourceMap"])
def test_unknown_versions_and_fields_are_rejected(kind):
    artifact, files = fixture()
    value = {"PreparedModelArtifact": artifact, "ExecutionBundle": bundle(artifact, files),
             "ProgramBindings": json.loads(files["generated/bindings.json"]),
             "ProgramSourceMap": json.loads(files["generated/source-map.json"])}[kind]
    validate(kind, value)
    with pytest.raises(ValidationError):
        validate(kind, {**value, "schema_version": "99"})
    with pytest.raises(ValidationError):
        validate(kind, {**value, "native_options": {}})


@pytest.mark.parametrize("change", [dict(protocol="hyprn_mvp.openmdao.program/2"), dict(factory="eval('x')"),
                                     dict(factory="other"), dict(options={}), dict(module_path="sources/body.py")])
def test_entrypoint_is_a_fixed_closed_protocol(change):
    artifact, _ = fixture()
    with pytest.raises(ValidationError):
        validate("ProgramEntrypoint", {**artifact["entrypoint"], **change})


@pytest.mark.parametrize("path", ["/generated/x.py", "generated/../x.py", "generated/./x.py", "generated//x.py",
                                   "generated/x.py/", "generated/\\x.py", "generated/x.py\n", "generated/" + "a/" * 16 + "x.py",
                                   "generated/" + "x" * 513])
def test_non_regular_or_unbounded_relative_paths_rejected(path):
    artifact, _ = fixture()
    with pytest.raises(ValidationError):
        validate("ProgramEntrypoint", {**artifact["entrypoint"], "module_path": path})
    descriptor = {**artifact["files"][0], "path": path}
    with pytest.raises(ValidationError):
        validate("PreparedFileV2", descriptor)


@pytest.mark.parametrize("field", ["symlink", "hardlink", "device", "mode", "native_id"])
def test_file_descriptor_cannot_authorize_special_entries(field):
    artifact, _ = fixture()
    with pytest.raises(ValidationError):
        validate("PreparedFileV2", {**artifact["files"][0], field: "escape"})


@pytest.mark.parametrize("mutation", ["raw", "size", "duplicate_path", "duplicate_id", "undeclared_support", "missing_entry", "missing_provenance", "digest", "config", "generator"])
def test_file_and_manifest_integrity(mutation):
    artifact, files = fixture()
    check_program(artifact, files, artifact["prepared_digest"])
    expected = artifact["prepared_digest"]
    if mutation == "raw": files["generated/support.py"] += b"# tamper"
    elif mutation == "size": artifact["files"][0]["size"] += 1
    elif mutation == "duplicate_path": artifact["files"].append({**artifact["files"][0], "file_id": uid(999)})
    elif mutation == "duplicate_id": artifact["files"][1]["file_id"] = artifact["files"][0]["file_id"]
    elif mutation == "undeclared_support": files["generated/extra.py"] = b"# extra"
    elif mutation == "missing_entry": del files[artifact["entrypoint"]["module_path"]]; seal(artifact, files)
    elif mutation == "missing_provenance": del files[artifact["generator_identity"]["provenance_path"]]; seal(artifact, files)
    elif mutation == "digest": artifact["executable_content_digest"] = "0" * 64
    elif mutation == "config": artifact["configuration_digest"] = "0" * 64
    elif mutation == "generator": artifact["generator_identity"]["adapter_digest"] = "0" * 64
    # Even a newly rehashed manifest cannot replace the independently retained pin.
    with pytest.raises((AssertionError, ValidationError)):
        check_program(artifact, files, expected)
    if mutation in ("duplicate_path", "duplicate_id", "missing_entry", "missing_provenance", "digest"):
        artifact["prepared_digest"] = digest({k: v for k, v in artifact.items() if k != "prepared_digest"})
        with pytest.raises((AssertionError, ValidationError)):
            check_program(artifact, files, artifact["prepared_digest"])


@pytest.mark.parametrize("mutation", ["target", "path", "component", "owner", "graph", "native_options"])
def test_bindings_reject_duplicate_or_unowned_observations(mutation):
    artifact, files = fixture()
    check_program(artifact, files, artifact["prepared_digest"])
    bindings = json.loads(files["generated/bindings.json"])
    if mutation == "target": bindings["inputs"].append({**bindings["inputs"][0], "path": "comp.other"})
    elif mutation == "path": bindings["outputs"][0]["path"] = bindings["inputs"][0]["path"]
    elif mutation == "component": bindings["components"].append({**bindings["components"][0], "path": "other"})
    elif mutation == "owner": bindings["inputs"][0]["target"]["instance_id"] = uid(999)
    else: bindings[mutation] = {}
    files["generated/bindings.json"] = rfc8785.dumps(bindings)
    seal(artifact, files)
    with pytest.raises((AssertionError, ValidationError)):
        check_program(artifact, files, artifact["prepared_digest"])


@pytest.mark.parametrize("change", [dict(source_path="../x"), dict(source_sha256="0" * 64),
                                    dict(generated_path="generated/missing.py"), dict(generated_line_start=0),
                                    dict(generated_line_start=5), dict(generated_line_end=99),
                                    dict(transforms=["arbitrary_exec"]), dict(native_sql_id=1), dict(instance_id=uid(999))])
def test_source_map_rejects_malformed_or_unbound_rows(change):
    artifact, files = fixture()
    check_program(artifact, files, artifact["prepared_digest"])
    source_map = json.loads(files["generated/source-map.json"])
    source_map["entries"][0].update(change)
    files["generated/source-map.json"] = rfc8785.dumps(source_map)
    seal(artifact, files)
    with pytest.raises((AssertionError, ValidationError)):
        check_program(artifact, files, artifact["prepared_digest"])


def test_digest_vectors_and_receipt_independence():
    artifact, files = fixture()
    # These fixed vectors bind raw UTF-8/BOM/CRLF and RFC8785 canonical bytes.
    assert raw_hash(files[next(p for p in files if p.startswith("sources/"))]) == "888dc46ae17f2ee56e7fed2acd2708faaa9f180a9183d59cf7102dbb0301902d"
    assert artifact["executable_content_digest"] == "cd03923ae01b944b8ea421fb040dd4a8e5d23e07579e97f08f0fdace9df0e6db"
    assert artifact["prepared_digest"] == "310b64ddebf0cad72f9f28bbe517e5f37f900c5a1347dbe87464f52bff6510ca"
    other = copy.deepcopy(artifact)
    other["preparation_id"] = uid(987)
    other["files"][0]["file_id"] = uid(988)
    assert content_digest(other) == artifact["executable_content_digest"]
    assert digest({k: v for k, v in other.items() if k != "prepared_digest"}) != artifact["prepared_digest"]
    assert rfc8785.dumps([1.0, -0.0, 1e-7, 1e20]) == b'[1,0,1e-7,100000000000000000000]'


def test_capabilities_advertise_only_supported_execution_versions():
    versions = dict(artifact_versions=["2"], bundle_versions=["2"], program_protocols=[PROTOCOL],
                    historical_artifact_versions=["1"], historical_bundle_versions=["1"])
    validate("ExecutionVersions", versions, MODEL_SCHEMA)
    for key in versions:
        with pytest.raises(ValidationError):
            validate("ExecutionVersions", {**versions, key: ["99"]}, MODEL_SCHEMA)
    with pytest.raises(ValidationError):
        validate("ExecutionVersions", {**versions, "artifact_versions": ["1", "2"]}, MODEL_SCHEMA)
    assert "execution_versions" in MODEL_SCHEMA["$defs"]["Capabilities"]["required"]


def test_models_http_and_portable_ancestry_keep_major_one():
    assert_execution_schema()
    for schema in (SCHEMA, MODEL_SCHEMA):
        Draft202012Validator.check_schema(schema)
        # Versioned unions keep their major-one branch; later versions are added beside it.
        for name in ("ModelDraft", "ModelRevision", "ModelPackage", "ConfigurationRevision"):
            assert {"$ref": "#/$defs/" + name + "1"} in schema["$defs"][name]["oneOf"]
            assert schema["$defs"][name + "1"]["properties"]["schema_version"] == {"enum": ["1"]}
        assert schema["$defs"]["PreparedModelArtifactResponse"]["properties"]["schema_version"] == {"enum": ["1"]}
    spec = json.loads((ROOT / "contracts/modeling.openapi.yaml").read_text())
    assert spec["openapi"] == "3.1.0"
    assert spec["paths"]["/models/{model_id}/prepare-execution"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PreparedModelArtifactResponse4")


def test_provenance_inventory_is_closed_and_separates_original_from_patched():
    artifact, files = fixture()
    def inventory(path, role):
        return dict(path=path, role=role, size=len(files[path]), sha256=raw_hash(files[path]))
    provenance = dict(schema_version="1", source_commit=artifact["generator_identity"]["source_commit"],
                      source_archive=inventory("provenance/source.tar", "source_archive"),
                      upstream_files=[dict(path="templates/component.erb", size=20, sha256="a" * 64, role="template")],
                      patched_files=[dict(path="templates/component.erb", size=21, sha256="b" * 64, role="template")],
                      applied_patches=[dict(path="patches/static.patch", size=8, sha256="c" * 64, role="patch")],
                      adapter_version="1", adapter_source=dict(path="adapter.rb", size=32, sha256="d" * 64, role="adapter"),
                      runtime_lock=dict(path="Gemfile.lock", size=128, sha256="e" * 64, role="runtime_lock"),
                      deterministic_settings=dict(ordering="topological_uuid", scalar_mode="real_scalar",
                          nonlinear_solver="NonlinearRunOnce", linear_solver="LinearRunOnce", parallel=False,
                          derivatives="none", source_symbol_view="1", availability_observer="1"))
    validate("ProgramProvenance", provenance)
    for field in provenance:
        bad = copy.deepcopy(provenance)
        del bad[field]
        with pytest.raises(ValidationError):
            validate("ProgramProvenance", bad)
    for change in (dict(native_options={}), dict(parallel=True), dict(derivatives="analytic")):
        bad = copy.deepcopy(provenance)
        bad["deterministic_settings"].update(change)
        with pytest.raises(ValidationError):
            validate("ProgramProvenance", bad)
    for key in ("source_archive", "adapter_source", "runtime_lock"):
        bad = copy.deepcopy(provenance)
        bad[key]["sha256"] = "not-a-hash"
        with pytest.raises(ValidationError):
            validate("ProgramProvenance", bad)


def test_notice_sets_and_generator_fields_cannot_be_dropped_or_conflated():
    artifact, files = fixture()
    validate("NativeGeneratorIdentity", artifact["generator_identity"])
    for field in artifact["generator_identity"]:
        bad = copy.deepcopy(artifact["generator_identity"])
        del bad[field]
        with pytest.raises(ValidationError):
            validate("NativeGeneratorIdentity", bad)
    for kind in ("model_author", "generated_code"):
        validate("PreparedLicenseNotice", dict(kind=kind, path="licenses/notice.txt"))
    with pytest.raises(ValidationError):
        validate("PreparedLicenseNotice", dict(kind="runtime", path="licenses/runtime.txt"))
    validate("BundleLicenseNotice", dict(kind="runtime", path="licenses/runtime.txt"))
    with pytest.raises(ValidationError):
        validate("BundleLicenseNotice", "license name without retained bytes")
    for kind in ("PreparedModelArtifactRead", "ExecutionBundleRead"):
        value = artifact if kind == "PreparedModelArtifactRead" else bundle(artifact, files)
        with pytest.raises(ValidationError):
            validate(kind, {**value, "schema_version": "99"})
    for field in ("source_archive_sha256", "generator_digest", "template_digest", "adapter_digest"):
        changed = copy.deepcopy(artifact)
        changed["generator_identity"][field] = "0" * 64
        assert content_digest(changed) != artifact["executable_content_digest"]


def test_http_envelopes_allow_historical_replay_without_active_version_fallback():
    artifact, _ = fixture()
    envelope = dict(schema_version="1", request_id=uid(300), data=artifact)
    validate("PreparedModelArtifactResponse", envelope, MODEL_SCHEMA)
    receipt = dict(state="committed", command_id=uid(301), payload_digest="0" * 64,
                   response=dict(data=artifact), status=200)
    validate("Receipt", receipt, MODEL_SCHEMA)
    versions = dict(artifact_versions=["2"], bundle_versions=["2"], program_protocols=[PROTOCOL],
                    historical_artifact_versions=["1"], historical_bundle_versions=["1"])
    cap = dict(contract_versions=["1"], schema_versions=["1"], service_build="fixture",
               generator_identity=artifact["generator_identity"], execution_versions=versions,
               capabilities=[dict(id="flat_explicit_scalar", version="1", supported=True,
                                  limits=dict(json_bytes=2097152, source_bytes=262144, edits=256, elements=1000, depth=16))],
               unit_compatibility=dict(engine="OpenMDAO", version="3.45.1", supported_units=["", "m"], affine_conversion=False))
    validate("CapabilitiesResponse", dict(schema_version="1", request_id=uid(302), data=cap), MODEL_SCHEMA)
    for value in ("1", "99"):
        with pytest.raises(ValidationError):
            validate("PreparedModelArtifact", {**artifact, "schema_version": value})


def test_typed_future_numerical_extensions_remain_closed():
    from test_modeling_contract import numerical
    current = numerical()
    validate("Numerical", current)
    for change in (dict(native_options={}), dict(optimizer=dict(family="unknown")),
                   dict(derivatives=dict(method="eval", form=None, check=None))):
        with pytest.raises(ValidationError):
            validate("Numerical", {**current, **change})
