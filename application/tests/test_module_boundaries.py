"""Dependency guard: pure contracts stay dependency-light and own their names.

Importing pure contract/identity helpers must not load storage, HTTP clients or runtime
modules, and production code must not reach those helpers through the persistence or
orchestration modules. The temporary aliases in ``store``/``modeling``/``execution``/
``result_bindings``/``modified_runs`` exist only for test imports; production code never
uses them.

Integration seam: launcher, calculation, the retained-result reader and
integration export reach the application only through the pure modules (``contracts``,
``units``, ``scientific_configuration``, ``approach_closure``, ``execution_bundle`` and the
location rule ``locations``, read by the installation loader), and
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
import shutil
import subprocess
import sys
from collections import Counter
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
    'hyprn_mvp_app.modeling': {**dict.fromkeys(('validate',), CONTRACTS),
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
                  'hyprn_mvp_app.approach_closure', BUNDLE, 'hyprn_mvp_app.locations'})
# Integration modules bound into the attestation whose application reach is checked.
BOUND_INTEGRATION = ('hyprn_mvp_integration.launcher', 'hyprn_mvp_integration.calculation',
                     'hyprn_mvp_integration.results')
INTEGRATION_SEAM = BOUND_INTEGRATION + ('hyprn_mvp_integration.computational_export',)
# Every launch-path root. The worker is a static root: it runs inside the worker
# image and is never imported by the host-side runtime probe.
ATTESTED_ROOTS = BOUND_INTEGRATION + ('hyprn_mvp_integration.worker',)
PROJECT_SOURCES = ('application/src/', 'integration/src/')
# Reviewed attested project modules (49-entry list; the other 35 entries are the
# deployment/generator/runtime/policy pins and the reviewed WhatsOpt patches).
ATTESTED_PROJECT_FILES = frozenset({
    'application/src/hyprn_mvp_app/__init__.py',
    'application/src/hyprn_mvp_app/approach_closure.py',
    'application/src/hyprn_mvp_app/contracts.py',
    'application/src/hyprn_mvp_app/execution_bundle.py',
    'application/src/hyprn_mvp_app/locations.py',
    'application/src/hyprn_mvp_app/scientific_configuration.py',
    'application/src/hyprn_mvp_app/units.py',
    'integration/src/hyprn_mvp_integration/__init__.py',
    'integration/src/hyprn_mvp_integration/calculation.py',
    'integration/src/hyprn_mvp_integration/computational_export.py',
    'integration/src/hyprn_mvp_integration/installation.py',
    'integration/src/hyprn_mvp_integration/launcher.py',
    'integration/src/hyprn_mvp_integration/results.py',
    'integration/src/hyprn_mvp_integration/worker.py',
})
# Every reviewed dynamic-loading construct is pinned by
# (path, enclosing function, callee, count): new, removed or moved constructs fail,
# while line drift outside a reviewed seam leaves its identity unchanged.
# calculation.py: literal ``__import__('hashlib')`` (stdlib, no project code).
# worker.py: the single frozen-entry candidate seam ``load_program``
# (spec_from_file_location, then module_from_spec and exec_module on that spec),
# reached only after byte verification of the frozen bundle.
DYNAMIC_ALLOWLIST = frozenset({
    ('integration/src/hyprn_mvp_integration/calculation.py',
     'ScalarCalculation.define.validate_inputs', '__import__', 1),
    ('integration/src/hyprn_mvp_integration/calculation.py', 'ScalarParser.parse', '__import__', 1),
    ('integration/src/hyprn_mvp_integration/worker.py',
     'load_program', 'spec_from_file_location', 1),
    ('integration/src/hyprn_mvp_integration/worker.py', 'load_program', 'module_from_spec', 1),
    ('integration/src/hyprn_mvp_integration/worker.py', 'load_program', 'exec_module', 1),
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
    assert len(bound) == 49


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
    assert len(literal) == len(set(literal)) == 39
    assert {p for p in literal if p.startswith(PROJECT_SOURCES)} == ATTESTED_PROJECT_FILES
    # The only computed addition is the reviewed WhatsOpt patch directory.
    assert len(augments) == 1
    assert 'upstream/whatsopt-patches' in ast.unparse(augments[0].value)
    assert 'src' not in ast.unparse(augments[0].value)


def function_scoped_nodes(node, qualified=(), enclosing='<module>'):
    """Yield nodes with their qualified enclosing function, including nested methods.

    Decorators, defaults and bases run outside the definition's body. A class adds
    its name to method qualification, but its body is not itself a function.
    """
    yield enclosing, node
    for field, value in ast.iter_fields(node):
        nested, owner = qualified, enclosing
        if field == 'body' and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            nested = (*qualified, node.name)
            if not isinstance(node, ast.ClassDef):
                owner = '.'.join(nested)
        for child in value if isinstance(value, list) else [value]:
            if isinstance(child, ast.AST):
                yield from function_scoped_nodes(child, nested, owner)


def dynamic_loading(path):
    """(enclosing function, callee, count) for every loading construct in ``path``."""
    found = set()
    for enclosing, node in function_scoped_nodes(ast.parse(path.read_text())):
        def record(location, callee):
            # The Call and its Name describe one construct; two calls on one line
            # remain distinct by source span, even when their callee and owner match.
            found.add((enclosing, location.lineno, location.col_offset,
                       location.end_lineno, location.end_col_offset, callee))

        if isinstance(node, ast.Call):
            func = node.func
            # Builtins are reached by bare name (``import builtins`` is banned below), so
            # ``re.compile`` and similar attribute calls are not dynamic code loading.
            name = func.id if isinstance(func, ast.Name) else None
            if name in DYNAMIC_CALLS:
                record(func, name)
            elif name in REFLECTIVE and (len(node.args) < 2 or not isinstance(node.args[1], ast.Constant)):
                record(func, name)
        if isinstance(node, ast.Attribute) and node.attr in DYNAMIC_ATTRIBUTES:
            record(node, node.attr)
        elif isinstance(node, ast.Name) and node.id in DYNAMIC_ATTRIBUTES:
            record(node, node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in DYNAMIC_MODULES or alias.name.split('.')[0] in DYNAMIC_MODULES:
                    record(alias, alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if module in DYNAMIC_MODULES or module.split('.')[0] in DYNAMIC_MODULES:
                record(node, module)
            for alias in node.names:
                if (alias.name in DYNAMIC_ATTRIBUTES or alias.name in DYNAMIC_CALLS
                        or (module == 'importlib' and alias.name != 'util')):
                    record(alias, alias.name)
    counts = Counter((owner, callee) for owner, _, _, _, _, callee in found)
    return {(owner, callee, count) for (owner, callee), count in counts.items()}


def test_attested_modules_load_no_code_dynamically_outside_the_reviewed_allowlist():
    """No importlib.import_module, __import__, runpy, exec/eval or
    entry_points in attested modules, except the reviewed allowlist (exact, no stale entry)."""
    found = set()
    for name in sorted(attested_closure()):
        found |= {(relative(name), owner, callee, count)
                  for owner, callee, count in dynamic_loading(module_path(name))}
    assert found == DYNAMIC_ALLOWLIST, dict(unreviewed=sorted(found - DYNAMIC_ALLOWLIST),
                                            stale=sorted(DYNAMIC_ALLOWLIST - found))
    calculation = ast.parse((INTEGRATION / 'calculation.py').read_text())
    imports = {owner: node for owner, node in function_scoped_nodes(calculation)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == '__import__'}
    assert set(imports) == {'ScalarCalculation.define.validate_inputs', 'ScalarParser.parse'}
    for call in imports.values():
        assert len(call.args) == 1 and not call.keywords
        assert isinstance(call.args[0], ast.Constant) and call.args[0].value == 'hashlib'
    worker = ast.parse((INTEGRATION / 'worker.py').read_text())
    seam = [node for owner, node in function_scoped_nodes(worker) if owner == 'load_program']
    assignments = {node.targets[0].id: node.value for node in seam
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   and isinstance(node.targets[0], ast.Name)}
    spec = assignments['spec']
    assert isinstance(spec, ast.Call)
    assert ast.unparse(spec.func) == 'importlib.util.spec_from_file_location'
    assert isinstance(spec.args[0], ast.Constant)
    assert spec.args[0].value == '_hyprn_mvp_frozen_entry'
    assert ast.unparse(assignments['module']) == 'importlib.util.module_from_spec(spec)'
    executions = [node for node in seam if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'exec_module']
    assert len(executions) == 1 and ast.unparse(executions[0]) == 'spec.loader.exec_module(module)'


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
        assert callee in {c for _, c, _ in dynamic_loading(path)}, source
    path.write_text("import re, hashlib\ngetattr(module, 'build_model', None)\nimport importlib.util\nre.compile('x')\n")
    assert dynamic_loading(path) == set()


def test_line_drift_outside_a_reviewed_seam_keeps_the_allowlist(tmp_path):
    path = tmp_path / 'candidate.py'
    source = "def load():\n    return __import__('hashlib')\n"
    path.write_text(source)
    reviewed = dynamic_loading(path)
    assert reviewed == {('load', '__import__', 1)}
    path.write_text('# Unrelated declaration\nvalue = 1\n\n' + source)
    assert dynamic_loading(path) == reviewed


@pytest.mark.parametrize('calls', [
    "__import__('hashlib')\n    __import__('hashlib')",
    "__import__('hashlib'); __import__('hashlib')",
    "__import__('hashlib').__import__('hashlib')",
])
def test_a_second_dynamic_call_changes_the_reviewed_count(tmp_path, calls):
    path = tmp_path / 'candidate.py'
    path.write_text('def load():\n    ' + calls + '\n')
    found = dynamic_loading(path)
    reviewed = {('load', '__import__', 1)}
    assert found - reviewed == {('load', '__import__', 2)}
    assert reviewed - found == reviewed


def test_a_moved_dynamic_call_has_an_unreviewed_owner_and_a_stale_entry(tmp_path):
    path = tmp_path / 'candidate.py'
    path.write_text("def other():\n    return __import__('hashlib')\n")
    found = dynamic_loading(path)
    reviewed = {('load', '__import__', 1)}
    assert found - reviewed == {('other', '__import__', 1)}
    assert reviewed - found == reviewed


def test_a_removed_dynamic_call_leaves_a_stale_allowlist_entry(tmp_path):
    path = tmp_path / 'candidate.py'
    path.write_text('def load():\n    return None\n')
    found = dynamic_loading(path)
    reviewed = {('load', '__import__', 1)}
    assert found == set() and reviewed - found == reviewed


@pytest.mark.parametrize('source,owner', [
    ("__import__('hashlib')\n", '<module>'),
    ("class Loader:\n    def load(self):\n        __import__('hashlib')\n", 'Loader.load'),
    ("def outer():\n    def inner():\n        __import__('hashlib')\n", 'outer.inner'),
    ("class Loader:\n    def load(self):\n        def inner():\n"
     "            __import__('hashlib')\n", 'Loader.load.inner'),
    ("async def load():\n    __import__('hashlib')\n", 'load'),
    ("class Loader:\n    __import__('hashlib')\n", '<module>'),
    ("def load(value=__import__('hashlib')):\n    pass\n", '<module>'),
    ("@__import__('hashlib')\ndef load():\n    pass\n", '<module>'),
])
def test_dynamic_calls_keep_their_qualified_enclosing_function(tmp_path, source, owner):
    path = tmp_path / 'candidate.py'
    path.write_text(source)
    assert dynamic_loading(path) == {(owner, '__import__', 1)}


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
    any docker inspection; only the current 49-entry inventory passes that check (and then
    reaches the image check, stubbed here)."""
    result = probe(f'REPO={str(REPO)!r}\n' + FAIL_CLOSED_PROBE)
    assert result['old'] == 51 and result['new'] == 49
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


# Reviewed ``run_associations`` statements outside ``store`` (which holds the table) and
# ``history`` (which owns every run-row read): the association writes of ``execution`` only,
# the insert at acceptance and the update of the native identity.
RUN_ASSOCIATION_WRITES = {
    ('application/src/hyprn_mvp_app/execution.py',
     'INSERT INTO run_associations(run_id,study_id,configuration_revision_id,command_id,'
     'accepted_at) VALUES(?,?,?,?,?)'),
    ('application/src/hyprn_mvp_app/execution.py',
     'UPDATE run_associations SET store_uuid=?,process_uuid=? WHERE run_id=?'),
}


def test_run_association_reads_have_one_owner():
    """Only ``history`` reads a run's association row (with its outbox state); ``execution``,
    ``approach`` and ``result_bindings`` read through it, and ``execution`` keeps only the
    reviewed association writes."""
    statements, owners = set(), {'application/src/hyprn_mvp_app/store.py', 'application/src/hyprn_mvp_app/history.py'}
    for root in PRODUCTION:
        for path in sorted(root.rglob('*.py')):
            relative = str(path.relative_to(REPO))
            if relative in owners:
                continue
            statements |= {(relative, value) for value in string_constants(path) if 'run_associations' in value}
    assert statements == RUN_ASSOCIATION_WRITES, sorted(statements ^ RUN_ASSOCIATION_WRITES)
    owner = module_path('hyprn_mvp_app.history')
    assert any('run_associations r JOIN outbox' in value for value in string_constants(owner))


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
    ('application/src/hyprn_mvp_app/modified_runs.py', "{'5': '3', '6': '4', '8': '6'}"),
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
# ``auth`` and ``authorize`` read), the edge helpers its router uses and ``contracts``;
# ``agent_policy`` (the agent route
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
                               or m in {AUTH, STORE, CONTRACTS, 'hyprn_mvp_app.edge'},
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
# no project module but ``contracts`` and serves only ``api``, the route modules and the agent
# runtime's router. Each row scans at least one module, so it is never vacuous.

API, EDGE, ROUTES = 'hyprn_mvp_app.api', 'hyprn_mvp_app.edge', 'hyprn_mvp_app.routes'
AGENT_ROUTER = 'hyprn_mvp_app.agent_runtime.routes'
ROUTE_OWNERS = frozenset('hyprn_mvp_app.' + m for m in (
    'store', 'auth', 'readiness', 'modeling', 'configuration', 'approach', 'answers',
    'execution', 'history',
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
    serving = {API, AGENT_ROUTER} | route_modules()
    assert API in importers and importers <= serving, sorted(importers - serving)


# ---- Layer table: every application import is an edge of architecture section 7 --------
# ``LAYERS`` maps each module of ``hyprn_mvp_app`` (the route package and each agent package as
# one row) to the project modules it may import directly. The observed import graph,
# function-local imports included, must be a subgraph of it; the table must be closed, acyclic
# and equal to the "Allowed imports" table of architecture section 7, so the test and the
# specification cannot drift. ``store -> readiness`` (function-local) is drawn: ``store`` calls
# the observation owner's two pure validators inside the trusted observation write and read,
# and ``readiness`` reaches only ``contracts``, so the edge can never close a cycle.

ARCHITECTURE = REPO / 'docs/specs/architecture-and-contracts.md'
PACKAGE_ROOT = 'hyprn_mvp_app'
LAYER_PACKAGES = ('routes', 'agent_tools', 'agent_runtime', 'agent_surface')
LAYERS = {
    PACKAGE_ROOT: frozenset(),
    'contracts': frozenset(),
    'locations': frozenset(),
    'units': frozenset({'contracts'}),
    'scientific_configuration': frozenset({'contracts'}),
    'approach_closure': frozenset({'contracts', 'units'}),
    'execution_bundle': frozenset(
        {'approach_closure', 'contracts', 'scientific_configuration', 'units'}
    ),
    'readiness': frozenset({'contracts'}),
    'store': frozenset({'contracts', 'locations', 'readiness'}),
    'history': frozenset({'contracts', 'execution_bundle', 'units'}),
    'result_bindings': frozenset({'contracts', 'execution_bundle', 'history', 'units'}),
    'modified_runs': frozenset({'contracts', 'history', 'readiness'}),
    'modeling': frozenset({'contracts', 'store', 'units'}),
    'approach': frozenset(
        {'approach_closure', 'contracts', 'execution_bundle', 'history', 'store'}
    ),
    'answers': frozenset({'approach', 'contracts', 'history'}),
    'configuration': frozenset(
        {
            'approach',
            'contracts',
            'execution_bundle',
            'history',
            'modeling',
            'modified_runs',
            'readiness',
            'result_bindings',
            'scientific_configuration',
            'store',
            'units',
        }
    ),
    'execution': frozenset(
        {
            'contracts',
            'execution_bundle',
            'history',
            'readiness',
            'result_bindings',
            'scientific_configuration',
        }
    ),
    'computational_export': frozenset(
        {
            'approach_closure',
            'contracts',
            'execution_bundle',
            'history',
            'locations',
            'modified_runs',
            'result_bindings',
        }
    ),
    'dispatcher': frozenset(
        {
            'computational_export',
            'contracts',
            'execution',
            'execution_bundle',
            'modeling',
            'readiness',
            'store',
        }
    ),
    'auth': frozenset({'contracts', 'store'}),
    'ui': frozenset(),
    'edge': frozenset({'contracts'}),
    'routes': frozenset(
        {
            'answers',
            'approach',
            'auth',
            'computational_export',
            'configuration',
            'contracts',
            'edge',
            'execution',
            'history',
            'modeling',
            'modified_runs',
            'readiness',
            'result_bindings',
            'store',
        }
    ),
    'agent_tools': frozenset({'contracts'}),
    'agent_policy': frozenset({'agent_tools', 'contracts'}),
    'agent_runtime': frozenset({'agent_tools', 'auth', 'contracts', 'edge', 'store'}),
    'agent_surface': frozenset({'agent_runtime'}),
    'api': frozenset(
        {
            'agent_policy',
            'agent_runtime',
            'answers',
            'approach',
            'auth',
            'computational_export',
            'configuration',
            'contracts',
            'edge',
            'execution',
            'history',
            'modeling',
            'modified_runs',
            'result_bindings',
            'routes',
            'store',
            'ui',
        }
    ),
}


def layer(module):
    """The layer-table row of project module ``module``: the package root, the route or agent
    package it belongs to, or its own name below the package. Any other project module
    (execution integration) keeps its full name, which no row admits."""
    parts = module.split('.')
    if parts[0] != PACKAGE_ROOT:
        return module
    if len(parts) == 1:
        return PACKAGE_ROOT
    return parts[1] if parts[1] in LAYER_PACKAGES else '.'.join(parts[1:])


def observed_layers():
    """Every (row, row) import edge of the application, function-local imports included. The
    package root, which importing any module runs first, is never an edge target."""
    edges = set()
    for path in sorted(APP.rglob('*.py')):
        module = module_name(path)
        source = layer(module)
        for target in project_imports(module):
            row = layer(target)
            if row not in (source, PACKAGE_ROOT):
                edges.add((source, row))
    return edges


def outside_layers(edges):
    return sorted(
        (source, target) for source, target in edges if target not in LAYERS.get(source, ())
    )


def test_application_imports_are_a_subgraph_of_the_layer_table():
    edges = observed_layers()
    sources = {layer(module_name(path)) for path in APP.rglob('*.py')}
    assert {source for source, _ in edges} >= {'api', 'store', 'routes', 'agent_runtime'}
    assert sources <= set(LAYERS), sorted(sources - set(LAYERS))
    assert outside_layers(edges) == []


def test_layer_table_is_closed_and_acyclic():
    assert all(targets <= set(LAYERS) for targets in LAYERS.values())
    remaining = {row: set(targets) for row, targets in LAYERS.items()}
    while remaining:
        leaves = {row for row, targets in remaining.items() if not targets}
        assert leaves, ('cycle among', sorted(remaining))
        remaining = {
            row: targets - leaves for row, targets in remaining.items() if row not in leaves
        }


def architecture_layers():
    """The "Allowed imports" table of architecture section 7, as rows of module names."""
    text = ARCHITECTURE.read_text()
    section = text[text.index('\n## 7. ') : text.index('\n## 8. ')]
    lines = section[section.index('**Allowed imports**') :].splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('|'))
    rows = {}
    for line in lines[start + 2 :]:
        if not line.startswith('|'):
            break
        module, targets = (cell.strip() for cell in line.strip().strip('|').split('|'))
        names = re.findall(r'`([a-z_]+)`', module)
        assert len(names) == 1 and names[0] not in rows, line
        rows[names[0]] = frozenset(re.findall(r'`([a-z_]+)`', targets))
    return rows


def test_layer_table_equals_the_architecture_allowed_imports():
    assert architecture_layers() == LAYERS


def test_an_import_outside_the_layer_table_fails_the_subgraph_check(tmp_path, monkeypatch):
    """The table is never vacuous: one extra edge in a scratch copy of the scanned tree (the
    observation owner reaching the transaction owner) is reported, and only that edge."""
    app = tmp_path / PACKAGE_ROOT
    shutil.copytree(APP, app, ignore=shutil.ignore_patterns('__pycache__'))
    with (app / 'readiness.py').open('a') as handle:
        handle.write('\n\ndef extra():\n    from .store import Store\n    return Store\n')
    monkeypatch.setattr(sys.modules[__name__], 'APP', app)
    assert outside_layers(observed_layers()) == [('readiness', 'store')]


# Reviewed computed schema names and the version guards that bound their families.
SCHEMA_COMPUTED = {
    (
        'application/src/hyprn_mvp_app/execution_bundle.py',
        'validate_retained_bundle',
        "'ApproachClosure4' if version == '9' else 'ApproachClosure3'",
    ): ('ApproachClosure4', 'ApproachClosure3'),
    (
        'application/src/hyprn_mvp_app/execution_bundle.py',
        'validate_frozen_configuration',
        "'FrozenConfiguration' + (version or 'Legacy')",
    ): (
        'FrozenConfigurationLegacy',
        'FrozenConfiguration4',
        'FrozenConfiguration5',
        'FrozenConfiguration7',
        'FrozenConfiguration8',
    ),
    (
        'application/src/hyprn_mvp_app/scientific_configuration.py',
        'project_scientific_configuration',
        "('ConfigurationRevision' if immutable else 'ConfigurationCandidate') + version",
    ): (
        'ConfigurationCandidate1',
        'ConfigurationCandidate2',
        'ConfigurationCandidate3',
        'ConfigurationCandidate4',
        'ConfigurationRevision1',
        'ConfigurationRevision2',
        'ConfigurationRevision3',
        'ConfigurationRevision4',
    ),
    (
        'application/src/hyprn_mvp_app/scientific_configuration.py',
        'project_scientific_configuration',
        (
            "('ModelingConfigurationRevision' if immutable else "
            "'ModelingConfiguration') + private_version"
        ),
    ): (
        'ModelingConfiguration2',
        'ModelingConfiguration3',
        'ModelingConfigurationRevision2',
        'ModelingConfigurationRevision3',
    ),
    (
        'application/src/hyprn_mvp_app/units.py',
        'active_ports',
        (
            "'ModelRevisionRead4' if isinstance(model, dict) and "
            "'model_revision_id' in model else 'ModelDraftRead4'"
        ),
    ): ('ModelRevisionRead4', 'ModelDraftRead4'),
}
SCHEMA_VERSION_GUARDS = {
    ('application/src/hyprn_mvp_app/execution_bundle.py', 'validate_frozen_configuration'): (
        "version not in (None, '4', '5', '7', '8')",
        (
            "frozen['configuration']['schema_version'] == '4' and version != "
            "frozen_version(frozen['model_snapshot'], frozen['approach_closure'])"
        ),
    ),
    (
        'application/src/hyprn_mvp_app/scientific_configuration.py',
        'project_scientific_configuration',
    ): (
        (
            'not isinstance(configuration, dict) or '
            "configuration.get('schema_version') not in ('1', '2', '3', '4')"
        ),
        "version == '4'",
        "version in ('2', '3', '4')",
        "version in ('3', '4')",
    ),
}


SCHEMA_VERSION_ASSIGNMENTS = {
    ('application/src/hyprn_mvp_app/execution_bundle.py', 'validate_frozen_configuration'): {
        'version': "version = frozen.get('schema_version')",
    },
    (
        'application/src/hyprn_mvp_app/scientific_configuration.py',
        'project_scientific_configuration',
    ): {
        'version': "version = configuration['schema_version']",
        'private_version': "private_version = '3' if version == '4' else version",
    },
}


def schema_roots(path, source):
    """Unresolved schema dispatch fails closed, including new computed expressions."""
    tree = ast.parse(source)
    names = set()
    aliases = {
        alias.asname or alias.name: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            expected = SCHEMA_VERSION_GUARDS.get((path, node.name))
            if expected is not None:
                actual = tuple(
                    ast.unparse(n.test)
                    for n in ast.walk(node)
                    if isinstance(n, ast.If) and 'version' in ast.unparse(n.test)
                )
                assert actual == expected, (path, node.name, 'version guards changed')
            for name, expression in SCHEMA_VERSION_ASSIGNMENTS.get((path, node.name), {}).items():
                bindings = [
                    n
                    for n in ast.walk(node)
                    if isinstance(n, ast.Name)
                    and n.id == name
                    and isinstance(n.ctx, (ast.Store, ast.Del))
                ]
                assignments = [
                    n
                    for n in ast.walk(node)
                    if isinstance(n, ast.Assign)
                    and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)
                    and n.targets[0].id == name
                ]
                assert (
                    len(bindings) == 1
                    and len(assignments) == 1
                    and ast.dump(assignments[0], include_attributes=False)
                    == ast.dump(ast.parse(expression).body[0], include_attributes=False)
                ), (path, node.name, name, 'version assignment changed')

    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    dispatch = (
        'validate',
        'closed',
        '_closed',
        'validate_execution',
        'definition',
        'validator',
        'definitions',
        'authored_schema',
        'documents_contract',
    )
    imported_dispatch = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in dispatch
    }
    callable_names = imported_dispatch | {'validate', 'closed', '_closed', 'validate_execution'}
    if not path.endswith(('/contracts.py', '/installation.py')):
        for node in ast.walk(tree):
            name = (
                node.id
                if isinstance(node, ast.Name)
                else (node.attr if isinstance(node, ast.Attribute) else None)
            )
            if aliases.get(name, name) not in dispatch or not isinstance(
                getattr(node, 'ctx', None), ast.Load
            ):
                continue
            if isinstance(node, ast.Name) and name not in callable_names:
                continue
            parent = parents.get(node)
            scope = parent
            while scope is not None and not isinstance(
                scope, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                scope = parents.get(scope)
            if (
                isinstance(node, ast.Name)
                and scope is not None
                and any(
                    isinstance(local, ast.Name)
                    and local.id == name
                    and isinstance(local.ctx, ast.Store)
                    for local in ast.walk(scope)
                )
            ):
                continue  # A local data binding shadows an imported name.
            # AiiDA port validation is not named contract-schema dispatch.
            if (
                path == 'integration/src/hyprn_mvp_integration/calculation.py'
                and ast.unparse(node) == 'spec.inputs.validator'
                and isinstance(parent, ast.Assign)
                and [ast.unparse(t) for t in parent.targets] == ['parent_validator']
            ):
                continue
            assert isinstance(parent, ast.Call) and parent.func is node, (
                'Unreviewed callable schema alias',
                path,
                getattr(node, 'lineno', None),
            )
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        callee = (
            call.func.id
            if isinstance(call.func, ast.Name)
            else (call.func.attr if isinstance(call.func, ast.Attribute) else None)
        )
        callee = aliases.get(callee, callee)
        if callee not in dispatch:
            continue
        # Installation validates its closed configuration, not a named wire definition.
        if path.endswith('/installation.py'):
            continue
        # The schema owner implements dispatch; consumers below must name every root.
        if path.endswith('/contracts.py'):
            continue
        assert call.args, (path, call.lineno, 'missing schema name')
        argument = call.args[0]
        parent = parents.get(call)
        while parent is not None and not isinstance(
            parent, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            parent = parents.get(parent)
        scopes = []
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scopes.append(parent.name)
            parent = parents.get(parent)
        function = '.'.join(reversed(scopes)) if scopes else '<module>'
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            names.add(argument.value)
        elif (
            path.endswith('/approach_closure.py')
            and function == '_closed'
            or path.endswith('/execution_bundle.py')
            and function == 'closed'
        ):
            assert callee == 'validate' and ast.unparse(argument) == 'name'
        else:
            key = path, function, ast.unparse(argument)
            assert key in SCHEMA_COMPUTED, ('Unreviewed schema dispatch', key)
            names.update(SCHEMA_COMPUTED[key])
    return names


def test_every_attested_schema_name_is_a_reviewed_execution_root():
    from hyprn_mvp_app.contracts import EXECUTION_ROOTS

    found = set()
    for path in ATTESTED_PROJECT_FILES:
        found.update(schema_roots(path, (REPO / path).read_text()))
    assert found == set(EXECUTION_ROOTS)


@pytest.mark.parametrize(
    'source',
    [
        'def check(value): validate(dynamic, value)',
        'def check(value): contracts.definition(dynamic)',
        'def check(value): validate_execution(prefix + version, value)',
        'def check(value): contracts.validator(dynamic)',
    ],
)
def test_unreviewed_computed_schema_dispatch_refuses(source):
    with pytest.raises(AssertionError, match='Unreviewed schema dispatch'):
        schema_roots('application/src/hyprn_mvp_app/units.py', source)


@pytest.mark.parametrize(
    'source',
    [
        'check = validate',
        'def check(value): return forward(contracts.validator, value)',
        'def check(name, value): validate(name, value)',
        'contracts.validator(dynamic)',
    ],
)
def test_unreviewed_schema_forwarding_refuses(source):
    with pytest.raises(AssertionError, match='Unreviewed'):
        schema_roots('application/src/hyprn_mvp_app/units.py', source)


def test_imported_schema_alias_and_module_literal_are_covered():
    source = "from owner import validate as admit; admit('Model4', value)"
    assert schema_roots('application/src/hyprn_mvp_app/units.py', source) == {'Model4'}


def test_widened_configuration_family_requires_root_review():
    path = 'application/src/hyprn_mvp_app/scientific_configuration.py'
    source = (REPO / path).read_text()
    tree = ast.parse(source)
    function = next(
        n for n in tree.body if getattr(n, 'name', '') == 'project_scientific_configuration'
    )
    guard = next(
        n
        for n in ast.walk(function)
        if isinstance(n, ast.Tuple)
        and [getattr(e, 'value', None) for e in n.elts] == ['1', '2', '3', '4']
    )
    guard.elts.append(ast.Constant(value='5'))
    with pytest.raises(AssertionError, match='version guards changed'):
        schema_roots(path, ast.unparse(tree))


@pytest.mark.parametrize(
    'replacement',
    [
        "private_version = '2' if version == '4' else version",
        "private_version = '3' if version == '4' else version; private_version = '9'",
        "private_version = '3' if version == '4' else version; version = '9'",
    ],
)
def test_configuration_projection_assignment_requires_root_review(replacement):
    path = 'application/src/hyprn_mvp_app/scientific_configuration.py'
    tree = ast.parse((REPO / path).read_text())
    function = next(
        n for n in tree.body if getattr(n, 'name', '') == 'project_scientific_configuration'
    )
    assignment = next(
        n
        for n in function.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == 'private_version'
    )
    position = function.body.index(assignment)
    function.body[position : position + 1] = ast.parse(replacement).body
    with pytest.raises(AssertionError, match='version assignment changed'):
        schema_roots(path, ast.unparse(ast.fix_missing_locations(tree)))


def test_launch_path_opens_only_the_attested_execution_schema():
    code = """
opened = []
def audit(event, args):
    if event == 'open' and 'contracts/schemas/' in str(args[0]):
        opened.append(str(args[0]).split('contracts/schemas/', 1)[1])
sys.addaudithook(audit)
from hyprn_mvp_integration import launcher, calculation, results
from hyprn_mvp_app import contracts, units
for name in contracts.EXECUTION_ROOTS:
    contracts.validator(name)
print(json.dumps(opened))
"""
    # Calculation imports AiiDA, so this isolated probe uses the runner's native interpreter.
    from scoped_fixture import APPROVED_PYTHON

    result = subprocess.run(
        [
            APPROVED_PYTHON,
            '-B',
            '-c',
            'import sys,json;sys.path[:0]='
            + repr([str(REPO / 'application/src'), str(REPO / 'integration/src')])
            + ';'
            + code,
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == ['execution.schema.json']


def test_documents_schema_belongs_only_to_the_application_inventory(tmp_path):
    result = probe(f"""
sys.path.insert(0, {str(REPO / 'deployment')!r})
from pathlib import Path
import application_runtime, modeling_runtime
from hyprn_mvp_integration import launcher
application_runtime.ui_dist = lambda: Path({str(tmp_path)!r})
print(json.dumps([sorted(application_runtime.hashes()),
                  sorted(modeling_runtime.source_hashes()),
                  sorted(launcher.execution_source_hashes())]))
""")
    application, modeling, execution = map(set, result)
    documents = 'contracts/schemas/documents.schema.json'
    assert documents in application
    assert documents not in modeling | execution
    assert len(modeling) == 23 and len(execution) == 49
    assert {
        'contracts/schemas/model.schema.json',
        'contracts/schemas/execution.schema.json',
    } <= modeling & execution
