import unittest
from dataclasses import asdict

from farmgame.model import Farm, GameError


class FarmingTests(unittest.TestCase):
    def test_crop_cycle_produces_goods_experience_and_sale_income(self):
        farm = Farm()
        farm.plant("a1", "ca_rot")
        farm.water("A1")
        farm.sleep("sunny")
        self.assertEqual(farm.plots["A1"].growth, 1)
        farm.water("A1")
        farm.sleep("sunny")
        farm.harvest("A1")
        self.assertEqual(farm.produce["ca_rot"], 1)
        self.assertEqual(farm.harvested, 1)
        self.assertEqual(farm.xp, 5)
        self.assertIsNone(farm.plots["A1"].crop)
        farm.sell_all()
        self.assertEqual(farm.coins, 144)
        self.assertEqual(farm.sales, 24)
        self.assertEqual(farm.produce["ca_rot"], 0)

    def test_dry_crop_does_not_grow_and_wilts_after_three_nights(self):
        farm = Farm()
        farm.plant("A1", "lua_mi")
        farm.sleep("sunny")
        farm.sleep("sunny")
        self.assertFalse(farm.plots["A1"].dead)
        farm.sleep("sunny")
        self.assertTrue(farm.plots["A1"].dead)
        self.assertEqual(farm.plots["A1"].growth, 0)
        with self.assertRaises(GameError):
            farm.harvest("A1")
        farm.clear("A1")
        farm.plant("A1", "ca_rot")
        self.assertEqual(farm.plots["A1"].crop, "ca_rot")

    def test_rain_waters_current_day_and_resets_dry_streak(self):
        farm = Farm()
        farm.plant("A1", "ca_rot")
        farm.sleep("rainy")
        self.assertEqual(farm.plots["A1"].growth, 0)
        self.assertTrue(farm.is_watered("A1"))
        before = farm.energy
        with self.assertRaises(GameError):
            farm.water("A1")
        self.assertEqual(farm.energy, before)
        farm.sleep("sunny")
        self.assertEqual(farm.plots["A1"].growth, 1)
        self.assertEqual(farm.plots["A1"].dry_days, 0)

    def test_watering_twice_is_free_of_side_effects(self):
        farm = Farm()
        farm.plant("A1", "ca_rot")
        farm.water("A1")
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.water("A1")
        self.assertEqual(asdict(farm), before)

    def test_sleep_restores_energy_and_mature_crops_stay_safe(self):
        farm = Farm()
        farm.plant("A1", "lua_mi")
        farm.water("A1")
        farm.sleep("sunny")
        self.assertEqual(farm.energy, 20)
        for _ in range(4):
            farm.sleep("sunny")
        self.assertTrue(farm.plots["A1"].ready)
        self.assertFalse(farm.plots["A1"].dead)
        farm.harvest("A1")
        self.assertEqual(farm.produce["lua_mi"], 1)

    def test_insufficient_energy_does_not_consume_seeds_or_change_plot(self):
        farm = Farm(energy=1)
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.plant("A1", "ca_rot")
        self.assertEqual(asdict(farm), before)

    def test_unripe_harvest_and_occupied_plant_do_not_spend_resources(self):
        farm = Farm()
        farm.plant("A1", "ca_rot")
        before = asdict(farm)
        for action in (lambda: farm.harvest("A1"),
                       lambda: farm.plant("A1", "lua_mi")):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)

    def test_invalid_coordinates_and_crops_do_not_change_game(self):
        farm = Farm()
        before = asdict(farm)
        for coordinate in ("A0", "Z1", "A5", "", "A1 A2"):
            with self.subTest(coordinate=coordinate):
                with self.assertRaises(GameError):
                    farm.plant(coordinate, "ca_rot")
        with self.assertRaises(GameError):
            farm.plant("A1", "unknown")
        self.assertEqual(asdict(farm), before)

    def test_shop_rejects_locked_crops_and_invalid_quantities(self):
        farm = Farm()
        before = asdict(farm)
        for crop, quantity in (("ca_chua", 1), ("ca_rot", 0),
                               ("ca_rot", -1), ("ca_rot", 1.5),
                               ("ca_rot", True), ("ca_rot", 9999)):
            with self.subTest(crop=crop, quantity=quantity):
                with self.assertRaises(GameError):
                    farm.buy_seeds(crop, quantity)
                self.assertEqual(asdict(farm), before)

    def test_buying_seeds_and_harvest_unlock_new_crops(self):
        farm = Farm(xp=37)
        farm.buy_seeds("ca_rot", 3)
        self.assertEqual(farm.coins, 96)
        self.assertEqual(farm.seeds["ca_rot"], 9)
        farm.plant("A1", "lua_mi")
        farm.water("A1")
        farm.sleep("sunny")
        farm.harvest("A1")
        self.assertEqual(farm.level, 2)
        farm.buy_seeds("ca_chua", 1)
        self.assertEqual(farm.seeds["ca_chua"], 1)

    def test_expansion_preserves_coordinates_and_adds_usable_land(self):
        farm = Farm(coins=1000)
        farm.plant("D4", "ca_rot")
        farm.upgrade("land")
        self.assertEqual(farm.size, 5)
        self.assertEqual(len(farm.plots), 25)
        self.assertEqual(farm.plots["D4"].crop, "ca_rot")
        farm.plant("E5", "lua_mi")
        farm.upgrade("land")
        self.assertEqual(farm.size, 6)
        self.assertEqual(farm.plots["E5"].crop, "lua_mi")
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.upgrade("land")
        self.assertEqual(asdict(farm), before)

    def test_sprinkler_automatically_grows_crops(self):
        farm = Farm(coins=500)
        farm.upgrade("sprinkler")
        farm.plant("A1", "lua_mi")
        self.assertTrue(farm.is_watered("A1"))
        farm.sleep("sunny")
        self.assertTrue(farm.plots["A1"].ready)
        self.assertEqual(farm.coins, 200)

    def test_energy_upgrade_is_not_repeated_and_restores_new_limit_on_sleep(self):
        farm = Farm(coins=500)
        farm.upgrade("energy")
        self.assertEqual(farm.max_energy, 30)
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.upgrade("energy")
        self.assertEqual(asdict(farm), before)
        farm.sleep("cloudy")
        self.assertEqual(farm.energy, 30)

    def test_unaffordable_upgrade_and_invalid_weather_leave_state_intact(self):
        farm = Farm(coins=0)
        before = asdict(farm)
        for action in (lambda: farm.upgrade("sprinkler"),
                       lambda: farm.sleep("unknown")):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)

    def test_work_lets_a_broke_player_buy_seeds(self):
        farm = Farm(coins=0)
        farm.work()
        self.assertEqual(farm.coins, 6)
        self.assertEqual(farm.energy, 16)
        self.assertEqual(farm.sales, 0)
        farm.buy_seeds("lua_mi", 1)
        self.assertEqual(farm.coins, 1)

    def test_goal_uses_lifetime_sales_even_after_spending(self):
        farm = Farm(harvested=30, sales=990, coins=0)
        farm.produce["lua_mi"] = 1
        farm.sell_all()
        self.assertTrue(farm.goal_complete)
        farm.buy_seeds("lua_mi", 2)
        self.assertEqual(farm.coins, 2)
        self.assertTrue(farm.goal_complete)


if __name__ == "__main__":
    unittest.main()
