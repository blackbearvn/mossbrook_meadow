"""Floating-window geometry, borders and cell-aware text helpers."""
import unicodedata
import unittest
from types import SimpleNamespace

from farmgame import tui


class Screen:
    def __init__(self, height, width):
        self.height, self.width = height, width
        self.rows = [[' '] * width for _ in range(height)]

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


class Painter:
    def __init__(self, height, width):
        self._screen = Screen(height, width)
        self._curses = SimpleNamespace(A_BOLD=1, A_DIM=2, A_REVERSE=4,
                                       error=RuntimeError)
        self._colors = {}
        self._dim_base = False

    def _put(self, y, x, text, color='', bold=False):
        height, width = self._screen.getmaxyx()
        if not (0 <= y < height and 0 <= x < width):
            return
        available = width - x - int(y == height - 1)
        if available <= 0:
            return
        self._screen.addnstr(y, x, text[:available], available, 0)


class TuiTextTests(unittest.TestCase):
    def test_cells_clip_and_pad_keep_wide_and_combining_text_together(self):
        self.assertEqual(tui.cells('a界b'), 4)
        self.assertEqual(tui.cells('a\u0301b'), 2)
        self.assertEqual(tui.clip('a界b', 3), 'a界')
        self.assertEqual(tui.clip('a\u0301b', 1), 'a\u0301')
        self.assertEqual(tui.pad('界', 3), '界 ')
        self.assertEqual(tui.ellipsize('a界b', 3), 'a…')
        self.assertEqual(tui.ellipsize('abcdef', 4, unicode=False), 'a...')
        self.assertEqual(tui.ellipsize('abc', 3), 'abc')

    def test_progress_bar_has_exact_width_and_clamped_ratio(self):
        self.assertEqual(tui.progress_bar(0.5, 6), '▰▰▰▱▱▱')
        self.assertEqual(tui.progress_bar(-1, 4), '▱▱▱▱')
        self.assertEqual(tui.progress_bar(2, 4), '▰▰▰▰')
        self.assertEqual(tui.progress_bar(0.5, 4, unicode=False), '##--')


class GeometryTests(unittest.TestCase):
    def test_panel_geometry_centres_above_reserved_status_bar(self):
        rect = tui.panel_geometry(24, 80, content_width=50, content_height=12,
                                  margin_x=2, margin_y=1, bottom_reserve=2,
                                  min_width=30, min_height=7)
        self.assertEqual((rect.width, rect.height), (50, 12))
        self.assertEqual(rect.x, 15)
        self.assertEqual(rect.y, 5)
        self.assertLessEqual(rect.bottom, 21)

    def test_tiny_screen_shrinks_instead_of_overflowing(self):
        rect = tui.panel_geometry(6, 16, content_width=80, content_height=80,
                                  margin_x=1, margin_y=1, bottom_reserve=2,
                                  min_width=30, min_height=7)
        self.assertGreaterEqual(rect.width, 1)
        self.assertGreaterEqual(rect.height, 1)
        self.assertLessEqual(rect.right, 15)
        self.assertLessEqual(rect.bottom, 5)


class PanelRenderingTests(unittest.TestCase):
    def test_unicode_panel_has_title_footer_shadow_and_opaque_body(self):
        painter = Painter(12, 40)
        rect = tui.Rect(2, 1, 30, 8)
        body = tui.draw_panel(painter, rect, title='TÚI ĐỒ',
                              footer='Esc quay lại', unicode=True,
                              bounds=(12, 40))
        lines = painter._screen.lines()
        self.assertEqual(lines[1][2], '╭')
        self.assertEqual(lines[1][31], '╮')
        self.assertIn('◆ TÚI ĐỒ', lines[1])
        self.assertEqual(lines[8][2], '╰')
        self.assertEqual(lines[8][31], '╯')
        self.assertEqual(lines[7][2], '│')
        self.assertIn('Esc quay lại', lines[7])
        self.assertEqual(lines[2][32], '░')
        self.assertEqual(lines[9][4], '░')
        self.assertEqual(body, tui.Rect(3, 2, 28, 5))
        self.assertEqual(lines[2][3:31], ' ' * 28)

    def test_ascii_panel_uses_plain_borders(self):
        painter = Painter(10, 30)
        tui.draw_panel(painter, tui.Rect(1, 1, 20, 6), title='TÚI ĐỒ',
                       footer='Esc', unicode=False, bounds=(10, 30))
        rendered = '\n'.join(painter._screen.lines())
        self.assertIn('+', rendered)
        self.assertIn('|', rendered)
        self.assertNotIn('╭', rendered)
        self.assertNotIn('░', rendered)

    def test_shadow_is_skipped_when_panel_touches_screen_edges(self):
        painter = Painter(8, 24)
        tui.draw_panel(painter, tui.Rect(0, 0, 24, 8), title='EDGE',
                       unicode=True, bounds=(8, 24))
        lines = painter._screen.lines()
        self.assertNotIn('░', '\n'.join(lines))
        self.assertEqual(lines[0][0], '╭')
        self.assertEqual(lines[7][23], ' ')

    def test_status_bar_keeps_controls_and_message_visible(self):
        painter = Painter(10, 40)
        tui.draw_status_bar(painter, 10, 40, '↑↓ chọn · Enter dùng',
                            'Đã lưu ván chơi.')
        lines = painter._screen.lines()
        self.assertIn('chọn', lines[8])
        self.assertIn('Đã lưu', lines[9])


if __name__ == '__main__':
    unittest.main()
