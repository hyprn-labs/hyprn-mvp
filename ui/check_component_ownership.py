"""Keep shared controls and scientific reading rhythm out of screen CSS.

No baseline: existing overrides must be migrated, not grandfathered. Page placement
(margin, grid position) remains legal; component internals belong to design. A page's
content width belongs to ContentColumn: screen CSS never sizes a page, section or dialog
with a layout width token, so every section of a page shares one column width.
The exact-text source editor is a separately owned design surface.
"""

import re
from pathlib import Path

CONTROL = re.compile(r'(?:\bbutton\b|\bsummary\b|\bselect\b|\.hf-btn\b)')
INTERNAL = re.compile(
    r'^(?:font(?:-.+)?|line-height|padding(?:-.+)?|height|min-height|'
    r'border(?:-.+)?|background(?:-.+)?|color|white-space|text-.+|'
    r'letter-spacing|gap|align-items|justify-content|flex-direction|--button-.+)$'
)
COMPOSITION = re.compile(
    r'\.(?:hf-(?:assertion|assertions|evidence|reading|source-reader|disclosure|brand-logo|workspace|navigation|'
    r'resource-card|settings|details-dock|details-layer|context-panel|context-reader|context-source|context-overlay|'
    r'claim|claim-button|exploration|quantity-slider|quantity-result|response-curve|record-metadata|'
    r'page-header|return-link|flow|option-list|collection-toolbar|collection-filters|'
    r'collection-status)(?=\b|__)|'
    r'(?:assumption-evidence|study-limit-item|inspector(?:-(?:section|step|model))?|'
    r'selection-inspector|panel-head|panel-body|detail-tabs|page-heading|case-list-row|canvas-toolbar|canvas-search)(?![\w-]))'
)
RAW = re.compile(r'<(?:a|button|input|select|textarea)\b')
PAGE_WIDTH = re.compile(r'(?:^|;)\s*(?:max-)?width\s*:[^;]*--(?:home|page|form|login|dialog)-max\b')
# Inline margins: margin-left/right/inline, or a margin shorthand with more than one value.
INLINE_MARGIN = re.compile(
    r'(?:^|;)\s*(?:margin-(?:left|right|inline(?:-start|-end)?)\s*:|margin\s*:\s*[^;\s]+\s+[^;]+)'
)
# The first element inside a ContentColumn and its classes.
COLUMN_CHILD = re.compile(r'<ContentColumn\b[^>]*>\s*<[A-Za-z][\w.]*\b[^>]*?\bclassName="([^"]+)"', re.S)


def column_children(root):
    """Classes of elements placed directly in a ContentColumn: the column owns their width
    and inline placement, so screen CSS may give them block margins only."""
    classes = set()
    for path in sorted((root / 'src').rglob('*.tsx')):
        for match in COLUMN_CHILD.finditer(path.read_text()):
            classes.update(match.group(1).split())
    return classes


def record_trigger_violations(text):
    triggers = re.findall(r'<ActionDialog\b[^>]*>|<summary>[^<]*</summary>', text, re.S)
    return any(re.search(r'record details|Method record', trigger, re.I) for trigger in triggers)


def css_violations(text, column_classes=frozenset()):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    errors = []
    for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', text):
        selector, body = match.groups()
        if COMPOSITION.search(selector):
            errors.append('shared composition selector: ' + selector.strip())
        if re.search(r'\.hf-panel__body\b|\b(?:td|th)\b', selector):
            if re.search(r'(?:^|;)\s*padding(?:-[a-z]+)?\s*:', body):
                errors.append('shared padding: ' + selector.strip())
        if PAGE_WIDTH.search(body):
            errors.append('page width outside ContentColumn: ' + selector.strip())
        # An inline auto margin shrinks a column child to its content width.
        if INLINE_MARGIN.search(body) and any(
            re.search(r'\.' + re.escape(name) + r'(?![\w-])', part)
            and not re.search(r'[\s>+~]', part.strip())
            for part in selector.split(',')
            for name in column_classes
        ):
            errors.append('inline margin on a ContentColumn child: ' + selector.strip())
        if CONTROL.search(selector):
            for declaration in body.split(';'):
                prop = declaration.split(':', 1)[0].strip()
                if INTERNAL.fullmatch(prop):
                    errors.append('control recipe: ' + selector.strip() + ' / ' + prop)
    return errors


def check(root):
    errors = []
    columns = column_children(root)
    for path in sorted((root / 'src').rglob('*')):
        if not path.is_file() or 'design' in path.relative_to(root / 'src').parts:
            continue
        text = path.read_text()
        if path.suffix == '.css':
            errors.extend(
                str(path.relative_to(root)) + ': ' + e for e in css_violations(text, columns)
            )
        if path.suffix == '.tsx' and re.search(r'<ActionDialog\b[^>]*(?:label|title)="(?:View evidence|Evidence detail)"', text):
            errors.append(str(path.relative_to(root)) + ': use the shared evidence details panel')
        if path.suffix == '.tsx' and re.search(r'>\s*View evidence(?: \([^<]*\))?\s*</Button>', text):
            errors.append(str(path.relative_to(root)) + ': use EvidenceDisclosure and EvidenceButton')
        if path.suffix == '.tsx' and re.search(r'<blockquote\b', text):
            errors.append(str(path.relative_to(root)) + ': use EvidenceReading for source excerpts')
        if path.suffix == '.tsx' and re.search(r'\bStatementActions\b|Statement details|Inspect statement|<ClaimButton\b', text):
            errors.append(str(path.relative_to(root)) + ': statements stay inline; open attached evidence directly')
        if path.suffix == '.tsx' and RAW.search(text):
            errors.append(str(path.relative_to(root)) + ': raw control outside design')
        if path.suffix == '.tsx' and re.search(r'<Button\b[^>]*\bvariant=["\']link["\']', text, re.S):
            errors.append(str(path.relative_to(root)) + ': use OpenLink for navigation, Button for commands')
        if path.suffix == '.tsx' and record_trigger_violations(text):
            errors.append(str(path.relative_to(root)) + ': use RecordDetails in the owning title metadata row')
        if path.suffix == '.tsx' and re.search(
            r'className="[^"]*\b(?:page-heading|model-heading|configuration-heading|back-link|model-row)\b', text
        ):
            errors.append(str(path.relative_to(root)) + ': use PageHeader, ReturnLink or ResourceCard')
        if path.suffix == '.tsx' and re.search(r'>\s*(?:Back to\b[^<]*|←[^<]*)<|returnLabel="(?!Return to )', text):
            errors.append(
                str(path.relative_to(root)) + ': returns read "Return to <destination>" (ReturnLink or RecordBar)'
            )
        if path.suffix == '.tsx' and re.search(r'Current draft|Saved version · ID', text):
            errors.append(str(path.relative_to(root)) + ': use VersionSelect labels')
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
