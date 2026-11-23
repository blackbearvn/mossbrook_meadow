"""Mining, forging, dungeon and wide-frame map additions."""

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from farmgame import world
from farmgame.catalog import FORGE_RECIPES, GEAR, ITEMS
from farmgame.dungeon import (MAX_DEPTH, advance, flee, player_attack,
                              start_run, status_lines, use_potion)
from farmgame.forge import (attack_power, forge, mining_bonus,
                            mining_energy_cost, recipe_for)
from farmgame.map_view import map_layout
from farmgame.mining import (mine_rock, mine_summary, rock_exhausted,
                             rock_remaining)
from farmgame.model import Farm, GameError
from farmgame.storage import SaveError, load_game, save_game


class MineWorldTests(unittest.TestCase):
    def test_mine_entrance_is_solid_and_opens_onto_a_connected_indoor_map(self):
        farm = Farm(player_x=76, player_y=7)
        self.assertEqual(world.tile_at('village', 76, 6), 'O')
        self.assertFalse(world.walkable('village', 76, 6))
        self.assertTrue(world.walkable('village', 76, 7))
        self.assertEqual(world.context(farm)[0], 'mine')
        world.enter_mine(farm)
        self.assertEqual((farm.area, farm.player_x, farm.player_y), ('mine', 2, 13))
        self.assertIn('Mỏ Khoáng', world.location_name(farm))
        self.assertTrue(world.walkable('mine', 2, 13))
        self.assertFalse(world.walkable('mine', 0, 0))
        self.assertIn((5, 12), world.MINE_ROCKS)
        self.assertFalse(world.walkable('mine', 5, 12))
        self.assertTrue(world.walkable('mine', 2, 12))
        # The exit is a reachable door in the mine, not a hole in the wall.
        farm.player_x, farm.player_y = 2, 14
        self.assertEqual(world.context(farm)[0], 'mine_exit')
        world.leave_mine(farm)
        self.assertEqual((farm.area, farm.player_x, farm.player_y), ('village', 76, 7))

    def test_mine_rock_kinds_are_stable_and_richer_eastward(self):
        self.assertEqual(world.mine_rock_kind(5, 12), world.mine_rock_kind(5, 12))
        self.assertIn(world.mine_rock_kind(5, 12), world.MINE_ROCK_NAMES)
        kinds = {world.mine_rock_kind(x, y) for x, y in world.MINE_ROCKS}
        self.assertIn('quang_dong', kinds)
        self.assertGreaterEqual(len(kinds), 2)


class MiningTests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm(area='mine', player_x=4, player_y=12, energy=20)

    def test_mining_spends_energy_writes_items_and_refills_after_sleep(self):
        self.assertEqual(world.context(self.farm)[0], 'rock')
        before = self.farm.energy
        message = mine_rock(self.farm, 5, 12)
        self.assertIn('đào', message.lower())
        self.assertGreaterEqual(self.farm.items['da'], 1)
        self.assertGreaterEqual(self.farm.items[world.mine_rock_kind(5, 12)], 1)
        self.assertEqual(self.farm.energy, before - mining_energy_cost(self.farm))
        self.assertEqual(rock_remaining(self.farm, 5, 12), 1)
        mine_rock(self.farm, 5, 12)
        self.assertTrue(rock_exhausted(self.farm, 5, 12))
        with self.assertRaises(GameError):
            mine_rock(self.farm, 5, 12)
        self.farm.sleep()
        self.assertFalse(rock_exhausted(self.farm, 5, 12))
        self.assertEqual(self.farm.hp, self.farm.max_hp)

    def test_mining_requires_mine_adjacency_and_energy(self):
        for farm, point in ((Farm(area='mine', player_x=2, player_y=13), (5, 12)),
                            (Farm(area='mine', player_x=20, player_y=20), (5, 12)),
                            (Farm(player_x=4, player_y=12), (5, 12))):
            with self.subTest(point=point), self.assertRaises(GameError):
                mine_rock(farm, *point)
        poor = Farm(area='mine', player_x=4, player_y=12, energy=0)
        with self.assertRaises(GameError):
            mine_rock(poor, 5, 12)

    def test_miner_hat_improves_cost_and_yield_and_rock_summary(self):
        self.assertEqual(mining_energy_cost(Farm()), 2)
        upgraded = Farm(gear={**Farm().gear, 'hat': 4})
        self.assertEqual(mining_energy_cost(upgraded), 1)
        self.assertEqual(mining_bonus(upgraded), 2)
        available, total = mine_summary(Farm(area='mine'))
        self.assertEqual(available, total)
        self.assertGreater(total, 20)


class ForgeTests(unittest.TestCase):
    def farm(self, **gear):
        farm = Farm(coins=1000)
        farm.gear.update(gear)
        for key in ITEMS:
            if key in ('da', 'quang_dong', 'quang_sat', 'quang_vang', 'kim_cuong'):
                farm.items[key] = 50
        return farm

    def test_forge_consumes_recipe_and_raises_equipment_rank(self):
        farm = self.farm()
        recipe = recipe_for(farm, 'sword')
        coins = farm.coins
        message = forge(farm, 'sword')
        self.assertIn('Hiếm', message)
        self.assertEqual(farm.gear['sword'], 1)
        self.assertEqual(farm.coins, coins - recipe['coins'])
        for key, amount in recipe.items():
            if key != 'coins':
                self.assertEqual(farm.items[key], 50 - amount)
        self.assertGreater(attack_power(farm), attack_power(Farm()))

    def test_armor_raises_max_health_and_heals_a_little(self):
        farm = self.farm(armor=1)
        before = farm.max_hp
        farm.hp = 3
        forge(farm, 'armor')
        self.assertGreater(farm.max_hp, before)
        self.assertGreater(farm.hp, 3)

    def test_forge_rejects_missing_materials_and_max_rank(self):
        poor = Farm(coins=0)
        with self.assertRaises(GameError):
            forge(poor, 'hat')
        maxed = self.farm(**{key: 4 for key in GEAR})
        with self.assertRaises(GameError):
            forge(maxed, 'hat')
        self.assertIsNone(recipe_for(maxed, 'hat'))
        with self.assertRaises(GameError):
            forge(self.farm(), 'unknown')

    def test_every_gear_slot_has_four_upgrades_to_mythic_rarity(self):
        from farmgame.catalog import RARITY_NAMES
        self.assertEqual([info.name for info in GEAR.values()],
                         ['Mũ thợ mỏ', 'Kiếm rèn', 'Giáp da', 'Quần da', 'Giày da'])
        self.assertEqual(RARITY_NAMES,
                         ('Bình thường', 'Hiếm', 'Sử thi', 'Truyền thuyết', 'Huyền thoại'))
        for key, info in GEAR.items():
            self.assertEqual(len(FORGE_RECIPES[key]), 4)
            for recipe in FORGE_RECIPES[key]:
                self.assertIn('coins', recipe)
                for item in recipe:
                    if item != 'coins':
                        self.assertIn(item, ITEMS)


class DungeonTests(unittest.TestCase):
    def ready_farm(self):
        farm = Farm(coins=1000, energy=30)
        for key in ITEMS:
            farm.items[key] = 100
        farm.gear.update({key: 4 for key in GEAR})
        farm.hp = farm.max_hp
        return farm

    def test_dungeon_needs_a_forged_sword_and_a_safe_hp(self):
        with self.assertRaises(GameError):
            start_run(Farm())
        farm = Farm(gear={**Farm().gear, 'sword': 1}, hp=1)
        with self.assertRaises(GameError):
            start_run(farm)

    def test_attack_progresses_through_a_floor_and_records_a_best_depth(self):
        farm = self.ready_farm()
        run = start_run(farm)
        self.assertEqual(run.phase, 'battle')
        self.assertEqual(run.depth, 1)
        guard = 0
        while run.phase == 'battle' and guard < 40:
            player_attack(farm, run)
            guard += 1
        self.assertEqual(run.phase, 'floor')
        self.assertGreaterEqual(farm.dungeon_best, 1)
        self.assertGreater(farm.coins, 1000)
        self.assertTrue(any(farm.items[key] > 100 for key in ('da', 'quang_dong')))
        message = advance(farm, run)
        self.assertIn('tầng 2', message)
        self.assertEqual(run.depth, 2)

    def test_potion_heals_and_flee_ends_the_run(self):
        farm = self.ready_farm()
        farm.hp = 5
        run = start_run(farm)
        self.assertIn('thuốc', use_potion(farm, run).lower())
        self.assertGreater(farm.hp, 5)
        self.assertEqual(farm.items['thuoc'], 99)
        flee(farm, run)
        self.assertEqual(run.phase, 'fled')
        self.assertTrue(run.finished)

    def test_defeat_costs_some_coins_and_never_leaves_zero_hp(self):
        farm = Farm(coins=1000, gear={**Farm().gear, 'sword': 1})
        farm.hp = 2
        run = start_run(farm)
        while run.phase == 'battle':
            player_attack(farm, run)
            if run.turn > 60:
                self.fail('Dungeon combat did not resolve')
        self.assertIn(run.phase, ('defeated', 'floor'))
        if run.phase == 'defeated':
            self.assertEqual(farm.hp, 1)
            self.assertLess(farm.coins, 1000)

    def test_max_depth_is_five_and_status_lines_are_readable(self):
        farm = self.ready_farm()
        run = start_run(farm)
        self.assertEqual(MAX_DEPTH, 5)
        lines = status_lines(farm, run, unicode=True)
        self.assertTrue(any('tầng 1/5' in line for line in lines))
        self.assertTrue(any('Nhớt Xanh' in line for line in lines))


class MineSaveTests(unittest.TestCase):
    def test_new_state_round_trips_and_old_schema_seven_gets_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = Farm(area='mine', player_x=4, player_y=12, hp=7, dungeon_best=3)
            farm.gear.update({'hat': 2, 'sword': 1, 'armor': 1})
            farm.mine_used['5,12'] = 2
            save_game(farm, path)
            restored = load_game(path)
            self.assertEqual(asdict(restored), asdict(farm))

            data = json.loads(path.read_text(encoding='utf-8'))
            for field in ('hp', 'gear', 'mine_used', 'dungeon_best'):
                data['farm'].pop(field)
            path.write_text(json.dumps(data), encoding='utf-8')
            old = load_game(path)
            self.assertEqual(old.hp, 20)
            self.assertEqual(old.gear, Farm().gear)
            self.assertEqual(old.mine_used, {})
            self.assertEqual(old.dungeon_best, 0)

    def test_invalid_new_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            save_game(Farm(), path)
            original = json.loads(path.read_text(encoding='utf-8'))
            changes = (
                ('gear', {}), ('gear', {'pickaxe': 9}),
                ('hp', 0), ('hp', 999), ('dungeon_best', 6),
                ('mine_used', {'0,0': 1}), ('mine_used', {'5,12': 9}),
            )
            for field, value in changes:
                with self.subTest(field=field, value=value):
                    data = json.loads(json.dumps(original))
                    data['farm'][field] = value
                    path.write_text(json.dumps(data), encoding='utf-8')
                    with self.assertRaises(SaveError):
                        load_game(path)


class WideFrameTests(unittest.TestCase):
    def test_expanded_layout_uses_narrow_cells_and_more_rows(self):
        farm = Farm(player_x=40, player_y=20)
        normal = map_layout(farm, 80, 24)
        wide = map_layout(farm, 80, 24, expanded=True)
        self.assertEqual(normal.cell, 2)
        self.assertEqual(wide.cell, 1)
        self.assertGreater(wide.rows, normal.rows)
        self.assertLessEqual(wide.left + wide.cols, world.VILLAGE_WIDTH)
        self.assertEqual((wide.x, wide.y), (1, 1))
        self.assertEqual((wide.cols, wide.rows), (78, 22))
        self.assertEqual(wide.x + wide.cols, 79)
        self.assertEqual(wide.y + wide.rows, 23)
        self.assertEqual(wide.y + wide.rows - 1, 22)

    def test_mine_layout_uses_mine_bounds(self):
        farm = Farm(area='mine', player_x=20, player_y=8)
        layout = map_layout(farm, 80, 24)
        self.assertLessEqual(layout.cols, world.MINE_WIDTH)
        self.assertLessEqual(layout.rows, world.MINE_HEIGHT)
        self.assertGreaterEqual(layout.left, 0)
        self.assertGreaterEqual(layout.top, 0)

    def test_wide_renderer_keeps_player_frame_and_context_visible(self):
        from tests.test_map_ui import CellScreen
        from farmgame.explore import ExplorerGame
        with tempfile.TemporaryDirectory() as temp:
            farm = Farm(area='mine', player_x=4, player_y=12)
            game = ExplorerGame(farm, Path(temp) / 'farm.json', color=False)
            game.unicode_map = True
            game._screen = CellScreen(24, 80)
            game._curses = SimpleNamespace(A_BOLD=1, error=RuntimeError,
                                           KEY_UP=259, KEY_DOWN=258,
                                           KEY_LEFT=260, KEY_RIGHT=261,
                                           KEY_F5=269)
            game.map_expanded = True
            game._draw()
            text = '\n'.join(game._screen.lines())
            self.assertIn('@', text)
            self.assertIn('MỎ KHOÁNG', text)
            self.assertIn('E: ', text)
            game.handle_key('z')
            self.assertFalse(game.map_expanded)


if __name__ == '__main__':
    unittest.main()
