"""Map styling keeps the player, controls and overlays visible after resizing."""
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from os import terminal_size
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unicodedata
import unittest
from unittest.mock import patch

from farmgame.explore import ExplorerGame, fit_text, overview_rows
from farmgame.automation import Automation, AutoOptions
from farmgame.model import Farm
from farmgame.terminal import TerminalGame
from farmgame.text_activities import _draw_map, map_mode
from farmgame.tutorial import TutorialState


def physical_rows(text, width):
    """Count terminal wrapping independently of the production clipping code."""
    rows = 0
    for line in text.split('\n'):
        count = sum(0 if unicodedata.combining(char) else
                    2 if unicodedata.east_asian_width(char) in 'WF' else 1
                    for char in line)
        rows += max(1, (count + width - 1) // width)
    return rows


class CellScreen:
    def __init__(self, height, width):
        self.height, self.width = height, width
        self.erase()

    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self.rows = [[' '] * self.width for _ in range(self.height)]

    def refresh(self):
        pass

    def addnstr(self, y, x, text, count, attributes):
        assert 0 <= y < self.height and 0 <= x < self.width
        for char in text[:count]:
            if unicodedata.combining(char):
                continue
            cells = 2 if unicodedata.east_asian_width(char) in 'WF' else 1
            assert x + cells <= self.width, (y, x, text)
            self.rows[y][x] = char
            x += cells

    def lines(self):
        return [''.join(row) for row in self.rows]


class MapUITests(unittest.TestCase):
    def game(self, farm=None, height=24, width=80):
        game = ExplorerGame(farm or Farm(), Path('/tmp/map-unused.json'), color=False)
        game._screen = CellScreen(height, width)
        game._curses = SimpleNamespace(A_BOLD=1, error=RuntimeError,
                                      KEY_UP=259, KEY_DOWN=258,
                                      KEY_LEFT=260, KEY_RIGHT=261, KEY_F5=269)
        return game

    def test_g_changes_map_style_without_moving_or_mutating_save_state(self):
        game = self.game()
        before = asdict(game.farm)
        initial = getattr(game, 'unicode_map', None)
        game.handle_key('g')
        self.assertIsInstance(getattr(game, 'unicode_map', None), bool)
        self.assertNotEqual(initial, game.unicode_map)
        self.assertEqual(asdict(game.farm), before)

    def test_g_keeps_ascii_when_terminal_cannot_encode_map_art(self):
        game = self.game()
        game.unicode_map = False
        before = asdict(game.farm)
        with patch('farmgame.map_art.supports_unicode', return_value=False):
            game.handle_key('g')
        self.assertFalse(game.unicode_map)
        self.assertEqual(asdict(game.farm), before)

    def test_both_styles_keep_camera_player_controls_and_save_error_on_resize(self):
        farm = Farm(player_x=110, player_y=21)
        farm.name = '天地玄黄宇宙洪荒日月'
        game = self.game(farm)
        before = asdict(farm)
        for unicode_map in (True, False):
            game.unicode_map = unicode_map
            for height, width in ((24, 80), (10, 22), (16, 60), (40, 140)):
                with self.subTest(unicode_map=unicode_map, size=(height, width)):
                    game._screen = CellScreen(height, width)
                    game._save_error = 'disk full'
                    game._draw()
                    lines = game._screen.lines()
                    self.assertTrue(any('@' in line for line in lines[3:height - 6]))
                    self.assertIn('Q', lines[-1])
                    self.assertIn('disk full', lines[-2])
        self.assertEqual(asdict(farm), before)

    def test_text_map_and_overview_share_style_and_keep_player_visible(self):
        farm = Farm()
        with tempfile.TemporaryDirectory() as directory:
            ui = TerminalGame(farm, Path(directory) / 'farm.json', color=False)
            for unicode_map in (True, False):
                ui.unicode_map = unicode_map
                with redirect_stdout(StringIO()) as output:
                    _draw_map(ui)
                self.assertIn('@', output.getvalue())
                if unicode_map:
                    self.assertIn('╭', output.getvalue())
                    self.assertIn('≈', output.getvalue())
                else:
                    self.assertNotIn('╭', output.getvalue())
                    self.assertNotIn('≈', output.getvalue())
                rows = overview_rows(farm, 39, 12, unicode=unicode_map)
                self.assertIn('@', ''.join(rows))
                self.assertTrue(all(len(row) <= 39 for row in rows))

    def test_ascii_flag_runs_the_real_text_map_with_plain_map_symbols(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(root / 'main.py'),
                                     '--text', '--ascii', '--skip-intro',
                                     '--save', str(Path(directory) / 'farm.json')],
                                    input='m\nb\n0\n', text=True, capture_output=True,
                                    timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('@', result.stdout)
        self.assertNotIn('╭', result.stdout)
        self.assertNotIn('≈', result.stdout)

    def test_text_map_fits_at_input_with_long_messages_guide_and_save_error(self):
        with tempfile.TemporaryDirectory() as directory:
            for rich in (True, False):
                for height, width in ((24, 80), (10, 22), (16, 60), (40, 140)):
                    with self.subTest(rich=rich, size=(height, width)):
                        farm = Farm(player_x=10, player_y=1, name='天地玄黄宇宙洪荒日月',
                                    tutorial=TutorialState(status='active', step=6, plot='A1'))
                        ui = TerminalGame(farm, Path(directory) / 'farm.json',
                                          color=False, clear_screen=False)
                        ui.unicode_map = rich
                        ui.unsaved = True
                        ui.messages = ['Thông báo dài ' * 20, 'Thông báo trước',
                                       'Lỗi lưu: disk full ' + 'ghi lại ' * 20]
                        before = asdict(farm)
                        try:
                            with patch('farmgame.text_activities.shutil.get_terminal_size',
                                       return_value=terminal_size((width, height))), \
                                 patch('builtins.input', return_value='b'), \
                                 redirect_stdout(StringIO()) as output:
                                self.assertFalse(map_mode(ui))
                            text = output.getvalue()
                            self.assertLessEqual(physical_rows(text, width), height, text)
                            self.assertTrue(any('@' in line and 'bạn' not in line
                                                for line in text.splitlines()), text)
                            self.assertIn('chưa lưu', text.lower())
                            self.assertIn('disk full', text)
                            self.assertIn('T', text)
                            prompt = text.split('\n')[-1].lower()
                            self.assertIn('q', prompt)
                            self.assertIn('g hình', prompt)
                            self.assertEqual(asdict(farm), before)
                        finally:
                            ui._line_input.close()

    def test_text_auto_frame_keeps_player_and_stop_control_within_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            for height, width in ((24, 80), (10, 22)):
                with self.subTest(size=(height, width)):
                    farm = Farm(player_x=10, player_y=1,
                                tutorial=TutorialState(status='active', step=6, plot='A1'))
                    ui = TerminalGame(farm, Path(directory) / 'farm.json', color=False)
                    ui.clear_screen = True
                    ui.unsaved = True
                    ui.messages = ['Thông báo rất dài ' * 20] * 3
                    ui.activities.auto = Automation(farm, AutoOptions(mode='farm'))
                    ui.poll_input = lambda timeout: 'o'
                    try:
                        with patch('farmgame.text_activities.shutil.get_terminal_size',
                                   return_value=terminal_size((width, height))), \
                             redirect_stdout(StringIO()) as output:
                            ui.activities.run_text_auto()
                        frame = output.getvalue().rsplit('\033[2J\033[H', 1)[-1]
                        self.assertLessEqual(physical_rows(frame, width), height, frame)
                        self.assertTrue(any('@' in line and 'bạn' not in line
                                            for line in frame.splitlines()), frame)
                        self.assertIn('AUTO', frame)
                        self.assertIn('o dừng', frame.lower())
                    finally:
                        ui._line_input.close()


if __name__ == '__main__':
    unittest.main()
