"""Owner-operated JSON-lines client of the local public API; credentials stay in memory."""

import argparse
import http.client
from http.cookies import CookieError, SimpleCookie
import ipaddress
import json
import math
import os
from pathlib import Path
import stat
import sys
from urllib.parse import unquote, urlsplit

COOKIE = 'hyprn_mvp_session'
LIMIT = 4 * 1024 * 1024


class ClientError(Exception):
    """A safe diagnostic that never includes request bodies or credentials."""


def origin_address(origin):
    try:
        parsed = urlsplit(origin)
        valid = (
            parsed.scheme == 'http'
            and ipaddress.ip_address(parsed.hostname).is_loopback
            and parsed.port is not None
            and parsed.port > 0
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        )
        if valid:
            return parsed.hostname, parsed.port
    except (ValueError, TypeError):
        pass
    raise ClientError('Use an HTTP loopback IP origin with an explicit port and no path.')


def api_path(path):
    if not isinstance(path, str) or not path.isascii():
        raise ClientError('Use an ASCII /api/1/ path.')
    parsed = urlsplit(path)
    decoded = unquote(parsed.path)
    if (
        not path.startswith('/api/1/')
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or any(ord(char) < 33 or ord(char) == 127 for char in path)
        or '\\' in decoded
        or '%' in decoded
        or any(part in {'.', '..'} for part in decoded.split('/'))
    ):
        raise ClientError('Use a /api/1/ path without traversal, fragments or control characters.')
    if decoded.rstrip('/') == '/api/1/session':
        raise ClientError('The helper owns login; session requests are not exposed.')
    return path


class LocalApi:
    def __init__(self, origin, timeout=45):
        self.host, self.port = origin_address(origin)
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ClientError('Timeout must be greater than zero and at most 120 seconds.')
        self.origin, self.timeout = origin, timeout
        self.cookie = self.csrf = None

    def _send(self, method, path, body):
        headers = {'Origin': self.origin, 'Accept': 'application/json'}
        if self.cookie:
            headers['Cookie'] = COOKIE + '=' + self.cookie
        if self.csrf and method != 'GET':
            headers['X-CSRF-Token'] = self.csrf
        encoded = None
        if body is not None:
            try:
                encoded = json.dumps(body, allow_nan=False, ensure_ascii=False).encode('utf-8')
            except (ValueError, TypeError, UnicodeError):
                raise ClientError('Request body must be finite JSON.') from None
            if len(encoded) > LIMIT:
                raise ClientError('Request body exceeds the 4 MiB limit.')
            headers['Content-Type'] = 'application/json'
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request(method, path, body=encoded, headers=headers)
            response = connection.getresponse()
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ClientError('Response exceeds 4 MiB; mutation outcome may be uncertain.')
            try:
                result = json.loads(raw) if raw else None
            except (ValueError, UnicodeError):
                raise ClientError(
                    'Response is not JSON; mutation outcome may be uncertain.'
                ) from None
            return response.status, result, response.getheader('Set-Cookie')
        except (OSError, http.client.HTTPException):
            raise ClientError(
                'Transport failed; no retry was made. Read the command receipt before retrying '
                'any mutation whose outcome is uncertain.'
            ) from None
        finally:
            connection.close()

    def login(self, username, password):
        status, body, cookie_header = self._send(
            'POST', '/api/1/session', {'username': username, 'password': password}
        )
        try:
            cookie = SimpleCookie(cookie_header or '')
            token = cookie[COOKIE].value
            csrf = body['data']['csrf_token']
            if status != 200 or not token or not isinstance(csrf, str) or not csrf:
                raise ValueError
        except (CookieError, KeyError, TypeError, ValueError):
            raise ClientError(
                f'Login failed (HTTP {status}); no response credentials printed.'
            ) from None
        self.cookie, self.csrf = token, csrf

    def request(self, command):
        if not isinstance(command, dict) or set(command) - {'method', 'path', 'body'}:
            raise ClientError('Expected an object with method, path and optional body only.')
        method = command.get('method', 'GET')
        if method not in {'GET', 'POST', 'PUT', 'PATCH'}:
            raise ClientError(
                'Supported methods: GET, POST, PUT, PATCH. Deletion is not authorized.'
            )
        path = api_path(command.get('path'))
        if not self.cookie:
            raise ClientError('Login is required.')
        status, body, _ = self._send(method, path, command.get('body'))
        return {'status': status, 'body': body}


def password_from_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != os.getuid()
        ):
            raise ClientError('Password file must be an owned regular file with mode 0600.')
        raw = stream.read(4097)
        if len(raw) > 4096:
            raise ClientError('Password file is too large.')
        return raw.decode('utf-8').rstrip('\r\n')


def emit(value, client):
    text = json.dumps(value, ensure_ascii=True, allow_nan=False)
    for secret in (client.cookie, client.csrf):
        if secret:
            text = text.replace(json.dumps(secret)[1:-1], '[redacted]')
    print(text, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password-file', type=Path)
    parser.add_argument('--timeout', type=float, default=45)
    args = parser.parse_args(argv)
    try:
        client = LocalApi(args.origin, args.timeout)
        if args.password_file:
            password = password_from_file(args.password_file)
        else:
            if sys.stdin.isatty():
                raise ClientError(
                    'Use --password-file or a private pipe; do not type secrets in a PTY.'
                )
            password = sys.stdin.readline(4097).rstrip('\r\n')
            if len(password) > 4096:
                raise ClientError('Password line is too large.')
        client.login(args.username, password)
        del password
    except (ClientError, OSError, UnicodeError):
        print(
            json.dumps({'error': 'Login failed; check origin, credentials and password-file mode.'})
        )
        return 1
    emit({'ready': True}, client)
    while line := sys.stdin.readline(LIMIT + 1):
        if len(line.encode('utf-8')) > LIMIT:
            emit({'error': 'Input line exceeds 4 MiB; closing without sending it.'}, client)
            return 1
        try:
            command = json.loads(line)
            result = client.request(command)
        except ClientError as error:
            result = {'error': str(error)}
        except (ValueError, TypeError, RecursionError):
            result = {'error': 'Invalid JSON request.'}
        emit(result, client)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
