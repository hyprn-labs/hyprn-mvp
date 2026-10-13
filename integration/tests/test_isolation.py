"""Current real containment attestation, independently of numerical acceptance."""
import copy
import pytest

@pytest.mark.quick
def test_missing_failed_and_changed_fingerprint_cannot_authorize_candidate(tmp_path):
    import json
    from hyprn_mvp_integration.launcher import require_attestation
    path=tmp_path/'attestation.json';current=dict(image='sha256:'+'a'*64,launcher='b'*64,policy='c'*64,runtime='new-runtime')
    with pytest.raises(RuntimeError):require_attestation(path,current)
    path.write_text(json.dumps(dict(passed=False,fingerprint=current)))
    with pytest.raises(RuntimeError):require_attestation(path,current)
    path.write_text(json.dumps(dict(passed=True,fingerprint=current)))
    require_attestation(path,current)
    for key in current:
        changed=copy.deepcopy(current);changed[key]='changed'
        with pytest.raises(RuntimeError):require_attestation(path,changed)

@pytest.mark.isolation
@pytest.mark.integration
def test_real_network_secret_home_socket_write_resource_and_concurrency_canaries():
    from hyprn_mvp_integration.launcher import attest
    from execution_fixtures import scoped_native_runtime
    # The canaries run against the worker built in this test's own scope, never an installation's.
    evidence=attest(root=scoped_native_runtime().root)
    assert evidence['passed'] and evidence['candidate_executions']==0
    assert set(evidence['cases']) >= {'access','memory','wall','output','file_bound','pids','concurrent_0','concurrent_1'}
    assert evidence['cases']['memory']['state']['OOMKilled']
    assert evidence['cases']['wall']['reason']=='wall_limit'
    assert evidence['cases']['output']['reason']=='output_limit'
    assert all(evidence['cases'][name]['exit_code']==0 for name in ('access','file_bound','pids','concurrent_0','concurrent_1'))
    access=evidence['access_checks']
    assert all(access[k] for k in ('network_denied','secret_denied','home_denied','socket_denied','outside_write_denied','input_readonly','nonroot'))
