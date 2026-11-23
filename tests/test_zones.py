"""Level-gated livestock zones keep purchases and capacities separate."""

import unittest
from dataclasses import asdict
from pathlib import Path
import tempfile

from farmgame.animals import (ANIMAL_ZONES, Animal, buy_animal,
                              zone_animals, zone_for)
from farmgame.model import Farm, GameError
from farmgame.storage import load_game, save_game


class LivestockZoneTests(unittest.TestCase):
    def test_zones_expose_levels_capacities_and_species(self):
        self.assertEqual([zone.level for zone in ANIMAL_ZONES.values()],
                         [1, 2, 4])
        self.assertEqual(zone_for('chicken').key, 'coop')
        self.assertEqual(zone_for('cow').key, 'pasture')
        self.assertEqual(zone_for('goat').key, 'highland')
        self.assertEqual(ANIMAL_ZONES['highland'].capacity, 2)

    def test_locked_zone_purchase_is_atomic_and_explains_the_level(self):
        farm = Farm(coins=2000)
        before = asdict(farm)
        for kind in ('cow', 'goat'):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(GameError, 'mở ở cấp'):
                    buy_animal(farm, kind)
                self.assertEqual(asdict(farm), before)

    def test_each_zone_has_its_own_capacity(self):
        farm = Farm(coins=3000, xp=40)  # level 2: pasture is open
        for index in range(4):
            buy_animal(farm, 'cow', f'Bò {index}')
        with self.assertRaisesRegex(GameError, 'Đồng Cỏ đã đủ 4 chỗ'):
            buy_animal(farm, 'cow', 'Bò 5')
        self.assertEqual(len(zone_animals(farm, 'pasture')), 4)
        farm.upgrade('barn')
        with self.assertRaisesRegex(GameError, 'Đồng Cỏ đã đủ 4 chỗ'):
            buy_animal(farm, 'cow', 'Bò 6')

    def test_highland_unlocks_at_level_four(self):
        farm = Farm(coins=2000, xp=120)
        buy_animal(farm, 'goat', 'Dê Núi')
        self.assertEqual([animal.kind for animal in zone_animals(farm, 'highland')],
                         ['goat'])

    def test_zone_collection_survives_reload_including_old_animals(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = Farm(coins=2000, xp=120)
            for kind in ('chicken', 'cow', 'goat'):
                buy_animal(farm, kind)
            save_game(farm, path)
            restored = load_game(path)
            self.assertEqual([animal.kind for animal in restored.animals],
                             ['chicken', 'cow', 'goat'])
            self.assertEqual(zone_for(restored.animals[2].kind).name, 'Đồi Dê')


if __name__ == '__main__':
    unittest.main()
