"""Bounded product lifecycle commands under the platform-owned deployment lock.

This is an operation adapter, not a deployment reconciler. It never provisions a
host, fetches secrets or resets data. The native owner attaches one fixed dispatcher.
"""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import selectors
import stat
import subprocess
import sys
import time
from uuid import UUID

import cloud_release

OPERATIONS = ('initialize', 'inspect', 'check', 'admission', 'drain', 'migrate', 'start', 'stop',
              'qualify', 'backup', 'restore')


class Refused(Exception):
    def __init__(self, reason, code=2):
        self.reason, self.code = reason, code


def binding(path, operation):
    value = cloud_release.read_json(path)
    required = {'schema', 'platform_root', 'workload', 'release', 'runtime', 'desired',
                'payload_inventory', 'control_root'}
    allowed = required | ({'migration_secret_file'} if operation in ('initialize', 'migrate') else set())
    if (not isinstance(value, dict) or not required <= set(value) <= allowed
            or value['schema'] != 'hyprn-product-binding/v1'):
        raise Refused('invalid_binding')
    for key in set(value) - {'schema'}:
        path = Path(value[key])
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise Refused('invalid_binding_path')
    return value


def private_root(path):
    path = Path(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise Refused('host_control_authority')
    return path


@contextmanager
def exclusive(root):
    # Root-owned same lock for every product operation. Platform still holds its
    # outer deployment/backup lock; the product does not emulate that journal.
    fd = os.open(root / 'product.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused('lifecycle_conflict', 4) from None
        yield
    finally:
        os.close(fd)


def control_record(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise Refused('host_control_authority')
    return cloud_release.read_json(path)


def write_record(path, value, *, mode=0o600):
    temporary = path.with_name('.' + path.name + '.new')
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), mode)
    try:
        os.fchmod(fd, mode)  # Shared nonsecret controls must survive a private host umask.
        with os.fdopen(fd, 'wb') as stream:
            stream.write(cloud_release.canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


class Lifecycle:
    def __init__(self, specification, timeout):
        self.binding, self.timeout = specification, timeout
        self.deadline = time.monotonic() + timeout
        self.contract, self.documents, self.preview = cloud_release.documents(
            specification['platform_root'], specification)
        self.release = self.documents['release']
        self.runtime = self.documents['runtime']
        self.root = private_root(specification['control_root'])
        app = self.preview['compose']['services']['app']
        mount = next(volume for volume in app['volumes']
                     if volume['target'] == str(Path(app['environment']['HYPRN_MVP_ADMISSION_FILE']).parent))
        if Path(mount['source']) != self.root or not mount.get('read_only'):
            raise Refused('host_control_mount_mismatch')
        self.identity = {'installation_id': self.runtime['installation_id'],
                         'release_sha256': self.contract.digest(self.release),
                         'config_sha256': self.contract.digest(self.preview)}

    def identity_check(self):
        actual = control_record(self.root / 'runtime-identity.json')
        if actual != self.identity:
            raise Refused('installation_identity_mismatch')

    def inspection_owner(self, active_binding=None):
        """Incoming probes can read only the exact protected active installation."""
        active = self
        if active_binding is not None:
            path = Path(active_binding)
            control_record(path)
            active = Lifecycle(binding(path, 'inspect'), self.timeout)
            stable = ('installation_id', 'project_id', 'project_number', 'disk_uuid', 'store_ids', 'mounts')
            if (active.root != self.root or any(active.runtime[key] != self.runtime[key] for key in stable)):
                raise Refused('inspection_installation_mismatch')
        active.identity_check()
        active.assert_stopped()
        owner = control_record(self.root / 'native-owner.json')
        incoming = self.native_projection()
        # Validate active descriptor data with the incoming reviewed loader. Do
        # not execute/import the active source or require its path to be ours.
        from hyprn_mvp_integration.installation import validate_cloud_execution
        raw = active.preview['execution']['configuration']
        projection = validate_cloud_execution(dict(raw,
            release_sha256=active.identity['release_sha256'], config_sha256=cloud_release.digest(raw)))
        if any(owner.get(key) != projection[key] for key in
               ('installation_id', 'store_id', 'execution_root', 'profile', 'release_sha256', 'config_sha256')):
            raise Refused('inspection_native_owner_mismatch')
        if any(incoming[key] != projection[key] for key in
               ('installation_id', 'store_id', 'execution_root', 'profile', 'host_home', 'docker')):
            raise Refused('inspection_native_authority_changed')
        return owner

    def inspect_schemas(self, owner):
        """Observe only after inspection_owner proves the active writers stopped."""
        from cloud_owner_schemas import MODELING_PROBE
        self.artifact_check()
        application = self.database('inspect')['application']
        model_root = Path(self.runtime['mounts']['modeling'])
        marker = cloud_release.read_json(model_root / 'initialized')
        expected = dict(schema='hyprn-modeling-owner/v1',
                        installation_id=self.runtime['installation_id'],
                        store_id=self.runtime['store_ids']['modeling'])
        if marker != expected or any(p.is_symlink() for p in (model_root / 'initialized', model_root, *model_root.parents)):
            raise Refused('modeling_owner_identity_mismatch')
        service = self.preview['compose']['services']['modeling']
        environment = {key: value for key, value in os.environ.items() if key in ('PATH', 'LANG', 'LC_ALL')}
        command = ['docker', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
                   '--cap-drop=ALL', '--security-opt=no-new-privileges:true', '--pids-limit=32',
                   '--memory=256m', '--cpus=1', '--user', str(service['user']),
                   '--mount', 'type=bind,src=' + str(model_root) + ',dst=/store,readonly',
                   '--entrypoint', 'bundle', service['image'], 'exec', 'ruby', '-e', MODELING_PROBE]
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=self.remaining())
        if result.returncode:
            raise Refused('modeling_schema_inspection_refused', 6)
        modeling = json.loads(result.stdout)
        configuration = self.native_projection()
        uid = self.preview['execution']['user']
        command = [configuration['python'], '-I', '-B',
                   str(Path(configuration['source']) / 'deployment/cloud_owner_schemas.py')]
        result = subprocess.run(command, input=json.dumps(owner), env=environment, user=uid, group=uid,
                                extra_groups=[], capture_output=True, text=True, timeout=self.remaining())
        if result.returncode:
            raise Refused('native_schema_inspection_refused', 6)
        execution = json.loads(result.stdout)
        observations = {'application': application, 'modeling': modeling, 'execution': execution}
        return {name: dict(schema='hyprn-owner-schema/v1', installation_id=self.runtime['installation_id'],
                           store_id=self.runtime['store_ids'][name], owner=name, observed=value)
                for name, value in observations.items()}

    def admission(self, *, surface=None, state='closed'):
        closed = {'schema': 'hyprn-admission/v1', **self.identity,
                  'browser': False, 'scientific': False, 'expires_at': int(time.time()) + 120}
        if state == 'open':
            self.identity_check()
            # Platform receipt must carry exact checked evidence. The product does
            # not convert missing native qualification into successful admission.
            raise Refused('host_qualification_receipt_required', 5)
        write_record(self.root / 'admission.json', closed, mode=0o644)

    def remaining(self):
        value = self.deadline - time.monotonic()
        if value <= 0:
            raise Refused('operation_timeout', 6)
        return value

    def require_native_owner(self):
        actual = self.native('inspect')
        pinned = control_record(self.root / 'native-owner.json')
        if actual != pinned:
            raise Refused('native_owner_identity_mismatch', 6)
        return actual

    def native_projection(self):
        configuration = dict(self.preview['execution']['configuration'],
                             release_sha256=self.identity['release_sha256'],
                             config_sha256=cloud_release.digest(self.preview['execution']['configuration']))
        # Read the reviewed loader through the currently verified source only.
        source = Path(configuration['source'])
        if source != Path(__file__).resolve().parents[1]:
            raise Refused('native_source_mismatch')
        sys.path[:0] = [str(source / name) for name in ('application/src', 'integration/src')]
        from hyprn_mvp_integration.installation import validate_cloud_execution
        return validate_cloud_execution(configuration)

    def native_command(self, operation, *arguments, configuration=None):
        configuration = self.native_projection() if configuration is None else configuration
        uid = self.preview['execution']['user']
        folder = self.root / 'native-private'
        if not folder.exists():
            if operation != 'initialize':
                raise Refused('native_configuration_missing', 5)
            folder.mkdir(mode=0o700)
            os.chown(folder, uid, uid)
        info = folder.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
                or info.st_mode & 0o077 or folder.is_symlink()):
            raise Refused('native_configuration_authority')
        path = folder / 'execution.json'
        if path.exists():
            if cloud_release.read_json(path) != configuration:
                raise Refused('native_configuration_changed', 6)
        else:
            if operation != 'initialize':
                raise Refused('native_configuration_missing', 5)
            write_record(path, configuration)
            os.chown(path, uid, uid)
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_mode & 0o077
                or info.st_nlink != 1):
            raise Refused('native_configuration_authority')
        environment = {key: value for key, value in os.environ.items()
                       if key in ('PATH', 'LANG', 'LC_ALL')}
        environment['HYPRN_MVP_CLOUD_EXECUTION_CONFIG'] = str(path)
        command = [configuration['python'], '-I', '-B',
                   str(Path(configuration['source']) / 'deployment/cloud_native.py'),
                   '--config', str(path), operation, *arguments]
        return command, environment, uid

    def native(self, operation, *arguments, configuration=None):
        configuration = self.native_projection() if configuration is None else configuration
        command, environment, uid = self.native_command(operation, *arguments, configuration=configuration)
        result = subprocess.run(command, env=environment, user=uid, group=uid,
                                extra_groups=self.native_socket_groups(uid, configuration=configuration),
                                capture_output=True, text=True, timeout=self.remaining())
        if result.returncode:
            raise Refused('native_owner_operation_refused', 6)
        value = json.loads(result.stdout)
        required = {'schema', 'installation_id', 'store_id', 'execution_root', 'profile',
                    'profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid',
                    'release_sha256', 'config_sha256'}
        if (set(value) != required or value['schema'] != 'hyprn-native-owner/v1'
                or any(value[key] != configuration[key] for key in
                       ('installation_id', 'store_id', 'execution_root', 'profile',
                        'release_sha256', 'config_sha256'))):
            raise Refused('native_owner_receipt_invalid', 6)
        for key in ('profile_uuid', 'repository_uuid', 'computer_uuid', 'code_uuid'):
            try:
                parsed = UUID(value[key]) if isinstance(value[key], str) else None
            except ValueError:
                parsed = None
            if parsed is None or value[key] not in (str(parsed), parsed.hex):
                raise Refused('native_owner_receipt_invalid', 6)
        return value

    def native_socket_groups(self, uid, *, configuration=None):
        configuration = self.native_projection() if configuration is None else configuration
        endpoint = configuration['docker']['endpoint'].removeprefix('unix://')
        path = Path(endpoint)
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise Refused('native_engine_socket_authority')
        info = path.stat()
        if (not stat.S_ISSOCK(info.st_mode) or info.st_uid not in (0, uid)
                or info.st_mode & 0o007 or info.st_gid == 0):
            raise Refused('native_engine_socket_authority')
        # Only the reviewed endpoint's non-root group; ambient host groups never
        # reach the execution owner. The privileged host controls this socket.
        return [info.st_gid]

    def rebind_native(self):
        """Explicit migration may replace a stopped owner's release, never its store."""
        configuration = self.native_projection()
        path = self.root / 'native-private/execution.json'
        from hyprn_mvp_integration.installation import validate_cloud_execution
        previous = validate_cloud_execution(cloud_release.read_json(path))
        # The execution user's file is only an observation. The protected host
        # receipt must bind its entire projection before any old command is run.
        projection = {key: value for key, value in previous.items()
                      if key not in ('release_sha256', 'config_sha256')}
        owner = control_record(self.root / 'native-owner.json')
        if (previous['config_sha256'] != cloud_release.digest(projection)
                or any(owner.get(key) != previous[key] for key in
                       ('installation_id', 'store_id', 'execution_root', 'profile',
                        'release_sha256', 'config_sha256'))):
            raise Refused('previous_native_configuration_unbound', 6)
        stable = ('schema', 'edition', 'installation_id', 'store_id', 'execution_root',
                  'profile', 'host_home', 'docker')
        if any(previous[key] != configuration[key] for key in stable):
            raise Refused('native_rebind_authority_changed', 6)
        self.native_quiescence()
        if self.native('inspect', configuration=previous) != owner:
            raise Refused('previous_native_owner_mismatch', 6)
        if previous == configuration:
            return owner
        authorization = self.root / 'native-rebind.json'
        write_record(authorization, dict(schema='hyprn-native-rebind/v1', previous=previous,
                     owner=owner, configuration_sha256=cloud_release.digest(configuration)), mode=0o644)
        # From this point an interruption leaves a changed projection with the
        # old protected receipt. Ordinary start refuses until reconciled.
        write_record(path, configuration)
        os.chown(path, self.preview['execution']['user'], self.preview['execution']['user'])
        actual = self.native('rebind', str(authorization))
        expected = dict(owner, release_sha256=configuration['release_sha256'],
                        config_sha256=configuration['config_sha256'])
        if actual != expected:
            raise Refused('native_rebind_identity_mismatch', 6)
        write_record(self.root / 'native-owner.json', actual)
        # A dead previous process receipt belongs to its old owner identity.
        (self.root / 'native-process.json').unlink(missing_ok=True)
        return actual

    def native_process(self):
        path = self.root / 'native-process.json'
        if not path.exists():
            return None
        value = control_record(path)
        if (set(value) != {'pid', 'identity', 'container_id', 'owner'}
                or type(value['pid']) is not int or value['pid'] <= 0
                or value['owner'] != control_record(self.root / 'native-owner.json')):
            raise Refused('native_process_identity_invalid', 6)
        actual = self.process_identity(value['pid'])
        if actual is None:
            return None
        if actual != value['identity']:
            raise Refused('native_process_identity_changed', 6)
        return value

    def process_identity(self, pid):
        result = subprocess.run(['ps', '-ww', '-p', str(pid), '-o', 'lstart=', '-o', 'command='],
                                capture_output=True, text=True, timeout=self.remaining())
        if result.returncode:
            return None
        return result.stdout.strip() or None

    def native_quiescence(self):
        if self.native_process() is not None:
            raise Refused('native_owner_running', 4)
        lock = Path(self.runtime['mounts']['execution']) / 'executor.lock'
        if not lock.exists():
            return
        fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('native_owner_unreconciled', 6) from None
        finally:
            os.close(fd)

    def running_native_workers(self, observe):
        return observe('ps', '--quiet', '--no-trunc', '--filter',
                       'label=org.hyprn-mvp.owner=hyprn-mvp-cloud-'
                       + self.runtime['installation_id']).split()

    def assert_stopped(self, *, allow_retained_images=False):
        """Observe stopped writers while the caller holds deployment/product/native locks.

        This does not acquire executor.lock again: the backup owner holds it for
        the whole snapshot, including these repeated observations. A Compose
        service summary is insufficient because one-off migrations can write too.
        """
        self.identity_check()
        admission = control_record(self.root / 'admission.json')
        if (admission.get('schema') != 'hyprn-admission/v1'
                or any(admission.get(key) != value for key, value in self.identity.items())
                or admission.get('browser') is not False
                or admission.get('scientific') is not False):
            raise Refused('backup_admission_not_closed', 6)
        if self.native_process() is not None:
            raise Refused('native_owner_running', 4)
        environment = {key: value for key, value in os.environ.items()
                       if key in ('PATH', 'LANG', 'LC_ALL')}

        def observe(*arguments):
            result = subprocess.run(['docker', *arguments], env=environment,
                                    capture_output=True, text=True, timeout=self.remaining())
            if result.returncode or len(result.stdout) > 1024 * 1024:
                raise Refused('writer_state_unavailable', 6)
            return result.stdout

        project = self.runtime['installation_id']
        workers = self.running_native_workers(observe)
        if workers:
            raise Refused('native_worker_running', 4)
        identifiers = observe('ps', '--all', '--quiet', '--no-trunc', '--filter',
                              'label=com.docker.compose.project=' + project).split()
        if (len(identifiers) > 512 or len(set(identifiers)) != len(identifiers)
                or any(not re.fullmatch(r'[0-9a-f]{64}', item) for item in identifiers)):
            raise Refused('writer_state_unavailable', 6)
        if not identifiers:
            return
        try:
            records = json.loads(observe('inspect', '--type', 'container', *identifiers))
            if (not isinstance(records, list) or len(records) != len(identifiers)
                    or {item['Id'] for item in records} != set(identifiers)):
                raise ValueError('container identity')
            images = {key: value['image']
                      for key, value in self.preview['compose']['services'].items()}
            images['database-operation'] = images['app']
            for item in records:
                config, state = item['Config'], item['State']
                labels = config['Labels']
                service = labels['com.docker.compose.service']
                if (labels['com.docker.compose.project'] != project or service not in images
                        or not allow_retained_images and config['Image'] != images[service]
                        or item['HostConfig']['RestartPolicy']['Name'] != 'no'):
                    raise Refused('writer_container_identity_mismatch', 6)
                if (any(state[key] is not False for key in ('Running', 'Paused', 'Restarting'))
                        or state['Status'] not in ('created', 'exited', 'dead')):
                    raise Refused('writer_container_not_stopped', 4)
        except (ValueError, TypeError, KeyError):
            raise Refused('writer_state_unavailable', 6) from None

    def start_native(self):
        owner = self.require_native_owner()
        if self.native('check') != owner:
            raise Refused('native_attestation_identity_mismatch', 6)
        running = self.native_process()
        if running is not None:
            return
        self.native_quiescence()
        self.compose('create', '--no-build', '--pull', 'never', 'dispatcher')
        container = self.compose('ps', '--all', '--quiet', 'dispatcher').strip()
        import re
        if not re.fullmatch(r'[0-9a-f]{64}', container):
            raise Refused('dispatcher_container_identity_missing', 6)
        command, environment, uid = self.native_command('serve', container)
        # Do not close a possibly running accepted operation on a timeout and
        # restart it. The intent receipt and executor lock force reconciliation.
        log = os.open(self.root / 'native-stderr.log', os.O_CREAT | os.O_APPEND | os.O_WRONLY
                      | os.O_NOFOLLOW, 0o600)
        try:
            child = subprocess.Popen(command, env=environment, user=uid, group=uid,
                                     extra_groups=self.native_socket_groups(uid),
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=log,
                                     start_new_session=True)
        finally:
            os.close(log)
        identity = self.process_identity(child.pid)
        if identity is None:
            raise Refused('native_owner_start_failed', 6)
        write_record(self.root / 'native-process.json',
                     dict(pid=child.pid, identity=identity, container_id=container, owner=owner))
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            if not selector.select(self.remaining()):
                raise Refused('native_owner_start_uncertain', 6)
            raw = child.stdout.readline(65537)
        if len(raw) > 65536 or json.loads(raw) != owner or child.poll() is not None:
            raise Refused('native_owner_start_uncertain', 6)
        child.stdout.close()

    def stop_native(self):
        process = self.native_process()
        if process is not None:
            os.kill(process['pid'], signal.SIGTERM)
            while self.process_identity(process['pid']) == process['identity']:
                time.sleep(min(0.1, self.remaining()))
        # A stopped attached client alone does not establish a stopped dispatcher.
        self.compose('stop', '--timeout', str(min(self.timeout, 120)), 'dispatcher')
        self.native_quiescence()

    def compose(self, *arguments):
        target = self.root / 'compose.json'
        write_record(target, self.preview['compose'])
        environment = {key: value for key, value in os.environ.items()
                       if key in ('PATH', 'LANG', 'LC_ALL')}
        result = subprocess.run(
            ['docker', 'compose', '--project-name', self.runtime['installation_id'],
             '--file', str(target), *arguments], env=environment, text=True,
            capture_output=True, timeout=self.remaining())
        if result.returncode:
            raise Refused('component_operation_failed', 6)
        return result.stdout

    def artifact_check(self):
        return cloud_release.payload(self.binding['payload_inventory'], self.release, self.contract)

    def database(self, operation):
        """One fixed image operation; never pass request/provider keys to migrations."""
        migration = operation in ('initialize', 'migrate', 'stopped-work')
        alias = 'db-app-migration' if migration else 'db-app-request'
        source = (self.binding.get('migration_secret_file') if migration else next(
            item['file'] for item in self.preview['secret_loads']
            if item['consumer'] == 'app' and item['alias'] == alias))
        if not source or not Path(source).is_file() or Path(source).is_symlink():
            raise Refused('database_credential_unavailable')
        app = self.preview['compose']['services']['app']
        environment = {key: value for key, value in app['environment'].items()
                       if key.startswith('HYPRN_MVP_DATABASE_')}
        environment.update(HYPRN_MVP_INSTALLATION_ID=self.runtime['installation_id'],
                           HYPRN_MVP_APPLICATION_STORE_ID=self.runtime['store_ids']['application'])
        target = '/run/secrets/' + alias
        environment['HYPRN_SECRET_' + alias.upper().replace('-', '_') + '_FILE'] = target
        ca = next(v for v in app['volumes'] if v['target'] == environment['HYPRN_MVP_DATABASE_CA_FILE'])
        service = {key: app[key] for key in ('image', 'user', 'read_only', 'cap_drop',
                   'security_opt', 'init', 'ulimits', 'tmpfs', 'mem_limit', 'cpus', 'pids_limit')}
        service.update(environment=environment, networks=['application'],
                       volumes=[ca, {'type': 'bind', 'source': source, 'target': target, 'read_only': True}],
                       entrypoint=['python', '-B', '-m', 'hyprn_mvp_cloud.database_cli'],
                       command=[operation], restart='no')
        path = self.root / 'database-operation.json'
        write_record(path, {'services': {'database-operation': service},
                           'networks': {'application': {'external': True,
                               'name': self.runtime['installation_id'] + '_application'}}})
        command = ['docker', 'compose', '--project-name', self.runtime['installation_id'],
                   '--file', str(path), 'run', '--rm', '--no-deps', '-T', 'database-operation']
        result = subprocess.run(command, capture_output=True, text=True, timeout=self.remaining(),
                                env={key: value for key, value in os.environ.items() if key in ('PATH', 'LANG', 'LC_ALL')})
        if result.returncode:
            raise Refused('database_operation_refused', 3)
        return json.loads(result.stdout)

    def drain(self):
        self.admission()
        deadline = self.deadline
        while time.monotonic() < deadline:
            counts = self.database('drain')
            if counts['uncertain']:
                raise Refused('accepted_operation_requires_reconciliation', 6)
            if counts['pending'] == 0 and counts['requests_quiescent']:
                return counts
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise Refused('drain_timeout', 4)

    def migration_quiescence(self):
        """Preserve unfinished records only after observing all their writers stopped.

        Retained service images may belong to the previous release. This permits
        no active container, restart policy or unknown service; ordinary backup
        and inspection continue to require exact image pins.
        """
        try:
            self.assert_stopped(allow_retained_images=True)
        except Refused as error:
            if error.reason not in {'native_owner_running', 'writer_container_not_stopped',
                                    'native_worker_running'}:
                raise
            self.drain()
            self.native_quiescence()
            self.compose('stop', '--timeout', str(min(self.timeout, 120)), 'app', 'modeling')
            self.assert_stopped(allow_retained_images=True)
        self.native_quiescence()
        counts = self.database('stopped-work')
        if (counts.get('requests_quiescent') is not True
                or type(counts.get('active_assistant_turns')) is not int
                or counts['active_assistant_turns'] != 0):
            raise Refused('stopped_work_has_active_requests', 6)
        self.assert_stopped(allow_retained_images=True)
        return counts

    def application_and_modeling(self, operation):
        """Explicit owner steps; native ownership must already be qualified by the host."""
        self.admission()
        self.artifact_check()
        # No hidden partial installation: require the native owner's receipt before
        # mutating either remaining owner. Its adapter is a separate prerequisite.
        if operation == 'initialize':
            model_root = Path(self.runtime['mounts']['modeling'])
            if not model_root.is_dir() or any(model_root.iterdir()):
                raise Refused('modeling_store_not_empty', 6)
            execution_root = Path(self.runtime['mounts']['execution'])
            if (not execution_root.is_dir() or any(execution_root.iterdir())
                    or (self.root / 'native-owner.json').exists()):
                raise Refused('execution_store_not_empty', 6)
            owner = self.native('initialize')
            write_record(self.root / 'native-owner.json', owner)
        else:
            # Closed, stopped owners can carry unresolved records into the new
            # release without retrying them or representing them as completed.
            self.migration_quiescence()
            self.rebind_native()
        # Create the fixed networks without starting either service or migrating.
        self.compose('create', '--no-build', '--pull', 'never', 'app', 'modeling')
        application = self.database(operation)
        script = ('test ! -e /store/model.sqlite3 && bundle exec rails db:schema:load db:migrate '
                  '&& touch /store/initialized' if operation == 'initialize' else
                  'test -f /store/initialized && bundle exec rails db:migrate')
        self.compose('run', '--rm', '--no-deps', '-T', '--entrypoint', 'sh', 'modeling', '-ec', script)
        if operation == 'initialize':
            write_record(Path(self.runtime['mounts']['modeling']) / 'initialized',
                         dict(schema='hyprn-modeling-owner/v1', installation_id=self.runtime['installation_id'],
                              store_id=self.runtime['store_ids']['modeling']), mode=0o644)
        return application

    def operation(self, operation):
        self.identity_check()
        if operation == 'inspect':
            # The fixed probe reads current credentials and current schema without
            # running startup, migrations, Assistant requests or candidate code.
            return self.inspect_schemas(self.inspection_owner())
        if operation == 'check':
            self.artifact_check()
            self.native('check')
            return self.operation('inspect')
        if operation == 'drain':
            self.drain()
            self.require_native_owner()
            return self.database('inspect')
        if operation in ('initialize', 'migrate'):
            return self.application_and_modeling(operation)
        if operation == 'stop':
            self.admission()
            self.require_native_owner()
            self.stop_native()
            self.compose('stop', '--timeout', str(min(self.timeout, 120)), 'app', 'modeling')
            self.assert_stopped()
            return None
        if operation == 'start':
            self.admission()
            self.artifact_check()
            self.require_native_owner()
            # Startup cannot migrate. Capture coherent owner schemas while all
            # writers are still stopped, before their first writable connection.
            observed = self.operation('inspect')
            # Init and migrations are independent operations; images must refuse
            # an absent store. Dispatcher remains a host-owned attached child.
            self.compose('up', '--no-build', '--pull', 'never', '--wait',
                         '--wait-timeout', str(self.timeout), '-d', 'modeling', 'app')
            self.start_native()
            return observed
        if operation == 'qualify':
            self.admission()
            self.artifact_check()
            self.native_quiescence()
            owner = self.require_native_owner()
            if self.native('attest') != owner:
                raise Refused('native_attestation_identity_mismatch', 6)
            return self.operation('inspect')
        # Never advertise an unimplemented owner operation as successful. The
        # native bundle/host bridge must supply actual owner evidence first.
        self.admission()
        raise Refused('owner_lifecycle_not_qualified', 6)


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise Refused('invalid_arguments')


def timeout_expired(_signal, _frame):
    raise Refused('operation_timeout', 6)


def main(argv=None):
    result = {'operation_id': None, 'operation': None, 'installation_id': None,
              'status': 'refused', 'reason_code': 'invalid_arguments',
              'observed_schema_versions': None, 'evidence_refs': []}
    lifecycle = None
    receipt = None
    receipt_identity = None
    previous_alarm = None
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('operation', choices=OPERATIONS)
        parser.add_argument('--binding', required=True)
        parser.add_argument('--operation-id', required=True)
        parser.add_argument('--timeout', required=True, type=int)
        parser.add_argument('--surface', choices=('browser', 'scientific'))
        parser.add_argument('--state', choices=('open', 'closed'))
        parser.add_argument('--compatibility-active-binding')
        args = parser.parse_args(argv)
        if str(UUID(args.operation_id)) != args.operation_id or not 1 <= args.timeout <= 3600:
            raise Refused('invalid_arguments')
        if ((args.operation == 'admission') != bool(args.surface and args.state)
                or (args.operation != 'admission' and (args.surface or args.state))
                or (args.compatibility_active_binding and args.operation != 'inspect')):
            raise Refused('invalid_arguments')
        result.update(operation_id=args.operation_id, operation=args.operation)
        previous_alarm = signal.signal(signal.SIGALRM, timeout_expired)
        signal.setitimer(signal.ITIMER_REAL, args.timeout)
        spec = binding(args.binding, args.operation)
        lifecycle = Lifecycle(spec, args.timeout)
        result['installation_id'] = lifecycle.identity['installation_id']
        with exclusive(lifecycle.root):
            if args.compatibility_active_binding:
                inspection_owner = lifecycle.inspection_owner(args.compatibility_active_binding)
            else:
                lifecycle.identity_check()
            receipt_inputs = dict(
                identity=lifecycle.identity, binding=spec, operation=args.operation,
                surface=args.surface, state=args.state)
            if args.compatibility_active_binding:
                receipt_inputs['compatibility_active_binding'] = dict(
                    path=args.compatibility_active_binding,
                    binding_sha256=cloud_release.digest(binding(args.compatibility_active_binding, 'inspect')),
                    native_owner=inspection_owner)
            receipt_identity = cloud_release.digest(receipt_inputs)
            target = lifecycle.root / ('operation-' + args.operation_id + '.json')
            if target.exists():
                previous = control_record(target)
                if previous.get('identity_sha256') != receipt_identity:
                    raise Refused('operation_identity_mismatch')
                if previous.get('state') != 'complete':
                    raise Refused('operation_requires_reconciliation', 6)
                print(json.dumps(previous['result'], sort_keys=True))
                return previous['exit_code']
            receipt = target
            write_record(receipt, dict(identity_sha256=receipt_identity, state='intent'))
            if args.operation == 'admission':
                lifecycle.admission(surface=args.surface, state=args.state)
            elif args.compatibility_active_binding:
                result['observed_schema_versions'] = lifecycle.inspect_schemas(inspection_owner)
            else:
                result['observed_schema_versions'] = lifecycle.operation(args.operation)
        result.update(status='success', reason_code='completed')
        code = 0
    except Refused as error:
        code = error.code
        result.update(reason_code=error.reason,
                      status='recovery_required' if code == 6 else 'refused')
    except subprocess.TimeoutExpired:
        code = 6
        result.update(status='recovery_required', reason_code='operation_timeout')
    except Exception:
        code = 5
        result.update(status='failed', reason_code='verification_failed')
    finally:
        if previous_alarm is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_alarm)
    if code and lifecycle is not None and result['operation'] not in ('inspect', 'check'):
        try:
            lifecycle.admission()
        except Exception:
            pass  # Missing/unreadable/expired admission is closed at every consumer.
    if receipt is not None:
        try:
            result['evidence_refs'] = [receipt.name]
            write_record(receipt, dict(identity_sha256=receipt_identity, state='complete',
                                       result=result, exit_code=code))
        except Exception:
            code = 6
            result.update(status='recovery_required', reason_code='operation_receipt_unavailable')
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
