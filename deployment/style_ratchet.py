"""Readability ratchet for Python and TypeScript (standard library only).

Rules, with the line limit of ``[tool.ruff] line-length`` in ``pyproject.toml`` (the prettier
``printWidth`` in ``ui/.prettierrc.json`` must be the same):

- Python: ``E501`` (line too long), ``E702`` (statements chained with ``;``) and ``E703``
  (useless trailing ``;``), reported by the ruff of the locked native environment with
  ``--ignore-noqa``, so a ``# noqa`` comment never hides a violation;
- TypeScript and JavaScript (``.ts``, ``.tsx``, ``.mjs``, ``.cjs``, ``.js``): ``long-line``,
  a line over the limit that is more than one word and does not end in a URL;
- formatting: ``ruff format --check`` and ``prettier --list-different``.

The baseline (``deployment/style_baseline.json``) records a base commit and, per file, the
violation counts of each rule at that commit. A covered file is then checked as follows:

- present at the base commit: no count may rise, and no violation may sit on a line added or
  changed since the base commit. Existing violations may stay and the file need not be
  formatted, so a change never forces a full-file reformat;
- absent at the base commit (new or renamed): it must be formatted and free of violations.

``--update`` lowers the counts to the current ones and moves the base commit to ``HEAD``; it
refuses while the check fails or a covered file has uncommitted changes, so it never raises a
count. ``--create`` writes the first baseline and refuses when one exists.

Excluded files are never checked. Each exclusion is read from its owner, never copied here:
the attested execution sources (``ATTESTED_PROJECT_FILES`` and the ``execution_source_hashes()``
literal, until they are reformatted before their next attestation, which removes this
exclusion), test files whose bytes are pinned by hash (every module-level table in a test
module that maps repository paths to SHA-256 digests), the generated files whose bytes are
asserted elsewhere, and captured fixtures (any file below a ``fixtures`` folder). A missing
owner, excluded file, tool, baseline or base commit fails the check; it never skips.

ruff runs with ``--no-cache`` and prettier without ``--cache``: nothing is written into the
checkout. Run it as ``./hyprn-mvp dev check style-ratchet``, or directly with the locked native
interpreter: ``<native environment>/bin/python -I -B deployment/style_ratchet.py [--update]``.
"""

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib

REPO = Path(__file__).resolve().parents[1]
BASELINE = 'deployment/style_baseline.json'
SCHEMA = 'hyprn_mvp.style_baseline/1'
PYTHON_RULES = ('E501', 'E702', 'E703')
LONG_LINE = 'long-line'
RULES = (*PYTHON_RULES, LONG_LINE)
PYTHON_SUFFIXES = ('.py',)
SCRIPT_SUFFIXES = ('.ts', '.tsx', '.mjs', '.cjs', '.js')
PRETTIER = 'ui/node_modules/prettier/bin/prettier.cjs'
PRETTIER_CONFIG = 'ui/.prettierrc.json'
# Owners of the attested execution sources, excluded until their format-only re-attestation.
ATTESTED_OWNER = ('application/tests/test_module_boundaries.py', 'ATTESTED_PROJECT_FILES')
LAUNCHER_OWNER = ('integration/src/hyprn_mvp_integration/launcher.py', 'execution_source_hashes')
# Generated files whose bytes are asserted by their generators' checks.
GENERATED = (
    'contracts/hyprn-mvp.openapi.yaml',
    'ui/src/contract.ts',
    'ui/src/design/tokens.css',
    'contracts/schemas/execution.schema.json',
)
PIN_PATH = re.compile(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]+')
DIGEST = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')
URL_TAIL = re.compile(r'[a-z][a-z0-9+.-]*://\S+$')
HUNK = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')


class StyleError(RuntimeError):
    """The ratchet cannot run: a tool, owner, exclusion, baseline or base commit is missing."""


def git(repo, *args):
    command = ['git', '-C', str(repo), '-c', 'core.quotePath=false', *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise StyleError('git ' + ' '.join(args[:2]) + ' failed: ' + result.stderr.strip())
    return result.stdout


def covered_suffix(path):
    return path.endswith(PYTHON_SUFFIXES + SCRIPT_SUFFIXES)


def is_python(path):
    return path.endswith(PYTHON_SUFFIXES)


# --- Limit and tools -------------------------------------------------------------------------


def line_limit(repo):
    """The limit of [tool.ruff] line-length, which prettier's printWidth must equal."""
    try:
        ruff = tomllib.loads((repo / 'pyproject.toml').read_text())['tool']['ruff']
        prettier = json.loads((repo / PRETTIER_CONFIG).read_text())
    except (OSError, KeyError, ValueError) as error:
        raise StyleError('formatter configuration missing: ' + str(error)) from None
    limit = ruff.get('line-length')
    if type(limit) is not int or limit != prettier.get('printWidth'):
        raise StyleError('pyproject.toml line-length and ui/.prettierrc.json printWidth differ')
    return limit


def pinned_versions(repo=REPO):
    """ruff's exact pin in the native uv.lock group and prettier's in ui/package.json."""
    try:
        groups = tomllib.loads((repo / 'pyproject.toml').read_text())['dependency-groups']
        ruff = [e.split('==', 1)[1] for e in groups['native'] if e.startswith('ruff==')]
        package = json.loads((repo / 'ui/package.json').read_text())
        prettier = package.get('devDependencies', {}).get('prettier')
    except (OSError, KeyError, ValueError, AttributeError) as error:
        raise StyleError('formatter pins unreadable: ' + str(error)) from None
    if len(ruff) != 1 or not prettier:
        raise StyleError('ruff or prettier is not pinned in pyproject.toml or ui/package.json')
    return ruff[0], prettier


def tools(repo=REPO):
    """The pinned ruff of the running locked environment, node and the locked prettier."""
    ruff_version, prettier_version = pinned_versions(repo)
    ruff = Path(sysconfig.get_path('scripts')) / 'ruff'
    if not ruff.is_file():
        raise StyleError(
            'ruff missing: run ./hyprn-mvp dev check style-ratchet (locked native environment)'
        )
    node = shutil.which('node')
    prettier = repo / PRETTIER
    if node is None:
        raise StyleError('node missing: install Node.js to check TypeScript formatting')
    if not prettier.is_file():
        raise StyleError('prettier missing: run npm --prefix ui ci')
    found = {
        'ruff': run([str(ruff), '--version']).stdout.strip(),
        'prettier': run([node, str(prettier), '--version']).stdout.strip(),
    }
    if found != {'ruff': 'ruff ' + ruff_version, 'prettier': prettier_version}:
        raise StyleError('formatter versions differ from their pins: ' + json.dumps(found))
    return {'ruff': str(ruff), 'node': node, 'prettier': str(prettier)}


def run(command, *, cwd=None, codes=(0,)):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode not in codes:
        detail = (result.stderr or result.stdout).strip()[-400:]
        raise StyleError(Path(command[0]).name + ' failed: ' + detail)
    return result


# --- Exclusions ------------------------------------------------------------------------------


def module_tree(repo, relative):
    path = repo / relative
    if not path.is_file():
        raise StyleError('exclusion owner missing: ' + relative)
    return ast.parse(path.read_text(), filename=relative)


def assigned(tree, name):
    """The value node of the module-level assignment of ``name``."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    return None


def string_items(node, where):
    if not isinstance(node, (ast.List, ast.Set, ast.Tuple)) or not all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts
    ):
        raise StyleError('exclusion owner is not a literal of strings: ' + where)
    return [e.value for e in node.elts]


def attested_files(repo):
    """ATTESTED_PROJECT_FILES and the execution_source_hashes() path literal."""
    owner, name = ATTESTED_OWNER
    value = assigned(module_tree(repo, owner), name)
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == 'frozenset'
    ):
        value = value.args[0] if len(value.args) == 1 else None
    files = set(string_items(value, owner + '::' + name))
    owner, name = LAUNCHER_OWNER
    function = next(
        (
            n
            for n in module_tree(repo, owner).body
            if isinstance(n, ast.FunctionDef) and n.name == name
        ),
        None,
    )
    literals = [] if function is None else [assigned(function, 'paths')]
    if len(literals) != 1 or literals[0] is None:
        raise StyleError('exclusion owner missing: ' + owner + '::' + name)
    files.update(string_items(literals[0], owner + '::' + name))
    return files


def pinned_test_files(repo, tracked):
    """Every path named by a pin table: a module-level dict literal in a test module whose keys
    are all repository paths and whose values are all SHA-256 digests."""
    files = set()
    modules = (p for p in tracked if '/tests/' in p and is_python(p) and (repo / p).is_file())
    for relative in sorted(modules):
        tree = module_tree(repo, relative)
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            keys, values = node.value.keys, node.value.values
            if keys and all(
                isinstance(k, ast.Constant)
                and isinstance(k.value, str)
                and PIN_PATH.fullmatch(k.value)
                and isinstance(v, ast.Constant)
                and isinstance(v.value, str)
                and DIGEST.fullmatch(v.value)
                for k, v in zip(keys, values)
            ):
                files.update(k.value for k in keys)
    return files


def captured(path):
    """A captured fixture: any file below a ``fixtures`` folder, tracked or new."""
    return 'fixtures' in path.split('/')[:-1]


def exclusions(repo, tracked):
    """{path: reason} of every excluded file named by an owner; each must exist. Captured
    fixtures are excluded by their location (``captured``)."""
    excluded = {}
    for reason, paths in (
        ('attested execution source', attested_files(repo)),
        ('hash-pinned test file', pinned_test_files(repo, tracked)),
        ('generated file', GENERATED),
    ):
        for path in paths:
            excluded.setdefault(path, reason)
    missing = sorted(p for p in excluded if not (repo / p).is_file())
    if missing:
        raise StyleError('excluded files missing: ' + ', '.join(missing))
    return excluded


# --- Measurement -----------------------------------------------------------------------------


def tracked_files(repo):
    return set(git(repo, 'ls-files', '-z').split('\0')) - {''}


def covered_files(repo, tracked):
    """Tracked and untracked (not ignored) files with a covered suffix, minus the exclusions."""
    untracked = set(git(repo, 'ls-files', '-z', '--others', '--exclude-standard').split('\0'))
    excluded = exclusions(repo, tracked)
    return sorted(
        p
        for p in (tracked | untracked) - {''}
        if covered_suffix(p) and p not in excluded and not captured(p) and (repo / p).is_file()
    )


def long_lines(text, limit):
    """1-based rows of the lines over ``limit`` that are more than one word and do not end in
    a URL starting within the limit (the exemptions of E501)."""
    rows = []
    for row, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if len(line) <= limit or len(stripped.split()) < 2:
            continue
        url = URL_TAIL.search(line)
        if url is not None and url.start() <= limit:
            continue
        rows.append(row)
    return rows


def roots(files):
    """The top-level folders (or root-level files) that hold ``files``. ruff and git walk
    these folders themselves and their output is filtered to ``files``, so no source path
    appears on their command lines: guarded test processes refuse a command line that names a
    management entry point, even as a file to read."""
    return sorted({p.split('/', 1)[0] for p in files})


def ruff_report(repo, files, tool, *arguments):
    """ruff's JSON report over the folders holding ``files``, keyed by repository path and
    limited to ``files``; refuses when ruff would not read one of ``files``."""
    config = ['--no-cache', '--config', str(repo / 'pyproject.toml')]
    root = repo.resolve()
    listed = run([tool['ruff'], 'check', *config, '--show-files', *roots(files)], cwd=repo)
    seen = {
        str(Path(line.strip()).resolve().relative_to(root))
        for line in listed.stdout.splitlines()
        if line.strip()
    }
    unread = sorted(set(files) - seen)
    if unread:
        raise StyleError('ruff does not read: ' + ', '.join(unread))
    command = [tool['ruff'], *arguments, *config, '--output-format', 'json', *roots(files)]
    result = run(command, cwd=repo, codes=(0, 1))
    report = {}
    for item in json.loads(result.stdout or '[]'):
        path = str(Path(item['filename']).resolve().relative_to(root))
        if path in files:
            report.setdefault(path, []).append(item)
    return report


def violations(repo, files, tool):
    """{path: [(rule, row)]} for the given covered files."""
    found = {path: [] for path in files}
    limit = line_limit(repo)
    python = [p for p in files if is_python(p)]
    if python:
        report = ruff_report(repo, python, tool, 'check', '--ignore-noqa')
        for path, items in report.items():
            for item in items:
                if item.get('code') not in PYTHON_RULES:
                    raise StyleError(path + ': ruff reported ' + str(item.get('message')))
                found[path].append((item['code'], item['location']['row']))
    for path in files:
        if not is_python(path):
            text = (repo / path).read_text(encoding='utf-8')
            found[path].extend((LONG_LINE, row) for row in long_lines(text, limit))
    return found


def unformatted(repo, files, tool):
    """The given covered files that the formatters would change."""
    changed = set()
    python = [p for p in files if is_python(p)]
    scripts = [p for p in files if not is_python(p)]
    if python:
        changed.update(ruff_report(repo, python, tool, 'format', '--check'))
    if scripts:
        command = [tool['node'], tool['prettier'], '--list-different', '--no-editorconfig']
        command += ['--config', str(repo / PRETTIER_CONFIG), *scripts]
        result = run(command, cwd=repo, codes=(0, 1))
        changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return changed


def counts(found):
    """{path: {rule: count}} without empty entries."""
    table = {}
    for path, items in found.items():
        tally = Counter(rule for rule, _ in items)
        if tally:
            table[path] = dict(sorted(tally.items()))
    return table


def changed_rows(repo, base, files):
    """{path: rows added or changed since ``base``} for files present at ``base``."""
    rows = {path: set() for path in files}
    if not files:
        return rows
    diff = git(
        repo,
        'diff',
        '-U0',
        '--no-color',
        '--no-ext-diff',
        '--no-textconv',
        '--no-renames',
        '--src-prefix=a/',
        '--dst-prefix=b/',
        base,
        '--',
        *roots(files),
    )
    current = None
    for line in diff.splitlines():
        if line.startswith('+++ '):
            current = line[len('+++ b/') :] if line.startswith('+++ b/') else None
        elif current in rows and (match := HUNK.match(line)):
            start, length = int(match[1]), 1 if match[2] is None else int(match[2])
            rows[current].update(range(start, start + length))
    return rows


# --- Baseline and check ----------------------------------------------------------------------


def load_baseline(repo):
    path = repo / BASELINE
    if not path.is_file():
        raise StyleError('baseline missing: ' + BASELINE)
    try:
        baseline = json.loads(path.read_text())
    except ValueError:
        raise StyleError('baseline malformed: ' + BASELINE) from None
    base = baseline.get('base') if isinstance(baseline, dict) else None
    if (
        not isinstance(baseline, dict)
        or baseline.get('schema') != SCHEMA
        or not isinstance(base, str)
        or not COMMIT.fullmatch(base)
        or not isinstance(baseline.get('files'), dict)
    ):
        raise StyleError('baseline malformed: ' + BASELINE)
    if baseline.get('line_length') != line_limit(repo):
        raise StyleError('baseline line length differs from the configured limit')
    head = subprocess.run(
        ['git', '-C', str(repo), 'merge-base', '--is-ancestor', base, 'HEAD'], capture_output=True
    )
    if head.returncode:
        raise StyleError('base commit ' + base + ' is missing or not an ancestor of HEAD')
    return baseline


def evaluate(repo=REPO, tool=None):
    """The failures of the ratchet on the working tree, one string per failure."""
    tool = tool or tools()
    baseline = load_baseline(repo)
    base = baseline['base']
    tracked = tracked_files(repo)
    files = covered_files(repo, tracked)
    at_base = set(git(repo, 'ls-tree', '-r', '-z', '--name-only', base).split('\0'))
    existing = [p for p in files if p in at_base]
    new = [p for p in files if p not in at_base]
    found = violations(repo, files, tool)
    current = counts(found)
    rows = changed_rows(repo, base, existing)
    failures = []
    for path in existing:
        before = baseline['files'].get(path, {})
        for rule, count in current.get(path, {}).items():
            if count > before.get(rule, 0):
                failures.append(f'{path}: {rule} rose from {before.get(rule, 0)} to {count}')
        for rule, row in found[path]:
            if row in rows[path]:
                failures.append(f'{path}:{row}: {rule} on a line changed since the base commit')
    for path in new:
        failures.extend(f'{path}:{row}: {rule} in a new file' for rule, row in found[path])
    failures.extend(
        f'{path}: new file is not formatted' for path in sorted(unformatted(repo, new, tool))
    )
    return failures


def write_baseline(repo, table, base):
    document = {'schema': SCHEMA, 'base': base, 'line_length': line_limit(repo), 'files': table}
    (repo / BASELINE).write_text(json.dumps(document, indent=1, sort_keys=True) + '\n')


def head_counts(repo, tool):
    """Counts over the covered files committed at HEAD, which must have no local changes."""
    tracked = tracked_files(repo)
    at_head = set(git(repo, 'ls-tree', '-r', '-z', '--name-only', 'HEAD').split('\0'))
    files = [p for p in covered_files(repo, tracked) if p in at_head]
    status = git(repo, 'status', '--porcelain', '-z', '--', *roots(files)).split('\0')
    if {entry[3:] for entry in status if entry} & set(files):
        raise StyleError('covered files have uncommitted changes; commit them first')
    return counts(violations(repo, files, tool)), git(repo, 'rev-parse', 'HEAD').strip()


def create(repo=REPO, tool=None):
    tool = tool or tools()
    if (repo / BASELINE).exists():
        raise StyleError('baseline exists: use --update, which only lowers counts')
    table, head = head_counts(repo, tool)
    write_baseline(repo, table, head)
    return table


def update(repo=REPO, tool=None):
    """Lower the baseline to the current counts at HEAD; never raise a count."""
    tool = tool or tools()
    failures = evaluate(repo, tool)
    if failures:
        raise StyleError('the ratchet fails; --update never raises a count: ' + failures[0])
    old = load_baseline(repo)['files']
    table, head = head_counts(repo, tool)
    for path, rules in table.items():
        for rule, count in rules.items():
            if count > old.get(path, {}).get(rule, 0):
                raise StyleError(f'{path}: {rule} would rise; --update never raises a count')
    write_baseline(repo, table, head)
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--update', action='store_true', help='lower the baseline to HEAD')
    action.add_argument('--create', action='store_true', help='write the first baseline')
    args = parser.parse_args(argv)
    try:
        if args.create or args.update:
            table = (create if args.create else update)()
            print(json.dumps({'baseline': BASELINE, 'files': len(table)}))
            return 0
        failures = evaluate()
    except StyleError as error:
        print('style-ratchet refused: ' + str(error), file=sys.stderr)
        return 2
    for failure in failures:
        print(failure)
    print(json.dumps({'style_ratchet': 'fail' if failures else 'pass', 'failures': len(failures)}))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
