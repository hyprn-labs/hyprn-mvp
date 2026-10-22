"""Compiled workspace over real hosted HTTPS/session/PostgreSQL boundaries."""

import json
from pathlib import Path
import subprocess
import sys

import foundry_ui_fixture as foundry
import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]
SPEC = 'hosted-identity.spec.ts'


def run():
    scope = guard.scope_from_environment()
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('Hosted browser requires reviewed application interpreter')
    sys.path.insert(0, str(REPO / 'application/src'))
    from hosted_fixture import hosted_http

    evidence = guard.scoped_path(scope, 'evidence')
    dist = guard.scoped_path(scope, 'artifacts/hosted-dist')
    env = guard.clean_environment(scope)
    built = subprocess.run(
        [
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
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    (evidence / 'build.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise ValueError('Hosted workspace build failed')
    with hosted_http(guard.scoped_path(scope, 'artifacts'), dist=dist) as hosted:
        config = foundry.browser_config(scope)
        config['testMatch'] = [SPEC]
        config['use'].update(baseURL=hosted['origin'], ignoreHTTPSErrors=True)
        chromium = env.get('HYPRN_MVP_CHROMIUM')
        if chromium:
            config['projects'] = [
                dict(
                    name='chromium',
                    use=dict(browserName='chromium', launchOptions=dict(executablePath=chromium)),
                )
            ]
        config_path = guard.scoped_path(scope, 'artifacts/hosted-playwright.config.mjs')
        config_path.write_text('export default ' + json.dumps(config) + ';\n')
        # Synthetic signed credentials live only in the child environment; never logs/traces.
        env.update(
            HYPRN_HOSTED_TEST_A=hosted['assertion']('browser-a', email='alice@example.invalid'),
            HYPRN_HOSTED_TEST_B=hosted['assertion']('browser-b', email='bob@example.invalid'),
        )
        tested = subprocess.run(
            [
                'node',
                str(REPO / 'ui/node_modules/playwright/cli.js'),
                'test',
                '--config',
                str(config_path),
                '--reporter=json',
            ],
            cwd=REPO / 'ui',
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        key_id = hosted['key_id']
    (evidence / 'browser-report.json').write_text(tested.stdout)
    (evidence / 'browser-stderr.log').write_text(tested.stderr)
    try:
        report = json.loads(tested.stdout[tested.stdout.index('{') :])
        stats = report['stats']
    except (ValueError, KeyError):
        report, stats = {}, {}
    passed = (
        tested.returncode == 0
        and stats.get('expected', 0) > 0
        and foundry.spec_files(report) == {SPEC}
        and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky'))
    )
    record = dict(
        group='hosted-ui',
        passed=passed,
        tests=stats.get('expected', 0),
        failures=stats.get('unexpected', 0),
        skipped=stats.get('skipped', 0),
        fixture_key_id=key_id,
        server_stopped=True,
        postgres_removed=True,
    )
    (evidence / 'tests.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record))
    if not passed:
        print(tested.stdout)
    return 0 if passed else 1
