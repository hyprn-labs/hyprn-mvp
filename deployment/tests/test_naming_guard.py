"""Structural namespace guard: every product name in the repository uses the hyprn-mvp namespace.

Checks (each over the tracked files, as listed by ``git ls-files``):

- ``packages``: every top-level package under application/src, integration/src and
  editions/*/src is ``hyprn_mvp_*``;
- ``old_packages``: no tracked Python, TypeScript, JavaScript, Dockerfile, YAML, JSON or TOML
  file imports or names the previous application or integration package or distribution. A
  leftover name would not fail an import: an interpreter whose path still reaches an older
  checkout would silently load that checkout's code instead;
- ``environment``: every environment variable read or set by product code and tests is
  ``HYPRN_MVP_*`` or one of the closed standard and tool variables below, and no string
  literal names a product-prefixed variable outside ``HYPRN_MVP_``;
- ``labels``: every container label key starts with ``org.hyprn-mvp.``;
- ``container_names``: no container, network, image or project name built by a manager
  uses the previous product prefix (they start with ``hyprn-mvp-``);
- ``contracts``: the contract files are exactly contracts/hyprn-mvp.openapi.yaml and
  contracts/modeling.openapi.yaml;
- ``openapi_extensions``: every OpenAPI extension key starts with ``x-hyprn-mvp-``;
- ``work_item_names``: no file, group, test function or browser tag name carries a numbered
  work-item reference, and no tracked content carries a numbered phase identifier.

Every searched literal is assembled at run time from fragments, so this file never contains
what it searches for. Every check must find nothing: there is no exemption list.
"""
# Live-runtime fence (deployment/tests/live_fence.py): refuses live roots, live ports, docker, live entry points and real signals.
import sys as _fence_sys
from pathlib import Path as _FencePath
if str(_FencePath(__file__).resolve().parent) not in _fence_sys.path:
    _fence_sys.path.append(str(_FencePath(__file__).resolve().parent))
import live_fence  # noqa: E402
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')
from pathlib import Path  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import unittest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
# Searched fragments, assembled at run time.
OLD = 'hyper' + 'ion'
ITEM = 'phase' + '02'
NEW_PACKAGE = 'hyprn' + '_mvp_'
NEW_VARIABLE = 'HYPRN' + '_MVP_'
NEW_LABEL = 'org.' + 'hyprn-mvp.'
NEW_EXTENSION = 'x-' + 'hyprn-mvp-'
CONTRACT_FILES = frozenset({'contracts/' + 'hyprn-mvp' + '.openapi.yaml', 'contracts/modeling.openapi.yaml'})
# Closed lists: standard variables, and tool variables that belong to a third-party tool.
STANDARD_VARIABLES = frozenset({'HOME', 'PATH', 'TMPDIR', 'DOCKER_HOST', 'CI', 'LANG',
                                'WSL_DISTRO_NAME'})  # set by Windows Subsystem for Linux
STANDARD_PREFIXES = ('XDG_', 'PLAYWRIGHT_', 'LC_')
TOOL_VARIABLES = frozenset({
    'AIIDA_PATH',  # AiiDA configuration folder of the scoped native profile
    'PYTEST_DISABLE_PLUGIN_AUTOLOAD', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE',
})
TOOL_PREFIXES = ('COMPOSE_',)  # Docker Compose settings a manager must refuse to inherit
SOURCE_SUFFIXES = ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs')
EXCLUDED_PREFIXES = ('.planning/', 'upstream/')

# Work-item references in names: numbered phases, review checkpoints (C4), plan-step codes
# (P4-S6), dotted plan numbers written as 01-09, and task, wave and documents-route numbers.
WORK_ITEM = re.compile('(?i)(?:' + '|'.join((
    'phase' + r'[-_ ]?\d+',
    r'(?:^|[-_./])c\d+(?=[-_.]|$)',
    r'(?:^|[-_./])p\d+[-_]s\d+',
    r'(?:^|[-_./])\d{2}[-_]\d{2}(?=[-_.]|$)',
    'task' + r'[-_]?\d+',
    'wave' + r'[-_]?\d+',
    'docs' + r'[-_]\d+[-_]\d+',
)) + ')')
WORK_ITEM_CONTENT = re.compile('(?i)' + 'phase' + r'[-_]?\d+')

def tracked():
    result = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z'], capture_output=True, check=True, timeout=120)
    return [item.decode() for item in result.stdout.split(b'\0') if item]


def text(relative):
    path = REPO / relative
    if path.is_symlink() or not path.is_file():
        return None
    raw = path.read_bytes()
    if b'\0' in raw[:8192]:
        return None
    return raw.decode('utf-8', errors='replace')


def add(findings, path, finding):
    findings.setdefault(path, set()).add(finding)


OLD_PACKAGE = re.compile(r'(?<![A-Za-z0-9])' + OLD + r'[-_](?:app|integration)(?![A-Za-z0-9])')
OLD_PACKAGE_SUFFIXES = ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.yaml', '.yml', '.json', '.toml')


def old_package_findings(files):
    findings = {}
    for relative in files:
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        if not (relative.endswith(OLD_PACKAGE_SUFFIXES) or relative.rsplit('/', 1)[-1].endswith('Dockerfile')):
            continue
        if OLD_PACKAGE.search(relative):
            add(findings, relative, 'path')
        content = text(relative)
        if content is None:
            continue
        for match in OLD_PACKAGE.finditer(content):
            add(findings, relative, match.group(0))
    return findings


def package_findings(files):
    findings = {}
    roots = ('application/src/', 'integration/src/')
    for relative in files:
        parts = relative.split('/')
        if relative.startswith(roots) and len(parts) >= 3:
            root, name = '/'.join(parts[:2]), parts[2]
        elif relative.startswith('editions/') and len(parts) >= 4 and parts[2] == 'src':
            root, name = '/'.join(parts[:3]), parts[3]
        else:
            continue
        package = name[:-3] if name.endswith('.py') and len(parts) == len(root.split('/')) + 1 else name
        if not package.startswith(NEW_PACKAGE):
            add(findings, root + '/' + package, package)
    return findings


READS = re.compile(r"""(?:environ(?:\.get|\.pop|\.setdefault)?\s*[\(\[]|getenv\(|setenv\(|delenv\()\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]""")
PROCESS_ENV = re.compile(r"""process\.env(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\])""")
PREFIXED = re.compile('[\'"`]((?:' + 'HYPRN' + '|' + OLD.upper() + r')_[A-Z0-9_]+)[\'"`]')


def allowed_variable(name):
    return (name.startswith(NEW_VARIABLE) or name in STANDARD_VARIABLES or name in TOOL_VARIABLES
            or name.startswith(STANDARD_PREFIXES) or name.startswith(TOOL_PREFIXES))


def environment_findings(files):
    findings = {}
    for relative in files:
        if relative.startswith(EXCLUDED_PREFIXES) or not relative.endswith(SOURCE_SUFFIXES):
            continue
        content = text(relative)
        if content is None:
            continue
        names = [m.group(1) for m in READS.finditer(content)] if relative.endswith('.py') else []
        names += [m.group(1) or m.group(2) for m in PROCESS_ENV.finditer(content)]
        names += [m.group(1) for m in PREFIXED.finditer(content)]
        for name in names:
            if not allowed_variable(name):
                add(findings, relative, name)
    return findings


LABEL = re.compile(r'(?<![A-Za-z0-9_.-])org\.([a-z0-9-]+)\.[a-z0-9_-]')


def label_findings(files):
    findings = {}
    for relative in files:
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        content = text(relative)
        if content is None:
            continue
        for match in LABEL.finditer(content):
            if 'org.' + match.group(1) + '.' != NEW_LABEL:
                add(findings, relative, 'org.' + match.group(1) + '.')
    return findings


MANAGER_NAME = re.compile('[\'"](' + OLD + r'-[A-Za-z0-9_.:-]*)')


def manager_file(relative):
    parts = relative.split('/')
    return ((parts[0] == 'deployment' and len(parts) == 2 and relative.endswith(('.py', '.yaml', '.json', '.Dockerfile', '.rb', '.sh')))
            or (relative.startswith(('integration/src/', 'application/src/')) and relative.endswith('.py')))


def container_name_findings(files):
    findings = {}
    for relative in files:
        if not manager_file(relative):
            continue
        content = text(relative)
        if content is None:
            continue
        for match in MANAGER_NAME.finditer(content):
            add(findings, relative, match.group(1))
    return findings


def contract_findings(files):
    findings = {}
    present = {f for f in files if f.startswith('contracts/') and f.count('/') == 1 and f.endswith('.openapi.yaml')}
    for relative in present - CONTRACT_FILES:
        add(findings, relative, 'unexpected contract file')
    for relative in CONTRACT_FILES - present:
        add(findings, relative, 'missing contract file')
    return findings


EXTENSION = re.compile(r'''(?:^|[\s{,'"])(x-[A-Za-z0-9][A-Za-z0-9-]*)['"]?\s*:''', re.M)
# Generators also emit HTTP header names (x-...); only product-namespaced extensions are theirs.
QUOTED_EXTENSION = re.compile(r'''['"](x-(?:''' + OLD + r'''|hyprn)-[a-z0-9-]*)['"]''')


def extension_findings(files):
    findings = {}
    for relative in files:
        contract = relative.startswith('contracts/') and relative.endswith(('.yaml', '.yml', '.json'))
        generator = relative.startswith(('application/src/', 'application/generate')) and relative.endswith('.py')
        if not (contract or generator):
            continue
        content = text(relative)
        if content is None:
            continue
        names = [m.group(1) for m in EXTENSION.finditer(content)] if contract else []
        names += [m.group(1) for m in QUOTED_EXTENSION.finditer(content)] if generator else []
        for name in names:
            if not name.startswith(NEW_EXTENSION):
                add(findings, relative, name)
    return findings


TEST_FUNCTION = re.compile(r'^\s*(?:async\s+)?def\s+(test_\w+)', re.M)
BROWSER_TAG = re.compile(r'''['"`][^'"`\n]*?(?<![\w.@/])@([a-z][a-z0-9]*(?:-[a-z0-9]+)*)''')


def group_names():
    sys.path.insert(0, str(REPO / 'deployment'))
    import checks
    return set(checks.GROUPS) | {'qualification'}


def work_item_findings(files):
    findings = {}
    for relative in files:
        for part in relative.split('/'):
            if WORK_ITEM.search(part):
                add(findings, relative, 'file name ' + part)
        if relative.startswith('.planning/'):
            continue
        content = text(relative)
        if content is None:
            continue
        for match in WORK_ITEM_CONTENT.finditer(content):
            add(findings, relative, 'identifier ' + match.group(0))
        if relative.endswith('.py'):
            for name in TEST_FUNCTION.findall(content):
                if WORK_ITEM.search(name):
                    add(findings, relative, 'test function ' + name)
        if relative.startswith('ui/tests/') and relative.endswith(('.ts', '.tsx')):
            for tag in BROWSER_TAG.findall(content):
                if WORK_ITEM.search(tag):
                    add(findings, relative, 'browser tag @' + tag)
    for group in group_names():
        if WORK_ITEM.search(group):
            add(findings, 'deployment/checks.py', 'group ' + group)
    return findings


CHECKS = {
    'packages': package_findings,
    'old_packages': old_package_findings,
    'environment': environment_findings,
    'labels': label_findings,
    'container_names': container_name_findings,
    'contracts': contract_findings,
    'openapi_extensions': extension_findings,
    'work_item_names': work_item_findings,
}


def inventory():
    files = tracked()
    return {check: {path: sorted(found) for path, found in function(files).items()} for check, function in CHECKS.items()}


class NamingGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = inventory()

    def assert_clean(self, check):
        self.assertEqual(self.inventory[check], {}, check + ': violations')

    def test_packages_use_the_product_namespace(self):
        self.assert_clean('packages')

    def test_no_file_imports_or_names_the_previous_packages(self):
        self.assert_clean('old_packages')

    def test_environment_variables_use_the_product_prefix_or_a_closed_standard_list(self):
        self.assert_clean('environment')

    def test_container_labels_use_the_product_namespace(self):
        self.assert_clean('labels')

    def test_manager_container_network_and_image_names_use_the_product_prefix(self):
        self.assert_clean('container_names')

    def test_contract_files_are_the_product_and_modeling_contracts(self):
        self.assert_clean('contracts')

    def test_openapi_extension_keys_use_the_product_namespace(self):
        self.assert_clean('openapi_extensions')

    def test_no_name_carries_a_numbered_work_item_reference(self):
        self.assert_clean('work_item_names')

    def test_detectors_flag_synthetic_violations(self):
        files = ['application/src/' + OLD + '_app/__init__.py', 'application/src/' + NEW_PACKAGE + 'app/__init__.py',
                 'editions/local/src/' + NEW_PACKAGE + 'local/__init__.py', 'editions/local/src/other/__init__.py']
        self.assertEqual(set(package_findings(files)), {'application/src/' + OLD + '_app', 'editions/local/src/other'})
        sources = {'a.py': 'from ' + OLD + '_app.store import Store', 'b.toml': 'name = "' + OLD + '-integration"',
                   'deployment/c.Dockerfile': 'COPY x /opt/' + OLD + '_integration/x', 'd.py': 'from hyprn_mvp_app import api',
                   'e.md': 'import ' + OLD + '_app', 'f.py': OLD + '_application_runtime ' + OLD + '-apps'}
        found = {}
        for name, source in sources.items():
            if name.endswith(OLD_PACKAGE_SUFFIXES) or name.endswith('Dockerfile'):
                for match in OLD_PACKAGE.finditer(source):
                    found.setdefault(name, []).append(match.group(0))
        self.assertEqual(found, {'a.py': [OLD + '_app'], 'b.toml': [OLD + '-integration'],
                                 'deployment/c.Dockerfile': [OLD + '_integration']})
        self.assertTrue(allowed_variable(NEW_VARIABLE + 'DATA_ROOT'))
        self.assertTrue(allowed_variable('XDG_CONFIG_HOME'))
        self.assertFalse(allowed_variable('HYPRN' + '_DATA_ROOT'))
        self.assertFalse(allowed_variable('MODEL_KEY_FILE'))
        # Synthetic reads are assembled so this file never reads a variable itself.
        reads = 'os.environ' + ".get('A_B') os.environ" + "['C'] monkeypatch.setenv" + '("D", 1)'
        self.assertEqual([m.group(1) for m in READS.finditer(reads)], ['A_B', 'C', 'D'])
        uses = 'process.' + 'env.E_F ?? process.' + "env['G']"
        self.assertEqual([m.group(1) or m.group(2) for m in PROCESS_ENV.finditer(uses)], ['E_F', 'G'])
        self.assertEqual([m.group(1) for m in LABEL.finditer('LABEL org.' + OLD + '.owner=x org.hyprn-mvp.owner=y')],
                         [OLD, 'hyprn-mvp'])
        self.assertEqual([m.group(1) for m in MANAGER_NAME.finditer("NAME='" + OLD + "-modeling'")], [OLD + '-modeling'])
        self.assertEqual(set(contract_findings(['contracts/' + OLD + '.openapi.yaml', 'contracts/modeling.openapi.yaml'])),
                         {'contracts/' + OLD + '.openapi.yaml', 'contracts/hyprn-mvp.openapi.yaml'})
        self.assertEqual([m.group(1) for m in EXTENSION.finditer('  x-' + OLD + '-invariants:\n  "x-hyprn-mvp-a": 1\n')],
                         ['x-' + OLD + '-invariants', 'x-hyprn-mvp-a'])
        for name in (ITEM + '_checks', 'test_original_c4_pinned', 'test_' + 'docs' + '_24_1_probe', 'evidence-01-09',
                     'P4-S6a', 'task' + '24', 'Phase 2'):
            with self.subTest(name=name):
                self.assertTrue(WORK_ITEM.search(name))
        for name in ('test_model3_receipt', 'bundle8', '010-workspace-tests.patch', '0001-repository-strategy.md',
                     'test_units_attestation_', 'ui-c', 'native-b'):
            with self.subTest(name=name):
                self.assertFalse(WORK_ITEM.search(name))
        self.assertEqual(BROWSER_TAG.findall("test('@approach-reading saves', x); const m='a@b.c';"), ['approach-reading'])


if __name__ == '__main__':
    unittest.main()
