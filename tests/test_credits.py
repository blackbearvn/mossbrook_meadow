"""The credits are complete, readable, and independent of a running farm."""
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from farmgame import credits


class FakeUI:
    def __init__(self, actions, size=(12, 60)):
        self.actions = iter(actions)
        self.size = size
        self.frames = []
        self.now = 0.0
        self.timeouts = []
        self._screen = SimpleNamespace(getmaxyx=lambda: self.size,
                                       timeout=self.timeouts.append)
        self._curses = SimpleNamespace(KEY_UP=259, KEY_DOWN=258,
                                      KEY_PPAGE=339, KEY_NPAGE=338,
                                      KEY_HOME=262, KEY_END=360,
                                      KEY_RESIZE=410, KEY_ENTER=343)

    def paint(self, title, lines, footer, selected=None, scroll=0):
        self.frames.append((tuple(lines), scroll, footer, self.size))

    def key(self):
        action = next(self.actions)
        if isinstance(action, tuple):
            self.size = action
            return self._curses.KEY_RESIZE
        delay, key = action if isinstance(action, list) else (0.0, action)
        self.now += delay
        return key


class CreditsTests(unittest.TestCase):
    def view(self, ui):
        with patch.object(credits.time, 'monotonic', side_effect=lambda: ui.now):
            credits.play_curses_credits(ui)

    def test_original_credits_exceed_one_hundred_meaningful_lines(self):
        lines = credits.credits_lines()
        actual = [line.strip() for line in lines if line.strip()]
        self.assertIsInstance(lines, tuple)
        self.assertGreater(len(actual), 100)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertIn('REDEYE STUDIO', actual)
        self.assertIn('b14ckb34rvn · Lập trình', actual)
        self.assertIn('TeaM1lk · Đồ họa', actual)
        self.assertIn("so'dly · Đồ họa", actual)
        self.assertIn('Hoàng Lê · Âm thanh', actual)
        self.assertIn('BrosHill · Cốt truyện', actual)
        self.assertIn('MoiMoi · Đồ họa', actual)
        self.assertIn('Fanta de Son · Đồ họa', actual)
        self.assertNotIn('Hỗ trợ lập trình: Codex', actual)
        self.assertTrue(all(len(line) >= 8 for line in actual))

    def test_end_home_and_resize_leave_last_line_readable(self):
        ui = FakeUI([360, (9, 23), 360, 262, 'q'])
        self.view(ui)
        for lines, scroll, _, size in (ui.frames[1], ui.frames[3]):
            room = size[0] - 5
            self.assertEqual(scroll, max(0, len(lines) - room))
            self.assertIn(credits.credits_lines()[-1].split()[-1], lines[-1])
        self.assertEqual(ui.frames[-1][1], 0)
        self.assertEqual(ui.timeouts[-1], 100)

    def test_auto_scroll_stops_at_bottom_without_exiting(self):
        ui = FakeUI([[0.45, -1], [10000, -1], [10000, -1], 'q'])
        self.view(ui)
        self.assertEqual(ui.frames[1][1], 1)
        self.assertEqual(ui.frames[-1][1], len(ui.frames[-1][0]) - 7)
        self.assertEqual(ui.frames[-2][1], ui.frames[-1][1])

    def test_space_and_manual_navigation_pause_elapsed_scroll(self):
        ui = FakeUI([' ', [50, -1], 338, [50, -1], 259, [50, -1], 'q'])
        self.view(ui)
        self.assertEqual(ui.frames[1][1], ui.frames[2][1])
        self.assertEqual(ui.frames[3][1], ui.frames[4][1])
        self.assertEqual(ui.frames[5][1], ui.frames[6][1])
        self.assertEqual(ui.frames[3][1], 7)
        self.assertEqual(ui.frames[5][1], 6)

    def test_resuming_does_not_include_time_spent_paused(self):
        ui = FakeUI([' ', [50, ' '], [0.44, -1], [0.02, -1], 'q'])
        self.view(ui)
        self.assertEqual([frame[1] for frame in ui.frames], [0, 0, 0, 0, 1])

    def test_interrupt_restores_timeout(self):
        ui = FakeUI([])
        ui.key = lambda: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            self.view(ui)
        self.assertEqual(ui.timeouts[-1], 100)

    def test_text_pages_can_read_all_original_lines(self):
        output = io.StringIO()
        with patch.object(credits.shutil, 'get_terminal_size', return_value=(48, 12)), \
                patch('builtins.input', return_value=''), redirect_stdout(output):
            credits.play_text_credits(object())
        rendered = output.getvalue()
        for line in credits.credits_lines():
            self.assertIn(' '.join(line.split()), ' '.join(rendered.replace('Credit nhà phát triển', '').split()))
        self.assertGreater(rendered.count('Credit nhà phát triển'), 2)

    def test_text_resize_preserves_every_unread_character(self):
        output = io.StringIO()
        sizes = [(40, 12), (80, 12), (25, 12)]
        page = 0

        def next_page(prompt):
            nonlocal page
            page += 1
            return ''

        with patch.object(credits.shutil, 'get_terminal_size',
                          side_effect=lambda **kwargs: sizes[min(page, 2)]), \
                patch('builtins.input', side_effect=next_page), redirect_stdout(output):
            credits.play_text_credits(object())
        rendered = output.getvalue().replace('Credit nhà phát triển', '')
        self.assertEqual(''.join(rendered.split()),
                         ''.join(''.join(credits.credits_lines()).split()))

    def test_text_previous_and_quit(self):
        output = io.StringIO()
        with patch.object(credits.shutil, 'get_terminal_size', return_value=(80, 12)), \
                patch('builtins.input', side_effect=['', 'b', 'q']), redirect_stdout(output):
            credits.play_text_credits(object())
        self.assertEqual(output.getvalue().count(credits.credits_lines()[0]), 2)

    def test_redirected_eof_outputs_remaining_pages(self):
        output = io.StringIO()
        with patch.object(credits.shutil, 'get_terminal_size', return_value=(80, 12)), \
                patch.object(credits.sys, 'stdin', io.StringIO('')), \
                patch('builtins.input', side_effect=EOFError), redirect_stdout(output):
            credits.play_text_credits(object())
        self.assertIn(credits.credits_lines()[-1], output.getvalue())
