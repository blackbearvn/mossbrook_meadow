"""Presentation can enrich the map without changing its rules or state."""

import codecs
import io
import random
import unicodedata
import unittest
from dataclasses import asdict, FrozenInstanceError
from types import SimpleNamespace

from farmgame import map_art, world
from farmgame.catalog import CROPS
from farmgame.identity import AVATARS, OUTFITS
from farmgame.model import Farm, GameError, Plot
from farmgame.tutorial import TutorialState
from farmgame.villagers import NPCS


def narrow_printable(text):
    """Independent cell-width check, matching the terminal's Unicode rules."""
    return (len(text) == 1 and text.isprintable()
            and not unicodedata.category(text).startswith(('C', 'M'))
            and unicodedata.east_asian_width(text) not in 'WF')


class MapArtTests(unittest.TestCase):
    def test_player_keeps_identity_and_facing_over_crops_and_routes(self):
        farm = Farm(player_x=26, player_y=42)
        farm.plots['A1'] = Plot(crop='ca_rot', dead=True)
        arrows = {'up': ('↑', '^'), 'down': ('↓', 'v'),
                  'left': ('←', '<'), 'right': ('→', '>')}
        for avatar in AVATARS:
            farm.avatar = avatar
            for outfit in OUTFITS:
                farm.outfit = outfit
                for facing, symbols in arrows.items():
                    farm.facing = facing
                    for rich, arrow in zip((True, False), symbols):
                        with self.subTest(avatar=avatar, outfit=outfit,
                                          facing=facing, rich=rich):
                            cell = map_art.map_cell(farm, 26, 42, unicode=rich,
                                                    path={(26, 42)})
                            self.assertEqual((cell.glyph, cell.color, cell.tail),
                                             (avatar, outfit, arrow))
                            self.assertTrue(cell.bold)

    def test_npc_numbers_survive_routes_and_player_has_highest_priority(self):
        farm = Farm()
        for npc in NPCS.values():
            with self.subTest(npc=npc.id):
                point = npc.position
                cell = map_art.map_cell(farm, *point, path={point})
                self.assertEqual(cell.glyph, npc.glyph)
                self.assertEqual(cell.color, 'magenta')
                farm.player_x, farm.player_y = point
                self.assertEqual(map_art.map_cell(farm, *point).glyph, farm.avatar)
                farm.player_x, farm.player_y = 10, 7

    def test_crop_stages_are_distinct_and_take_priority_over_guidance(self):
        farm = Farm()
        stages = (Plot(), Plot(crop='ca_rot'), Plot(crop='ca_rot', growth=1),
                  Plot(crop='ca_rot', growth=2), Plot(crop='ca_rot', dead=True))
        glyphs = []
        ascii_glyphs = []
        for plot in stages:
            farm.plots['A1'] = plot
            rich = map_art.map_cell(farm, 26, 42, path={(26, 42)})
            plain = map_art.map_cell(farm, 26, 42, unicode=False, path={(26, 42)})
            glyphs.append(rich.glyph)
            ascii_glyphs.append(plain.glyph)
            self.assertNotEqual(rich.glyph, '·')
        self.assertEqual(len(set(glyphs)), 5)
        self.assertEqual(len(set(ascii_glyphs)), 5)
        self.assertEqual(map_art.map_cell(farm, 26, 42).color, 'red')
        farm.plots['A1'] = stages[3]
        self.assertEqual(map_art.map_cell(farm, 26, 42).color, 'yellow')

    def test_water_state_includes_weather_and_sprinklers_without_advancing_growth(self):
        farm = Farm()
        for plot in (Plot(), Plot(crop='ca_rot'), Plot(crop='ca_rot', growth=1)):
            farm.plots['A1'] = plot
            for weather, sprinkler, watered in (('sunny', False, True),
                                                 ('rainy', False, False),
                                                 ('sunny', True, False)):
                with self.subTest(plot=plot, weather=weather, sprinkler=sprinkler):
                    farm.weather, farm.sprinkler = weather, sprinkler
                    plot.watered = watered
                    before = asdict(farm)
                    self.assertEqual(map_art.map_cell(farm, 26, 42).color, 'cyan')
                    for rich in (True, False):
                        self.assertEqual(map_art.map_cell(farm, 26, 42,
                                                          unicode=rich).tail, '~')
                    self.assertEqual(asdict(farm), before)

    def test_real_watering_marks_seedlings_and_growing_crops_without_color(self):
        for rich in (True, False):
            for growing in (False, True):
                with self.subTest(rich=rich, growing=growing):
                    farm = Farm()
                    farm.plant('A1', 'ca_rot')
                    if growing:
                        farm.water('A1')
                        farm.sleep('sunny')
                    dry = map_art.map_cell(farm, 26, 42, unicode=rich)
                    self.assertEqual(dry.tail, ' ')
                    farm.water('A1')
                    before = asdict(farm)
                    wet = map_art.map_cell(farm, 26, 42, unicode=rich,
                                           path={(26, 42)})
                    self.assertEqual(wet.glyph, dry.glyph)
                    self.assertEqual(wet.tail, '~')
                    self.assertNotEqual(wet.glyph + wet.tail, dry.glyph + dry.tail)
                    self.assertIn('~ ướt', ' '.join(map_art.map_legend(farm,
                                                                    unicode=rich)))
                    self.assertEqual(asdict(farm), before)
                    farm.player_x, farm.player_y, farm.facing = 26, 42, 'right'
                    player = map_art.map_cell(farm, 26, 42, unicode=rich)
                    self.assertEqual(player.tail, '→' if rich else '>')

    def test_wet_marker_does_not_replace_ripe_or_dead_crop_symbols(self):
        farm = Farm(weather='rainy', sprinkler=True)
        for plot in (Plot(crop='ca_rot', growth=2), Plot(crop='ca_rot', dead=True)):
            farm.plots['A1'] = plot
            for rich in (True, False):
                cell = map_art.map_cell(farm, 26, 42, unicode=rich)
                self.assertEqual(cell.tail, ' ')

    def test_guidance_only_changes_walkable_cells_not_obstacles_or_doors(self):
        farm = Farm()
        for point in ((9, 7), (11, 8), (33, 4)):
            self.assertTrue(world.walkable(farm.area, *point, farm.size))
            self.assertEqual(map_art.map_cell(farm, *point, path={point}).glyph, '·')
            self.assertEqual(map_art.map_cell(farm, *point, path={point},
                                              unicode=False).glyph, '+')
        for point in ((0, 7), (2, 1), world.HOME_DOOR, (26, 10)):
            self.assertFalse(world.walkable(farm.area, *point, farm.size))
            self.assertEqual(map_art.map_cell(farm, *point, path={point}),
                             map_art.map_cell(farm, *point))

    def test_roads_follow_real_junctions_and_extend_only_to_right_connections(self):
        farm = Farm(player_x=4, player_y=4)
        for point, glyph, tail in (((10, 7), '┼', '─'),
                                    ((39, 7), '┬', '─'),
                                    ((26, 20), '│', ' '),
                                    ((11, 7), '─', '─'),
                                    ((29, 7), '─', ' '),
                                    ((7, 2), '│', ' ')):
            with self.subTest(point=point):
                self.assertEqual(world.tile_at('village', *point), '=')
                cell = map_art.map_cell(farm, *point)
                self.assertEqual((cell.glyph, cell.tail), (glyph, tail))
        farm.player_x, farm.player_y = 10, 7
        self.assertNotEqual(map_art.map_cell(farm, 10, 7).glyph, '┼')

    def test_building_art_fits_solid_footprints_and_preserves_usable_doors(self):
        farm = Farm()
        for left, top, right, bottom, door in (
                (2, 1, 6, 3, world.HOME_DOOR),
                (24, 1, 28, 3, world.SHOP_DOOR),
                (13, 4, 17, 6, world.BARN_DOOR)):
            with self.subTest(door=door):
                roof = ''.join(map_art.map_cell(farm, x, top).glyph
                               for x in range(left, right + 1))
                self.assertEqual(roof, '╱───╲')
                self.assertEqual(map_art.map_cell(farm, left, bottom).glyph, '└')
                self.assertEqual(map_art.map_cell(farm, right, bottom).glyph, '┘')
                self.assertEqual(map_art.map_cell(farm, *door).glyph,
                                 world.tile_at('village', *door))
                for y in range(top, bottom + 1):
                    for x in range(left, right + 1):
                        self.assertFalse(world.walkable('village', x, y))
                self.assertTrue(world.walkable('village', door[0], door[1] + 1))
        for point in ((1, 1), (7, 1), (12, 4), (18, 6), (23, 1), (29, 2)):
            self.assertIn(world.tile_at('village', *point), ('.', '='))
            self.assertNotIn(map_art.map_cell(farm, *point).glyph, '╱╲│└┘▣')

    def test_interior_walls_connect_and_furniture_matches_area(self):
        farm = Farm(area='home', player_x=8, player_y=7)
        for point, glyph in (((0, 0), '┌'), ((15, 0), '┐'),
                             ((0, 8), '└'), ((15, 8), '┘'),
                             ((0, 4), '│'), ((6, 0), '─'),
                             ((7, 8), '─'), ((9, 8), '─')):
            with self.subTest(point=point):
                self.assertEqual(map_art.map_cell(farm, *point).glyph, glyph)
        for point, rich, plain in ((world.TV, '▣', 'V'), (world.BED, '▰', 'Z'),
                                    (world.CHEST, '▤', 'C'), (world.EXIT, '⇥', 'D')):
            with self.subTest(furniture=point):
                self.assertEqual(map_art.map_cell(farm, *point).glyph, rich)
                self.assertEqual(map_art.map_cell(farm, *point, unicode=False).glyph,
                                 plain)
                self.assertFalse(world.walkable(farm.area, *point))

    def test_every_generated_cell_is_narrow_ascii_is_seven_bit_and_map_is_unchanged(self):
        colors = {'green', 'yellow', 'cyan', 'blue', 'magenta', 'red', 'white', 'dim',
                  'grass', 'forest', 'flower', 'soil', 'sand', 'lake', 'sea',
                  'path', 'stone', 'building', 'roof', 'furniture', 'door'}
        for area, width, height in (('village', 128, 64), ('home', 16, 9)):
            farm = Farm(area=area, player_x=8, player_y=7, size=6)
            for crop in CROPS:
                for growth in range(CROPS[crop].days + 1):
                    farm.plots['A1'] = Plot(crop=crop, growth=growth)
                    for rich in (True, False):
                        cell = map_art.map_cell(farm, 26, 42, unicode=rich)
                        self.assertTrue(narrow_printable(cell.glyph))
                        self.assertTrue(narrow_printable(cell.tail))
            original = world.terrain_grid(area, farm.size)
            for rich in (True, False):
                for y in range(height):
                    for x in range(width):
                        cell = map_art.map_cell(farm, x, y, unicode=rich)
                        if not narrow_printable(cell.glyph) or not narrow_printable(cell.tail):
                            self.fail(f'Invalid cell at {(area, x, y)}: {cell!r}')
                        self.assertIn(cell.color, colors)
                        if not rich:
                            self.assertTrue((cell.glyph + cell.tail).isascii())
            self.assertEqual(world.terrain_grid(area, farm.size), original)

    def test_beach_sand_lake_and_sea_have_distinct_semantic_colours(self):
        farm = Farm()
        sand = map_art.map_cell(farm, 107, 50)
        sea = map_art.map_cell(farm, 115, 50)
        lake = map_art.map_cell(farm, 45, 28)
        self.assertEqual((sand.color, sea.color, lake.color),
                         ('sand', 'sea', 'lake'))
        self.assertEqual(world.tile_at('village', 107, 50), 's')
        self.assertEqual(world.tile_at('village', 115, 50), 'S')
        self.assertTrue(world.walkable('village', 107, 50))
        self.assertFalse(world.walkable('village', 115, 50))
        self.assertIn('hồ/biển', map_art.map_legend(farm)[-1])

    def test_rendering_is_repeatable_and_does_not_mutate_farm_or_random_stream(self):
        farm = Farm(tutorial=TutorialState(status='active', step=6, plot='A1'))
        farm.plots['A1'] = Plot(crop='lua_mi', watered=True)
        farm.plots['B1'] = Plot(crop='ca_rot', dead=True)
        before = asdict(farm)
        rng_before = random.getstate()
        points = [(x, y) for y in range(64) for x in range(128)]
        forward = [map_art.map_cell(farm, *p) for p in points]
        backwards = [map_art.map_cell(farm, *p) for p in reversed(points)]
        self.assertEqual(forward, list(reversed(backwards)))
        map_art.map_legend(farm)
        map_art.map_legend(farm, unicode=False)
        self.assertEqual(asdict(farm), before)
        self.assertEqual(random.getstate(), rng_before)
        self.assertEqual(farm.daily.day, 0)
        self.assertFalse(farm.daily.tasks)
        grass = [forward[y * 128 + x] for y in range(14) for x in range(32)
                 if world.tile_at('village', x, y) == '.'
                 and (x, y) not in {npc.position for npc in NPCS.values()}]
        self.assertGreater(len({cell.glyph for cell in grass}), 1)
        self.assertGreater(sum(cell.glyph == ' ' for cell in grass), len(grass) / 2)
        self.assertTrue(all(cell.color == 'grass' for cell in grass))

    def test_invalid_coordinates_raise_world_errors_before_any_overlay(self):
        farm = Farm()
        for point in ((1.5, 7), (True, 7), (10, '7')):
            with self.subTest(point=point):
                with self.assertRaises(GameError) as expected:
                    world.tile_at(farm.area, *point, farm.size)
                with self.assertRaises(GameError) as actual:
                    map_art.map_cell(farm, *point)
                self.assertEqual(str(actual.exception), str(expected.exception))
        farm.area = 'moon'
        with self.assertRaises(GameError):
            map_art.map_cell(farm, farm.player_x, farm.player_y)
        farm.area, farm.size = 'village', 7
        with self.assertRaises(GameError):
            map_art.map_cell(farm, farm.player_x, farm.player_y)

    def test_outside_coordinates_remain_solid_and_have_a_safe_presentation(self):
        for area, width, height in (('village', 128, 64), ('home', 16, 9)):
            farm = Farm(area=area)
            for point in ((-1, 0), (width, 4), (3, -1), (3, height)):
                self.assertEqual(world.tile_at(area, *point), '#')
                cell = map_art.map_cell(farm, *point)
                self.assertTrue(narrow_printable(cell.glyph))
                self.assertTrue(narrow_printable(cell.tail))

    def test_cells_reject_variable_width_and_control_characters(self):
        for invalid in ('', 'ab', '界', '🌲', '\u0301', '\n', '\x1b', '\u200d'):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    map_art.MapCell(invalid)
                with self.assertRaises(ValueError):
                    map_art.MapCell('.', tail=invalid)
        cell = map_art.map_cell(Farm(), 10, 7)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            cell.glyph = 'x'
        self.assertFalse(hasattr(cell, '__dict__'))

    def test_overview_terrain_preserves_door_and_character_markers(self):
        for rich in (True, False):
            for marker in 'HMB12345@&o':
                self.assertEqual(map_art.terrain_glyph(marker, unicode=rich), marker)
            for tile in '.T~,:=#VZCD':
                glyph = map_art.terrain_glyph(tile, unicode=rich)
                self.assertTrue(narrow_printable(glyph))
                if not rich:
                    self.assertTrue(glyph.isascii())
        self.assertNotEqual(map_art.terrain_glyph('~'), '~')
        self.assertNotEqual(map_art.terrain_glyph('T'), 'T')

    def test_legend_is_compact_and_uses_symbols_from_the_rendered_map(self):
        for area in ('village', 'home'):
            farm = Farm(area=area, facing='left', avatar='&')
            for rich in (True, False):
                with self.subTest(area=area, rich=rich):
                    lines = map_art.map_legend(farm, unicode=rich)
                    self.assertIn(len(lines), (1, 2))
                    self.assertTrue(all(len(line) <= 80 for line in lines))
                    joined = ' '.join(lines)
                    player = map_art.map_cell(farm, farm.player_x, farm.player_y,
                                              unicode=rich)
                    self.assertIn(player.glyph + player.tail, joined)
                    if area == 'home':
                        for point in (world.TV, world.BED, world.CHEST, world.EXIT):
                            self.assertIn(map_art.map_cell(farm, *point,
                                                          unicode=rich).glyph, joined)
                    if not rich:
                        symbols = ''.join(c for c in joined if not c.isalpha())
                        self.assertTrue(symbols.isascii(), repr(symbols))

    def test_ascii_forest_meadow_and_building_use_a_richer_palette(self):
        farm = Farm()
        trees = {map_art.map_cell(farm, x, y, unicode=False).glyph
                 for y in range(36) for x in range(80)
                 if world.tile_at('village', x, y) == 'T'}
        flowers = {map_art.map_cell(farm, x, y, unicode=False).glyph
                   for y in range(36) for x in range(80)
                   if world.tile_at('village', x, y) == ','}
        self.assertTrue(trees <= set('TYt'))
        self.assertGreater(len(trees), 1)
        self.assertTrue(flowers <= set(',%*'))
        self.assertGreater(len(flowers), 1)
        roof = ''.join(map_art.map_cell(farm, x, 1, unicode=False).glyph
                       for x in range(2, 7))
        self.assertEqual(roof, '/---\\')

    def test_ascii_crop_and_guidance_symbols_stay_distinct(self):
        farm = Farm()
        farm.plots['A1'] = Plot(crop='ca_rot', growth=1)
        self.assertEqual(map_art.map_cell(farm, 26, 42, unicode=False).glyph, 't')
        self.assertEqual(map_art.map_cell(farm, 9, 7, unicode=False,
                                          path={(9, 7)}).glyph, '+')
        self.assertIn('t lớn', ' '.join(map_art.map_legend(farm, unicode=False)))

    def test_doors_join_walls_and_lake_tiles_fill_both_map_columns(self):
        farm = Farm()
        for door, glyph in ((world.HOME_DOOR, 'H'), (world.SHOP_DOOR, 'M'),
                            (world.BARN_DOOR, 'B')):
            with self.subTest(door=door):
                rich = map_art.map_cell(farm, *door)
                plain = map_art.map_cell(farm, *door, unicode=False)
                self.assertEqual((rich.glyph, rich.tail), (glyph, '─'))
                self.assertEqual((plain.glyph, plain.tail), (glyph, '-'))
                self.assertTrue(rich.bold)
        home = Farm(area='home', player_x=8, player_y=7)
        rich = map_art.map_cell(home, *world.EXIT)
        plain = map_art.map_cell(home, *world.EXIT, unicode=False)
        self.assertEqual((rich.glyph, rich.tail), ('⇥', '─'))
        self.assertEqual((plain.glyph, plain.tail), ('D', '-'))
        self.assertEqual(world.tile_at('village', 45, 10), '~')
        rich = map_art.map_cell(farm, 45, 10)
        plain = map_art.map_cell(farm, 45, 10, unicode=False)
        self.assertEqual((rich.glyph, rich.tail), ('≈', '≈'))
        self.assertEqual((plain.glyph, plain.tail), ('~', '~'))

    def test_unicode_detection_checks_complete_palette_encoding_and_dumb_term(self):
        for encoding, term, expected in (('utf-8', 'xterm-256color', True),
                                         ('utf-16', 'screen', True),
                                         ('ascii', 'xterm', False),
                                         ('iso-8859-1', 'xterm', False),
                                         ('cp437', 'xterm', False),
                                         ('utf-8', 'dumb', False)):
            with self.subTest(encoding=encoding, term=term):
                buffer = io.BytesIO()
                with io.TextIOWrapper(buffer, encoding=encoding) as stream:
                    self.assertEqual(map_art.supports_unicode(stream, term=term), expected)
                    self.assertEqual(buffer.getvalue(), b'')
        self.assertFalse(map_art.supports_unicode(io.StringIO(), term='xterm'))

    def test_unicode_detection_falls_back_when_only_a_frame_or_status_symbol_is_missing(self):
        for missing in '╭╮╰╯▱':
            with self.subTest(missing=missing):
                # A terminal encoding may carry the map but reject one HUD glyph.
                def encode(text, errors='strict'):
                    if missing in text:
                        offset = text.index(missing)
                        raise UnicodeEncodeError('partial-map', text, offset,
                                                 offset + 1, 'unsupported symbol')
                    return codecs.utf_8_encode(text, errors)

                def search(name):
                    if name == 'partial_map':
                        return codecs.CodecInfo(name=name, encode=encode,
                                                decode=codecs.utf_8_decode)
                    return None

                codecs.register(search)
                try:
                    stream = SimpleNamespace(encoding='partial-map')
                    self.assertFalse(map_art.supports_unicode(stream, term='xterm'))
                finally:
                    codecs.unregister(search)


if __name__ == '__main__':
    unittest.main()
