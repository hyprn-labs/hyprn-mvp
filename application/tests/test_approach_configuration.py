"""Approach-bound configuration requests are refused for new writes; retained approach-bound
frozen configurations stay readable exactly as saved. No native run."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from test_assumption_configuration import env, config, body, counts, evidence, sample, D  # noqa: F401
from hyprn_mvp_app.approach import Approaches
from hyprn_mvp_app.store import DomainError, digest, uid

def pin(config, *, linked=True, extra_evidence=False, descriptive=False):
    e,c,r,m,record=config
    service=Approaches(e['store'],e['coord']);content=sample(D['ApproachContent1'])
    binding=dict(binding_id=uid(),model_id=m['model_id'],model_revision_id=m['model_revision_id'])
    step=sample(D['ApproachStep1'])
    if linked:step.update(implementation_state='linked',remaining_work='',implementation_refs=[dict(kind='model',binding_id=binding['binding_id'])])
    content['model_bindings']=[binding] if linked else [];content['steps']=[step]
    if extra_evidence:
        extra=evidence(e,title='Approach-only basis')
        step['evidence_links']=[dict(evidence_version_id=extra['evidence_version_id'],relation='context')]
    if descriptive:content.update(schema_version='2',original_question=None,elaboration=None,limit_items=[])
    request=dict(schema_version='2' if descriptive else '1',expected_revision=None,content=content)
    p=service.preview(e['actor'],e['sid'],request)
    d=service.save_draft(e['actor'],e['sid'],dict(request,command_id=uid(),expected_preview_digest=p['preview_digest']))
    request['expected_revision']=d['revision'];p=service.preview(e['actor'],e['sid'],request)
    saved=service.save_version(e['actor'],e['sid'],dict(schema_version='1',command_id=uid(),expected_revision=d['revision'],expected_preview_digest=p['preview_digest']))['saved']
    r.update(schema_version='4',approach_selection=dict(approach_version_id=saved['version']['approach_version_id']))
    return saved,None,service


@pytest.mark.parametrize('selection', ['pinned', 'none'])
def test_request4_is_refused_for_new_writes_without_allocation_or_modeling_call(config, selection):
    """A configuration request bound (or bindable) to a modeling approach is no longer a write
    format: preview and save answer unsupported_record_version and allocate nothing."""
    e, c, r, m, _ = config
    if selection == 'pinned':
        pin(config)
    else:
        r.update(schema_version='4', approach_selection=None)
    e['transport'].calls.clear()
    stale = {'candidate_digest': '0' * 64}
    for action in ('preview', 'commit'):
        with pytest.raises(DomainError) as error:
            if action == 'preview':
                c.preview(e['actor'], e['sid'], r)
            else:
                c.commit(e['actor'], e['sid'], body(config, stale))
        assert (error.value.code, error.value.status) == ('unsupported_record_version', 422)
    client = e['client']
    path = '/api/1/studies/' + e['sid'] + '/configurations'
    for url, payload in ((path + '/preview', r), (path, body(config, stale))):
        response = client.post(url, json=payload)
        assert response.status_code == 422, response.text
        assert response.json()['error']['code'] == 'unsupported_record_version'
    assert counts(e) == (0, 0, 0)
    calls = [called for _, called, _ in e['transport'].calls]
    assert not any(called.endswith('/configuration-compatibility') for called in calls)


def retained_frozen7():
    """An approach-bound frozen configuration 7 on a Model4 revision, as saved before
    approach-bound writes were retired: the captured golden configuration and model, closed
    over a descriptive approach version (the captured closure carries the retired cases
    field, so it is rebuilt with the production closure builder and re-signed)."""
    from test_approach_closure import link, resolution, signed
    from hyprn_mvp_app.approach_closure import build_closure

    golden = Path(__file__).resolve().parent / 'fixtures/identity_golden.json'
    corpus = json.loads(golden.read_text())
    frozen = next(
        deepcopy(b['inputs']['frozen'])
        for b in corpus['bundles']
        if b['inputs']['frozen'].get('schema_version') == '7'
        and b['inputs']['frozen']['model_snapshot']['schema_version'] == '4'
    )
    c = frozen['configuration']
    m = frozen['model_snapshot']
    v = sample(D['ApproachVersion1'])
    v['study_id'] = c['study_id']
    link(v, m)
    v['schema_version'] = '2'
    v['content'].update(
        schema_version='2',
        original_question=None,
        elaboration=None,
        limit_items=[
            dict(limit_id=uid(), statement='A bounded descriptive limit', evidence_links=[])
        ],
    )
    signed(v)
    closure = build_closure(v, resolution(models=[m]), study_id=c['study_id'])
    frozen['approach_closure'] = closure
    c['approach_binding'] = dict(
        approach_id=v['approach_id'],
        approach_version_id=v['approach_version_id'],
        approach_digest=v['digest'],
        closure_digest=closure['digest'],
    )
    signed(c)
    return frozen


def test_page_validation_reuses_identical_subrecords_and_rejects_changed_bytes(monkeypatch):
    from hyprn_mvp_app.history import configuration_name_projection, _page_configuration_validator
    from hyprn_mvp_app.contracts import JsonValidator

    frozen = retained_frozen7()
    configuration = frozen['configuration']
    assert frozen['approach_closure'] is not None
    assert configuration['approach_binding'] is not None
    model = frozen['model_snapshot']
    sid = configuration['study_id']
    revision = configuration['configuration_revision_id']
    raw = json.dumps(frozen)
    expected = configuration_name_projection(raw, sid, revision)
    assert expected == configuration['name']
    calls = []
    reference = JsonValidator.VALIDATORS['$ref']

    def counted(*args):
        calls.append(args[1])
        yield from reference(*args)

    monkeypatch.setitem(JsonValidator.VALIDATORS, '$ref', counted)
    check = _page_configuration_validator()
    assert configuration_name_projection(raw, sid, revision, check=check) == expected
    shared_model_ref = '#/$defs/ModelRevision' + model['schema_version']
    first = calls.count(shared_model_ref)
    changed = deepcopy(frozen)
    renamed = changed['configuration']
    renamed['name'] = 'Different explicit inputs'
    renamed['digest'] = digest({k: v for k, v in renamed.items() if k != 'digest'})
    calls.clear()
    projected = configuration_name_projection(json.dumps(changed), sid, revision, check=check)
    assert projected == 'Different explicit inputs'
    # A new configuration still checks its shared saved subrecords once.
    assert calls.count(shared_model_ref) == 0 < first
    faults = ('extra', 'schema', 'model', 'source', 'closure', 'pin', 'digest', 'numeric_type')
    for fault in faults:
        damaged = deepcopy(frozen)
        version = damaged['approach_closure']['approach_versions'][0]
        if fault == 'extra':
            damaged['model_snapshot']['unexpected'] = True
        elif fault == 'schema':
            damaged['schema_version'] = '8'
        elif fault == 'model':
            damaged['model_snapshot']['name'] = 'Changed under the same ID'
        elif fault == 'source':
            damaged['model_snapshot']['source_files'].append(
                dict(path='model.py', bytes='eA==', sha256='0' * 64)
            )
        elif fault == 'closure':
            version['content']['question'] = 'Changed'
        elif fault == 'pin':
            damaged['configuration']['approach_binding']['approach_version_id'] = uid()
        elif fault == 'numeric_type':
            version['version_number'] = True
        else:
            damaged['configuration']['digest'] = 'f' * 64
        candidate = json.dumps(damaged)
        assert configuration_name_projection(candidate, sid, revision, check=check) is None
        assert configuration_name_projection(candidate, sid, revision) is None
    assert configuration_name_projection(raw, uid(), revision, check=check) is None
