"""Auto runs ordinary game rules a single interruptible step at a time."""

from copy import deepcopy
from importlib import import_module, util
import random
import unittest
from unittest.mock import patch

from farmgame.animals import ANIMAL_TYPES, Animal
from farmgame.catalog import CROPS, FISH_TYPES
from farmgame.fishing import FishingRound
from farmgame.model import Farm, Plot
from farmgame.tutorial import start_tutorial
from farmgame import world


class AutomationTests(unittest.TestCase):
    def engine(self, farm=None, *, mode='all', days=1, seed=7):
        self.assertIsNotNone(util.find_spec('farmgame.automation'),
                             'The incremental automation engine is missing')
        module = import_module('farmgame.automation')
        return module.Automation(farm or Farm(),
                                 module.AutoOptions(mode=mode, days=days),
                                 rng=random.Random(seed))

    def run_until(self, auto, predicate=None, limit=12000):
        messages = []
        for _ in range(limit):
            result = auto.step()
            messages.append(result.message)
            if predicate is not None and predicate():
                return messages
            if result.done:
                if predicate is not None:
                    self.fail('Auto stopped before its objective: ' + '\n'.join(messages[-5:]))
                return messages
        self.fail('Auto did not finish within its action budget: ' + '\n'.join(messages[-5:]))

    def test_options_validate_mode_days_and_continuous_run(self):
        auto = self.engine(days=0)
        options = type(auto.options)
        for kwargs in ({'mode': 'unknown'}, {'days': -1}, {'days': True},
                       {'days': 1.5}, {'days': '3'}):
            with self.assertRaises(ValueError):
                options(**kwargs)
        self.assertEqual(options().mode, 'all')
        self.assertEqual(options().days, 1)
        self.assertFalse(auto.done)

    def test_pause_and_stop_leave_saved_game_untouched(self):
        farm = Farm()
        auto = self.engine(farm)
        auto.paused = True
        before = deepcopy(farm)
        for _ in range(5):
            result = auto.step()
            self.assertFalse(result.changed or result.moved or result.done)
        self.assertEqual(farm, before)
        auto.paused = False
        self.assertTrue(auto.step().moved)
        auto.stop()
        before = deepcopy(farm)
        self.assertTrue(auto.step().done)
        self.assertEqual(farm, before)
        self.assertEqual(auto.path_points(), set())

    def test_moves_one_tile_per_step_and_keeps_the_current_route(self):
        farm = Farm()
        auto = self.engine(farm, mode='farm')
        module = import_module('farmgame.automation')
        with patch.object(module, 'route', wraps=module.route) as routes:
            for _ in range(12):
                before = farm.player_x, farm.player_y
                result = auto.step()
                self.assertTrue(result.moved)
                self.assertEqual(abs(before[0] - farm.player_x)
                                 + abs(before[1] - farm.player_y), 1)
            self.assertEqual(routes.call_count, 1)
        self.assertTrue(auto.path_points())

    def test_manual_position_change_replans_without_a_jump(self):
        farm = Farm()
        auto = self.engine(farm, mode='farm')
        auto.step()
        world.move(farm, 'right')
        before = farm.player_x, farm.player_y
        result = auto.step()
        self.assertTrue(result.moved)
        self.assertEqual(abs(before[0] - farm.player_x)
                         + abs(before[1] - farm.player_y), 1)

    def test_seven_farming_days_harvest_and_never_plant_without_water_energy(self):
        farm = Farm(coins=0)
        farm.chest['crop:ca_rot'] = 4
        auto = self.engine(farm, mode='farm', days=7)
        day = farm.day
        for _ in range(12000):
            before = deepcopy(farm)
            result = auto.step()
            if farm.day != before.day:
                for key, plot in before.plots.items():
                    if plot.crop and not plot.ready and not plot.dead:
                        self.assertTrue(before.is_watered(key), (before.day, key))
            self.assertFalse(any(plot.dead for plot in farm.plots.values()))
            if result.done:
                break
        else:
            self.fail('Seven-day farm auto did not finish')
        self.assertEqual(farm.day, day + 7)
        self.assertGreater(farm.harvested, 0)
        self.assertGreater(farm.sales, 0)
        self.assertEqual(farm.chest['crop:ca_rot'], 4)
        self.assertTrue(auto.done)
        self.assertIn('7', auto.summary)

    def test_waters_existing_crops_before_any_other_energy_spending(self):
        farm = Farm(energy=8)
        keys = list(farm.plots)
        for key in keys[:8]:
            farm.plots[key] = Plot('ca_rot')
        farm.plots[keys[8]] = Plot('lua_mi', growth=1)
        auto = self.engine(farm, mode='farm')
        for _ in range(800):
            before = deepcopy(farm)
            result = auto.step()
            thirsty = [key for key, plot in before.plots.items()
                       if plot.crop and not plot.ready and not plot.dead
                       and not before.is_watered(key)]
            if farm.energy < before.energy and thirsty:
                self.assertEqual(farm.harvested, 0)
                self.assertEqual(sum(farm.is_watered(key) for key in thirsty), 1)
            if result.done:
                break
        self.assertEqual(farm.day, 2)
        self.assertTrue(all(farm.plots[key].growth == 1 for key in keys[:8]))

    def test_overfull_dry_field_rotates_water_to_avoid_starving_far_plots(self):
        farm = Farm(size=6, coins=0)
        for key in farm.plots:
            farm.plots[key] = Plot('bi_ngo')
        auto = self.engine(farm, mode='farm', days=7)
        real_sleep = Farm.sleep

        def sunny_sleep(farm):
            return real_sleep(farm, 'sunny')

        with patch.object(Farm, 'sleep', autospec=True, side_effect=sunny_sleep):
            self.run_until(auto)
        self.assertEqual(farm.day, 8)
        self.assertFalse(any(plot.dead for plot in farm.plots.values()))
        self.assertTrue(all(plot.growth > 0 for plot in farm.plots.values()))

    def test_harvests_mature_crops_and_clears_dead_plants(self):
        farm = Farm(player_x=26, player_y=41, facing='down')
        farm.plots['A1'] = Plot('ca_rot', growth=2)
        farm.plots['B1'] = Plot('lua_mi', dead=True)
        auto = self.engine(farm, mode='farm')
        self.run_until(auto, lambda: farm.harvested == 1
                       and not farm.plots['B1'].dead)
        self.assertEqual(farm.produce['ca_rot'], 1)
        self.assertGreaterEqual(farm.xp, CROPS['ca_rot'].xp)

    def test_empty_poor_exhausted_farmer_sleeps_without_inventing_items(self):
        farm = Farm(energy=0, coins=0)
        farm.seeds = dict.fromkeys(CROPS, 0)
        before_items = dict(farm.items)
        auto = self.engine(farm, mode='farm')
        self.run_until(auto)
        self.assertEqual((farm.day, farm.coins, farm.xp, farm.harvested), (2, 0, 0, 0))
        self.assertEqual(farm.seeds, dict.fromkeys(CROPS, 0))
        self.assertEqual(farm.items, before_items)
        self.assertFalse(any(plot.crop for plot in farm.plots.values()))

    def test_no_money_or_seeds_recovers_with_real_work_and_purchase(self):
        farm = Farm(coins=0)
        farm.seeds = dict.fromkeys(CROPS, 0)
        auto = self.engine(farm, mode='farm')
        messages = self.run_until(auto, lambda: any(plot.crop for plot in farm.plots.values()))
        self.assertGreaterEqual(farm.xp, 2)
        self.assertTrue(any('nhặt củi' in message for message in messages))
        self.assertTrue(any('Mua' in message for message in messages))
        self.assertLess(farm.energy, 20)
        self.assertGreaterEqual(farm.coins, 0)

    def test_rain_and_sprinkler_do_not_spend_water_energy(self):
        for kwargs in ({'weather': 'rainy'}, {'sprinkler': True}):
            with self.subTest(**kwargs):
                farm = Farm(coins=0, **kwargs)
                auto = self.engine(farm, mode='farm')
                messages = self.run_until(auto)
                self.assertFalse(any('đã tưới nước' in message for message in messages))
                self.assertEqual(sum(plot.growth for plot in farm.plots.values()), 10)
                self.assertEqual(farm.day, 2)

    def test_sleep_happens_at_real_indoor_bed(self):
        for area, x, y in (('home', 2, 7), ('village', 10, 7)):
            farm = Farm(area=area, player_x=x, player_y=y, energy=0, coins=0)
            auto = self.engine(farm, mode='farm')
            for _ in range(250):
                before = deepcopy(farm)
                result = auto.step()
                if farm.day != before.day:
                    self.assertEqual(before.area, 'home')
                    self.assertTrue(world.is_near(before, 'bed'))
                    self.assertTrue(result.changed and result.done)
                    break
            else:
                self.fail('Auto could not reach the bed')

    def test_ranch_feeds_pets_collects_and_trades_through_the_barn(self):
        farm = Farm(coins=10, animals=[Animal('chicken', 'Một', age=2, produce=1),
                                      Animal('cow', 'Hai', age=3, produce=1)])
        farm.items['feed'] = 0
        chest = dict(farm.chest)
        auto = self.engine(farm, mode='ranch')
        observed_feed = observed_collection = False
        for _ in range(1500):
            before = deepcopy(farm)
            result = auto.step()
            if sum(animal.fed for animal in farm.animals) > sum(animal.fed for animal in before.animals):
                observed_feed = True
                self.assertTrue(world.is_near(farm, 'barn'))
            if sum(a.produce for a in farm.animals) < sum(a.produce for a in before.animals):
                observed_collection = True
                self.assertTrue(world.is_near(before, 'barn'))
            if result.done:
                break
        self.assertTrue(observed_feed and observed_collection)
        self.assertEqual([animal.friendship for animal in farm.animals], [1, 1])
        self.assertGreater(farm.sales, 0)
        self.assertEqual(farm.chest, chest)
        self.assertEqual((len(farm.animals), farm.size, farm.fish_caught), (2, 4, 0))
        self.assertFalse(any(plot.crop for plot in farm.plots.values()))

    def test_fishing_runs_real_physics_then_claims_one_actual_catch(self):
        farm = Farm(player_x=25, player_y=7, coins=0)
        auto = self.engine(farm, mode='fish')
        original_step = FishingRound.step
        with patch.object(FishingRound, 'step', autospec=True,
                          side_effect=original_step) as physics:
            self.run_until(auto, lambda: farm.fish_caught == 1)
            self.assertGreater(physics.call_count, 10)
        self.assertEqual(sum(farm.items[key] for key in FISH_TYPES), 1)
        self.assertEqual((farm.energy, farm.xp), (17, 5))
        self.assertFalse(any(plot.crop for plot in farm.plots.values()))
        self.assertEqual(farm.animals, [])

    def test_cast_and_cancel_never_claim_a_phantom_catch(self):
        farm = Farm(player_x=25, player_y=7)
        auto = self.engine(farm, mode='fish')
        self.run_until(auto, lambda: auto.fishing_round is not None)
        self.assertEqual(farm.energy, 17)
        self.assertEqual(farm.fish_caught, 0)
        for _ in range(3):
            self.assertFalse(auto.step().changed)
        auto.stop()
        before = deepcopy(farm)
        for _ in range(5):
            self.assertTrue(auto.step().done)
        self.assertEqual(farm, before)
        self.assertEqual(farm.fish_caught, 0)

    def test_all_mode_claims_completed_daily_rewards_once(self):
        farm = Farm()
        from farmgame.daily import DailyQuest, DailyState
        farm.daily = DailyState(day=farm.day, tasks=[DailyQuest('plant', 3),
            DailyQuest('water', 3), DailyQuest('work', 2), DailyQuest('talk', 2)])
        auto = self.engine(farm, days=1)
        self.run_until(auto, lambda: all(task.claimed for task in farm.daily.tasks))
        self.assertTrue(all(task.progress >= task.target for task in farm.daily.tasks))
        self.assertGreater(farm.xp, 0)
        claimed_coins = farm.coins
        claimed_xp = farm.xp
        from farmgame.daily import claim_all
        try:
            claim_all(farm)
        except ValueError:
            pass
        self.assertEqual((farm.coins, farm.xp), (claimed_coins, claimed_xp))

    def test_all_mode_buys_animals_upgrades_and_spends_only_available_points(self):
        farm = Farm(coins=4000, xp=120)
        auto = self.engine(farm)
        self.run_until(auto)
        self.assertEqual({animal.kind for animal in farm.animals}, set(ANIMAL_TYPES))
        self.assertTrue(farm.sprinkler)
        self.assertGreater(farm.size, 4)
        self.assertGreater(farm.max_energy, 20)
        self.assertGreater(sum(farm.attributes.values()), 0)
        self.assertGreater(sum(farm.skills.values()), 0)
        self.assertGreaterEqual(farm.attribute_points, 0)
        self.assertGreaterEqual(farm.skill_points, 0)
        self.assertGreaterEqual(farm.coins, 0)

    def test_specialist_modes_do_not_buy_animals_upgrades_or_allocate_points(self):
        for mode in ('farm', 'ranch', 'fish'):
            farm = Farm(coins=4000, xp=120)
            auto = self.engine(farm, mode=mode)
            self.run_until(auto)
            self.assertEqual(farm.animals, [])
            self.assertEqual((farm.size, farm.max_energy, farm.sprinkler), (4, 20, False))
            self.assertFalse(any(farm.attributes.values()))
            self.assertFalse(any(farm.skills.values()))

    def test_specialists_respect_mode_scope_even_with_an_active_tutorial(self):
        for mode in ('farm', 'ranch', 'fish'):
            with self.subTest(mode=mode):
                farm = Farm(coins=4000, xp=120)
                start_tutorial(farm)
                auto = self.engine(farm, mode=mode, days=3)
                self.run_until(auto)
                self.assertFalse(any(farm.attributes.values()))
                self.assertFalse(any(farm.skills.values()))
                self.assertFalse(farm.tutorial.reward_given)
                self.assertEqual((farm.size, farm.max_energy, farm.sprinkler), (4, 20, False))
                self.assertEqual(farm.animals, [])
                if mode != 'farm':
                    self.assertEqual(farm.harvested, 0)
                    self.assertFalse(any(plot.crop for plot in farm.plots.values()))
                if mode != 'fish':
                    self.assertEqual(farm.fish_caught, 0)

    def test_tutorial_performs_the_actual_fifteen_objectives(self):
        farm = Farm()
        start_tutorial(farm)
        auto = self.engine(farm, days=3)
        self.run_until(auto, lambda: farm.tutorial.status == 'completed')
        self.assertEqual(farm.tutorial.moves, 4)
        self.assertTrue(farm.tutorial.reward_given)
        self.assertGreaterEqual(farm.friendships['lan'], 1)
        self.assertGreater(farm.harvested, 0)
        self.assertGreater(farm.sales, 0)
        self.assertGreater(sum(farm.attributes.values()) + sum(farm.skills.values()), 0)
        self.assertIsNotNone(farm.tutorial.plot)
        self.assertGreaterEqual(farm.day, 2)

    def test_active_tutorial_also_feeds_existing_livestock_before_sleep(self):
        farm = Farm(animals=[Animal('chicken', 'Gà nhà', age=2)])
        start_tutorial(farm)
        auto = self.engine(farm, days=2)
        care_before_sleep = []
        real_sleep = Farm.sleep

        def sleep(farm, *args):
            care_before_sleep.append((farm.animals[0].fed, farm.animals[0].petted))
            return real_sleep(farm, *args)

        with patch.object(Farm, 'sleep', autospec=True, side_effect=sleep):
            self.run_until(auto, lambda: farm.day == 2)
        self.assertEqual(care_before_sleep, [(True, True)])

    def test_budget_fallback_keeps_the_route_home_between_ticks(self):
        farm = Farm(energy=0)
        auto = self.engine(farm, mode='farm')
        module = import_module('farmgame.automation')
        with patch.object(type(auto), '_DAY_STEP_LIMIT', 1):
            with patch.object(module, 'route', wraps=module.route) as routes:
                for _ in range(8):
                    self.assertTrue(auto.step().moved)
                self.assertLessEqual(routes.call_count, 2)

    def test_continuous_mode_can_advance_days_and_still_be_stopped(self):
        farm = Farm(energy=0)
        auto = self.engine(farm, mode='ranch', days=0)
        self.run_until(auto, lambda: farm.day == 3)
        self.assertFalse(auto.done)
        auto.stop()
        self.assertTrue(auto.done)

    def test_blocked_route_is_bounded_and_reports_the_problem(self):
        farm = Farm(energy=0)
        auto = self.engine(farm, mode='farm')
        module = import_module('farmgame.automation')
        with patch.object(module, 'route', return_value=(world.HOME_DOOR, (), 'M')):
            messages = self.run_until(auto, limit=12)
        self.assertEqual(farm.day, 1)
        self.assertTrue(any('đường' in message.lower() for message in messages))
        self.assertTrue(auto.done)

    def test_unexpected_action_error_stops_with_a_readable_message(self):
        farm = Farm(area='home', player_x=12, player_y=3, energy=0)
        auto = self.engine(farm, mode='farm')
        with patch.object(Farm, 'sleep', side_effect=RuntimeError('thử lỗi hành động')):
            messages = self.run_until(auto, limit=8)
        self.assertTrue(auto.done)
        self.assertIn('thử lỗi hành động', messages[-1])
        self.assertEqual(farm.day, 1)


if __name__ == '__main__':
    unittest.main()
