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
        farm = Farm(gear={'hat': 1, 'sword': 2, 'armor': 0,
                            'pants': 0, 'shoes': 0})
        farm.items['da'] = 3
        farm.items['thuoc'] = 2
        farm.produce['ca_rot'] = 2
        game = profile_game(farm)

        game._read = Mock(side_effect=['\t', 'q'])
        game.handle_key('c')
        equipment = '\n'.join(game._screen.lines())
        self.assertIn('TRANG BỊ', equipment)
        self.assertIn('Sát thương', equipment)
        self.assertIn('Mũ thợ mỏ', equipment)
        self.assertIn('Quần da', equipment)
        self.assertIn('Giày da', equipment)

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

    def test_only_tab_changes_profile_tabs_not_a_or_d(self):
        game = profile_game(Farm())
        frames = []
        sequence = iter(['\t', 'd', 'a', '\t', 'q'])

        def read():
            frames.append('\n'.join(game._screen.lines()))
            return next(sequence)

        game._read = read
        game.handle_key('c')
        self.assertIn('TRANG BỊ', frames[1])
        self.assertIn('TRANG BỊ', frames[2])
        self.assertIn('TRANG BỊ', frames[3])
        self.assertIn('TÚI ĐỒ', frames[4])

    def test_gear_tab_uses_five_square_slots_and_enter_opens_a_tooltip(self):
        farm = Farm(gear={'hat': 1, 'sword': 2, 'armor': 0,
                          'pants': 0, 'shoes': 0})
        game = profile_game(farm)
        frames = []
        sequence = iter(['\t', '\n', None, ' ', 'q'])

        def read():
            frames.append('\n'.join(game._screen.lines()))
            return next(sequence)

        game._read = read
        game.handle_key('c')
        equipment = frames[1]
        for name in ('Mũ thợ mỏ', 'Kiếm rèn', 'Giáp da', 'Quần da', 'Giày da'):
            self.assertIn(name, equipment)
        self.assertIn('›1', equipment)
        tooltip = frames[2]
        self.assertIn('Mũ thợ mỏ · Hiếm', tooltip)
        self.assertIn('Cấp bậc: Hiếm (2/5)', tooltip)
        self.assertIn('Rèn kế tiếp', tooltip)
        self.assertIn('Nhấn phím bất kỳ để đóng', tooltip)
        # A timeout (None) keeps the tooltip visible instead of flashing shut.
        self.assertIn('Nhấn phím bất kỳ để đóng', frames[3])

    def test_number_key_selects_a_gear_slot_before_opening_its_tooltip(self):
        game = profile_game(Farm())
        frames = []
        sequence = iter(['\t', '5', '\n', ' ', 'q'])

        def read():
            frames.append('\n'.join(game._screen.lines()))
            return next(sequence)

        game._read = read
        game.handle_key('c')
        self.assertIn('Giày da · Bình thường', frames[3])

    def test_clicking_a_square_slot_opens_the_same_item_tooltip(self):
        game = profile_game(Farm())
        game._curses.KEY_MOUSE = 409
        game._curses.BUTTON1_CLICKED = 1
        frames = []
        mouse_event = SimpleNamespace(x=0, y=0, bstate=1)

        def read():
            frames.append('\n'.join(game._screen.lines()))
            return next(sequence)

        def getmouse():
            bx, by, bw, bh = game._gear_boxes[4]
            mouse_event.x = bx + bw // 2
            mouse_event.y = by + bh // 2
            return mouse_event

        sequence = iter(['\t', 409, ' ', 'q'])
        game._read = read
        game._curses.getmouse = getmouse
        game.handle_key('c')
        self.assertIn('Giày da · Bình thường', frames[2])

    def test_text_character_menu_can_read_equipment_and_bag(self):
        ui = Mock(farm=Farm())
        ui.ask.side_effect = ['g', 'i', '0']
        text_activities.character_menu(ui)
        rendered = ' '.join(call.args[0] for call in ui.wrapped.call_args_list
                            if call.args)
        self.assertIn('Trang bị', rendered)
        self.assertIn('Mũ thợ mỏ', rendered)
        self.assertIn('Quần da', rendered)
        self.assertIn('Giày da', rendered)
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
