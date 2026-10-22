"""A dedicated PostgreSQL instance; teardown is fenced by its random ownership label."""

from contextlib import contextmanager
from dataclasses import replace
import json
import secrets
import subprocess
import time
from uuid import uuid4

from hyprn_mvp_app.database import Connection, PostgreSQLCredentials
from hyprn_mvp_app.migrations import initialize

# Official docker-library/postgres 17.6-bookworm, Linux amd64. This is test
# infrastructure, not the production database image or an execution worker.
IMAGE = 'postgres@sha256:45cd22f8d32e189d245403954882f88e7a8714301fda80dab6da90f1265b25a3'
LABEL = 'ai.hyprn.fixture.postgres'


def docker(*args, input=None):
    return subprocess.run(
        ['docker', *args],
        input=input,
        text=True,
        capture_output=True,
        check=True,
        timeout=90,
    ).stdout.strip()


@contextmanager
def postgres_fixture(*, initialize_schema=True):
    identity = uuid4().hex
    name = f'hyprn-pg-test-{identity}'
    password = secrets.token_urlsafe(32)
    # Password input stays on stdin, never argv, subprocess error text or files.
    created = False
    try:
        docker(
            'create',
            '--name',
            name,
            '--label',
            f'{LABEL}={identity}',
            '--platform',
            'linux/amd64',
            '--memory',
            '512m',
            '--cpus',
            '1',
            '--pids-limit',
            '128',
            '--publish',
            '127.0.0.1::5432',
            '--tmpfs',
            '/var/lib/postgresql/data:rw,noexec,nosuid,size=256m',
            '--env-file',
            '/dev/stdin',
            IMAGE,
            input=f'POSTGRES_PASSWORD={password}\n',
        )
        created = True
        docker('start', name)
        info = json.loads(docker('inspect', name))[0]
        port = int(info['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort'])
        admin = PostgreSQLCredentials('127.0.0.1', 'postgres', 'postgres', password, port, False)
        for _ in range(150):
            try:
                raw = admin.connect()
                break
            except ImportError:
                raise
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError('Fixture PostgreSQL did not become ready')
        try:
            db = Connection(raw)
            for role in ('hyprn_request', 'hyprn_auth', 'hyprn_migration',
                         'hyprn_assistant_background', 'hyprn_dispatcher_background'):
                # Static audited role identifiers; generated fixture-only password.
                db.execute(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'")
            db.execute('GRANT CREATE ON SCHEMA public TO hyprn_migration')
            raw.commit()
        finally:
            raw.close()
        migration = replace(admin, user='hyprn_migration', password=password)
        if initialize_schema:
            initialize(migration)
        request = replace(admin, user='hyprn_request', password=password)
        auth = replace(admin, user='hyprn_auth', password=password)
        yield dict(admin=admin, migration=migration, request=request, auth=auth, name=name,
                   assistant=replace(admin, user='hyprn_assistant_background'),
                   dispatcher=replace(admin, user='hyprn_dispatcher_background'))
    finally:
        if created:
            info = json.loads(docker('inspect', name))[0]
            if info['Config']['Labels'].get(LABEL) != identity:
                raise RuntimeError('Refusing cleanup of a foreign PostgreSQL container')
            docker('rm', '--force', '--volumes', name)


@contextmanager
def hosted_http(root, *, dist=None):
    """Real TLS ingress and PostgreSQL; only the provider's signing keys are synthetic."""
    from datetime import datetime, timedelta, timezone
    import ipaddress
    from pathlib import Path
    import socket
    import sys
    from threading import Thread
    import httpx
    import jwt
    import uvicorn
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'editions/cloud/src'))
    from hyprn_mvp_cloud.access import AccessVerifier
    from hyprn_mvp_cloud.asgi import AccessIngress
    from hyprn_mvp_app.api import create_app
    from hyprn_mvp_app.external_identity import HostedAuth
    from hyprn_mvp_app.store import Store
    from hyprn_mvp_app.ui import WorkspaceFiles

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer, audience = 'https://synthetic.cloudflareaccess.com', 'synthetic-browser'
    kid = 'fixture-' + uuid4().hex
    public = {**jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True),
              'kid': kid, 'alg': 'RS256', 'use': 'sig'}
    verifier = AccessVerifier(issuer, audience, transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={'keys': [public]})))
    def assertion(subject, **claims):
        now = int(time.time())
        payload=dict(iss=issuer, aud=audience, sub=subject, iat=now-1, exp=now+600)
        payload.update(claims)
        return jwt.encode(payload, key, algorithm='RS256', headers={'kid': kid})
    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'isolated fixture')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(tls_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
            .not_valid_after(now+timedelta(hours=1)).add_extension(x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False).sign(tls_key, hashes.SHA256()))
    cert_path, key_path = root / 'tls.pem', root / 'tls-key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(tls_key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    with postgres_fixture() as fixture, socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); sock.listen()
        origin = f'https://127.0.0.1:{sock.getsockname()[1]}'
        store = Store.postgres(fixture['request'], fixture['auth'], artifact_root=root,
                               background=fixture['assistant'])
        auth = HostedAuth(store, origin)
        app = create_app(store, auth, None)
        if dist is not None:
            app.mount('/ui', WorkspaceFiles(directory=dist, html=True))
        outer = AccessIngress(app, auth, verifier)
        server = uvicorn.Server(uvicorn.Config(outer, log_level='critical', lifespan='off',
            ssl_certfile=str(cert_path), ssl_keyfile=str(key_path)))
        thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(0.05)
            if not server.started:raise RuntimeError('Fixture HTTPS server did not start')
            yield dict(fixture=fixture, store=store, auth=auth, app=app, origin=origin,
                       assertion=assertion, issuer=issuer, key_id=kid, public_key=public)
        finally:
            server.should_exit=True; thread.join(15); verifier.close()
            key_path.unlink(missing_ok=True); cert_path.unlink(missing_ok=True)
            if thread.is_alive():raise RuntimeError('Fixture HTTPS server did not stop')
