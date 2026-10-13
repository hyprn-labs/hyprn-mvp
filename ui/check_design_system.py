"""Baseline-aware HYPRN MVP Foundry style guard for ui/src (stdlib only).

Scans ui/src/**/*.{ts,tsx,css}, excluding ui/src/design/** (the design layer itself), for:
  colour        hex colours (3/4/6/8 digits), rgb()/rgba()/hsl()/hsla(); in CSS also the
                white/black keywords in declaration values
  px            CSS px literals other than 1px and 2px, outside @media/@container preludes
  inline-style  TS/TSX style attributes (style= in any form), setAttribute('style'), cssText
  font          CSS font-family declarations and font shorthand (except inherit/initial/
                unset/revert); TS/TSX fontFamily keys

Existing violations are recorded in design-baseline.json keyed by (file, rule, normalised
snippet) with counts, so moving lines never fails. A normal run prints WARN for baselined
counts and FAIL (exit 1) only where a count exceeds its baseline. --update-baseline rewrites
the baseline and exits 0. Not wired into the build, the tests or the served runtime.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HEX = re.compile(r'(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])')
FUNC = re.compile(r'(?<![\w-])(?:rgba?|hsla?)\(')
DECL = re.compile(r'([\w-]+)\s*:\s*([^;{}]*)')
KEYWORD = re.compile(r'(?<![\w-])(?:white|black)(?![\w-])', re.IGNORECASE)
PX = re.compile(r'(?<![\w.#-])(\d*\.?\d+)px(?![\w-])')
AT_PRELUDE = re.compile(r'@(?:media|container)\b[^{]*', re.IGNORECASE)
FONT_DECL = re.compile(r'(?<![\w-])(font-family|font)\s*:\s*([^;{}]*)', re.IGNORECASE)
CSS_WIDE = {'inherit', 'initial', 'unset', 'revert'}
STYLE_ATTR = re.compile(r'(?<![\w$.-])style\s*=(?!=)')
STYLE_DECLARATION = re.compile(r'\b(?:const|let|var)\s+style\s*=')
SET_STYLE = re.compile(r'setAttribute\(\s*[\'"`]style[\'"`]')
CSS_TEXT = re.compile(r'\bcssText\b')
FONT_FAMILY_KEY = re.compile(r'(?<![\w$-])[\'"]?fontFamily[\'"]?\s*:')


def norm(text):
    return re.sub(r'\s+', ' ', text.strip().lower())[:80]


def strip_css_comments(text):
    return re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)


def scan_css(text):
    found = []
    for lineno, line in enumerate(strip_css_comments(text).splitlines(), 1):
        for m in HEX.finditer(line):
            found.append((lineno, 'colour', norm(m.group(0))))
        for m in FUNC.finditer(line):
            found.append((lineno, 'colour', norm(m.group(0))))
        for d in DECL.finditer(line):
            for m in KEYWORD.finditer(d.group(2)):
                found.append((lineno, 'colour', norm(m.group(0))))
        unprefixed = AT_PRELUDE.sub(lambda m: ' ' * len(m.group(0)), line)
        for m in PX.finditer(unprefixed):
            if float(m.group(1)) not in (1.0, 2.0):
                found.append((lineno, 'px', norm(m.group(0))))
        for m in FONT_DECL.finditer(line):
            prop, value = m.group(1).lower(), m.group(2).strip().lower()
            if prop == 'font' and value in CSS_WIDE:
                continue
            found.append((lineno, 'font', norm(prop + ': ' + value)))
    return found


def scan_ts(text):
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in HEX.finditer(line):
            found.append((lineno, 'colour', norm(m.group(0))))
        for m in FUNC.finditer(line):
            found.append((lineno, 'colour', norm(m.group(0))))
        declared = {m.end() for m in STYLE_DECLARATION.finditer(line)}
        for m in STYLE_ATTR.finditer(line):
            if m.end() in declared:
                continue
            found.append((lineno, 'inline-style', 'style='))
        for m in SET_STYLE.finditer(line):
            found.append((lineno, 'inline-style', "setattribute('style')"))
        for m in CSS_TEXT.finditer(line):
            found.append((lineno, 'inline-style', 'csstext'))
        for m in FONT_FAMILY_KEY.finditer(line):
            found.append((lineno, 'font', 'fontfamily'))
    return found


def scan(root):
    src = root / 'src'
    design = src / 'design'
    results = {}
    files = sorted(p for p in src.rglob('*') if p.is_file() and p.suffix in ('.ts', '.tsx', '.css'))
    for path in files:
        if design in path.parents:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        rel = path.relative_to(root).as_posix()
        hits = scan_css(text) if path.suffix == '.css' else scan_ts(text)
        if hits:
            results[rel] = hits
    return results


def counts_of(results):
    counts = {}
    for rel, hits in results.items():
        per = counts.setdefault(rel, {})
        for _, rule, snippet in hits:
            key = rule + '|' + snippet
            per[key] = per.get(key, 0) + 1
    return counts


def write_baseline(path, counts):
    data = {'version': 1, 'violations': {rel: dict(sorted(v.items())) for rel, v in sorted(counts.items())}}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main(argv=None):
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description='HYPRN MVP Foundry style guard (warn existing, fail new).')
    parser.add_argument('--root', type=Path, default=here, help='ui directory to scan (default: this script directory)')
    parser.add_argument('--baseline', type=Path, default=None, help='baseline JSON (default: <root>/design-baseline.json)')
    parser.add_argument('--update-baseline', action='store_true')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    baseline_path = args.baseline or (root / 'design-baseline.json')
    results = scan(root)
    counts = counts_of(results)
    if args.update_baseline:
        write_baseline(baseline_path, counts)
        total = sum(sum(v.values()) for v in counts.values())
        print('baseline updated: ' + str(total) + ' violation(s) in ' + str(len(counts)) + ' file(s) -> ' + str(baseline_path))
        return 0
    baseline = {}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding='utf-8')).get('violations', {})
    failures = 0
    for rel in sorted(set(counts) | set(baseline)):
        now = counts.get(rel, {})
        base = baseline.get(rel, {})
        baselined = sum(min(n, base.get(k, 0)) for k, n in now.items())
        if baselined:
            print('WARN ' + rel + ': ' + str(baselined) + ' baselined violation(s)')
        for key, n in sorted(now.items()):
            if n > base.get(key, 0):
                rule, snippet = key.split('|', 1)
                for lineno, r, s in results[rel]:
                    if r == rule and s == snippet:
                        failures += 1
                        print('FAIL ' + rel + ':' + str(lineno) + ':' + rule + ':' + snippet)
        for key, n in sorted(base.items()):
            if now.get(key, 0) < n:
                print('NOTE ' + rel + ': ' + key + ' dropped from ' + str(n) + ' to ' + str(now.get(key, 0))
                      + '; the baseline can be tightened with --update-baseline')
    if failures:
        print('design guard: ' + str(failures) + ' new violation occurrence(s)')
        return 1
    print('design guard: no new violations')
    return 0


if __name__ == '__main__':
    sys.exit(main())
