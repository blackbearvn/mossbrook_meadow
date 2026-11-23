"""Expanded crops, animals and their illustrated cards."""

import unittest

from farmgame.animals import (ANIMAL_TYPES, PRODUCT_NAMES, product_name,
                              zone_for)
from farmgame.artwork import ART_WIDTH, art_for, icon_for
from farmgame.catalog import CROPS, EXTRA_ITEMS, ITEMS
from farmgame.tui import cells


class ContentUpgradeTests(unittest.TestCase):
    def test_new_crops_have_seed_produce_and_art(self):
        for key in ('khoai_tay', 'dua_hau', 'dau_tay', 'hoa_hong'):
            with self.subTest(crop=key):
                crop = CROPS[key]
                self.assertIn(f'seed:{key}', ITEMS)
                self.assertIn(f'crop:{key}', ITEMS)
                self.assertGreater(crop.sell_price, crop.seed_price)
                for art_key in (f'seed:{key}', f'crop:{key}'):
                    for unicode in (True, False):
                        art = art_for(art_key, unicode=unicode)
                        self.assertGreaterEqual(len(art), 2)
                        self.assertTrue(all(cells(line) <= ART_WIDTH for line in art))
                        self.assertTrue(icon_for(art_key, unicode=unicode))

    def test_new_animals_have_products_zones_and_art(self):
        for kind in ('rabbit', 'pig'):
            with self.subTest(animal=kind):
                info = ANIMAL_TYPES[kind]
                self.assertIn(info.product, EXTRA_ITEMS)
                self.assertIn(info.product, ITEMS)
                self.assertTrue(PRODUCT_NAMES[kind])
                self.assertTrue(product_name(kind))
                self.assertIn(zone_for(kind).key, ('coop', 'pasture'))
                for unicode in (True, False):
                    art = art_for(kind, unicode=unicode)
                    self.assertGreaterEqual(len(art), 2)
                    self.assertTrue(all(cells(line) <= ART_WIDTH for line in art))
                    self.assertTrue(icon_for(kind, unicode=unicode))

    def test_catalog_keeps_unique_names_and_positive_prices(self):
        names = []
        for item in ITEMS.values():
            self.assertGreaterEqual(item.sell_price, 0)
            self.assertGreaterEqual(item.buy_price, 0)
            if item.name:
                names.append(item.name)
        self.assertGreaterEqual(len(set(names)), len(CROPS))
        self.assertEqual(len(ANIMAL_TYPES), len(set(ANIMAL_TYPES)))


if __name__ == '__main__':
    unittest.main()
