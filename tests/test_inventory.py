import unittest
from dataclasses import asdict

from farmgame.catalog import ITEMS
from farmgame.inventory import (SECTION_ORDER, count_item, deposit_all,
                                inventory_rows, item_section, section_rows,
                                transfer_item)
from farmgame.model import Farm, GameError


class InventoryTests(unittest.TestCase):
    def test_deposit_and_withdraw_preserve_each_inventory_category(self):
        farm = Farm()
        farm.produce['ca_rot'] = 2
        farm.items['milk'] = 2
        for key in ('seed:ca_rot', 'crop:ca_rot', 'milk'):
            before = count_item(farm, key)
            transfer_item(farm, key, 1, 'deposit')
            self.assertEqual(count_item(farm, key), before - 1)
            self.assertEqual(farm.chest[key], 1)
            transfer_item(farm, key, 1, 'withdraw')
            self.assertEqual(count_item(farm, key), before)
            self.assertEqual(farm.chest[key], 0)

    def test_invalid_transfers_do_not_move_or_duplicate_items(self):
        farm = Farm()
        before = asdict(farm)
        for key, quantity, direction in (
            ('milk', 1, 'deposit'), ('seed:ca_rot', 99, 'deposit'),
            ('seed:ca_rot', -1, 'deposit'), ('seed:ca_rot', True, 'deposit'),
            ('seed:ca_rot', 0, 'deposit'), ('milk', 1, 'withdraw'),
            ('unknown', 1, 'deposit'), ('seed:ca_rot', 1, 'invalid'),
        ):
            with self.subTest(key=key, quantity=quantity, direction=direction):
                with self.assertRaises(GameError):
                    transfer_item(farm, key, quantity, direction)
                self.assertEqual(asdict(farm), before)

    def test_selling_bag_preserves_food_seeds_and_chest(self):
        farm = Farm()
        farm.items['milk'] = 2
        farm.items['ca_ro'] = 1
        transfer_item(farm, 'milk', 1, 'deposit')
        farm.sell_all()
        self.assertEqual(farm.coins, 183)
        self.assertEqual(farm.sales, 63)
        self.assertEqual(farm.chest['milk'], 1)
        self.assertEqual(farm.items['feed'], 8)
        self.assertEqual(farm.seeds['ca_rot'], 6)
        self.assertEqual(farm.items['milk'], 0)

    def test_deposit_all_is_reversible_and_rows_show_chest_contents(self):
        farm = Farm()
        farm.items['wool'] = 2
        deposit_all(farm)
        self.assertEqual(farm.chest['wool'], 2)
        self.assertEqual(count_item(farm, 'seed:lua_mi'), 0)
        rows = {row[0]: row for row in inventory_rows(farm)}
        self.assertEqual(rows['wool'][2:], (0, 2))
        self.assertEqual(rows['seed:lua_mi'][2:], (0, 6))
        transfer_item(farm, 'wool', 2, 'withdraw')
        self.assertEqual(farm.items['wool'], 2)

    def test_sections_partition_every_item_without_overlap(self):
        seen = set()
        for section in SECTION_ORDER[1:]:
            keys = {key for key in ITEMS if item_section(key) == section}
            self.assertTrue(keys, section)
            self.assertFalse(seen & keys, section)
            seen |= keys
        self.assertEqual(seen, set(ITEMS))

    def test_section_rows_keeps_inventory_row_shape(self):
        farm = Farm()
        farm.produce['ca_rot'] = 2
        rows = [row for row in inventory_rows(farm) if row[2] or row[3]]
        crop_rows = section_rows(rows, 'crop')
        self.assertEqual([row[0] for row in crop_rows], ['crop:ca_rot'])
        self.assertEqual(crop_rows[0][2:], (2, 0))
        self.assertEqual(section_rows(rows, 'all'), rows)

    def test_feed_purchase_validates_funds_and_count(self):
        farm = Farm()
        farm.buy_item('feed', 2)
        self.assertEqual(farm.items['feed'], 10)
        self.assertEqual(farm.coins, 110)
        before = asdict(farm)
        for key, quantity in (('milk', 1), ('feed', -1), ('feed', 100), ('?', 1)):
            with self.assertRaises(GameError):
                farm.buy_item(key, quantity)
            self.assertEqual(asdict(farm), before)

    def test_tv_forecast_stays_fixed_and_becomes_next_days_weather(self):
        farm = Farm()
        expected = farm.forecast
        first = farm.forecast_report()
        self.assertEqual(farm.forecast_report(), first)
        self.assertEqual(farm.day, 1)
        farm.sleep()
        self.assertEqual(farm.day, 2)
        self.assertEqual(farm.weather, expected)


if __name__ == '__main__':
    unittest.main()
