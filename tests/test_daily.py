import random
import unittest
from dataclasses import asdict

from farmgame import daily
from farmgame.animals import Animal, collect_products, feed_animals, pet_animal
from farmgame.daily import DailyQuest, DailyState, ensure_daily
from farmgame.fishing import finish_fishing, start_fishing
from farmgame.model import Farm, GameError, Plot
from farmgame.villagers import talk


class DailyBoardTests(unittest.TestCase):
    def board(self, farm):
        self.assertIsNotNone(getattr(farm, 'daily', None))
        return ensure_daily(farm)

    def test_board_is_lazy_and_stays_fixed_during_the_day(self):
        farm = Farm()
        self.assertIsNotNone(getattr(farm, 'daily', None))
        self.assertEqual((farm.daily.day, farm.daily.tasks), (0, []))
        board = self.board(farm)
        self.assertEqual(board.day, 1)
        self.assertEqual(len(board.tasks), 4)
        self.assertEqual(len({task.kind for task in board.tasks}), 4)
        before = asdict(board)
        farm.sprinkler = True
        farm.coins += 100
        self.assertIs(self.board(farm), board)
        self.assertEqual(asdict(board), before)

    def test_new_farm_does_not_get_harvest_or_animal_tasks(self):
        for day in range(1, 13):
            with self.subTest(day=day):
                kinds = {task.kind for task in self.board(Farm(day=day)).tasks}
                self.assertFalse(kinds & {'harvest', 'feed', 'pet', 'collect'})

    def test_rain_and_sprinkler_never_assign_watering(self):
        for day in range(1, 13):
            for options in ({'weather': 'rainy'}, {'sprinkler': True}):
                with self.subTest(day=day, options=options):
                    board = self.board(Farm(day=day, **options))
                    self.assertEqual(len(board.tasks), 4)
                    self.assertNotIn('water', {task.kind for task in board.tasks})

    def test_available_crop_and_animal_tasks_appear_across_days(self):
        seen = set()
        for day in range(1, 21):
            farm = Farm(day=day, animals=[Animal('chicken', 'Mây', produce=1)])
            farm.plots['A1'] = Plot('lua_mi', growth=1)
            seen.update(task.kind for task in self.board(farm).tasks)
        self.assertTrue({'harvest', 'feed', 'pet', 'collect'} <= seen)

    def test_already_fed_and_petted_animals_do_not_get_impossible_repeat_care(self):
        for day in range(1, 21):
            for fed, petted in ((True, False), (False, True), (True, True)):
                with self.subTest(day=day, fed=fed, petted=petted):
                    farm = Farm(day=day, animals=[
                        Animal('chicken', 'Mây', fed=fed, petted=petted),
                    ])
                    before = (asdict(farm.animals[0]), farm.items['feed'], farm.xp)
                    kinds = {task.kind for task in self.board(farm).tasks}
                    if fed:
                        self.assertNotIn('feed', kinds)
                    if petted:
                        self.assertNotIn('pet', kinds)
                    self.assertEqual(len(kinds), 4)
                    self.assertEqual((asdict(farm.animals[0]), farm.items['feed'], farm.xp),
                                     before)

    def test_mixed_herd_can_get_care_for_animals_that_still_need_it(self):
        seen = set()
        for day in range(1, 21):
            farm = Farm(day=day, animals=[
                Animal('chicken', 'Mây', fed=True),
                Animal('cow', 'Sữa', petted=True),
            ])
            seen.update(task.kind for task in self.board(farm).tasks)
        self.assertTrue({'feed', 'pet'} <= seen)

    def test_targets_fit_limited_planting_and_watering_space(self):
        seen = set()
        for day in range(1, 13):
            farm = Farm(day=day)
            for key in farm.plots:
                farm.plots[key] = Plot('ca_rot', watered=True)
            farm.plots['A1'] = Plot()
            for task in self.board(farm).tasks:
                if task.kind in {'plant', 'water'}:
                    seen.add(task.kind)
                    self.assertEqual(task.target, 1)
        self.assertEqual(seen, {'plant', 'water'})

    def test_sleep_replaces_old_progress_after_new_day_weather_is_set(self):
        farm = Farm()
        old_board = self.board(farm)
        old_board.tasks[0].progress = old_board.tasks[0].target
        old_board.tasks[0].claimed = True
        farm.sleep('rainy')
        self.assertEqual((farm.day, farm.daily.day), (2, 2))
        self.assertIsNot(farm.daily, old_board)
        self.assertEqual(len(farm.daily.tasks), 4)
        self.assertNotIn('water', {task.kind for task in farm.daily.tasks})
        self.assertTrue(all(task.progress == 0 and not task.claimed
                            for task in farm.daily.tasks))
        self.assertNotEqual([task.kind for task in old_board.tasks],
                            [task.kind for task in farm.daily.tasks])


class DailyRewardTests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm(daily=DailyState(1, [
            DailyQuest('plant', 3), DailyQuest('work', 2),
            DailyQuest('talk', 2), DailyQuest('sell', 40),
        ]))

    def test_progress_caps_without_granting_rewards(self):
        daily.record_daily(self.farm, 'plant', 2)
        self.assertEqual(self.farm.daily.tasks[0].progress, 2)
        daily.record_daily(self.farm, 'plant', 999)
        self.assertEqual(self.farm.daily.tasks[0].progress, 3)
        self.assertFalse(self.farm.daily.tasks[0].claimed)
        self.assertEqual((self.farm.coins, self.farm.xp), (120, 0))

    def test_invalid_or_unrelated_progress_does_not_change_the_board(self):
        before = asdict(self.farm)
        for amount in (0, -1, True, 1.5, '1', None):
            daily.record_daily(self.farm, 'plant', amount)
        daily.record_daily(self.farm, 'missing', 3)
        self.assertEqual(asdict(self.farm), before)

    def test_claiming_requires_valid_index_and_completed_task(self):
        for index in (-1, 4, True, 1.5, '0', None, 0):
            with self.subTest(index=index):
                before = asdict(self.farm)
                with self.assertRaises(GameError):
                    daily.claim_quest(self.farm, index)
                self.assertEqual(asdict(self.farm), before)

    def test_reward_is_manual_uses_normal_xp_and_can_only_be_claimed_once(self):
        self.farm.attributes['focus'] = 2
        self.farm.xp = 39
        self.farm.daily.tasks[0].progress = 3
        message = daily.claim_quest(self.farm, 0)
        self.assertEqual((self.farm.coins, self.farm.xp), (135, 44))
        self.assertTrue(self.farm.daily.tasks[0].claimed)
        self.assertIn('15', message)
        self.assertIn('LÊN CẤP', message)
        before = asdict(self.farm)
        with self.assertRaises(GameError):
            daily.claim_quest(self.farm, 0)
        self.assertEqual(asdict(self.farm), before)

    def test_claim_all_only_rewards_completed_unclaimed_tasks(self):
        self.farm.daily.tasks[0].progress = 3
        self.farm.daily.tasks[1].progress = 2
        self.farm.daily.tasks[2].progress = 1
        self.farm.daily.tasks[3].progress = 40
        self.farm.daily.tasks[3].claimed = True
        self.assertTrue(daily.claim_all(self.farm))
        self.assertEqual((self.farm.coins, self.farm.xp), (147, 6))
        self.assertEqual([task.claimed for task in self.farm.daily.tasks],
                         [True, True, False, True])
        before = asdict(self.farm)
        self.assertTrue(daily.claim_all(self.farm))
        self.assertEqual(asdict(self.farm), before)

    def test_board_lines_show_progress_rewards_and_claim_status(self):
        self.farm.daily.tasks[0].progress = 3
        self.farm.daily.tasks[1].progress = 2
        self.farm.daily.tasks[1].claimed = True
        before = asdict(self.farm)
        lines = daily.daily_lines(self.farm)
        self.assertIn('ngày 1', lines[0].lower())
        self.assertTrue(any('3/3' in line and '15 xu' in line
                            and 'Nhận thưởng' in line for line in lines))
        self.assertTrue(any('Đã nhận' in line for line in lines))
        self.assertTrue(any('1.' in line for line in lines))
        self.assertEqual(asdict(self.farm), before)


class DailyActionTests(unittest.TestCase):
    def farm_for(self, *kinds, **options):
        farm = Farm(**options)
        farm.daily = DailyState(farm.day, [
            DailyQuest(kind, daily.QUESTS[kind].target) for kind in kinds
        ])
        return farm

    def test_planting_and_watering_count_successful_actions_only(self):
        farm = self.farm_for('plant', 'water', 'harvest', 'sell')
        farm.plant('A1', 'ca_rot')
        farm.plant('B1', 'lua_mi')
        farm.water('A1')
        self.assertEqual([task.progress for task in farm.daily.tasks], [2, 1, 0, 0])
        self.assertEqual((farm.coins, farm.xp, farm.energy), (120, 0, 15))
        before = asdict(farm)
        for action in (lambda: farm.plant('A1', 'ca_rot'),
                       lambda: farm.water('A1'),
                       lambda: farm.harvest('A1'),
                       lambda: farm.water('C1')):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)

    def test_harvest_and_sale_track_real_products_and_revenue(self):
        farm = self.farm_for('harvest', 'sell', 'work', 'talk')
        farm.plots['A1'] = Plot('ca_rot', growth=2)
        farm.plots['B1'] = Plot('ca_rot', growth=2)
        farm.harvest('A1')
        farm.sell_all()
        self.assertEqual([task.progress for task in farm.daily.tasks], [1, 24, 0, 0])
        self.assertEqual((farm.coins, farm.xp), (144, 5))
        farm.harvest('B1')
        farm.sell_all()
        self.assertEqual(farm.daily.tasks[1].progress, 40)
        self.assertEqual((farm.coins, farm.xp), (168, 10))
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.sell_all()
        self.assertEqual(asdict(farm), before)

    def test_work_counts_without_adding_daily_reward_automatically(self):
        farm = self.farm_for('work', 'sell', 'fish', 'talk', energy=4)
        farm.work()
        self.assertEqual(farm.daily.tasks[0].progress, 1)
        self.assertEqual((farm.coins, farm.xp, farm.items['wood']), (126, 2, 1))
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.work()
        self.assertEqual(asdict(farm), before)

    def test_failed_first_action_keeps_lazy_board_and_entire_farm_unchanged(self):
        farm = Farm(energy=0)
        before = asdict(farm)
        for action in (lambda: farm.plant('A1', 'ca_rot'), farm.work,
                       lambda: farm.water('A1'), farm.sell_all,
                       lambda: farm.sleep('invalid')):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)

    def test_first_action_gets_credit_for_last_plantable_space(self):
        farm = Farm()
        for key in farm.plots:
            farm.plots[key] = Plot('ca_rot', watered=True)
        farm.plots['A1'] = Plot()
        farm.plant('A1', 'lua_mi')
        task = next((task for task in farm.daily.tasks if task.kind == 'plant'), None)
        self.assertIsNotNone(task)
        self.assertEqual((task.target, task.progress), (1, 1))

    def test_first_action_gets_credit_for_last_dry_crop(self):
        farm = Farm()
        for key in farm.plots:
            farm.plots[key] = Plot('ca_rot', watered=True)
        farm.plots['A1'].watered = False
        farm.water('A1')
        task = next((task for task in farm.daily.tasks if task.kind == 'water'), None)
        self.assertIsNotNone(task)
        self.assertEqual((task.target, task.progress), (1, 1))

    def test_first_harvest_generates_board_before_consuming_last_ripe_crop(self):
        farm = Farm(day=3)
        farm.plots['A1'] = Plot('lua_mi', growth=1)
        farm.harvest('A1')
        task = next((task for task in farm.daily.tasks if task.kind == 'harvest'), None)
        self.assertIsNotNone(task)
        self.assertEqual(task.progress, 1)

    def test_animal_care_and_collection_count_once_and_fail_atomically(self):
        farm = self.farm_for('feed', 'pet', 'collect', 'work',
                             animals=[Animal('chicken', 'Mây', produce=2)])
        feed_animals(farm)
        pet_animal(farm, 0)
        collect_products(farm)
        self.assertEqual([task.progress for task in farm.daily.tasks], [1, 1, 1, 0])
        self.assertEqual((farm.coins, farm.xp, farm.items['egg']), (120, 6, 2))
        before = asdict(farm)
        for action in (lambda: feed_animals(farm),
                       lambda: pet_animal(farm, 0),
                       lambda: collect_products(farm)):
            with self.assertRaises(GameError):
                action()
            self.assertEqual(asdict(farm), before)

    def test_first_collection_generates_board_before_consuming_last_product(self):
        farm = Farm(day=9, animals=[Animal('chicken', 'Mây', produce=1)])
        collect_products(farm)
        task = next((task for task in farm.daily.tasks if task.kind == 'collect'), None)
        self.assertIsNotNone(task)
        self.assertEqual(task.progress, 1)

    def test_caught_fish_counts_after_real_round_and_never_twice(self):
        farm = self.farm_for('fish', 'talk', 'work', 'sell', player_x=21, player_y=9)
        round_ = start_fishing(farm, random.Random(7))
        self.assertEqual(farm.daily.tasks[0].progress, 0)
        for _ in range(1200):
            round_.step(0.05, round_.bar + round_.velocity * 0.35 < round_.target)
            if round_.done:
                break
        self.assertTrue(round_.caught)
        finish_fishing(farm, round_)
        self.assertEqual((farm.daily.tasks[0].progress, farm.fish_caught), (1, 1))
        self.assertEqual((farm.coins, farm.xp), (120, 5))
        before = asdict(farm)
        with self.assertRaises(GameError):
            finish_fishing(farm, round_)
        self.assertEqual(asdict(farm), before)

    def test_escaped_fish_does_not_change_any_daily_progress(self):
        farm = self.farm_for('fish', 'talk', 'work', 'sell', player_x=21, player_y=9)
        round_ = start_fishing(farm, random.Random(7))
        for _ in range(1200):
            round_.step(0.05, False)
            if round_.done:
                break
        self.assertTrue(round_.done)
        self.assertFalse(round_.caught)
        before = asdict(farm)
        finish_fishing(farm, round_)
        self.assertEqual(asdict(farm), before)

    def test_each_villager_counts_once_daily_even_at_maximum_friendship(self):
        farm = self.farm_for('talk', 'fish', 'work', 'sell', player_x=28, player_y=4)
        farm.friendships['lan'] = 10
        talk(farm, 'lan')
        self.assertEqual(farm.daily.tasks[0].progress, 1)
        talk(farm, 'lan', 'work')
        self.assertEqual(farm.daily.tasks[0].progress, 1)
        before = asdict(farm)
        with self.assertRaises(GameError):
            talk(farm, 'mai')
        self.assertEqual(asdict(farm), before)
        farm.player_x, farm.player_y = 30, 9
        talk(farm, 'tu')
        self.assertEqual(farm.daily.tasks[0].progress, 2)
        self.assertEqual((farm.coins, farm.xp), (120, 0))

    def test_sprinkler_upgrade_counts_only_crops_that_actually_gain_water(self):
        farm = self.farm_for('water', 'plant', 'work', 'talk', coins=400)
        farm.plots['A1'] = Plot('ca_rot')
        farm.plots['B1'] = Plot('ca_rot', watered=True)
        farm.plots['C1'] = Plot('lua_mi', growth=1)
        farm.plots['D1'] = Plot('ca_rot', dead=True)
        board = farm.daily
        farm.upgrade('sprinkler')
        self.assertTrue(farm.sprinkler)
        self.assertTrue(farm.is_watered('A1'))
        self.assertIs(farm.daily, board)
        self.assertEqual([task.progress for task in farm.daily.tasks], [1, 0, 0, 0])
        self.assertEqual((farm.coins, farm.xp, farm.energy), (100, 0, 20))
        before = asdict(farm)
        with self.assertRaises(GameError):
            farm.upgrade('sprinkler')
        self.assertEqual(asdict(farm), before)

    def test_new_plants_under_sprinkler_progress_existing_water_quest_per_plot(self):
        farm = self.farm_for('water', 'plant', 'work', 'talk', sprinkler=True)
        farm.plant('A1', 'ca_rot')
        self.assertEqual([task.progress for task in farm.daily.tasks], [1, 1, 0, 0])
        farm.plant('B1', 'lua_mi')
        self.assertEqual([task.progress for task in farm.daily.tasks], [2, 2, 0, 0])
        farm.plant('C1', 'lua_mi')
        self.assertEqual([task.progress for task in farm.daily.tasks], [3, 3, 0, 0])
        self.assertTrue(farm.is_watered('C1'))
        self.assertEqual((farm.coins, farm.xp), (120, 0))
        self.assertFalse(farm.daily.tasks[0].claimed)

    def test_rain_already_supplies_water_so_sprinkler_upgrade_cannot_count_it_again(self):
        farm = self.farm_for('water', 'plant', 'work', 'talk',
                             weather='rainy', coins=400)
        farm.plots['A1'] = Plot('ca_rot')
        farm.upgrade('sprinkler')
        self.assertEqual(farm.daily.tasks[0].progress, 0)


if __name__ == '__main__':
    unittest.main()


class ExtendedDailyQuestTests(unittest.TestCase):
    def board(self, *tasks):
        return Farm(daily=DailyState(1, [DailyQuest(kind, target)
                                         for kind, target in tasks]))

    def test_clear_buy_and_upgrade_actions_count_once(self):
        farm = self.board(('clear', 1), ('buy', 3), ('upgrade', 1), ('work', 1))
        farm.plots['A1'] = Plot('ca_rot', dead=True)
        farm.clear('A1')
        self.assertEqual(farm.daily.tasks[0].progress, 1)
        farm.coins = 1000
        farm.buy_seeds('ca_rot', 3)
        self.assertEqual(farm.daily.tasks[1].progress, 3)
        farm.upgrade('land')
        self.assertEqual(farm.daily.tasks[2].progress, 1)

    def test_new_fish_and_selling_fish_count_in_the_journal_quests(self):
        from farmgame.fishing import FishingRound
        from farmgame.catalog import FISH_TYPES
        farm = self.board(('catch_new', 1), ('sell_fish', 2), ('fish', 1), ('sell', 10))
        round_ = FishingRound(random.Random(2))
        round_.fish_key = 'ca_tram'
        round_.done = True
        round_.caught = True
        finish_fishing(farm, round_)
        self.assertEqual(farm.daily.tasks[0].progress, 1)
        self.assertEqual(farm.items['ca_tram'], 1)
        farm.items['ca_ro'] = 2
        farm.sell_all()
        self.assertEqual(farm.daily.tasks[1].progress, 2)
        self.assertEqual(farm.daily.tasks[2].progress, 1)
        self.assertGreaterEqual(farm.daily.tasks[3].progress, 10)
        self.assertIn(farm.fish_collection['ca_tram'], (0, 1))
        self.assertEqual(farm.fish_collection['ca_tram'], 1)
        self.assertGreater(FISH_TYPES['ca_tram'].points, 0)

    def test_new_quests_rotate_into_the_daily_board(self):
        seen = set()
        for day in range(1, 40):
            farm = Farm(day=day)
            farm.coins = 1000
            seen.update(task.kind for task in ensure_daily(farm).tasks)
        self.assertTrue({'clear', 'buy', 'upgrade', 'catch_new'} & seen)
