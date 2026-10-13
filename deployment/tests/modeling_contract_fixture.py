"""The backend-independent modeling contract suite against private services owned by the test scope.

Two guarded private services (units_model_fixture.PrivateModel: scope-labelled, no network, no
published port, read-only image on the pinned producer image) stand behind the suite's
``private://modeling`` and ``private://modeling-import`` transports for the whole session. Their
names and credentials exist only inside the scope; nothing names an installation's service.
Test modules load this module with ``pytest_plugins`` so that one pair serves the session.
"""
import os
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import scoped_fixture as guard  # noqa: E402

VARIABLES = ('HYPRN_MVP_MODEL_URL', 'HYPRN_MVP_MODEL_KEY_FILE', 'HYPRN_MVP_MODEL_IMPORT_URL',
             'HYPRN_MVP_MODEL_IMPORT_KEY_FILE', 'HYPRN_MVP_MODEL_IMPORT_CONTAINER', 'HYPRN_MVP_MODEL_CONTAINER')


@pytest.fixture(scope='session', autouse=True)
def modeling_contract_services():
    from units_model_fixture import PrivateModel
    import deployment.tests.model_client as transport
    previous = {name: os.environ.get(name) for name in VARIABLES}, transport.CONTAINER
    source = target = None
    try:
        source = PrivateModel()
        target = PrivateModel()
        for service in (source, target):
            if not service.name.startswith(guard.SCOPE_PREFIX + service.scope.run_uuid[:8]):
                raise ValueError('Modeling contract service outside the test scope')
        os.environ.update({
            'HYPRN_MVP_MODEL_URL': 'private://modeling',
            'HYPRN_MVP_MODEL_KEY_FILE': str(source.stage / 'model.key'),
            'HYPRN_MVP_MODEL_CONTAINER': source.name,
            'HYPRN_MVP_MODEL_IMPORT_URL': 'private://modeling-import',
            'HYPRN_MVP_MODEL_IMPORT_KEY_FILE': str(target.stage / 'model.key'),
            'HYPRN_MVP_MODEL_IMPORT_CONTAINER': target.name,
        })
        transport.CONTAINER = source.name
        yield source, target
    finally:
        transport.CONTAINER = previous[1]
        for name, value in previous[0].items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        for service in (target, source):
            if service is not None:
                service.close()
