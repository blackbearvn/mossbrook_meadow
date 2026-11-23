"""Toast cards, compact HUD goals and the upgraded automation modes."""
import random
import unittest
from pathlib import Path

from farmgame import world
from farmgame.automation import Automation, AutoOptions, _Intent
from farmgame.explore import ExplorerGame
from farmgame.map_view import objective_line
from farmgame.model import Farm
from farmgame.navigation import route
from farmgame.toast import Toast, ToastCenter, classify, draw_toasts, toast_text
from farmgame.tui import cells


class FakeToastUI:
    def __init__(self):
        self.writes = []

    def _put(self, y, x, text, color='', bold=False):
        self.writes.append((y, x, text, color, bold))


class ToastTests(unittest.TestCase):
    def test_push_dedupes_recent_identical_messages_and_expires(self):
        center = ToastCenter(clock=lambda: 10.0)
        self.assertTrue(center.push('Đã lưu ván chơi.', now=10.0))
        self.assertTrue(center.push('Đã lưu ván chơi.', now=10.5))
        visible = center.visible(now=10.5)
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0].repeat, 2)
        self.assertEqual(visible[0].kind, 'success')
        self.assertEqual(center.visible(now=15.0), [])
        self.assertTrue(center.tick(now=15.0))
        self.assertEqual(len(center), 0)

    def test_classify_uses_errors_rewards_and_auto_prefix(self):
        self.assertEqual(classify('Không thể đào vì hết năng lượng.'), 'error')
        self.assertEqual(classify('Bạn nhận 15 xu!'), 'reward')
        self.assertEqual(classify('Auto đang chạy.'), 'auto')
        self.assertEqual(classify('Đã lưu ván chơi.'), 'success')
        self.assertEqual(classify('Hôm nay trời nắng.'), 'info')

    def test_draw_toasts_is_a_compact_ascii_bracket_card(self):
        ui = FakeToastUI()
        items = [Toast('Bạn nhận 15 xu!', 'reward', created=0.0, ttl=4.0)]
        draw_toasts(ui, 40, 24, items, unicode=False, now=0.0)
        self.assertEqual(len(ui.writes), 1)
        row, col, text, color, bold = ui.writes[0]
        self.assertEqual((row, col), (3, 0))
        self.assertIn('[', text)
        self.assertIn(']', text)
        self.assertNotIn('╭', text)
        self.assertEqual(color, 'yellow')
        self.assertTrue(bold)
        self.assertLessEqual(cells(text), 40)

    def test_toast_text_uses_ascii_icon_and_repeat_count(self):
        toast = Toast('Đã tưới 3 ô.', 'success', 0.0, 3.0, repeat=2)
        self.assertIn('+ Đã tưới 3 ô. ×2', toast_text(toast, unicode=False))
        self.assertIn('✓', toast_text(toast, unicode=True))

    def test_game_log_pushes_a_toast_and_can_suppress_routine_auto_lines(self):
        game = ExplorerGame(Farm(), Path('/tmp/toast-unused.json'),
                            color=False)
        game._log('Bạn nhận 15 xu!')
        self.assertEqual(game.toasts.visible()[0].kind, 'reward')
        game._log('Auto: đi tới (1, 2).', toast=False)
        self.assertEqual(len(game.toasts.visible()), 1)


class HudTests(unittest.TestCase):
    def test_objective_line_keeps_the_goal_and_pending_points_in_one_row(self):
        farm = Farm()
        plain = objective_line(farm, 40)
        self.assertIn('Mục tiêu', plain)
        self.assertLessEqual(cells(plain), 40)
        farm.xp = 400
        self.assertGreater(farm.attribute_points, 0)
        packed = objective_line(farm, 80)
        self.assertIn('Mục tiêu', packed)
        self.assertIn('C', packed)
        self.assertLessEqual(cells(packed), 80)

    def test_goal_complete_message_replaces_the_progress_counters(self):
        farm = Farm(harvested=30, sales=1000, fish_caught=12)
        self.assertIn('CHỦ NÔNG TRẠI', objective_line(farm, 80))


class UpgradeTests(unittest.TestCase):
    def test_options_accept_mining_and_dungeon_modes(self):
        self.assertEqual(AutoOptions(mode='mine').mode, 'mine')
        self.assertEqual(AutoOptions(mode='dungeon', days=0).days, 0)
        with self.assertRaises(ValueError):
            AutoOptions(mode='cave')

    def test_route_reaches_a_specific_rock_inside_the_mine(self):
        farm = Farm()
        target = (5, 12)
        route_to_mine = route(farm, 'mine', target, kind='rock')
        for point in route_to_mine[1]:
            dx, dy = point[0] - farm.player_x, point[1] - farm.player_y
            direction = {(0, -1): 'up', (0, 1): 'down',
                         (-1, 0): 'left', (1, 0): 'right'}[(dx, dy)]
            self.assertTrue(world.move(farm, direction))
        self.assertEqual(world.context(farm), ('mine', 'E: vào mỏ khoáng'))
        world.enter_mine(farm)
        inside = route(farm, 'mine', target, kind='rock')
        for point in inside[1]:
            dx, dy = point[0] - farm.player_x, point[1] - farm.player_y
            direction = {(0, -1): 'up', (0, 1): 'down',
                         (-1, 0): 'left', (1, 0): 'right'}[(dx, dy)]
            self.assertTrue(world.move(farm, direction))
        self.assertEqual(world.target_rock(farm), target)
        self.assertEqual(world.context(farm)[0], 'rock')

    def test_mine_auto_mines_forges_and_reports_ore(self):
        farm = Farm()
        auto = Automation(farm, AutoOptions(mode='mine', days=1),
                          rng=random.Random(4))
        for _ in range(3000):
            result = auto.step()
            if result.done:
                break
        self.assertTrue(result.done)
        self.assertGreater(farm.items.get('da', 0), 0)
        self.assertGreaterEqual(farm.gear['pickaxe'], 1)
        self.assertIn('quặng', auto.summary)
        self.assertGreaterEqual(farm.day, 2)

    def test_dungeon_auto_equips_and_clears_at_least_one_floor(self):
        farm = Farm(gear={'pickaxe': 0, 'sword': 1, 'armor': 0},
                    items={'thuoc': 3})
        auto = Automation(farm, AutoOptions(mode='dungeon', days=1),
                          rng=random.Random(2))
        for _ in range(3000):
            result = auto.step()
            if result.done:
                break
        self.assertTrue(result.done)
        self.assertGreaterEqual(farm.dungeon_best, 1)
        self.assertIsNone(auto.dungeon_run)

    def test_auto_sell_keeps_crafting_materials_but_sells_produce(self):
        farm = Farm(items={'da': 2, 'quang_dong': 1}, produce={'ca_rot': 2})
        auto = Automation(farm, AutoOptions(mode='farm', days=1),
                          rng=random.Random(1))
        self.assertTrue(auto._sellable())
        before = auto._state()
        auto._perform(_Intent('sell_keep'), before)
        self.assertEqual(farm.items.get('da'), 2)
        self.assertEqual(farm.items.get('quang_dong'), 1)
        self.assertEqual(farm.produce.get('ca_rot', 0), 0)
        self.assertGreater(farm.coins, 120)


if __name__ == '__main__':
    unittest.main()
