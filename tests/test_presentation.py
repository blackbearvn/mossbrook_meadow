"""Deterministic animation and input tests for the in-game introduction."""
import io
import math
import os
import types
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from farmgame import presentation


class TypewriterTests(unittest.TestCase):
    def test_fractional_progress_and_reveal(self):
        writer = presentation.Typewriter('abcd', 2)
        self.assertEqual(writer.visible, '')
        self.assertFalse(writer.done)
        self.assertEqual(writer.advance(.25), '')
        self.assertEqual(writer.advance(.25), 'a')
        self.assertEqual(writer.advance(.5), 'ab')
        self.assertEqual(writer.reveal(), 'abcd')
        self.assertTrue(writer.done)
        self.assertEqual(writer.advance(100), 'abcd')

    def test_combining_marks_stay_with_base(self):
        writer = presentation.Typewriter('Bi\u0300nh', 1)
        self.assertEqual(writer.advance(2), 'Bi\u0300')
        self.assertEqual(writer.advance(1), 'Bi\u0300n')

    def test_empty_and_invalid_timing(self):
        self.assertTrue(presentation.Typewriter('').done)
        for speed in (0, -1, math.inf, math.nan):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                presentation.Typewriter('a', speed)
        for dt in (-1, math.inf, math.nan):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                presentation.Typewriter('a').advance(dt)


class FakeScreen:
    def __init__(self):
        self.size = (8, 24)
        self.timeouts = []

    def getmaxyx(self):
        return self.size

    def timeout(self, value):
        self.timeouts.append(value)


class FakeUI:
    def __init__(self, keys):
        self.keys = iter(keys)
        self.frames = []
        self._screen = FakeScreen()
        self._curses = types.SimpleNamespace(KEY_ENTER=100, KEY_BACKSPACE=101,
            KEY_UP=102, KEY_DOWN=103, KEY_PPAGE=104, KEY_NPAGE=105, KEY_RESIZE=106)

    def key(self):
        key = next(self.keys)
        if isinstance(key, BaseException):
            raise key
        if callable(key):
            return key(self)
        return key

    def paint(self, title, lines, footer, selected=None, scroll=0):
        room = max(1, self._screen.size[0] - 5)
        scroll = min(max(0, scroll), max(0, len(lines) - room))
        self.frames.append((title, list(lines), scroll))
        return room, scroll


class CursesIntroTests(unittest.TestCase):
    def run_intro(self, ui, pages=None, step=0):
        clock = iter(n * step for n in range(1000))
        with patch.object(presentation, 'intro_pages', return_value=pages or [('A', 'abcdef'), ('B', 'second')]), patch.object(presentation.time, 'monotonic', side_effect=lambda: next(clock)):
            return presentation.play_curses_intro(ui, object())

    def test_enter_reveals_then_advances(self):
        ui = FakeUI(['\n', '\n', 's'])
        self.assertTrue(self.run_intro(ui))
        self.assertEqual([frame[0] for frame in ui.frames], ['A · 1/2', 'A · 1/2', 'B · 2/2'])
        self.assertEqual(''.join(ui.frames[0][1]), '')
        self.assertEqual(''.join(ui.frames[1][1]), 'abcdef')
        self.assertEqual(ui._screen.timeouts, [25, 100])

    def test_skip_while_typing_and_interrupt_restore_timeout(self):
        ui = FakeUI(['Q'])
        self.assertTrue(self.run_intro(ui))
        self.assertEqual(len(ui.frames), 1)
        for error in (KeyboardInterrupt(), EOFError()):
            ui = FakeUI([error])
            with self.assertRaises(type(error)):
                self.run_intro(ui)
            self.assertEqual(ui._screen.timeouts, [25, 100])

    def test_elapsed_time_changes_prefix_without_changing_page(self):
        ui = FakeUI([None, None, None, 's'])
        self.run_intro(ui, [('A', 'a' * 100)], step=.1)
        lengths = [len(''.join(frame[1])) for frame in ui.frames]
        self.assertGreater(lengths[-1], lengths[0])
        self.assertLess(lengths[-1], 100)
        self.assertEqual({frame[0] for frame in ui.frames}, {'A · 1/1'})

    def test_previous_resize_and_manual_scroll_keep_complete_content(self):
        def resize(ui):
            ui._screen.size = (8, 12)
            return ui._curses.KEY_RESIZE
        body = '\n'.join(f'line {n}' for n in range(12))
        ui = FakeUI([' ', 102, resize, ' ', ' ', 'p', 'q'])
        self.run_intro(ui, [('A', body), ('B', 'next')])
        self.assertGreater(ui.frames[1][2], 0)  # reveal follows the tail
        self.assertEqual(ui.frames[2][2], ui.frames[1][2] - 1)
        self.assertEqual(ui.frames[-1][0], 'A · 1/2')
        self.assertIn('line11', ''.join(ui.frames[-1][1]).replace(' ', ''))


class TextIntroTests(unittest.TestCase):
    def test_pipe_pages_are_instant_and_keep_previous_commands(self):
        output = io.StringIO()
        with patch.object(presentation, 'intro_pages', return_value=[('A', 'first'), ('B', 'second')]), patch.object(presentation.sys, 'stdin', io.StringIO()), patch.object(presentation.sys, 'stdout', output), patch('builtins.input', side_effect=['', 'p', 's']):
            self.assertTrue(presentation.play_text_intro(object(), object()))
        self.assertEqual(output.getvalue().count('first'), 2)
        self.assertIn('second', output.getvalue())

    def test_tty_progress_reveal_and_skip_restore_input(self):
        output = io.StringIO()
        output.isatty = lambda: True
        stdin = io.StringIO()
        stdin.isatty = lambda: True
        restored = []
        snapshots = []
        @contextmanager
        def keys():
            def read(timeout):
                snapshots.append(output.getvalue().rsplit('\n', 1)[-1])
                return next(events)
            try:
                yield read
            finally:
                restored.append(True)
        events = iter([None, ' ', 's'])
        clock = iter([0, .05, .1, .15, .2, .25, .3, .35])
        with patch.object(presentation, 'intro_pages', return_value=[('A', 'abcdefghijklmno')]), patch.object(presentation.sys, 'stdin', stdin), patch.object(presentation.sys, 'stdout', output), patch.object(presentation, '_terminal_keys', keys), patch.object(presentation.time, 'monotonic', side_effect=lambda: next(clock)):
            self.assertTrue(presentation.play_text_intro(object(), object()))
        self.assertIn('abcdefghijklmno', output.getvalue())
        self.assertEqual(snapshots[0], 'a')
        self.assertEqual(snapshots[1], 'abc')
        self.assertEqual(snapshots[2], 'abcdefghijklmno')
        self.assertEqual(restored, [True])

    def test_tty_interrupt_propagates_and_restores_input(self):
        stdin = io.StringIO()
        stdin.isatty = lambda: True
        restored = []
        @contextmanager
        def keys():
            def read(timeout):
                raise KeyboardInterrupt
            try:
                yield read
            finally:
                restored.append(True)
        output = io.StringIO()
        output.isatty = lambda: True
        with patch.object(presentation, 'intro_pages', return_value=[('A', 'text')]), patch.object(presentation.sys, 'stdin', stdin), patch.object(presentation.sys, 'stdout', output), patch.object(presentation, '_terminal_keys', keys):
            with self.assertRaises(KeyboardInterrupt):
                presentation.play_text_intro(object(), object())
        self.assertEqual(restored, [True])

    def test_redirected_output_is_instant_even_with_tty_input(self):
        stdin = io.StringIO()
        stdin.isatty = lambda: True
        output = io.StringIO()
        with patch.object(presentation, 'intro_pages', return_value=[('A', 'complete')]), patch.object(presentation.sys, 'stdin', stdin), patch.object(presentation.sys, 'stdout', output), patch('builtins.input', return_value='s'), patch.object(presentation, '_terminal_keys', side_effect=AssertionError('must not animate redirected output')):
            self.assertTrue(presentation.play_text_intro(object(), object()))
        self.assertIn('complete', output.getvalue())

    @unittest.skipIf(os.name == 'nt', 'Unix terminal input mode')
    def test_real_terminal_mode_is_nonblocking_and_restored_after_interrupt(self):
        import pty
        import termios
        master, slave = pty.openpty()
        try:
            with os.fdopen(slave, 'r') as terminal:
                original = termios.tcgetattr(terminal.fileno())
                with patch.object(presentation.sys, 'stdin', terminal):
                    with self.assertRaises(KeyboardInterrupt):
                        with presentation._terminal_keys() as read:
                            current = termios.tcgetattr(terminal.fileno())
                            self.assertFalse(current[3] & termios.ICANON)
                            self.assertFalse(current[3] & termios.ECHO)
                            self.assertIsNone(read(0))
                            os.write(master, b'q')
                            self.assertEqual(read(.1), 'q')
                            raise KeyboardInterrupt
                self.assertEqual(termios.tcgetattr(terminal.fileno()), original)
        finally:
            os.close(master)

    @unittest.skipIf(os.name == 'nt', 'Unix escape sequences')
    def test_terminal_decodes_arrow_and_pages_without_losing_next_key(self):
        import pty
        master, slave = pty.openpty()
        try:
            with os.fdopen(slave, 'r') as terminal, patch.object(presentation.sys, 'stdin', terminal):
                with presentation._terminal_keys() as read:
                    os.write(master, b'\x1b[A\x1b[6~s')
                    self.assertEqual(read(.1), 'up')
                    self.assertEqual(read(.1), 'page_down')
                    self.assertEqual(read(.1), 's')
                    os.write(master, b'\x1bx')
                    self.assertEqual(read(.1), '\x1b')
                    self.assertEqual(read(.1), 'x')
                    os.write(master, b'\x1b')
                    self.assertEqual(read(.1), '\x1b')
        finally:
            os.close(master)

    @unittest.skipIf(os.name == 'nt', 'Unix escape sequences')
    def test_real_tty_intro_arrow_does_not_skip_and_s_still_skips(self):
        import pty
        master, slave = pty.openpty()
        output = io.StringIO()
        output.isatty = lambda: True
        reads = []
        original_keys = presentation._terminal_keys
        @contextmanager
        def keys():
            with original_keys() as read:
                os.write(master, b'\x1b[As')
                def tracked_read(timeout):
                    key = read(timeout)
                    reads.append(key)
                    return key
                yield tracked_read
        try:
            with os.fdopen(slave, 'r') as terminal, patch.object(presentation.sys, 'stdin', terminal), patch.object(presentation.sys, 'stdout', output), patch.object(presentation, 'intro_pages', return_value=[('A', 'text')]), patch.object(presentation, '_terminal_keys', keys):
                self.assertTrue(presentation.play_text_intro(object(), object()))
            self.assertEqual(reads, ['up', 's'])
            self.assertNotIn('↑↓', output.getvalue())
        finally:
            os.close(master)
