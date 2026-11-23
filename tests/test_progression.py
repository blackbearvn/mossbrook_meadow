import random
import unittest
from dataclasses import asdict

from farmgame.animals import Animal, advance_animals, collect_products
from farmgame.catalog import CROPS, ITEMS
from farmgame.fishing import FishingRound, finish_fishing, start_fishing
from farmgame.model import Farm, GameError, Plot


class ProgressionTests(unittest.TestCase):
    def test_work_gives_wood_and_base_experience_without_sales(self):
        farm = Farm()
        farm.work()
        self.assertEqual(farm.items['wood'], 1)
        self.assertEqual(farm.xp, 2)
        self.assertEqual(farm.sales, 0)

    def test_existing_xp_and_multiple_level_crossings_grant_full_budgets(self):
        farm = Farm(xp=79)
        self.assertEqual((farm.level, farm.attribute_points, farm.skill_points), (2, 1, 2))
        message = farm.award_xp(82)
        self.assertEqual((farm.level, farm.attribute_points, farm.skill_points), (5, 4, 8))
        self.assertIn('3 điểm thuộc tính', message)
        self.assertIn('6 điểm tay nghề', message)

    def test_upgrade_spends_derived_budget_and_caps_at_five(self):
        from farmgame.progression import upgrade_attribute, upgrade_skill
        farm = Farm(xp=400)
        for _ in range(5):
            upgrade_attribute(farm, 'focus')
            upgrade_skill(farm, 'farming')
        self.assertEqual((farm.attribute_points, farm.skill_points), (5, 15))
        before = asdict(farm)
        for action in (lambda: upgrade_attribute(farm, 'focus'),
                       lambda: upgrade_skill(farm, 'farming'),
                       lambda: upgrade_attribute(farm, 'unknown'),
                       lambda: upgrade_skill(farm, 'unknown')):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)
        poor = Farm()
        for action in (lambda: upgrade_attribute(poor, 'focus'),
                       lambda: upgrade_skill(poor, 'farming')):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(poor), asdict(Farm()))

    def test_endurance_heals_and_stacks_with_base_upgrade_and_sleep(self):
        from farmgame.progression import upgrade_attribute
        farm = Farm(xp=200, coins=500)
        for _ in range(5):
            upgrade_attribute(farm, 'endurance')
        self.assertEqual((farm.max_energy, farm.energy_limit, farm.energy), (20, 40, 40))
        farm.upgrade('energy')
        self.assertEqual((farm.max_energy, farm.energy_limit, farm.energy), (30, 50, 50))
        farm.energy = 0
        self.assertIn('50', farm.sleep('sunny'))
        self.assertEqual(farm.energy, 50)

    def test_dexterity_threshold_and_farming_yield(self):
        for rank in range(6):
            with self.subTest(rank=rank):
                farm = Farm(xp=400)
                farm.attributes['dexterity'] = rank
                farm.skills['farming'] = rank
                farm.plant('A1', 'ca_rot')
                self.assertEqual(farm.energy, 20 - (1 if rank >= 3 else 2))
                farm.plots['A1'].growth = CROPS['ca_rot'].days
                farm.harvest('A1')
                self.assertEqual(farm.energy, 20 - (2 if rank >= 3 else 4))
                self.assertEqual(farm.produce['ca_rot'], 2 if rank >= 3 else 1)
                self.assertEqual(farm.harvested, 2 if rank >= 3 else 1)
                self.assertEqual(farm.xp, 405)

    def test_focus_applies_once_to_each_success_and_never_to_failed_actions(self):
        farm = Farm(xp=400)
        farm.attributes['focus'] = 5
        farm.work()
        self.assertEqual(farm.xp, 407)
        farm.plots['A1'] = Plot(crop='ca_rot', growth=2)
        farm.harvest('A1')
        self.assertEqual(farm.xp, 417)
        farm.animals = [Animal('chicken', 'A', produce=2), Animal('cow', 'B', produce=1)]
        collect_products(farm)
        self.assertEqual(farm.xp, 431)
        round_ = FishingRound(random.Random(7))
        round_.done = round_.caught = True
        finish_fishing(farm, round_)
        self.assertEqual(farm.xp, 441)
        before = asdict(farm)
        for action in (lambda: farm.harvest('A1'), lambda: collect_products(farm),
                       lambda: finish_fishing(farm, round_)):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)
        farm.energy = 0
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.work()
        self.assertEqual(asdict(farm), before)

    def test_all_fishing_and_foraging_ranks_change_real_actions(self):
        outcomes = ((0, .260, 3, 6, 1, 4), (1, .285, 3, 8, 1, 4),
                    (2, .310, 2, 10, 2, 3), (3, .335, 2, 12, 2, 3),
                    (4, .360, 1, 14, 3, 2), (5, .385, 1, 16, 3, 2))
        for rank, width, fishing_cost, coins, wood, work_cost in outcomes:
            with self.subTest(rank=rank):
                farm = Farm(xp=400, player_x=21, player_y=9)
                farm.skills['fishing'] = rank
                farm.skills['foraging'] = rank
                farm.energy = fishing_cost
                round_ = start_fishing(farm, random.Random(7))
                self.assertAlmostEqual(round_.bar_width, width)
                self.assertEqual(farm.energy, 0)
                farm.energy = 20
                farm.work()
                self.assertEqual(farm.energy, 20 - work_cost)
                self.assertEqual(farm.coins, 120 + coins)
                self.assertEqual(farm.items['wood'], wood)

    def test_ranching_yield_stacks_with_animal_friendship(self):
        for rank in range(6):
            for friendship in (0, 4):
                with self.subTest(rank=rank, friendship=friendship):
                    farm = Farm(xp=400)
                    farm.skills['ranching'] = rank
                    farm.animals = [Animal('cow', 'Sữa', age=3, fed=True, friendship=friendship)]
                    advance_animals(farm)
                    self.assertEqual(farm.animals[0].produce,
                                     1 + int(friendship >= 4) + int(rank >= 3))

    def test_sale_bonus_rounds_each_unit_and_only_applies_when_selling(self):
        from farmgame.progression import sale_price
        outcomes = ((0, 24, 45, 180), (1, 26, 49, 194),
                    (2, 28, 54, 210), (3, 31, 58, 227),
                    (4, 33, 63, 243), (5, 36, 67, 260))
        for rank, carrot_price, milk_price, expected in outcomes:
            farm = Farm(xp=400)
            farm.skills['farming'] = farm.skills['ranching'] = rank
            for key in ITEMS:
                skill_rank = (rank if key.startswith('crop:')
                              or key in ('egg', 'milk', 'wool', 'fur', 'truffle')
                              else 0)
                self.assertEqual(sale_price(farm, key), ITEMS[key].sell_price * (10+skill_rank)//10)
            farm.produce['ca_rot'] = 3
            farm.items['milk'] = 2
            farm.items['ca_ro'] = 1
            self.assertEqual(farm.sales, 0)
            self.assertEqual(sale_price(farm, 'crop:ca_rot'), carrot_price)
            self.assertEqual(sale_price(farm, 'milk'), milk_price)
            farm.sell_all()
            self.assertEqual(farm.sales, expected)
            self.assertEqual(farm.coins, 120+expected)

    def test_character_describes_all_stats_and_defaults_are_independent(self):
        from farmgame.progression import ATTRIBUTES, SKILLS, character_lines
        farm = Farm()
        other = Farm()
        farm.attributes['focus'] = 1
        self.assertEqual(other.attributes['focus'], 0)
        farm.skills['farming'] = 1
        self.assertEqual(other.skills['farming'], 0)
        text = '\n'.join(character_lines(farm))
        for definition in (*ATTRIBUTES.values(), *SKILLS.values()):
            self.assertIn(definition.name, text)
            self.assertTrue(definition.description)

    def test_invalid_xp_is_atomic(self):
        farm = Farm()
        before = asdict(farm)
        for invalid in (-1, True, 1.5):
            with self.assertRaises(GameError):
                farm.award_xp(invalid)
            self.assertEqual(asdict(farm), before)
