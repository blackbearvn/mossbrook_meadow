"""Village navigation and contextual interactions, independent of a terminal."""
import unittest
from collections import deque
from dataclasses import asdict

from farmgame.model import Farm, GameError
from farmgame import world


class WorldTests(unittest.TestCase):
    def test_movement_changes_position_and_facing_without_spending_day_or_energy(self):
        farm = Farm()
        before = (farm.day, farm.energy)
        self.assertTrue(world.move(farm, 'left'))
        self.assertEqual((farm.player_x, farm.player_y, farm.facing), (9, 7, 'left'))
        self.assertEqual((farm.day, farm.energy), before)

    def test_blocked_door_turns_player_without_moving(self):
        farm = Farm(player_x=4, player_y=4)
        self.assertFalse(world.move(farm, 'up'))
        self.assertEqual((farm.player_x, farm.player_y, farm.facing), (4, 4, 'up'))
        self.assertEqual(world.context(farm)[0], 'home')

    def test_walls_water_trees_doors_and_furniture_block_walking(self):
        for area, point, tile in (
            ('village', (4, 3), 'H'), ('village', (15, 6), 'B'),
            ('village', (26, 3), 'M'), ('village', (26, 10), '~'),
            ('village', (0, 7), 'T'), ('home', (0, 0), '#'),
            ('home', (3, 2), 'V'), ('home', (12, 2), 'Z'),
            ('home', (3, 5), 'C'), ('home', (8, 8), 'D')):
            with self.subTest(area=area, point=point):
                self.assertEqual(world.tile_at(area, *point), tile)
                self.assertFalse(world.walkable(area, *point))

    def test_edges_cannot_be_crossed(self):
        for area, width, height in (
                ('village', world.VILLAGE_WIDTH, world.VILLAGE_HEIGHT),
                ('home', world.HOME_WIDTH, world.HOME_HEIGHT)):
            for x, y in ((-1, 1), (1, -1), (width, 1), (1, height)):
                with self.subTest(area=area, x=x, y=y):
                    self.assertFalse(world.walkable(area, x, y))
                    self.assertEqual(world.tile_at(area, x, y), '#')
        farm = Farm(area='home', player_x=1, player_y=1)
        self.assertFalse(world.move(farm, 'left'))
        self.assertFalse(world.move(farm, 'up'))
        self.assertEqual((farm.player_x, farm.player_y), (1, 1))

    def test_plot_mapping_tracks_land_expansion(self):
        for x, y, size, expected in (
            (26, 42, 4, 'A1'), (29, 45, 4, 'D4'), (30, 42, 4, None),
            (30, 42, 5, 'E1'), (31, 47, 6, 'F6'), (25, 42, 6, None),
            (26, 48, 6, None), (3, 4, 6, None)):
            self.assertEqual(world.plot_at(x, y, size), expected)
        self.assertEqual(world.tile_at('village', 31, 47, 6), ':')
        self.assertTrue(world.walkable('village', 31, 47, 6))

    def test_target_plot_prefers_facing_then_underfoot_and_never_home(self):
        farm = Farm(player_x=27, player_y=43, facing='right')
        self.assertEqual(world.target_plot(farm), 'C2')
        farm.player_x, farm.player_y, farm.facing = 26, 42, 'left'
        self.assertEqual(world.target_plot(farm), 'A1')
        farm.area, farm.player_x, farm.player_y = 'home', 3, 4
        self.assertIsNone(world.target_plot(farm))

    def test_enter_and_leave_home_require_adjacent_matching_door(self):
        farm = Farm()
        before = asdict(farm)
        with self.assertRaises(GameError):
            world.enter_home(farm)
        self.assertEqual(asdict(farm), before)
        farm.player_x, farm.player_y = 4, 4
        world.enter_home(farm)
        self.assertEqual((farm.area, farm.player_x, farm.player_y), ('home', 8, 7))
        self.assertTrue(world.walkable(farm.area, farm.player_x, farm.player_y))
        self.assertEqual(world.context(farm)[0], 'exit')
        with self.assertRaises(GameError):
            world.enter_home(farm)
        farm.player_x, farm.player_y = 8, 6
        with self.assertRaises(GameError):
            world.leave_home(farm)
        farm.player_y = 7
        world.leave_home(farm)
        self.assertEqual((farm.area, farm.player_x, farm.player_y), ('village', 4, 4))
        with self.assertRaises(GameError):
            world.leave_home(farm)

    def test_landmark_adjacency_is_orthogonal_and_area_specific(self):
        farm = Farm(player_x=4, player_y=4)
        self.assertTrue(world.is_near(farm, 'home'))
        self.assertFalse(world.is_near(farm, 'chest'))
        farm.player_x = 5
        self.assertFalse(world.is_near(farm, 'home'))
        farm.area, farm.player_x, farm.player_y = 'home', 3, 3
        self.assertTrue(world.is_near(farm, 'tv'))
        self.assertFalse(world.is_near(farm, 'home'))

    def test_west_bank_is_a_reachable_fishing_spot(self):
        farm = Farm(player_x=21, player_y=9)
        self.assertTrue(world.walkable('village', 21, 9))
        self.assertTrue(world.is_near(farm, 'water'))
        self.assertEqual(world.context(farm)[0], 'fish')

    def test_context_covers_furniture_shops_fishing_and_forest(self):
        for area, x, y, expected in (
            ('home', 3, 3, 'tv'), ('home', 12, 3, 'bed'),
            ('home', 3, 6, 'chest'), ('village', 15, 7, 'barn'),
            ('village', 26, 4, 'shop'), ('village', 26, 7, 'fish'),
            ('village', 1, 7, 'forest'), ('village', 10, 7, 'none'),
            ('village', 27, 43, 'plot'), ('village', 4, 5, 'none')):
            farm = Farm(area=area, player_x=x, player_y=y)
            action, label = world.context(farm)
            self.assertEqual(action, expected)
            self.assertTrue(label)

    def test_all_landmarks_fields_and_home_furniture_are_reachable(self):
        for size in (4, 5, 6):
            reachable = self.reachable('village', (10, 7), size)
            farm = Farm(size=size)
            for kind in ('home', 'barn', 'shop', 'water', 'forest'):
                self.assert_reachable_interaction(farm, reachable, kind)
            for y in range(42, 42 + size):
                for x in range(26, 26 + size):
                    self.assertIn((x, y), reachable)
        reachable = self.reachable('home', (8, 7), 4)
        farm = Farm(area='home')
        for kind in ('tv', 'bed', 'chest', 'exit'):
            self.assert_reachable_interaction(farm, reachable, kind)

    def assert_reachable_interaction(self, farm, reachable, kind):
        # Reuse one farm: constructing a whole inventory at every BFS tile
        # makes proximity checks needlessly expensive on the expanded map.
        for farm.player_x, farm.player_y in reachable:
            if world.is_near(farm, kind):
                return
        self.fail(f'No reachable interaction: {kind}')

    @staticmethod
    def reachable(area, start, size):
        width, height = ((world.LEGACY_WIDTH, world.LEGACY_HEIGHT)
                         if area == 'village' else (world.HOME_WIDTH, world.HOME_HEIGHT))
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (0 <= point[0] < width and 0 <= point[1] < height
                        and point not in seen
                        and world.walkable(area, *point, size)):
                    seen.add(point)
                    queue.append(point)
        return seen

    def test_invalid_inputs_raise_game_error_without_changing_farm(self):
        farm = Farm()
        before = asdict(farm)
        for action in (lambda: world.move(farm, 'north'),
                       lambda: world.is_near(farm, 'spaceship'),
                       lambda: world.tile_at('moon', 1, 1),
                       lambda: world.walkable('home', 1.5, 1),
                       lambda: world.plot_at(3, 4, 7)):
            with self.assertRaises(GameError):
                action()
        self.assertEqual(asdict(farm), before)

    def test_location_names_reflect_area(self):
        self.assertIn('làng', world.location_name(Farm()).lower())
        self.assertIn('nhà', world.location_name(Farm(area='home')).lower())

    def test_expanded_map_keeps_old_village_with_retired_plots_and_gates(self):
        self.assertEqual((world.VILLAGE_WIDTH, world.VILLAGE_HEIGHT), (1280, 720))
        original = (
            'TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT',
            'T.#####...=..TT...TT....#####..T',
            'T.#####=..=.............#####..T',
            'T.##H##=================##M##..T',
            'T..::::====..#####........=....T',
            'T..::::...=..#####........=....T',
            'T..::::...=..##B##........=....T',
            'T.=::::=======================.T',
            'T.........=.............~~~~~..T',
            'T.........=...........~~~~~~~~.T',
            'T.TT......=......TTTT.~~~~~~~~.T',
            'T.TT......=......TTTT.~~~~~~~~.T',
            'T.........=......TTTT..........T',
            'TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT',
        )
        gates = {(31, 7), (10, 13), (26, 13)}
        for size in (4, 5, 6):
            for y, row in enumerate(original):
                for x, expected in enumerate(row):
                    if (x, y) in gates:
                        expected = '='
                    elif expected == ':':
                        expected = '=' if y == 4 and x >= 4 or y == 7 else '.'
                    self.assertEqual(world.tile_at('village', x, y, size), expected,
                                     (size, x, y))

    def test_new_regions_landmarks_bridges_and_npcs_are_reachable(self):
        from farmgame.villagers import NPCS, npc_at

        self.assertEqual(set(world.LANDMARKS),
                         {'farm', 'home', 'shop', 'barn', 'meadow', 'square',
                          'forest', 'lake', 'hill', 'valley', 'tea', 'floodplain',
                          'beach', 'mine'})
        # The flood fill excludes occupied NPC tiles, like actual movement.
        seen = {(10, 7)}
        queue = deque(seen)
        while queue:
            x, y = queue.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (0 <= point[0] < world.LEGACY_WIDTH
                        and 0 <= point[1] < world.LEGACY_HEIGHT
                        and point not in seen and world.walkable('village', *point)
                        and npc_at(*point) is None):
                    seen.add(point)
                    queue.append(point)
        for name, (_, (x, y)) in world.LANDMARKS.items():
            self.assertTrue((x, y) in seen or any(
                point in seen for point in ((x-1, y), (x+1, y), (x, y-1), (x, y+1))),
                name)
        for npc in NPCS.values():
            x, y = npc.position
            self.assertTrue(world.walkable('village', x, y), npc.id)
            self.assertTrue(any(point in seen for point in
                                ((x-1, y), (x+1, y), (x, y-1), (x, y+1))), npc.id)
        for y in (7, 21):
            for x in range(44, 49):
                self.assertEqual(world.tile_at('village', x, y), '=')
                self.assertIn((x, y), seen)
        for y in range(1, world.LEGACY_HEIGHT - 1):
            for x in range(45, 48):
                self.assertEqual(world.tile_at('village', x, y),
                                 'T' if y == 35 else '=' if y in (7, 21, 41, 55) else '~')
        self.assertEqual(world.tile_at('village', 60, 28), '~')
        self.assertTrue(any(world.tile_at('village', x, y) == ','
                            for y in range(3, 17) for x in range(32, 45)))
        self.assertTrue(world.walkable('village', 40, 10))

    def test_npcs_block_movement_but_static_walkability_allows_old_saves(self):
        from farmgame.villagers import NPCS

        for npc in NPCS.values():
            x, y = npc.position
            dx, dy, approach, leave = next(
                option for option in ((-1, 0, 'right', 'left'),
                                      (1, 0, 'left', 'right'),
                                      (0, -1, 'down', 'up'),
                                      (0, 1, 'up', 'down'))
                if world.walkable('village', x + option[0], y + option[1]))
            farm = Farm(player_x=x+dx, player_y=y+dy)
            self.assertTrue(world.walkable('village', x, y))
            self.assertFalse(world.move(farm, approach), npc.id)
            self.assertEqual((farm.player_x, farm.player_y), (x+dx, y+dy))
            self.assertEqual(world.context(farm),
                             ('npc', f'E: trò chuyện với {npc.name}'))
            farm.player_x, farm.player_y = x, y
            self.assertEqual(world.context(farm)[0], 'npc')
            self.assertTrue(world.move(farm, leave), npc.id)

    def test_context_resolves_buildings_and_prioritizes_npcs_over_terrain(self):
        farm = Farm(player_x=26, player_y=4)
        self.assertEqual(world.context(farm)[0], 'shop')
        # Bác Tư stands by the old lake: conversation wins over fishing.
        farm = Farm(player_x=30, player_y=9)
        self.assertTrue(world.is_near(farm, 'water'))
        self.assertEqual(world.context(farm)[0], 'npc')

    def test_wider_world_is_1280x720_and_connected_to_the_old_village(self):
        from farmgame import pages

        self.assertEqual((world.VILLAGE_WIDTH, world.VILLAGE_HEIGHT), (1280, 720))
        for point in ((127, 55), (128, 55), (26, 63), (26, 64),
                      (39, 63), (39, 64), (320, 300), (640, 500),
                      (960, 700), (1136, 55)):
            self.assertEqual(world.tile_at('village', *point), '=', point)
            self.assertTrue(world.walkable('village', *point), point)
        for page in pages.PAGES.values():
            self.assertTrue(world.walkable('village', *page.spawn), page.key)
        farm = Farm(player_x=800, player_y=300)
        self.assertIn('Hồ Nước Sâu', world.location_name(farm))
        farm.map_pages = True
        self.assertEqual(world.location_name(farm), 'Rừng Già')

    def test_location_names_identify_all_new_regions(self):
        for point, label in (((10, 7), 'Nông trại'), ((39, 10), 'Đồng Hoa'),
                             ((55, 20), 'Quảng trường'), ((20, 25), 'Rừng Thông'),
                             ((53, 28), 'Hồ Sen'), ((72, 6), 'Đồi Gió'),
                             ((27, 41), 'Cánh đồng'), ((26, 42), 'Cánh đồng'),
                             ((110, 50), 'Bãi Biển'),
                             ((96, 22), 'Thung Lũng Đông'), ((110, 10), 'Đồi Trà'),
                             ((100, 50), 'Bãi Bồi')):
            farm = Farm(player_x=point[0], player_y=point[1])
            self.assertEqual(world.location_name(farm), f'Làng Mossbrook Meadow / {label}')

    def test_old_static_walkable_positions_still_load_at_all_field_sizes(self):
        # Row bitmasks captured from the previous 80x36 map (all sizes).
        old_rows = (
            '0x0', '0x7fffffff1fff60f39f82', '0x7fffffff1fff60ffff82',
            '0x6fdfffff1fff60ffff82', '0x7fffffff1fff7ffc1ffe', '0x7fffffff1fff7ffc1ffe',
            '0x6fdfffff1fff7ffc1ffe', '0x7ffffffffffffffffffe', '0x7fffffff1fff60fffffe',
            '0x6fdfffff1fff403ffffe', '0x7fffffff1fff4021fff2', '0x7fffffff1fff4021fff2',
            '0x7fffffff1fff7fe1fffe', '0x7fffffff1fff04000400', '0x7fffffff1ffffffffffe',
            '0x7fffffff1ffffffffffe', '0x7fffffff1ffffffffffe', '0x7fffffff1ff99ccc6632',
            '0x7fffffff1ffb3598cc66', '0x7fffffff1ffe67319cce', '0x7fffffff1ffcc663359a',
            '0x7fffffffffffffffff32', '0x7fffffff1ffb199cc662', '0x7fffffff1ffe33198cc6',
            '0x7fffffff1ffc6633198e', '0x7fffffff1fffffffff1a', '0x7e00003f1ff998dc6632',
            '0x7e00003f1ffb3198cc66', '0x7e00003f1ffe633198ce', '0x7e00003f1ffcc673319a',
            '0x7e00003f1ff98cd66332', '0x7e00003f1ffb199cc662', '0x7fffffff1ffe33198cc6',
            '0x7fffffff1ffc6633198e', '0x7fffffff1ffffffffffe', '0x0',
        )
        for size in (4, 5, 6):
            for y, row in enumerate(old_rows):
                mask = int(row, 16)
                for x in range(80):
                    if mask & (1 << x):
                        self.assertTrue(world.walkable('village', x, y, size),
                                        (size, x, y))

    def test_fields_are_far_from_home_and_connected_by_a_road(self):
        from farmgame.villagers import NPCS

        self.assertEqual(world.LANDMARKS['farm'], ('Cánh đồng', (27, 41)))
        for size in (4, 5, 6):
            seen = self.reachable('village', (4, 4), size)
            for y in range(42, 42 + size):
                for x in range(26, 26 + size):
                    self.assertGreater(abs(x - 4) + abs(y - 3), 50)
                    self.assertIn((x, y), seen)
                    self.assertEqual(world.tile_at('village', x, y, size), ':')
                    self.assertNotIn((x, y), [npc.position for npc in NPCS.values()])
            for x, y in ((25, 41), (32, 41), (25, 48), (32, 48)):
                self.assertIn((x, y), seen)
        # Follow a useful path from the house, through the old southern gate.
        route = ([(x, 4) for x in range(4, 11)]
                 + [(10, y) for y in range(4, 22)]
                 + [(x, 21) for x in range(10, 27)]
                 + [(26, y) for y in range(21, 42)])
        for point in route:
            self.assertEqual(world.tile_at('village', *point), '=')

    def test_old_fields_have_no_farming_interaction(self):
        for size in (4, 5, 6):
            for y in range(4, 10):
                for x in range(3, 9):
                    farm = Farm(size=size, player_x=x, player_y=y)
                    self.assertIsNone(world.target_plot(farm))
                    self.assertNotEqual(world.context(farm)[0], 'plot')

    def test_new_landmarks_share_a_continuous_road_from_home(self):
        seen = {(4, 4)}
        queue = deque(seen)
        while queue:
            x, y = queue.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point not in seen and world.tile_at('village', *point) == '=':
                    seen.add(point)
                    queue.append(point)
        for name in ('farm', 'valley', 'tea', 'floodplain'):
            self.assertIn(world.LANDMARKS[name][1], seen, name)
        for point in ((79, 7), (79, 21), (79, 32), (26, 35), (39, 35)):
            self.assertIn(point, seen)
        for y, start_x in ((7, 75), (21, 70), (32, 73)):
            for x in range(start_x, 80):
                self.assertEqual(world.tile_at('village', x, y), '=')
        for y in range(32, 36):
            self.assertEqual(world.tile_at('village', 39, y), '=')

    def test_new_regions_have_roads_and_bridges_at_both_rivers(self):
        for y in (7, 21, 41, 55):
            for x in range(90, 93):
                self.assertEqual(world.tile_at('village', x, y), '=')
        for y in (41, 55):
            for x in range(45, 48):
                self.assertEqual(world.tile_at('village', x, y), '=')
        for point in ((91, 10), (91, 30), (91, 50)):
            self.assertEqual(world.tile_at('village', *point), '~')


if __name__ == '__main__':
    unittest.main()
