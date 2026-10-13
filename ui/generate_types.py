"""Generate data-only TypeScript declarations from the public HYPRN MVP schema."""
import json
import argparse
from pathlib import Path
root = Path(__file__).resolve().parent
def ts(s):
    if '$ref' in s: return s['$ref'].rsplit('/', 1)[1]
    if 'enum' in s: return ' | '.join(json.dumps(x) for x in s['enum'])
    if 'const' in s: return json.dumps(s['const'])
    for key in ('oneOf', 'anyOf'):
        if key in s:
            branches = s[key]
            if s.get('type') == 'object':
                base = {k: v for k, v in s.items() if k != key}
                # Constraints without a type inherit the enclosing object.
                # Intersect instead of replacing base property types, so both
                # schemas apply. Required-only branches reuse base declarations.
                branches = [{**branch, 'type': branch.get('type', 'object'),
                             'properties': {**{name: s.get('properties', {}).get(name, {})
                                               for name in branch.get('required', [])},
                                            **branch.get('properties', {})},
                             'required': list(dict.fromkeys(s.get('required', []) + branch.get('required', [])))}
                            for branch in branches]
                return '(' + ts(base) + ' & (' + ' | '.join(ts(branch) for branch in branches) + '))'
            return '(' + ' | '.join(ts(x) for x in branches) + ')'
    kind = s.get('type')
    if kind == 'array': return 'Array<' + ts(s.get('items', {})) + '>'
    if kind == 'object':
        props = s.get('properties', {})
        if not props and isinstance(s.get('additionalProperties'), dict):
            return 'Record<string, ' + ts(s['additionalProperties']) + '>'
        if not props and s.get('additionalProperties') is not False: return 'Record<string, unknown>'
        return '{ ' + '; '.join(json.dumps(k) + ('' if k in s.get('required', []) else '?') + ': ' + ts(v) for k,v in props.items()) + ' }'
    return {'string':'string', 'integer':'number', 'number':'number', 'boolean':'boolean', 'null':'null'}.get(kind, 'unknown')
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=root.parent / 'contracts/hyprn-mvp.openapi.yaml')
    parser.add_argument('--output', type=Path, default=root / 'src/contract.ts')
    args = parser.parse_args()
    schemas = json.loads(args.input.read_text())['components']['schemas']
    args.output.write_text('// Generated from contracts/hyprn-mvp.openapi.yaml by ui/generate_types.py.\n' + '\n'.join('export type ' + name + ' = ' + ts(schema) + ';' for name,schema in schemas.items()) + '\n')


if __name__ == '__main__':
    main()
