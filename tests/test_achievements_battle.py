"""Achievement milestones and the turn-based battle presentation."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from farmgame import mining, world
from collections import Counter

from farmgame import daily
from farmgame.achievements import (ACHIEVEMENTS, achievement_lines,
                                   achievement_score, tier_label,
                                   sync_achievements)
from farmgame.dungeon import (enemy_intent, player_attack, player_defend,
                              player_skill, start_run)
from farmgame.model import Farm, GameError
from farmgame.storage import load_game, save_game
from tests.test_floating_ui import CellScreen, curses_namespace
from farmgame.explore import ExplorerGame


class AchievementTests(unittest.TestCase):
    def test_defaults_are_all_locked_and_sync_is_idempotent(self):
        farm = Farm()
        self.assertEqual(set(farm.achievements), {item.id for item in ACHIEVEMENTS})
        self.assertFalse(any(farm.achievements.values()))
        self.assertEqual(sync_achievements(farm), [])
        farm.harvested = 1
        unlocked = sync_achievements(farm)
        self.assertEqual([item.id for item in unlocked], ['first_harvest'])
        self.assertTrue(farm.achievements['first_harvest'])
        self.assertEqual(sync_achievements(farm), [])
        self.assertGreater(achievement_score(farm), 0)
        self.assertTrue(any('Mầm xanh đầu tiên' in line
                            for line in achievement_lines(farm)))

    def test_achievement_families_have_five_equipment_tiers(self):
        families = Counter(item.family for item in ACHIEVEMENTS)
        self.assertEqual(len(families), 12)
        self.assertTrue(all(count == 5 for count in families.values()))
        self.assertEqual(len({item.id for item in ACHIEVEMENTS}),
                         len(ACHIEVEMENTS))
        self.assertIn('Huyền thoại', tier_label(5))
        farm = Farm()
        farm.harvested = 100
        unlocked = {item.id for item in sync_achievements(farm)}
        self.assertEqual(unlocked,
                         {'first_harvest', 'harvest_5', 'harvest_15',
                          'harvest_30', 'harvest_100'})

    def test_new_daily_quest_kinds_can_be_recorded(self):
        farm = Farm()
        kinds = ('forge', 'cook', 'dungeon', 'animal')
        for kind in kinds:
            self.assertIn(kind, daily.QUESTS)
        farm.daily = daily.DailyState(
            farm.day, [daily.DailyQuest(kind, 1) for kind in kinds])
        for kind in kinds:
            daily.record_daily(farm, kind)
        self.assertEqual([task.progress for task in farm.daily.tasks],
                         [1, 1, 1, 1])

    def test_mining_tracks_lifetime_swings_and_unlocks(self):
        farm = Farm(area='mine')
        rock = next(iter(world.MINE_ROCKS))
        farm.player_x, farm.player_y = rock[0], rock[1] + 1
        farm.energy = 20
        for _ in range(10):
            farm.mine_used.clear()
            mining.mine_rock(farm, *rock)
        self.assertEqual(farm.mined_total, 10)
        unlocked = sync_achievements(farm)
        self.assertIn('mine_10', [item.id for item in unlocked])

    def test_achievements_and_mining_total_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'save.json'
            farm = Farm()
            farm.mined_total = 7
            farm.achievements['first_harvest'] = True
            save_game(farm, path)
            loaded = load_game(path)
            self.assertEqual(loaded.mined_total, 7)
            self.assertTrue(loaded.achievements['first_harvest'])
            self.assertFalse(loaded.achievements['mine_100'])


class BattleTests(unittest.TestCase):
    def farm(self):
        farm = Farm()
        farm.gear['sword'] = 1
        farm.hp = farm.max_hp
        farm.items['thuoc'] = 2
        return farm

    def test_intent_telegraphs_every_third_enemy_action(self):
        farm = self.farm()
        run = start_run(farm)
        self.assertEqual(enemy_intent(run), 'Tấn công')
        run.turn = 2
        self.assertEqual(enemy_intent(run), 'Tung đòn mạnh')
        run.current().mp = 0
        self.assertEqual(enemy_intent(run), 'Tấn công')

    def test_guarding_halves_a_normal_enemy_hit(self):
        farm = self.farm()
        run = start_run(farm)
        run.current().hp = 100
        run.current().attack = 10
        farm.hp = farm.max_hp
        player_attack(farm, run)
        unguarded_loss = farm.max_hp - farm.hp
        farm.hp = farm.max_hp
        run.guard = False
        run.turn = 0
        run.current().hp = 100
        player_defend(farm, run)
        guarded_loss = farm.max_hp - farm.hp
        self.assertGreater(unguarded_loss, guarded_loss)
        self.assertGreaterEqual(guarded_loss, 1)

    @patch('farmgame.explore.save_game')
    def test_character_achievement_tab_lists_milestones(self, save):
        farm = self.farm()
        farm.harvested = 1
        sync_achievements(farm)
        game = ExplorerGame(farm, Path('/tmp/achievement-tab.json'), color=False)
        game._screen = CellScreen(24, 80)
        game._curses = curses_namespace()
        game._colors = {}
        game.coach = SimpleNamespace(event=Mock(), draw_curses=Mock(),
                                      path_points=lambda: set())
        game._read = Mock(side_effect=['\t', '\t', '\t', 'q'])
        game.handle_key('c')
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('THÀNH TỰU', rendered)
        self.assertIn('Mầm xanh đầu tiên', rendered)

    def test_skill_spends_mp_and_deals_heavy_damage(self):
        farm = self.farm()
        run = start_run(farm)
        enemy = run.current()
        enemy.hp = enemy.max_hp = 100
        before = enemy.hp
        player_skill(farm, run)
        self.assertEqual(run.mp, run.max_mp - 3)
        self.assertLess(enemy.hp, before - 6)
        run.mp = 0
        with self.assertRaises(GameError):
            player_skill(farm, run)

    @patch('farmgame.explore.save_game')
    def test_battle_panel_has_arena_actions_and_defend_key(self, save):
        farm = self.farm()
        game = ExplorerGame(farm, Path('/tmp/achievement-battle.json'),
                            color=False)
        game._screen = CellScreen(24, 80)
        game._curses = curses_namespace()
        game._colors = {}
        game.coach = SimpleNamespace(event=Mock(), draw_curses=Mock(),
                                      path_points=lambda: set())
        game._read = Mock(side_effect=['4', '3'])
        game._dungeon()
        rendered = '\n'.join(game._screen.lines())
        self.assertIn('HÀNH ĐỘNG', rendered)
        self.assertIn('[4] Đỡ đòn', rendered)
        self.assertIn('Ý định:', rendered)
        self.assertIn('NHẬT KÝ', rendered)
        self.assertIn('BẠN', rendered)
        self.assertIn('HP', rendered)
        self.assertIn('MP', rendered)
        self.assertTrue(game._screen.lines()[0].startswith('╭'))
        self.assertTrue(save.called)


if __name__ == '__main__':
    unittest.main()
