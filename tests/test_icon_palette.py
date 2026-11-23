"""The themed icon palette stays one cell wide in every terminal mode."""

import unicodedata
import unittest

from farmgame import artwork
from farmgame.tui import cells


class IconPaletteTests(unittest.TestCase):
    def mappings(self):
        return {
            'SYMBOLS': artwork.SYMBOLS,
            'WEATHER_ICONS': artwork.WEATHER_ICONS,
            'QUEST_ICONS': artwork.QUEST_ICONS,
            'STAT_ICONS': artwork.STAT_ICONS,
        }

    def test_every_themed_glyph_is_narrow_printable_and_not_combining(self):
        for table_name, table in self.mappings().items():
            for name, pair in table.items():
                with self.subTest(table=table_name, name=name):
                    rich, plain = pair
                    self.assertEqual(cells(rich), 1)
                    self.assertTrue(rich.isprintable())
                    self.assertFalse(unicodedata.category(rich).startswith(('C', 'M')))
                    self.assertFalse(unicodedata.combining(rich))

    def test_ascii_fallbacks_are_single_ascii_cells(self):
        for table_name, table in self.mappings().items():
            for name, (_, plain) in table.items():
                with self.subTest(table=table_name, name=name):
                    self.assertEqual(len(plain), 1)
                    self.assertTrue(plain.isascii())
                    self.assertTrue(plain.isprintable())

    def test_wide_emoji_variation_selectors_and_combining_marks_are_not_used(self):
        risky = ('⚡', '🌥', '🌨', '𖣂', '\ufe0e', '\ufe0f', '\u08ea')
        rendered = ''.join(rich + plain
                           for table in self.mappings().values()
                           for rich, plain in table.values())
        for char in risky:
            self.assertNotIn(char, rendered)

    def test_requested_glyph_audit_documents_what_is_safe(self):
        for glyph in ('↟', '⛈', '☀', '⚘', '☾', '♱', '❄'):
            with self.subTest(glyph=glyph):
                self.assertEqual(cells(glyph), 1)
                self.assertTrue(glyph.isprintable())
                self.assertFalse(unicodedata.combining(glyph))
        # Wide emoji and braille blank are not suitable for a fixed-width cell.
        self.assertEqual(cells('⚡'), 2)
        for emoji in ('🌥', '🌨'):
            # Python's table says 1, but emoji presentations may occupy 2 cells.
            self.assertEqual(cells(emoji), 1)
            self.assertGreaterEqual(ord(emoji), 0x1F000)
        self.assertEqual(cells('⠀'), 1)
        self.assertEqual(unicodedata.name('⠀'), 'BRAILLE PATTERN BLANK')
        # Variation selectors and combining marks would silently add 0 cells.
        for text in ('☀︎', '⚡︎', '𖣂࣪'):
            with self.subTest(text=text):
                self.assertTrue(any(unicodedata.combining(ch) or
                                    unicodedata.category(ch) == 'Mn'
                                    for ch in text))

    def test_player_portrait_keeps_identity_narrow_and_has_ascii_fallback(self):
        for avatar in ('@', '&', 'o'):
            for unicode in (True, False):
                with self.subTest(avatar=avatar, unicode=unicode):
                    lines = artwork.player_portrait(avatar, unicode=unicode)
                    self.assertEqual(len(lines), 6)
                    self.assertTrue(all(cells(line) <= 11 for line in lines))
                    self.assertTrue(any(avatar in line for line in lines))
                    if not unicode:
                        self.assertTrue(all(line.isascii() for line in lines))

    def test_meter_and_icons_have_stable_width(self):
        for unicode in (True, False):
            self.assertEqual(cells(artwork.pips(2, unicode=unicode)), 5)
            self.assertEqual(cells(artwork.symbol('coin', unicode=unicode)), 1)
            self.assertEqual(cells(artwork.weather_icon('rainy', unicode=unicode)), 1)
            self.assertEqual(cells(artwork.quest_icon('plant', unicode=unicode)), 1)
            self.assertEqual(cells(artwork.stat_icon('farming', unicode=unicode)), 1)


if __name__ == '__main__':
    unittest.main()
