"""Floating dialogs stay readable over the map at common terminal sizes."""
import unicodedata
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from farmgame import tui
from farmgame.explore import ExplorerGame
from farmgame.model import Farm
from farmgame.start_screen import CursesUI


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
        assert 0 <= y < self.height and 0 <= x < self.width, (y, x)
        for char in text[:count]:
            if unicodedata.combining(char):
                continue
            size = 2 if unicodedata.east_asian_width(char) in 'WF' else 1
            assert x + size <= self.width, (y, x, text)
            self.rows[y][x] = char
            x += size

    def lines(self):
        return [''.join(row) for row in self.rows]


def curses_namespace():
    return SimpleNamespace(
        A_BOLD=1, A_DIM=2, A_REVERSE=4, error=RuntimeError,
        KEY_UP=259, KEY_DOWN=258, KEY_LEFT=260, KEY_RIGHT=261,
        KEY_F5=269, KEY_ENTER=343, KEY_NPAGE=338, KEY_PPAGE=339,
        KEY_END=360, KEY_HOME=262, KEY_BACKSPACE=263)


class FloatingDialogTests(unittest.TestCase):
    def game(self, height=24, width=80):
        game = ExplorerGame(Farm(), Path('/tmp/floating-ui-unused.json'),
                            color=False)
        game._screen = CellScreen(height, width)
        game._curses = curses_namespace()
        game._colors = {}
        game.coach = SimpleNamespace(event=Mock(), draw_curses=Mock(),
                                     path_points=lambda: set())
        return game

    def test_choose_is_a_centred_panel_over_the_visible_map(self):
        game = self.game()
        game._read = Mock(return_value='q')
        game._choose('CHỢ LÀNG · 120 xu',
                     ['Hạt cà rốt · 8 xu', 'Bán tất cả sản phẩm trong túi'],
                     ['Mua bán không làm mất đồ trong rương.'])
        lines = game._screen.lines()
        rendered = '\n'.join(lines)
        self.assertIn('╭', rendered)
        self.assertIn('◆ CHỢ LÀNG · 120 xu', rendered)
        self.assertIn('> 1. Hạt cà rốt', rendered)
        self.assertIn('chọn', lines[-2])
        self.assertTrue(any('♣' in line or '@' in line for line in lines),
                        rendered)
        self.assertNotEqual(lines[0][0], '╭')

    def test_scrolling_choose_keeps_key_hint_before_scroll_counter(self):
        narrow = self.game(8, 20)
        narrow._read = Mock(return_value='q')
        narrow._choose('TÚI ĐỒ', ['Cà rốt', 'Lúa mì', 'Gửi tất cả'], ['Chi tiết'])
        self.assertIn('chọn', narrow._screen.lines()[-2])

        wide = self.game(8, 80)
        wide._read = Mock(return_value='q')
        wide._choose('TÚI ĐỒ', ['Cà rốt', 'Lúa mì', 'Gửi tất cả'], ['Chi tiết'])
        self.assertIn('1/3', wide._screen.lines()[-2])

    def test_choose_keeps_art_lines_intact_above_details_and_options(self):
        game = self.game()
        game._read = Mock(return_value='q')
        game._choose('Lan · Chủ tiệm', ['Giỏ hạt nhiều màu', 'Bảng ghi giống'],
                     ['“Một cửa tiệm mở cửa là một lời chào.”'],
                     art=('  .---.', ' ( o o )', '  \\ - /'))
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('( o o )', rendered)
        self.assertIn('Một cửa tiệm mở cửa', rendered)
        self.assertIn('> 1. Giỏ hạt nhiều màu', rendered)
        self.assertIn('chọn', game._screen.lines()[-2])

    def test_field_board_draws_plots_and_crop_states(self):
        game = self.game(24, 80)
        game.farm.plots['A1'].crop = 'ca_rot'
        game.farm.plots['A1'].growth = 2
        game._read = Mock(return_value='q')
        game.handle_key('f')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('CÁNH ĐỒNG', rendered)
        self.assertIn('A1', rendered)
        self.assertIn('Cà rốt', rendered)
        self.assertIn('Chín', rendered)
        self.assertIn('Trống', rendered)
        self.assertIn('F/Esc đóng', game._screen.lines()[-2])

    def test_barn_board_shows_level_gated_zones_and_animals(self):
        game = self.game(24, 80)
        game.farm.xp = 40
        game.farm.animals = [SimpleNamespace(
            kind='chicken', name='Mơ', age=3, fed=True, petted=False,
            friendship=4, produce=2, days_since_product=0)]
        game._read = Mock(return_value='q')
        game.handle_key('b')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('Sân Gà Vịt', rendered)
        self.assertIn('Đồng Cỏ', rendered)
        self.assertIn('Đồi Dê', rendered)
        self.assertIn('cấp 4', rendered)
        self.assertIn('Mơ', rendered)

    def test_fish_journal_shows_rarity_catches_and_points(self):
        game = self.game(24, 80)
        game.farm.fish_collection['ca_ro'] = 3
        game.farm.fish_collection['ca_lang'] = 1
        game.farm.fish_caught = 4
        game._read = Mock(return_value='q')
        game.handle_key('k')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('BỘ SƯU TẦM CÁ', rendered)
        self.assertIn('Cá rô', rendered)
        self.assertIn('Cá lăng', rendered)
        self.assertIn('Cực hiếm', rendered)
        self.assertIn('điểm sưu tầm', rendered)

    def test_ascii_field_barn_and_fish_panels_use_ascii_controls(self):
        for key, label in (('f', 'W/S/A/D'), ('b', 'W/S'), ('k', 'W/S')):
            game = self.game(20, 60)
            game.unicode_map = False
            game._read = Mock(return_value='q')
            game.handle_key(key)
            lines = game._screen.lines()
            rendered = '\n'.join(lines)
            self.assertNotIn('↑↓', rendered, label)
            self.assertNotIn('←→', rendered, label)
            self.assertTrue(any(label in line for line in lines[-2:]), key)

    def test_short_field_board_fits_a_second_row_and_uses_x_in_ascii(self):
        game = self.game(18, 58)
        game.unicode_map = False
        game._read = Mock(return_value='q')
        game.handle_key('f')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('CÁNH ĐỒNG · 4x4', rendered)
        self.assertIn('A2', rendered)

    def test_medium_fish_journal_switches_to_readable_full_width_list(self):
        game = self.game(20, 60)
        game._read = Mock(return_value='q')
        game.handle_key('k')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('Bộ sưu tầm:', rendered)
        self.assertIn('Cá măng', rendered)
        self.assertNotIn('…', rendered)

    def test_panel_footer_ellipsizes_instead_of_cutting_a_word(self):
        game = self.game(24, 80)
        rect = tui.Rect(1, 1, 24, 5)
        tui.draw_panel(game, rect, title='Thử', footer='chi tiết rất dài ' * 8,
                       unicode=True, bounds=(24, 80))
        footer = game._screen.lines()[4]
        self.assertIn('…', footer)

    def test_narrow_hud_keeps_energy_goal_and_short_controls(self):
        game = self.game(15, 40)
        game._draw()
        lines = game._screen.lines()
        self.assertIn('Sức', lines[1])
        self.assertIn('Mục tiêu', lines[2])
        self.assertLessEqual(max(map(len, lines)), 40)

    def test_ascii_help_replaces_arrow_glyphs(self):
        game = self.game(24, 80)
        game.unicode_map = False
        game._read = Mock(return_value='q')
        game._help()
        rendered = '\n'.join(game._screen.lines())
        self.assertNotIn('↑↓', rendered)
        self.assertNotIn('←→', rendered)
        self.assertIn('W/S', rendered)

    def test_number_dialog_cancels_cleanly_without_inventory_state(self):
        game = self.game(24, 80)
        game._read = Mock(return_value='q')
        self.assertIsNone(game._number('Số lượng', 5))

    def test_inventory_sheet_groups_items_and_shows_art_and_details(self):
        game = self.game(24, 80)
        game._read = Mock(return_value='q')
        game.handle_key('i')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('TÚI ĐỒ', rendered)
        self.assertIn('Tất cả', rendered)
        self.assertIn('Hạt giống', rendered)
        self.assertIn('Nông sản', rendered)
        self.assertIn('Cá', rendered)
        self.assertIn('Khác', rendered)
        self.assertIn('( # )', rendered)
        self.assertIn('Gieo ở ruộng', rendered)
        self.assertIn('Túi 6', rendered)

    def test_inventory_chest_filter_switches_to_crop_and_transfer_hint(self):
        game = self.game(24, 80)
        game.farm.chest['crop:ca_rot'] = 4
        game._read = Mock(side_effect=['3', 'q'])
        game._inventory(True)
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('RƯƠNG · GỬI / RÚT', rendered)
        self.assertIn('Cà rốt', rendered)
        self.assertIn('Túi 0 · Rương 4', rendered)
        self.assertIn('Enter gửi/rút', rendered)

    @patch('farmgame.explore.save_game')
    def test_inventory_sheet_enter_withdraws_selected_chest_item(self, save):
        game = self.game(24, 80)
        game.farm.chest['crop:ca_rot'] = 4
        game._read = Mock(side_effect=['3', '\n', '2', '\n', 'q'])
        game._inventory(True)
        self.assertEqual(game.farm.chest['crop:ca_rot'], 2)
        self.assertEqual(game.farm.produce['ca_rot'], 2)
        save.assert_called()

    def test_inventory_sheet_ascii_uses_ascii_tabs_and_controls(self):
        game = self.game(24, 80)
        game.unicode_map = False
        game._read = Mock(return_value='q')
        game.handle_key('i')
        lines = game._screen.lines()
        rendered = '\n'.join(lines)
        self.assertNotIn('↑↓', rendered)
        self.assertNotIn('–', rendered)
        self.assertIn('W/S', lines[-2])
        self.assertIn('1b Tất cả', rendered)

    @patch('farmgame.explore.save_game')
    def test_home_kitchen_opens_cooking_and_cooks_selected_recipe(self, save):
        game = self.game(24, 80)
        game.farm.area = 'home'
        game.farm.player_x, game.farm.player_y = 10, 5
        game.farm.xp = 400
        game.farm.produce['lua_mi'] = 2
        game.farm.items['egg'] = 1
        game._read = Mock(side_effect=['\n', 'q'])
        game.handle_key('e')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('BẾP NHÀ · NẤU ĂN', rendered)
        self.assertIn('Bánh mì nướng', rendered)
        self.assertIn('đã nấu', rendered.lower())
        self.assertEqual(game.farm.items['banh_mi'], 1)
        save.assert_called()

    @patch('farmgame.explore.save_game')
    def test_region_directory_fast_travels_to_a_named_region(self, save):
        game = self.game(24, 80)
        game._read = Mock(return_value='\n')
        game.handle_key('r')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('KHU VỰC · ĐI NHANH', rendered)
        self.assertIn('Bãi Biển', rendered)
        self.assertEqual((game.farm.player_x, game.farm.player_y), (10, 7))
        save.assert_called()

    @patch('farmgame.explore.save_game')
    def test_character_x_exchanges_overflow_points(self, save):
        game = self.game(24, 80)
        game.farm.xp = 69633
        game.farm.attributes = {key: 5 for key in game.farm.attributes}
        game.farm.skills = {key: 5 for key in game.farm.skills}
        game._read = Mock(side_effect=['x', 'q'])
        game.handle_key('c')
        self.assertEqual((game.farm.attribute_points, game.farm.skill_points), (0, 0))
        self.assertTrue(any('Đã đổi toàn bộ điểm dư' in line
                            for line in game._screen.lines()))
        save.assert_called()

    def test_character_sheet_draws_portrait_identity_and_stat_pips(self):
        game = self.game(24, 80)
        game.farm.attributes['endurance'] = 3
        game.farm.xp = 45
        game._read = Mock(return_value='q')
        game.handle_key('c')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('HỒ SƠ NÔNG DÂN', rendered)
        self.assertIn('(@)', rendered)
        self.assertIn('THUỘC TÍNH', rendered)
        self.assertIn('TAY NGHỀ', rendered)
        self.assertIn('▰', rendered)
        self.assertIn('▱', rendered)
        self.assertIn('◆', rendered)
        self.assertIn('↑↓/W/S chọn', game._screen.lines()[-2])

    def test_shop_grid_draws_illustrated_cards_and_category_tabs(self):
        game = self.game(24, 80)
        game._read = Mock(return_value='q')
        game.farm.coins = 500
        game._shop()
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('CHỢ LÀNG · 500 xu · Hạt giống', rendered)
        self.assertIn('Hạt giống', rendered)
        self.assertIn('Hạt Cà rốt', rendered)
        self.assertIn('( # )', rendered)
        self.assertIn('8 xu', rendered)
        self.assertIn('Tab hoặc 1–5', game._screen.lines()[-2])

    def test_reader_keeps_body_status_and_bottom_controls_inside_panel(self):
        game = self.game(10, 22)
        game._read = Mock(return_value='q')
        game._reader('Lan · Cuộc trò chuyện',
                     'Lan: Chào bạn! Hôm nay trời đẹp nhỉ. ' * 4)
        lines = game._screen.lines()
        self.assertEqual(lines[0][1], '╭')
        self.assertEqual(lines[0][20], '╮')
        self.assertIn('Lan: Chào bạn', '\n'.join(lines[2:8]))
        self.assertIn('Dòng', lines[8])
        self.assertIn('/', lines[8])
        self.assertEqual(lines[9][1], '╰')
        self.assertEqual(lines[9][20], '╯')
        self.assertIn('cuộn', lines[9])

    def test_overview_uses_floating_panel_and_keeps_map_legend(self):
        game = self.game()
        game._read = Mock(return_value='q')
        game._overview()
        lines = game._screen.lines()
        rendered = '\n'.join(lines)
        self.assertIn('◆ BẢN ĐỒ LÀNG', rendered)
        self.assertIn('J dân làng', rendered)
        self.assertIn('@', rendered)
        self.assertIn('╰', rendered)
        self.assertIn('╯', rendered)

    def test_ascii_mode_switches_the_whole_floating_shell(self):
        game = self.game()
        game.unicode_map = False
        game._read = Mock(return_value='q')
        game._choose('TÚI ĐỒ', ['Cà rốt: túi 3'], ['Đồ trong rương được giữ lại.'])
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('+', rendered)
        self.assertIn('|', rendered)
        self.assertNotIn('╭', rendered)
        self.assertNotIn('░', rendered)


class StartScreenFloatingTests(unittest.TestCase):
    def test_paint_draws_top_rule_and_floating_panel(self):
        ui = CursesUI(color=False)
        ui._screen = CellScreen(24, 80)
        ui._curses = curses_namespace()
        ui._colors = {}
        room, scroll = ui.paint(
            'MÂY NHỎ · Một cuộc sống chậm giữa mây trời',
            ['Dòng giới thiệu', '1. Tiếp tục'], 'Enter: chọn', selected=1)
        lines = ui._screen.lines()
        rendered = '\n'.join(lines)
        self.assertTrue(lines[0].startswith('─'))
        self.assertIn('MÂY NHỎ', lines[0])
        self.assertIn('╭', lines[1])
        self.assertIn('◆ MÂY NHỎ', lines[1])
        self.assertIn('› 1. Tiếp tục', rendered)
        self.assertIn('Enter: chọn', rendered)
        self.assertGreaterEqual(room, 1)
        self.assertEqual(scroll, 0)


if __name__ == '__main__':
    unittest.main()
