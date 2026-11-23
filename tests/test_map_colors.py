"""The map palette has one semantic role for every landscape element."""

import unittest
from types import SimpleNamespace

from farmgame import map_art
from farmgame.terminal import STYLES
from farmgame.tui import init_colors


class FakeCurses:
    A_DIM = 1
    A_BOLD = 2
    COLORS = 256
    COLOR_PAIRS = 256
    COLOR_GREEN = 2
    COLOR_YELLOW = 3
    COLOR_CYAN = 6
    COLOR_BLUE = 4
    COLOR_MAGENTA = 5
    COLOR_RED = 1
    COLOR_WHITE = 7
    error = RuntimeError

    def __init__(self):
        self.pairs = {}

    def has_colors(self):
        return True

    def start_color(self):
        pass

    def use_default_colors(self):
        pass

    def init_pair(self, pair, foreground, background):
        self.pairs[pair] = (foreground, background)

    def color_pair(self, pair):
        return pair


class MapColorTests(unittest.TestCase):
    def test_every_landscape_role_is_defined(self):
        expected = {'grass', 'forest', 'flower', 'soil', 'sand', 'lake',
                    'sea', 'path', 'stone', 'building', 'furniture', 'door'}
        self.assertTrue(expected <= set(map_art.MAP_COLORS.values()))
        for role in expected | {'roof'}:
            self.assertIn(role, STYLES)

    def test_256_colour_palette_uses_golden_sand_pale_lake_and_blue_sea(self):
        curses = FakeCurses()
        colors = init_colors(curses)
        for role in ('grass', 'forest', 'flower', 'soil', 'sand', 'lake',
                     'sea', 'path', 'stone', 'building', 'roof',
                     'furniture', 'door'):
            self.assertIn(role, colors)
        self.assertEqual(curses.pairs[colors['sand']][0], 220)
        self.assertEqual(curses.pairs[colors['lake']][0], 121)
        self.assertEqual(curses.pairs[colors['sea']][0], 27)

    def test_basic_eight_colour_terminal_still_gets_fallbacks(self):
        curses = FakeCurses()
        curses.COLORS = 8
        colors = init_colors(curses)
        for role in ('sand', 'lake', 'sea', 'forest', 'roof'):
            self.assertIn(role, colors)
        self.assertEqual(curses.pairs[colors['sand']][0], FakeCurses.COLOR_YELLOW)
        self.assertEqual(curses.pairs[colors['lake']][0], FakeCurses.COLOR_CYAN)
        self.assertEqual(curses.pairs[colors['sea']][0], FakeCurses.COLOR_BLUE)


if __name__ == '__main__':
    unittest.main()
