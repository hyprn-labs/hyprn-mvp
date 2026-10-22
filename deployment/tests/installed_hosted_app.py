"""Fixture entry point run inside the exact application image, never a source mount.

Only external provider/JWKS HTTP transports are synthetic. The packaged factory,
TLS database, admission, sessions, routes, persistence and UI are unchanged.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import sys
import time

ROOT = Path('/fixture')


def write(path, raw, *, uid=0, mode=0o644):
    path.write_bytes(raw)
    path.chmod(mode)
    os.chown(path, uid, uid)


def record(path, value, **permissions):
    write(path, json.dumps(value, sort_keys=True).encode(), **permissions)


def seed(installation, release_hash):
    import jwt
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from managed_assistant import definition

    ROOT.chmod(0o755)
    for name in ('control', 'secrets', 'data', 'data/artifacts'):
        path = ROOT / name
        path.mkdir(mode=0o755)
        if name.startswith('data'):
            os.chown(path, 10002, 10002)
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'isolated hosted artifact CA')])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))
    ca_bytes = ca.public_bytes(serialization.Encoding.PEM)
    write(ROOT / 'ca.pem', ca_bytes)
    for name, uid, alternatives in (
            ('postgres', 999, [x509.DNSName('postgres')]),
            ('https', 10002, [x509.IPAddress(ipaddress.ip_address('127.0.0.1')), x509.DNSName('application'),
                *[x509.DNSName('application-' + suffix) for suffix in
                  ('first', 'replacement', 'uninitialized', 'conflicting-writer', 'schema-refused')]])):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'isolated ' + name)])
        certificate = (x509.CertificateBuilder().subject_name(leaf_name).issuer_name(ca_name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(hours=2))
            .add_extension(x509.SubjectAlternativeName(alternatives), critical=False)
            .sign(ca_key, hashes.SHA256()))
        write(ROOT / (name + '.crt'), certificate.public_bytes(serialization.Encoding.PEM))
        write(ROOT / (name + '.key'), key.private_bytes(serialization.Encoding.PEM,
              serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), uid=uid, mode=0o600)
    password = secrets.token_urlsafe(32)
    for alias in ('db-app-request', 'db-app-auth', 'db-app-migration', 'db-assistant-background'):
        write(ROOT / 'secrets' / alias, password.encode(), uid=10002, mode=0o600)
    for alias in ('modeling-auth', 'assistant-provider'):
        write(ROOT / 'secrets' / alias, secrets.token_urlsafe(32).encode(), uid=10002, mode=0o600)
    plan = definition('staging', 'claude-sonnet-5-5', 'high')
    record(ROOT / 'control/assistant-plan.json', plan)
    prefix = 'HYPRN_MVP_'
    values = dict(EDITION='cloud', EXTERNAL_ORIGIN='https://staging.hyprn.ai', UI_ROOT='/app/ui',
        MODEL_URL='http://unavailable-modeling.invalid:3000/modeling/1',
        ARTIFACT_ROOT='/fixture/data/artifacts', INSTALLATION_ID=installation,
        APPLICATION_STORE_ID='application-' + installation,
        DATABASE_HOST='postgres', DATABASE_PORT='5432', DATABASE_NAME='postgres',
        DATABASE_ROLE='hyprn_request', DATABASE_AUTH_ROLE='hyprn_auth',
        DATABASE_ASSISTANT_BACKGROUND_ROLE='hyprn_assistant_background',
        DATABASE_SSLMODE='verify-full', DATABASE_TLS_SERVER_NAME='postgres',
        DATABASE_CA_FILE='/fixture/ca.pem', DATABASE_CA_SHA256=hashlib.sha256(ca_bytes).hexdigest(),
        ACCESS_ISSUER='https://synthetic.cloudflareaccess.com', ACCESS_AUDIENCE='artifact-fixture',
        HOST_IDENTITY_FILE='/fixture/control/runtime-identity.json',
        ADMISSION_FILE='/fixture/control/admission.json',
        ASSISTANT_KEY_FILE='/fixture/secrets/assistant-provider',
        ASSISTANT_AGENT_ID='agent_fixture', ASSISTANT_AGENT_VERSION='1',
        ASSISTANT_ENVIRONMENT_ID='environment_fixture', ASSISTANT_PRIOR_CENTS='0',
        ASSISTANT_TOTAL_CENTS='100', ASSISTANT_DEFINITIONS_SHA256=plan['definitions_sha256'],
        ASSISTANT_CONFIGURATION_SHA256=plan['configuration_sha256'],
        ASSISTANT_PLAN_FILE='/fixture/control/assistant-plan.json',
        ASSISTANT_CONTINUITY_FILE='/fixture/control/assistant-continuity.json')
    environment = {prefix + key: value for key, value in values.items()}
    for alias in ('db-app-request', 'db-app-auth', 'db-app-migration', 'db-assistant-background', 'modeling-auth'):
        environment['HYPRN_SECRET_' + alias.upper().replace('-', '_') + '_FILE'] = '/fixture/secrets/' + alias
    record(ROOT / 'environment.json', environment)
    identity = dict(installation_id=installation, release_sha256=release_hash,
        config_sha256=hashlib.sha256(json.dumps(environment, sort_keys=True).encode()).hexdigest())
    record(ROOT / 'control/runtime-identity.json', identity)
    record(ROOT / 'control/assistant-continuity.json', dict(schema='hyprn-assistant-continuity/v1',
        **identity, configuration_sha256=plan['configuration_sha256'], prior_cents=0, total_cents=100,
        carried_sessions={}, untracked_cents=0,
        review_sha256=hashlib.sha256(b'fresh isolated fixture: enumerated empty provider').hexdigest()))
    signing = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    kid = 'isolated-artifact'
    public = dict(jwt.algorithms.RSAAlgorithm.to_jwk(signing.public_key(), as_dict=True),
                  kid=kid, alg='RS256', use='sig')
    record(ROOT / 'jwks.json', {'keys': [public]})
    tokens = {subject: jwt.encode(dict(iss=values['ACCESS_ISSUER'], aud=values['ACCESS_AUDIENCE'],
              sub=subject, iat=int(time.time())-1, exp=int(time.time())+3600), signing,
              algorithm='RS256', headers={'kid': kid}) for subject in ('person-a', 'person-b')}
    assets = {str(path.relative_to('/app/ui')): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in Path('/app/ui').rglob('*') if path.is_file()}
    api_sha256 = hashlib.sha256(Path('/app/contracts/hyprn-mvp.openapi.yaml').read_bytes()).hexdigest()
    print(json.dumps(dict(password=password, tokens=tokens, assets=assets, api_sha256=api_sha256,
                         origin=values['EXTERNAL_ORIGIN'],
                         identity=identity, ca=ca_bytes.decode())))


def admission(state):
    if state == 'missing':
        (ROOT / 'control/admission.json').unlink()
        return
    identity = json.loads((ROOT / 'control/runtime-identity.json').read_bytes())
    record(ROOT / 'control/admission.json', dict(schema='hyprn-admission/v1', **identity,
          browser=state in ('browser', 'expired'), scientific=False,
          expires_at=int(time.time()) + (-1 if state == 'expired' else 240)))


def serve():
    import copy
    import httpx
    import uvicorn
    from hyprn_mvp_app.assistant.claude import Claude
    from hyprn_mvp_cloud.access import AccessVerifier
    from managed_assistant import MANAGERS
    plan = json.loads((ROOT / 'control/assistant-plan.json').read_bytes())
    jwks = json.loads((ROOT / 'jwks.json').read_bytes())
    def external(request):
        if request.method != 'GET':
            raise AssertionError('Fixture permits no external mutation or model request')
        if request.url.host == 'synthetic.cloudflareaccess.com':
            return httpx.Response(200, json=jwks)
        if request.url.host != 'api.anthropic.com':
            raise AssertionError('Unexpected external fixture destination')
        if request.url.path == '/v1/agents/agent_fixture':
            return httpx.Response(200, json=dict(plan['agent'], id='agent_fixture', version=1))
        if request.url.path == '/v1/environments/environment_fixture':
            value = copy.deepcopy(plan['environment'])
            value['config']['packages'] = {'type': 'packages', **{manager: [] for manager in MANAGERS}}
            return httpx.Response(200, json=dict(value, id='environment_fixture'))
        if request.url.path == '/v1/sessions' and request.url.params.get('include_archived') == 'true':
            return httpx.Response(200, json={'data': [], 'next_page': None})
        raise AssertionError('Unexpected external fixture request')
    original_provider, original_access = Claude.__init__, AccessVerifier.__init__
    def provider(self, key_file, **kwargs):
        original_provider(self, key_file, transport=httpx.MockTransport(external))
    def access(self, issuer, audience, **kwargs):
        original_access(self, issuer, audience, transport=httpx.MockTransport(external))
    Claude.__init__, AccessVerifier.__init__ = provider, access
    from hyprn_mvp_cloud.asgi import from_environment
    app = from_environment()
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='warning', access_log=False,
                ssl_certfile=str(ROOT / 'https.crt'), ssl_keyfile=str(ROOT / 'https.key'))


def request():
    """A bounded HTTPS client with only the fixture CA mounted; no application imports."""
    import base64
    import ssl
    from urllib.error import HTTPError, URLError
    from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

    value = json.load(sys.stdin)
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, file, code, message, headers, new_url):
            return None
    client = build_opener(ProxyHandler({}), NoRedirect(),
        HTTPSHandler(context=ssl.create_default_context(cafile=str(ROOT / 'ca.pem'))))
    call = Request(value['url'], method=value['method'], headers=value['headers'],
                   data=None if value['body'] is None else base64.b64decode(value['body']))
    try:
        try:
            reply = client.open(call, timeout=value['timeout'])
        except HTTPError as error:
            reply = error
        with reply:
            raw = reply.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError('HTTPS fixture response exceeds its bound')
            print(json.dumps(dict(status=reply.status, headers=list(reply.headers.items()),
                                  body=base64.b64encode(raw).decode())))
    except (URLError, ConnectionError, TimeoutError) as error:
        reason = getattr(error, 'reason', error)
        print(json.dumps(dict(connection_unavailable=True,
            reason_type=type(reason).__name__, reason=str(reason)[:512])))


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'seed':
        seed(*sys.argv[2:])
    elif action == 'admission':
        admission(sys.argv[2])
    elif action == 'request':
        request()
    elif action == 'client':
        time.sleep(1800)
    else:
        os.environ.update(json.loads((ROOT / 'environment.json').read_bytes()))
        if action == 'serve':
            serve()
        elif action in ('database', 'database-foreign'):
            if action == 'database-foreign':
                os.environ['HYPRN_MVP_APPLICATION_STORE_ID'] = 'foreign-store'
            from hyprn_mvp_cloud.database_cli import main
            raise SystemExit(main(sys.argv[2:]))
        else:
            raise ValueError('Unknown fixture action')
