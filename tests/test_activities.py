import math
import random
import unittest
from dataclasses import asdict

from farmgame.animals import (Animal, advance_animals, buy_animal, buy_feed,
                              collect_products, feed_animals, pet_animal)
from farmgame.fishing import FishingRound, finish_fishing, start_fishing
from farmgame.model import Farm, GameError


class AnimalTests(unittest.TestCase):
    def test_chicken_grows_only_produces_when_fed_and_can_be_collected_once(self):
        farm = Farm(coins=500)
        buy_animal(farm, "chicken", "Mơ")
        self.assertEqual(farm.coins, 420)
        self.assertEqual(farm.animals[0].name, "Mơ")
        feed_animals(farm)
        advance_animals(farm)
        self.assertEqual(farm.animals[0].produce, 0)
        feed_animals(farm)
        advance_animals(farm)
        self.assertEqual(farm.animals[0].produce, 1)
        self.assertFalse(farm.animals[0].fed)
        collect_products(farm)
        self.assertEqual(farm.items["egg"], 1)
        self.assertGreater(farm.xp, 0)
        with self.assertRaises(GameError):
            collect_products(farm)
        advance_animals(farm)
        self.assertEqual(len(farm.animals), 1)
        self.assertEqual(farm.animals[0].produce, 0)

    def test_sheep_needs_two_fed_mature_days_and_friendship_increases_yield(self):
        farm = Farm()
        farm.animals = [Animal("sheep", "Bông", age=3, friendship=3)]
        pet_animal(farm, 0)
        self.assertEqual(farm.animals[0].friendship, 4)
        for expected in (0, 2):
            feed_animals(farm)
            advance_animals(farm)
            self.assertEqual(farm.animals[0].produce, expected)
        collect_products(farm)
        self.assertEqual(farm.items["wool"], 2)

    def test_duck_and_goat_produce_their_species_goods(self):
        from farmgame.animals import product_name
        farm = Farm(coins=1000, xp=120)
        buy_animal(farm, 'duck', 'Vịt Bông')
        buy_animal(farm, 'goat', 'Dê Núi')
        for _ in range(4):
            feed_animals(farm)
            advance_animals(farm)
        self.assertEqual(product_name('duck'), 'Trứng vịt')
        self.assertEqual(product_name('goat'), 'Sữa dê')
        collect_products(farm)
        self.assertEqual(farm.items['egg'], 3)
        self.assertEqual(farm.items['milk'], 1)

    def test_petting_and_feeding_twice_do_not_consume_resources(self):
        farm = Farm()
        farm.animals = [Animal("cow", "Sữa", age=3, friendship=5)]
        feed_animals(farm)
        pet_animal(farm, 0)
        before = asdict(farm)
        for action in (lambda: feed_animals(farm), lambda: pet_animal(farm, 0)):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)
        advance_animals(farm)
        self.assertEqual(farm.animals[0].produce, 2)
        self.assertFalse(farm.animals[0].petted)
        pet_animal(farm, 0)
        self.assertEqual(farm.animals[0].friendship, 5)

    def test_insufficient_feed_leaves_entire_herd_unfed(self):
        farm = Farm()
        farm.animals = [Animal("chicken", "A"), Animal("cow", "B")]
        farm.items["feed"] = 1
        before = asdict(farm)
        with self.assertRaises(GameError):
            feed_animals(farm)
        self.assertEqual(asdict(farm), before)

    def test_animal_names_reject_control_characters_and_overflow_atomically(self):
        farm = Farm(coins=500)
        before = asdict(farm)
        for name in ("\x1b[2J", "x" * 25, "", "   "):
            with self.subTest(name=name):
                with self.assertRaises(GameError):
                    buy_animal(farm, "chicken", name)
                self.assertEqual(asdict(farm), before)
        buy_animal(farm, "chicken", "  Mơ  ")
        self.assertEqual(farm.animals[0].name, "Mơ")

    def test_purchase_capacity_and_invalid_actions_are_atomic(self):
        farm = Farm(coins=1000, xp=40)
        farm.animals = [Animal("chicken", str(i)) for i in range(4)]
        before = asdict(farm)
        for action in (lambda: buy_animal(farm, "cow"),
                       lambda: buy_animal(farm, "dragon"),
                       lambda: buy_feed(farm, -1),
                       lambda: buy_feed(farm, True),
                       lambda: pet_animal(farm, -1),
                       lambda: pet_animal(farm, True),
                       lambda: pet_animal(farm, 99)):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)
        farm.upgrade("barn")
        buy_animal(farm, "cow")
        self.assertEqual(len(farm.animals), 5)
        self.assertEqual(farm.coins, 480)
        buy_feed(farm, 2)
        self.assertEqual(farm.items["feed"], 10)
        self.assertLess(farm.coins, 480)


class FishingTests(unittest.TestCase):
    def test_cast_requires_water_and_energy_without_partial_spending(self):
        farm = Farm()
        before = asdict(farm)
        with self.assertRaises(GameError):
            start_fishing(farm)
        self.assertEqual(asdict(farm), before)
        # The west bank of the lake; verified against the real world geometry.
        farm.player_x, farm.player_y = 21, 9
        farm.energy = 2
        before = asdict(farm)
        with self.assertRaises(GameError):
            start_fishing(farm)
        self.assertEqual(asdict(farm), before)
        farm.energy = 3
        round_ = start_fishing(farm, random.Random(7))
        self.assertIsInstance(round_, FishingRound)
        self.assertEqual(farm.energy, 0)

    def test_controls_move_bar_and_seed_replays_fish_motion(self):
        lifted = FishingRound(random.Random(2))
        dropped = FishingRound(random.Random(2))
        original = lifted.bar
        for _ in range(8):
            lifted.step(0.05, True)
            dropped.step(0.05, False)
        self.assertGreater(lifted.bar, original)
        self.assertLess(dropped.bar, original)
        self.assertEqual(lifted.target, dropped.target)
        self.assertNotEqual(lifted.target, 0.5)

    def test_tracking_fish_catches_and_rewards_exactly_once(self):
        farm = Farm()
        round_ = FishingRound(random.Random(7))
        before = asdict(farm)
        with self.assertRaises(GameError):
            finish_fishing(farm, round_)
        self.assertEqual(asdict(farm), before)
        for _ in range(1200):
            round_.step(0.05, round_.bar + round_.velocity * 0.35 < round_.target)
            if round_.done:
                break
        self.assertTrue(round_.caught)
        finish_fishing(farm, round_)
        self.assertEqual(farm.items[round_.fish_key], 1)
        self.assertEqual(farm.fish_caught, 1)
        self.assertGreater(farm.xp, 0)
        before = asdict(farm)
        with self.assertRaises(GameError):
            finish_fishing(farm, round_)
        self.assertEqual(asdict(farm), before)

    def test_uncontrolled_cast_escapes_and_never_rewards(self):
        farm = Farm()
        round_ = FishingRound(random.Random(7))
        for _ in range(1200):
            round_.step(0.05, False)
            if round_.done:
                break
        self.assertTrue(round_.done)
        self.assertFalse(round_.caught)
        before = asdict(farm)
        finish_fishing(farm, round_)
        self.assertTrue(round_.claimed)
        self.assertEqual(asdict(farm), before)
        with self.assertRaises(GameError):
            finish_fishing(farm, round_)

    def test_time_step_is_bounded_and_invalid_time_does_not_change_round(self):
        round_ = FishingRound(random.Random(4))
        for invalid in (-1, math.nan, math.inf):
            before = vars(round_).copy()
            with self.assertRaises(ValueError):
                round_.step(invalid, True)
            self.assertEqual(vars(round_), before)
        round_.step(100000, True)
        self.assertLessEqual(round_.elapsed, 0.25)
        self.assertGreaterEqual(round_.bar, 0)
        self.assertLessEqual(round_.bar, 1)


if __name__ == "__main__":
    unittest.main()
