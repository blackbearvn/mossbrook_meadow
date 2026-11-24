"""Chơi Mossbrook Meadow ngay trong trình duyệt.

Một máy chủ nhỏ (chỉ dùng thư viện chuẩn) giữ một phiên PTY chạy game
và bắc cầu I/O cho giao diện xterm.js: trình duyệt gửi phím qua POST,
lấy dữ liệu màn hình qua long-poll, nên chơi được cả khi game và trình
duyệt khác máy. Mặc định chỉ lắng nghe trên 127.0.0.1; dùng --web-host
để mở cho mạng ngoài (hãy tự cân nhắc bảo mật).
"""

import base64
import fcntl
import json
import os
import pty
import select
import signal
import struct
import sys
import termios
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "web_static"
STATIC_FILES = {
    "/static/xterm.js": "xterm.js",
    "/static/xterm.css": "xterm.css",
    "/static/xterm-addon-fit.js": "xterm-addon-fit.js",
}
GAME_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PORT = 8765
DEFAULT_COLS = 100
DEFAULT_ROWS = 32

try:
    _INDEX_HTML = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
except OSError:  # giao diện web thiếu: báo lỗi khi mở /
    _INDEX_HTML = ""


class PtySession:
    """Một tiến trình game chạy trong PTY, đọc ghi theo lượt.

    Mỗi đối tượng chỉ chạy một lần: để chơi lại, hãy tạo phiên mới qua
    GameHost.restart thay vì gọi spawn lần nữa.
    """

    def __init__(self, argv: list[str], cwd: Path = GAME_ROOT,
                 cols: int = DEFAULT_COLS, rows: int = DEFAULT_ROWS):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._buffer = bytearray()
        self.exited = False
        self.exit_code: int | None = None
        self._pid: int | None = None
        self._master: int | None = None
        self._stopping = False
        self._argv = list(argv)
        self._cwd = cwd
        self._reader: threading.Thread | None = None
        self._spawn(cols, rows)

    # -- vòng đời ---------------------------------------------------------
    def _spawn(self, cols: int, rows: int) -> None:
        master, slave = pty.openpty()
        env = dict(os.environ)
        env.update({"TERM": "xterm-256color", "LANG": "C.UTF-8",
                    "COLUMNS": str(cols), "LINES": str(rows)})
        pid = os.fork()
        if pid == 0:  # con: biến terminal phụ thành stdin/stdout
            os.close(master)
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave, 2)
            if slave > 2:
                os.close(slave)
            try:
                self._resize_fd(slave, cols, rows)
            except OSError:
                pass
            os.chdir(self._cwd)
            os.execve(self._argv[0], self._argv, env)
            os._exit(127)
        os.close(slave)
        self._pid = pid
        self._master = master
        self._resize_fd(master, cols, rows)
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        """Đọc dữ liệu từ PTY vào bộ đệm cho tới khi phiên dừng."""
        try:
            while not self._stopping:
                try:
                    ready, _, _ = select.select([self._master], [], [], 0.2)
                except (OSError, ValueError):
                    break
                if not ready:
                    continue
                try:
                    chunk = os.read(self._master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                with self._condition:
                    self._buffer.extend(chunk)
                    self._condition.notify_all()
        finally:
            self._finish()

    def _finish(self) -> None:
        """Kết thúc phiên: dừng tiến trình con, chốt mã thoát, đóng PTY."""
        with self._condition:
            if self.exited:
                return
            pid = self._pid
            self._pid = None
            master = self._master
            self._master = None
            self.exited = True
        if master is not None:
            try:
                os.close(master)
            except OSError:
                pass
        code = None
        if pid is not None:
            code = -signal.SIGTERM
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    break
                for _ in range(50):
                    done = False
                    try:
                        _, status = os.waitpid(pid, os.WNOHANG)
                        done = pid == 0 or os.WIFSIGNALED(status) or os.WIFEXITED(status)
                        if status:
                            code = (os.WEXITSTATUS(status)
                                    if os.WIFEXITED(status)
                                    else -os.WTERMSIG(status))
                    except ChildProcessError:
                        done = True
                        break
                    if done:
                        break
                    time.sleep(0.02)
                else:
                    continue
                break
        with self._condition:
            self.exit_code = code
            self._condition.notify_all()

    def terminate(self, timeout: float = 3.0) -> None:
        """Dừng phiên hiện tại và dọn dẹp tiến trình con."""
        with self._lock:
            self._stopping = True
        reader = self._reader
        if reader is not None and reader.is_alive():
            reader.join(timeout)
        self._finish()

    # -- I/O --------------------------------------------------------------
    def write(self, data: bytes) -> None:
        with self._lock:
            master, exited = self._master, self.exited
        if exited or master is None:
            raise RuntimeError('Trò chơi đã thoát.')
        try:
            os.write(master, data)
        except OSError as error:
            self._finish()
            raise RuntimeError('Trò chơi đã thoát.') from error

    def resize(self, cols: int, rows: int) -> None:
        with self._lock:
            master = self._master
        if master is not None:
            try:
                self._resize_fd(master, cols, rows)
            except OSError:
                pass

    @staticmethod
    def _resize_fd(fd: int, cols: int, rows: int) -> None:
        winsize = struct.pack("HHHH", max(rows, 2), max(cols, 8), 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    def read_since(self, cursor: int) -> tuple[bytes, int]:
        """Dữ liệu mới từ vị trí cursor, kèm vị trí mới để lần sau."""
        with self._lock:
            start = max(0, min(cursor, len(self._buffer)))
            return bytes(self._buffer[start:]), len(self._buffer)

    def wait_new(self, cursor: int, timeout: float) -> bool:
        """Chờ cho tới khi có dữ liệu mới (long-poll)."""
        deadline = time.monotonic() + max(0.0, min(timeout, 1.0))
        with self._condition:
            while len(self._buffer) <= cursor and not self.exited:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return len(self._buffer) > cursor or self.exited


class GameHost:
    """Giữ phiên game hiện tại và thay phiên mới khi người chơi restart."""

    def __init__(self, argv: list[str], cwd: Path = GAME_ROOT,
                 cols: int = DEFAULT_COLS, rows: int = DEFAULT_ROWS):
        self._argv = list(argv)
        self._cwd = cwd
        self._lock = threading.Lock()
        self._session = PtySession(self._argv, cwd, cols, rows)

    @property
    def session(self) -> PtySession:
        with self._lock:
            return self._session

    def restart(self, cols: int = DEFAULT_COLS, rows: int = DEFAULT_ROWS) -> PtySession:
        with self._lock:
            old = self._session
            old.terminate()
            self._session = PtySession(self._argv, self._cwd, cols, rows)
            return self._session

    def stop(self) -> None:
        with self._lock:
            session = self._session
            self._session = None
        if session is not None:
            session.terminate()


def make_handler(host: GameHost):
    """Đóng gói một GameHost vào các route HTTP."""

    class WebGameHandler(BaseHTTPRequestHandler):
        server_version = "MossbrookWeb/1.0"

        def log_message(self, fmt, *args):  # im lặng, tránh rác khi chơi
            pass

        # -- helpers ------------------------------------------------------
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _read_json(self) -> dict | None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0 or length > 8192:
                return None
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None
            return data if isinstance(data, dict) else None

        # -- routes -------------------------------------------------------
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, _INDEX_HTML.encode("utf-8"),
                           "text/html; charset=utf-8")
                return
            if path in STATIC_FILES:
                target = STATIC_DIR / STATIC_FILES[path]
                try:
                    body = target.read_bytes()
                except OSError:
                    self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                    return
                ctype = ("text/css" if path.endswith(".css")
                         else "application/javascript")
                self._send(HTTPStatus.OK, body, f"{ctype}; charset=utf-8")
                return
            if path == "/api/out":
                query = self.path.split("?", 1)[-1]
                cursor = _query_int(query, "n", 0)
                wait = min(_query_int(query, "wait", 250), 1000) / 1000.0
                session = host.session
                if wait > 0 and session is not None:
                    session.wait_new(cursor, wait)
                if session is None:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE,
                               {"b64": "", "next": 0, "exited": True,
                                "exitCode": None})
                    return
                data, position = session.read_since(cursor)
                self._json(HTTPStatus.OK, {
                    "b64": base64.b64encode(data).decode("ascii"),
                    "next": position,
                    "exited": session.exited,
                    "exitCode": session.exit_code,
                })
                return
            self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            data = self._read_json()
            if path == "/api/keys":
                text = data.get("data") if data else None
                if not isinstance(text, str) or not text or len(text) > 2048:
                    self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
                    return
                session = host.session
                if session is None:
                    self._json(HTTPStatus.CONFLICT, {"ok": False, "exited": True})
                    return
                try:
                    session.write(text.encode("utf-8"))
                except RuntimeError:
                    self._json(HTTPStatus.CONFLICT, {"ok": False, "exited": True})
                    return
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/size":
                try:
                    cols, rows = int(data.get("cols")), int(data.get("rows"))
                except (TypeError, ValueError, AttributeError):
                    self._json(HTTPStatus.BAD_REQUEST, {"ok": False})
                    return
                host.session.resize(max(20, min(cols, 500)), max(6, min(rows, 200)))
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/restart":
                cols = max(20, min(_query_int(self.path, "cols", DEFAULT_COLS), 500))
                rows = max(6, min(_query_int(self.path, "rows", DEFAULT_ROWS), 200))
                try:
                    host.restart(cols, rows)
                except (OSError, RuntimeError) as error:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                               {"ok": False, "error": str(error)})
                    return
                self._json(HTTPStatus.OK, {"ok": True})
                return
            self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

    return WebGameHandler


def _query_int(query: str, key: str, default: int) -> int:
    for part in query.split("&"):
        if part.startswith(f"{key}="):
            raw = part[len(key) + 1:]
            try:
                return max(0, min(int(raw), 10**9))
            except ValueError:
                return default
    return default


def make_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT,
                argv: list[str] | None = None) -> tuple[ThreadingHTTPServer, GameHost]:
    """Tạo máy chủ web kèm một phiên game (chưa chạy chờ kết nối)."""
    if argv is None:
        argv = [sys.executable, str(GAME_ROOT / "main.py"), "--quick"]
    game = GameHost(argv)
    server = ThreadingHTTPServer((host, port), make_handler(game))
    server.daemon_threads = True
    return server, game


def serve(host: str = "127.0.0.1", port: int = DEFAULT_PORT,
          argv: list[str] | None = None) -> None:
    """Chạy máy chủ web cho tới khi Ctrl+C."""
    server, game = make_server(host, port, argv=argv)
    print(f"Mossbrook Meadow trên web: http://{host}:{port}/  (Ctrl+C để dừng)",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        game.stop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chơi Mossbrook Meadow trên web.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    arguments = parser.parse_args()
    serve(arguments.host, arguments.port)
