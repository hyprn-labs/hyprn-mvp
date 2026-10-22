"""Only verified signed assertions produce a stable external identity."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'editions/cloud/src'))
from hyprn_mvp_cloud.access import AccessVerifier, InvalidAssertion

ISSUER = 'https://synthetic.cloudflareaccess.com'
AUDIENCE = 'synthetic-application'


@pytest.fixture(scope='module')
def keys():
    return [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]


def jwk(key, kid='current'):
    return {
        **jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True),
        'kid': kid,
        'use': 'sig',
        'alg': 'RS256',
    }


def token(key, *, kid='current', claims=None, headers=None):
    now = int(time.time())
    payload = dict(
        iss=ISSUER, aud=[AUDIENCE], sub='stable-subject', iat=now - 10, nbf=now - 10, exp=now + 600
    )
    payload.update(claims or {})
    return jwt.encode(payload, key, algorithm='RS256', headers={'kid': kid, **(headers or {})})


class KeyService:
    def __init__(self, keys):
        self.body = {'keys': [jwk(keys[0])]}
        self.status = 200
        self.calls = []
        self.clock = 1000.0
        self.error = None

    def respond(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return httpx.Response(self.status, json=self.body)

    def verifier(self):
        return AccessVerifier(
            ISSUER,
            AUDIENCE,
            transport=httpx.MockTransport(self.respond),
            monotonic=lambda: self.clock,
        )


@pytest.mark.parametrize('proxy', [
    'http://proxy.example:3128', 'http://169.254.169.254:80',
    'http://0.0.0.0:3128', 'http://8.8.8.8:3128',
    'http://user:password@127.0.0.1:3128', 'http://127.0.0.1:3128/path',
    'http://127.0.0.1:3128?x=1', 'http://127.0.0.1:0', '',
])
def test_access_proxy_rejects_ambient_authority_and_nonprivate_destinations(proxy):
    with pytest.raises(ValueError, match='Access proxy'):
        AccessVerifier(ISSUER, AUDIENCE, proxy=proxy)


def test_access_proxy_is_explicit_and_does_not_enable_ambient_tls_trust(monkeypatch):
    captured = {}
    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)
        def close(self):
            pass
    monkeypatch.setattr(httpx, 'Client', Client)
    verifier = AccessVerifier(ISSUER, AUDIENCE, proxy='http://172.29.81.1:3128')
    try:
        assert captured['proxy'] == 'http://172.29.81.1:3128'
        assert captured['trust_env'] is False
        assert captured.get('verify', True) is True
        assert captured['follow_redirects'] is False
    finally:
        verifier.close()


def test_key_retrieval_uses_real_connect_proxy_and_refuses_proxy_failure(keys):
    from socketserver import StreamRequestHandler, ThreadingTCPServer
    from threading import Thread

    observed = []
    class Proxy(StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(2)
            observed.append(self.rfile.readline(4096).decode().strip())
            self.wfile.write(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n')

    with ThreadingTCPServer(('127.0.0.1', 0), Proxy) as proxy:
        thread = Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        verifier = AccessVerifier(ISSUER, AUDIENCE,
                                  proxy=f'http://127.0.0.1:{proxy.server_address[1]}')
        try:
            with pytest.raises(InvalidAssertion):
                verifier.verify(token(keys[0]))
            assert observed == ['CONNECT synthetic.cloudflareaccess.com:443 HTTP/1.1']
        finally:
            verifier.close()
            proxy.shutdown()
            thread.join(timeout=3)


def test_signed_assertion_returns_immutable_issuer_subject(keys):
    service = KeyService(keys)
    verifier = service.verifier()
    try:
        try:
            identity = verifier.verify(token(keys[0]))
        except InvalidAssertion:
            identity = None
        assert identity is not None, 'A correctly signed assertion must produce an identity'
        assert (identity.issuer, identity.subject) == (ISSUER, 'stable-subject')
        with pytest.raises(FrozenInstanceError):
            identity.subject = 'different'
        assert len(service.calls) == 1
    finally:
        verifier.close()


@pytest.mark.parametrize('email,expected', [('member@example.invalid','member@example.invalid'),
    (None,None),('bad\nlabel@example.invalid',None),('a'*129+'@example.invalid',None),(True,None)])
def test_contact_is_optional_display_metadata_only(keys,email,expected):
    verifier=KeyService(keys).verifier()
    try:
        identity=verifier.verify(token(keys[0],claims={'email':email}))
        assert identity.subject=='stable-subject'
        assert identity.contact==expected
    finally:verifier.close()


@pytest.mark.parametrize(
    'claims',
    [
        {'iss': ISSUER + '/wrong'},
        {'iss': ISSUER + '/'},
        {'aud': ['other']},
        {'exp': 1},
        {'exp': None},
        {'exp': True},
        {'exp': '9999999999'},
        {'exp': float('inf')},
        {'exp': float('nan')},
        {'exp': 2**53},
        {'nbf': 9999999999},
        {'nbf': None},
        {'nbf': '1'},
        {'nbf': True},
        {'iat': 9999999999},
        {'iat': None},
        {'iat': '1'},
        {'iat': True},
        {'sub': ''},
        {'sub': '   '},
        {'sub': None},
        {'sub': 4},
        {'type': 'org'},
    ],
)
def test_invalid_claims_never_produce_identity(keys, claims):
    verifier = KeyService(keys).verifier()
    try:
        with pytest.raises(InvalidAssertion, match='Invalid access assertion'):
            verifier.verify(token(keys[0], claims=claims))
    finally:
        verifier.close()


@pytest.mark.parametrize('missing', ['iss', 'aud', 'sub', 'exp', 'iat'])
def test_required_claims_cannot_be_omitted(keys, missing):
    claims = jwt.decode(token(keys[0]), options={'verify_signature': False})
    del claims[missing]
    assertion = jwt.encode(claims, keys[0], algorithm='RS256', headers={'kid': 'current'})
    verifier = KeyService(keys).verifier()
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(assertion)
    finally:
        verifier.close()


@pytest.mark.parametrize('assertion', [None, '', 'not-a-jwt', 'x' * 16385, b'bytes'])
def test_missing_or_malformed_assertions_do_not_fetch_keys(keys, assertion):
    service = KeyService(keys)
    verifier = service.verifier()
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(assertion)
        assert service.calls == []
    finally:
        verifier.close()


def test_signature_and_algorithm_are_verified(keys):
    verifier = KeyService(keys).verifier()
    try:
        for assertion in (
            token(keys[1]),
            jwt.encode({'sub': 'forged'}, 'x' * 64, algorithm='HS256', headers={'kid': 'current'}),
            jwt.encode({'sub': 'forged'}, '', algorithm='none'),
        ):
            with pytest.raises(InvalidAssertion):
                verifier.verify(assertion)
    finally:
        verifier.close()


def test_unverified_key_urls_and_critical_headers_grant_no_authority(keys):
    service = KeyService(keys)
    verifier = service.verifier()
    try:
        for headers in (
            {'jku': 'https://attacker.invalid/keys'},
            {'jwk': jwk(keys[1])},
            {'x5u': 'https://attacker.invalid/cert'},
            {'crit': ['unknown']},
            {'kid': 'x' * 257},
        ):
            with pytest.raises(InvalidAssertion):
                verifier.verify(token(keys[0], headers=headers))
        assert service.calls == []
    finally:
        verifier.close()


def test_rotation_unknown_key_stream_and_concurrency_share_refresh_budget(keys):
    service = KeyService(keys)
    verifier = service.verifier()
    try:
        assertion = token(keys[0])
        with ThreadPoolExecutor(max_workers=8) as pool:
            identities = list(pool.map(verifier.verify, [assertion] * 32))
        assert all(identity.subject == 'stable-subject' for identity in identities)
        assert len(service.calls) == 1
        for i in range(100):
            with pytest.raises(InvalidAssertion):
                verifier.verify(token(keys[1], kid=f'unknown-{i}'))
        assert len(service.calls) == 1
        service.body = {'keys': [jwk(keys[1], 'rotated')]}
        service.clock += 31
        assert verifier.verify(token(keys[1], kid='rotated')).subject == 'stable-subject'
        with pytest.raises(InvalidAssertion):
            verifier.verify(assertion)
        assert len(service.calls) == 2
    finally:
        verifier.close()


def test_outage_cannot_extend_cached_key_lifetime(keys):
    service = KeyService(keys)
    verifier = service.verifier()
    try:
        assertion = token(keys[0])
        verifier.verify(assertion)
        service.status = 503
        service.clock += 31
        with pytest.raises(InvalidAssertion):
            verifier.verify(token(keys[1], kid='rotated'))
        assert verifier.verify(assertion).subject == 'stable-subject'
        service.clock += 301
        for _ in range(10):
            with pytest.raises(InvalidAssertion):
                verifier.verify(assertion)
        assert len(service.calls) == 3
    finally:
        verifier.close()


@pytest.mark.parametrize(
    'body',
    [
        None,
        {},
        {'keys': []},
        {'keys': 'wrong'},
        {'keys': [{}]},
        {'keys': [{'kid': 'current'}] * 17},
        {'keys': [], 'padding': 'x' * 65537},
    ],
)
def test_malformed_or_oversized_keys_fail_closed(keys, body):
    service = KeyService(keys)
    service.body = body
    verifier = service.verifier()
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(token(keys[0]))
    finally:
        verifier.close()


def test_duplicate_key_identifiers_are_ambiguous(keys):
    service = KeyService(keys)
    service.body = {'keys': [jwk(keys[0]), jwk(keys[1])]}
    verifier = service.verifier()
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(token(keys[0]))
    finally:
        verifier.close()


def test_transport_failure_has_no_token_or_claim_details(keys, caplog):
    service = KeyService(keys)
    service.error = httpx.ReadTimeout('upstream unavailable')
    verifier = service.verifier()
    assertion = token(keys[0])
    try:
        with pytest.raises(InvalidAssertion) as error:
            verifier.verify(assertion)
        assert str(error.value) == 'Invalid access assertion'
        assert assertion not in caplog.text
        assert 'stable-subject' not in caplog.text
    finally:
        verifier.close()


@pytest.mark.parametrize(
    'issuer,audience',
    [
        ('', AUDIENCE),
        ('http://team.invalid', AUDIENCE),
        ('https://user:pass@team.invalid', AUDIENCE),
        (ISSUER + '?x=1', AUDIENCE),
        (ISSUER + '/path', AUDIENCE),
        (ISSUER, ''),
        (ISSUER, ['aud']),
    ],
)
def test_invalid_operator_configuration_is_rejected(issuer, audience):
    with pytest.raises(ValueError):
        AccessVerifier(issuer, audience)


def test_optional_not_before_and_audience_membership_follow_provider_tokens(keys):
    claims = jwt.decode(token(keys[0]), options={'verify_signature': False})
    del claims['nbf']
    claims['aud'] = ['another-application', AUDIENCE]
    assertion = jwt.encode(claims, keys[0], algorithm='RS256', headers={'kid': 'current'})
    verifier = KeyService(keys).verifier()
    try:
        assert verifier.verify(assertion).subject == 'stable-subject'
    finally:
        verifier.close()


@pytest.mark.parametrize(
    'change',
    [
        {'alg': 'HS256'},
        {'use': 'enc'},
        {'key_ops': ['sign']},
        {'d': 'private'},
        {'n': '!malformed'},
        {'kty': 'oct'},
        {'kid': ''},
    ],
)
def test_keys_have_only_approved_public_signing_properties(keys, change):
    service = KeyService(keys)
    service.body = {'keys': [{**jwk(keys[0]), **change}]}
    verifier = service.verifier()
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(token(keys[0]))
    finally:
        verifier.close()


def test_weak_rsa_keys_are_not_trusted(keys):
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    service = KeyService(keys)
    service.body = {'keys': [jwk(weak)]}
    verifier = service.verifier()
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(token(keys[0]))
    finally:
        verifier.close()


@pytest.mark.parametrize(
    'response',
    [
        httpx.Response(302, headers={'location': 'https://attacker.invalid/keys'}),
        httpx.Response(503),
        httpx.Response(200, content=b'not JSON'),
        httpx.Response(200, content=b'{"keys": [', headers={'content-length': 'invalid'}),
        httpx.Response(200, content=b'{}', headers={'content-encoding': 'unsupported'}),
    ],
)
def test_unusable_responses_fail_closed_without_retry_or_redirect(keys, response):
    calls = []

    def respond(request):
        calls.append(request)
        return response

    verifier = AccessVerifier(ISSUER, AUDIENCE, transport=httpx.MockTransport(respond))
    try:
        for _ in range(10):
            with pytest.raises(InvalidAssertion):
                verifier.verify(token(keys[0]))
        assert len(calls) == 1
        request = calls[0]
        assert str(request.url) == ISSUER + '/cdn-cgi/access/certs'
        assert request.extensions['timeout'] == dict(connect=2, read=2, write=2, pool=2)
        assert request.headers['accept-encoding'] == 'identity'
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
    finally:
        verifier.close()


def test_streamed_body_size_is_bounded_without_a_length_header(keys):
    class Body(httpx.SyncByteStream):
        def __iter__(self):
            yield b' ' * 65536
            yield b' '
            pytest.fail('Oversized response must stop reading the stream')

    verifier = AccessVerifier(
        ISSUER,
        AUDIENCE,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Body())),
    )
    try:
        with pytest.raises(InvalidAssertion):
            verifier.verify(token(keys[0]))
    finally:
        verifier.close()


def test_process_environment_cannot_supply_proxy_or_tls_trust(monkeypatch, keys):
    # A nonexistent ambient trust file would make Client creation fail if inherited.
    monkeypatch.setenv('SSL_CERT_FILE', str(Path('nonexistent-ambient-ca.pem')))
    monkeypatch.setenv('HTTPS_PROXY', 'http://ambient-user:ambient-password@127.0.0.1:1')
    service = KeyService(keys)
    verifier = service.verifier()
    try:
        assert verifier.verify(token(keys[0])).subject == 'stable-subject'
        assert 'proxy-authorization' not in service.calls[0].headers
    finally:
        verifier.close()


def test_closed_verifier_never_grants_an_identity(keys):
    verifier = KeyService(keys).verifier()
    verifier.verify(token(keys[0]))
    verifier.close()
    with pytest.raises(InvalidAssertion):
        verifier.verify(token(keys[0]))
