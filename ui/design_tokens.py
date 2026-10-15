"""Generate ui/src/design/tokens.css from design-system/tokens.json.

Stdlib only. Deterministic: output follows tokens.json order. Run with --check
to fail (exit 1) when the generated file on disk is stale.
"""
import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
TOKENS_LABEL = 'design-system/tokens.json'
DEFAULT_TOKENS = root.parent / TOKENS_LABEL
DEFAULT_OUT = root / 'src/design/tokens.css'


def block(selector, lines, indent=''):
    body = ''.join(indent + '  ' + line + '\n' for line in lines)
    return indent + selector + ' {\n' + body + indent + '}\n'


def theme_lines(data, theme):
    lines = ['color-scheme: ' + theme + ';']
    for token in data['color']['tokens']:
        lines.append('--' + token['name'] + ': ' + token['value'][theme] + ';')
    for token in data['shadow']['tokens']:
        lines.append('--' + token['name'] + ': ' + token['value'][theme] + ';')
    return lines


def invariant_lines(data):
    lines = []
    for group in ('spacing', 'radius', 'size'):
        for token in data[group]['tokens']:
            lines.append('--' + token['name'] + ': ' + token['value'] + ';')
    for name, stack in data['type']['families'].items():
        lines.append('--font-' + name + ': ' + stack + ';')
    for group in data['type']['groups']:
        for style in group['styles']:
            prefix = '--type-' + style['name']
            lines.append(prefix + '-size: ' + style['fontSize'] + ';')
            lines.append(prefix + '-line: ' + style['lineHeight'] + ';')
            lines.append(prefix + '-weight: ' + str(style['fontWeight']) + ';')
            if 'letterSpacing' in style:
                lines.append(prefix + '-tracking: ' + style['letterSpacing'] + ';')
    return lines


def render(data, source_label):
    header = (
        '/* GENERATED FILE - do not hand-edit.\n'
        ' * Source: ' + source_label + ' (' + data['name'] + ' v' + str(data['version']) + ')\n'
        ' * Generator: ui/design_tokens.py (run `python3 ui/design_tokens.py`; `--check` detects staleness).\n'
        ' */\n'
    )
    parts = [
        header,
        block(':root', invariant_lines(data)),
        block(':root, [data-theme="light"]', theme_lines(data, 'light')),
        block('[data-theme="dark"]', theme_lines(data, 'dark')),
        '@media (prefers-color-scheme: dark) {\n'
        + block(':root:not([data-theme="light"])', theme_lines(data, 'dark'), indent='  ')
        + '}\n',
    ]
    return '\n'.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokens', type=Path, default=DEFAULT_TOKENS)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--check', action='store_true', help='exit 1 if the output file is stale')
    args = parser.parse_args(argv)
    data = json.loads(args.tokens.read_text(encoding='utf-8'))
    css = render(data, TOKENS_LABEL)
    if args.check:
        current = args.out.read_text(encoding='utf-8') if args.out.exists() else None
        if current != css:
            print('stale: ' + str(args.out) + ' does not match tokens.json; run python3 ui/design_tokens.py')
            return 1
        print('fresh: ' + str(args.out))
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(css, encoding='utf-8')
    print('wrote ' + str(args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
