"""Controller contracts that do not require a real terminal."""

import unittest
from pathlib import Path
import io
import sys
from contextlib import redirect_stderr
from unittest.mock import patch, Mock
from types import SimpleNamespace

from farmgame.explore import ExplorerGame, fit_text
from farmgame.model import Farm
from farmgame.storage import SaveError
from farmgame import world


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm()
        self.game = ExplorerGame(self.farm, Path('/tmp/unused-village-test.json'))

    def test_import_does_not_load_curses(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, '-c',
                                 'import sys; import farmgame.explore; assert "curses" not in sys.modules'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clip_wide_and_combining_unicode(self):
        self.assertEqual(fit_text('a界b', 3), 'a界')
        self.assertEqual(fit_text('a\u0301b', 1), 'a\u0301')
        self.assertEqual(fit_text('a\nb', 3), 'a b')

    @patch('farmgame.explore.save_game')
    def test_s_moves_down_and_saves_without_advancing_day(self, save):
        self.assertTrue(self.game.handle_key('s'))
        self.assertEqual(self.farm.facing, 'down')
        self.assertEqual((self.farm.player_x, self.farm.player_y), (10, 8))
        self.assertEqual((self.farm.day, self.farm.energy), (1, 20))
        save.assert_called_once_with(self.farm, self.game.save_path)

    @patch('farmgame.explore.save_game')
    def test_blocked_movement_still_saves_new_facing(self, save):
        self.farm.player_x, self.farm.player_y = 1, 1
        with patch('farmgame.explore.world.move', return_value=False):
            self.assertTrue(self.game.handle_key('w'))
        save.assert_called_once()

    @patch('farmgame.explore.save_game', side_effect=SaveError('disque plein'))
    def test_failed_quit_remains_playable_and_explains_failure(self, save):
        self.assertTrue(self.game.handle_key('q'))
        self.assertIn('disque plein', self.game.messages[-1])
        self.assertIn('disque plein', self.game._save_error)

    @patch('farmgame.explore.save_game', side_effect=SaveError('không thể ghi'))
    def test_ctrl_c_failed_save_returns_one_with_visible_reason(self, save):
        stderr = io.StringIO()
        fake_curses = Mock()
        fake_curses.wrapper.side_effect = KeyboardInterrupt
        with patch.dict(sys.modules, {'curses': fake_curses}), redirect_stderr(stderr):
            result = self.game.run()
        self.assertEqual(result, 1)
        self.assertIn('không thể ghi', stderr.getvalue())

    @patch('farmgame.explore.save_game')
    def test_quit_only_exits_after_successful_save(self, save):
        self.assertFalse(self.game.handle_key('Q'))
        save.assert_called_once()

    @patch('farmgame.explore.save_game')
    def test_tv_reads_forecast_without_advancing_day(self, save):
        self.farm.area = 'home'
        self.farm.player_x, self.farm.player_y = 3, 3
        forecast = self.farm.forecast
        self.game.handle_key('e')
        self.game.handle_key('e')
        self.assertEqual(self.farm.forecast, forecast)
        self.assertEqual(self.farm.day, 1)
        self.assertEqual(self.game.messages[-1], self.farm.forecast_report())
        save.assert_not_called()

    @patch('farmgame.explore.save_game')
    def test_sleep_consumes_real_forecast(self, save):
        self.farm.area = 'home'
        self.farm.player_x, self.farm.player_y = 12, 3
        forecast = self.farm.forecast
        self.game.handle_key('e')
        self.assertEqual(self.farm.day, 2)
        self.assertEqual(self.farm.weather, forecast)
        save.assert_called_once()

    @patch('farmgame.explore.save_game')
    def test_thirsty_sleep_can_be_cancelled(self, save):
        self.farm.plant('A1', 'ca_rot')
        self.farm.area = 'home'
        self.farm.player_x, self.farm.player_y = 12, 3
        self.game._choose = Mock(return_value=0)
        self.game.handle_key('e')
        self.assertEqual(self.farm.day, 1)
        save.assert_not_called()

    @patch('farmgame.explore.save_game')
    def test_context_plant_then_water(self, save):
        self.farm.player_x, self.farm.player_y = world.FIELD_ORIGIN
        self.farm.facing = 'left'
        self.game._choose = Mock(return_value=0)
        self.game.handle_key('e')
        self.assertEqual(self.farm.plots['A1'].crop, 'ca_rot')
        self.game.handle_key('e')
        self.assertTrue(self.farm.is_watered('A1'))
        self.assertEqual(save.call_count, 2)

    def _record_modal_rows(self, height):
        rows = {}
        self.game._screen = Mock()
        self.game._screen.getmaxyx.return_value = (height, 80)
        self.game._curses = SimpleNamespace(KEY_UP=259, KEY_DOWN=258, KEY_ENTER=343)
        self.game._clear = rows.clear
        self.game._put = lambda y, x, text, *args: rows.update({y: text})
        self.game._refresh = Mock()
        self.game._read = Mock(return_value='q')
        return rows

    def test_barn_details_leave_a_visible_option_above_final_footer(self):
        for height in (10, 14):
            with self.subTest(height=height):
                rows = self._record_modal_rows(height)
                self.game._choose('CHUỒNG', ['Cho cả đàn ăn', 'Thu sản phẩm', 'Mua vật nuôi'],
                                  [f'Con {index}: đã ăn' for index in range(8)])
                option_rows = [row for row, text in rows.items() if text.startswith('> 1. ')]
                self.assertEqual(len(option_rows), 1, rows)
                self.assertLess(option_rows[0], height - 4)
                self.assertIn('chọn', rows[height - 2])

    def test_help_return_action_survives_final_composed_rows(self):
        for height in (10, 14):
            with self.subTest(height=height):
                rows = self._record_modal_rows(height)
                self.game._help()
                option_rows = [row for row, text in rows.items()
                               if text == '> 1. Trở lại làng']
                self.assertEqual(len(option_rows), 1, rows)
                self.assertLess(option_rows[0], height - 4)
                self.assertIn('chọn', rows[height - 2])

    @patch('farmgame.explore.save_game')
    def test_fishing_cancel_saves_energy_before_reading_keys(self, save):
        from farmgame.fishing import FishingRound
        fishing = FishingRound()
        events = []
        def cast(farm):
            farm.energy -= 3
            return fishing
        def read():
            events.append('read')
            self.assertEqual(self.farm.energy, 17)
            self.assertEqual(save.call_count, 1)
            return 'q'
        self.game._read = read
        with patch('farmgame.fishing.start_fishing', side_effect=cast), patch('farmgame.fishing.finish_fishing') as finish:
            self.game._fish()
        finish.assert_not_called()
        self.assertEqual(events, ['read'])
        self.assertEqual(self.farm.fish_caught, 0)

    @patch('farmgame.explore.save_game')
    def test_completed_fishing_claimed_once_and_saved(self, save):
        from farmgame.fishing import FishingRound
        fishing = FishingRound()
        fishing.done = fishing.caught = True
        with patch('farmgame.fishing.start_fishing', return_value=fishing):
            self.game._fish()
        self.assertTrue(fishing.claimed)
        self.assertEqual(self.farm.fish_caught, 1)
        self.assertEqual(save.call_count, 2)


if __name__ == '__main__':
    unittest.main()
