"""Closed isolated browser groups on the Foundry in-browser double.

Builds the current ui/ into this guarded scope and runs exactly the specs registered
for the group: 'foundry-nav' (model, configuration and run screens, and zoom),
'ported-isolated' (command recovery and history races, never against a served
installation), 'ui-navigation' (shell and study navigation state), 'ui-reading'
(readable values, records, evidence and labels) and the opt-in 'ui-fidelity' (visual
comparison with the design-system reference images). Every API request is the
declared in-browser double in ui/tests/foundry-fixtures.ts, served from a test-owned
ephemeral loopback socket, or a pure client double. No application, modeling, native
process or live runtime is started or contacted, and no Python test module is imported.
"""
import json
from pathlib import Path
import subprocess
import sys

import scoped_fixture as guard

REPO = Path(__file__).resolve().parents[2]
GROUP_SPECS = {
    'foundry-nav': ('model-configuration-run.spec.ts', 'foundry-zoom.spec.ts'),
    'ported-isolated': ('command-recovery.spec.ts', 'history-races-isolated.spec.ts'),
    'ui-navigation': ('study-navigation.spec.ts',),
    'ui-reading': ('screen-readability.spec.ts', 'evidence-workspace.spec.ts', 'record-labels.spec.ts'),
    'ui-fidelity': ('prototype-fidelity.spec.ts',),
}
SPECS = GROUP_SPECS['foundry-nav']
BUILD = 'artifacts/nav-dist'
EVIDENCE = 'evidence/nav'


def browser_environment(scope):
    """Exact guarded environment plus the two scope-bound paths the specs require."""
    env = guard.clean_environment(scope)
    env.update(HYPRN_MVP_NAV_BUILD=str(guard.scoped_path(scope, BUILD)),
               HYPRN_MVP_UI_EVIDENCE_ROOT=str(guard.scoped_path(scope, EVIDENCE)))
    return env


def browser_config(scope, group='foundry-nav'):
    """Import-free Playwright config fixed to the group's specs; outputs stay in the scope."""
    evidence = guard.scoped_path(scope, 'evidence')
    return dict(testDir=str(REPO / 'ui/tests'), testMatch=list(GROUP_SPECS[group]), forbidOnly=True, workers=1, retries=0,
                timeout=45000, expect=dict(timeout=8000), outputDir=str(evidence / 'browser'),
                snapshotPathTemplate=str(evidence / 'snapshots') + '/{arg}{ext}', reporter=[['list']],
                use=dict(actionTimeout=8000, viewport=dict(width=1440, height=1000), trace='off',
                         screenshot='only-on-failure'),
                projects=[dict(name='chromium', use=dict(browserName='chromium', channel='chrome'))])


def report_passed(returncode, stats, files, forbidden, group='foundry-nav'):
    """Fail closed: no zero selection, skip, flake, unexpected result or foreign/missing spec."""
    return (returncode == 0 and stats.get('expected', 0) > 0 and not forbidden
            and not any(stats.get(k, 0) for k in ('unexpected', 'skipped', 'flaky'))
            and bool(files) and set(files) == set(GROUP_SPECS[group]))


def spec_files(report):
    files = set()
    def walk(suite):
        for spec in suite.get('specs', []):
            files.add(spec.get('file'))
        for child in suite.get('suites', []):
            walk(child)
    for suite in report.get('suites', []):
        walk(suite)
    return files


def run(*, group):
    scope = guard.scope_from_environment()  # Before any build, write or browser start.
    if sys.executable != scope.interpreter or scope.interpreter != guard.APPROVED_CONTRACT_PYTHON:
        raise ValueError('Foundry browser group requires the reviewed application interpreter')
    if group not in GROUP_SPECS:
        raise ValueError('Unknown foundry browser group')
    env = browser_environment(scope)
    evidence = guard.scoped_path(scope, 'evidence')
    guard.scoped_path(scope, EVIDENCE).mkdir()
    stage = guard.scoped_path(scope, 'artifacts/nav-config')
    stage.mkdir()
    build = ['node', str(REPO / 'ui/node_modules/vite/bin/vite.js'), 'build', str(REPO / 'ui'),
             '--config', str(REPO / 'ui/vite.config.ts'), '--configLoader', 'runner',
             '--outDir', env['HYPRN_MVP_NAV_BUILD']]
    built = subprocess.run(build, cwd=REPO, env=env, capture_output=True, text=True, timeout=300)
    (evidence / 'fixture-build.log').write_text(built.stdout + built.stderr)
    if built.returncode:
        raise ValueError('Foundry fixture build failed; see fixture-build.log')
    config = stage / 'playwright.config.mjs'
    config.write_text('export default ' + json.dumps(browser_config(scope, group), indent=2) + ';\n')
    command = ['node', str(REPO / 'ui/node_modules/playwright/cli.js'), 'test', '--config', str(config),
               '--update-snapshots=none', '--reporter=json']
    tested = subprocess.run(command, cwd=REPO / 'ui', env=env, capture_output=True, text=True, timeout=600)
    (evidence / 'browser-report.json').write_text(tested.stdout)
    (evidence / 'browser-stderr.log').write_text(tested.stderr)
    try:
        report = json.loads(tested.stdout[tested.stdout.index('{'):])
        stats = report['stats']
    except (ValueError, KeyError):
        report, stats = {}, {}
    files = spec_files(report)
    forbidden = [n for n in sys.modules if n.split('.')[0] in {'aiida', 'openmdao', 'openturns'}]
    passed = report_passed(tested.returncode, stats, files, forbidden, group)
    record = dict(group=group, passed=passed, tests=stats.get('expected', 0) + stats.get('unexpected', 0),
                  failures=stats.get('unexpected', 0), skipped=stats.get('skipped', 0), flaky=stats.get('flaky', 0),
                  spec_files=sorted(f for f in files if f), command=command, build_command=build,
                  native_imports=forbidden,
                  fixture='Current ui build in scope; declared in-browser foundry API double; no application, modeling, native or live service')
    (evidence / 'tests.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    return 0 if passed else 1
