"""Declared-data validation only. Candidate source is parsed, never imported."""
import ast
import json
import math
import re
import sys
import textwrap

MAX_SOURCE = 65536
MAX_REQUEST = 262144

def validate_source(source, inputs, outputs):
    if not isinstance(source, str) or len(source.encode('utf-8')) > MAX_SOURCE:
        raise ValueError("source: limit is 65536 UTF-8 bytes")
    if not source.strip():
        raise ValueError("source: enter the Python compute body")
    try:
        tree = ast.parse("def compute(self, inputs, outputs):\n" + textwrap.indent(source, "    "))
    except (SyntaxError, ValueError, RecursionError) as error:
        line = max(1, getattr(error, 'lineno', 2) - 1)
        raise ValueError(f"source line {line}: {getattr(error, 'msg', 'invalid syntax')}") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in ('inputs','outputs'):
            allowed = inputs if node.value.id == 'inputs' else outputs
            if not isinstance(node.slice, ast.Constant) or node.slice.value not in allowed:
                raise ValueError(f"source line {node.lineno-1}: undeclared {node.value.id} port")
    return True


def unit(value):
    value = value or ''
    if value == 'dimensionless': value = ''
    if not isinstance(value, str) or len(value) > 128: raise ValueError('units: invalid unit expression')
    if value:
        try: tree = ast.parse(value, mode='eval')
        except SyntaxError: raise ValueError('units: invalid unit expression') from None
        allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Name, ast.Load, ast.Constant)
        for node in ast.walk(tree):
            if not isinstance(node, allowed): raise ValueError('units: use native unit symbols and multiplication/division/powers')
            if isinstance(node, ast.Constant) and (type(node.value) not in (int,float) or not math.isfinite(node.value) or abs(node.value)>100):
                raise ValueError('units: numeric exponent out of bounds')
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                exponent = node.right
                if isinstance(exponent, ast.UnaryOp): exponent = exponent.operand
                if not isinstance(node.left, ast.Name) or not isinstance(exponent, ast.Constant) or type(exponent.value) is not int or abs(exponent.value)>16: raise ValueError('units: bounded integer powers only')
        if len(list(ast.walk(tree)))>40: raise ValueError('units: expression too complex')
    return value

def scalar(value):
    if isinstance(value, str):
        if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', value.strip()):
            raise ValueError('enter an explicit finite real scalar')
        value = float(value)
    if type(value) not in (int, float): raise ValueError('enter an explicit finite real scalar')
    try: finite = math.isfinite(value)
    except OverflowError: finite = False
    if not finite: raise ValueError('enter an explicit finite real scalar')
    return value

def convert(value, entered, expected):
    from openmdao.utils.units import unit_conversion
    entered, expected = unit(entered), unit(expected)
    if not entered and not expected: return value
    if not entered or not expected: raise ValueError('units are dimensionally incompatible')
    try: factor, offset = unit_conversion(entered, expected)
    except (ValueError, TypeError, KeyError): raise ValueError(f'units {entered} are not compatible with {expected}') from None
    if offset != 0: raise ValueError('affine unit conversions are not approved; enter the model unit')
    return scalar(value * factor)

def contract(port):
    if port.get('shape') != '1' or port.get('type') != 'Float': raise ValueError(f"{port.get('name')}: only real scalar ports are supported")
    units = unit(port.get('units'))
    convert(1,units,units)
    return {'id':port['id'], 'units':units, 'shape':'1', 'type':'Float'}

def validate_configuration(ports, assignments):
    if not isinstance(assignments,list): raise ValueError('assignments must be rows identified by native port ID')
    by_id={}
    for row in assignments:
        if not isinstance(row,dict) or type(row.get('port_id')) is not int: raise ValueError('port_id: native integer identity required')
        if row['port_id'] in by_id: raise ValueError('duplicate port_id')
        by_id[row['port_id']]=row
    expected={p['id'] for p in ports}
    extra=set(by_id)-expected
    if extra: raise ValueError(f'Configuration does not match model: replaced/missing native ports {sorted(extra)}')
    result=[]
    for port in sorted(ports,key=lambda p:p['id']):
        name=f"{port['name']} (port {port['id']})"
        try:
            signature=contract(port)
            row=by_id.get(port['id'])
            if row is None: raise ValueError('enter a value; unassigned is not zero')
            if row.get('contract') and row['contract'] != signature: raise ValueError('port units/shape/type changed; review and explicitly accept the target contract')
            value=scalar(row.get('value'))
            provenance=row.get('provenance')
            if not isinstance(provenance,str) or not provenance.strip(): raise ValueError('record input provenance')
            normalized=convert(value,row.get('units'),port.get('units'))
            result.append({'port_id':port['id'], 'value':normalized, 'units':signature['units'], 'provenance':provenance,
                'entered_value':value,'entered_units':unit(row.get('units')), 'contract':signature})
        except ValueError as error: raise ValueError(name+': '+str(error)) from None
    return result

def validate_criteria(outputs, criteria):
    by_id={p['id']:p for p in outputs}
    result=[]
    for criterion in criteria:
        port=by_id.get(criterion.get('port_id'))
        if not port: raise ValueError('criterion: choose a current output port')
        if criterion.get('operator') not in ('<','<=','>','>=','=='): raise ValueError('criterion: unsupported operator')
        contract(port)
        threshold=convert(scalar(criterion.get('threshold')),criterion.get('units'),port.get('units'))
        result.append({'port_id':port['id'],'operator':criterion['operator'],'threshold':threshold,'units':unit(port.get('units'))})
    return result

def main():
    raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
    try:
        if len(raw) > MAX_REQUEST: raise ValueError('request exceeds 262144 bytes')
        request = json.loads(raw)
        if request.get('operation') == 'configuration':
            settings=request.get('numerical_settings',{'mode':'deterministic'})
            if settings != {'mode':'deterministic'}: raise ValueError('only deterministic scalar settings are supported')
            result={'assignments':validate_configuration(request['ports'],request['assignments']),
                'criteria':validate_criteria(request.get('outputs',[]),request.get('criteria',[])), 'numerical_settings':settings}
            print(json.dumps(result,allow_nan=False)); return 0
        if request.get('operation') != 'source': raise ValueError('unsupported operation')
        for component in request['components']:
            for port in component['ports']: contract(port)
            try:
                validate_source(component['source'], [p['name'] for p in component['ports'] if p['io_mode']=='in'], [p['name'] for p in component['ports'] if p['io_mode']=='out'])
            except ValueError as error:
                raise ValueError(str(component['name']) + ': ' + str(error)) from None
        print(json.dumps({'valid': True}))
    except (ValueError, KeyError, TypeError, RecursionError) as error:
        print(json.dumps({'error': str(error)[:1000]}))
        return 1
    return 0

if __name__ == '__main__': sys.exit(main())
