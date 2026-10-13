"""Isolated-fixture launch-worker entry: run THIS tree's execution launcher.

A development interpreter's startup .pth may name another checkout, so a bare `-m` launcher
started from a worktree or a selected-release copy could execute that checkout's launcher.
This entry removes every project path that is not this tree, prepends this tree's
integration/src and application/src, refuses any project module already imported or resolved
elsewhere, records the actual module files and hashes, then runs the launcher exactly as `-m`
would. Fixture use only; production uses the release bootstrap (release_binding.py
exec-module).

  scoped_fixture_launcher.py --check-only          print the binding record, run nothing
  scoped_fixture_launcher.py --runtime-root R ...  record evidence under R/evidence, run launcher
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import uuid

TREE = Path(__file__).resolve().parents[2]
ROOTS = (TREE / 'integration/src', TREE / 'application/src')
PACKAGES = ('hyprn_mvp_integration', 'hyprn_mvp_app')
# Scoped roots are <scratch root>/hyprn-mvp-test-<uuid> (deployment/local_paths.py); the
# scoped child environment always names the scratch root explicitly.
SCRATCH_ROOT = Path(os.environ.get('HYPRN_MVP_SCRATCH_ROOT') or os.path.realpath(tempfile.gettempdir()))
SCOPE_PREFIX = 'hyprn-mvp-test-'


def _project(entry):
    """A package or deployment root of this or any other checkout. Other checkouts (for example
    one named by the interpreter's startup .pth) are recognized by layout, not by package name,
    so a checkout that predates the current package names is still removed from the path."""
    path = Path(entry or os.getcwd())
    try:
        return (any((path / name).is_dir() for name in PACKAGES) or (path / 'dispatch_runtime.py').is_file()
                or (path.name == 'src' and path.parent.name in ('application', 'integration')))
    except OSError:
        return False


def _record(name):
    spec = importlib.util.find_spec(name)
    if spec is None or not spec.origin:
        raise SystemExit('Fixture launcher refused: ' + name + ' not found')
    file = Path(spec.origin).resolve()
    if not any(file.is_relative_to(root) for root in ROOTS):
        raise SystemExit('Fixture launcher refused: ' + name + ' resolves outside ' + str(TREE) + ': ' + str(file))
    return dict(file=str(file), sha256=hashlib.sha256(file.read_bytes()).hexdigest())


def bind():
    loaded = [n for n in sys.modules if n.partition('.')[0] in PACKAGES]
    if loaded:
        raise SystemExit('Fixture launcher refused: project module already imported: ' + loaded[0])
    removed = [p for p in sys.path if _project(p) and Path(p or os.getcwd()).resolve() not in ROOTS]
    sys.path[:] = [str(r) for r in ROOTS] + [p for p in sys.path if p not in removed and Path(p or '.').resolve() not in ROOTS]
    modules = {name: _record(name) for name in ('hyprn_mvp_app', 'hyprn_mvp_integration', 'hyprn_mvp_integration.launcher')}
    return dict(tree=str(TREE), pid=os.getpid(), executable=sys.executable, cwd=os.getcwd(),
                sys_path=list(sys.path), removed_sys_path=removed, modules=modules)


def main():
    args = sys.argv[1:]
    check_only = args[:1] == ['--check-only']
    if check_only:
        args = args[1:]
    record = bind()
    if check_only:
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0
    if args[:1] == ['--runtime-root'] and len(args) > 1:
        root = Path(args[1])
        evidence = root / 'evidence'
        if (root.parent == SCRATCH_ROOT and root.name.startswith(SCOPE_PREFIX)
                and evidence.is_dir() and not evidence.is_symlink()):
            name = 'fixture-launcher-binding-' + str(os.getpid()) + '-' + uuid.uuid4().hex + '.json'
            with (evidence / name).open('x') as output:
                json.dump(dict(record, argv=args), output, indent=2, sort_keys=True)
    sys.argv = [record['modules']['hyprn_mvp_integration.launcher']['file'], *args]
    runpy.run_module('hyprn_mvp_integration.launcher', run_name='__main__', alter_sys=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
