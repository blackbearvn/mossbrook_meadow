"""Character profile tabs, quit-to-title and the exit confirmation."""
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from farmgame import text_activities
from farmgame.explore import ExplorerGame
from farmgame.model import Farm
from farmgame.start_screen import TextUI, confirm_exit
from tests.test_floating_ui import CellScreen, curses_namespace


def profile_game(farm=None):
    game = ExplorerGame(farm or Farm(), Path('/tmp/profile-tabs-unused.json'),
                        color=False)
    game._screen = CellScreen(24, 80)
    game._curses = curses_namespace()
    game._colors = {}
    game.coach = SimpleNamespace(event=Mock(), draw_curses=Mock(),
                                 path_points=lambda: set())
    return game


class CharacterTabTests(unittest.TestCase):
    def test_tab_cycles_to_equipment_and_bag_inside_the_same_profile(self):
        farm = Farm(gear={'pickaxe': 1, 'sword': 2, 'armor': 0})
        farm.items['da'] = 3
        farm.items['thuoc'] = 2
        farm.produce['ca_rot'] = 2
        game = profile_game(farm)

        game._read = Mock(side_effect=['\t', 'q'])
        game.handle_key('c')
        equipment = '\n'.join(game._screen.lines())
        self.assertIn('TRANG BỊ', equipment)
        self.assertIn('Sát thương', equipment)
        self.assertIn('Cuốc mỏ', equipment)

        game._read = Mock(side_effect=['\t', '\t', 'q'])
        game.handle_key('c')
        bag = '\n'.join(game._screen.lines())
        self.assertIn('TÚI ĐỒ', bag)
        self.assertIn('Đá', bag)
        self.assertIn('Thuốc hồi sức', bag)

    def test_tab_zero_still_shows_stats_and_the_existing_footer(self):
        game = profile_game()
        game._read = Mock(return_value='q')
        game.handle_key('c')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('THUỘC TÍNH', rendered)
        self.assertIn('TAY NGHỀ', rendered)
        self.assertIn('↑↓/W/S chọn', game._screen.lines()[-2])

    def test_text_character_menu_can_read_equipment_and_bag(self):
        ui = Mock(farm=Farm())
        ui.ask.side_effect = ['g', 'i', '0']
        text_activities.character_menu(ui)
        rendered = ' '.join(call.args[0] for call in ui.wrapped.call_args_list
                            if call.args)
        self.assertIn('Trang bị', rendered)
        self.assertIn('Cuốc mỏ', rendered)
        self.assertIn('Túi đồ', rendered)


class QuitTests(unittest.TestCase):
    def test_character_profile_q_closes_the_panel_not_the_game(self):
        game = profile_game()
        game._read = Mock(return_value='q')
        with patch('farmgame.explore.save_game'):
            game.handle_key('c')
        self.assertFalse(game.return_to_menu)

    def test_map_q_requests_the_title_after_saving(self):
        game = profile_game()
        game.quit_to_menu = True
        with patch('farmgame.explore.save_game') as save:
            self.assertFalse(game.handle_key('q'))
        self.assertTrue(game.return_to_menu)
        save.assert_called_once()

    def test_quick_map_q_keeps_the_old_one_shot_exit(self):
        game = profile_game()
        game.quit_to_menu = False
        with patch('farmgame.explore.save_game'):
            self.assertFalse(game.handle_key('q'))
        self.assertFalse(game.return_to_menu)

    def test_exit_confirmation_accepts_yes_and_cancels_on_no(self):
        with patch('builtins.input', side_effect=['1']), redirect_stdout(io.StringIO()):
            self.assertTrue(confirm_exit(TextUI()))
        with patch('builtins.input', side_effect=['0']), redirect_stdout(io.StringIO()):
            self.assertFalse(confirm_exit(TextUI()))


if __name__ == '__main__':
    unittest.main()
