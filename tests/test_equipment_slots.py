"""Five equipment slots, rarity ladder and schema-seven gear migration."""
import json
import tempfile
import unittest
from pathlib import Path

from farmgame.catalog import GEAR, ITEMS, MAX_GEAR, RARITY_NAMES
from farmgame.forge import (attack_power, defense_power, forge, gear_rank,
                            rarity_name, recipe_for, tier_label)
from farmgame.model import Farm, GameError
from farmgame.storage import load_game, save_game


class EquipmentSlotTests(unittest.TestCase):
    def test_five_named_slots_start_at_normal_rarity(self):
        farm = Farm()
        self.assertEqual(tuple(GEAR), ('hat', 'sword', 'armor', 'pants', 'shoes'))
        self.assertEqual([info.name for info in GEAR.values()],
                         ['Mũ thợ mỏ', 'Kiếm rèn', 'Giáp da', 'Quần da', 'Giày da'])
        self.assertEqual(RARITY_NAMES,
                         ('Bình thường', 'Hiếm', 'Sử thi', 'Truyền thuyết', 'Huyền thoại'))
        self.assertEqual(set(farm.gear), set(GEAR))
        self.assertTrue(all(rank == 0 for rank in farm.gear.values()))
        self.assertEqual(rarity_name(0), 'Bình thường')
        self.assertEqual(gear_rank(0), 1)
        self.assertEqual(tier_label(MAX_GEAR), 'Huyền thoại (5/5)')

    def test_each_slot_can_be_forged_from_normal_to_mythic(self):
        farm = Farm(coins=20000)
        for item in ('da', 'quang_dong', 'quang_sat', 'quang_vang', 'kim_cuong'):
            farm.items[item] = 999
        for key in GEAR:
            for expected_rank, expected_rarity in enumerate(RARITY_NAMES[1:], 1):
                forge(farm, key)
                self.assertEqual(farm.gear[key], expected_rank)
                self.assertEqual(rarity_name(farm.gear[key]), expected_rarity)
            self.assertIsNone(recipe_for(farm, key))
            with self.assertRaises(GameError):
                forge(farm, key)

    def test_armor_pants_and_shoes_add_health_and_defense(self):
        base = Farm()
        armoured = Farm(gear={'armor': 1, 'pants': 1, 'shoes': 1})
        self.assertEqual(armoured.max_hp, base.max_hp + 7)
        self.assertEqual(defense_power(armoured), defense_power(base) + 4)
        self.assertGreater(attack_power(Farm(gear={'sword': 1})),
                           attack_power(base))

    def test_schema_seven_three_slot_gear_migrates_to_five_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            save_game(Farm(), path)
            data = json.loads(path.read_text(encoding='utf-8'))
            data['farm']['gear'] = {'pickaxe': 5, 'sword': 5, 'armor': 5}
            data['farm']['hp'] = 40  # valid at the old rank-five armour cap
            path.write_text(json.dumps(data), encoding='utf-8')
            restored = load_game(path)
        self.assertEqual(restored.gear,
                         {'hat': 4, 'sword': 4, 'armor': 4, 'pants': 0, 'shoes': 0})
        self.assertEqual(set(restored.gear), set(GEAR))
        self.assertLessEqual(max(restored.gear.values()), MAX_GEAR)
        self.assertGreater(restored.max_hp, Farm().max_hp)
        self.assertEqual(restored.hp, restored.max_hp)


if __name__ == '__main__':
    unittest.main()
