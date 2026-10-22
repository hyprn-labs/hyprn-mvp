"""Tests for the HYPRN MVP Foundry design tooling (stdlib unittest; temp dirs are off-cloud).

Run: python3 ui/test_design_tooling.py
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

UI = Path(__file__).resolve().parent
TOKENS = UI.parent / 'design-system/tokens.json'
GENERATOR = UI / 'design_tokens.py'


def run(script, *args):
    return subprocess.run([sys.executable, str(script)] + [str(a) for a in args], capture_output=True, text=True)


class DesignTokensGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hyprn-mvp-design-tokens-')
        self.dir = Path(self.tmp.name)
        self.data = json.loads(TOKENS.read_text(encoding='utf-8'))

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self, name='tokens.css'):
        out = self.dir / name
        result = run(GENERATOR, '--tokens', TOKENS, '--out', out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return out

    def test_deterministic(self):
        a = self.generate('a.css').read_bytes()
        b = self.generate('b.css').read_bytes()
        self.assertEqual(a, b)

    def test_follows_tokens_order(self):
        css = self.generate().read_text(encoding='utf-8')
        light = css.split(':root, [data-theme="light"] {', 1)[1].split('}', 1)[0]
        positions = [light.index('--' + t['name'] + ':') for t in self.data['color']['tokens']]
        self.assertEqual(positions, sorted(positions))

    def test_theme_selectors_and_color_scheme(self):
        css = self.generate().read_text(encoding='utf-8')
        self.assertIn(':root, [data-theme="light"] {\n  color-scheme: light;', css)
        self.assertIn('[data-theme="dark"] {\n  color-scheme: dark;', css)
        self.assertIn('@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n    color-scheme: dark;', css)
        light, dark, media = (css.split(':root, [data-theme="light"] {', 1)[1].split('}', 1)[0],
                              css.split('\n[data-theme="dark"] {', 1)[1].split('}', 1)[0],
                              css.split(':root:not([data-theme="light"]) {', 1)[1].split('}', 1)[0])
        for token in self.data['color']['tokens']:
            name = '--' + token['name'] + ': '
            self.assertIn(name + token['value']['light'] + ';', light, token['name'])
            self.assertIn(name + token['value']['dark'] + ';', dark, token['name'])
            self.assertIn(name + token['value']['dark'] + ';', media, token['name'])
            self.assertEqual(css.count(name), 3, token['name'])

    def test_invariants_once_and_themed_shadows(self):
        css = self.generate().read_text(encoding='utf-8')
        invariant = css.split(':root {', 1)[1].split('}', 1)[0]
        for group in ('spacing', 'radius', 'size'):
            for token in self.data[group]['tokens']:
                self.assertEqual(css.count('--' + token['name'] + ':'), 1, token['name'])
                self.assertIn('--' + token['name'] + ': ' + token['value'] + ';', invariant)
        for name in ('sans', 'condensed', 'mono'):
            self.assertEqual(css.count('--font-' + name + ':'), 1)
            self.assertIn('--font-' + name + ': ' + self.data['type']['families'][name] + ';', invariant)
        for group in self.data['type']['groups']:
            for style in group['styles']:
                prefix = '--type-' + style['name']
                self.assertIn(prefix + '-size: ' + style['fontSize'] + ';', invariant)
                self.assertIn(prefix + '-line: ' + style['lineHeight'] + ';', invariant)
                self.assertIn(prefix + '-weight: ' + str(style['fontWeight']) + ';', invariant)
                self.assertEqual(prefix + '-tracking:' in invariant, 'letterSpacing' in style)
        for name in ('shadow-float', 'focus-ring'):
            self.assertNotIn('--' + name, invariant)
            self.assertEqual(css.count('--' + name + ':'), 3)

    def test_check_detects_stale_and_accepts_fresh(self):
        out = self.generate()
        fresh = run(GENERATOR, '--tokens', TOKENS, '--out', out, '--check')
        self.assertEqual(fresh.returncode, 0, fresh.stdout)
        raw = bytearray(out.read_bytes())
        raw[-2] = ord('x') if raw[-2] != ord('x') else ord('y')
        out.write_bytes(bytes(raw))
        stale = run(GENERATOR, '--tokens', TOKENS, '--out', out, '--check')
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn('stale', stale.stdout)

    def test_committed_tokens_css_is_fresh(self):
        result = run(GENERATOR, '--check')
        self.assertEqual(result.returncode, 0, result.stdout)


GUARD = UI / 'check_design_system.py'


class DesignSystemGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hyprn-mvp-design-guard-')
        self.root = Path(self.tmp.name)
        (self.root / 'src/design').mkdir(parents=True)
        self.baseline = self.root / 'design-baseline.json'
        self.baseline.write_text(json.dumps({'version': 1, 'violations': {}}) + '\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def guard(self, *extra):
        return run(GUARD, '--root', self.root, *extra)

    def test_design_layer_is_excluded(self):
        self.write('src/design/foundry.css', '.x { color: #ff0000; font: 600 14px/20px serif; }\n')
        self.write('src/design/components.tsx', 'const a = <div style={{ color: "#fff" }} />;\n')
        result = self.guard()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('FAIL', result.stdout)
        self.assertNotIn('WARN', result.stdout)

    def test_warn_existing_fail_new(self):
        self.write('src/screen.css', '.a {\n  color: #12ab34;\n}\n')
        first = self.guard()
        self.assertEqual(first.returncode, 1, first.stdout)
        self.assertIn('FAIL src/screen.css:2:colour:#12ab34', first.stdout)
        update = self.guard('--update-baseline')
        self.assertEqual(update.returncode, 0, update.stdout)
        data = json.loads(self.baseline.read_text(encoding='utf-8'))
        self.assertEqual(data, {'version': 1, 'violations': {'src/screen.css': {'colour|#12ab34': 1}}})
        self.assertTrue(self.baseline.read_text(encoding='utf-8').endswith('}\n'))
        warned = self.guard()
        self.assertEqual(warned.returncode, 0, warned.stdout)
        self.assertIn('WARN src/screen.css', warned.stdout)
        self.write('src/screen.css', '.a {\n  color: #12ab34;\n}\n.b {\n  background: rgb(1, 2, 3);\n}\n')
        failed = self.guard()
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertIn('FAIL src/screen.css:5:colour:rgb(', failed.stdout)
        self.assertNotIn(':2:colour', failed.stdout)

    def test_moving_lines_does_not_fail(self):
        self.write('src/screen.css', '.a { color: #abc; }\n')
        self.guard('--update-baseline')
        self.write('src/screen.css', '\n\n\n.z { margin: 0; }\n.a { color: #abc; }\n')
        result = self.guard()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_dropped_count_prints_note(self):
        self.write('src/screen.css', '.a { color: #abc; }\n.b { color: #abc; }\n')
        self.guard('--update-baseline')
        self.write('src/screen.css', '.a { color: #abc; }\n')
        result = self.guard()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('NOTE', result.stdout)
        self.assertIn('tightened', result.stdout)

    def test_px_rules(self):
        self.write('src/screen.css', '.a { border: 1px solid var(--line); outline: 2px solid var(--focus); }\n'
                                     '@media (max-width: 820px) { .a { gap: var(--space-2); } }\n'
                                     '@container (min-width: 600px) { .b { margin: 0; } }\n')
        clean = self.guard()
        self.assertEqual(clean.returncode, 0, clean.stdout)
        self.write('src/screen.css', '.a { font-size: 14px; }\n')
        flagged = self.guard()
        self.assertEqual(flagged.returncode, 1, flagged.stdout)
        self.assertIn('FAIL src/screen.css:1:px:14px', flagged.stdout)

    def test_inline_style_and_font_rules(self):
        self.write('src/View.tsx', 'export const V = () => <div style={{ width: 3 }} />;\n')
        tsx = self.guard()
        self.assertEqual(tsx.returncode, 1, tsx.stdout)
        self.assertIn('FAIL src/View.tsx:1:inline-style:style=', tsx.stdout)
        self.write('src/View.tsx', 'export const V = 1;\n')
        self.write('src/theme.ts', 'export const t = { fontFamily: "Arial" };\n')
        ts = self.guard()
        self.assertEqual(ts.returncode, 1, ts.stdout)
        self.assertIn('FAIL src/theme.ts:1:font:fontfamily', ts.stdout)
        self.write('src/theme.ts', 'export const t = 1;\n')
        self.write('src/screen.css', '.a { font-family: Georgia, serif; }\n')
        css = self.guard()
        self.assertEqual(css.returncode, 1, css.stdout)
        self.assertIn('FAIL src/screen.css:1:font:font-family: georgia, serif', css.stdout)
        self.write('src/screen.css', '.a { font: inherit; white-space: nowrap; }\n')
        ok = self.guard()
        self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_css_keywords_and_other_inline_forms(self):
        self.write('src/screen.css', '.a { background: white; color: Black; }\n')
        css = self.guard()
        self.assertEqual(css.returncode, 1, css.stdout)
        self.assertIn(':colour:white', css.stdout)
        self.assertIn(':colour:black', css.stdout)
        self.write('src/screen.css', '.a { margin: 0; }\n')
        self.write('src/dom.ts', 'el.setAttribute("style", "x");\nel.style.cssText = "x";\nconst html = `<b style="x">`;\n')
        ts = self.guard()
        self.assertEqual(ts.returncode, 1, ts.stdout)
        self.assertIn("src/dom.ts:1:inline-style:setattribute('style')", ts.stdout)
        self.assertIn('src/dom.ts:2:inline-style:csstext', ts.stdout)
        self.assertIn('src/dom.ts:3:inline-style:style=', ts.stdout)


class ComponentOwnership(unittest.TestCase):
    def test_record_details_has_one_shared_trigger_recipe(self):
        from check_component_ownership import record_trigger_violations, css_violations
        for trigger in ('<ActionDialog label="Run record details">',
                        '<ActionDialog title="Method record">',
                        '<summary>Prediction record details</summary>'):
            self.assertTrue(record_trigger_violations(trigger))
        self.assertFalse(record_trigger_violations('<RecordDetails kind="Run">'))
        self.assertTrue(css_violations('.screen .hf-record-metadata {margin:0}'))
        self.assertTrue(css_violations('.page-heading {align-items:center}'))
        self.assertTrue(css_violations('.case-list-row {padding:0}'))

    def test_screen_cannot_resize_shared_controls_or_assertions(self):
        from check_component_ownership import css_violations
        for selector in ('.dialog .hf-btn', '.row > button', '.row > summary', '.row > select'):
            self.assertTrue(css_violations(selector + '{font-size:var(--type-small-size)}'))
            self.assertTrue(css_violations(selector + '{min-height:var(--control-desk)}'))
        self.assertTrue(css_violations('.hf-assertion {margin:0}'))
        self.assertTrue(css_violations('.card .hf-panel__body {padding:var(--space-6)}'))
        self.assertTrue(css_violations('.results td {padding-block:var(--space-1)}'))
        self.assertFalse(css_violations('.results td {text-align:right}'))
        self.assertFalse(css_violations('.toolbar {display:flex;gap:var(--space-2)}'))
        self.assertFalse(css_violations('.toolbar>.hf-btn {margin-left:auto}'))

    def test_page_and_section_widths_come_only_from_content_column(self):
        from check_component_ownership import css_violations
        for declaration in ('max-width:var(--home-max)', 'width:var(--form-max)',
                            'max-width: var(--login-max)', 'width:min(var(--page-max),100%)',
                            'max-width:var(--dialog-max)'):
            with self.subTest(declaration=declaration):
                self.assertTrue(css_violations('[aria-label="Study brief"]{' + declaration + '}'))
        self.assertFalse(css_violations('.home-page{margin:var(--page-gutter) auto}'))
        # A ContentColumn child takes block margins only: an inline auto margin shrinks it.
        children = frozenset({'home-page', 'login'})
        for body in ('margin:var(--page-gutter) auto', 'margin:0 var(--space-3)',
                     'margin-inline:auto', 'margin-left:var(--space-2)'):
            with self.subTest(body=body):
                self.assertTrue(css_violations('.home-page{' + body + '}', children))
        self.assertFalse(css_violations('.home-page{margin-block:var(--page-gutter)}', children))
        self.assertFalse(css_violations('.home-page h1{margin:0 auto}', children))
        self.assertFalse(css_violations('.homepage{margin:0 auto}', children))
        # A wide table may scroll inside its own box at a token width.
        self.assertFalse(css_violations('.variables-scroll table{min-width:var(--home-max)}'))

    def test_workspace_recipes_have_no_screen_override_escape(self):
        from check_component_ownership import css_violations
        for family in ("workspace", "navigation", "resource-card", "settings", "source-reader", "disclosure",
                       "context-panel", "details-dock", "details-layer", "claim", "claim-button",
                       "flow", "option-list", "collection-toolbar", "collection-filters",
                       "collection-status"):
            for suffix in ("", "__body", "--selected"):
                with self.subTest(family=family, suffix=suffix):
                    selector = ".screen .hf-" + family + suffix
                    self.assertTrue(css_violations(selector + "{padding:var(--space-6)}"))
                    self.assertTrue(css_violations(selector + "{border-radius:var(--radius-xs)}"))
        self.assertFalse(css_violations(".profile-placement {margin:var(--space-6) auto}"))
        for selector in (".inspector-section", ".inspector .section-header", ".detail-tabs",
                         ".canvas-toolbar", ".canvas-search"):
            self.assertTrue(css_violations(selector + "{padding:var(--space-4)}"))
        self.assertFalse(css_violations(".model-region:not(.inspector-collapsed) {grid-row:2}"))
        self.assertFalse(css_violations(".connected-inspector {grid-row:2;max-height:80vh}"))
        self.assertFalse(css_violations(".case-grid {display:grid;gap:var(--space-4)}"))

    def test_raw_controls_and_class_aliases_are_rejected(self):
        from check_component_ownership import check
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'src').mkdir()
            (root / 'src/Screen.tsx').write_text('<button>Save</button>')
            self.assertTrue(check(root))
            (root / 'src/Screen.tsx').write_text('<a href="/reader">Read</a>')
            self.assertTrue(check(root))
            (root / 'src/Screen.tsx').write_text('<Button variant="link">Read</Button>')
            self.assertTrue(check(root))
            (root / 'src/Screen.tsx').write_text('<OpenLink href="/reader">Read</OpenLink>')
            self.assertFalse(check(root))
            (root / 'src/Screen.tsx').write_text('<Button className="primary">Save</Button>')
            self.assertTrue(check(root))
            for trigger in ('<ActionDialog title="Evidence detail" label="View evidence">',
                            '<Button>View evidence (2)</Button>',
                            '<blockquote>Source excerpt</blockquote>'):
                (root / 'src/Screen.tsx').write_text(trigger)
                self.assertTrue(check(root))
            (root / 'src/Screen.tsx').write_text('<Button variant="primary">Save</Button>')
            self.assertFalse(check(root))


if __name__ == '__main__':
    unittest.main()
