"""Intro starts inside the running game after new-game confirmation."""

import tempfile
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from farmgame.identity import create_character
from farmgame.model import Farm
from farmgame.storage import load_game, save_game
from farmgame.start_screen import run_startup


class OpeningFlowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'farm.json'

    def test_confirm_new_game_commits_before_any_intro_runs(self):
        answers = ['2', 'Linh', 'Vườn Sớm', '1', '1', '1', '1']
        with patch('builtins.input', side_effect=answers), redirect_stdout(StringIO()):
            with patch('farmgame.start_screen.TextUI.intro', side_effect=AssertionError('Intro before gameplay')):
                result = run_startup(self.path, graphical=False)
        self.assertTrue(result.created)
        self.assertTrue(result.play_intro)
        self.assertFalse(load_game(self.path).intro_seen)

    def test_continue_requests_pending_intro_without_playing_it_in_menu(self):
        save_game(create_character('Linh', 'Vườn'), self.path)
        before = self.path.read_bytes()
        with patch('builtins.input', side_effect=['1', EOFError]), redirect_stdout(StringIO()):
            result = run_startup(self.path, graphical=False)
        self.assertTrue(result.play_intro)
        self.assertEqual(self.path.read_bytes(), before)

    def test_text_runtime_draws_game_then_intro_then_saves_completion(self):
        from farmgame.terminal import TerminalGame
        farm = create_character('Linh', 'Vườn')
        save_game(farm, self.path)
        events = []
        game = TerminalGame(farm, self.path, intro=True)
        game.draw = lambda: events.append('map')
        def intro(_):
            events.append('intro')
            self.assertFalse(load_game(self.path).intro_seen)
            return True
        with patch('farmgame.start_screen.TextUI.intro', side_effect=intro):
            with patch('builtins.input', return_value='0'), redirect_stdout(StringIO()):
                self.assertEqual(game.run(), 0)
        self.assertEqual(events[:2], ['map', 'intro'])
        self.assertTrue(load_game(self.path).intro_seen)

    def test_text_runtime_interrupt_keeps_intro_pending_and_new_game_saved(self):
        from farmgame.terminal import TerminalGame
        farm = create_character('Linh', 'Vườn')
        save_game(farm, self.path)
        game = TerminalGame(farm, self.path, intro=True)
        game.draw = Mock()
        with patch('farmgame.start_screen.TextUI.intro', side_effect=KeyboardInterrupt):
            with redirect_stdout(StringIO()):
                self.assertEqual(game.run(), 0)
        restored = load_game(self.path)
        self.assertFalse(restored.intro_seen)
        self.assertEqual(restored.player_name, 'Linh')

    def test_curses_intro_eof_exits_cleanly_with_pending_save(self):
        from farmgame.explore import ExplorerGame
        farm = create_character('Linh', 'Vườn')
        save_game(farm, self.path)
        game = ExplorerGame(farm, self.path, intro=True)
        fake_curses = Mock()
        fake_curses.wrapper.side_effect = EOFError
        with patch.dict(sys.modules, {'curses': fake_curses}):
            self.assertEqual(game.run(), 0)
        self.assertFalse(load_game(self.path).intro_seen)


if __name__ == '__main__':
    unittest.main()
