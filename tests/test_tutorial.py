"""Tutorial follows successful play, with navigation and recoverable state."""
from copy import deepcopy
import unittest

from farmgame.model import Farm, GameError
from farmgame.progression import upgrade_attribute
from farmgame.tutorial import (STEPS, TutorialState, current_step, pause_tutorial,
    record_event, resume_tutorial, skip_tutorial, start_tutorial, sync_tutorial,
    tutorial_hint, tutorial_lines)
from farmgame import world
from farmgame.villagers import npc_at


class TutorialTests(unittest.TestCase):
    def at_step(self, step):
        farm = Farm()
        start_tutorial(farm)
        farm.tutorial.step = step
        return farm

    def test_default_and_contract(self):
        farm = Farm()
        self.assertEqual(farm.tutorial, TutorialState())
        self.assertEqual([s.id for s in STEPS], ['map', 'movement', 'talk', 'bag',
            'buy', 'field', 'plant', 'water', 'home', 'tv', 'sleep', 'harvest',
            'sell', 'character', 'upgrade'])
        self.assertIsNone(current_step(farm))

    def test_wrong_actions_failed_actions_and_movement(self):
        farm = self.at_step(0)
        self.assertEqual(record_event(farm, 'bag'), '')
        self.assertEqual(farm.tutorial.step, 0)
        record_event(farm, 'map')
        for _ in range(4):
            old = farm.player_x, farm.player_y
            self.assertTrue(world.move(farm, 'right'))
            record_event(farm, 'move', from_x=old[0], from_y=old[1])
        self.assertEqual(current_step(farm).id, 'talk')
        record_event(farm, 'talk', npc_id='lan', done=False)
        record_event(farm, 'talk', npc_id='an', done=True)
        self.assertEqual(current_step(farm).id, 'talk')
        record_event(farm, 'talk', npc_id='lan', done=True)
        self.assertEqual(current_step(farm).id, 'bag')
        farm.tutorial.step = 4
        farm.coins = 0
        before = deepcopy(farm)
        with self.assertRaises(GameError):
            farm.buy_seeds('lua_mi', 1)
        self.assertEqual(farm, before)

    def test_real_farming_sequence_same_plot_and_reward_once(self):
        farm = self.at_step(4)
        farm.buy_seeds('lua_mi', 1)
        self.assertEqual(current_step(farm).id, 'field')
        farm.player_x, farm.player_y = 26, 42
        farm.facing = 'left'
        sync_tutorial(farm)
        farm.plant('A1', 'lua_mi')
        self.assertEqual(farm.tutorial.plot, 'A1')
        farm.plant('B1', 'lua_mi')
        farm.water('B1')
        self.assertEqual(current_step(farm).id, 'water')
        farm.water('A1')
        self.assertEqual(current_step(farm).id, 'home')
        record_event(farm, 'enter_home')
        self.assertEqual(current_step(farm).id, 'tv')
        day = farm.day
        farm.forecast_report()
        record_event(farm, 'tv')
        self.assertEqual(farm.day, day)
        farm.sleep('sunny')
        self.assertEqual(current_step(farm).id, 'harvest')
        farm.harvest('A1')
        self.assertEqual(current_step(farm).id, 'sell')
        farm.sell_all()
        self.assertEqual(current_step(farm).id, 'character')
        before = farm.xp
        tutorial_lines(farm)
        tutorial_hint(farm)
        self.assertEqual(farm.xp, before)
        record_event(farm, 'character')
        self.assertEqual(farm.xp, before + 40)
        self.assertTrue(farm.tutorial.reward_given)
        completion = upgrade_attribute(farm, 'endurance')
        self.assertEqual(farm.tutorial.status, 'completed')
        self.assertIn('15 bước', completion)
        start_tutorial(farm)
        self.assertEqual(farm.tutorial.status, 'completed')
        self.assertEqual(farm.xp, before + 40)

    def test_paused_tracks_and_skip_restart_preserves_reward(self):
        farm = self.at_step(13)
        pause_tutorial(farm)
        self.assertIsNone(tutorial_hint(farm))
        record_event(farm, 'character')
        self.assertEqual(farm.xp, 40)
        resume_tutorial(farm)
        skip_tutorial(farm)
        start_tutorial(farm)
        self.assertTrue(farm.tutorial.reward_given)
        farm.tutorial.step = 13
        record_event(farm, 'character')
        self.assertEqual(farm.xp, 40)

    def test_rain_and_dead_missing_recovery(self):
        for wet in ('rain', 'sprinkler'):
            farm = self.at_step(6)
            farm.weather = 'rainy' if wet == 'rain' else 'sunny'
            farm.sprinkler = wet == 'sprinkler'
            farm.plant('A1', 'lua_mi')
            self.assertEqual(current_step(farm).id, 'home')
            self.assertEqual(farm.tutorial.watered_on, 1)
            farm.plots['A1'].dead = True
            self.assertTrue(sync_tutorial(farm))
            self.assertEqual(current_step(farm).id, 'plant')
            self.assertIn('dọn', tutorial_hint(farm).body.lower())
            farm.clear('A1')
            farm.plant('A1', 'lua_mi')
            self.assertEqual(current_step(farm).id, 'home')
            farm.tutorial.step = 11
            farm.plots['A1'].crop = None
            sync_tutorial(farm)
            self.assertEqual(current_step(farm).id, 'plant')

    def follow_hint(self, farm):
        hint = tutorial_hint(farm)
        before = deepcopy(farm)
        self.assertEqual(tutorial_hint(farm), hint)
        tutorial_lines(farm)
        self.assertEqual(farm, before)
        last = (farm.player_x, farm.player_y)
        for point in hint.path:
            if point == last:
                continue
            self.assertEqual(abs(point[0]-last[0])+abs(point[1]-last[1]), 1)
            self.assertTrue(world.walkable(farm.area, *point, farm.size))
            self.assertIsNone(npc_at(*point, farm.area))
            last = point
        farm.player_x, farm.player_y = last
        return hint

    def test_bfs_lan_shop_home_indoor_and_field(self):
        for step, expected in ((2, 'npc'), (4, 'shop'), (8, 'home')):
            farm = self.at_step(step)
            self.follow_hint(farm)
            self.assertEqual(world.context(farm)[0], expected)
        farm = self.at_step(9)
        self.follow_hint(farm)
        self.assertTrue(world.is_near(farm, 'home'))
        world.enter_home(farm)
        self.follow_hint(farm)
        self.assertTrue(world.is_near(farm, 'tv'))
        farm.tutorial.step = 4
        self.follow_hint(farm)
        self.assertTrue(world.is_near(farm, 'exit'))
        farm = self.at_step(6)
        self.follow_hint(farm)
        self.assertEqual(world.context(farm)[0], 'plot')

    def test_plot_route_finishes_with_exact_target_including_facing(self):
        for coordinate in ('A1', 'B2', 'D4'):
            farm = self.at_step(7)
            farm.plots[coordinate].crop = 'lua_mi'
            farm.tutorial.plot = coordinate
            hint = tutorial_hint(farm)
            for x, y in hint.path:
                dx, dy = x - farm.player_x, y - farm.player_y
                direction = {(0, -1): 'up', (0, 1): 'down',
                             (-1, 0): 'left', (1, 0): 'right'}[dx, dy]
                self.assertTrue(world.move(farm, direction))
            self.assertEqual(world.target_plot(farm), coordinate)
            self.assertEqual(tutorial_hint(farm).key, 'E')

    def test_recovery_hints_do_not_grant_resources(self):
        farm = self.at_step(6)
        farm.energy = 0
        self.assertIn('ngủ', tutorial_hint(farm).body.lower())
        farm.energy = 20
        farm.seeds['lua_mi'] = 0
        self.assertIn('mua', tutorial_hint(farm).body.lower())
        farm.coins = 0
        self.assertIn('thuê', tutorial_hint(farm).body.lower())
        farm.seeds['lua_mi'] = 1
        for plot in farm.plots.values():
            plot.crop = 'ca_rot'
        self.assertIn('đầy', tutorial_hint(farm).body.lower())

    def test_all_max_character_completes(self):
        farm = self.at_step(13)
        farm.attributes = dict.fromkeys(farm.attributes, 5)
        farm.skills = dict.fromkeys(farm.skills, 5)
        record_event(farm, 'character')
        self.assertEqual(farm.tutorial.status, 'completed')

    def test_replaced_crop_recovery_uses_new_empty_plot(self):
        farm = self.at_step(11)
        farm.tutorial.plot = 'A1'
        farm.plots['A1'].crop = 'ca_rot'
        self.assertTrue(sync_tutorial(farm))
        self.assertIsNone(farm.tutorial.plot)
        self.assertEqual(current_step(farm).id, 'plant')
        self.assertIn('B1', tutorial_hint(farm).body)
        farm.plant('B1', 'lua_mi')
        self.assertEqual(farm.tutorial.plot, 'B1')
        self.assertEqual(current_step(farm).id, 'water')
        self.assertEqual(farm.plots['A1'].crop, 'ca_rot')

    def test_full_field_guides_watering_sleep_and_harvesting(self):
        farm = self.at_step(6)
        for plot in farm.plots.values():
            plot.crop = 'ca_rot'
        self.assertIn('Tưới', tutorial_hint(farm).body)
        for plot in farm.plots.values():
            plot.watered = True
        hint = tutorial_hint(farm)
        self.assertIn('ngủ', hint.body)
        self.assertEqual(hint.target, world.HOME_DOOR)
        for plot in farm.plots.values():
            plot.growth = 100
        self.assertIn('Thu hoạch', tutorial_hint(farm).body)
        farm.harvest('A1')
        self.assertIn('A1', tutorial_hint(farm).body)
        farm.plant('A1', 'lua_mi')
        self.assertEqual(current_step(farm).id, 'water')
