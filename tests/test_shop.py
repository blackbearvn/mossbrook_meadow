"""Shop catalogue, card art and partial selling without curses."""

import unittest
from dataclasses import asdict

from farmgame.animals import ANIMAL_TYPES
from farmgame.artwork import ART_WIDTH, art_for, hearts, icon_for, npc_portrait
from farmgame.catalog import CROPS
from farmgame.model import Farm, GameError
from farmgame.shop import (CATEGORY_ORDER, buy_seed_bundle, perform,
                           sell_item, sell_total, shop_categories)
from farmgame.tui import cells
from farmgame.villagers import NPCS


class ShopCatalogueTests(unittest.TestCase):
    def test_categories_cover_seeds_pets_supplies_sales_and_upgrades(self):
        farm = Farm(coins=2000)
        categories = {category.key: category for category in shop_categories(farm)}
        self.assertEqual(tuple(categories), CATEGORY_ORDER)
        self.assertEqual(len(categories['seeds'].entries), len(CROPS))
        self.assertEqual({entry.payload for entry in categories['animals'].entries},
                         set(ANIMAL_TYPES))
        self.assertIn('duck', ANIMAL_TYPES)
        self.assertIn('goat', ANIMAL_TYPES)
        self.assertEqual(len(categories['upgrades'].entries), 4)
        self.assertTrue(all(entry.name and entry.detail
                            for category in categories.values()
                            for entry in category.entries))

    def test_seed_card_actions_buy_exact_quantity_and_bundle_one_of_each(self):
        farm = Farm(coins=500)
        seeds = next(category for category in shop_categories(farm)
                     if category.key == 'seeds')
        entry = next(item for item in seeds.entries if item.payload == 'ca_rot')
        perform(farm, entry, 3)
        self.assertEqual(farm.seeds['ca_rot'], 9)
        self.assertEqual(farm.coins, 500 - 3 * CROPS['ca_rot'].seed_price)
        unlocked = [key for key, crop in CROPS.items() if crop.level <= farm.level]
        message = buy_seed_bundle(farm, ','.join(unlocked))
        self.assertIn('Túi hạt hỗn hợp', message)
        for key in unlocked:
            start = 9 if key == 'ca_rot' else (6 if key == 'lua_mi' else 0)
            self.assertEqual(farm.seeds[key], start + 1)

    def test_partial_sale_only_touches_bag_and_reports_value(self):
        farm = Farm(coins=100)
        farm.produce['ca_rot'] = 4
        farm.items['milk'] = 2
        farm.chest['milk'] = 3
        before = asdict(farm)
        message = sell_item(farm, 'crop:ca_rot', 2)
        self.assertIn('2 Cà rốt', message)
        self.assertEqual(farm.produce['ca_rot'], 2)
        self.assertEqual(farm.chest, before['chest'])
        self.assertEqual(farm.coins, 100 + 2 * 24)
        self.assertEqual(farm.sales, 48)
        with self.assertRaises(GameError):
            sell_item(farm, 'crop:ca_rot', 3)
        with self.assertRaises(GameError):
            sell_item(farm, 'seed:ca_rot', 1)

    def test_sell_all_card_is_disabled_until_the_bag_has_value(self):
        farm = Farm()
        sell = next(category for category in shop_categories(farm)
                    if category.key == 'sell')
        self.assertTrue(sell.entries[-1].disabled)
        self.assertEqual(sell_total(farm), 0)
        farm.items['ca_ro'] = 2
        sell = next(category for category in shop_categories(farm)
                    if category.key == 'sell')
        self.assertFalse(sell.entries[-1].disabled)
        self.assertEqual(sell.entries[-1].price, 36)


class CardArtTests(unittest.TestCase):
    def test_every_card_has_a_narrow_multiline_illustration(self):
        keys = [f'seed:{key}' for key in CROPS]
        keys += [f'crop:{key}' for key in CROPS]
        keys += list(ANIMAL_TYPES)
        keys += ['ca_ro', 'ca_chep', 'ca_tram', 'ca_hoi', 'ca_mang',
                 'ca_vang', 'ca_lang', 'egg', 'milk',
                 'wool', 'feed', 'wood', 'coins', 'mixed_seeds',
                 'upgrade:land', 'upgrade:energy', 'upgrade:sprinkler',
                 'upgrade:barn']
        for key in keys:
            for unicode in (True, False):
                with self.subTest(key=key, unicode=unicode):
                    art = art_for(key, unicode=unicode)
                    self.assertGreaterEqual(len(art), 2)
                    self.assertTrue(all(cells(line) <= ART_WIDTH for line in art))
                    self.assertTrue(icon_for(key, unicode=unicode))
                    if not unicode:
                        self.assertTrue(all(line.isascii() for line in art))

    def test_every_villager_has_a_narrow_portrait_and_relationship_meter(self):
        for npc in NPCS.values():
            for unicode in (True, False):
                with self.subTest(npc=npc.id, unicode=unicode):
                    portrait = npc_portrait(npc.id, unicode=unicode)
                    self.assertEqual(len(portrait), 5)
                    self.assertTrue(all(cells(line) <= 11 for line in portrait))
                    self.assertEqual(cells(hearts(4, unicode=unicode)), 10)


if __name__ == '__main__':
    unittest.main()
