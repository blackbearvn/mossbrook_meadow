"""The fishing journal records species, rarity and collection value."""

import json
import random
import unittest
from dataclasses import asdict
from pathlib import Path
import tempfile

from farmgame.catalog import EXTRA_ITEMS, FISH_TYPES
from farmgame.fishing import FishingRound, finish_fishing
from farmgame.model import Farm
from farmgame.storage import SaveError, load_game, save_game


class FishingJournalTests(unittest.TestCase):
    def round_for(self, key, *, caught=True):
        round_ = FishingRound(random.Random(1))
        round_.fish_key = key
        round_.done = True
        round_.caught = caught
        return round_

    def test_first_catch_unlocks_species_and_adds_collection_points(self):
        farm = Farm()
        message = finish_fishing(farm, self.round_for('ca_lang'))
        self.assertIn('Cá lăng', message)
        self.assertIn('Loài mới', message)
        self.assertEqual(farm.fish_collection['ca_lang'], 1)
        self.assertEqual(farm.fish_points, FISH_TYPES['ca_lang'].points)
        self.assertEqual(farm.fish_species, 1)
        self.assertEqual(farm.fish_collection_value,
                         EXTRA_ITEMS['ca_lang'].sell_price)
        self.assertEqual(farm.items['ca_lang'], 1)

    def test_repeat_catch_counts_again_without_duplicate_species_bonus(self):
        farm = Farm()
        finish_fishing(farm, self.round_for('ca_ro'))
        first_points = farm.fish_points
        message = finish_fishing(farm, self.round_for('ca_ro'))
        self.assertIn('2 lần', message)
        self.assertEqual(farm.fish_collection['ca_ro'], 2)
        self.assertEqual(farm.fish_species, 1)
        self.assertEqual(farm.fish_points, first_points + FISH_TYPES['ca_ro'].points)

    def test_escaped_fish_never_changes_the_journal(self):
        farm = Farm()
        before = asdict(farm)
        finish_fishing(farm, self.round_for('ca_lang', caught=False))
        self.assertEqual(asdict(farm), before)

    def test_new_species_are_level_gated_in_the_happy_path(self):
        low = {FishingRound(random.Random(seed)).fish_key for seed in range(20)}
        high = {FishingRound(random.Random(seed), level=4).fish_key
                for seed in range(80)}
        self.assertTrue(low <= {'ca_ro', 'ca_chep', 'ca_hoi', 'ca_vang'})
        self.assertTrue({'ca_tram', 'ca_mang', 'ca_lang'} & high)

    def test_old_version_seven_save_without_journal_gets_an_empty_one(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            save_game(Farm(day=4, coins=222), path)
            data = json.loads(path.read_text(encoding='utf-8'))
            data['farm'].pop('fish_collection')
            path.write_text(json.dumps(data), encoding='utf-8')
            restored = load_game(path)
            self.assertEqual(restored.fish_collection,
                             {key: 0 for key in FISH_TYPES})
            self.assertEqual((restored.day, restored.coins), (4, 222))

    def test_pre_journal_inventory_gains_missing_species_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = Farm()
            farm.items['ca_ro'] = 2
            farm.chest['ca_chep'] = 1
            save_game(farm, path)
            data = json.loads(path.read_text(encoding='utf-8'))
            for field in ('items', 'chest'):
                for key in ('ca_tram', 'ca_mang', 'ca_lang'):
                    data['farm'][field].pop(key)
            path.write_text(json.dumps(data), encoding='utf-8')
            restored = load_game(path)
            self.assertEqual(restored.items['ca_ro'], 2)
            self.assertEqual(restored.chest['ca_chep'], 1)
            for key in ('ca_tram', 'ca_mang', 'ca_lang'):
                self.assertEqual(restored.items[key], 0)
                self.assertEqual(restored.chest[key], 0)

    def test_malformed_journal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            save_game(Farm(), path)
            original = json.loads(path.read_text(encoding='utf-8'))
            for value in ({}, {'ca_ro': -1}, {'ca_ro': True},
                          {**{key: 0 for key in FISH_TYPES}, 'unknown': 1}):
                with self.subTest(value=value):
                    data = json.loads(json.dumps(original))
                    data['farm']['fish_collection'] = value
                    path.write_text(json.dumps(data), encoding='utf-8')
                    with self.assertRaises(SaveError):
                        load_game(path)

    def test_journal_round_trips_and_old_inventory_gets_new_fish_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = Farm()
            farm.fish_collection['ca_mang'] = 3
            farm.items['ca_mang'] = 2
            save_game(farm, path)
            restored = load_game(path)
            self.assertEqual(restored.fish_collection['ca_mang'], 3)
            self.assertEqual(restored.fish_points, 3 * FISH_TYPES['ca_mang'].points)
            self.assertEqual(restored.items['ca_mang'], 2)

    def test_every_fish_has_a_sell_price_and_a_journal_definition(self):
        for key, fish in FISH_TYPES.items():
            with self.subTest(key=key):
                self.assertEqual(EXTRA_ITEMS[key].name, fish.name)
                self.assertGreater(EXTRA_ITEMS[key].sell_price, 0)
                self.assertGreater(fish.points, 0)
                self.assertIn(fish.level, (1, 2, 3, 4))


if __name__ == '__main__':
    unittest.main()
