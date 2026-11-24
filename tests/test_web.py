"""Máy chủ web chơi game: phiên PTY và các route HTTP."""
import base64
import json
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from farmgame.web import (GAME_ROOT, STATIC_DIR, GameHost, PtySession,
                          make_handler)

# Trò chơi giả: đọc từng dòng từ terminal và nhắc lại, đủ để thử I/O PTY.
ECHO_SCRIPT = (
    "import sys\n"
    "print('MOSS-WEB-READY', flush=True)\n"
    "for line in sys.stdin:\n"
    "    sys.stdout.write('echo:' + line.rstrip('\\n') + '\\r\\n')\n"
    "    sys.stdout.flush()\n"
)


def echo_argv():
    return [sys.executable, '-c', ECHO_SCRIPT]


def drain(session, needle, timeout=5.0, cursor=0):
    """Đọc cho tới khi thấy needle trong dữ liệu mới."""
    deadline = time.monotonic() + timeout
    seen = b''
    while time.monotonic() < deadline:
        data, cursor = session.read_since(cursor)
        seen += data
        if needle in seen:
            return seen
        time.sleep(0.05)
    return seen


class PtySessionTests(unittest.TestCase):
    def test_output_streams_and_keys_reach_the_process(self):
        session = PtySession(echo_argv(), cols=80, rows=24)
        try:
            seen = drain(session, b'MOSS-WEB-READY')
            self.assertIn(b'MOSS-WEB-READY', seen)
            session.write(b'lan\r')
            seen = drain(session, b'echo:lan')
            self.assertIn(b'echo:lan', seen)
        finally:
            session.terminate()

    def test_cursor_only_returns_new_bytes(self):
        session = PtySession(echo_argv(), cols=80, rows=24)
        try:
            drain(session, b'MOSS-WEB-READY')
            _, cursor = session.read_since(0)
            session.write(b'a\r')
            drain(session, b'echo:a', cursor=cursor)
            again, _ = session.read_since(cursor)
            self.assertNotIn(b'MOSS-WEB-READY', again)
            self.assertIn(b'echo:a', again)
        finally:
            session.terminate()

    def test_terminate_stops_the_process(self):
        session = PtySession(echo_argv(), cols=80, rows=24)
        drain(session, b'MOSS-WEB-READY')
        session.terminate()
        self.assertTrue(session.exited)
        self.assertLess(session.exit_code, 0)  # bị kết thúc bằng tín hiệu

    def test_long_poll_returns_without_data_after_timeout(self):
        session = PtySession(echo_argv(), cols=80, rows=24)
        try:
            drain(session, b'MOSS-WEB-READY')
            _, cursor = session.read_since(0)
            start = time.monotonic()
            self.assertFalse(session.wait_new(cursor, 0.3))
            self.assertLess(time.monotonic() - start, 1.5)
        finally:
            session.terminate()


class GameHostTests(unittest.TestCase):
    def test_restart_serves_a_fresh_game(self):
        host = GameHost(echo_argv())
        try:
            old = host.session
            drain(old, b'MOSS-WEB-READY')
            fresh = host.restart()
            self.assertIsNot(fresh, old)
            self.assertIs(fresh, host.session)
            seen = drain(fresh, b'MOSS-WEB-READY')
            self.assertIn(b'MOSS-WEB-READY', seen)
        finally:
            host.stop()


class HttpRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = GameHost(echo_argv())
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.host))
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.host.stop()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as res:
            return res.status, res.read(), dict(res.headers)

    def post(self, path, payload):
        request = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=5) as res:
            return res.status, json.loads(res.read().decode('utf-8'))

    def test_index_and_static_assets_are_served(self):
        status, body, headers = self.get('/')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'].split(';')[0], 'text/html')
        self.assertIn(b'xterm.js', body)
        for name in ('xterm.js', 'xterm.css', 'xterm-addon-fit.js'):
            status, body, _ = self.get(f'/static/{name}')
            self.assertEqual(status, 200, name)
            self.assertGreater(len(body), 500, name)
        self.assertTrue((STATIC_DIR / 'index.html').exists())

    def test_keys_write_and_output_long_polls(self):
        status, payload = self.post('/api/keys', {'data': 'hai\r'})
        self.assertEqual(status, 200)
        self.assertTrue(payload['ok'])
        deadline = time.monotonic() + 5.0
        seen = b''
        payload = {'b64': ''}
        while time.monotonic() < deadline:
            status, body, _ = self.get('/api/out?n=0&wait=300')
            payload = json.loads(body.decode('utf-8'))
            self.assertEqual(status, 200)
            seen += base64.b64decode(payload['b64'])
            if b'echo:hai' in seen:
                break
        self.assertIn(b'echo:hai', seen)
        self.assertIn('next', payload)

    def test_size_and_unknown_routes(self):
        status, payload = self.post('/api/size', {'cols': 120, 'rows': 30})
        self.assertEqual(status, 200)
        try:
            self.get('/api/khong-ton-tai')
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 404)
        else:
            self.fail('Route lạ phải trả 404.')

    def test_real_entrypoint_exists_and_web_flag_works(self):
        self.assertTrue((GAME_ROOT / 'main.py').exists())
        result = __import__('subprocess').run(
            [sys.executable, str(GAME_ROOT / 'main.py'), '--help'],
            capture_output=True, text=True, timeout=30)
        self.assertIn('--web', result.stdout)


if __name__ == '__main__':
    unittest.main()
