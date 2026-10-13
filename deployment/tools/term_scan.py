"""Configurable term scan over the tracked contents and paths of a Git repository.

Stdlib only. The term patterns are never part of the repository: they come from pattern
files supplied by the development environment.

    python3 -B deployment/tools/term_scan.py [--patterns FILE ...] [--root DIR] [--show]

Pattern files: every ``--patterns FILE`` (repeatable) or, when none is given, the
``HYPRN_MVP_TERM_SCAN_FILES`` environment variable (a path-separator list of files). In a
pattern file, blank lines and lines starting with ``#`` are ignored; every other line is
one extended regular expression. All patterns are joined and matched case-insensitively.

The scan covers the contents of every tracked text file (files with a NUL byte in their
first 8 KiB are binary and only their path is scanned) and every tracked path, as listed
by ``git ls-files -z`` in the repository root (default: the repository holding this tool).
It prints ``path:count`` for each file with matches and a ``total:`` line. Matched text is
printed only with ``--show``.

Exit status: 0 no match, 1 at least one match, 2 no pattern file configured, a configured
pattern file unreadable or empty, an invalid pattern, or a repository that cannot be listed.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ENVIRONMENT = 'HYPRN_MVP_TERM_SCAN_FILES'
BINARY_PROBE = 8192


class ConfigurationError(Exception):
    """The scan cannot run as configured; never reported as a clean result."""


def pattern_files(arguments, environ):
    if arguments:
        return list(arguments)
    value = environ.get(ENVIRONMENT, '')
    files = [item for item in value.split(os.pathsep) if item]
    if not files:
        raise ConfigurationError('no pattern file configured: pass --patterns FILE or set ' + ENVIRONMENT)
    return files


def load_patterns(files):
    patterns = []
    for name in files:
        try:
            text = Path(name).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            # The file name may itself be sensitive configuration; report the position only.
            raise ConfigurationError('pattern file %d of %d is unreadable' % (files.index(name) + 1, len(files)))
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    if not patterns:
        raise ConfigurationError('the configured pattern files contain no pattern')
    try:
        return re.compile('|'.join('(?:' + pattern + ')' for pattern in patterns), re.IGNORECASE)
    except re.error:
        raise ConfigurationError('a configured pattern is not a valid regular expression')


def default_root():
    return Path(__file__).resolve().parents[2]


def tracked_paths(root):
    try:
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise ConfigurationError('the repository cannot be listed')
    if result.returncode:
        raise ConfigurationError('the repository cannot be listed')
    return [os.fsdecode(item) for item in result.stdout.split(b'\0') if item]


def file_text(path):
    """Text content of one tracked file, or None for a binary or missing file."""
    if path.is_symlink():
        return os.readlink(path)
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b'\0' in raw[:BINARY_PROBE]:
        return None
    return raw.decode('utf-8', errors='replace')


def scan(root, expression):
    """Return {path: [(location, matched text), ...]} for every tracked path with a match."""
    findings = {}
    for relative in tracked_paths(root):
        hits = [('path', m.group(0)) for m in expression.finditer(relative)]
        text = file_text(Path(root) / relative)
        if text is not None:
            for number, line in enumerate(text.splitlines(), 1):
                hits += [(str(number), m.group(0)) for m in expression.finditer(line)]
        if hits:
            findings[relative] = hits
    return findings


def main(argv=None, environ=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--patterns', action='append', metavar='FILE', help='pattern file (repeatable)')
    parser.add_argument('--root', help='repository root (default: the repository holding this tool)')
    parser.add_argument('--show', action='store_true', help='also print each matched text with its line')
    args = parser.parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        expression = load_patterns(pattern_files(args.patterns, environ))
        findings = scan(Path(args.root) if args.root else default_root(), expression)
    except ConfigurationError as error:
        print('term scan refused: ' + str(error), file=sys.stderr)
        return 2
    total = 0
    for relative in sorted(findings):
        hits = findings[relative]
        total += len(hits)
        print('%s:%d' % (relative, len(hits)))
        if args.show:
            for location, text in hits:
                print('  %s:%s: %s' % (relative, location, text))
    print('total: %d' % total)
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
