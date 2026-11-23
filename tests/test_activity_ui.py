"""Real controllers remain interruptible and checkpoint automated movement."""
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from farmgame.explore import ExplorerGame
from farmgame.model import Farm
from farmgame.storage import load_game
from farmgame.terminal import TerminalGame


class ActivityControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'farm.json'
        self.farm = Farm()
        self.game = ExplorerGame(self.farm, self.path, color=False)

    def test_o_opens_auto_choices_without_moving_before_first_tick(self):
        before = self.farm.player_x, self.farm.player_y
        self.game._choose = Mock(side_effect=[1, 0, 2])
        self.game.handle_key('o')
        activities = getattr(self.game, 'activities', None)
        self.assertIsNotNone(activities, 'O must open the real automation menu')
        self.assertTrue(activities.running)
        self.assertEqual((self.farm.player_x, self.farm.player_y), before)
        self.assertEqual(activities.auto.options.mode, 'farm')
        self.assertEqual(activities.auto.options.days, 1)

    def test_n_claims_completed_quest_and_saves_reward_once(self):
        for key in ('A1', 'B1', 'C1'):
            self.farm.plant(key, 'lua_mi')
        self.game._choose = Mock(side_effect=[0, None])
        self.game.handle_key('n')
        restored = load_game(self.path)
        self.assertEqual((restored.coins, restored.xp), (135, 3))
        self.assertTrue(restored.daily.tasks[0].claimed)
        self.game._choose = Mock(side_effect=[0, None])
        self.game.handle_key('n')
        self.assertEqual((self.farm.coins, self.farm.xp), (135, 3))

    def test_text_board_uses_same_claim_and_retains_daily_state(self):
        for key in ('A1', 'B1', 'C1'):
            self.farm.plant(key, 'lua_mi')
        ui = TerminalGame(self.farm, self.path, color=False, clear_screen=False)
        ui.ask = Mock(side_effect=['n', '1', '0', '0'])
        with redirect_stdout(StringIO()) as output:
            result = ui.run()
        self.assertEqual(result, 0)
        self.assertIn('NHIỆM VỤ NGÀY 1', output.getvalue())
        restored = load_game(self.path)
        self.assertEqual((restored.coins, restored.xp), (135, 3))
        self.assertTrue(restored.daily.tasks[0].claimed)

    def test_space_pauses_and_manual_movement_stops_auto(self):
        self.game._choose = Mock(side_effect=[1, 0, 2])
        self.game.handle_key('o')
        self.game.handle_key(' ')
        before = asdict(self.farm)
        for tick in range(20):
            self.game.activities.tick(tick + 1)
        self.assertEqual(asdict(self.farm), before)
        self.game.handle_key('s')
        self.assertFalse(self.game.activities.running)
        self.assertEqual((self.farm.player_x, self.farm.player_y), (10, 8))
        self.assertEqual(asdict(load_game(self.path)), asdict(self.farm))

    def test_movement_is_checkpointed_and_stop_flushes_latest_position(self):
        self.game._choose = Mock(side_effect=[1, 0, 2])
        self.game.handle_key('o')
        saved = []
        original_save = self.game._save
        def save():
            saved.append((self.farm.area, self.farm.player_x, self.farm.player_y))
            return original_save()
        self.game.activities.save_callback = save
        moves = 0
        for tick in range(25):
            before = self.farm.area, self.farm.player_x, self.farm.player_y
            self.game.activities.tick(tick * 0.1)
            after = self.farm.area, self.farm.player_x, self.farm.player_y
            moves += before != after
        self.assertGreater(moves, 10)
        self.assertLess(len(saved), moves // 2)
        self.game.handle_key('o')
        self.assertFalse(self.game.activities.running)
        self.assertEqual(asdict(load_game(self.path)), asdict(self.farm))

    def test_failed_checkpoint_stops_automation_without_further_mutation(self):
        self.game._choose = Mock(side_effect=[1, 0, 2])
        self.game.handle_key('o')
        self.game.activities.save_callback = lambda: False
        for tick in range(30):
            self.game.activities.tick(tick + 1)
            if not self.game.activities.running:
                break
        self.assertFalse(self.game.activities.running)
        before = asdict(self.farm)
        self.game.activities.tick(200)
        self.assertEqual(asdict(self.farm), before)
        self.assertIn('lưu', self.game.messages[-1].lower())


if __name__ == '__main__':
    unittest.main()
