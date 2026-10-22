"""Bounded Cloudflare Access verification; no session or application authority.

One verifier is shared by a process and closed on shutdown. Call ``verify`` in
a bounded thread pool from async applications: refreshing keys is synchronous.
Only operator configuration determines the HTTPS key endpoint. A failed refresh
does not extend cache life; unknown key IDs share the same refresh cooldown.
"""

from dataclasses import dataclass
import json
from threading import Lock
import time
from urllib.parse import urlsplit

import httpx
import jwt

MAX_TOKEN_BYTES = 16384
MAX_JWKS_BYTES = 65536
MAX_KEYS = 16
KEY_LIFETIME_SECONDS = 300
REFRESH_INTERVAL_SECONDS = 30
FETCH_BUDGET_SECONDS = 5


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    contact: str | None = None


class InvalidAssertion(ValueError):
    """The assertion grants no authority."""


class AccessVerifier:
    """Verify RS256 with the exact configured issuer and application audience."""

    def __init__(self, issuer, audience, *, transport=None, monotonic=None, proxy=None):
        if not isinstance(issuer, str) or not isinstance(audience, str) or not audience.strip():
            raise ValueError('Access issuer and audience are required')
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != 'https'
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or any(char.isspace() for char in issuer)
            or len(issuer) > 2048
            or len(audience) > 1024
        ):
            raise ValueError('Access issuer must be an HTTPS origin')
        # Validate malformed ports now, before creating a network client.
        parsed.port
        if proxy is not None:
            # Only an explicit host-provided private proxy may route key retrieval.
            # Ambient proxy variables and TLS trust remain ignored.
            from ipaddress import ip_address, ip_network
            try:
                endpoint = urlsplit(proxy)
                address = ip_address(endpoint.hostname or '')
                if (endpoint.scheme != 'http' or address.version != 4
                        or not any(address in ip_network(cidr) for cidr in (
                            '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8'))
                        or endpoint.username is not None or endpoint.password is not None
                        or endpoint.path or endpoint.query or endpoint.fragment
                        or not endpoint.port or any(c.isspace() for c in proxy)):
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ValueError('Access proxy must be a private HTTP endpoint') from None
        self._issuer = issuer
        self._audience = audience
        self._url = issuer + '/cdn-cgi/access/certs'
        self._clock = monotonic or time.monotonic
        self._lock = Lock()
        self._keys = {}
        self._expires = 0.0
        self._refresh_after = 0.0
        self._closed = False
        self._client = httpx.Client(
            transport=transport,
            trust_env=False,
            proxy=proxy,
            follow_redirects=False,
            timeout=httpx.Timeout(2.0),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'},
        )

    def verify(self, assertion):
        try:
            if (
                not isinstance(assertion, str)
                or not assertion.isascii()
                or not 0 < len(assertion) <= MAX_TOKEN_BYTES
            ):
                raise ValueError()
            header = jwt.get_unverified_header(assertion)
            kid = header.get('kid')
            if (
                header.get('alg') != 'RS256'
                or not isinstance(kid, str)
                or not 0 < len(kid) <= 256
                or any(name in header for name in ('jku', 'jwk', 'x5u', 'crit', 'b64'))
            ):
                raise ValueError()
            key = self._key(kid)
            claims = jwt.decode(
                assertion,
                key,
                algorithms=['RS256'],
                issuer=self._issuer,
                audience=self._audience,
                options={'require': ['iss', 'aud', 'sub', 'exp', 'iat']},
                leeway=0,
            )
            # JWT libraries accept some coercible dates; identity boundaries do not.
            for name in ('exp', 'iat', 'nbf'):
                if name in claims and (
                    type(claims[name]) is not int or not 0 <= claims[name] < 2**53
                ):
                    raise ValueError()
            if (
                claims['iat'] >= claims['exp']
                or claims.get('nbf', 0) >= claims['exp']
                or not isinstance(claims['sub'], str)
                or not claims['sub'].strip()
                or len(claims['sub']) > 1024
                or claims.get('type', 'app') != 'app'
            ):
                raise ValueError()
            contact = claims.get('email')
            if not isinstance(contact, str) or not 1 <= len(contact) <= 128 or any(
                ord(char) < 33 or ord(char) > 126 for char in contact
            ) or contact.count('@') != 1:
                contact = None
            return VerifiedIdentity(issuer=self._issuer, subject=claims['sub'], contact=contact)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            # Suppress upstream exception text and chains: never expose claims or tokens.
            raise InvalidAssertion('Invalid access assertion') from None

    def _key(self, kid):
        with self._lock:
            if self._closed:
                raise ValueError()
            now = self._clock()
            if now < self._expires and kid in self._keys:
                return self._keys[kid]
            if now >= self._refresh_after:
                self._refresh_after = now + REFRESH_INTERVAL_SECONDS
                try:
                    keys = self._fetch_keys()
                except (
                    httpx.HTTPError,
                    jwt.PyJWTError,
                    ValueError,
                    TypeError,
                    KeyError,
                    OverflowError,
                    RecursionError,
                ):
                    keys = None
                if keys is not None:
                    self._keys = keys
                    self._expires = self._clock() + KEY_LIFETIME_SECONDS
            if self._clock() >= self._expires or kid not in self._keys:
                raise ValueError()
            return self._keys[kid]

    def _fetch_keys(self):
        started = time.monotonic()
        body = bytearray()
        with self._client.stream('GET', self._url) as response:
            if (
                response.status_code != 200
                or response.headers.get('content-encoding', 'identity') != 'identity'
            ):
                raise ValueError()
            length = response.headers.get('content-length')
            if length is not None and (not length.isdecimal() or int(length) > MAX_JWKS_BYTES):
                raise ValueError()
            for chunk in response.iter_bytes():
                if (
                    len(body) + len(chunk) > MAX_JWKS_BYTES
                    or time.monotonic() - started > FETCH_BUDGET_SECONDS
                ):
                    raise ValueError()
                body.extend(chunk)
        if time.monotonic() - started > FETCH_BUDGET_SECONDS:
            raise ValueError()
        document = json.loads(body)
        if not isinstance(document, dict):
            raise ValueError()
        entries = document.get('keys')
        if not isinstance(entries, list) or not 0 < len(entries) <= MAX_KEYS:
            raise ValueError()
        keys = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError()
            kid = entry.get('kid')
            if (
                not isinstance(kid, str)
                or not 0 < len(kid) <= 256
                or kid in keys
                or entry.get('kty') != 'RSA'
                or entry.get('alg') != 'RS256'
                or entry.get('use') != 'sig'
                or entry.get('key_ops', ['verify']) != ['verify']
                or any(field in entry for field in ('d', 'p', 'q', 'dp', 'dq', 'qi', 'oth'))
            ):
                raise ValueError()
            key = jwt.PyJWK.from_dict(entry, algorithm='RS256').key
            if not 2048 <= key.key_size <= 8192:
                raise ValueError()
            keys[kid] = key
        return keys

    def close(self):
        with self._lock:
            self._closed = True
            self._keys.clear()
            self._client.close()
