"""Shared routes checked against an independent queue-based BFS oracle."""
from collections import deque
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from farmgame import tutorial, villagers, world
from farmgame.model import Farm, GameError


DIRECTIONS = ((0, -1, 'up'), (0, 1, 'down'), (-1, 0, 'left'), (1, 0, 'right'))


def bfs_distance(farm, goal):
    """Use only movement/context rules, with no planner helpers or heuristics."""
    start = farm.player_x, farm.player_y, farm.facing
    queue = deque([(start, 0)])
    seen = {start}
    probe = SimpleNamespace(area=farm.area, size=farm.size)
    while queue:
        (x, y, facing), distance = queue.popleft()
        probe.player_x, probe.player_y, probe.facing = x, y, facing
        if goal(probe):
            return distance
        for dx, dy, direction in DIRECTIONS:
            step = x + dx, y + dy, direction
            nx, ny = step[:2]
            # The oracle is used for the original village routes; bounding it
            # keeps proving an intentional dead end cheap on the 1280 x 720 map.
            inside = 0 <= nx < world.LEGACY_WIDTH and 0 <= ny < world.LEGACY_HEIGHT
            if (inside and step not in seen
                    and world.walkable(farm.area, *step[:2], farm.size)
                    and villagers.npc_at(*step[:2], farm.area) is None):
                seen.add(step)
                queue.append((step, distance + 1))
    return None


class NavigationTests(unittest.TestCase):
    @staticmethod
    def route(farm, area, target, *, kind=''):
        # Missing shared routing fails as a contract assertion during RED.
        import importlib.util
        if importlib.util.find_spec('farmgame.navigation') is None:
            raise AssertionError('The shared navigation.route API is missing')
        from farmgame.navigation import route
        return route(farm, area, target, kind=kind)

    def follow(self, farm, path):
        for x, y in path:
            delta = x - farm.player_x, y - farm.player_y
            direction = next((name for dx, dy, name in DIRECTIONS if (dx, dy) == delta), None)
            self.assertIsNotNone(direction, 'Each path entry must be a real orthogonal move')
            self.assertTrue(world.move(farm, direction), (farm.area, (x, y)))

    def assert_shortest(self, farm, area, target, kind, goal):
        before = deepcopy(farm)
        expected = bfs_distance(farm, goal)
        actual_target, path, key = self.route(farm, area, target, kind=kind)
        self.assertEqual(farm, before, 'Planning must not mutate the save state')
        self.assertEqual(actual_target, target)
        self.assertIsInstance(path, tuple)
        if expected is None:
            self.assertEqual((path, key), ((), 'M'))
            return
        self.assertEqual(len(path), expected)
        if path:
            delta = path[0][0] - farm.player_x, path[0][1] - farm.player_y
            self.assertEqual(key, {(0, -1): 'W / ↑', (0, 1): 'S / ↓',
                                   (-1, 0): 'A / ←', (1, 0): 'D / →'}[delta])
        else:
            self.assertEqual(key, 'E')
        self.follow(farm, path)
        self.assertTrue(goal(farm))
        self.assertEqual(self.route(farm, area, target, kind=kind)[1:], ((), 'E'))

    def test_tile_goal_reaches_the_exact_point(self):
        farm = Farm()
        self.assert_shortest(farm, 'village', (11, 7), 'tile',
                             lambda f: (f.player_x, f.player_y) == (11, 7))
        self.assertEqual((farm.player_x, farm.player_y), (11, 7))

    def test_routes_match_bfs_across_streams_and_regions(self):
        for start, target in (((10, 7), (110, 10)), ((110, 21), (26, 41)),
                              ((100, 55), (72, 6)), ((26, 41), (20, 25))):
            with self.subTest(start=start, target=target):
                farm = Farm(player_x=start[0], player_y=start[1])
                self.assert_shortest(farm, 'village', target, 'tile',
                                     lambda f, t=target: (f.player_x, f.player_y) == t)

    def test_every_plot_in_four_five_and_six_fields_is_actionable_and_shortest(self):
        for size in (4, 5, 6):
            for row in range(size):
                for col in range(size):
                    coordinate = f'{chr(65 + col)}{row + 1}'
                    target = 26 + col, 42 + row
                    with self.subTest(size=size, coordinate=coordinate):
                        farm = Farm(size=size, player_x=26, player_y=41)
                        def goal(f, t=target, c=coordinate):
                            return (abs(f.player_x - t[0]) + abs(f.player_y - t[1]) <= 1
                                    and world.target_plot(f) == c
                                    and world.context(f)[0] == 'plot')
                        self.assert_shortest(farm, 'village', target, 'plot', goal)

    def test_wrong_facing_underfoot_needs_real_steps_to_select_middle_plot(self):
        farm = Farm(player_x=27, player_y=43, facing='right')
        self.assertEqual(world.target_plot(farm), 'C2')
        _, path, _ = self.route(farm, 'village', (27, 43), kind='plot')
        self.assertEqual(len(path), 3)
        self.follow(farm, path)
        self.assertEqual(world.target_plot(farm), 'B2')
        self.assertEqual(world.context(farm)[0], 'plot')

    def test_adjacent_plot_with_wrong_facing_and_underfoot_edge_goal(self):
        farm = Farm(player_x=26, player_y=43, facing='up')
        _, path, _ = self.route(farm, 'village', (27, 43), kind='plot')
        self.assertEqual(len(path), 2)
        self.follow(farm, path)
        self.assertEqual(world.target_plot(farm), 'B2')
        farm.player_x, farm.player_y, farm.facing = 26, 42, 'up'
        self.assertEqual(self.route(farm, 'village', (26, 42), kind='plot'),
                         ((26, 42), (), 'E'))

    def test_npc_bodies_are_avoided_but_adjacent_interaction_needs_no_turn(self):
        farm = Farm(player_x=27, player_y=5)
        self.assert_shortest(farm, 'village', (29, 5), 'tile',
                             lambda f: (f.player_x, f.player_y) == (29, 5))
        farm = Farm(player_x=28, player_y=6, facing='down')
        self.assertEqual(self.route(farm, 'village', (28, 5), kind='npc'),
                         ((28, 5), (), 'E'))

    def test_water_route_avoids_neighbours_shadowed_by_npc_context(self):
        farm = Farm(player_x=30, player_y=9)
        self.assertEqual(world.context(farm)[0], 'npc')
        target, path, _ = self.route(farm, 'village', (29, 9), kind='water')
        self.assertEqual(target, (29, 9))
        self.assertEqual(len(path), 2)
        self.follow(farm, path)
        self.assertEqual((farm.player_x, farm.player_y), (29, 8))
        self.assertEqual(world.context(farm)[0], 'fish')

    def test_forest_and_water_goals_match_actual_context(self):
        for target, kind, expected in (((9, 13), 'forest', 'forest'),
                                        ((25, 8), 'water', 'fish')):
            farm = Farm()
            self.assert_shortest(farm, 'village', target, kind,
                lambda f, t=target, e=expected: (
                    abs(f.player_x - t[0]) + abs(f.player_y - t[1]) == 1
                    and world.context(f)[0] == e))

    def test_indoor_furniture_and_door_routes_match_bfs(self):
        for target, kind in ((world.TV, 'tv'), (world.BED, 'bed'),
                              (world.CHEST, 'chest'), (world.EXIT, 'exit')):
            farm = Farm(area='home', player_x=8, player_y=7)
            self.assert_shortest(farm, 'home', target, kind,
                lambda f, t=target: abs(f.player_x - t[0]) + abs(f.player_y - t[1]) == 1)
            self.assertTrue(world.is_near(farm, kind))

    def test_cross_area_routes_use_current_door_then_continue_after_transition(self):
        farm = Farm()
        target, path, _ = self.route(farm, 'home', world.BED, kind='bed')
        self.assertEqual(target, world.HOME_DOOR)
        self.follow(farm, path)
        world.enter_home(farm)
        _, path, _ = self.route(farm, 'home', world.BED, kind='bed')
        self.follow(farm, path)
        self.assertEqual(world.context(farm)[0], 'bed')
        target, path, _ = self.route(farm, 'village', (26, 42), kind='plot')
        self.assertEqual(target, world.EXIT)
        self.follow(farm, path)
        world.leave_home(farm)
        _, path, _ = self.route(farm, 'village', (26, 42), kind='plot')
        self.follow(farm, path)
        self.assertEqual(world.target_plot(farm), 'A1')

    def test_blocked_and_missing_goals_are_unreachable(self):
        for farm, area, target, kind in (
                (Farm(), 'village', (28, 5), 'tile'),
                (Farm(), 'village', (0, 0), ''),
                (Farm(), 'village', (30, 42), 'plot'),
                (Farm(), 'village', (25, 7), 'water'),
                (Farm(), 'village', (-10, -10), 'tile'),
                (Farm(area='home', player_x=8, player_y=7), 'home', (7, 3), 'tile')):
            with self.subTest(area=area, target=target, kind=kind):
                self.assertEqual(self.route(farm, area, target, kind=kind), (target, (), 'M'))

    def test_cache_tracks_field_size_start_facing_and_npc_obstacles(self):
        farm = Farm(player_x=30, player_y=41)
        self.assertEqual(self.route(farm, 'village', (30, 42), kind='plot')[2], 'M')
        farm.size = 5
        self.assertEqual(self.route(farm, 'village', (30, 42), kind='plot')[2], 'E')
        farm.player_x, farm.player_y, farm.facing = 19, 7, 'right'
        self.assertEqual(len(self.route(farm, 'village', (21, 7), kind='tile')[1]), 2)
        blocker = villagers.NPC('test', 'Test', '', '?', (20, 7), '')
        with patch.dict(villagers.NPCS, {'test': blocker}):
            _, path, _ = self.route(farm, 'village', (21, 7), kind='tile')
            self.assertEqual(len(path), 4)
            self.assertNotIn((20, 7), path)
        self.assertEqual(len(self.route(farm, 'village', (21, 7), kind='tile')[1]), 2)

    def test_walkable_goal_can_be_unreachable_when_its_only_entrance_is_blocked(self):
        # (1,1) is bordered by a tree above/left, a house right, and (1,2) below.
        farm = Farm()
        self.assertTrue(world.walkable('village', 1, 1))
        blocker = villagers.NPC('test', 'Test', '', '?', (1, 2), '')
        with patch.dict(villagers.NPCS, {'test': blocker}):
            self.assertEqual(self.route(farm, 'village', (1, 1), kind='tile'),
                             ((1, 1), (), 'M'))

    def test_replaced_npc_layout_invalidates_previous_walkable_route(self):
        farm = Farm(player_x=19, player_y=7)
        self.assertEqual(len(self.route(farm, 'village', (21, 7), kind='tile')[1]), 2)
        blocker = villagers.NPC('test', 'Test', '', '?', (20, 7), '')
        with patch.object(villagers, 'NPCS', {**villagers.NPCS, 'test': blocker}):
            _, path, _ = self.route(farm, 'village', (21, 7), kind='tile')
            self.assertEqual(len(path), 4)
            self.follow(farm, path)
            self.assertEqual((farm.player_x, farm.player_y), (21, 7))

    def test_invalid_route_inputs_raise_game_error_without_mutating_farm(self):
        farm = Farm()
        before = deepcopy(farm)
        for area, target, kind in (('moon', (1, 1), ''), ('village', None, ''),
                ('village', (1,), ''), ('village', (1, 2, 3), ''),
                ('village', [1, 2], ''), ('village', (True, 2), ''),
                ('village', (1.0, 2), ''), ('village', (1, 2), 'spaceship')):
            with self.subTest(area=area, target=target, kind=kind):
                with self.assertRaises(GameError):
                    self.route(farm, area, target, kind=kind)
        self.assertEqual(farm, before)
        for field, value in (('area', 'moon'), ('facing', 'north'),
                              ('size', True), ('player_x', -1), ('player_y', 1.0)):
            invalid = deepcopy(farm)
            setattr(invalid, field, value)
            with self.subTest(field=field), self.assertRaises(GameError):
                self.route(invalid, 'village', (11, 7), kind='tile')

    def test_tutorial_adapter_preserves_actionable_route_contract(self):
        farm = Farm(player_x=27, player_y=43, facing='right')
        expected = self.route(farm, 'village', (27, 43), kind='plot')
        self.assertEqual(tutorial._route(farm, 'village', (27, 43), kind='plot'), expected)


class TerrainCacheTests(unittest.TestCase):
    def test_grid_is_immutable_and_retains_sizes_doors_and_terrain(self):
        self.assertTrue(hasattr(world, 'terrain_grid'), 'A reusable static terrain grid is missing')
        for area, width, height in (('village', world.VILLAGE_WIDTH, world.VILLAGE_HEIGHT), ('home', 16, 9)):
            for size in (4, 5, 6):
                grid = world.terrain_grid(area, size)
                self.assertIsInstance(grid, tuple)
                self.assertEqual((len(grid[0]), len(grid)), (width, height))
                self.assertTrue(all(isinstance(row, str) for row in grid))
        self.assertEqual(world.terrain_grid('home')[3][4], '.')
        self.assertEqual(world.terrain_grid('home')[3][7:9], '##')
        self.assertEqual(world.terrain_grid('home')[8][8], 'D')
        self.assertEqual(world.terrain_grid('village', 4)[42][30], '.')
        self.assertEqual(world.terrain_grid('village', 5)[42][30], ':')
        self.assertEqual(world.terrain_grid('village', 6)[47][31], ':')

    def test_warm_tile_cache_still_validates_types_and_outside_is_wall(self):
        self.assertEqual(world.tile_at('village', 1, 1, 4), '.')
        for area, x, y, size in (('moon', 1, 1, 4), ('village', True, 1, 4),
                ('village', 1.0, 1, 4), ('village', 1, False, 4),
                ('village', 1, 1, True), ('village', 1, 1, 4.0),
                ('village', 1, 1, 3), ('home', 1, 1, 7)):
            with self.subTest(area=area, x=x, y=y, size=size), self.assertRaises(GameError):
                world.tile_at(area, x, y, size)
        for area in ('home', 'village'):
            for point in ((-1, 1), (1, -1), (world.VILLAGE_WIDTH, world.VILLAGE_HEIGHT)):
                self.assertEqual(world.tile_at(area, *point), '#')


if __name__ == '__main__':
    unittest.main()
