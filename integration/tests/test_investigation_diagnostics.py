"""Data-only diagnostics policy checks; no candidate source is executed here.

Synthetic coordinates test formatting only. Actual frozen-code/traceback
correspondence is exercised by investigation-worker and investigation-native.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import pytest
from hyprn_mvp_integration import worker


def mapped(tmp_path, source=b"raise RuntimeError('downstream failed')\n"):
    sha=hashlib.sha256(source).hexdigest()
    row=dict(instance_id='11111111-1111-4111-8111-111111111111',
        definition_version_id='22222222-2222-4222-8222-222222222222',
        source_path='sources/'+sha+'.py',source_sha256=sha,
        generated_path='generated/impl/component.py',generated_line_start=3,
        generated_line_end=2+len(source.decode('utf-8-sig').splitlines()))
    normalized=source.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
    generated=('class Component:\n    def _authored_compute(self):\n'+
        ''.join('        '+line+'\n' for line in normalized.splitlines())).encode()
    files={row['source_path']:source,row['generated_path']:generated}
    for name,raw in files.items():
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    manifest=dict(files=[dict(path=p,sha256=hashlib.sha256(raw).hexdigest()) for p,raw in files.items()])
    return manifest,dict(entries=[row]),row


@pytest.mark.parametrize('source,kind,first,last',[
    (b"assert False, 'Required pressure closure not reached'\n",'AssertionError',1,1),
    (b"assert (\n    False\n), 'Required pressure closure not reached'\n",'AssertionError',1,3),
    (b"raise RuntimeError(\n    'downstream failed'\n)\n",'RuntimeError',1,3),
    (b"\xef\xbb\xbf# retained\r\nassert False, 'literal'\r\n",'AssertionError',2,2),
])
def test_catalog_proves_exact_normalized_authored_lines(tmp_path,source,kind,first,last):
    manifest,mapping,row=mapped(tmp_path,source)
    catalog=worker.diagnostic_catalog(tmp_path,manifest,mapping)
    assert catalog[row['generated_path']][1][0][:3]==(first,last,kind)


@pytest.mark.parametrize('change',['hash','source_hash','range','generated_bytes','path','duplicate','syntax'])
def test_unproved_mapping_never_invents_location(tmp_path,change):
    manifest,mapping,row=mapped(tmp_path)
    if change=='hash':manifest['files'][0]['sha256']='a'*64
    elif change=='source_hash':row['source_sha256']='a'*64
    elif change=='range':row['generated_line_start']+=1
    elif change=='generated_bytes':
        p=tmp_path/row['generated_path'];p.write_bytes(p.read_bytes().replace(b'failed',b'spoofed'))
        manifest['files'][1]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    elif change=='path':row['generated_path']='generated/../../private.py'
    elif change=='duplicate':mapping['entries'].append(deepcopy(row))
    else:
        manifest,mapping,row=mapped(tmp_path,b'not valid python !!!\n')
    assert not worker.diagnostic_catalog(tmp_path,manifest,mapping).get(row['generated_path'])


# The Windows account path is assembled from fragments at run time, so the source never holds
# a literal that the repository hygiene guard refuses.
@pytest.mark.parametrize('literal',[
    '/private/runtime/credential.txt', 'C:' + '\\' + 'Users' + '\\' + 'account\\key.txt',
    'token=abc123', 'password: hunter2', 'Authorization Bearer secret-value',
    'https://example.invalid/api?key=123', 'sk-abcdefghijklmnopqrstuv',
])
def test_path_and_credential_like_literals_are_withheld(literal):
    assert worker._literal_diagnostic(literal)=='[message withheld]'


def test_literal_size_controls_and_markup():
    value=worker._literal_diagnostic('safe\x00\n<script>bad</script>')
    assert value=='[message withheld]'  # slash-bearing markup is withheld too
    value=worker._literal_diagnostic('safe\x00\n<b>plain</b>')
    assert value=='[message withheld]'
    value=worker._literal_diagnostic('<b>safe\x00\n'+('x'*5000))
    assert len(value)<=512 and all(c.isprintable() for c in value)
    assert value.startswith('<b>safe')  # The client renders text, never HTML.
    assert worker._literal_diagnostic('pressure must be > 0 & < 10')=='pressure must be > 0 & < 10'
    assert worker._literal_diagnostic('safe\u202etext')=='safe text'


def _raise(error):
    raise error


def test_exception_objects_are_never_formatted_or_used_as_messages():
    class Trap:
        def __str__(self):pytest.fail('Exception argument was stringified')
        def __repr__(self):pytest.fail('Exception argument was represented')
    class Error(ValueError):
        def __str__(self):pytest.fail('Exception was stringified')
    for error,expected in ((Error(Trap()),'Exception'),(ValueError(Trap()),'ValueError')):
        try:_raise(error)
        except Exception as caught:
            assert worker.runtime_diagnostic(caught,{}, {})==expected


@pytest.mark.parametrize('registered',[False,True])
def test_dynamic_args_and_forged_code_identity_do_not_leak(registered):
    try:_raise(RuntimeError('private runtime secret /host/path'))
    except RuntimeError as error:
        code=_raise.__code__;line=code.co_firstlineno+1
        row=dict(source_path='sources/'+'a'*64+'.py',instance_id='1',definition_version_id='2',
            generated_line_start=line,generated_line_end=line)
        catalog={'generated/impl/a.py':(row,[])}
        codes={id(code):(code if registered else test_literal_size_controls_and_markup.__code__,'generated/impl/a.py')}
        message=worker.runtime_diagnostic(error,catalog,codes)
        assert 'private' not in message and 'secret' not in message and '/host' not in message
        assert ('sources/' in message)==registered


def test_dynamic_authored_message_is_not_treated_as_literal(tmp_path):
    manifest,mapping,row=mapped(tmp_path,b"raise RuntimeError('value '+str(inputs['x']))\n")
    assert worker.diagnostic_catalog(tmp_path,manifest,mapping)[row['generated_path']][1]==[]


def test_optional_ast_recursion_failure_omits_diagnostic(tmp_path,monkeypatch):
    manifest,mapping,row=mapped(tmp_path)
    def exhausted(_text):raise RecursionError('bounded optional parser failure')
    monkeypatch.setattr(worker.ast,'parse',exhausted)
    assert worker.diagnostic_catalog(tmp_path,manifest,mapping)=={}


def _condition_error():
    assert _raise(AssertionError('private dynamic detail')), 'wrong assertion message'


def test_error_evaluating_assert_condition_does_not_claim_its_literal():
    try:_condition_error()
    except AssertionError as error:
        code=_condition_error.__code__;line=code.co_firstlineno+1
        row=dict(source_path='sources/'+'a'*64+'.py',instance_id='1',definition_version_id='2',
            generated_line_start=line,generated_line_end=line)
        catalog={'generated/impl/a.py':(row,[(1,1,'AssertionError','wrong assertion message')])}
        message=worker.runtime_diagnostic(error,catalog,{id(code):(code,'generated/impl/a.py')})
        assert message.startswith('AssertionError [source ')
        assert 'wrong assertion' not in message and 'private dynamic' not in message
