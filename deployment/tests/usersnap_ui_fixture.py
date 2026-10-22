"""Real application HTTP/static policy with a browser-owned vendor double."""

from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import foundry_ui_fixture as foundry
import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]
SPEC = 'usersnap.spec.ts'


def run():
    scope = guard.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('Usersnap browser group requires the reviewed application interpreter')
    sys.path.insert(0, str(REPO / 'application/src'))
    import uvicorn
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.auth import Auth
    from hyprn_mvp_app.store import Store
    from hyprn_mvp_app.ui import WorkspaceFiles

    evidence = guard.scoped_path(scope, 'evidence')
    dist = guard.scoped_path(scope, 'artifacts/usersnap-dist')
    env = guard.clean_environment(scope)
    build = [
        'node',
        str(REPO / 'ui/node_modules/vite/bin/vite.js'),
        'build',
        str(REPO / 'ui'),
        '--config',
        str(REPO / 'ui/vite.config.ts'),
        '--configLoader',
        'runner',
        '--outDir',
        str(dist),
    ]
    built = subprocess.run(build, cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    (evidence / 'fixture-build.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise ValueError('Usersnap fixture build failed; see fixture-build.log')
    server = None
    thread = None
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        scope = replace(scope, url=f'http://127.0.0.1:{listener.getsockname()[1]}')
        guard.validate_url(scope.url)
        (scope.root / 'scope.json').write_text(json.dumps(scope.record()))
        env = guard.clean_environment(scope)
        store = Store(guard.scoped_path(scope, 'artifacts/usersnap.sqlite'))
        auth = Auth(store, scope.url)
        auth.provision('owner', 'correct horse battery staple')
        app = create_app(store, auth, None)
        app.mount(
            '/ui',
            WorkspaceFiles(
                directory=dist, html=True, usersnap_global_id='9c4a930c-b62f-4b89-bca3-260ec022694a'
            ),
        )
        app.mount('/disabled', WorkspaceFiles(directory=dist, html=True))
        config = foundry.browser_config(scope)
        config['testMatch'] = [SPEC]
        config['use']['baseURL'] = scope.url
        chromium = env.get('HYPRN_MVP_CHROMIUM')
        if chromium:
            config['projects'] = [
                dict(
                    name='chromium',
                    use=dict(browserName='chromium', launchOptions=dict(executablePath=chromium)),
                )
            ]
        config_path = guard.scoped_path(scope, 'artifacts/usersnap-playwright.config.mjs')
        config_path.write_text('export default ' + json.dumps(config) + ';\n')
        command = [
            'node',
            str(REPO / 'ui/node_modules/playwright/cli.js'),
            'test',
            '--config',
            str(config_path),
            '--update-snapshots=none',
            '--reporter=json',
        ]
        try:
            server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
            thread = threading.Thread(
                target=server.run, kwargs={'sockets': [listener]}, daemon=True
            )
            thread.start()
            deadline = time.monotonic() + 15
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise ValueError('Scoped Usersnap HTTP server failed to start')
            tested = subprocess.run(
                command, cwd=REPO / 'ui', env=env, capture_output=True, text=True, timeout=600
            )
        finally:
            if server:
                server.should_exit = True
            if thread:
                thread.join(timeout=15)
                if thread.is_alive():
                    raise ValueError('Scoped Usersnap HTTP server did not stop')
    (evidence / 'browser-report.json').write_text(tested.stdout)
    (evidence / 'browser-stderr.log').write_text(tested.stderr)
    try:
        report = json.loads(tested.stdout[tested.stdout.index('{') :])
        stats = report['stats']
    except (ValueError, KeyError):
        report, stats = {}, {}
    files = foundry.spec_files(report)
    forbidden = [n for n in sys.modules if n.split('.')[0] in {'aiida', 'openmdao', 'openturns'}]
    passed = (
        tested.returncode == 0
        and stats.get('expected', 0) > 0
        and files == {SPEC}
        and not forbidden
        and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky'))
    )
    record = dict(
        group='usersnap-ui',
        passed=passed,
        tests=stats.get('expected', 0) + stats.get('unexpected', 0),
        failures=stats.get('unexpected', 0),
        skipped=stats.get('skipped', 0),
        flaky=stats.get('flaky', 0),
        spec_files=sorted(files),
        command=command,
        build_command=build,
        native_imports=forbidden,
        server_stopped=True,
        fixture=(
            'Actual application HTTP, auth and WorkspaceFiles; compiled UI; '
            'vendor double only; no provider submission'
        ),
    )
    (evidence / 'tests.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return 0 if passed else 1
