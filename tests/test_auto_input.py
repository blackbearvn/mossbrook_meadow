"""Text automation and manual prompts share complete lines from real pipes."""
from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from farmgame.model import Farm
from farmgame.storage import load_game, save_game
from farmgame.terminal import TerminalGame


ROOT = Path(__file__).resolve().parents[1]


class TextAutoInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'farm.json'
        self.output = bytearray()

    def launch(self, farm=None):
        if farm is not None:
            save_game(farm, self.path)
        process = subprocess.Popen(
            [sys.executable, '-u', str(ROOT / 'main.py'), '--text', '--quick',
             '--skip-intro', '--save', str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, cwd=self.directory.name,
        )
        self.addCleanup(self.cleanup_process, process)
        return process

    @staticmethod
    def cleanup_process(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if process.stdin is not None:
            process.stdin.close()
        if process.stdout is not None:
            process.stdout.close()

    def read_until(self, process, predicate, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            ready, _, _ = select.select([process.stdout], [], [],
                                        min(0.05, max(0, deadline - time.monotonic())))
            if ready:
                chunk = os.read(process.stdout.fileno(), 65536)
                self.output.extend(chunk)
                if not chunk:
                    try:
                        process.wait(timeout=min(0.05, max(0, deadline - time.monotonic())))
                    except subprocess.TimeoutExpired:
                        continue
                    break
        return predicate()

    def contains(self, message):
        return ' '.join(message.split()) in ' '.join(
            self.output.decode('utf-8', errors='replace').split())

    def finish(self, process):
        self.assertTrue(self.read_until(process, lambda: process.poll() is not None),
                        self.output.decode('utf-8', errors='replace'))
        self.assertEqual(process.returncode, 0, self.output.decode('utf-8', errors='replace'))
        self.assertNotIn(b'Traceback', self.output)
        self.assertNotIn(b'Fatal Python error', self.output)

    def test_stop_queued_with_menu_is_consumed_while_stdin_pipe_stays_open(self):
        process = self.launch()
        process.stdin.write(b'o\n3\n4\n3\no\n')
        self.assertTrue(self.read_until(process, lambda: self.contains('Đã dừng auto.')),
                        'The already queued stop must work before any additional input')
        stopped = load_game(self.path)
        self.assertEqual(stopped.day, 1)
        process.stdin.write(b'q\n')
        self.finish(process)
        self.assertEqual(load_game(self.path), stopped)
        self.assertTrue(self.contains('Chỉ Toàn bộ mới hoàn tất hướng dẫn đang chạy'))
        self.assertTrue(self.contains('chế độ riêng không tự phân bổ điểm'))

    def test_partial_line_does_not_block_ticks_and_remains_available_until_enter(self):
        process = self.launch()
        process.stdin.write(b'o\n3\n4\n3\n')
        self.assertTrue(self.read_until(process, lambda: self.contains('AUTO: p =')))
        process.stdin.write(b'p')
        def next_day_saved():
            return self.path.exists() and load_game(self.path).day > 1
        self.assertTrue(self.read_until(process, next_day_saved),
                        'An incomplete control line must leave automation ticking')
        process.stdin.write(b'\no\n')
        self.assertTrue(self.read_until(process, lambda: self.contains('Đã dừng auto.')))
        process.stdin.write(b'q\n')
        self.finish(process)
        self.assertTrue(self.contains('Auto tạm dừng.'))

    def test_finite_completion_keeps_next_queued_command_for_manual_menu(self):
        process = self.launch(Farm(area='home', player_x=12, player_y=3))
        process.stdin.write(b'o\n3\n1\n3\n8\nq\n')
        self.finish(process)
        restored = load_game(self.path)
        self.assertEqual((restored.day, restored.coins, restored.energy), (2, 126, 16))
        self.assertTrue(self.contains('AUTO HOÀN TẤT'))

    def test_eof_in_auto_saves_and_exits_without_waiting_for_more_input(self):
        process = self.launch()
        process.stdin.write(b'o\n3\n4\n3\n')
        process.stdin.close()
        self.finish(process)
        self.assertTrue(self.path.exists())
        self.assertGreaterEqual(load_game(self.path).day, 1)

    @unittest.skipUnless(os.name == 'posix', 'SIGINT requires POSIX')
    def test_ctrl_c_during_auto_input_wait_saves_and_exits(self):
        process = self.launch()
        process.stdin.write(b'o\n3\n4\n3\n')
        self.assertTrue(self.read_until(process, lambda: self.contains('AUTO: p =')))
        process.stdin.write(b'p')
        self.assertTrue(self.read_until(process, lambda: load_game(self.path).day > 1))
        process.send_signal(signal.SIGINT)
        self.finish(process)
        self.assertTrue(self.path.exists())
        self.assertGreaterEqual(load_game(self.path).day, 1)

    def test_pending_read_preserves_manual_command_when_final_auto_tick_completes(self):
        from farmgame.automation import AutoOptions
        read_fd, write_fd = os.pipe()
        with os.fdopen(read_fd, 'r', encoding='utf-8') as source, \
                os.fdopen(write_fd, 'w', encoding='utf-8') as commands:
            farm = Farm(area='home', player_x=12, player_y=3)
            game = TerminalGame(farm, self.path, color=False, clear_screen=False)
            self.addCleanup(game._line_input.close)
            with patch('sys.stdin', source), redirect_stdout(StringIO()):
                self.assertIsNone(game.poll_input(0))
                commands.write('8\n')
                commands.flush()
                game.activities.start(AutoOptions(mode='ranch', days=1), speed=2)
                game.activities.run_text_auto()
                self.assertEqual(farm.day, 2)
                self.assertFalse(game.activities.running)
                self.assertEqual(game.ask('Manual command: '), '8')

    def test_manual_input_keeps_mocked_input_and_eof_behavior(self):
        game = TerminalGame(Farm(), self.path, color=False, clear_screen=False)
        self.addCleanup(game._line_input.close)
        with patch('builtins.input', side_effect=['  hello  ', EOFError]), redirect_stdout(StringIO()):
            self.assertEqual(game.ask('Prompt: '), 'hello')
            with self.assertRaises(EOFError):
                game.ask('Next: ')


if __name__ == '__main__':
    unittest.main()
