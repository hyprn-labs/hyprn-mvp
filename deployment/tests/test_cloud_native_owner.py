"""Native owner reads the actual isolated AiiDA profile, never an invented receipt."""

import live_fence
setUpModule, tearDownModule = live_fence.unittest_module_hooks('unit')

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


class HostPrerequisiteTests(unittest.TestCase):
    def module(self):
        sys.path.insert(0, str(ROOT / 'deployment'))
        import cloud_native
        return cloud_native

    def test_real_owner_commands_pass_without_listing_other_processes(self):
        native = self.module()
        native.host_prerequisites()

    def test_missing_owner_command_refuses_before_initialization_writes(self):
        native = self.module()
        actual = native.shutil.which
        for missing in ('bash', 'ps', 'tail', 'whoami'):
            with self.subTest(command=missing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with (patch.object(native.shutil, 'which',
                       side_effect=lambda name, **kwargs: None if name == missing else actual(name, **kwargs)),
                      patch.object(native, 'packaged_inventory') as inventory):
                    with self.assertRaisesRegex(RuntimeError, 'owner PATH: ' + missing):
                        native.initialize({'execution_root': str(root)}, root / 'configuration')
                    inventory.assert_not_called()
                self.assertEqual(list(root.iterdir()), [])

    def test_unusable_scheduler_command_refuses_attested_admission(self):
        native = self.module()
        actual = native.subprocess.run
        def run(argv, **kwargs):
            if Path(argv[0]).name == 'ps':
                self.assertEqual(argv[1:], ['-o', 'pid=', '-p', str(os.getpid())])
                return SimpleNamespace(returncode=1, stdout='', stderr='unsupported')
            return actual(argv, **kwargs)
        with patch.object(native.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'scheduler preflight: ps'):
                native.inspect({}, None, attested=True)

    def test_missing_transport_home_refuses_before_runtime_admission(self):
        native = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'missing-home'
            with self.assertRaisesRegex(ValueError, 'Execution home is missing'):
                native.host_prerequisites({'host_home': str(home)})
            self.assertFalse(home.exists())

    def test_initialized_home_supports_real_local_transport(self):
        native = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / 'home'
            configuration = {'host_home': str(home)}
            native.execution_home(configuration, create=True)
            retained = home / 'retained'
            retained.write_text('keep')
            native.execution_home(configuration, create=True)
            self.assertEqual(retained.read_text(), 'keep')
            self.assertEqual(home.stat().st_mode & 0o777, 0o700)
            with patch.dict(os.environ, {'HOME': str(home)}):
                native.host_prerequisites(configuration)
                from aiida.transports.plugins.local import LocalTransport
                with LocalTransport() as transport:
                    import pwd
                    self.assertEqual(transport.whoami(), pwd.getpwuid(os.getuid()).pw_name)

    def test_unsafe_existing_home_is_never_repaired_implicitly(self):
        native = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / 'home'
            home.mkdir(mode=0o755)
            home.chmod(0o755)
            with self.assertRaisesRegex(ValueError, 'Execution home must be private'):
                native.execution_home({'host_home': str(home)}, create=True)
            home.rmdir()
            home.symlink_to(Path(tmp).resolve(), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Unsafe execution home'):
                native.execution_home({'host_home': str(home)}, create=True)


class HostRebindTests(unittest.TestCase):
    def scenario(self, directory):
        sys.path.insert(0, str(ROOT / 'deployment'))
        sys.path.insert(0, str(ROOT / 'integration/src'))
        sys.path.insert(0, str(ROOT / 'application/src'))
        import cloud_lifecycle
        import cloud_release
        root = Path(directory).resolve()
        private = root / 'native-private'
        private.mkdir(mode=0o700)
        old = dict(schema='hyprn-cloud-execution/v1', edition='cloud', installation_id='retained',
                   store_id='retained-store', execution_root=str(root / 'execution'),
                   host_home=str(root / 'home'), docker={'endpoint':'unix://'+str(root / 'socket')},
                   profile='hyprn-mvp-cloud-retained', source=str(root / 'old/source'),
                   native_root=str(root / 'old/native'), python=str(root / 'old/native/bin/python'))
        old.update(config_sha256=cloud_release.digest(old), release_sha256='a'*64)
        new = dict(old, source=str(root / 'new/source'), native_root=str(root / 'new/native'),
                   python=str(root / 'new/native/bin/python'), release_sha256='b'*64)
        new['config_sha256'] = cloud_release.digest({k:v for k,v in new.items()
                                                   if k not in ('release_sha256','config_sha256')})
        owner = {key:old[key] for key in ('installation_id','store_id','execution_root','profile',
                                        'release_sha256','config_sha256')}
        owner.update(schema='hyprn-native-owner/v1',profile_uuid='p',repository_uuid='r',
                     computer_uuid='c',code_uuid='n')
        path = private / 'execution.json'
        path.write_text(json.dumps(old))
        path.chmod(0o600)
        (root / 'native-owner.json').write_text(json.dumps(owner))
        lifecycle=cloud_lifecycle.Lifecycle.__new__(cloud_lifecycle.Lifecycle)
        lifecycle.root=root
        lifecycle.preview={'execution':{'user':os.getuid()}}
        lifecycle.native_projection=lambda:new
        calls=[]
        lifecycle.native_quiescence=lambda:calls.append('quiescent')
        def native(operation,*arguments,configuration=None):
            calls.append(operation)
            if operation=='inspect':
                self.assertEqual(configuration,old)
                return owner
            self.assertEqual(operation,'rebind')
            self.assertEqual(json.loads(path.read_text()),new)
            request=json.loads(Path(arguments[0]).read_text())
            self.assertEqual(request['previous'],old)
            self.assertEqual(request['owner'],owner)
            return dict(owner,release_sha256=new['release_sha256'],config_sha256=new['config_sha256'])
        lifecycle.native=native
        return SimpleNamespace(module=cloud_lifecycle,host=lifecycle,old=old,new=new,owner=owner,
                               path=path,calls=calls)

    def test_host_binds_both_releases_before_preserving_owner_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=self.scenario(tmp)
            # Root ownership is covered by the real Linux control test; this
            # exercises host transition ordering with only native process I/O replaced.
            with patch.object(value.module,'control_record',side_effect=lambda p:json.loads(p.read_text())), \
                    patch.object(value.module.os,'chown') as chown:
                actual=value.host.rebind_native()
                chown.assert_called_once_with(value.path,os.getuid(),os.getuid())
            self.assertEqual(value.calls,['quiescent','inspect','rebind'])
            self.assertEqual(actual['repository_uuid'],value.owner['repository_uuid'])
            self.assertEqual(json.loads((value.host.root/'native-owner.json').read_text()),actual)

    def test_unbound_old_projection_never_executes_its_selected_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=self.scenario(tmp)
            value.old['python']=str(value.host.root/'old/native/bin/foreign-python')
            value.path.write_text(json.dumps(value.old))
            with patch.object(value.module,'control_record',return_value=value.owner):
                with self.assertRaises(value.module.Refused) as refused:
                    value.host.rebind_native()
            self.assertEqual(refused.exception.reason,'previous_native_configuration_unbound')
            self.assertEqual(value.calls,[])

    def test_release_change_cannot_change_docker_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=self.scenario(tmp)
            value.new['docker']={'endpoint':'unix://'+str(value.host.root/'other-socket')}
            with patch.object(value.module,'control_record',return_value=value.owner):
                with self.assertRaises(value.module.Refused) as refused:
                    value.host.rebind_native()
            self.assertEqual(refused.exception.reason,'native_rebind_authority_changed')
            self.assertEqual(value.calls,[])

    def test_interrupted_native_transition_cannot_replace_protected_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=self.scenario(tmp)
            original=value.host.native
            def fail(operation,*args,**kwargs):
                if operation=='rebind':raise value.module.Refused('native_owner_operation_refused',6)
                return original(operation,*args,**kwargs)
            value.host.native=fail
            with patch.object(value.module,'control_record',return_value=value.owner), \
                    patch.object(value.module.os,'chown'):
                with self.assertRaises(value.module.Refused):value.host.rebind_native()
            self.assertEqual(json.loads(value.path.read_text()),value.new)
            self.assertEqual(json.loads((value.host.root/'native-owner.json').read_text()),value.owner)


class NativeOwnerTests(unittest.TestCase):
    def test_paused_pre_upload_process_can_be_killed_without_execution(self):
        self.run_native('''
(root/'launch-worker').write_text(cloud_native.wrapper(configuration,config))
(root/'launch-worker').chmod(0o700)
native_environment.initialize(root,configuration)
import asyncio
from aiida import orm
from aiida.calculations.arithmetic.add import ArithmeticAddCalculation
from aiida.manage import get_manager
from plumpy import process_states
from aiida.engine.utils import loop_scope
from unittest.mock import patch
runner=get_manager().create_runner(communicator=None)
with loop_scope(runner.loop):
    process=ArithmeticAddCalculation(runner=runner,inputs={
        'x':orm.Int(1),'y':orm.Int(2),'code':orm.load_code('hyprn-mvp-scalar')})
    process.transition_to(process_states.Running(process,process.run))
    process.transition_to(process_states.Waiting(process,None,'pre-upload fixture'))
    process.pause('isolated recovery fixture')
    runner.persister.save_checkpoint(process)
    node=process.node
    identity=node.uuid
    assert node.paused and node.get_job_id() is None
    before=orm.QueryBuilder().append(orm.CalcJobNode).count()
    async def interrupted():
        loop=asyncio.get_running_loop()
        result=loop.create_future()
        loop.call_soon(lambda:result.set_result(process.kill(msg_text='signal-context regression')))
        return await result
    assert runner.run_until_complete(interrupted()) is False
    assert node.process_state.value=='waiting'
    process.close()
    from native_recovery import terminate_paused, checkpoint_identity
    expected=dict(uuid=identity,process_type=node.process_type,
                  checkpoint_sha256=checkpoint_identity(node))
    for invalid in (dict(expected,uuid='wrong'),dict(expected,checkpoint_sha256='wrong')):
        try:terminate_paused(node,invalid)
        except ValueError:pass
        else:raise AssertionError('Unverified checkpoint accepted')
    with patch.object(node,'get_job_id',return_value='already-submitted'):
        try:terminate_paused(node,expected)
        except ValueError:pass
        else:raise AssertionError('Submitted job accepted for pre-upload recovery')
    with patch.object(ArithmeticAddCalculation,'run',
                      side_effect=AssertionError('Model must not run')):
        result=terminate_paused(node,expected)
    assert result==dict(uuid=identity,state='killed',sealed=True)
    node=orm.load_node(identity)
    assert node.process_state.value=='killed' and node.is_sealed
    assert node.get_job_id() is None
    assert not node.base.links.get_outgoing().all_link_labels()
    assert orm.QueryBuilder().append(orm.CalcJobNode).count()==before
runner.close()
''')

    def run_native(self, body):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            execution = root / 'execution'
            execution.mkdir(mode=0o700)
            private = root / 'private'
            private.mkdir(mode=0o700)
            config = private / 'execution.json'
            value = {'schema': 'hyprn-cloud-execution/v1', 'edition': 'cloud',
                     'installation_id': 'isolated-native', 'store_id': 'isolated-native-store',
                     'execution_root': str(execution), 'host_home': str(root / 'home'),
                     'docker': {'endpoint': 'unix://' + str(root / 'docker.sock')},
                     'profile': 'hyprn-mvp-cloud-isolated-native', 'source': str(ROOT),
                     'native_root': str(ROOT.parent / 'native'),
                     'python': str(ROOT.parent / 'native/bin/python'),
                     'release_sha256': 'a' * 64, 'config_sha256': 'b' * 64}
            config.write_text(json.dumps(value))
            config.chmod(0o600)
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith(('HYPRN_MVP_', 'AIIDA_', 'PYTHON'))}
            environment['HYPRN_MVP_CLOUD_EXECUTION_CONFIG'] = str(config)
            environment['AIIDA_PATH'] = str(execution / 'aiida')
            setup = ('import sys,json;from pathlib import Path;'
                     'source=Path(sys.argv[1]);config=Path(sys.argv[2]);'
                     'sys.path[:0]=[str(source/p) for p in ("deployment","application/src","integration/src")];'
                     'import cloud_native,native_environment;'
                     'configuration=json.loads(config.read_text());root=Path(configuration["execution_root"]);')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', setup + body, str(ROOT), str(config)],
                                    env=environment, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_nonempty_store_refuses_before_initialization(self):
        self.run_native('(root/"authoring-record").write_text("retained");\n'
                        'try: cloud_native.initialize(configuration,config)\n'
                        'except ValueError as error: assert "nonempty" in str(error)\n'
                        'else: raise AssertionError("Nonempty store accepted")\n'
                        'assert (root/"authoring-record").read_text()=="retained"\n'
                        'assert not (root/"aiida").exists()')

    def test_observed_uuid_is_real_and_changed_profile_pin_is_refused(self):
        self.run_native('(root/"launch-worker").write_text(cloud_native.wrapper(configuration,config));'
                        '(root/"launch-worker").chmod(0o700);'
                        'native_environment.initialize(root,configuration);'
                        'receipt=cloud_native.inspect(configuration,config);'
                        'from aiida.manage import get_manager;'
                        'assert receipt["repository_uuid"]==get_manager().get_profile_storage().get_repository().uuid;'
                        'assert receipt["profile_uuid"]!=receipt["repository_uuid"];'
                        'pin=json.loads((root/"profile-identity.json").read_text());'
                        'pin["profile_uuid"]="00000000-0000-4000-8000-000000000000";'
                        '(root/"profile-identity.json").write_text(json.dumps(pin));\n'
                        'try: cloud_native.inspect(configuration,config)\n'
                        'except RuntimeError as error: assert "identity changed" in str(error)\n'
                        'else: raise AssertionError("Changed profile pin accepted")')

    def test_existing_native_profile_cannot_be_reinitialized(self):
        self.run_native('(root/"launch-worker").write_text(cloud_native.wrapper(configuration,config));'
                        '(root/"launch-worker").chmod(0o700);'
                        'native_environment.initialize(root,configuration);'
                        'before=(root/"profile-identity.json").read_bytes();\n'
                        'try: native_environment.initialize(root,configuration)\n'
                        'except ValueError as error: assert "existing profile" in str(error)\n'
                        'else: raise AssertionError("Existing profile overwritten")\n'
                        'assert (root/"profile-identity.json").read_bytes()==before')

    def rebind_case(self, body):
        self.run_native('''
from unittest.mock import patch
from aiida import orm
from hyprn_mvp_integration import launcher
import hashlib
previous=dict(configuration,release_sha256='c'*64)
projection={k:v for k,v in previous.items() if k not in ('release_sha256','config_sha256')}
previous['config_sha256']=hashlib.sha256(cloud_native.canonical(projection)).hexdigest()
(root/'launch-worker').write_text(cloud_native.wrapper(previous,config))
(root/'launch-worker').chmod(0o700)
native_environment.initialize(root,configuration)
saved=orm.Dict(dict={'value':12.5,'unit':'m','source':'synthetic-retained-record'}).store()
saved_uuid=saved.uuid
pin=(root/'profile-identity.json').read_bytes()
owner=dict(json.loads(pin),schema='hyprn-native-owner/v1',installation_id=previous['installation_id'],
    store_id=previous['store_id'],execution_root=str(root),release_sha256=previous['release_sha256'],
    config_sha256=previous['config_sha256'])
selected=b'{}'
(root/'selected.json').write_bytes(selected)
old_runtime=dict(owner=launcher.OWNER,root=str(root),selected_sha256=hashlib.sha256(selected).hexdigest(),
    execution_configuration_sha256=hashlib.sha256(cloud_native.canonical(previous)).hexdigest())
(root/'runtime.json').write_bytes(cloud_native.canonical(old_runtime))
new_runtime=dict(old_runtime,execution_configuration_sha256=launcher.execution_configuration_sha256())
(root/'evidence').mkdir()
old_evidence=cloud_native.canonical({'passed':True,'fingerprint':{'runtime':old_runtime}})
(root/'evidence/containment.json').write_bytes(old_evidence)
launcher.require_attestation(current={'runtime':old_runtime})
with patch.object(cloud_native,'rebind_request',return_value=(previous,owner)), \
     patch.object(cloud_native,'packaged_inventory',return_value=(new_runtime,selected,[])), \
     patch.object(launcher,'fingerprint',side_effect=lambda **kwargs: {'runtime':launcher.identity()}):
''' + '\n'.join('    '+line for line in body.splitlines()))

    def test_rebind_preserves_real_native_records_and_requires_new_attestation(self):
        self.rebind_case('''computer=orm.load_computer(owner['computer_uuid'])
computer.set_minimum_job_poll_interval(10)
receipt=cloud_native.rebind(configuration,config,'host-authorized')
assert orm.load_computer(owner['computer_uuid']).get_minimum_job_poll_interval()==0.2
poll=json.loads((root/'evidence/execution-polling.json').read_bytes())
assert poll['previous_seconds']==10 and poll['current_seconds']==0.2
assert receipt['repository_uuid']==owner['repository_uuid']
assert receipt['profile_uuid']==owner['profile_uuid']
assert receipt['computer_uuid']==owner['computer_uuid']
assert receipt['code_uuid']==owner['code_uuid']
assert receipt['release_sha256']==configuration['release_sha256']
assert (root/'profile-identity.json').read_bytes()==pin
assert orm.load_node(saved_uuid).get_dict()=={'value':12.5,'unit':'m','source':'synthetic-retained-record'}
assert (root/'evidence/containment.json').read_bytes()==old_evidence
try: launcher.require_attestation()
except RuntimeError: pass
else: raise AssertionError('Old attestation admitted replaced runtime')
assert not (root/'rebind-pending.json').exists()''')

    def test_rebind_preserves_a_faster_existing_scheduler_interval(self):
        self.rebind_case('''computer=orm.load_computer(owner['computer_uuid'])
computer.set_minimum_job_poll_interval(0.1)
cloud_native.rebind(configuration,config,'host-authorized')
assert orm.load_computer(owner['computer_uuid']).get_minimum_job_poll_interval()==0.1
poll=json.loads((root/'evidence/execution-polling.json').read_bytes())
assert poll['previous_seconds']==poll['current_seconds']==0.1
assert orm.load_node(saved_uuid).get_dict()['value']==12.5''')

    def test_rebind_refuses_linked_polling_evidence_before_any_write(self):
        self.rebind_case('''before=(root/'runtime.json').read_bytes()
(root/'evidence').rename(root/'held-evidence')
(root/'evidence').symlink_to(root/'held-evidence',target_is_directory=True)
try: cloud_native.rebind(configuration,config,'host-authorized')
except ValueError as error: assert 'Unsafe retained inventory destination' in str(error)
else: raise AssertionError('Linked polling evidence accepted')
assert (root/'runtime.json').read_bytes()==before
assert not (root/'rebind-pending.json').exists()
assert not (root/'held-evidence/execution-polling.json').exists()''')

    def test_rebind_refuses_unfinished_native_process_before_metadata_write(self):
        self.rebind_case('''node=orm.CalcJobNode().store()
before=(root/'runtime.json').read_bytes()
try: cloud_native.rebind(configuration,config,'host-authorized')
except ValueError as error: assert 'processes require reconciliation' in str(error)
else: raise AssertionError('Unfinished native process accepted')
assert (root/'runtime.json').read_bytes()==before
assert not (root/'rebind-pending.json').exists()''')

    def test_interrupted_rebind_refuses_ordinary_inspection(self):
        self.rebind_case('''with patch.object(cloud_native,'replace_record',side_effect=OSError('interrupted write')):
    try: cloud_native.rebind(configuration,config,'host-authorized')
    except OSError: pass
    else: raise AssertionError('Interrupted write accepted')
assert (root/'rebind-pending.json').exists()
try: cloud_native.inspect(configuration,config)
except ValueError as error: assert 'reconciliation' in str(error)
else: raise AssertionError('Partial replacement accepted')
assert orm.load_node(saved_uuid).get_dict()['value']==12.5
assert (root/'profile-identity.json').read_bytes()==pin''')

    def test_rebind_refuses_changed_actual_identity_before_metadata_write(self):
        self.rebind_case('''owner['repository_uuid']='00000000-0000-4000-8000-000000000000'
before=(root/'runtime.json').read_bytes()
try: cloud_native.rebind(configuration,config,'host-authorized')
except ValueError as error: assert 'protected previous receipt' in str(error)
else: raise AssertionError('Foreign native identity accepted')
assert (root/'runtime.json').read_bytes()==before
assert not (root/'rebind-pending.json').exists()''')

    def test_native_rebind_requires_root_owned_host_authorization(self):
        self.run_native('''
request=config.parent/'rebind.json'
request.write_text('{}')
request.chmod(0o666)
try: cloud_native.rebind_request(request,configuration)
except ValueError as error: assert 'host authority' in str(error)
else: raise AssertionError('Unprivileged authorization accepted')
''')
