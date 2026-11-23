"""Named regions and fast travel share one safe geography."""

import unittest
from dataclasses import asdict

from farmgame import regions, world
from farmgame.model import Farm


class RegionTests(unittest.TestCase):
    def test_regions_cover_the_village_and_have_unique_names(self):
        names = [region.name for region in regions.REGIONS.values()]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(regions.REGIONS['forest'].name, 'Rừng Thông')
        self.assertEqual(regions.REGIONS['beach'].name, 'Bãi Biển')
        self.assertEqual(regions.region_at('village', 20, 25).key, 'forest')
        self.assertEqual(regions.region_at('village', 55, 20).key, 'square')
        self.assertEqual(regions.region_at('village', 100, 50).key, 'floodplain')
        self.assertEqual(regions.region_at('village', 110, 50).key, 'beach')
        self.assertEqual(regions.region_at('home', 8, 7).key, 'home')

    def test_every_fast_travel_spawn_is_walkable_and_between_regions(self):
        farm = Farm(xp=200)
        for region in regions.travel_regions(farm):
            with self.subTest(region=region.key):
                x, y = region.spawn
                self.assertTrue(world.walkable('village', x, y, farm.size))
                self.assertEqual(regions.region_at('village', x, y).key, region.key)

    def test_fast_travel_moves_without_spending_energy_or_time(self):
        farm = Farm(xp=200, energy=13, day=9)
        before = asdict(farm)
        message = regions.travel(farm, 'beach')
        self.assertIn('Bãi Biển', message)
        self.assertEqual((farm.area, farm.player_x, farm.player_y), ('village', 108, 50))
        self.assertEqual((farm.energy, farm.day), (13, 9))
        self.assertEqual(before['coins'], farm.coins)

    def test_sea_water_is_east_of_the_walkable_beach(self):
        self.assertEqual(world.tile_at('village', 115, 50), 'S')
        self.assertFalse(world.walkable('village', 115, 50))
        self.assertIn('Bãi Biển', world.location_name(Farm(player_x=110, player_y=50)))
        self.assertIn('Bãi Biển', [name for name, _ in world.LANDMARKS.values()])


if __name__ == '__main__':
    unittest.main()
