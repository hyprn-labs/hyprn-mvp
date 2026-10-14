"""Closed isolated browser group for the agent attribution and activity screens.

Builds the current ui/ into this guarded scope and runs exactly the specs registered for the
group 'agent-ui' on the in-browser agent double (ui/tests/agent-fixtures.ts, layered over the
foundry double of ui/tests/foundry-fixtures.ts), served from a test-owned ephemeral loopback
socket. No application, modeling, native process or live runtime is started or contacted, and
no Python test module is imported. The report fails closed: no zero selection, skip, flake,
unexpected result, or foreign or missing spec.
"""

import json
from pathlib import Path
import subprocess
import sys

import foundry_ui_fixture as foundry
import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]
GROUP_SPECS = {'agent-ui': ('agent-attribution.spec.ts',)}


def browser_config(scope, group='agent-ui'):
    """Import-free Playwright config fixed to the group's specs; outputs stay in the scope."""
    evidence = guard.scoped_path(scope, 'evidence')
    return dict(
        testDir=str(REPO / 'ui/tests'),
        testMatch=list(GROUP_SPECS[group]),
        forbidOnly=True,
        workers=1,
        retries=0,
        timeout=45000,
        expect=dict(timeout=8000),
        outputDir=str(evidence / 'browser'),
        snapshotPathTemplate=str(evidence / 'snapshots') + '/{arg}{ext}',
        reporter=[['list']],
        use=dict(
            actionTimeout=8000,
            viewport=dict(width=1440, height=1000),
            trace='off',
            screenshot='only-on-failure',
        ),
        projects=[dict(name='chromium', use=dict(browserName='chromium', channel='chrome'))],
    )


def report_passed(returncode, stats, files, forbidden, group='agent-ui'):
    """Fail closed: no zero selection, skip, flake, unexpected result or foreign/missing spec."""
    return (
        returncode == 0
        and stats.get('expected', 0) > 0
        and not forbidden
        and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky'))
        and bool(files)
        and set(files) == set(GROUP_SPECS[group])
    )


def run(*, group):
    scope = guard.scope_from_environment()  # Before any build, write or browser start.
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('Agent browser group requires the reviewed application interpreter')
    if group not in GROUP_SPECS:
        raise ValueError('Unknown agent browser group')
    env = foundry.browser_environment(scope)
    evidence = guard.scoped_path(scope, 'evidence')
    guard.scoped_path(scope, foundry.EVIDENCE).mkdir()
    stage = guard.scoped_path(scope, 'artifacts/agent-config')
    stage.mkdir()
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
        env['HYPRN_MVP_NAV_BUILD'],
    ]
    built = subprocess.run(build, cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    (evidence / 'fixture-build.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise ValueError('Agent fixture build failed; see fixture-build.log')
    config = stage / 'playwright.config.mjs'
    config.write_text(
        'export default ' + json.dumps(browser_config(scope, group), indent=2) + ';\n'
    )
    command = [
        'node',
        str(REPO / 'ui/node_modules/playwright/cli.js'),
        'test',
        '--config',
        str(config),
        '--update-snapshots=none',
        '--reporter=json',
    ]
    tested = subprocess.run(
        command, cwd=REPO / 'ui', env=env, capture_output=True, text=True, timeout=600
    )
    (evidence / 'browser-report.json').write_text(tested.stdout)
    (evidence / 'browser-stderr.log').write_text(tested.stderr)
    try:
        report = json.loads(tested.stdout[tested.stdout.index('{') :])
        stats = report['stats']
    except (ValueError, KeyError):
        report, stats = {}, {}
    files = foundry.spec_files(report)
    forbidden = [n for n in sys.modules if n.split('.')[0] in {'aiida', 'openmdao', 'openturns'}]
    passed = report_passed(tested.returncode, stats, files, forbidden, group)
    record = dict(
        group=group,
        passed=passed,
        tests=stats.get('expected', 0) + stats.get('unexpected', 0),
        failures=stats.get('unexpected', 0),
        skipped=stats.get('skipped', 0),
        flaky=stats.get('flaky', 0),
        spec_files=sorted(f for f in files if f),
        command=command,
        build_command=build,
        native_imports=forbidden,
        fixture='Current ui build in scope; declared in-browser agent API double over the '
        'foundry double; no application, modeling, native or live service',
    )
    (evidence / 'tests.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return 0 if passed else 1
