"""Cooking recipes use the normal inventory and never lose ingredients on failure."""

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from farmgame.cooking import (COOKED_ITEMS, RECIPES, can_cook, cook,
                              missing_ingredients, recipe_rows)
from farmgame.catalog import ITEMS
from farmgame.model import Farm, GameError
from farmgame.storage import load_game, save_game


class CookingTests(unittest.TestCase):
    def test_every_recipe_has_known_ingredients_and_a_sellable_dish(self):
        self.assertGreaterEqual(len(RECIPES), 8)
        for key, recipe in RECIPES.items():
            with self.subTest(recipe=key):
                self.assertIn(key, COOKED_ITEMS)
                self.assertIn(key, ITEMS)
                self.assertGreater(ITEMS[key].sell_price, 0)
                self.assertGreater(recipe.energy, 0)
                self.assertGreater(recipe.xp, 0)
                for item, amount in recipe.ingredients.items():
                    self.assertIn(item, ITEMS)
                    self.assertGreater(amount, 0)

    def test_failed_cook_is_atomic(self):
        farm = Farm(xp=400)
        before = asdict(farm)
        with self.assertRaisesRegex(GameError, 'Còn thiếu'):
            cook(farm, 'banh_mi')
        self.assertEqual(asdict(farm), before)
        with self.assertRaisesRegex(GameError, 'Không có công thức'):
            cook(farm, 'khong_co')

    def test_ingredients_can_come_from_bag_or_chest_and_energy_is_capped(self):
        farm = Farm(xp=400)
        farm.produce['lua_mi'] = 2
        farm.chest['egg'] = 1
        farm.energy = 1
        self.assertTrue(can_cook(farm, RECIPES['banh_mi']))
        message = cook(farm, 'banh_mi')
        self.assertIn('Bánh mì nướng', message)
        self.assertEqual(farm.items['banh_mi'], 1)
        self.assertEqual(farm.produce['lua_mi'], 0)
        self.assertEqual(farm.chest['egg'], 0)
        self.assertGreater(farm.energy, 1)
        self.assertLessEqual(farm.energy, farm.energy_limit)

    def test_recipe_progress_and_missing_lines_are_readable(self):
        farm = Farm()
        rows = recipe_rows(farm)
        self.assertEqual(len(rows), len(RECIPES))
        missing = missing_ingredients(farm, RECIPES['salad_vuon'])
        self.assertEqual(missing['crop:ca_rot'], 2)
        self.assertFalse(any(can_cook(farm, recipe) for recipe, _ in rows))

    def test_cooked_dish_is_an_ordinary_item_that_can_be_sold(self):
        farm = Farm(xp=400)
        farm.produce['lua_mi'] = 2
        farm.items['egg'] = 1
        cook(farm, 'banh_mi')
        coins = farm.coins
        sales = farm.sales
        farm.sell_all()
        self.assertGreater(farm.coins, coins)
        self.assertGreater(farm.sales, sales)
        self.assertEqual(farm.items['banh_mi'], 0)

    def test_cooked_slot_and_new_inventory_slots_survive_reload(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = Farm(xp=400, coins=900)
            farm.items['banh_mi'] = 2
            farm.seeds['hoa_hong'] = 1
            farm.produce['dau_tay'] = 3
            save_game(farm, path)
            restored = load_game(path)
            self.assertEqual(asdict(restored), asdict(farm))
            self.assertEqual(restored.items['banh_mi'], 2)
            self.assertEqual(restored.seeds['hoa_hong'], 1)


if __name__ == '__main__':
    unittest.main()
