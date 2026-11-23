"""RPG-style bottom dialogue boxes with typewriter text."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from farmgame.explore import ExplorerGame
from farmgame.model import Farm
from farmgame.terminal import TerminalGame
from farmgame.text_activities import conversation
from tests.test_floating_ui import CellScreen, curses_namespace


class CursesDialogueBoxTests(unittest.TestCase):
    def game(self):
        farm = Farm(player_x=27, player_y=5, facing='right')
        game = ExplorerGame(farm, Path('/tmp/dialogue-box-unused.json'),
                            color=False)
        game._screen = CellScreen(24, 80)
        game._curses = curses_namespace()
        game._colors = {}
        game.coach = SimpleNamespace(event=Mock(), draw_curses=Mock(),
                                     path_points=lambda: set())
        game._choose = Mock(return_value=0)
        return game

    def test_dialogue_box_types_at_the_bottom_and_then_shows_choices(self):
        game = self.game()
        frames = []
        sequence = iter([' ', '1', ' ', '1', ' '])

        def read():
            frames.append('\n'.join(game._screen.lines()))
            return next(sequence)

        game._read = read
        with patch('farmgame.explore.save_game', return_value=None):
            game.handle_key('e')

        # The first frame is still empty while the typewriter is starting.
        self.assertNotIn('Một giỏ đầy màu sắc', frames[0])
        revealed = frames[1]
        self.assertIn('Lan · Chủ tiệm', revealed)
        self.assertIn('Một giỏ đầy màu sắc', revealed)
        self.assertIn('( o o )', revealed)
        self.assertIn('› 1.', revealed)
        self.assertIn('trả lời', revealed)
        self.assertEqual(game.farm.friendships['lan'], 1)
        self.assertEqual(game.farm.xp, 3)
        self.assertEqual(len(game.toasts.visible()), 0)

    def test_escape_closes_the_box_without_awarding_a_reply(self):
        game = self.game()
        game._read = Mock(return_value='\x1b')
        with patch('farmgame.explore.save_game', return_value=None):
            game.handle_key('e')
        self.assertEqual(game.farm.friendships['lan'], 0)
        self.assertEqual(game.farm.xp, 0)


class TextDialogueBoxTests(unittest.TestCase):
    def test_line_mode_renders_a_boxed_speaker_and_choices(self):
        farm = Farm(player_x=27, player_y=5, facing='right')
        game = TerminalGame(farm, Path('/tmp/dialogue-text-unused.json'),
                            color=False, clear_screen=False)
        output = io.StringIO()
        with patch('builtins.input', side_effect=['1', '1', '1']), \
                redirect_stdout(output):
            conversation(game)
        rendered = output.getvalue()
        self.assertIn('╭─ Lan · Chủ tiệm', rendered)
        self.assertIn('1. Một giỏ đầy màu sắc', rendered)
        self.assertIn('Bạn trả lời', rendered)
        self.assertEqual(farm.friendships['lan'], 1)
        self.assertEqual(farm.xp, 3)


if __name__ == '__main__':
    unittest.main()
