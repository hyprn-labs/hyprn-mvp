"""Documents 25.1 structural wire tests, not runtime/native qualification."""
from hyprn_mvp_app.contracts import authored_schema
from test_schema_sources import assert_execution_schema
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = [authored_schema()]
S = SCHEMAS[0]
ID = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
HASH = "a" * 64
BEGIN = dict(command_id=ID, filename="pressure.txt", media_type="text/plain",
             byte_length=6, sha256=HASH)
SPAN = dict(kind="extracted_span", extraction_id=ID, artifact_id=OTHER,
            artifact_sha256=HASH, start=1, end=2)
BASELINE = [{'id': 'https://hyprn-mvp.local/contracts/model.schema.json', 'names': ['Source', 'PortDeclaration', 'Port', 'PortRef', 'BatchPortRef', 'VersionRef', 'Annotation', 'BoundaryMapping', 'Instance', 'Connection', 'Definition', 'DefinitionChange', 'Edit1', 'ModelDraft1', 'ModelRevision1', 'File', 'Generator', 'ModelPackage1', 'Scaling', 'Numerical', 'Input', 'Criterion', 'EvidenceSnapshotLegacy', 'ConfigurationCandidate', 'ConfigurationRevision', 'Diagnostic', 'CompatibilityResult', 'PreparedModelArtifact', 'Error', 'Create', 'Apply1', 'Preview1', 'Commit', 'Validate', 'Compatibility', 'Prepare', 'Import', 'ByteFile', 'CreatedIds', 'ValidationResult', 'Capabilities', 'CapabilitiesResponse', 'ModelDraftResponse', 'ModelDraftEditResponse', 'ModelRevisionResponse', 'ValidationResultResponse', 'ModelPackageResponse', 'CompatibilityResultResponse', 'PreparedModelArtifactResponse', 'ByteFileResponse', 'Receipt', 'ReceiptResponse', 'ProgramEntrypoint', 'ProgramBinding', 'ProgramComponent', 'ProgramBindings', 'ProgramSourceMapEntry', 'ProgramSourceMap', 'NativeGeneratorIdentity', 'ProgramProvenanceFile', 'ProgramProvenance', 'PreparedFileV2', 'BundleFileV2', 'PreparedLicenseNotice', 'BundleLicenseNotice', 'HistoricalPreparedModelArtifactV1', 'PreparedModelArtifactRead', 'ExecutionBundle', 'HistoricalExecutionBundleV1', 'ExecutionBundleRead', 'ExecutionVersions', 'RevisionSummary', 'RevisionList', 'RevisionListResponse', 'EvidenceResourceRef1', 'EvidenceCreate1', 'EvidenceRecord1', 'EvidenceCreate2', 'EvidenceRecord2', 'EvidenceCreate', 'EvidenceRecord', 'ConfigurationCandidate1', 'ConfigurationRevision1', 'ExecutionBundle2', 'LiteralRequest', 'ResultRequest', 'ContextSource', 'DerivationRequest', 'ConfigurationRequest2', 'UnitInterpretation', 'SourceLabels', 'ResultBinding', 'ResolvedInput2', 'Change', 'ChangeSummary', 'Derivation', 'ModelingConfiguration2', 'ModelingConfigurationRevision2', 'ConfigurationCandidate2', 'ConfigurationRevision2', 'RuntimeComparison', 'ConfigurationPreview2', 'ConfigurationCommit2', 'ModifiedRunSeed1', 'NativeSource', 'ScalarMapping', 'ResultDependencies1', 'BundleFileV3', 'ExecutionBundle3', 'ResultSource', 'ResultSourcePage', 'RunLabel', 'ExportLimits', 'ReexecutionPrerequisites', 'RecordPreview', 'StoredError', 'RecordRequest', 'RecordPreviewRequest', 'RecordCreateRequest', 'ArchiveRun', 'ArchiveRecordRequest1', 'NodeInventory', 'LinkInventory', 'EntityInventory', 'RepositoryInventory', 'NativeInventory', 'ArchiveRecordResponse1', 'RunMapping', 'PayloadFile', 'ComputationalRecordManifest1', 'CompatibilityResult1', 'InputInterpretation2', 'CompatibilityResult2', 'Edit', 'ModelDraft', 'ModelRevision', 'ModelPackage', 'EvidenceSnapshot', 'Apply', 'Preview', 'EvidenceSnapshotRead', 'AssumptionEvidenceLink', 'AssumptionOwner', 'AssumptionBatchOwner', 'ConfigurationAssumption', 'ModelAssumption', 'ModelDraft2', 'ModelRevision2', 'ModelPackage2', 'Edit2', 'Preview2', 'Apply2', 'RecordedResourceLabel', 'RecordedEvidenceContext1', 'EvidenceCreate3', 'EvidenceRecord3', 'EvidenceRevise3', 'EvidenceSnapshot3', 'EvidenceRecordRead', 'EvidenceFamily3', 'AssumptionEvidenceResolutionLink', 'AssumptionEvidenceResolution1', 'ConfigurationContextOverride1', 'ConfigurationRequest3', 'ConfigurationCandidate3', 'ConfigurationRevision3', 'ModelingConfiguration3', 'ModelingConfigurationRevision3', 'ConfigurationPreview3', 'ConfigurationCommit3', 'ModifiedRunSeed2', 'ModifiedRunSeed', 'ExecutionBundle4', 'RetainedOutput', 'RetainedResults', 'HistoryArtifact', 'ConfigurationRevisionLegacyRead', 'RunHistory1', 'RunHistory2', 'RunHistory', 'PreparedModelArtifact2', 'EvidenceCursor1', 'EvidencePage1', 'ConfigurationCommit1', 'ApproachModelBinding1', 'ApproachElementRef1', 'ApproachEvidenceLink1', 'ApproachAssumption1', 'ApproachAssumptionOrigin1', 'ApproachAssumptionRef1', 'ApproachIntent1', 'ApproachStep1', 'ApproachCase1', 'ApproachBasisRef1', 'ApproachContent1', 'ApproachDraft1', 'ApproachVersion1', 'ApproachVersionSummary1', 'ApproachState1', 'ApproachSaved1', 'ApproachPreviewRequest1', 'ApproachDraftWrite1', 'ApproachVersionSave1', 'ApproachVersionSaved1', 'ApproachRestore1', 'ApproachCoverage1', 'ApproachRunContext1', 'ApproachResolution1', 'ApproachClosure1', 'ApproachIssue1', 'ApproachChange1', 'ApproachPreview1', 'ApproachCursor1', 'ApproachPageRequest1', 'ApproachVersionPage1', 'ApproachUsage1', 'ApproachUsageCursor1', 'ApproachUsageRequest1', 'ApproachUsagePage1', 'ApproachSelection1', 'ApproachBinding1', 'ConfigurationRequest4', 'ConfigurationCandidate4', 'ConfigurationRevision4', 'ConfigurationPreview4', 'ConfigurationCommit4', 'FrozenConfigurationLegacy', 'FrozenConfiguration4', 'FrozenConfiguration', 'BundleFileV5', 'ExecutionBundle5', 'RunHistory3', 'ModifiedRunSeed3', 'ApproachExportSummary1', 'RecordPreview2', 'RecordRequest2', 'RecordPreviewRead', 'RecordRequestRead', 'RecordRequestResponse', 'RecordStatusResponse', 'RecordReceiptResult', 'PayloadFile2', 'ApproachPayloadIndex1', 'ComputationalRecordManifest2', 'ComputationalRecordManifestRead', 'ApproachError1', 'ApproachCommandResult1', 'ApproachStateResponse1', 'ApproachPreviewResponse1', 'ApproachDraftResponse1', 'ApproachSavedResponse1', 'ApproachVersionSaveResponse1', 'ApproachVersionListResponse1', 'ApproachUsageResponse1', 'ApproachReceipt1', 'ApproachReceiptCategory1', 'ConfigurationRevisionPreApproach', 'UnitDeclaration1', 'PortDeclaration3', 'Port3', 'Definition3', 'DefinitionChange3', 'Edit3', 'ModelDraft3', 'ModelRevision3', 'ModelRevisionPreUnits', 'ApproachClosurePreUnits', 'ModelPackage3', 'Create3', 'CreateRequest', 'Preview3', 'Apply3', 'FrozenConfiguration5', 'ExecutionBundle6', 'RunHistory4', 'ModifiedRunSeed4', 'UnitCatalog1', 'UnitCatalogResponse1', 'DefinitionRead3', 'PortRead3', 'ApproachClosureWithModel3', 'FrozenConfiguration5Model3', 'FrozenConfiguration5Model2', 'RunHistory4Model3', 'RunHistory4Model2', 'ModifiedRunSeed4Model3', 'ModifiedRunSeed4Model2', 'ExecutionBundle6Model3', 'ExecutionBundle6Model2']}, {'id': 'https://hyprn-mvp.local/contracts/execution.schema.json', 'names': ['Source', 'PortDeclaration', 'Port', 'PortRef', 'BatchPortRef', 'VersionRef', 'Annotation', 'BoundaryMapping', 'Instance', 'Connection', 'Definition', 'DefinitionChange', 'Edit1', 'ModelDraft1', 'ModelRevision1', 'File', 'Generator', 'ModelPackage1', 'Scaling', 'Numerical', 'Input', 'Criterion', 'EvidenceSnapshotLegacy', 'ConfigurationCandidate', 'ConfigurationRevision', 'Diagnostic', 'CompatibilityResult', 'PreparedModelArtifact', 'Error', 'Create', 'Apply1', 'Preview1', 'Commit', 'Validate', 'Compatibility', 'Prepare', 'Import', 'ByteFile', 'CreatedIds', 'ValidationResult', 'Capabilities', 'CapabilitiesResponse', 'ModelDraftResponse', 'ModelDraftEditResponse', 'ModelRevisionResponse', 'ValidationResultResponse', 'ModelPackageResponse', 'CompatibilityResultResponse', 'PreparedModelArtifactResponse', 'ByteFileResponse', 'Receipt', 'ReceiptResponse', 'ProgramEntrypoint', 'ProgramBinding', 'ProgramComponent', 'ProgramBindings', 'ProgramSourceMapEntry', 'ProgramSourceMap', 'NativeGeneratorIdentity', 'ProgramProvenanceFile', 'ProgramProvenance', 'PreparedFileV2', 'BundleFileV2', 'PreparedLicenseNotice', 'BundleLicenseNotice', 'HistoricalPreparedModelArtifactV1', 'PreparedModelArtifactRead', 'ExecutionBundle', 'HistoricalExecutionBundleV1', 'ExecutionBundleRead', 'ExecutionVersions', 'RevisionSummary', 'RevisionList', 'RevisionListResponse', 'EvidenceResourceRef1', 'EvidenceCreate1', 'EvidenceRecord1', 'EvidenceCreate2', 'EvidenceRecord2', 'EvidenceCreate', 'EvidenceRecord', 'ConfigurationCandidate1', 'ConfigurationRevision1', 'ExecutionBundle2', 'LiteralRequest', 'ResultRequest', 'ContextSource', 'DerivationRequest', 'ConfigurationRequest2', 'UnitInterpretation', 'SourceLabels', 'ResultBinding', 'ResolvedInput2', 'Change', 'ChangeSummary', 'Derivation', 'ModelingConfiguration2', 'ModelingConfigurationRevision2', 'ConfigurationCandidate2', 'ConfigurationRevision2', 'RuntimeComparison', 'ConfigurationPreview2', 'ConfigurationCommit2', 'ModifiedRunSeed1', 'NativeSource', 'ScalarMapping', 'ResultDependencies1', 'BundleFileV3', 'ExecutionBundle3', 'ResultSource', 'ResultSourcePage', 'RunLabel', 'ExportLimits', 'ReexecutionPrerequisites', 'RecordPreview', 'StoredError', 'RecordRequest', 'RecordPreviewRequest', 'RecordCreateRequest', 'ArchiveRun', 'ArchiveRecordRequest1', 'NodeInventory', 'LinkInventory', 'EntityInventory', 'RepositoryInventory', 'NativeInventory', 'ArchiveRecordResponse1', 'RunMapping', 'PayloadFile', 'ComputationalRecordManifest1', 'CompatibilityResult1', 'InputInterpretation2', 'CompatibilityResult2', 'Edit', 'ModelDraft', 'ModelRevision', 'ModelPackage', 'EvidenceSnapshot', 'Apply', 'Preview', 'EvidenceSnapshotRead', 'AssumptionEvidenceLink', 'AssumptionOwner', 'AssumptionBatchOwner', 'ConfigurationAssumption', 'ModelAssumption', 'ModelDraft2', 'ModelRevision2', 'ModelPackage2', 'Edit2', 'Preview2', 'Apply2', 'RecordedResourceLabel', 'RecordedEvidenceContext1', 'EvidenceCreate3', 'EvidenceRecord3', 'EvidenceRevise3', 'EvidenceSnapshot3', 'EvidenceRecordRead', 'EvidenceFamily3', 'AssumptionEvidenceResolutionLink', 'AssumptionEvidenceResolution1', 'ConfigurationContextOverride1', 'ConfigurationRequest3', 'ConfigurationCandidate3', 'ConfigurationRevision3', 'ModelingConfiguration3', 'ModelingConfigurationRevision3', 'ConfigurationPreview3', 'ConfigurationCommit3', 'ModifiedRunSeed2', 'ModifiedRunSeed', 'ExecutionBundle4', 'RetainedOutput', 'RetainedResults', 'HistoryArtifact', 'ConfigurationRevisionLegacyRead', 'RunHistory1', 'RunHistory2', 'RunHistory', 'PreparedModelArtifact2', 'EvidenceCursor1', 'EvidencePage1', 'ConfigurationCommit1', 'ApproachModelBinding1', 'ApproachElementRef1', 'ApproachEvidenceLink1', 'ApproachAssumption1', 'ApproachAssumptionOrigin1', 'ApproachAssumptionRef1', 'ApproachIntent1', 'ApproachStep1', 'ApproachCase1', 'ApproachBasisRef1', 'ApproachContent1', 'ApproachDraft1', 'ApproachVersion1', 'ApproachVersionSummary1', 'ApproachState1', 'ApproachSaved1', 'ApproachPreviewRequest1', 'ApproachDraftWrite1', 'ApproachVersionSave1', 'ApproachVersionSaved1', 'ApproachRestore1', 'ApproachCoverage1', 'ApproachRunContext1', 'ApproachResolution1', 'ApproachClosure1', 'ApproachIssue1', 'ApproachChange1', 'ApproachPreview1', 'ApproachCursor1', 'ApproachPageRequest1', 'ApproachVersionPage1', 'ApproachUsage1', 'ApproachUsageCursor1', 'ApproachUsageRequest1', 'ApproachUsagePage1', 'ApproachSelection1', 'ApproachBinding1', 'ConfigurationRequest4', 'ConfigurationCandidate4', 'ConfigurationRevision4', 'ConfigurationPreview4', 'ConfigurationCommit4', 'FrozenConfigurationLegacy', 'FrozenConfiguration4', 'FrozenConfiguration', 'BundleFileV5', 'ExecutionBundle5', 'RunHistory3', 'ModifiedRunSeed3', 'ApproachExportSummary1', 'RecordPreview2', 'RecordRequest2', 'RecordPreviewRead', 'RecordRequestRead', 'RecordRequestResponse', 'RecordStatusResponse', 'RecordReceiptResult', 'PayloadFile2', 'ApproachPayloadIndex1', 'ComputationalRecordManifest2', 'ComputationalRecordManifestRead', 'ApproachError1', 'ApproachCommandResult1', 'ApproachStateResponse1', 'ApproachPreviewResponse1', 'ApproachDraftResponse1', 'ApproachSavedResponse1', 'ApproachVersionSaveResponse1', 'ApproachVersionListResponse1', 'ApproachUsageResponse1', 'ApproachReceipt1', 'ApproachReceiptCategory1', 'ConfigurationRevisionPreApproach', 'UnitDeclaration1', 'PortDeclaration3', 'Port3', 'Definition3', 'DefinitionChange3', 'Edit3', 'ModelDraft3', 'ModelRevision3', 'ModelRevisionPreUnits', 'ApproachClosurePreUnits', 'ModelPackage3', 'Create3', 'CreateRequest', 'Preview3', 'Apply3', 'FrozenConfiguration5', 'ExecutionBundle6', 'RunHistory4', 'ModifiedRunSeed4', 'UnitCatalog1', 'UnitCatalogResponse1', 'DefinitionRead3', 'PortRead3', 'ApproachClosureWithModel3', 'FrozenConfiguration5Model3', 'FrozenConfiguration5Model2', 'RunHistory4Model3', 'RunHistory4Model2', 'ModifiedRunSeed4Model3', 'ModifiedRunSeed4Model2', 'ExecutionBundle6Model3', 'ExecutionBundle6Model2']}]

# Released body digest of every prior definition (BASELINE names and DOCS25_1_NAMES), shared by both
# schemas. A changed prior definition fails by name.
PRIOR_DEFINITIONS = json.loads((ROOT / "contracts/tests/documents_prior_definitions.json").read_text())["definitions"]
# Two prior read definitions were widened in place after release, before this repository's history:
# the ModelPackage read union gained ModelPackage4 and ExecutionVersions gained bundle version "8".
# These are their released bodies; the widening itself is pinned exactly below and is open for review.
WIDENED_IN_PLACE = {
    "ModelPackage": {"oneOf": [{"$ref": "#/$defs/ModelPackage1"}, {"$ref": "#/$defs/ModelPackage2"},
                               {"$ref": "#/$defs/ModelPackage3"}]},
    "ExecutionVersions": {"type": "object", "properties": {
        "artifact_versions": {"type": "array", "items": {"enum": ["2"]}, "minItems": 1, "maxItems": 1, "uniqueItems": True},
        "bundle_versions": {"type": "array", "items": {"enum": ["2", "3", "4", "5", "6"]}, "minItems": 1, "maxItems": 5,
                            "uniqueItems": True},
        "program_protocols": {"type": "array", "items": {"enum": ["hyprn_mvp.openmdao.program/1"]}, "minItems": 1,
                              "maxItems": 1, "uniqueItems": True},
        "historical_artifact_versions": {"type": "array", "items": {"enum": ["1"]}, "minItems": 1, "maxItems": 1,
                                         "uniqueItems": True},
        "historical_bundle_versions": {"type": "array", "items": {"enum": ["1"]}, "minItems": 1, "maxItems": 1,
                                       "uniqueItems": True}},
        "required": ["artifact_versions", "bundle_versions", "program_protocols", "historical_artifact_versions",
                     "historical_bundle_versions"], "additionalProperties": False},
}


def definition_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(name, value):
    assert name in S["$defs"], "Missing contract: " + name
    Draft202012Validator({**S, "$ref": "#/$defs/" + name},
                         format_checker=FormatChecker()).validate(value)


def rejected(name, value):
    with pytest.raises(ValidationError):
        validate(name, value)


def test_documents_contracts_upload_accepts_exact_original_and_rejects_native_capability():
    validate("DocumentUploadBegin1", BEGIN)
    for extra in ("native_uuid", "store", "profile", "path", "method", "actor_id", "study_id"):
        rejected("DocumentUploadBegin1", BEGIN | {extra: ID})
    rejected("DocumentUploadBegin1", BEGIN | {"byte_length": 10485761})
    rejected("DocumentUploadBegin1", BEGIN | {"sha256": HASH.upper()})
    rejected("DocumentUploadBegin1", BEGIN | {"media_type": "text/html"})
    rejected("DocumentUploadBegin1", BEGIN | {"filename": "x" * 201})
    rejected("DocumentUploadBegin1", BEGIN | {"command_id": ID.upper().replace("1", "A", 1)})


def test_documents_contracts_existing_family_upload_requires_paired_cas():
    validate("DocumentUploadBegin1", BEGIN | {"family_id": ID, "expected_revision": 2})
    rejected("DocumentUploadBegin1", BEGIN | {"family_id": ID})
    rejected("DocumentUploadBegin1", BEGIN | {"expected_revision": 2})
    rejected("DocumentUploadBegin1", BEGIN | {"family_id": ID, "expected_revision": -1})


@pytest.mark.parametrize("locator", [
    {"kind": "original_file"}, {"kind": "original_file", "section_label": "Unverified appendix"},
    {"kind": "pdf_page", "page": 1}, {"kind": "pdf_page", "page": 500}, SPAN])
def test_documents_contracts_locators_preserve_distinct_source_meanings(locator):
    validate("DocumentLocator1", locator)


@pytest.mark.parametrize("locator", [
    {"kind": "original_file", "quoted_text": "claimed verified"},
    {"kind": "original_file", "extraction_id": ID},
    {"kind": "pdf_page", "page": 0}, {"kind": "pdf_page", "page": 501},
    {"kind": "pdf_page", "page": 1, "section_label": "mixed"},
    SPAN | {"start": -1}, SPAN | {"start": 1.5}, SPAN | {"byte_offset": 1},
    SPAN | {"artifact_sha256": "bad"}, SPAN | {"kind": "url"},
    {"kind": "extracted_span", "start": 0, "end": 1},
])
def test_documents_contracts_invalid_or_mixed_locators_fail(locator):
    rejected("DocumentLocator1", locator)


def test_documents_contracts_structural_acceptance_does_not_claim_runtime_comparisons():
    # Both validate structurally. The runtime must reject the stale revision,
    # cross-study association, conflicting command digest and reversed span.
    validate("DocumentCollectionDelete1", {"command_id": ID, "expected_revision": 1})
    validate("DocumentCollectionDelete1", {"command_id": ID, "expected_revision": 2})
    validate("DocumentLocator1", SPAN | {"start": 4, "end": 2})
    for study, digest in ((ID, HASH), (OTHER, "b" * 64)):
        validate("DocumentCommandIdentity1", dict(study_id=study, actor_id=ID,
            command_id=ID, payload_sha256=digest, operation_id=ID))
    obligations = S["x-hyprn-mvp-documents-contract"]["runtime_invariants"]
    for key in ("current_authorization", "scope_association", "revision_cas",
                "canonical_command_digest", "span_bounds_and_hash", "delete_fences",
                "byte_length_and_hash", "replay_before_visibility_and_cas"):
        assert key in obligations
        assert obligations[key]["enforcement"] == "runtime"
        assert obligations[key]["verification_tasks"]


def test_documents_contracts_chunk_transport_and_membership_limits():
    validate("DocumentUploadChunk1", dict(offset=0, byte_length=262144, sha256=HASH))
    rejected("DocumentUploadChunk1", dict(offset=0, byte_length=262145, sha256=HASH))
    rejected("DocumentUploadChunk1", dict(offset=-1, byte_length=1, sha256=HASH))
    members = [f"00000000-0000-4000-8000-{i:012d}" for i in range(100)]
    value = dict(command_id=ID, expected_revision=1, action="add", version_ids=members)
    validate("DocumentCollectionMembersChange1", value)
    rejected("DocumentCollectionMembersChange1", value | {"version_ids": members + [OTHER]})
    rejected("DocumentCollectionMembersChange1", value | {"version_ids": [ID, ID]})
    rejected("DocumentCollectionMembersChange1", value | {"action": "clear"})
    limits = S["x-hyprn-mvp-documents-contract"]["limits"]
    assert limits["collection_members"] == 10000
    assert limits["members_per_mutation"] == 100


def test_documents_contracts_unknown_keys_are_rejected_by_every_new_object():
    # Schema-shape inspection enforces closure; literal fixtures above exercise admission.
    for name in S["x-hyprn-mvp-documents-contract"]["definitions"]:
        schema = S["$defs"][name]
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False, name
            assert set(schema["required"]) <= set(schema["properties"]), name
    for schema in SCHEMAS:
        Draft202012Validator.check_schema(schema)


def test_documents_contracts_prior_definitions_and_mixed_units_branches_remain_exact():
    for schema, baseline in zip(SCHEMAS, BASELINE):
        assert schema["$id"] == baseline["id"]
        for name in baseline["names"]:
            released = WIDENED_IN_PLACE.get(name, schema["$defs"][name])
            assert definition_digest(released) == PRIOR_DEFINITIONS[name], name
        # The only in-place changes of prior definitions are exactly these two widenings.
        assert schema["$defs"]["ModelPackage"] == {"oneOf": WIDENED_IN_PLACE["ModelPackage"]["oneOf"]
                                                   + [{"$ref": "#/$defs/ModelPackage4"}]}
        widened = copy.deepcopy(WIDENED_IN_PLACE["ExecutionVersions"])
        widened["properties"]["bundle_versions"]["items"]["enum"].append("8")
        widened["properties"]["bundle_versions"]["maxItems"] = 6
        assert schema["$defs"]["ExecutionVersions"] == widened
    assert_execution_schema()


def test_documents_contracts_all_routes_have_typed_requests_outcomes_and_permissions():
    registry = S["x-hyprn-mvp-documents-contract"]
    expected = {"upload", "operation", "library", "original", "metadata", "collection",
                "extraction", "search", "annotation", "citation", "usage", "delete",
                "export", "import", "restore"}
    assert {r["family"] for r in registry["routes"]} == expected
    for route in registry["routes"]:
        assert route["input"] in S["$defs"]
        assert route["output"] in S["$defs"]
        assert route["errors"] == "DocumentError1"
        assert route["authorization"] == "current_study_before_lookup_and_delivery"
        assert set(route["roles"]) <= {"owner", "writer", "reader", "operator"}
        if route["method"] != "GET":
            assert route["csrf"] is True
    assert {r["method"] + " " + r["path"] for r in registry["routes"]} >= {
        "POST document-uploads", "PUT document-uploads/{upload_id}/chunks/{offset}",
        "POST document-uploads/{upload_id}/complete", "GET document-versions/{version_id}/original",
        "POST document-deletions/commit", "POST document-citations/preview"}


@pytest.mark.parametrize("verb", ["submit", "launch", "resume", "cancel", "exec", "GET", "../original"])
def test_documents_contracts_bridge_refuses_science_and_generic_dispatch(verb):
    rejected("DocumentBridgeRead1", {"mode": "document-read", "verb": verb,
        "study_id": ID, "request_id": ID, "input": {}})
    rejected("DocumentBridgeWrite1", {"mode": "document-write", "verb": verb,
        "identity": dict(study_id=ID, actor_id=ID, command_id=ID,
                         payload_sha256=HASH, operation_id=ID), "input": {}})


def test_documents_contracts_fixed_read_is_typed_and_disallows_profile_path():
    value = dict(mode="document-read", verb="descriptor", study_id=ID, request_id=ID,
                 input={"version_id": ID})
    validate("DocumentBridgeRead1", value)
    rejected("DocumentBridgeRead1", value | {"profile": "default"})
    rejected("DocumentBridgeRead1", value | {"input": {"path": "/etc/passwd"}})
    rejected("DocumentBridgeRead1", value | {"verb": "original", "input": {"version_id": ID, "size": 999999999}})


def test_documents_contracts_operation_states_and_logical_delete_are_explicit():
    registry = S["x-hyprn-mvp-documents-contract"]
    transitions = registry["operation_transitions"]
    assert transitions["receiving"] == ["queued", "failed", "expired", "interrupted"]
    assert "published" in transitions["committed"]
    assert transitions["published"] == []
    assert transitions["uncertain"] == ["committed", "failed"]
    logical = registry["collection_protocol"]
    assert logical["delete"] == "empty_terminal_group_revision_immutable_witness_one_transaction"
    assert logical["physical_cleanup"] is False
    assert logical["replay_order"] == ["authorize", "exact_witness", "active_visibility", "cas"]
    assert logical["active_filter_boundary"] == "native_query_before_pagination"
    assert logical["delete_members_limit"] == 10000
    assert registry["scientific_allocations_owner"] == "25.2"


def test_documents_contracts_search_bounds_and_delete_exact_set():
    validate("DocumentSearchQuery1", {"query": "Δp😀", "mode": "both", "limit": 100})
    rejected("DocumentSearchQuery1", {"query": "x"*257, "mode": "text", "limit": 100})
    rejected("DocumentSearchQuery1", {"query": "x", "mode": "semantic", "limit": 10})
    rejected("DocumentDeleteSelection1", {"document_id": ID, "all_versions": True})
    validate("DocumentDeleteSelection1", {"document_id": ID, "expected_revision": 2,
        "versions": [{"version_id": ID, "expected_revision": 1}]})
    rejected("DocumentDeleteSelection1", {"document_id": ID, "expected_revision": 2, "versions": []})

def test_documents_contracts_empty_native_list_preserves_its_resource_kind():
    validate("DocumentNativeListResult1",
             {"resource": "documents", "data": {"items": [], "next_cursor": None}})
    validate("DocumentNativeListResult1",
             {"resource": "collections", "data": {"items": [], "next_cursor": None}})
    rejected("DocumentNativeListResult1",
             {"resource": "profiles", "data": {"items": [], "next_cursor": None}})


def test_documents_contracts_existing_public_error_envelope_is_reused():
    error = {"error": {"code": "command_payload_conflict", "message": "command payload conflict",
        "request_id": ID, "command_id": ID, "resource_id": None, "current_revision": None,
        "fields": [], "outcome": "unchanged"}}
    validate("DocumentError1", error)
    rejected("DocumentError1", {"code": "command_conflict", "message": "conflict", "retryable": False})


def test_documents_contracts_plain_text_and_pdf_extractor_pins_are_distinct():
    pin = dict(name="hyprn-mvp-utf8", version="1", image_sha256=HASH,
               config_sha256=HASH, policy_id="documents-text-v1")
    validate("DocumentExtractorIdentity1", pin)
    validate("DocumentExtractorIdentity1", pin | {"name": "pypdf", "version": "6.20.0"})
    rejected("DocumentExtractorIdentity1", pin | {"name": "pypdf"})
    rejected("DocumentExtractorIdentity1", pin | {"argv": ["sh"]})


def test_documents_contracts_transition_wire_rejects_impossible_publication():
    rejected("DocumentOperationTransition1",
             {"from": "running", "to": "committed", "proof": "verified_native_witness"})
    # A proof label alone is insufficient; complete app/native compositions below.
    rejected("DocumentOperationTransition1",
             {"from": "receiving", "to": "published", "proof": "verified_native_witness"})
    rejected("DocumentOperationTransition1",
             {"from": "uncertain", "to": "running", "proof": "timeout"})


def test_documents_contracts_operation_failure_cannot_carry_success_or_run_id():
    pending = dict(schema_version="1", operation_id=ID, study_id=ID, command_id=ID,
        category="collection_delete", state="queued", reserved_ids={"collection_id": OTHER},
        created_at="2026-10-11T08:30:00Z", updated_at="2026-10-11T08:30:00Z",
        waiting_for_native_storage=True, result=None, error=None)
    validate("DocumentOperation1", pending)
    rejected("DocumentOperation1", pending | {"run_id": ID})
    rejected("DocumentOperation1", pending | {"state": "published"})
    rejected("DocumentOperation1", pending | {"state": "uncertain"})
    result = {"collection_id": OTHER, "revision": 2, "deleted": True, "originals_preserved": True}
    validate("DocumentOperation1", pending | {"state": "published", "result": result,
                                             "waiting_for_native_storage": False})
    rejected("DocumentOperation1", pending | {"state": "failed", "result": result})


def test_documents_contracts_partial_extraction_keeps_text_coverage_but_failed_page_has_no_text():
    page = dict(page=1, state="partial", artifact_id=ID, text_sha256=HASH,
                text_bytes=6, codepoints=3, reason="output_limit")
    validate("DocumentPageCoverage1", page)
    rejected("DocumentPageCoverage1", page | {"state": "failed"})
    validate("DocumentPageCoverage1", page | {"state": "failed", "artifact_id": None,
        "text_sha256": None, "text_bytes": 0, "codepoints": 0})
    rejected("DocumentPageCoverage1", page | {"confidence": 0.99})


def test_documents_contracts_citation_candidates_are_exact_and_never_client_verified_quotes():
    original = {"version_id": ID, "locator": {"kind": "original_file"}, "relationship": "supports"}
    validate("DocumentCitationCandidate1", original)
    rejected("DocumentCitationCandidate1", original | {"quoted_text": "claimed"})
    rejected("DocumentCitationCandidate1", original | {"extraction_id": OTHER})
    extracted = original | {"locator": SPAN, "extraction_id": ID}
    validate("DocumentCitationCandidate1", extracted)
    rejected("DocumentCitationCandidate1", original | {"locator": SPAN})
    rejected("DocumentCitationCandidate1", original | {"annotation_id": OTHER})


def test_documents_contracts_terminal_collection_cannot_hide_remaining_members():
    tombstone = dict(schema_version="documents-collection-terminal/1", collection_id=ID,
        study_id=ID, native_store_id=ID, native_group_id=OTHER, command_id=ID,
        payload_sha256=HASH, lifecycle="deleted", member_count=0,
        previous_revision=1, revision=2, witness_id=ID)
    validate("DocumentCollectionTerminal1", tombstone)
    rejected("DocumentCollectionTerminal1", tombstone | {"member_count": 1})
    rejected("DocumentCollectionTerminal1", tombstone | {"lifecycle": "active"})


# Documents25.2: literal wire fixtures. These do not execute a resolver, parser,
# native adapter or scientific model. Digests below are structural examples.
SCOPE4 = dict(scope_version="1", study_id=ID, kind="study")
CONTEXT4 = dict(schema_version="1", label="Pressure evidence", resource_labels=[])
TEXT_CONTEXT = dict(description="Pressure loss", boundary="One pipe", notes=[])
NUMERICAL4 = dict(mode="deterministic", initialization=[], solvers=[],
    derivatives=dict(method="none", form=None, check=None), design_variables=[],
    objectives=[], constraints=[], optimizer=None, uncertainty=None)
CANDIDATE4 = dict(version_id=OTHER, locator={"kind": "original_file"}, relationship="supports")
CITATION4 = dict(schema_version="1", citation_id=HASH, study_id=ID,
    document_id=ID, document_version_id=OTHER, original_sha256=HASH,
    original_size=6, original_media_type="text/plain", title="Measured pressure",
    filename="pressure.txt", extraction_id=None, extraction_digest=None,
    extractor=None, locator={"kind": "original_file"}, quoted_text=None,
    quoted_text_sha256=None, annotation=None, relationship="supports")
CREATE4 = dict(command_id=ID, evidence_schema_version="4", resource_scope=SCOPE4,
    kind="note", title="Pressure loss", content="The measured loss supports this case.",
    source_refs=["Unverified notebook reference"], citations=[CANDIDATE4],
    expected_context_revision="study-r3", expected_preview_digest=HASH)
RECORD4 = dict(evidence_id=ID, evidence_version_id=OTHER, study_id=ID,
    evidence_schema_version="4", resource_scope=SCOPE4, kind="note",
    title="Pressure loss", content="The measured loss supports this case.",
    source_refs=["Unverified notebook reference"], citations=[CITATION4],
    parent_evidence_version_id=None, recorded_context=CONTEXT4)
CONFIG5 = dict(schema_version="5", study_id=ID, model_id=ID, model_revision_id=OTHER,
    name="Pressure case", inputs=[], criteria=[], numerical=NUMERICAL4,
    context_snapshot=TEXT_CONTEXT, evidence_snapshots=[RECORD4],
    required_capabilities=["flat_explicit_scalar"],
    context_source=dict(kind="current_study", expected_study_revision="study-r3"),
    derivation=None, assumptions=[], general_context_evidence_version_ids=[OTHER],
    approach_binding=None, configuration_id=ID, configuration_revision_id=OTHER,
    parent_revision_id=None, digest=HASH)
REQUEST5 = dict(schema_version="5", study_id=ID, model_id=ID, model_revision_id=OTHER,
    name="Pressure case", inputs=[], criteria=[], numerical=NUMERICAL4,
    context_source=dict(kind="current_study", expected_study_revision="study-r3"),
    notes=[], derivation=None, assumptions=[], general_context_evidence_version_ids=[OTHER],
    approach_selection=None)
PRIVATE4 = dict(schema_version="4", study_id=ID, model_id=ID, model_revision_id=OTHER,
    name="Pressure case", inputs=[], criteria=[], numerical=NUMERICAL4,
    context_snapshot=TEXT_CONTEXT, evidence_snapshots=[RECORD4],
    required_capabilities=["flat_explicit_scalar"], configuration_id=ID,
    configuration_revision_id=OTHER, parent_revision_id=None, digest=HASH)
MODEL2 = dict(schema_version="2", model_id=ID, model_revision_id=OTHER,
    root_instance_id=ID, definitions=[], instances=[], ports=[], connections=[],
    boundary_mappings=[], annotations=[], source_files=[],
    required_capabilities=["flat_explicit_scalar"], parent_model_revision_id=None,
    originating_draft_revision="draft-r1", digest=HASH, assumptions=[])
MODEL3 = MODEL2 | dict(schema_version="3",
    required_capabilities=["flat_explicit_scalar", "unit_declarations/1"])
APPROACH_VERSION = dict(schema_version="1", approach_id=ID, approach_version_id=OTHER,
    study_id=ID, version_number=1, predecessor_version_id=None,
    content=dict(schema_version="1", question="Pressure", scope="Pipe", limitations="",
        open_questions="", model_bindings=[], steps=[], assumptions=[], cases=[], basis_refs=[]),
    created_by=ID, created_at="2026-10-11T08:40:00Z", digest=HASH)
CLOSURE2 = dict(schema_version="2", root_approach_version_id=OTHER,
    root_approach_digest=HASH, approach_versions=[APPROACH_VERSION], models=[MODEL2],
    configurations=[], run_contexts=[], evidence=[RECORD4], digest=HASH)
BINDING4 = dict(approach_id=ID, approach_version_id=OTHER, approach_digest=HASH,
    closure_digest=HASH, case_id=None)
RUNTIME4 = dict(image_digest="sha256:"+HASH, architecture="arm64", python_version="3.12",
    worker_entrypoint="hyprn_mvp_integration.worker", policy_digest=HASH)


def extracted_citation4():
    return CITATION4 | dict(extraction_id=ID, extraction_digest=HASH, locator=SPAN,
        extractor=dict(name="hyprn-mvp-utf8", version="1", image_sha256=HASH,
            config_sha256=HASH, policy_id="documents-text-v1"),
        quoted_text="😀", quoted_text_sha256=hashlib.sha256("😀".encode()).hexdigest())


def frozen6(model=MODEL3, closure=None):
    return dict(schema_version="6", configuration=CONFIG5 | dict(
        approach_binding=BINDING4 if closure is not None else None),
        model_snapshot=model, study_revision="study-r3", approach_closure=closure)


def history5(model=MODEL3, closure=None):
    frozen = frozen6(model, closure)
    return dict(history_schema_version="5", configuration=frozen["configuration"],
        model_snapshot=model, context=TEXT_CONTEXT, evidence=[RECORD4],
        bundle=dict(schema_version="7", bundle_digest=HASH, model_digest=HASH,
            configuration_digest=HASH, dependencies=[],
            approach_digest=HASH if closure else None, approach_closure_digest=HASH if closure else None),
        approach_closure=closure, results=None, assessment=None, artifacts=[],
        errors=[dict(code="missing_results", partial=True)])


def seed5(model=MODEL3, closure=None):
    return dict(schema_version="5", source_run_id=ID, source_configuration_digest=HASH,
        model_snapshot=model, configuration=REQUEST5, source_context=TEXT_CONTEXT,
        current_context=TEXT_CONTEXT, current_study_revision="study-r3", context_changed=False,
        requires_context_choice=False, source_runtime=RUNTIME4,
        runtime_comparison=dict(source=RUNTIME4, current=None, state="unavailable",
            basis="prepared_bundle", observed_at=None, expires_at=None),
        source_configuration=frozen6(model, closure)["configuration"], approach_closure=closure)


@pytest.mark.parametrize("name,value", [
    ("EvidenceCreate4", CREATE4), ("EvidenceRevise4", CREATE4 | {"expected_revision": OTHER}),
    ("EvidenceRecord4", RECORD4), ("EvidenceSnapshot4", RECORD4),
    ("ConfigurationRevision5", CONFIG5), ("ConfigurationRequest5", REQUEST5),
    ("ModelingConfigurationRevision4", PRIVATE4), ("ApproachClosure2", CLOSURE2),
])
def test_documents_citation_contracts_closed_new_objects_and_required_fields(name, value):
    validate(name, value)
    rejected(name, value | {"unknown": True})
    for key in S["$defs"][name]["required"]:
        bad = copy.deepcopy(value); del bad[key]
        rejected(name, bad)


@pytest.mark.parametrize("citation", [CITATION4, extracted_citation4(),
    CITATION4 | dict(original_media_type="application/pdf", locator=dict(kind="pdf_page", page=2))])
def test_documents_citation_contracts_frozen_citation_modes_preserve_complete_context(citation):
    validate("DocumentCitation1", citation)
    validate("EvidenceRecord4", RECORD4 | {"citations": [citation]})
    for key in ("title", "filename", "original_sha256", "original_size", "extractor",
                "extraction_digest", "relationship", "annotation", "study_id"):
        bad = copy.deepcopy(citation); del bad[key]
        rejected("DocumentCitation1", bad)


@pytest.mark.parametrize("changes", [
    {"quoted_text": "client claim", "quoted_text_sha256": HASH},
    {"extraction_id": ID}, {"original_size": 10485761}, {"original_sha256": "bad"},
    {"native_node_id": ID}, {"original_bytes": "PDF bytes"}, {"relationship": "proves"},
    {"locator": dict(kind="pdf_page", page=1)},
])
def test_documents_citation_contracts_citation_rejects_mixed_authority_and_invalid_source(changes):
    rejected("DocumentCitation1", CITATION4 | changes)


def test_documents_citation_contracts_extracted_quote_and_annotation_are_closed_snapshots():
    citation = extracted_citation4()
    annotation = dict(schema_version="1", annotation_id=ID, version_id=OTHER, study_id=ID,
        revision=2, locator=SPAN, text="Check this line", tags=["pressure"], created_by=ID,
        updated_by=OTHER, created_at="2026-10-11T08:40:00Z", updated_at="2026-10-11T08:41:00Z")
    validate("DocumentCitation1", citation | {"annotation": annotation})
    for key in ("created_by", "updated_by", "revision", "locator", "text"):
        bad = copy.deepcopy(annotation); del bad[key]
        rejected("DocumentCitation1", citation | {"annotation": bad})
    for key in ("extraction_id", "extraction_digest", "extractor", "quoted_text", "quoted_text_sha256"):
        rejected("DocumentCitation1", citation | {key: None})
    rejected("DocumentCitation1", citation | {"quoted_text": "x" * 4097})
    rejected("EvidenceCreate4", CREATE4 | {"citations": [citation]})
    rejected("EvidenceCreate4", CREATE4 | {"citations": [CANDIDATE4 | {"quoted_text": "claimed"}]})


def test_documents_citation_contracts_duplicates_and_limits_in_candidates_and_retained_records():
    for name, value, citation in (("EvidenceCreate4", CREATE4, CANDIDATE4),
                                ("EvidenceRecord4", RECORD4, CITATION4)):
        rejected(name, value | {"citations": [citation, copy.deepcopy(citation)]})
        distinct = [citation | ({"version_id": f"00000000-0000-4000-8000-{i:012d}"}
            if name == "EvidenceCreate4" else {"citation_id": f"{i:064x}"}) for i in range(20)]
        validate(name, value | {"citations": distinct})
        rejected(name, value | {"citations": distinct + [citation]})


def test_documents_citation_contracts_preview_binds_statement_target_revision_and_server_result():
    request = {k: copy.deepcopy(v) for k, v in CREATE4.items()
               if k not in ("command_id", "expected_preview_digest")}
    validate("EvidenceCitationPreviewRequest4", request)
    validate("EvidenceCitationPreviewRequest4", request | {"evidence_id": ID, "expected_revision": OTHER})
    rejected("EvidenceCitationPreviewRequest4", request | {"evidence_id": ID})
    rejected("EvidenceCitationPreviewRequest4", request | {"expected_revision": OTHER})
    response = dict(preview_digest=HASH, request_digest=HASH,
        expires_at="2026-10-11T08:45:00Z", resource_scope=SCOPE4,
        context_revision="study-r3", parent_evidence_version_id=None,
        recorded_context=CONTEXT4, citations=[CITATION4])
    validate("EvidenceCitationPreview4", response)
    rejected("EvidenceCitationPreview4", response | {"citations": [CANDIDATE4]})
    rejected("EvidenceCreate4", CREATE4 | {"expected_preview_digest": "bad"})


def test_documents_citation_contracts_legacy_evidence_stays_textual_and_rejects_new_nesting():
    for version in (1, 2, 3):
        old = dict(command_id=ID, kind="note", content="Legacy note", source_refs=["document://unverified"])
        old.update(dict(scope=None) if version == 1 else
                   dict(evidence_schema_version=str(version), resource_scope=SCOPE4))
        if version == 3: old["title"] = "Legacy title"
        validate("EvidenceCreate"+str(version), old)
        validate("EvidenceCreateRead4", old)
        rejected("EvidenceCreate"+str(version), old | {"citations": [CANDIDATE4]})
    old_record = {k:v for k,v in RECORD4.items() if k != "citations"} | {"evidence_schema_version":"3"}
    validate("EvidenceRecord3", old_record)
    validate("EvidenceRecordRead4", old_record)
    for name in ("EvidenceRecord3", "EvidenceSnapshot3", "EvidenceRecordRead", "EvidenceSnapshotRead"):
        rejected(name, RECORD4)


def test_documents_citation_contracts_private_and_public_versions_cannot_be_crossed():
    validate("ConfigurationRevisionRead5", CONFIG5)
    validate("EvidenceSnapshotRead4", RECORD4)
    rejected("ConfigurationRevision4", CONFIG5 | {"schema_version": "4"})
    rejected("ModelingConfigurationRevision3", PRIVATE4 | {"schema_version": "3"})
    rejected("ModelingConfigurationRevision4", CONFIG5 | {"schema_version": "4"})
    rejected("ConfigurationRevision5", PRIVATE4 | {"schema_version": "5"})
    old = copy.deepcopy(CONFIG5); old.update(schema_version="4", evidence_snapshots=[])
    validate("ConfigurationRevision4", old)
    validate("ConfigurationRevisionRead5", old)
    rejected("ConfigurationRevision", CONFIG5)


@pytest.mark.parametrize("factory,name", [(frozen6,"FrozenConfiguration6"),
    (history5,"RunHistory5"), (seed5,"ModifiedRunSeed5")])
@pytest.mark.parametrize("case", ["typed", "legacy", "legacy_linked", "mixed"])
def test_documents_citation_contracts_exact_selected_model_and_closure_branches(factory, name, case):
    model = MODEL3 if case == "typed" else MODEL2
    closure = None if case in ("typed", "legacy") else copy.deepcopy(CLOSURE2)
    if case == "mixed": closure["models"].append(MODEL3)
    value = factory(model, closure)
    validate(name, value)
    branches = S["$defs"][name]["oneOf"]
    assert sum(Draft202012Validator({**S, **b}).is_valid(value) for b in branches) == 1
    rejected(name, value | {"unknown": True})
    old = copy.deepcopy(value)
    field = "source_configuration" if name == "ModifiedRunSeed5" else "configuration"
    old[field]["schema_version"] = "4"
    rejected(name, old)
    bad = copy.deepcopy(value); bad["model_snapshot"]["schema_version"] = "1"
    bad["model_snapshot"].pop("assumptions")
    rejected(name, bad)
    if closure is not None:
        bad = copy.deepcopy(value); bad[field]["approach_binding"] = None
        rejected(name, bad)


def test_documents_citation_contracts_mixed_branch_needs_binding_and_explanatory_model3():
    closure = CLOSURE2 | {"models": [MODEL2, MODEL3]}
    value = frozen6(MODEL2, closure)
    validate("FrozenConfiguration6Model2WithModel3", value)
    rejected("FrozenConfiguration6Model2WithModel3", frozen6(MODEL2, CLOSURE2))
    rejected("FrozenConfiguration6Model2", value)
    rejected("FrozenConfiguration6Model2WithModel3", value | {"approach_closure": None})
    rejected("ApproachClosure1", CLOSURE2)
    rejected("ApproachClosure1", CLOSURE2 | {"schema_version":"1"})


def test_documents_citation_contracts_null_history_is_disjoint_and_integrity_is_public_metadata():
    value = history5()
    for key in ("configuration", "model_snapshot", "context", "evidence", "bundle", "approach_closure"):
        value[key] = None
    value["errors"] = [dict(code="corrupt_retained_record", partial=True)]
    validate("RunHistory5", value)
    rejected("RunHistory5", value | {"retained_integrity": {"schema_version":"1","results_digest":HASH}})


def test_documents_citation_contracts_new_definition_refs_resolve_and_closed_shapes_are_equal():
    assert_execution_schema()
    for schema in SCHEMAS: Draft202012Validator.check_schema(schema)
    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value: assert value["$ref"].removeprefix("#/$defs/") in S["$defs"]
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(S["$defs"])


def bundle7(typed=True, linked=False):
    files = [dict(path=p, role=r, sha256=HASH, size=10, media_type="application/json")
             for p,r in (("configuration.json","configuration"),
                         ("modeling-configuration.json","modeling_configuration"),
                         ("result-dependencies.json","result_dependencies"))]
    if linked: files.append(dict(path="approach/closure.json",role="approach",
        sha256=HASH,size=10,media_type="application/json"))
    return dict(schema_version="7",bundle_id=ID,run_id=OTHER,prepared_digest=HASH,
        model_revision_id=OTHER,configuration_revision_id=OTHER,model_digest=HASH,
        configuration_digest=HASH,files=files,generator=dict(name="native-static",
            version="1",source_commit="a"*40,source_archive_sha256=HASH,
            generator_digest=HASH,template_digest=HASH,adapter_version="1",
            adapter_digest=HASH,provenance_path="provenance/generator.json"),
        entrypoint=dict(protocol="hyprn_mvp.openmdao.program/1",module_path="generated/model.py",
            factory="build_model",bindings_path="generated/bindings.json",
            source_map_path="generated/source-map.json"),executable_content_digest=HASH,
        dependencies=[],runtime=RUNTIME4,required_capabilities=(
            ["flat_explicit_scalar","unit_declarations/1"] if typed else ["flat_explicit_scalar"]),
        licenses=[],result_protocol_version="1",bundle_digest=HASH,
        modeling_configuration_digest=HASH,result_dependencies=dict(path="result-dependencies.json",
            sha256=HASH,size=10),approach_digest=HASH if linked else None,
        approach_closure_digest=HASH if linked else None)


@pytest.mark.parametrize("typed,linked", [(True,False),(True,True),(False,False),(False,True)])
def test_documents_citation_contracts_bundle7_exact_capabilities_files_and_no_source_bytes(typed, linked):
    value = bundle7(typed,linked)
    validate("ExecutionBundle7", value)
    validate("ExecutionBundleRead7", value)
    rejected("ExecutionBundle", value)
    rejected("ExecutionBundle7", value | {"result_protocol_version":"2"})
    rejected("ExecutionBundle7", value | {"source_bytes":"PDF"})
    rejected("ExecutionBundle7", value | {"required_capabilities":["flat_explicit_scalar","documents/1"]})
    rejected("ExecutionBundle7", value | {"approach_closure_digest":None if linked else HASH})
    bad=copy.deepcopy(value);bad["files"][0]["media_type"]="application/pdf"
    rejected("ExecutionBundle7",bad)
    bad=copy.deepcopy(value);bad["files"].pop(1)
    rejected("ExecutionBundle7",bad)
    branches=S["$defs"]["ExecutionBundle7"]["oneOf"]
    assert sum(Draft202012Validator({**S,**b}).is_valid(value) for b in branches)==1


def test_documents_citation_contracts_config_preview_commit_and_read_unions():
    candidate={k:v for k,v in CONFIG5.items() if k not in
               ("configuration_id","configuration_revision_id","parent_revision_id","digest")}
    validate("ConfigurationCandidate5",candidate)
    private={k:v for k,v in PRIVATE4.items() if k not in
             ("configuration_id","configuration_revision_id","parent_revision_id","digest")}
    validate("ModelingConfiguration4",private)
    # Existing compatibility fields are literal; model execution is not exercised.
    compatibility=dict(schema_version="1",compatible=True,model_revision_id=OTHER,model_digest=HASH,
        candidate_digest=HASH,diagnostics=[],required_capabilities=["flat_explicit_scalar"],
        validator_identity="modeling-contract/1-static")
    preview=dict(schema_version="5",request_digest=HASH,resolved_candidate=candidate,
        candidate_digest=HASH,model_digest=HASH,compatibility=compatibility,
        changes=[],runtime_comparison=None,approach_closure=None)
    validate("ConfigurationPreview5",preview)
    rejected("ConfigurationPreview4",preview)
    commit=dict(command_id=ID,expected_revision=None,configuration_id=None,
        configuration=REQUEST5,expected_preview_digest=HASH)
    validate("ConfigurationCommit5",commit)
    validate("ConfigurationCommitRead5",commit)
    rejected("ConfigurationCommit4",commit)
    rejected("ConfigurationCommit5",commit | {"configuration": REQUEST5 | {"schema_version":"4"}})


@pytest.mark.parametrize("factory,newname,oldname",[(frozen6,"FrozenConfiguration6","FrozenConfiguration5"),
    (history5,"RunHistory5","RunHistory4"),(seed5,"ModifiedRunSeed5","ModifiedRunSeed4")])
def test_documents_citation_contracts_old_units_envelopes_remain_literal_valid_without_promoting_citations(factory,newname,oldname):
    value=factory()
    field="source_configuration" if factory==seed5 else "configuration"
    value[field]=copy.deepcopy(value[field]);value[field].update(schema_version="4",evidence_snapshots=[])
    value["history_schema_version" if factory==history5 else "schema_version"]={
        frozen6:"5",history5:"4",seed5:"4"}[factory]
    if factory==history5:value.update(evidence=[],bundle=value["bundle"] | {"schema_version":"6"})
    if factory==seed5:value["configuration"]=REQUEST5 | {"schema_version":"4"}
    validate(oldname,value)
    rejected(newname,value)
    value[field]["evidence_snapshots"]=[RECORD4]
    rejected(oldname,value)


def test_documents_citation_contracts_structural_schema_does_not_claim_hash_or_cross_field_verification():
    # Malformed digests fail structurally, but a syntactically valid wrong digest
    # or foreign identity requires the future actual resolver/worker admission.
    validate("DocumentCitation1",extracted_citation4() | {"quoted_text_sha256":"b"*64})
    validate("EvidenceRecord4",RECORD4 | {"study_id":OTHER})
    registry=S["x-hyprn-mvp-documents-contract"]["scientific_allocations"]
    assert registry["status"]=="contract_only_runtime_pending"
    assert registry["public_integrity"]["optional"] is True
    assert registry["prepared_artifact"]=="PreparedModelArtifact2"
    assert registry["result_protocol_version"]=="1"
    assert registry["commit_barrier"]["owners"]==["34.2","35.1","37.1","39.1"]


def test_documents_citation_contracts_approach_preview_and_saved_wrappers_preserve_old_version_meaning():
    saved=dict(version=APPROACH_VERSION,closure=CLOSURE2)
    validate("ApproachSaved2",saved)
    validate("ApproachVersionSaved2",dict(saved=saved,draft_revision=ID))
    rejected("ApproachSaved1",saved)
    rejected("ApproachVersionSaved1",dict(saved=saved,draft_revision=ID))
    resolution={k:CLOSURE2[k] for k in ("approach_versions","models","configurations","run_contexts","evidence")}
    validate("ApproachResolution2",resolution)
    rejected("ApproachResolution1",resolution)
    assert S["$defs"]["ApproachPreview2"]["properties"]["resolved"]=={"$ref":"#/$defs/ApproachResolution2"}


DOCS25_1_NAMES = ['DocumentId1', 'DocumentDigest1', 'DocumentTimestamp1', 'DocumentEmpty1', 'DocumentCommand1', 'DocumentVersionKey1', 'DocumentCollectionKey1', 'DocumentAnnotationKey1', 'DocumentAttemptKey1', 'DocumentOperationKey1', 'DocumentOriginalLocator1', 'DocumentPdfPageLocator1', 'DocumentExtractedSpanLocator1', 'DocumentLocator1', 'Document1', 'DocumentVersion1', 'DocumentNativeAssociation1', 'DocumentCollection1', 'DocumentCollectionMember1', 'DocumentAnnotation1', 'DocumentExtractorIdentity1', 'DocumentTextPolicy1', 'DocumentPageCoverage1', 'DocumentExtractionAttempt1', 'DocumentExtractionResult1', 'DocumentFragment1', 'DocumentSourceDescriptor1', 'DocumentUploadBegin1', 'DocumentUploadChunk1', 'DocumentUploadChunkReceipt1', 'DocumentUploadStatus1', 'DocumentMetadataPatch1', 'DocumentArchiveChange1', 'DocumentListQuery1', 'DocumentPageQuery1', 'DocumentList1', 'DocumentVersionList1', 'DocumentCollectionList1', 'DocumentMemberList1', 'DocumentAnnotationList1', 'DocumentAttemptList1', 'DocumentOriginalQuery1', 'DocumentByteDescriptor1', 'DocumentFragmentQuery1', 'DocumentCollectionCreate1', 'DocumentCollectionPatch1', 'DocumentCollectionMembersChange1', 'DocumentCollectionDelete1', 'DocumentCollectionDeleted1', 'DocumentExtractionCreate1', 'DocumentExtractionRetry1', 'DocumentSearchQuery1', 'DocumentSearchHit1', 'DocumentSearchResult1', 'DocumentAnnotationCreate1', 'DocumentAnnotationRevise1', 'DocumentAnnotationDelete1', 'DocumentAnnotationDeleted1', 'DocumentCitationCandidate1', 'DocumentCitationPreview1', 'DocumentUsage1', 'DocumentUsageList1', 'DocumentDeleteVersion1', 'DocumentDeleteSelection1', 'DocumentDeletePreview1', 'DocumentDeleteCommit1', 'DocumentDeletionFence1', 'DocumentTombstone1', 'DocumentDeletionResult1', 'DocumentPortableSelection1', 'DocumentPortablePreviewRequest1', 'DocumentPortablePreview1', 'DocumentPortableCreate1', 'DocumentPortableArtifact1', 'DocumentPortableDownload1', 'DocumentImportBegin1', 'DocumentImportCommit1', 'DocumentImportMapping1', 'DocumentImportResult1', 'DocumentRestoreRequest1', 'DocumentRestoreResult1', 'DocumentError1', 'DocumentReservedIds1', 'DocumentOperationResult1', 'DocumentOperation1', 'DocumentCommandIdentity1', 'DocumentNativeWitness1', 'DocumentCollectionTerminal1', 'DocumentImportChunk1', 'DocumentImportChunkReceipt1', 'DocumentNativeOriginalRead1', 'DocumentNativeOriginalReply1', 'DocumentNativeMemberRead1', 'DocumentNativeAnnotationRead1', 'DocumentNativeFragmentRead1', 'DocumentNativeList1', 'DocumentNativeListResult1', 'DocumentNativeStatus1', 'DocumentNativeStatusResult1', 'DocumentNativeStoreOriginal1', 'DocumentNativeCollectionUpdate1', 'DocumentNativeCollectionMembers1', 'DocumentNativeCollectionDelete1', 'DocumentNativeAnnotationCreate1', 'DocumentNativeAnnotationRevise1', 'DocumentNativeAnnotationDelete1', 'DocumentNativeExtractionStart1', 'DocumentBridgeRead1', 'DocumentBridgeReadReply1', 'DocumentBridgeWrite1', 'DocumentBridgeWriteReply1', 'DocumentFailure1', 'DocumentOperationTransition1', 'DocumentNativeByteDescriptor1']


# Only these four undeployed Documents definitions were corrected after release.
# Their retained literal originals are verified against the released per-definition digests.
REPAIR25R_ORIGINALS = {'DocumentNativeAnnotationCreate1': {'type': 'object', 'properties': {'version_id': {'$ref': '#/$defs/DocumentId1'}, 'request': {'$ref': '#/$defs/DocumentAnnotationCreate1'}}, 'required': ['version_id', 'request'], 'additionalProperties': False}, 'DocumentNativeExtractionStart1': {'type': 'object', 'properties': {'version_id': {'$ref': '#/$defs/DocumentId1'}, 'attempt_id': {'$ref': '#/$defs/DocumentId1'}, 'request': {'$ref': '#/$defs/DocumentExtractionCreate1'}}, 'required': ['version_id', 'attempt_id', 'request'], 'additionalProperties': False}, 'DocumentBridgeWrite1': {'oneOf': [{'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'store_original'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeStoreOriginal1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'collection_create'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentCollectionCreate1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'collection_update'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeCollectionUpdate1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'collection_members'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeCollectionMembers1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'collection_delete'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeCollectionDelete1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'annotation_create'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeAnnotationCreate1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'annotation_revise'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeAnnotationRevise1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'annotation_delete'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeAnnotationDelete1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'extraction_start'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentNativeExtractionStart1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'source_delete_preview'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentDeleteSelection1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'source_delete'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentDeleteCommit1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'export'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentPortableCreate1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'import'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentImportCommit1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'restore'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentRestoreRequest1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}, {'type': 'object', 'properties': {'mode': {'const': 'document-write'}, 'verb': {'const': 'reconcile'}, 'identity': {'$ref': '#/$defs/DocumentCommandIdentity1'}, 'input': {'$ref': '#/$defs/DocumentOperationKey1'}}, 'required': ['mode', 'verb', 'identity', 'input'], 'additionalProperties': False}]}, 'DocumentOperationTransition1': {'oneOf': [{'type': 'object', 'properties': {'from': {'const': 'receiving'}, 'to': {'const': 'queued'}, 'proof': {'const': 'verified_complete_upload'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'receiving'}, 'to': {'const': 'failed'}, 'proof': {'const': 'verified_failure'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'receiving'}, 'to': {'const': 'expired'}, 'proof': {'const': 'expired_uncommitted_lease'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'receiving'}, 'to': {'const': 'interrupted'}, 'proof': {'const': 'controller_interrupted'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'queued'}, 'to': {'const': 'running'}, 'proof': {'const': 'authorized_single_writer_admission'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'queued'}, 'to': {'const': 'failed'}, 'proof': {'const': 'verified_failure'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'queued'}, 'to': {'const': 'interrupted'}, 'proof': {'const': 'controller_interrupted'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'running'}, 'to': {'const': 'committed'}, 'proof': {'const': 'verified_native_witness'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'running'}, 'to': {'const': 'failed'}, 'proof': {'const': 'verified_failure'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'running'}, 'to': {'const': 'interrupted'}, 'proof': {'const': 'controller_interrupted'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'running'}, 'to': {'const': 'uncertain'}, 'proof': {'const': 'unresolved_native_disposition'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'committed'}, 'to': {'const': 'published'}, 'proof': {'const': 'authorized_verified_publication'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'committed'}, 'to': {'const': 'uncertain'}, 'proof': {'const': 'unresolved_native_disposition'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'interrupted'}, 'to': {'const': 'queued'}, 'proof': {'const': 'fenced_writer_absence'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'interrupted'}, 'to': {'const': 'committed'}, 'proof': {'const': 'verified_native_witness'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'interrupted'}, 'to': {'const': 'failed'}, 'proof': {'const': 'verified_failure'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'interrupted'}, 'to': {'const': 'uncertain'}, 'proof': {'const': 'unresolved_native_disposition'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'uncertain'}, 'to': {'const': 'committed'}, 'proof': {'const': 'verified_native_witness'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}, {'type': 'object', 'properties': {'from': {'const': 'uncertain'}, 'to': {'const': 'failed'}, 'proof': {'const': 'proven_not_applied'}}, 'required': ['from', 'to', 'proof'], 'additionalProperties': False}]}}
REPAIR25R_CORRECTED_HASHES = {'DocumentNativeAnnotationCreate1': 'ec84a48bbc6ab134ea9d84d416b8d776cb1a254cb863483bc170f50c4dfe2826', 'DocumentNativeExtractionStart1': '3f51707012efbf51d967fc0ac15379aae5a964bbc54798f7db58c4fdd7d92c44', 'DocumentBridgeWrite1': 'cdb9dd2dc6e216d62efc88009215d1488d27f3d3ce1bbb35e74787fde8e94e36', 'DocumentOperationTransition1': 'a1f5e29b5c1f493dc7710a401202cc82ad234dd00c7430837e3921a6ded633f0'}

def test_documents_citation_contracts_every_previous_definition_including_aliases_remains_exact():
    names = BASELINE[0]["names"] + DOCS25_1_NAMES
    assert len(names) == 403 and set(names) == set(PRIOR_DEFINITIONS)
    assert set(REPAIR25R_ORIGINALS) == set(REPAIR25R_CORRECTED_HASHES)
    for schema in SCHEMAS:
        for name in names:
            released = schema["$defs"][name]
            if name in REPAIR25R_ORIGINALS:
                assert definition_digest(released) == REPAIR25R_CORRECTED_HASHES[name], name
                released = REPAIR25R_ORIGINALS[name]
            released = WIDENED_IN_PLACE.get(name, released)
            assert definition_digest(released) == PRIOR_DEFINITIONS[name], name


def test_documents_citation_contracts_model_assumption_resolution_keeps_exact_revision_and_new_evidence():
    value=dict(schema_version="2",model_digest=HASH,draft_revision=None,
        model_revision_id=OTHER,links=[dict(assumption_id=ID,evidence_version_id=OTHER,status="resolved")],
        evidence=[RECORD4])
    validate("AssumptionEvidenceResolution2",value)
    rejected("AssumptionEvidenceResolution1",value | {"schema_version":"1"})
    rejected("AssumptionEvidenceResolution2",value | {"draft_revision":"draft-r1"})
    validate("AssumptionEvidenceResolution2",value | dict(model_digest=None,
        model_revision_id=None,draft_revision="draft-r1"))
    rejected("AssumptionEvidenceResolution2",value | {"evidence":[RECORD4,RECORD4]})


def test_documents_citation_contracts_old_mixed_units_fixture_keeps_its_stricter_branch():
    old_record={k:v for k,v in RECORD4.items() if k!="citations"} | {"evidence_schema_version":"3"}
    closure=CLOSURE2 | dict(schema_version="1",models=[MODEL2,MODEL3],evidence=[old_record])
    old=dict(schema_version="5",configuration=CONFIG5 | dict(schema_version="4",
        evidence_snapshots=[old_record],approach_binding=BINDING4),
        model_snapshot=MODEL2,study_revision="study-r3",approach_closure=closure)
    validate("FrozenConfiguration5Model2",old)
    validate("FrozenConfiguration",old)
    rejected("FrozenConfiguration5Model2",old | {"approach_closure":closure | {"models":[MODEL2]}})
    new=frozen6(MODEL2,closure)
    validate("FrozenConfiguration6Model2WithModel3",new)
    rejected("FrozenConfiguration6Model2",new)

# 25.R compositions are literal protocol fixtures, not a reference backend.
AT25R = "2026-10-11T08:30:00Z"
THIRD25R = "33333333-3333-4333-8333-333333333333"
IDENTITY25R = dict(study_id=ID, actor_id=ID, command_id=ID,
                  operation_id=OTHER, payload_sha256=HASH)
EXTRACTOR25R = dict(name="hyprn-mvp-utf8", version="1", image_sha256=HASH,
                   config_sha256=HASH, policy_id="documents-text-v1")


def witness25r(category, reserved, result):
    return dict(schema_version="documents-witness/1", identity=IDENTITY25R,
                native_store_id=ID, reserved_ids=reserved, associations=[],
                category=category, result=result, previous_revision=None,
                resulting_revision=1)


def test_documents_contracts_repair_import_begin_composes_using_returned_ids_only():
    routes = S["x-hyprn-mvp-documents-contract"]["routes"]
    begin = next(r for r in routes if r["path"] == "document-imports")
    status = dict(upload_id=OTHER, operation_id=THIRD25R, expected_bytes=6,
                  received_bytes=0, sha256=HASH, expires_at=AT25R, state="receiving")
    assert begin["output"] == "DocumentImportUploadStatus1"
    validate(begin["input"], dict(command_id=ID, filename="sources.zip",
                                 byte_length=6, sha256=HASH, envelope_version="3"))
    validate(begin["output"], status)
    rejected(begin["output"], status | {"native_store_id": ID})
    for key in ("upload_id", "operation_id"):
        rejected(begin["output"], {k:v for k,v in status.items() if k != key})
    chunk_route = next(r for r in routes if r["family"] == "import" and r["method"] == "PUT")
    Draft202012Validator({**S, **chunk_route["path_parameters"]}).validate(
        dict(upload_id=status["upload_id"], offset=status["received_bytes"]))
    chunk = dict(offset=status["received_bytes"], byte_length=status["expected_bytes"],
                 sha256=status["sha256"])
    validate(chunk_route["input"], chunk)
    receipt = chunk | dict(upload_id=status["upload_id"], next_offset=6)
    validate(chunk_route["output"], receipt)
    complete = next(r for r in routes if r["path"] == "document-imports/{upload_id}/complete")
    validate(complete["input"], dict(command_id=ID, upload_id=receipt["upload_id"],
                                     sha256=status["sha256"]))
    poll = next(r for r in routes if r["path"] == "document-imports/{operation_id}")
    Draft202012Validator({**S, **poll["path_parameters"]}).validate(
        {"operation_id": status["operation_id"]})


@pytest.mark.parametrize("kind", ["collection", "annotation"])
def test_documents_contracts_repair_reserved_creation_ids_cross_request_result_witness(kind):
    public = (dict(command_id=ID, title="Sources", description="References")
              if kind == "collection" else
              dict(command_id=ID, locator={"kind":"original_file"}, text="Note", tags=[]))
    public_type = "DocumentCollectionCreate1" if kind == "collection" else "DocumentAnnotationCreate1"
    validate(public_type, public)
    rejected(public_type, public | {kind+"_id": OTHER})
    internal = {kind+"_id":OTHER, "request":public}
    if kind == "annotation":
        internal["version_id"] = THIRD25R
    frame = dict(mode="document-write", verb=kind+"_create", identity=IDENTITY25R, input=internal)
    validate("DocumentBridgeWrite1", frame)
    rejected("DocumentBridgeWrite1", frame | {"input": internal | {"native_uuid": ID}})
    rejected("DocumentBridgeWrite1", frame | {"input": {k:v for k,v in internal.items() if k != kind+"_id"}})
    result = (dict(schema_version="1", collection_id=internal["collection_id"], study_id=ID,
                   title=public["title"], description=public["description"], revision=1,
                   lifecycle="active", member_count=0)
              if kind == "collection" else
              dict(schema_version="1", annotation_id=internal["annotation_id"],
                   version_id=internal["version_id"], study_id=ID, revision=1,
                   locator=public["locator"], text=public["text"], tags=public["tags"],
                   created_by=ID, updated_by=ID, created_at=AT25R, updated_at=AT25R))
    reply = {k:v for k,v in frame.items() if k != "input"} | {"result":result}
    validate("DocumentBridgeWriteReply1", reply)
    witness = witness25r(kind+"_create", {kind+"_id": internal[kind+"_id"]}, reply["result"])
    validate("DocumentNativeWitness1", witness)
    validate("DocumentBridgeWriteReply1", reply | {"verb":"reconcile", "result":witness})
    assert witness["reserved_ids"][kind+"_id"] == witness["result"][kind+"_id"]
    assert witness["identity"] == frame["identity"]
    rejected("DocumentNativeWitness1", witness | {"reallocated_id":ID})


@pytest.mark.parametrize("kind", ["initial", "retry"])
def test_documents_contracts_repair_extraction_preserves_explicit_retry_lineage(kind):
    request = dict(command_id=ID, policy_id="documents-text-v1")
    if kind == "retry":
        request["prior_attempt_id"] = THIRD25R
    internal = dict(kind=kind, version_id=ID, attempt_id=OTHER, request=request)
    frame = dict(mode="document-write", verb="extraction_start", identity=IDENTITY25R, input=internal)
    validate("DocumentBridgeWrite1", frame)
    rejected("DocumentBridgeWrite1", frame | {"input":internal | {"kind":"retry" if kind=="initial" else "initial"}})
    rejected("DocumentBridgeWrite1", frame | {"input":{k:v for k,v in internal.items() if k != "kind"}})
    if kind == "retry":
        rejected("DocumentBridgeWrite1", frame | {"input":internal | {"request":{k:v for k,v in request.items() if k!="prior_attempt_id"}}})
    attempt = dict(schema_version="1", attempt_id=internal["attempt_id"],
        version_id=internal["version_id"], study_id=ID, original_sha256=HASH,
        extractor=EXTRACTOR25R, state="queued", wrapper_state="not_started",
        result_id=None, retry_of=request.get("prior_attempt_id"), created_by=ID, created_at=AT25R)
    reply = dict(mode="document-write", verb="extraction_start", identity=IDENTITY25R, result=attempt)
    validate("DocumentBridgeWriteReply1", reply)
    witness = witness25r("extraction", {"attempt_id":internal["attempt_id"]}, reply["result"])
    validate("DocumentNativeWitness1", witness)
    validate("DocumentBridgeWriteReply1", reply | {"verb":"reconcile", "result":witness})
    assert witness["result"]["retry_of"] == request.get("prior_attempt_id")
    assert witness["result"]["attempt_id"] == internal["attempt_id"]
    # Equality is a future adapter obligation, not provided by JSON Schema.
    validate("DocumentExtractionAttempt1", attempt | {"retry_of":ID})


@pytest.mark.parametrize("category", ["metadata", "archive"])
@pytest.mark.parametrize("origin", ["running", "interrupted", "uncertain"])
def test_documents_contracts_repair_app_only_commit_and_lost_reply_proof(category, origin):
    result = dict(schema_version="1", document_id=ID, study_id=ID, title="Sources",
        tags=[], archived=category=="archive", revision=2, head_version_id=OTHER,
        created_by=ID, created_at=AT25R)
    proof = dict(schema_version="documents-app-commit/1", identity=IDENTITY25R,
        category=category, reserved_ids={"document_id":ID}, result=result,
        previous_revision=1, resulting_revision=2)
    event = dict(category=category, **{"from":origin, "to":"committed"},
                 proof="verified_app_transaction", app_commit=proof)
    validate("DocumentOperationTransition1", event)
    validate("DocumentAppCommit1", proof)
    rejected("DocumentAppCommit1", proof | {"native_store_id":ID})
    rejected("DocumentAppCommit1", proof | {"result":{"collection_id":ID,"revision":2,"deleted":True,"originals_preserved":True}})
    rejected("DocumentOperationTransition1", event | {"category":"collection_create"})
    rejected("DocumentOperationTransition1", event | {"category":"metadata" if category=="archive" else "archive"})
    rejected("DocumentOperationTransition1", {k:v for k,v in event.items() if k!="app_commit"})
    native = witness25r(category, {"document_id":ID}, result)
    rejected("DocumentOperationTransition1", dict(category=category,
        **{"from":origin,"to":"committed"},proof="verified_native_witness",witness=native))
    assert proof["result"]["document_id"] == proof["reserved_ids"]["document_id"]


@pytest.mark.parametrize("origin", ["running", "interrupted", "uncertain"])
def test_documents_contracts_repair_native_commit_keeps_exact_witness(origin):
    result = dict(collection_id=OTHER, revision=2, deleted=True, originals_preserved=True)
    witness = witness25r("collection_delete", {"collection_id":OTHER}, result)
    event = dict(category="collection_delete", **{"from":origin, "to":"committed"},
                 proof="verified_native_witness", witness=witness)
    validate("DocumentOperationTransition1", event)
    rejected("DocumentOperationTransition1", event | {"category":"annotation_delete"})
    rejected("DocumentOperationTransition1", event | {"proof":"verified_app_transaction"})
    rejected("DocumentOperationTransition1", event | {"app_commit":witness})
    rejected("DocumentOperationTransition1", {k:v for k,v in event.items() if k!="witness"})


@pytest.mark.parametrize("outcome", ["unsupported", "needs_transcription"])
def test_documents_contracts_repair_uncertain_extraction_recovers_exact_terminal_outcome(outcome):
    policy = dict(policy_id="documents-text-v1", encoding="utf-8", newlines="lf",
        positions="unicode_codepoints", original_max_bytes=10485760,pdf_max_pages=500,
        page_max_bytes=262144,total_max_bytes=8388608)
    result = dict(schema_version="1", extraction_id=THIRD25R, attempt_id=OTHER,
        version_id=ID, study_id=ID, original_sha256=HASH, extractor=EXTRACTOR25R,
        manifest_sha256=HASH, policy=policy, outcome=outcome,
        page_count=None, pages=[], total_text_bytes=0)
    event = dict(attempt_id=OTHER, **{"from":"uncertain","to":outcome},
                 proof="verified_exact_retained_result", result=result)
    assert outcome in S["x-hyprn-mvp-documents-contract"]["extraction_transitions"]["uncertain"]
    validate("DocumentExtractionReconciliation1", event)
    rejected("DocumentExtractionReconciliation1", event | {"proof":"timeout"})
    rejected("DocumentExtractionReconciliation1", event | {"to":"complete"})
    rejected("DocumentExtractionReconciliation1", event | {"to":"queued"})
    rejected("DocumentExtractionReconciliation1", event | {"retry":True})
    rejected("DocumentExtractionReconciliation1", {k:v for k,v in event.items() if k!="result"})
    attempt = dict(schema_version="1", attempt_id=event["attempt_id"], version_id=ID,
        study_id=ID,original_sha256=HASH,extractor=EXTRACTOR25R,state=event["to"],
        wrapper_state="finished",result_id=result["extraction_id"],retry_of=None,
        created_by=ID,created_at=AT25R)
    validate("DocumentExtractionAttempt1", attempt)
    assert attempt["state"] == result["outcome"]
    assert attempt["attempt_id"] == result["attempt_id"]
    assert S["x-hyprn-mvp-documents-contract"]["extraction_transitions"][outcome] == []

DOCS25_2_PRESERVED_NAMES = ['DocumentCitation1', 'EvidenceCreate4', 'EvidenceRevise4', 'EvidenceRecord4', 'EvidenceSnapshot4', 'EvidenceCreateRead4', 'EvidenceReviseRead4', 'EvidenceRecordRead4', 'EvidenceSnapshotRead4', 'EvidenceFamily4', 'EvidencePage2', 'EvidenceCitationPreviewRequest4', 'EvidenceCitationPreview4', 'ConfigurationRequest5', 'ConfigurationCandidate5', 'ConfigurationRevision5', 'ConfigurationPreview5', 'ConfigurationCommit5', 'ModelingConfiguration4', 'ModelingConfigurationRevision4', 'ConfigurationCandidateRead5', 'ConfigurationRevisionRead5', 'ConfigurationRequestRead5', 'ConfigurationPreviewRead5', 'ConfigurationCommitRead5', 'ApproachClosure2', 'ApproachResolution2', 'ApproachSaved2', 'ApproachClosureRead2', 'ApproachClosure2Model2Only', 'ApproachClosure2WithModel3', 'ApproachClosureModel2Read2', 'ApproachClosureWithModel3Read2', 'FrozenConfiguration6Model3', 'FrozenConfiguration6Model2', 'FrozenConfiguration6Model2WithModel3', 'FrozenConfiguration6', 'RunHistory5Model3', 'RunHistory5Model2', 'RunHistory5Model2WithModel3', 'RunHistory5', 'ModifiedRunSeed5Model3', 'ModifiedRunSeed5Model2', 'ModifiedRunSeed5Model2WithModel3', 'ModifiedRunSeed5', 'ExecutionBundle7Model3', 'ExecutionBundle7Model2', 'ExecutionBundle7', 'FrozenConfigurationRead6', 'ExecutionBundleRead7', 'RunHistoryRead5', 'ModifiedRunSeedRead5', 'ApproachVersionSaved2', 'ApproachPreview2', 'AssumptionEvidenceResolution2']

def test_documents_citation_contracts_repair_preserves_all_scientific_allocations():
    for schema in SCHEMAS:
        definitions = {n:schema["$defs"][n] for n in DOCS25_2_PRESERVED_NAMES}
        assert len(definitions) == 55
        assert hashlib.sha256(json.dumps(definitions,sort_keys=True,separators=(",",":")).encode()).hexdigest() == '5f6188220868112ab9094367aa6d6f0096c6c54d6c8a7d7000c8cdd7056e685e'
