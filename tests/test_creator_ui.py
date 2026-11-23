"""Live character-creation page and its terminal-size fallback."""
import unicodedata
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        KEY_ENTER=343, KEY_BTAB=353, KEY_BACKSPACE=263)


class CreatorUITests(unittest.TestCase):
    def ui(self, height=24, width=80, unicode=True):
        ui = CursesUI(color=False)
        ui._screen = CellScreen(height, width)
        ui._curses = curses_namespace()
        ui._colors = {}
        ui.unicode_map = unicode
        return ui

    def test_creator_page_shows_form_live_preview_and_actions(self):
        ui = self.ui()
        ui._read = Mock(return_value='\x1b')
        self.assertIsNone(ui.character_wizard('Vườn Nắng'))
        rendered = '\n'.join(ui._screen.lines())
        for text in ('TẠO NHÂN VẬT', 'Tên bạn', 'Nông trại', 'Biểu tượng',
                     'Màu áo', 'Xuất thân', 'XEM TRƯỚC', 'Vườn Nắng',
                     'Bắt đầu hành trình', 'Hủy'):
            self.assertIn(text, rendered)
        self.assertIn('Người làm vườn', rendered)
        self.assertIn('(@)', rendered)

    def test_creator_cycles_options_and_returns_profile(self):
        ui = self.ui()
        keys = ui._curses
        ui._read = Mock(side_effect=[
            keys.KEY_DOWN, keys.KEY_DOWN, keys.KEY_RIGHT,
            keys.KEY_DOWN, keys.KEY_RIGHT,
            keys.KEY_DOWN, keys.KEY_RIGHT,
            keys.KEY_DOWN, keys.KEY_ENTER,
        ])
        profile = ui.character_wizard('Vườn Nắng')
        self.assertEqual(profile['player_name'], 'Người làm vườn')
        self.assertEqual(profile['farm_name'], 'Vườn Nắng')
        self.assertEqual((profile['avatar'], profile['outfit'],
                          profile['background']), ('&', 'cyan', 'angler'))

    def test_creator_edits_text_field_through_existing_modal(self):
        ui = self.ui()
        ui.name = Mock(return_value='Bình')
        ui._read = Mock(side_effect=[
            ui._curses.KEY_ENTER,
            *([ui._curses.KEY_DOWN] * 5),
            ui._curses.KEY_ENTER,
        ])
        profile = ui.character_wizard('Vườn Nắng')
        self.assertEqual(profile['player_name'], 'Bình')
        ui.name.assert_called_once_with('Tên bạn', 'Người làm vườn', 24)

    def test_creator_uses_ascii_shell_when_unicode_is_off(self):
        ui = self.ui(unicode=False)
        ui._read = Mock(return_value='\x1b')
        ui.character_wizard('Vườn Nắng')
        rendered = '\n'.join(ui._screen.lines())
        self.assertIn('+', rendered)
        self.assertIn('|', rendered)
        self.assertNotIn('╭', rendered)
        self.assertNotIn('░', rendered)

    def test_creator_separates_the_longest_label_from_its_value(self):
        ui = self.ui()
        ui._read = Mock(return_value='\x1b')
        ui.character_wizard('Vườn Nắng')
        rendered = '\n'.join(ui._screen.lines())
        self.assertIn('Biểu tượng @ Nhà nông', rendered)
        self.assertNotIn('Biểu tượng@', rendered)
        self.assertIn('Tên bạn    Người làm vườn', rendered)

    def test_medium_terminal_keeps_two_columns_and_the_preview_card(self):
        ui = self.ui(20, 60)
        ui._read = Mock(return_value='\x1b')
        ui.character_wizard('Vườn Nắng')
        rendered = '\n'.join(ui._screen.lines())
        self.assertIn('XEM TRƯỚC', rendered)
        self.assertIn('╭', rendered)
        self.assertIn('Vườn Nắng', rendered)

    def test_short_terminal_uses_a_compact_live_preview(self):
        ui = self.ui(18, 50)
        ui._read = Mock(return_value='\x1b')
        ui.character_wizard('Vườn Nắng')
        rendered = '\n'.join(ui._screen.lines())
        self.assertIn('@ Người làm vườn · Vườn Nắng', rendered)
        self.assertIn('Xanh lá · Người làm vườn', rendered)
        self.assertNotIn('XEM TRƯỚC', rendered)

    def test_tiny_terminal_falls_back_to_step_wizard(self):
        ui = self.ui(10, 30)
        with patch('farmgame.start_screen._wizard_steps',
                   return_value={'fallback': True}) as fallback:
            self.assertEqual(ui.character_wizard('Vườn Nắng'),
                             {'fallback': True})
        fallback.assert_called_once_with(ui, 'Vườn Nắng')


if __name__ == '__main__':
    unittest.main()
