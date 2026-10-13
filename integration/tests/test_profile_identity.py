"""Fresh stores retain exact identities instead of reusing historical UUIDs."""
import json
from types import SimpleNamespace
import pytest
from hyprn_mvp_integration import calculation, launcher


@pytest.mark.parametrize('change', ['none', 'profile', 'repository', 'store', 'missing_pin', 'default_profile',
                                    'computer', 'executable', 'workdir', 'hostname'])
def test_native_profile_repository_code_and_computer_are_bound_before_use(tmp_path, monkeypatch, change):
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    monkeypatch.setenv('AIIDA_PATH', str(tmp_path/'aiida'))
    pin=tmp_path/'profile-identity.json'
    if change != 'missing_pin':
        pin.write_text(json.dumps({'profile_uuid':'fresh-profile','repository_uuid':'fresh-repository',
                                   'code_uuid':'fresh-code','computer_uuid':'fresh-computer'}))
    profile=SimpleNamespace(uuid='changed' if change=='profile' else 'fresh-profile',
        storage_config={'filepath':str(tmp_path/('wrong-store' if change=='store' else 'aiida-store'))})
    config=SimpleNamespace(dirpath=str(tmp_path/'aiida/.aiida'),profile_names=[calculation.PROFILE],get_profile=lambda name:profile,
                           default_profile_name=calculation.PROFILE if change=='default_profile' else None)
    import aiida
    import aiida.manage
    import aiida.manage.configuration
    monkeypatch.setattr(aiida.manage.configuration,'get_config',lambda:config)
    monkeypatch.setattr(aiida,'load_profile',lambda name:None)
    repository=SimpleNamespace(uuid='changed' if change=='repository' else 'fresh-repository')
    manager=SimpleNamespace(get_profile_storage=lambda:SimpleNamespace(get_repository=lambda:repository))
    monkeypatch.setattr(aiida.manage,'get_manager',lambda:manager)
    # The pinned code must run the scope's own worker wrapper on the local computer it was pinned with.
    computer=SimpleNamespace(uuid='changed' if change=='computer' else 'fresh-computer',
        hostname='elsewhere' if change=='hostname' else 'localhost',
        get_workdir=lambda:str(tmp_path/('other-work' if change=='workdir' else 'aiida-work')/'{username}'))
    code=SimpleNamespace(computer=computer,filepath_executable=str(tmp_path/('other-worker' if change=='executable' else 'launch-worker')))
    loaded=[]
    monkeypatch.setattr(calculation.orm,'load_code',lambda uuid:loaded.append(uuid) or code)
    if change=='none':
        assert calculation.NativeExecution.from_environment().store_uuid=='fresh-repository'
        assert loaded==['fresh-code']
    else:
        with pytest.raises((RuntimeError,FileNotFoundError)):
            calculation.NativeExecution.from_environment()
