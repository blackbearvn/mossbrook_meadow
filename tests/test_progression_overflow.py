"""Overflow points are retired safely instead of growing without a sink."""

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from farmgame.model import Farm
from farmgame.progression import (POINT_SOFT_CAP, exchange_points,
                                  settle_excess_points)
from farmgame.storage import load_game, save_game


def maxed_farm() -> Farm:
    farm = Farm(xp=69633)
    farm.attributes = {key: 5 for key in farm.attributes}
    farm.skills = {key: 5 for key in farm.skills}
    return farm


class ProgressionOverflowTests(unittest.TestCase):
    def test_over_cap_points_are_exchanged_for_coins_and_stay_stable(self):
        farm = maxed_farm()
        self.assertGreater(farm.attribute_points, POINT_SOFT_CAP)
        coins = farm.coins
        earned = settle_excess_points(farm)
        self.assertGreater(earned, 0)
        self.assertEqual(farm.coins, coins + earned)
        self.assertEqual(farm.attribute_points, POINT_SOFT_CAP)
        self.assertEqual(farm.skill_points, POINT_SOFT_CAP)
        self.assertEqual(settle_excess_points(farm), 0)

    def test_level_up_retires_new_overflow_without_a_reload(self):
        farm = maxed_farm()
        settle_excess_points(farm)
        coins = farm.coins
        farm.award_xp(40)
        self.assertLessEqual(farm.attribute_points, POINT_SOFT_CAP)
        self.assertLessEqual(farm.skill_points, POINT_SOFT_CAP)
        self.assertGreater(farm.coins, coins)

    def test_exchange_clears_the_reserve_only_when_everything_is_maxed(self):
        farm = maxed_farm()
        settle_excess_points(farm)
        coins = farm.coins
        message = exchange_points(farm)
        self.assertIn('xu', message)
        self.assertEqual((farm.attribute_points, farm.skill_points), (0, 0))
        self.assertGreater(farm.coins, coins)
        with self.assertRaisesRegex(ValueError, 'Không còn điểm'):
            exchange_points(farm)

    def test_old_schema_seven_save_without_retirement_fields_is_fixed_on_load(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = maxed_farm()
            data = asdict(farm)
            data.pop('retired_attribute_points')
            data.pop('retired_skill_points')
            path.write_text(json.dumps({'version': 7, 'farm': data}), encoding='utf-8')
            restored = load_game(path)
            self.assertEqual(restored.attribute_points, POINT_SOFT_CAP)
            self.assertGreater(restored.retired_attribute_points, 0)
            save_game(restored, path)
            again = load_game(path)
            self.assertEqual(again.attribute_points, POINT_SOFT_CAP)
            self.assertEqual(again.coins, restored.coins)


if __name__ == '__main__':
    unittest.main()
