"""Scoped installed cloud application rehearsal using verified OCI payload bytes."""

import base64
from email.message import Message
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time
from types import SimpleNamespace
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import uuid4

import cloud_release
import scoped_fixture as fixture
from installed_native_fixture import LABEL, owned_volume

POSTGRES = 'postgres@sha256:45cd22f8d32e189d245403954882f88e7a8714301fda80dab6da90f1265b25a3'


def docker(*args, input=None, timeout=120, accepted=True):
    result = subprocess.run(['docker', *args], input=input, capture_output=True, text=True,
                            timeout=timeout, env={**os.environ, 'DOCKER_DEFAULT_PLATFORM': 'linux/amd64'})
    if accepted and result.returncode:
        raise RuntimeError('Isolated Docker operation failed: ' + result.stderr[-3000:])
    return result


def response(client, origin, path, *, method='GET', value=None, headers=None, timeout=20):
    return client.request(origin + path, method=method, value=value, headers=headers, timeout=timeout)


class HTTPSClient:
    """Public-boundary client executed in a separate container with no store credentials."""

    def __init__(self, container, external_origin):
        self.container, self.addheaders, self.cookies = container, [], CookieJar()
        self.authority = urlsplit(external_origin).netloc

    def request(self, url, *, method='GET', value=None, headers=None, timeout=20):
        # Ingress preserves the configured external Host over its internal hop.
        # The URL still verifies the actual internal TLS peer certificate.
        sent = {'Content-Type': 'application/json', 'Host': self.authority,
                **dict(self.addheaders), **(headers or {})}
        cookie_request = Request(url, headers=sent, method=method)
        self.cookies.add_cookie_header(cookie_request)
        sent = dict(cookie_request.header_items())
        result = docker('exec', '-i', self.container, 'python', '-B', '/fixture-controller.py', 'request',
            input=json.dumps(dict(url=url, method=method, headers=sent, timeout=min(10, timeout),
                body=None if value is None else base64.b64encode(json.dumps(value).encode()).decode())),
            timeout=timeout)
        reply = json.loads(result.stdout)
        if reply.get('connection_unavailable'):
            raise ConnectionError('Isolated HTTPS transport failed: '
                + reply['reason_type'] + ': ' + reply['reason'])
        received = Message()
        for key, value in reply['headers']:
            received[key] = value
        self.cookies.extract_cookies(SimpleNamespace(info=lambda: received), cookie_request)
        return reply['status'], received, base64.b64decode(reply['body'])


def rehearse_application(scope, inputs, documents, payload):
    fixture.guarded(scope, lambda _: None)
    run = scope.run_uuid
    image_archive = payload['files']['app']
    expected = documents['release']['images']['app'].split('@sha256:')[1]
    cloud_release.verify_oci(image_archive, expected)
    with tarfile.open(image_archive) as archive:
        manifest = json.load(archive.extractfile('blobs/sha256/' + expected))
        config_image = manifest['config']['digest']
    docker('image', 'load', '--input', str(image_archive), timeout=180)
    image = 'sha256:' + expected
    inspected = docker('image', 'inspect', image, accepted=False)
    if inspected.returncode:
        # Classic Docker addresses the config; containerd addresses the manifest.
        image = config_image
        inspected = docker('image', 'inspect', image)
    actual = json.loads(inspected.stdout)[0]
    if actual['Id'] not in ('sha256:' + expected, config_image):
        raise ValueError('Imported image identity differs from verified OCI graph')
    if (actual['Os'], actual['Architecture']) != ('linux', 'amd64'):
        raise ValueError('Installed app must be the verified Linux amd64 image')
    evidence = fixture.scoped_path(scope, 'evidence')
    name = 'hyprn-installed-app-' + run
    volume, network = name + '-state', name + '-network'
    containers = []
    made_volume = made_network = False
    controller = Path(__file__).with_name('installed_hosted_app.py')
    common = ['--pull=never', '--platform=linux/amd64', '--read-only',
              '--security-opt=no-new-privileges:true', '--label', LABEL + '=' + run,
              '--memory=512m', '--cpus=1', '--pids-limit=128',
              '--tmpfs=/tmp:rw,noexec,nosuid,size=64m,mode=1777']
    records = []
    try:
        docker('volume', 'create', '--label', LABEL + '=' + run, volume)
        made_volume = True
        volume_source = owned_volume(volume, run)
        docker('network', 'create', '--internal', '--label', LABEL + '=' + run, network)
        made_network = True
        script_mount = ['--mount', 'type=bind,source=' + str(controller) + ',target=/fixture-controller.py,readonly']
        root_mount = ['--mount', 'type=volume,source=' + volume + ',target=/fixture']
        def root_action(*arguments):
            return docker('run', '--rm', *common, '--network=none', '--user=0:0',
                *root_mount, *script_mount, image, 'python', '-B', '/fixture-controller.py', *arguments)
        seeded = json.loads(root_action('seed', 'artifact-' + run,
                                       cloud_release.digest(documents['release'])).stdout)
        ui = cloud_release.read_json(payload['files']['ui'])
        if seeded['assets'] != {path: row['sha256'] for path, row in ui['files'].items()}:
            raise AssertionError('Image UI differs from the release UI manifest')
        if seeded['api_sha256'] != documents['release']['product_contracts']['api_sha256']:
            raise AssertionError('Image public contract differs from release')
        ca_path = fixture.scoped_path(scope, 'artifacts/installed-hosted-ca.pem')
        ca_path.write_text(seeded['ca'])
        def mounts(names, *, writable=()):
            values = []
            for relative in names:
                values.extend(['--mount', 'type=bind,source=' + volume_source + '/' + relative
                    + ',target=/fixture/' + relative + ('' if relative in writable else ',readonly')])
            return values
        client_container = name + '-client'
        containers.append(client_container)
        docker('run', '--detach', *common, '--name', client_container, '--network', network,
            '--cap-drop=ALL', '--user=10002:10002', *mounts(('ca.pem',)), *script_mount,
            image, 'python', '-B', '/fixture-controller.py', 'client')
        database_name = name + '-postgres'
        containers.append(database_name)
        docker('create', *common, '--name', database_name, '--network', network,
            '--network-alias=postgres', '--env-file=/dev/stdin',
            '--tmpfs=/var/lib/postgresql/data:rw,noexec,nosuid,size=256m',
            '--tmpfs=/var/run/postgresql:rw,noexec,nosuid,size=8m,mode=1777',
            *mounts(('postgres.crt', 'postgres.key')), POSTGRES,
            'postgres', '-c', 'ssl=on', '-c', 'ssl_cert_file=/fixture/postgres.crt',
            '-c', 'ssl_key_file=/fixture/postgres.key', input='POSTGRES_PASSWORD=' + seeded['password'] + '\n')
        docker('start', database_name)
        for _ in range(120):
            if docker('exec', database_name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', accepted=False).returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError('Isolated TLS PostgreSQL did not start')
        roles = ('hyprn_request', 'hyprn_auth', 'hyprn_migration', 'hyprn_assistant_background',
                 'hyprn_dispatcher_background')
        sql = ''.join("CREATE ROLE " + role + " LOGIN PASSWORD '" + seeded['password'] + "';\n" for role in roles)
        sql += 'GRANT CREATE ON SCHEMA public TO hyprn_migration;\n'
        docker('exec', '-i', database_name, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', input=sql)
        def database(operation, *, accepted=True, foreign=False):
            alias = 'db-app-migration' if operation in ('initialize', 'migrate') else 'db-app-request'
            result = docker('run', '--rm', *common, '--cap-drop=ALL', '--user=10002:10002',
                '--network', network, *mounts(('environment.json', 'ca.pem', 'secrets/' + alias)),
                *script_mount, image, 'python', '-B', '/fixture-controller.py',
                'database-foreign' if foreign else 'database', operation,
                accepted=False)
            if (result.returncode == 0) != accepted:
                (evidence / ('database-' + operation + '.stderr')).write_text(result.stderr)
                raise AssertionError('Packaged database ' + operation + ' outcome differs: ' + result.stdout)
            return json.loads(result.stdout)
        app_mounts = ('environment.json', 'ca.pem', 'https.crt', 'https.key', 'jwks.json', 'control', 'data',
                      'secrets/db-app-request', 'secrets/db-app-auth', 'secrets/db-assistant-background',
                      'secrets/modeling-auth', 'secrets/assistant-provider')
        def create_app(suffix, *, expect_start=True):
            container = name + '-' + suffix
            containers.append(container)
            stable_alias = ['--network-alias=application'] if expect_start else []
            docker('create', *common, '--name', container, '--cap-drop=ALL', '--user=10002:10002',
                '--network', network, '--network-alias=application-' + suffix, *stable_alias,
                *mounts(app_mounts, writable=('data',)), *script_mount,
                image, 'python', '-B', '/fixture-controller.py', 'serve')
            docker('start', container)
            origin = 'https://application-' + suffix + ':8000'
            probe = HTTPSClient(client_container, seeded['origin'])
            deadline = time.monotonic() + 90
            unavailable = None
            while time.monotonic() < deadline:
                info = json.loads(docker('inspect', container,
                    timeout=min(15, deadline-time.monotonic())).stdout)[0]
                if not info['State']['Running']:
                    log = docker('logs', container).stdout + docker('logs', container).stderr
                    (evidence / (suffix + '.log')).write_text(log)
                    if expect_start:
                        raise AssertionError('Packaged cloud factory failed; inspect ' + suffix + '.log')
                    if info['State']['ExitCode'] == 0:
                        raise AssertionError('Refused factory returned success')
                    return container, origin
                try:
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        break
                    status, _, _ = response(probe, origin, '/api/1/session/mode', timeout=min(15, remaining))
                    if status == 401:
                        if not expect_start:
                            raise AssertionError('Factory started despite invalid state')
                        return container, 'https://application:8000'
                except (ConnectionError, TimeoutError) as error:
                    unavailable = str(error)
                time.sleep(0.2)
            raise RuntimeError('Packaged application readiness timed out: ' + str(unavailable))
        create_app('uninitialized', expect_start=False)
        initialized = database('initialize')
        database('initialize', accepted=False)
        database('inspect', accepted=False, foreign=True)
        root_action('admission', 'browser')
        app_name, origin = create_app('first')
        create_app('conflicting-writer', expect_start=False)
        database('migrate', accepted=False)
        clients = []
        for subject in ('person-a', 'person-b'):
            client = HTTPSClient(client_container, seeded['origin'])
            client.addheaders = [('Cf-Access-Jwt-Assertion', seeded['tokens'][subject]),
                                 ('Origin', seeded['origin'])]
            status, headers, raw = response(client, origin, '/api/1/session/external', method='POST', value={})
            if status != 200 or not all(flag in headers['Set-Cookie'].lower() for flag in ('secure', 'httponly', 'samesite=strict')):
                raise AssertionError('Packaged hosted sign-in failed: ' + str(status)
                    + ' Location=' + str(headers.get('Location')) + ' ' + raw.decode())
            client.addheaders.append(('X-CSRF-Token', json.loads(raw)['data']['csrf_token']))
            if response(client, origin, '/api/1/session/mode', headers={'Host': 'unreviewed.invalid'})[0] != 403:
                raise AssertionError('Hosted request accepted an unreviewed external Host')
            status, _, raw = response(client, origin, '/api/1/studies', method='POST',
                                     value=dict(command_id=str(uuid4()), name='Private ' + subject))
            if status != 201:
                raise AssertionError('Packaged private study creation failed: ' + str(status) + ' ' + raw.decode())
            clients.append((client, json.loads(raw)['data']))
        saved_reads = {}
        def private_reads(origin):
            for index, (client, own) in enumerate(clients):
                status, _, raw = response(client, origin, '/api/1/studies')
                if status != 200 or [item['study_id'] for item in json.loads(raw)['data']] != [own['study_id']]:
                    raise AssertionError('Private study listing differs')
                status, _, raw = response(client, origin, '/api/1/studies/' + own['study_id'])
                data = json.loads(raw).get('data')
                if status != 200 or data['study_id'] != own['study_id'] or data['name'] != own['name']:
                    raise AssertionError('Persisted study changed')
                if own['study_id'] in saved_reads and data != saved_reads[own['study_id']]:
                    raise AssertionError('Restart changed the saved study')
                saved_reads[own['study_id']] = data
                foreign = clients[1-index][1]['study_id']
                if response(client, origin, '/api/1/studies/' + foreign)[0] != 404:
                    raise AssertionError('Foreign private study disclosed')
        private_reads(origin)
        if response(clients[0][0], origin, '/api/1/studies/' + clients[0][1]['study_id'] + '/runs',
                    method='POST', value={'command_id': str(uuid4())})[0] != 503:
            raise AssertionError('Browser admission permitted scientific work')
        for relative, digest in seeded['assets'].items():
            status, _, raw = response(clients[0][0], origin, '/ui/' + relative)
            if status != 200 or hashlib.sha256(raw).hexdigest() != digest:
                raise AssertionError('Served image UI bytes differ')
        root_action('admission', 'closed')
        if response(clients[0][0], origin, '/api/1/studies')[0] != 503:
            raise AssertionError('Closed host admission accepted a read')
        for admission_state in ('expired', 'missing'):
            root_action('admission', admission_state)
            if response(clients[0][0], origin, '/api/1/studies')[0] != 503:
                raise AssertionError('Unavailable host admission accepted a read')
        docker('stop', '--time=15', app_name)
        docker('network', 'disconnect', network, app_name)
        version = initialized['application'][-1]
        def change_checksum(checksum):
            docker('exec', '-i', database_name, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres',
                   input="UPDATE hyprn_schema_versions SET checksum='" + checksum + "' WHERE version='"
                         + version['version'] + "';\n")
        change_checksum('0' * 64)
        create_app('schema-refused', expect_start=False)
        change_checksum(version['checksum'])
        migrated = database('migrate')
        if initialized != migrated or database('inspect') != initialized:
            raise AssertionError('Explicit migration changed installed schema identity')
        root_action('admission', 'browser')
        _, replacement = create_app('replacement')
        private_reads(replacement)
        records = dict(schema='hyprn-installed-application-evidence/v1', source_commit=documents['release']['source_commit'],
                       app_manifest_sha256=expected, image=image, payload_sha256=payload['inventory_sha256'],
                       database_tls=True, actual_packaged_factory=True,
                       external_boundaries='synthetic-read-only-jwks-and-provider',
                       initial_install=True, reinitialize_refused=True, uninitialized_start_refused=True,
                       conflicting_writer_refused=True, live_migration_refused=True,
                       foreign_store_refused=True, incompatible_schema_start_refused=True,
                       private_studies=2, foreign_reads_denied=True, foreign_host_refused=True,
                       served_ui_files=len(seeded['assets']),
                       api_sha256=seeded['api_sha256'],
                       closed_admission_refused=True, expired_admission_refused=True,
                       missing_admission_refused=True, scientific_admission_refused=True,
                       replacement_retained_studies=True,
                       schema_identity=initialized, aggregate_host_lifecycle_verified=False)
        (evidence / 'installed-hosted-application.json').write_text(json.dumps(records, sort_keys=True, indent=2))
        return records
    finally:
        for container in reversed(containers):
            info = docker('inspect', container, accepted=False)
            if info.returncode:
                continue
            if json.loads(info.stdout)[0]['Config']['Labels'].get(LABEL) != run:
                raise ValueError('Foreign fixture container cleanup refused')
            if container.endswith(('-first', '-replacement')):
                # Keep bounded failure evidence before removing the only server
                # that can distinguish an HTTP failure from a transport failure.
                details = json.loads(info.stdout)[0]
                (evidence / (container.rsplit('-', 1)[-1] + '-state.json')).write_text(
                    json.dumps(dict(state=details['State'], networks=details['NetworkSettings']['Networks']),
                               sort_keys=True, indent=2))
                try:
                    logs = docker('logs', '--tail=100', container, timeout=15, accepted=False)
                    text = (logs.stdout + logs.stderr)[-32768:]
                except subprocess.TimeoutExpired:
                    text = 'Bounded app log collection timed out; cleanup continued.'
                (evidence / (container.rsplit('-', 1)[-1] + '.log')).write_text(text)
            docker('rm', '--force', '--volumes', container)
        if made_network:
            info = json.loads(docker('network', 'inspect', network).stdout)[0]
            if info.get('Labels', {}).get(LABEL) != run:
                raise ValueError('Foreign fixture network cleanup refused')
            docker('network', 'rm', network)
        if made_volume:
            owned_volume(volume, run)
            docker('volume', 'rm', volume)
        (evidence / 'installed-hosted-cleanup.json').write_text(json.dumps(dict(released=True, scope=run)))
