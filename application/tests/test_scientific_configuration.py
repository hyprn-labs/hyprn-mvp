"""App/private digest separation; data-only and immutable by construction."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'application/src'))
sys.path.insert(0, str(ROOT / 'contracts/tests'))
from test_reuse_contract import candidate, revision, validate
from hyprn_mvp_app.store import digest, DomainError


def project(value):
    from hyprn_mvp_app.scientific_configuration import project_scientific_configuration
    return project_scientific_configuration(value)


def saved():
    value = revision()
    value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
    return value


def test_projection_preserves_literals_and_omits_application_authority():
    value = saved(); before = copy.deepcopy(value)
    result = project(value)
    validate('ModelingConfigurationRevision2', result)
    assert set(result) == set(value) - {'context_source', 'derivation'}
    assert result['inputs'] == [{k: v for k, v in value['inputs'][0].items() if k != 'result_binding'}]
    assert result['inputs'][0]['value'] == 150 and result['inputs'][0]['units'] == 'cm'
    assert result['required_capabilities'] == ['flat_explicit_scalar']
    assert result['digest'] == digest({k: v for k, v in result.items() if k != 'digest'})
    assert result['digest'] != value['digest']
    assert value == before
    result['context_snapshot']['notes'].append('isolated')
    assert value == before


def test_projection_digest_is_deterministic_and_separate_from_metadata():
    value = saved(); first = project(value)
    value['inputs'][0]['result_binding']['labels']['run_name'] = 'Retained label changed'
    value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
    assert project(value) == first
    assert project(dict(reversed(list(value.items())))) == first
    value['inputs'][0]['value'] = 151
    value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
    assert project(value)['digest'] != first['digest']


def test_candidate_has_no_immutable_fields_or_digest():
    result = project(candidate())
    validate('ModelingConfiguration2', result)
    assert 'digest' not in result
    from hyprn_mvp_app.scientific_configuration import scientific_configuration_digest
    assert scientific_configuration_digest(candidate()) == digest(result)
    assert scientific_configuration_digest(saved()) == project(saved())['digest']


@pytest.mark.parametrize('mutation', ['unknown', 'native', 'bad_digest', 'bool', 'nan', 'duplicate', 'version'])
def test_invalid_public_configuration_fails_before_projection(mutation):
    value = saved()
    if mutation == 'unknown': value['unexpected'] = True
    elif mutation == 'native': value['inputs'][0]['result_binding']['process_uuid'] = value['study_id']
    elif mutation == 'bad_digest': value['name'] = 'tampered'
    elif mutation == 'bool': value['inputs'][0]['value'] = True
    elif mutation == 'nan': value['inputs'][0]['value'] = float('nan')
    elif mutation == 'duplicate': value['inputs'].append(copy.deepcopy(value['inputs'][0]))
    elif mutation == 'version': value['schema_version'] = '99'
    with pytest.raises((ValueError, DomainError)):
        project(value)


def test_legacy_literal_record_is_byte_identical():
    value = project(saved()); value['schema_version'] = '1'
    value['digest'] = digest({k: v for k, v in value.items() if k != 'digest'})
    assert project(value) == value
    assert project(value) is not value


def test_configuration3_projection_preserves_exact_context_and_evidence():
    from test_assumptions_evidence_contracts import sample,D
    value=saved();value['schema_version']='3'
    value['assumptions']=[sample(D['ConfigurationAssumption'])]
    record=sample(D['EvidenceSnapshot3'])
    value['evidence_snapshots']=[record]
    value['general_context_evidence_version_ids']=[record['evidence_version_id']]
    value['required_capabilities'].append('configuration_assumptions/1')
    value['digest']=digest({k:v for k,v in value.items() if k!='digest'})
    before=copy.deepcopy(value);result=project(value)
    validate('ModelingConfigurationRevision3',result)
    assert result['schema_version']=='3'
    assert result['context_snapshot']==value['context_snapshot']
    assert result['evidence_snapshots']==value['evidence_snapshots']
    assert set(result)==set(value)-{'assumptions','general_context_evidence_version_ids','context_source','derivation'}
    assert result['required_capabilities']==['flat_explicit_scalar']
    value['assumptions'][0]['statement']='Explicitly different'
    value['digest']=digest({k:v for k,v in value.items() if k!='digest'})
    assert value['digest']!=before['digest'] and project(value)==result
    value['evidence_snapshots'][0]['title']='Different retained title'
    value['digest']=digest({k:v for k,v in value.items() if k!='digest'})
    assert project(value)['digest']!=result['digest']
    assert result['evidence_snapshots']==before['evidence_snapshots']


@pytest.mark.parametrize('immutable',[False,True])
@pytest.mark.parametrize('pin',[False,True])
@pytest.mark.parametrize('number',[0,-0.0,1.5,1e-9,9007199254740991])
def test_configuration4_is_exact_private3_projection(immutable,pin,number):
    from test_assumptions_evidence_contracts import sample,D
    from hyprn_mvp_app.store import canonical
    old=saved() if immutable else candidate()
    old.update(schema_version='3',assumptions=[],general_context_evidence_version_ids=[])
    old['inputs'][0]['value']=number
    old['required_capabilities'].append('configuration_assumptions/1')
    if immutable:old['digest']=digest({k:v for k,v in old.items() if k!='digest'})
    new=copy.deepcopy(old);new.update(schema_version='4',approach_binding=sample(D['ApproachBinding1']) if pin else None)
    if immutable:new['digest']=digest({k:v for k,v in new.items() if k!='digest'})
    before=copy.deepcopy(new)
    assert canonical(project(new))==canonical(project(old))
    assert new==before

@pytest.mark.parametrize('bad',['missing','extra','digest','bool','nan'])
def test_configuration4_validation_precedes_projection(bad):
    value=candidate();value.update(schema_version='4',assumptions=[],general_context_evidence_version_ids=[],approach_binding=None)
    if bad=='missing':value.pop('approach_binding')
    elif bad=='extra':value['approach_closure']={}
    elif bad=='digest':
        from test_assumptions_evidence_contracts import sample,D
        value['approach_binding']=sample(D['ApproachBinding1']);value['approach_binding']['closure_digest']='invalid'
    else:value['inputs'][0]['value']=True if bad=='bool' else float('nan')
    with pytest.raises((ValueError,DomainError)):project(value)
