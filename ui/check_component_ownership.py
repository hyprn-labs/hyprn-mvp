"""Keep shared controls and scientific reading rhythm out of screen CSS.

No baseline: existing overrides must be migrated, not grandfathered. Page placement
(width, margin, grid position) remains legal; component internals belong to design.
The exact-text source editor is a separately owned design surface.
"""

import re
from pathlib import Path

CONTROL = re.compile(r'(?:\bbutton\b|\.hf-btn\b)')
INTERNAL = re.compile(
    r'^(?:font(?:-.+)?|line-height|padding(?:-.+)?|height|min-height|'
    r'border(?:-.+)?|background(?:-.+)?|color|white-space|text-.+|'
    r'letter-spacing|gap|align-items|justify-content|flex-direction|--button-.+)$'
)
COMPOSITION = re.compile(
    r'\.(?:hf-(?:assertion|assertions|evidence|reading|brand-logo|workspace|navigation|'
    r'resource-card|settings|context-panel|context-reader|context-source|context-overlay|'
    r'claim|claim-button|exploration|quantity-slider|quantity-result|response-curve)(?=\b|__)|'
    r'(?:assumption-evidence|study-limit-item|inspector(?:-(?:section|step|model))?|'
    r'selection-inspector|panel-head|panel-body|detail-tabs)(?![\w-]))'
)
RAW = re.compile(r'<(?:button|input|select|textarea)\b')


def css_violations(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    errors = []
    for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', text):
        selector, body = match.groups()
        if COMPOSITION.search(selector):
            errors.append('shared composition selector: ' + selector.strip())
        if re.search(r'\.hf-panel__body\b|\b(?:td|th)\b', selector):
            if re.search(r'(?:^|;)\s*padding(?:-[a-z]+)?\s*:', body):
                errors.append('shared padding: ' + selector.strip())
        if CONTROL.search(selector):
            for declaration in body.split(';'):
                prop = declaration.split(':', 1)[0].strip()
                if INTERNAL.fullmatch(prop):
                    errors.append('control recipe: ' + selector.strip() + ' / ' + prop)
    return errors


def check(root):
    errors = []
    for path in sorted((root / 'src').rglob('*')):
        if not path.is_file() or 'design' in path.relative_to(root / 'src').parts:
            continue
        text = path.read_text()
        if path.suffix == '.css':
            errors.extend(str(path.relative_to(root)) + ': ' + e for e in css_violations(text))
        if path.suffix == '.tsx' and RAW.search(text):
            errors.append(str(path.relative_to(root)) + ': raw control outside design')
        if path.suffix == '.tsx' and re.search(r'className="(?:primary|quiet|link)(?: |")', text):
            errors.append(
                str(path.relative_to(root)) + ': use Button variant instead of class alias'
            )
    return errors


if __name__ == '__main__':
    failures = check(Path(__file__).resolve().parent)
    for failure in failures:
        print('FAIL ' + failure)
    print('component ownership: ' + str(len(failures)) + ' violation(s)')
    raise SystemExit(bool(failures))
