"""The local helper uses one ordinary login and never repeats an uncertain mutation."""

import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import live_fence  # noqa: E402
import scoped_fixture  # noqa: E402
from tools.local_api import ClientError, LIMIT, LocalApi, main, password_from_file  # noqa: E402

setUpModule, tearDownModule = live_fence.unittest_module_hooks('baseline')


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        observed = self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                self.handle_request()

            def do_POST(self):
                self.handle_request()

            def do_PATCH(self):
                self.handle_request()

            def handle_request(self):
                raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                body = json.loads(raw) if raw else None
                observed.append((self.command, self.path, dict(self.headers), body))
                if self.path == '/api/1/disconnect':
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                status = 200
                response = {'data': {'study_id': 'created-study'}}
                if self.path == '/api/1/session':
                    if body != {'username': 'owner', 'password': 'test owner password'}:
                        status = 401
                    response = {'data': {'csrf_token': 'test-csrf-value'}}
                elif self.path == '/api/1/redirect':
                    status = 307
                elif self.path == '/api/1/forbidden':
                    status = 403
                    response = {'error': {'code': 'forbidden'}}
                elif self.path == '/api/1/echo':
                    response = {'data': ['test-cookie-value', 'test-csrf-value']}
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                if self.path == '/api/1/session':
                    self.send_header(
                        'Set-Cookie', 'hyprn_mvp_session=test-cookie-value; Path=/api/1'
                    )
                if status == 307:
                    self.send_header('Location', 'http://192.0.2.1/api/1/elsewhere')
                encoded = json.dumps(response).encode()
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.client = LocalApi(self.origin)
        self.client.login('owner', 'test owner password')

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_create_read_edit_share_ordinary_cookie_and_csrf(self):
        for command in (
            {'method': 'POST', 'path': '/api/1/studies', 'body': {'name': 'Fuel comparison'}},
            {'method': 'GET', 'path': '/api/1/studies/created-study'},
            {'method': 'PATCH', 'path': '/api/1/studies/created-study', 'body': {'revision': 1}},
            {'path': '/api/1/commands/recorded-command'},
        ):
            self.assertEqual(self.client.request(command)['status'], 200)
        self.assertEqual(len(self.requests), 5)
        for method, _, headers, _ in self.requests[1:]:
            self.assertEqual(headers['Cookie'], 'hyprn_mvp_session=test-cookie-value')
            self.assertEqual(headers['Origin'], self.origin)
            self.assertEqual(
                headers.get('X-CSRF-Token'), None if method == 'GET' else 'test-csrf-value'
            )

    def test_transport_failure_never_repeats_mutation(self):
        with self.assertRaisesRegex(ClientError, 'no retry'):
            self.client.request({'method': 'POST', 'path': '/api/1/disconnect', 'body': {}})
        self.assertEqual(sum(path == '/api/1/disconnect' for _, path, _, _ in self.requests), 1)
        self.assertEqual(
            self.client.request({'path': '/api/1/commands/known-command'})['status'], 200
        )

    def test_status_shortcut_reads_twenty_runs_in_one_public_request(self):
        study_id, run_ids = str(uuid4()), [str(uuid4()) for _ in range(20)]
        result = self.client.request(
            {'operation': 'run_status', 'study_id': study_id, 'run_ids': run_ids}
        )
        self.assertEqual(result, {'status': 200, 'body': {'data': {'study_id': 'created-study'}}})
        self.assertEqual(len(self.requests), 2)
        method, path, headers, body = self.requests[-1]
        self.assertEqual(method, 'GET')
        self.assertEqual(
            path,
            f'/api/1/studies/{study_id}/run-status?' + '&'.join('run_id=' + r for r in run_ids),
        )
        self.assertIsNone(body)
        self.assertNotIn('X-CSRF-Token', headers)

    def test_status_shortcut_rejects_invalid_batches_before_sending(self):
        study_id, run_id = str(uuid4()), str(uuid4())
        for ids in ([], [run_id] * 21, [run_id, run_id], run_id, [None], ['../runs']):
            with self.subTest(ids=ids), self.assertRaises(ClientError):
                self.client.run_status(study_id, ids)
        for invalid in ('../studies', None, 'AAAAAAAA-AAAA-4AAA-AAAA-AAAAAAAAAAAA'):
            with self.subTest(study_id=invalid), self.assertRaises(ClientError):
                self.client.run_status(invalid, [run_id])
        with self.assertRaises(ClientError):
            self.client.request(
                {'operation': 'run_status', 'study_id': study_id, 'run_ids': [run_id], 'body': {}}
            )
        self.assertEqual(len(self.requests), 1)

    def test_json_lines_accept_status_shortcut_without_changing_the_response(self):
        study_id, run_id = str(uuid4()), str(uuid4())
        command = {'operation': 'run_status', 'study_id': study_id, 'run_ids': [run_id]}
        output = io.StringIO()
        with (
            patch('sys.stdin', io.StringIO('test owner password\n' + json.dumps(command) + '\n')),
            patch('sys.stdout', output),
        ):
            self.assertEqual(main(['--origin', self.origin, '--username', 'owner']), 0)
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(
            lines,
            [{'ready': True}, {'status': 200, 'body': {'data': {'study_id': 'created-study'}}}],
        )

    def test_redirect_and_authorization_errors_are_returned_without_followup(self):
        self.assertEqual(self.client.request({'path': '/api/1/redirect'})['status'], 307)
        result = self.client.request({'path': '/api/1/forbidden'})
        self.assertEqual(result, {'status': 403, 'body': {'error': {'code': 'forbidden'}}})
        self.assertEqual(len(self.requests), 3)

    def test_origin_and_paths_cannot_leave_public_loopback_api(self):
        for origin in (
            'https://127.0.0.1:9',
            'http://example.com:9',
            'http://127.0.0.1',
            'http://user@127.0.0.1:9',
            'http://127.0.0.1:9/base',
        ):
            with self.subTest(origin=origin), self.assertRaises(ClientError):
                LocalApi(origin)
        for path in (
            'http://127.0.0.1:9/api/1/studies',
            '/modeling/1/models',
            '/api/1/../session',
            '/api/1/%2e%2e/session',
            '/api/1/%252e%252e/session',
            '/api/1/studies#fragment',
            '/api/1/session',
            '/api/1/studies\r\nX: secret',
        ):
            with self.subTest(path=path), self.assertRaises(ClientError):
                self.client.request({'path': path})
        self.assertEqual(len(self.requests), 1)

    def test_body_bounds_and_nonfinite_values_refuse_before_send(self):
        for body in ({'value': float('nan')}, {'text': 'a' * LIMIT}):
            with self.assertRaises(ClientError):
                self.client.request({'method': 'POST', 'path': '/api/1/studies', 'body': body})
        self.assertEqual(len(self.requests), 1)

    def test_json_lines_keep_session_and_never_print_secrets(self):
        commands = (
            'test owner password\n'
            + '\n'.join(
                json.dumps(command)
                for command in (
                    {
                        'method': 'POST',
                        'path': '/api/1/studies',
                        'body': {'name': 'Fuel comparison'},
                    },
                    {'path': '/api/1/studies/created-study'},
                    {'path': '/api/1/echo'},
                )
            )
            + '\n'
        )
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(commands)), patch('sys.stdout', output):
            self.assertEqual(main(['--origin', self.origin, '--username', 'owner']), 0)
        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(lines[0], {'ready': True})
        self.assertEqual(len(lines), 4)
        for secret in ('test owner password', 'test-cookie-value', 'test-csrf-value'):
            self.assertNotIn(secret, output.getvalue())

    def test_password_file_requires_owned_regular_0600_file(self):
        scope = scoped_fixture.scope_from_environment()
        with tempfile.TemporaryDirectory(dir=scope.root / 'tmp') as folder:
            path = Path(folder) / 'owner-password'
            path.write_text('test owner password\n')
            path.chmod(0o600)
            self.assertEqual(password_from_file(path), 'test owner password')
            path.chmod(0o644)
            with self.assertRaises(ClientError):
                password_from_file(path)
            link = Path(folder) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                password_from_file(link)
