"""Historical preparation admits its own frozen identities, never current schemas."""

import base64
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from execution_fixtures import runtime_fixture
from hyprn_mvp_app.contracts import uid
from hyprn_mvp_app.execution_bundle import (
    assemble_bundle,
    validate_preparation,
    validate_retained_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / 'integration/tests/fixtures/native-programs-pre-schema-split.json.gz'
IDENTITIES = 'provenance/support/schema-identities.json'
PRIOR = [
    {
        'path': 'contracts/schemas/model.schema.json',
        'size': 1060581,
        'sha256': '8553e1ae0d3519014ca41b6dd00e2c4944ab6225ac3a02de6d9d7e8096f67b99',
    },
    {
        'path': 'contracts/schemas/execution.schema.json',
        'size': 1060585,
        'sha256': 'f8a25ccf1aa942536918497a59516d48dff80c7fbd6f3eeb5f4aa4565667b2fe',
    },
]


def test_artifact_prepared_with_earlier_schema_identities_stays_admissible():
    raw = CAPTURE.read_bytes()
    assert len(raw) == 2927542
    assert hashlib.sha256(raw).hexdigest() == (
        '3fdd2de1275704b7b3fa2a59a409ecaef00bb1f18ea13bfff7bd4325ae1ea018'
    )
    capture = json.loads(gzip.decompress(raw))
    case = capture['cases']['chain']
    files = {
        row['path']: base64.b64decode(capture['blobs'][row['sha256']], validate=True)
        for row in case['prepared']['files']
    }
    before = deepcopy(case), dict(files)
    recorded = files[IDENTITIES]
    assert len(recorded) == 395
    assert hashlib.sha256(recorded).hexdigest() == (
        '41d15d9cfdc0a8c679d3aec529c57c24744034616bdad6e1c9b692081e097c70'
    )
    assert json.loads(recorded) == {'schema_version': '1', 'schemas': PRIOR}
    # This module is data-only and does not import worker/launcher into the app interpreter.
    import modeling_runtime

    assert modeling_runtime.schema_identities() != json.loads(recorded)
    validate_preparation(case['prepared'], files, case['frozen'])
    bundle = assemble_bundle(
        uid(),
        case['prepared'],
        files,
        case['frozen'],
        runtime_fixture(),
        None,
    )
    manifest = bundle['manifest']
    request = {
        'run_id': manifest['run_id'],
        'scope': case['frozen']['configuration']['study_id'],
        'command_id': uid(),
        'payload_digest': 'a' * 64,
        'bundle_digest': manifest['bundle_digest'],
    }
    validate_retained_bundle(bundle, request, case['frozen'])
    code = """
import base64, json, sys
sys.path.insert(0, sys.argv[1])
from hyprn_mvp_integration.worker import verify_unit_catalog
payload = json.load(sys.stdin)
files = {name: base64.b64decode(raw, validate=True) for name, raw in payload['files'].items()}
verify_unit_catalog(payload['manifest'], files, payload['prepared'],
                    payload['model'], payload['configuration'])
print('retained provenance accepted')
"""
    payload = {
        'manifest': manifest,
        'files': {
            name: base64.b64encode(value).decode() for name, value in bundle['files'].items()
        },
        'prepared': case['prepared'],
        'model': case['frozen']['model_snapshot'],
        'configuration': case['frozen']['configuration'],
    }
    result = subprocess.run(
        [sys.executable, '-B', '-c', code, str(ROOT / 'integration/src')],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'retained provenance accepted'
    assert (case, files) == before
    assert CAPTURE.read_bytes() == raw
    assert files[IDENTITIES] == recorded
    assert (
        not {'hyprn_mvp_integration.worker', 'hyprn_mvp_integration.launcher'} & sys.modules.keys()
    )
