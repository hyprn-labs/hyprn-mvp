"""Dependency guard: pure contracts stay dependency-light and own their names.

Importing pure contract/identity helpers must not load storage, HTTP clients or runtime
modules, and production code must not reach those helpers through the persistence or
orchestration modules. The temporary aliases in ``store``/``modeling``/``execution``/
``result_bindings``/``modified_runs`` exist only for test imports; production code never
uses them.

Integration seam: launcher, calculation, the retained-result reader and
integration export reach the application only through the pure modules (``contracts``,
``units``, ``scientific_configuration``, ``approach_closure``, ``execution_bundle``), and
every application module they can reach, including through function-local imports, is
bound into ``launcher.execution_source_hashes()``.

Attestation scope: the attestation covers exactly what the launch path can load: the
project ``.py`` entries of
``execution_source_hashes()`` must equal the static import closure of launcher,
calculation, results and worker (both packages, package ``__init__`` files included),
the list stays a reviewed literal in ``launcher.py``, and attested modules may not load
code dynamically outside the reviewed allowlist.

Retained-run owner: ``history`` owns retained-run reading and outcome
completeness; the scalar-source (``result_bindings``) and seed (``modified_runs``)
workflows depend on it and never the reverse.

Evidence owner: ``store`` alone reads and validates exact evidence versions and
creates evidence snapshots; ``configuration`` reads saved approach versions through
``approach.saved_version`` and ``approach`` never reaches ``configuration``.

In-transaction interface and model-record owners: no module reaches another
object's private attributes outside a reviewed allowlist; ``store`` owns the study, receipt and
per-model association reads (``study_row``, ``command_receipt``, ``model_association``) and the
modeling domain owns the pure model integrity check (``modeling.checked_model``).

Version-interpretation owners: ``execution_bundle`` holds the one retained
pairing table (``RETAINED_PAIRINGS``, read through ``bundle_family``) and ``units`` the one
port-units rule (``port_units``); no other application module repeats either.

Wording guard: in the public API document, "package" means only a method
package. Portable model records, execution bundles and computational record exports are not
packages; their legacy wire names (``ModelPackageN``, the ``package`` request field,
``model_package_manifest``) stay documented in contracts/README.md and are the only other uses.
"""
import ast
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
APP = REPO / 'application/src/hyprn_mvp_app'
INTEGRATION = REPO / 'integration/src/hyprn_mvp_integration'
PRODUCTION = (APP, INTEGRATION)

CONTRACTS, UNITS, BUNDLE = 'hyprn_mvp_app.contracts', 'hyprn_mvp_app.units', 'hyprn_mvp_app.execution_bundle'
BUNDLE_NAMES = (
    'MAX_BYTES', 'MAX_FILES', 'assemble_bundle', 'closed', 'executable_digest', 'frozen_version',
    'model_capabilities', 'port_key', 'safe_path', 'unique', 'uses_polish_envelope', 'uses_typed_units',
    'uses_units_envelope', 'validate_approach_binding', 'validate_assumption_closure', 'validate_bundle_shape',
    'validate_frozen_configuration', 'validate_preparation', 'validate_provenance', 'validate_retained_bundle',
    'validate_scientific_snapshot', 'validate_unit_catalog', 'verify_files',
)
# Temporary alias -> owner. Production code must import each name from its owner,
# never through the forwarding alias.
MOVED = {
    'hyprn_mvp_app.store': dict.fromkeys(('canonical', 'digest', 'uid', 'DomainError'), CONTRACTS),
    'hyprn_mvp_app.modeling': {**dict.fromkeys(('validate', 'SCHEMA', 'VALIDATORS'), CONTRACTS),
                              **dict.fromkeys(('UNIT_CATALOG_DIGEST', 'UNIT_ENGINE_SOURCE_SHA256',
                                               'UNIT_CATALOG_BYTES'), UNITS)},
    'hyprn_mvp_app.execution': {**dict.fromkeys(('data_json', 'raw_hash', 'check_digest'), CONTRACTS),
                               **dict.fromkeys(BUNDLE_NAMES, BUNDLE)},
    'hyprn_mvp_app.result_bindings': dict.fromkeys(('verify_dependencies', 'finite'), BUNDLE),
    'hyprn_mvp_app.modified_runs': dict(complete_outcome='hyprn_mvp_app.history'),
}
# No production module may import a temporary alias, the worker-image file (results.py) included.
ALLOWED = set()

# The only application modules the integration seam may reach: dependency-light,
# data-only, bound into the execution attestation.
PURE = frozenset({'hyprn_mvp_app', CONTRACTS, UNITS, 'hyprn_mvp_app.scientific_configuration',
                  'hyprn_mvp_app.approach_closure', BUNDLE})
# Integration modules bound into the attestation whose application reach is checked.
BOUND_INTEGRATION = ('hyprn_mvp_integration.launcher', 'hyprn_mvp_integration.calculation',
                     'hyprn_mvp_integration.results')
INTEGRATION_SEAM = BOUND_INTEGRATION + ('hyprn_mvp_integration.computational_export',)
# Every launch-path root. The worker is a static root: it runs inside the worker
# image and is never imported by the host-side runtime probe.
ATTESTED_ROOTS = BOUND_INTEGRATION + ('hyprn_mvp_integration.worker',)
PROJECT_SOURCES = ('application/src/', 'integration/src/')
# Reviewed attested project modules (34-entry list; the other 22 entries are the
# deployment/generator/runtime/policy pins and the reviewed WhatsOpt patches).
ATTESTED_PROJECT_FILES = frozenset({
    'application/src/hyprn_mvp_app/__init__.py',
    'application/src/hyprn_mvp_app/approach_closure.py',
    'application/src/hyprn_mvp_app/contracts.py',
    'application/src/hyprn_mvp_app/execution_bundle.py',
    'application/src/hyprn_mvp_app/scientific_configuration.py',
    'application/src/hyprn_mvp_app/units.py',
    'integration/src/hyprn_mvp_integration/__init__.py',
    'integration/src/hyprn_mvp_integration/calculation.py',
    'integration/src/hyprn_mvp_integration/computational_export.py',
    'integration/src/hyprn_mvp_integration/launcher.py',
    'integration/src/hyprn_mvp_integration/results.py',
    'integration/src/hyprn_mvp_integration/worker.py',
})
# The only reviewed dynamic code loading in attested modules,
# (path, line, callee). Line drift fails the test and needs a reviewed update.
# calculation.py: literal ``__import__('hashlib')`` (stdlib, no project code).
# worker.py 1010/1013/1014: the single frozen-entry candidate seam ``load_program``
# (spec_from_file_location at 1010, then module_from_spec and exec_module on that spec),
# reached only after byte verification of the frozen bundle.
DYNAMIC_ALLOWLIST = frozenset({
    ('integration/src/hyprn_mvp_integration/calculation.py', 66, '__import__'),
    ('integration/src/hyprn_mvp_integration/calculation.py', 129, '__import__'),
    ('integration/src/hyprn_mvp_integration/worker.py', 1010, 'spec_from_file_location'),
    ('integration/src/hyprn_mvp_integration/worker.py', 1013, 'module_from_spec'),
    ('integration/src/hyprn_mvp_integration/worker.py', 1014, 'exec_module'),
})
DYNAMIC_CALLS = frozenset({'__import__', 'exec', 'eval', 'compile', 'globals', 'locals', 'vars'})
DYNAMIC_ATTRIBUTES = frozenset({
    'import_module', 'spec_from_file_location', 'spec_from_loader', 'module_from_spec', 'exec_module',
    'load_module', 'find_spec', 'find_module', 'SourceFileLoader', 'SourcelessFileLoader', 'ExtensionFileLoader',
    'run_path', 'run_module', 'entry_points', 'iter_entry_points', 'load_entry_point', 'get_entry_info',
    'get_entry_map', 'reload', '__builtins__', '__loader__', '__spec__',
    # Builtins referenced (not only called) by name or attribute, e.g. ``sys.modules['builtins'].exec``.
    '__import__', 'exec', 'eval'})
DYNAMIC_MODULES = frozenset({'runpy', 'importlib.metadata', 'importlib_metadata', 'importlib.machinery',
                             'importlib.resources', 'pkg_resources', 'pkgutil', 'zipimport', 'imp', 'builtins',
                             'code', 'codeop'})
REFLECTIVE = frozenset({'getattr', 'setattr', 'delattr', 'hasattr'})


def probe(code):
    """Run ``code`` in a fresh interpreter that imports this tree's sources first."""
    prelude = ('import sys,json;'
               f'sys.path[:0]=[{str(REPO / "application/src")!r},{str(REPO / "integration/src")!r}];')
    result = subprocess.run([sys.executable, '-B', '-c', prelude + code], capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def test_pure_contract_and_unit_imports_do_not_load_storage_clients_or_runtime():
    loaded = probe('import hyprn_mvp_app.contracts, hyprn_mvp_app.units;'
                   'print(json.dumps(dict(modules=sorted(sys.modules), file=hyprn_mvp_app.contracts.__file__)))')
    assert Path(loaded['file']).resolve().is_relative_to(REPO)
    modules = set(loaded['modules'])
    forbidden = {'httpx', 'sqlite3', '_sqlite3', 'fastapi', 'starlette', 'aiida', 'openmdao', 'openturns',
                 'hyprn_mvp_app.store', 'hyprn_mvp_app.modeling', 'hyprn_mvp_app.execution', 'hyprn_mvp_integration'}
    assert not modules & forbidden
    assert {m for m in modules if m.startswith('hyprn_mvp_app')} == {'hyprn_mvp_app', 'hyprn_mvp_app.contracts', 'hyprn_mvp_app.units'}


def test_launcher_attestation_binds_every_application_module_it_imports():
    result = probe('from hyprn_mvp_integration import launcher;'
                   'print(json.dumps(dict(modules=sorted(m for m in sys.modules if m.startswith("hyprn_mvp_app.")),'
                   'bound=sorted(launcher.execution_source_hashes()))))')
    imported = {'application/src/' + m.replace('.', '/') + '.py' for m in result['modules']}
    assert 'application/src/hyprn_mvp_app/contracts.py' in imported
    assert imported <= set(result['bound'])


def test_launcher_import_loads_no_persistence_orchestration_or_transport():
    """The launcher reaches only the pure application modules at import time."""
    loaded = probe('from hyprn_mvp_integration import launcher;'
                   'print(json.dumps(dict(modules=sorted(sys.modules), file=launcher.__file__)))')
    assert Path(loaded['file']).resolve().is_relative_to(REPO)
    modules = set(loaded['modules'])
    forbidden = {'httpx', 'sqlite3', '_sqlite3', 'fastapi', 'starlette', 'aiida', 'openmdao', 'openturns',
                 'hyprn_mvp_app.store', 'hyprn_mvp_app.modeling', 'hyprn_mvp_app.execution',
                 'hyprn_mvp_app.history', 'hyprn_mvp_app.result_bindings'}
    assert not modules & forbidden
    assert {m for m in modules if m.startswith('hyprn_mvp_app')} <= PURE
    assert BUNDLE in modules


def package_roots():
    return {'hyprn_mvp_app': APP, 'hyprn_mvp_integration': INTEGRATION}


def module_path(name):
    """The source file of project module ``name``: ``pkg/sub/mod.py`` or, for a package or
    subpackage, its ``__init__.py``; ``None`` when no such module exists."""
    package, _, rest = name.partition('.')
    root = package_roots()[package]
    if not rest:
        path = root / '__init__.py'
    else:
        base = root / rest.replace('.', '/')
        path = base.parent / (base.name + '.py')
        if not path.is_file():
            path = base / '__init__.py'
    return path if path.is_file() else None


def module_name(path):
    """The dotted module of project source ``path``, derived from its location below the
    package root (``pkg/sub/__init__.py`` is ``pkg.sub``)."""
    for package, root in package_roots().items():
        if path.is_relative_to(root):
            parts = [package, *path.relative_to(root).with_suffix('').parts]
            return '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)
    raise AssertionError((str(path), 'not below a project package root'))


def resolve_relative(module, is_package, level, target):
    """Absolute module of ``from <level dots><target> import ...`` written in ``module``.

    Level 1 names the module's own package (the module itself when it is a package
    ``__init__``); each further level goes one package up. Climbing above the project
    package fails closed instead of being silently mis-resolved."""
    package = module.split('.') if is_package else module.split('.')[:-1]
    assert level >= 1 and len(package) >= level, (module, level, 'relative import above the project package')
    base = package[:len(package) - (level - 1)]
    return '.'.join(base + ([target] if target else []))


def imports(path):
    """Yield (absolute module, imported name) for every from-import, including function-local ones."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                module = resolve_relative(module_name(path), path.name == '__init__.py', node.level, node.module)
            else:
                module = node.module
            for alias in node.names:
                yield module, alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None


def packages_run_by(module):
    """Every package ``__init__`` that importing ``module`` runs first (its ancestors)."""
    parts = module.split('.')
    return {'.'.join(parts[:i]) for i in range(1, len(parts)) if module_path('.'.join(parts[:i]))}


def project_imports(name):
    """Project modules ``name`` imports anywhere in its source, function-local imports included."""
    found = set()
    for module, imported in imports(module_path(name)):
        if module.split('.')[0] not in ('hyprn_mvp_app', 'hyprn_mvp_integration'):
            continue
        if imported and module_path(module + '.' + imported):
            found.add(module + '.' + imported)  # from package import submodule
            found |= packages_run_by(module + '.' + imported)  # ... which runs its packages first
        elif module_path(module):
            found.add(module)
            found |= packages_run_by(module)  # importing a submodule runs its packages
    return found - {name}  # a package __init__ importing its own submodule does not import itself


def reachable(roots):
    # Importing any root also runs its package __init__ files.
    seen, stack = set(), [*roots, *{p for r in roots for p in packages_run_by(r)}]
    while stack:
        name = stack.pop()
        if name not in seen:
            seen.add(name)
            stack.extend(project_imports(name) - seen)
    return seen


def test_integration_reaches_only_pure_application_modules_including_local_imports():
    """Static closure over every import (top-level and function-local)."""
    application = {m for m in reachable(INTEGRATION_SEAM) if m.startswith('hyprn_mvp_app')}
    assert BUNDLE in application and CONTRACTS in application
    assert application <= PURE, sorted(application - PURE)


def test_attestation_binds_every_application_module_bound_integration_can_load():
    """Nothing the bound integration modules can load, lazily or not, escapes
    ``execution_source_hashes()``; the attestation-scope checks below rely on it."""
    result = probe('from hyprn_mvp_integration import launcher;'
                   'print(json.dumps(sorted(launcher.execution_source_hashes())))')
    bound = set(result)
    closure = reachable(BOUND_INTEGRATION)
    files = {str(module_path(m).relative_to(REPO)) for m in closure if m.startswith('hyprn_mvp_app.')}
    files |= {str(module_path(m).relative_to(REPO)) for m in BOUND_INTEGRATION}
    assert 'application/src/hyprn_mvp_app/execution_bundle.py' in files
    assert files <= bound, sorted(files - bound)


def test_production_code_never_imports_temporary_aliases():
    found = set()
    for root in PRODUCTION:
        for path in sorted(root.rglob('*.py')):
            relative = str(path.relative_to(REPO))
            for module, name in imports(path):
                if name in MOVED.get(module, ()):
                    found.add((relative, module, name))
    assert found == ALLOWED


def test_aliases_forward_the_single_owner_without_copies():
    for module, names in MOVED.items():
        alias = importlib.import_module(module)
        for name, owner in names.items():
            assert getattr(alias, name) is getattr(importlib.import_module(owner), name), (module, name)


# ---- Attestation scope equals the launch-path closure ---------------------------------

def relative(name):
    return str(module_path(name).relative_to(REPO))


def attested_closure():
    return reachable(ATTESTED_ROOTS)


def test_static_closure_covers_both_packages_their_init_files_and_the_worker_root():
    """Package __init__ files and both packages are in the
    closure, and the worker is followed as a static root."""
    closure = attested_closure()
    assert {'hyprn_mvp_app', 'hyprn_mvp_integration', 'hyprn_mvp_integration.worker'} <= closure
    assert 'hyprn_mvp_integration.computational_export' in closure  # calculation.py lazy import is followed
    files = {relative(m) for m in closure}
    assert files == ATTESTED_PROJECT_FILES, sorted(files ^ ATTESTED_PROJECT_FILES)


def test_runtime_import_of_launch_path_binds_every_project_module_including_packages():
    """Everything the host actually loads from both packages
    (package ``__init__`` included) through launcher and results is bound."""
    result = probe('from hyprn_mvp_integration import launcher, results;'
                   'mods={m:getattr(sys.modules[m],"__file__",None) for m in sys.modules '
                   'if m.split(".")[0] in ("hyprn_mvp_app","hyprn_mvp_integration")};'
                   'print(json.dumps(dict(mods=mods,bound=sorted(launcher.execution_source_hashes()))))')
    loaded = {str(Path(f).resolve().relative_to(REPO)) for f in result['mods'].values()}
    assert {'application/src/hyprn_mvp_app/__init__.py', 'integration/src/hyprn_mvp_integration/__init__.py'} <= loaded
    assert loaded <= set(result['bound']), sorted(loaded - set(result['bound']))
    assert loaded <= ATTESTED_PROJECT_FILES


def test_attested_project_sources_equal_the_static_launch_path_closure():
    """Two-sided equality. Nothing reachable is unbound (lazy imports included)
    and nothing unreachable is bound (execution, modeling, result_bindings, store)."""
    bound = set(probe('from hyprn_mvp_integration import launcher;'
                      'print(json.dumps(sorted(launcher.execution_source_hashes())))'))
    project = {p for p in bound if p.startswith(PROJECT_SOURCES) and p.endswith('.py')}
    closure = {relative(m) for m in attested_closure()}
    assert project == closure, dict(unbound=sorted(closure - project), unreachable=sorted(project - closure))
    assert project == ATTESTED_PROJECT_FILES
    assert not {p for p in bound if p.startswith(PROJECT_SOURCES)} - project  # no non-.py project entries
    for removed in ('execution', 'modeling', 'result_bindings', 'store'):
        assert f'application/src/hyprn_mvp_app/{removed}.py' not in bound
    assert len(bound) == 34


def _execution_source_list():
    tree = ast.parse((INTEGRATION / 'launcher.py').read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execution_source_hashes')
    assigns = [n for n in ast.walk(function) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'paths' for t in n.targets)]
    augments = [n for n in ast.walk(function) if isinstance(n, ast.AugAssign)
                and isinstance(n.target, ast.Name) and n.target.id == 'paths']
    return assigns, augments


def test_attested_list_stays_a_reviewed_literal_in_the_launcher():
    """The list is written out, never computed from the closure."""
    assigns, augments = _execution_source_list()
    assert len(assigns) == 1 and isinstance(assigns[0].value, ast.List)
    values = assigns[0].value.elts
    assert all(isinstance(v, ast.Constant) and isinstance(v.value, str) for v in values)
    literal = [v.value for v in values]
    assert len(literal) == len(set(literal)) == 25
    assert {p for p in literal if p.startswith(PROJECT_SOURCES)} == ATTESTED_PROJECT_FILES
    # The only computed addition is the reviewed WhatsOpt patch directory.
    assert len(augments) == 1
    assert 'upstream/whatsopt-patches' in ast.unparse(augments[0].value)
    assert 'src' not in ast.unparse(augments[0].value)


def dynamic_loading(path):
    """(line, callee) for every dynamic code-loading construct in ``path``."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            func = node.func
            # Builtins are reached by bare name (``import builtins`` is banned below), so
            # ``re.compile`` and similar attribute calls are not dynamic code loading.
            name = func.id if isinstance(func, ast.Name) else None
            if name in DYNAMIC_CALLS:
                found.add((node.lineno, name))
            elif name in REFLECTIVE and (len(node.args) < 2 or not isinstance(node.args[1], ast.Constant)):
                found.add((node.lineno, name))
        if isinstance(node, ast.Attribute) and node.attr in DYNAMIC_ATTRIBUTES:
            found.add((node.lineno, node.attr))
        elif isinstance(node, ast.Name) and node.id in DYNAMIC_ATTRIBUTES:
            found.add((node.lineno, node.id))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in DYNAMIC_MODULES or alias.name.split('.')[0] in DYNAMIC_MODULES:
                    found.add((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if module in DYNAMIC_MODULES or module.split('.')[0] in DYNAMIC_MODULES:
                found.add((node.lineno, module))
            for alias in node.names:
                if (alias.name in DYNAMIC_ATTRIBUTES or alias.name in DYNAMIC_CALLS
                        or (module == 'importlib' and alias.name != 'util')):
                    found.add((node.lineno, alias.name))
    return found


def test_attested_modules_load_no_code_dynamically_outside_the_reviewed_allowlist():
    """No importlib.import_module, __import__, runpy, exec/eval or
    entry_points in attested modules, except the reviewed allowlist (exact, no stale entry)."""
    found = set()
    for name in sorted(attested_closure()):
        found |= {(relative(name), line, callee) for line, callee in dynamic_loading(module_path(name))}
    assert found == DYNAMIC_ALLOWLIST, dict(unreviewed=sorted(found - DYNAMIC_ALLOWLIST),
                                            stale=sorted(DYNAMIC_ALLOWLIST - found))
    calculation = (INTEGRATION / 'calculation.py').read_text().splitlines()
    for line in (66, 129):
        assert "__import__('hashlib')" in calculation[line - 1]
    source = (INTEGRATION / 'worker.py').read_text()
    seam = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'load_program')
    assert seam.lineno < 1010 and 1014 <= seam.end_lineno
    assert "spec_from_file_location('_hyprn_mvp_frozen_entry'" in ast.get_source_segment(source, seam)


def test_dynamic_loading_scanner_detects_every_banned_form(tmp_path):
    cases = {
        'import importlib\nimportlib.import_module(name)\n': 'import_module',
        'from importlib import import_module\n': 'import_module',
        '__import__(name)\n': '__import__',
        'import runpy\n': 'runpy',
        'from runpy import run_path\n': 'runpy',
        'exec(code)\n': 'exec',
        'eval(code)\n': 'eval',
        'compile(code, "x", "exec")\n': 'compile',
        'from importlib.metadata import entry_points\n': 'importlib.metadata',
        'import importlib.metadata as m\nm.entry_points()\n': 'entry_points',
        'import pkg_resources\n': 'pkg_resources',
        'getattr(module, name)\n': 'getattr',
        'x = __builtins__\n': '__builtins__',
        'loader.exec_module(m)\n': 'exec_module',
        'run = exec\n': 'exec',
        'import sys\nsys.modules["builtins"].eval(code)\n': 'eval',
    }
    path = tmp_path / 'candidate.py'
    for source, callee in cases.items():
        path.write_text(source)
        assert callee in {c for _, c in dynamic_loading(path)}, source
    path.write_text("import re, hashlib\ngetattr(module, 'build_model', None)\nimport importlib.util\nre.compile('x')\n")
    assert dynamic_loading(path) == set()


FAIL_CLOSED_PROBE = '''
import hashlib
from pathlib import Path
from hyprn_mvp_integration import launcher
repo = Path(REPO)
current = launcher.execution_source_hashes()
added = ('application/src/hyprn_mvp_app/__init__.py', 'integration/src/hyprn_mvp_integration/computational_export.py')
removed = ('execution', 'modeling', 'result_bindings', 'store')
old = {k: v for k, v in current.items() if k not in added}
for name in removed:
    path = 'application/src/hyprn_mvp_app/' + name + '.py'
    old[path] = hashlib.sha256((repo / path).read_bytes()).hexdigest()
out = dict(old=len(old), new=len(current))
calls = []
def command(args, timeout=30):
    calls.append(args)
    raise LookupError('image check reached')
launcher.command = command
for label, inventory in (('old', old), ('new', current)):
    launcher.identity = lambda root=None, inventory=inventory: dict(source_hashes=inventory,
                                                                    worker_image='sha256:' + '0' * 64)
    try:
        launcher.fingerprint()
    except Exception as error:
        out[label + '_error'] = type(error).__name__ + ': ' + str(error)
out['docker_calls'] = len(calls)
print(json.dumps(out))
'''


def test_a_runtime_recorded_against_a_wider_inventory_refuses_until_rebuilt_and_reattested():
    """A runtime.json recorded against a wider inventory (the current one
    plus the modules unreachable from every launch) fails closed on inventory drift before
    any docker inspection; only the current 34-entry inventory passes that check (and then
    reaches the image check, stubbed here)."""
    result = probe(f'REPO={str(REPO)!r}\n' + FAIL_CLOSED_PROBE)
    assert result['old'] == 36 and result['new'] == 34
    assert result['old_error'] == 'RuntimeError: Execution source inventory drift; rebuild before attesting'
    assert result['new_error'] == 'LookupError: image check reached'
    assert result['docker_calls'] == 1


def test_retained_run_owner_never_depends_on_its_consumers():
    """Static, function-local imports included. ``history`` reaches neither the
    scalar-source nor the seed workflow, and neither workflow reaches the other: the
    former history/modified_runs/result_bindings cycle stays broken."""
    owner, sources, seeds = 'hyprn_mvp_app.history', 'hyprn_mvp_app.result_bindings', 'hyprn_mvp_app.modified_runs'
    assert not reachable([owner]) & {sources, seeds}, sorted(reachable([owner]) & {sources, seeds})
    assert seeds not in reachable([sources])
    assert sources not in reachable([seeds])


# ---- Evidence snapshot owner and the approach/configuration cycle -----------------------

# Reviewed raw evidence-table statements outside ``store``: write-time witnesses only, never
# interpretation. The approach resolver pins every row it reads and re-executes the same
# statement at commit; Configurations' commit compares the frozen snapshots with the stored
# rows inside the commit transaction (both rechecks stay as they are).
EVIDENCE_WITNESSES = {
    ('application/src/hyprn_mvp_app/approach.py', 'SELECT * FROM evidence WHERE study_id=? AND evidence_version_id=?'),
    ('application/src/hyprn_mvp_app/configuration.py', 'SELECT payload FROM evidence WHERE study_id=? AND evidence_version_id=?'),
}


def string_constants(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def test_approach_never_depends_on_configuration_workflow():
    """Static, function-local imports included. Configurations reads saved approach
    versions through ``approach.saved_version``; approach resolution takes evidence snapshots
    from ``store`` and never reaches ``configuration``: the former cycle stays broken."""
    approach, configuration = 'hyprn_mvp_app.approach', 'hyprn_mvp_app.configuration'
    assert configuration not in reachable([approach]), sorted(reachable([approach]))
    assert approach in project_imports(configuration)
    local = [n for n in ast.walk(ast.parse(module_path(configuration).read_text()))
             if isinstance(n, ast.FunctionDef) for m in ast.walk(n)
             if isinstance(m, ast.ImportFrom) and m.module == 'approach']
    assert not local, 'configuration -> approach must be a top-level import'


def test_no_production_code_reaches_the_former_private_snapshot_and_saved_helpers():
    found = []
    for root in PRODUCTION:
        for path in sorted(root.rglob('*.py')):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Attribute) and node.attr in ('_snapshot', '_saved'):
                    found.append((str(path.relative_to(REPO)), node.lineno, node.attr))
    assert found == []
    from hyprn_mvp_app import approach, store
    from hyprn_mvp_app.configuration import Configurations
    assert not hasattr(approach.Approaches, '_saved')
    # Temporary test-only alias (identity_golden.py); it forwards the single owner.
    assert Configurations._snapshot is store.evidence_snapshot


def test_exact_evidence_reading_has_one_owner():
    """Only ``store`` validates stored evidence (``EvidenceRecordRead``) or selects evidence
    rows by version; the remaining raw statements elsewhere are reviewed write-time witnesses."""
    validators, statements = set(), set()
    for root in PRODUCTION:
        for path in sorted(root.rglob('*.py')):
            relative = str(path.relative_to(REPO))
            if relative == 'application/src/hyprn_mvp_app/store.py':
                continue
            for value in string_constants(path):
                if value == 'EvidenceRecordRead':
                    validators.add(relative)
                if re.search(r'\bFROM evidence\b(?!_)', value):
                    statements.add((relative, value))
    assert validators == set()
    assert statements == EVIDENCE_WITNESSES, sorted(statements ^ EVIDENCE_WITNESSES)


# ---- Model integrity, model association and Store's in-transaction interface ------------

# Private helpers no other object may reach. Their owners expose
# public names: ``Store.study_row``/``command_receipt``/``model_association`` (caller holds the
# connection) and the pure ``modeling.checked_model``.
OWNER_PRIVATE_HELPERS = ('_study', '_receipt', '_checked_model', '_authorize_request')
# Reviewed cross-object private attribute accesses that remain in the application package,
# as (path, object expression, attribute). None of them reaches another project module:
# - api.py ``request._body``: Starlette's request body cache, re-seated with the validated bytes
#   in the body-bounding middleware (framework idiom, no project module).
# - computational_export.py ``ComputationalRecords._package``: the module's own class, called
#   from the same module's archive verifier (same module).
# - dispatcher.py ``os._exit``: the standard library's public immediate-exit call (fault mode).
PRIVATE_ALLOWLIST = {
    ('application/src/hyprn_mvp_app/api.py', 'request', '_body'),
    ('application/src/hyprn_mvp_app/computational_export.py', 'ComputationalRecords', '_package'),
    ('application/src/hyprn_mvp_app/dispatcher.py', 'os', '_exit'),
}
# Reviewed ``model_associations`` statements outside ``store`` (Store holds the table and owns
# the authorized per-model read ``Store.model_association``). The Coordinator writes an
# association after a committed remote command and lists the ones it wrote; the approach
# resolver pins the row it read and re-executes the same statement at commit (write-time
# witness, rechecks unchanged, as for its evidence witness).
ASSOCIATION_STATEMENTS = {
    ('application/src/hyprn_mvp_app/modeling.py', 'INSERT OR IGNORE INTO model_associations VALUES(?,?,?)'),
    ('application/src/hyprn_mvp_app/modeling.py',
     'SELECT model_id,command_id FROM model_associations WHERE study_id=? ORDER BY model_id'),
    ('application/src/hyprn_mvp_app/approach.py', 'SELECT * FROM model_associations WHERE study_id=? AND model_id=?'),
}


def cross_object_private_accesses(root):
    """Yield (path, object expression, attribute, line) for ``x._name`` where ``x`` is not
    ``self``/``cls`` (dunder names excluded): one module reaching into another object."""
    for path in sorted(root.rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Attribute) and node.attr.startswith('_') and not node.attr.startswith('__')
                    and not (isinstance(node.value, ast.Name) and node.value.id in ('self', 'cls'))):
                yield str(path.relative_to(REPO)), ast.unparse(node.value), node.attr, node.lineno


def test_no_production_code_reaches_store_or_coordinator_private_helpers():
    """``store._study``/``store._receipt`` and ``coordinator._checked_model``/
    ``coordinator._authorize_request`` are never reached from another object, by attribute or
    by name string, anywhere in production code."""
    found = [hit for root in PRODUCTION for hit in cross_object_private_accesses(root) if hit[2] in OWNER_PRIVATE_HELPERS]
    names = [(str(path.relative_to(REPO)), value) for root in PRODUCTION for path in sorted(root.rglob('*.py'))
             for value in string_constants(path) if value in OWNER_PRIVATE_HELPERS]
    assert found == [] and names == [], (found, names)
    from hyprn_mvp_app import modeling
    from hyprn_mvp_app.store import Store
    assert not hasattr(Store, '_study') and not hasattr(modeling.Coordinator, '_checked_model')
    # Temporary test-only alias (receipt assertions in tests); it forwards the owner.
    assert Store._receipt is Store.command_receipt
    assert callable(modeling.checked_model)


def test_application_cross_object_private_access_is_exactly_the_reviewed_allowlist():
    """Whole-package scan: every application module, function bodies included."""
    found = {hit[:3] for hit in cross_object_private_accesses(APP)}
    assert found == PRIVATE_ALLOWLIST, sorted(found ^ PRIVATE_ALLOWLIST)


def test_model_association_reads_have_one_owner():
    """Only ``store`` reads a study's association with one model; ``configuration`` holds no
    association SQL at all and reaches the read through ``Store.model_association``."""
    statements = set()
    for root in PRODUCTION:
        for path in sorted(root.rglob('*.py')):
            relative = str(path.relative_to(REPO))
            if relative == 'application/src/hyprn_mvp_app/store.py':
                continue
            statements |= {(relative, value) for value in string_constants(path) if 'model_associations' in value}
    assert statements == ASSOCIATION_STATEMENTS, sorted(statements ^ ASSOCIATION_STATEMENTS)


def test_model_integrity_check_is_a_pure_module_function():
    """``modeling.checked_model`` takes the record and its expected identity only: no
    Coordinator, Store, connection or transport, so historical replays never need them."""
    import inspect
    from hyprn_mvp_app import modeling
    assert list(inspect.signature(modeling.checked_model).parameters) == ['value', 'sid', 'mid', 'revision']
    source = ast.parse(inspect.getsource(modeling.checked_model))
    used = {n.id for n in ast.walk(source) if isinstance(n, ast.Name)}
    assert not used & {'self', 'httpx', 'Store', 'Coordinator', 'ModelingClient', 'time'}, used


# ---- One owner per backend version-interpretation point -------------------------------

# The historic retained run pairings, as (history projection, bundle, configuration, model)
# schema versions. Written out here, independently of the owner, so a change to the owner's
# table is a reviewed change to this test as well.
HISTORIC_PAIRINGS = frozenset({
    ('1', '1', '1', '1'), ('1', '2', '1', '1'), ('1', '3', '2', '1'),
    ('2', '4', '3', '1'), ('2', '4', '3', '2'),
    ('3', '5', '4', '1'), ('3', '5', '4', '2'),
    ('4', '6', '4', '2'), ('4', '6', '4', '3'),
    ('6', '8', '4', '2'), ('6', '8', '4', '3'), ('6', '8', '4', '4'),
})
# bundle -> (history projection, configuration, models, carries the modeling-configuration
# and result-dependencies files, carries approach pins)
HISTORIC_FAMILIES = {
    '1': ('1', '1', {'1'}, False, False),
    '2': ('1', '1', {'1'}, False, False),
    '3': ('1', '2', {'1'}, True, False),
    '4': ('2', '3', {'1', '2'}, True, False),
    '5': ('3', '4', {'1', '2'}, True, True),
    '6': ('4', '4', {'2', '3'}, True, True),
    '8': ('6', '4', {'2', '3', '4'}, True, True),
}


def test_retained_pairings_are_exactly_the_twelve_historic_tuples_with_one_owner():
    from hyprn_mvp_app import execution_bundle, history
    assert isinstance(execution_bundle.RETAINED_PAIRINGS, frozenset)
    assert execution_bundle.RETAINED_PAIRINGS == HISTORIC_PAIRINGS
    assert len(execution_bundle.RETAINED_PAIRINGS) == 12
    # The retained reader holds the owner's table, not a copy.
    assert history.RETAINED_PAIRINGS is execution_bundle.RETAINED_PAIRINGS


@pytest.mark.parametrize('bundle', sorted(HISTORIC_FAMILIES))
def test_bundle_family_is_derived_from_the_single_table(bundle):
    from hyprn_mvp_app.execution_bundle import bundle_family
    family = bundle_family(bundle)
    history, configuration, models, dependencies, approach = HISTORIC_FAMILIES[bundle]
    assert (family.history, family.configuration, set(family.models)) == (history, configuration, models)
    assert (family.carries_dependencies, family.carries_approach) == (dependencies, approach)
    assert {(family.history, bundle, family.configuration, m) for m in family.models} == {
        p for p in HISTORIC_PAIRINGS if p[1] == bundle}


@pytest.mark.parametrize('version', ['0', '7', '9', '10', '', ' 8', '8.0', None, 8, ['8'], {'v': '8'}])
def test_unlisted_bundle_versions_are_explicitly_unsupported(version):
    from hyprn_mvp_app.execution_bundle import UnsupportedRetainedVersion, bundle_family
    assert issubclass(UnsupportedRetainedVersion, ValueError)
    with pytest.raises(UnsupportedRetainedVersion):
        bundle_family(version)


# Retained-family literals that only the owner's table may express: the bundles carrying
# result dependencies, the bundles carrying approach pins and the retained history versions.
FAMILY_LITERALS = {('3', '4', '5', '6', '8'), ('5', '6', '8'), ('1', '2', '3', '4', '6')}
# Reviewed version maps that remain explicit because they produce, not interpret: the bundle
# a new configuration is frozen into (``assemble_bundle``) and the seed version a retained
# history produces (``ModifiedRuns.seed``, validated against ``ModifiedRunSeed<N>``).
PRODUCER_MAPS = {
    ('application/src/hyprn_mvp_app/execution_bundle.py', "{'2': '3', '3': '4', '4': '5'}"),
    ('application/src/hyprn_mvp_app/modified_runs.py', "{'3': '3', '4': '4', '6': '6'}"),
}


def version_literals(path):
    """Yield (line, literal) for every all-string tuple and every version-to-version map."""
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Tuple) and node.elts and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
            yield node.lineno, tuple(e.value for e in node.elts)
        if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and k.value in HISTORIC_FAMILIES for k in node.keys) and all(
                isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value.isdigit() for v in node.values):
            yield node.lineno, ast.unparse(node)


def test_application_holds_no_second_retained_pairing_table():
    """No application module repeats a retained pairing tuple, a bundle-family tuple or a
    bundle -> history/configuration map; the owner's table is the only place they are written.
    Admission sets (``('2','3','4','5','6','8')``) and the reviewed producer maps stay explicit."""
    owner = 'application/src/hyprn_mvp_app/execution_bundle.py'
    found, table = [], []
    for path in sorted(APP.rglob('*.py')):
        relative = str(path.relative_to(REPO))
        for line, value in version_literals(path):
            if isinstance(value, str):
                if (relative, value) not in PRODUCER_MAPS:
                    found.append((relative, line, value))
            elif value in HISTORIC_PAIRINGS and relative == owner:
                table.append(value)
            elif value in HISTORIC_PAIRINGS or value in FAMILY_LITERALS:
                found.append((relative, line, value))
    assert found == [], found
    assert sorted(table) == sorted(HISTORIC_PAIRINGS)


def legacy_unit_fallbacks(path):
    """``<resolved>[key] if <...> else <port>['units']``: the repeated port-units choice."""
    for node in ast.walk(ast.parse(path.read_text())):
        if (isinstance(node, ast.IfExp) and isinstance(node.orelse, ast.Subscript)
                and isinstance(node.orelse.slice, ast.Constant) and node.orelse.slice.value == 'units'):
            yield node.lineno


def test_port_units_rule_has_one_owner():
    """``units.port_units`` alone chooses between the exact retained literal (Model1/2) and the
    resolved engine spelling (Model3/4); its consumers ask it and never repeat the choice."""
    found = [(str(path.relative_to(REPO)), line) for path in sorted(APP.rglob('*.py'))
             if path.name != 'units.py' for line in legacy_unit_fallbacks(path)]
    assert found == [], found
    for name in ('history', 'result_bindings', 'configuration', 'execution_bundle'):
        assert ('hyprn_mvp_app.units', 'port_units') in set(imports(APP / (name + '.py'))), name
    # The resolved table is never indexed directly outside ``units``.
    indexed = [(str(path.relative_to(REPO)), node.lineno) for path in sorted(APP.rglob('*.py'))
               if path.name != 'units.py' for node in ast.walk(ast.parse(path.read_text()))
               if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Call)
               and getattr(node.value.func, 'id', None) == 'resolved_model_units']
    assert indexed == [], indexed


# "Package" in user-visible API wording means only a method package (CONTEXT.md glossary).
PACKAGE_WORDING_ALLOWED = (
    re.compile(r'\bModelPackage\w*'),            # legacy wire record names (portable model record)
    re.compile(r'\bmodel_package_manifest\b'),   # legacy wire field inside the execution bundle
    re.compile(r'\brequest field package\b'),    # legacy ImportModel request field, named as a field
    re.compile(r'\bmethod packages?\b', re.I),   # the one domain meaning of "package"
)


def api_wording(node, where=''):
    """Every human-readable ``summary``/``description``/``title`` string in an OpenAPI document."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ('summary', 'description', 'title') and isinstance(value, str):
                yield where + '/' + key, value
            else:
                yield from api_wording(value, where + '/' + str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from api_wording(value, f'{where}/{index}')


def test_public_api_wording_uses_package_only_for_method_packages():
    spec = json.loads((REPO / 'contracts/hyprn-mvp.openapi.yaml').read_text())
    found = []
    for where, text in api_wording(spec):
        stripped = text
        for pattern in PACKAGE_WORDING_ALLOWED:
            stripped = pattern.sub('', stripped)
        if re.search(r'packag', stripped, re.I):
            found.append((where, text[:160]))
    assert found == [], found


@pytest.mark.parametrize('text,allowed', [
    ('Authorized hash-verified inspection package; fixed attachment filename', False),
    ('Download the model package', False),
    ('Portable model record (legacy wire name ModelPackage) for one committed model version', True),
    ('The request field package carries the record; not a method package.', True),
    ('Execution bundle preparation retains model_package_manifest.', True),
])
def test_package_wording_rule_distinguishes_legacy_names_from_product_language(text, allowed):
    stripped = text
    for pattern in PACKAGE_WORDING_ALLOWED:
        stripped = pattern.sub('', stripped)
    assert (re.search(r'packag', stripped, re.I) is None) is allowed


# ---- Agent packages: one-way dependencies outside the attested launch path ------------
# ``agent_tools`` (the registry) reaches only itself and ``contracts``; ``agent_surface``
# (MCP server, bridges) reaches only itself and ``agent_runtime``; ``agent_runtime`` reaches
# only itself, ``agent_tools``, ``auth``, ``store`` (whose schema holds the principal tables
# ``auth`` and ``authorize`` read) and ``contracts``; ``agent_policy`` (the agent route
# allowlist) reaches only ``agent_tools`` and ``contracts`` and is imported only by ``api``.
# Nothing in execution integration reaches an agent module, so the attested source set is
# unchanged. A row for a package that exists must scan at least one file, so it is never vacuous.

AGENT_PACKAGES = ('agent_tools', 'agent_runtime', 'agent_surface')
AGENT_POLICY = 'hyprn_mvp_app.agent_policy'
AUTH, STORE = 'hyprn_mvp_app.auth', 'hyprn_mvp_app.store'


def within(module, *packages):
    return any(module == p or module.startswith(p + '.') for p in packages)


def is_agent_module(module):
    return within(module, AGENT_POLICY, *('hyprn_mvp_app.' + p for p in AGENT_PACKAGES))


AGENT_REACH = {
    'agent_tools': lambda m: within(m, 'hyprn_mvp_app.agent_tools') or m == CONTRACTS,
    'agent_surface': lambda m: within(m, 'hyprn_mvp_app.agent_surface', 'hyprn_mvp_app.agent_runtime'),
    'agent_runtime': lambda m: within(m, 'hyprn_mvp_app.agent_runtime', 'hyprn_mvp_app.agent_tools')
                               or m in {AUTH, STORE, CONTRACTS},
}


def package_modules(package):
    """Every module of application (sub)package ``package``, scanned recursively; empty while
    the package does not exist, and never empty once it does."""
    root = APP / package
    if not root.is_dir():
        return set()
    files = sorted(root.rglob('*.py'))
    assert files, (package, 'exists but holds no module to scan')
    return {module_name(path) for path in files}


def direct_reach(modules):
    """Project modules imported by ``modules`` themselves (the project roots are omitted)."""
    found = set()
    for module in modules:
        found |= project_imports(module)
    return found - set(package_roots()) - set(modules)


def test_agent_packages_reach_only_their_allowed_modules():
    for package, allowed in AGENT_REACH.items():
        modules = package_modules(package)
        assert all(module_path(m) for m in modules), package
        outside = sorted(m for m in direct_reach(modules) if not allowed(m))
        assert outside == [], (package, outside)


def test_agent_policy_reaches_only_the_registry_and_contracts_and_only_api_imports_it():
    assert module_path(AGENT_POLICY) is not None
    outside = sorted(m for m in project_imports(AGENT_POLICY) - set(package_roots())
                     if not (within(m, 'hyprn_mvp_app.agent_tools') or m == CONTRACTS))
    assert outside == [], outside
    importers = {module_name(path) for root in PRODUCTION for path in sorted(root.rglob('*.py'))
                 if AGENT_POLICY in project_imports(module_name(path))}
    assert importers == {'hyprn_mvp_app.api'}, sorted(importers)


def test_store_and_auth_never_reach_an_agent_module():
    for owner in (STORE, AUTH):
        assert not any(is_agent_module(m) for m in reachable([owner])), owner


def test_execution_integration_and_the_attested_closure_reach_no_agent_module():
    integration = [module_name(path) for path in sorted(INTEGRATION.rglob('*.py'))]
    assert integration and 'hyprn_mvp_integration.launcher' in integration
    reached = sorted(m for m in reachable(integration) if is_agent_module(m))
    assert reached == [], reached
    closure = attested_closure()
    assert not any(is_agent_module(m) for m in closure)
    assert {relative(m) for m in closure} == ATTESTED_PROJECT_FILES


def test_membership_statements_have_one_owner():
    """Only ``store`` reads or writes ``memberships``; every other module asks ``authorize``,
    so an agent actor's authority is always intersected with its delegating user's role."""
    found = sorted((str(path.relative_to(REPO)), value) for root in PRODUCTION for path in sorted(root.rglob('*.py'))
                   if str(path.relative_to(REPO)) != 'application/src/hyprn_mvp_app/store.py'
                   for value in string_constants(path)
                   if re.search(r'\b(?:FROM|JOIN|INTO|UPDATE)\s+memberships\b', value, re.I))
    assert found == [], found


def test_production_scans_include_subpackage_modules(tmp_path, monkeypatch):
    """Subpackage modules are scanned and their relative imports resolve to their own package,
    its parents and the package root, with each subpackage ``__init__`` run on import."""
    app = tmp_path / 'hyprn_mvp_app'
    (app / 'agent_tools' / 'catalogue').mkdir(parents=True)
    for name, text in {
        '__init__.py': '',
        'contracts.py': '',
        'store.py': 'from . import contracts\n',
        'agent_tools/__init__.py': 'from .spec import ToolSpec\n',
        'agent_tools/spec.py': 'from ..contracts import uid\n',
        'agent_tools/catalogue/__init__.py': '',
        'agent_tools/catalogue/study.py': 'from .. import spec\nfrom ...store import Store\n',
    }.items():
        (app / name).write_text(text)
    monkeypatch.setattr(sys.modules[__name__], 'APP', app)
    assert module_path('hyprn_mvp_app.agent_tools') == app / 'agent_tools/__init__.py'
    assert module_path('hyprn_mvp_app.agent_tools.catalogue.study') == app / 'agent_tools/catalogue/study.py'
    assert module_name(app / 'agent_tools/catalogue/__init__.py') == 'hyprn_mvp_app.agent_tools.catalogue'
    assert package_modules('agent_tools') == {'hyprn_mvp_app.agent_tools', 'hyprn_mvp_app.agent_tools.spec',
                                              'hyprn_mvp_app.agent_tools.catalogue',
                                              'hyprn_mvp_app.agent_tools.catalogue.study'}
    assert project_imports('hyprn_mvp_app.agent_tools.catalogue.study') == {
        'hyprn_mvp_app', 'hyprn_mvp_app.agent_tools', 'hyprn_mvp_app.agent_tools.spec', 'hyprn_mvp_app.store'}
    assert project_imports('hyprn_mvp_app.agent_tools') == {'hyprn_mvp_app', 'hyprn_mvp_app.agent_tools.spec'}
    assert reachable(['hyprn_mvp_app.agent_tools.catalogue.study']) >= {
        'hyprn_mvp_app.agent_tools', 'hyprn_mvp_app.agent_tools.catalogue', 'hyprn_mvp_app.contracts'}
    outside = sorted(m for m in direct_reach(package_modules('agent_tools')) if not AGENT_REACH['agent_tools'](m))
    assert outside == ['hyprn_mvp_app.store']
    (app / 'agent_runtime').mkdir()
    with pytest.raises(AssertionError, match='holds no module'):
        package_modules('agent_runtime')


@pytest.mark.parametrize('module,is_package,level,target,expected', [
    ('hyprn_mvp_app.api', False, 1, 'store', 'hyprn_mvp_app.store'),
    ('hyprn_mvp_app.api', False, 1, None, 'hyprn_mvp_app'),
    ('hyprn_mvp_app.agent_tools.registry', False, 1, 'spec', 'hyprn_mvp_app.agent_tools.spec'),
    ('hyprn_mvp_app.agent_tools.registry', False, 2, 'contracts', 'hyprn_mvp_app.contracts'),
    ('hyprn_mvp_app.agent_tools', True, 1, 'spec', 'hyprn_mvp_app.agent_tools.spec'),
    ('hyprn_mvp_app.agent_tools', True, 2, None, 'hyprn_mvp_app'),
])
def test_relative_imports_resolve_from_the_module_location(module, is_package, level, target, expected):
    assert resolve_relative(module, is_package, level, target) == expected


def test_relative_import_above_the_project_package_fails_closed():
    with pytest.raises(AssertionError):
        resolve_relative('hyprn_mvp_app.api', False, 2, 'x')


# ---- API edge and per-owner routers ------------------------------------------------------
# ``api`` is the HTTP edge (middleware, exception handlers, session and actor dependencies,
# router composition) and the only importer of a route module. Each ``routes/<owner>.py``
# reaches only the edge helpers (``edge``), ``contracts`` and the domain owners whose public
# functions it calls: never ``api``, another route module or an agent module. ``edge`` reaches
# no project module but ``contracts`` and serves only ``api`` and the route modules. Each row
# scans at least one module, so it is never vacuous.

API, EDGE, ROUTES = 'hyprn_mvp_app.api', 'hyprn_mvp_app.edge', 'hyprn_mvp_app.routes'
ROUTE_OWNERS = frozenset('hyprn_mvp_app.' + m for m in (
    'store', 'auth', 'readiness', 'modeling', 'configuration', 'approach', 'execution', 'history',
    'result_bindings', 'modified_runs', 'computational_export'))


def route_modules():
    modules = package_modules('routes') - {ROUTES}
    assert modules, 'no route module scanned'
    return modules


def production_importers(predicate):
    """Production modules whose own imports include a module satisfying ``predicate``."""
    return {module_name(path) for root in PRODUCTION for path in sorted(root.rglob('*.py'))
            if any(predicate(m) for m in project_imports(module_name(path)))}


def test_only_the_api_edge_imports_a_route_module():
    routes = route_modules()
    importers = production_importers(lambda m: within(m, ROUTES)) - routes - {ROUTES}
    assert importers == {API}, sorted(importers)


def test_route_modules_reach_only_the_edge_contracts_and_domain_owners():
    for module in sorted(route_modules()):
        reach = project_imports(module) - set(package_roots())
        forbidden = sorted(m for m in reach if m == API or within(m, ROUTES) or is_agent_module(m))
        assert forbidden == [], (module, forbidden)
        outside = sorted(m for m in reach if m not in ROUTE_OWNERS | {EDGE, CONTRACTS})
        assert outside == [], (module, outside)


def test_edge_helpers_reach_only_contracts_and_serve_only_the_edge_and_route_modules():
    assert module_path(EDGE) is not None
    assert project_imports(EDGE) - set(package_roots()) == {CONTRACTS}, sorted(project_imports(EDGE))
    importers = production_importers(lambda m: m == EDGE)
    assert API in importers and importers <= {API} | route_modules(), sorted(importers - {API} - route_modules())
