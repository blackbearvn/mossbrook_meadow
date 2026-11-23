import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from farmgame.model import Farm
from farmgame.storage import load_game, save_game


ROOT = Path(__file__).resolve().parents[1]


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "farm.json"

    def play(self, commands, *arguments):
        return subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--save", str(self.path),
             *arguments],
            input=commands, text=True, capture_output=True, timeout=10,
            cwd=self.temp.name,
            env={**os.environ, "COLUMNS": "80", "LINES": "24"},
        )

    def test_full_crop_cycle_through_numbered_menu(self):
        result = self.play(
            "1\n1\nA1 A2\n2\nall\n7\n2\nall\n7\n3\nall\n5\n0\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.day, 3)
        self.assertEqual(farm.harvested, 2)
        self.assertEqual(farm.sales, 48)
        self.assertEqual(farm.coins, 168)
        self.assertEqual(farm.seeds["ca_rot"], 4)
        self.assertNotIn("\x1b[", result.stdout)
        self.assertIn("NÔNG TRẠI", result.stdout)

    def test_resume_uses_previous_progress(self):
        save_game(Farm(day=7, coins=333), self.path)
        result = self.play("8\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.day, 7)
        self.assertEqual(farm.coins, 339)

    def test_invalid_batch_coordinates_do_not_partially_plant(self):
        result = self.play("nonsense\n1\n1\nA1 Z9\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.seeds["ca_rot"], 6)
        self.assertEqual(farm.energy, 20)
        self.assertIsNone(farm.plots["A1"].crop)

    def test_invalid_purchase_does_not_change_money_or_seeds(self):
        result = self.play("4\n1\n-5\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.coins, 120)
        self.assertEqual(farm.seeds["ca_rot"], 6)

    def test_bulk_actions_stop_at_available_seeds_and_energy(self):
        result = self.play("1\n1\nall\n2\nall\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        planted = [plot for plot in farm.plots.values() if plot.crop]
        self.assertEqual(len(planted), 6)
        self.assertEqual(sum(plot.watered for plot in planted), 6)
        self.assertEqual(farm.energy, 2)

    def test_eof_during_submenu_saves_completed_actions(self):
        result = self.play("8\n1\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(load_game(self.path).coins, 126)
        self.assertNotIn("Traceback", result.stderr)

    def test_new_game_backs_up_original_save(self):
        save_game(Farm(day=12, coins=456), self.path)
        result = self.play("0\n", "--new", "--name", "Vườn mới")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(load_game(self.path).day, 1)
        self.assertEqual(load_game(self.path).name, "Vườn mới")
        backups = list(self.path.parent.glob("farm.json.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(load_game(backups[0]).coins, 456)

    def test_corrupt_save_is_not_overwritten(self):
        self.path.write_text("broken save", encoding="utf-8")
        result = self.play("0\n")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken save")
        self.assertNotIn("Traceback", result.stderr)

    def test_failed_save_exits_with_failure_and_explanation_on_eof(self):
        blocker = Path(self.temp.name) / "not-a-directory"
        blocker.write_text("keep this file", encoding="utf-8")
        result = self.play("s\n8\n0\n", "--save", str(blocker / "farm.json"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Không thể lưu", result.stdout)
        self.assertFalse("Đã lưu tiến trình." in result.stdout,
                         "Không được báo lưu thành công khi ghi file thất bại")
        self.assertEqual(blocker.read_text(encoding="utf-8"), "keep this file")
        self.assertNotIn("Traceback", result.stderr)

    def test_help_is_available_without_starting_or_saving_game(self):
        result = self.play("", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--save", result.stdout)
        self.assertFalse(self.path.exists())

    def test_text_map_house_tv_and_chest_are_connected(self):
        result = self.play(
            'm\nwwwaaaaaa\ne\naaaawwwwa\ne\ns\ne\n1\n1\n2\nb\n0\n',
            '--text',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.area, 'home')
        self.assertEqual(farm.chest['seed:ca_rot'], 2)
        self.assertEqual(farm.seeds['ca_rot'], 4)
        self.assertEqual(farm.day, 1)
        self.assertIn('Dự báo ngày 2', result.stdout)

    def test_text_map_barn_buys_and_feeds_animal(self):
        result = self.play('m\nddddd\ne\n4\n1\ne\n1\nb\n0\n', '--text')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(len(farm.animals), 1)
        self.assertTrue(farm.animals[0].fed)
        self.assertEqual(farm.items['feed'], 7)
        self.assertEqual(farm.coins, 40)

    def test_text_fishing_cancel_spends_cast_energy_but_grants_nothing(self):
        result = self.play('m\ndddddddddddss\ne\nq\nb\n0\n', '--text')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual((farm.player_x, farm.player_y), (21, 9))
        self.assertEqual(farm.energy, 17)
        self.assertEqual(farm.fish_caught, 0)

    @unittest.skipUnless(os.name == 'posix', 'PTY requires Unix')
    def test_unknown_terminal_falls_back_to_text_and_saves(self):
        import pty
        import select
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [sys.executable, str(ROOT / 'main.py'), '--save', str(self.path), '--quick'],
            stdin=slave, stdout=slave, stderr=slave,
            env={**os.environ, 'TERM': 'may-nho-unsupported-terminal'},
        )
        os.close(slave)
        try:
            os.write(master, b'0\n')
            process.wait(timeout=5)
            output = bytearray()
            while select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
            self.assertEqual(process.returncode, 0, output.decode(errors='replace'))
            self.assertEqual(load_game(self.path).day, 1)
            self.assertIn('NÔNG TRẠI', output.decode())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(master)

    def test_text_chat_keeps_daily_friendship_across_resume(self):
        save_game(Farm(player_x=28, player_y=6, facing='up'), self.path)
        result = self.play('m\ne\n1\n1\n2\natlas\n\nj\n\nb\n0\n', '--text')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.friendships['lan'], 1)
        self.assertEqual(farm.talked_on['lan'], 1)
        self.assertEqual((farm.day, farm.energy), (1, 20))
        self.assertIn('Lan:', result.stdout)
        self.assertIn('BẢN ĐỒ TOÀN LÀNG', result.stdout)
        self.assertIn('Mai', result.stdout)
        self.assertIn('Sơn', result.stdout)
        resumed = self.play('m\ne\n2\n2\n1\nb\n0\n', '--text')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(load_game(self.path).friendships['lan'], 1)

    def test_text_can_walk_to_new_meadow_and_talk(self):
        # Day-one route uses original east gate then a straight path to the meadow.
        result = self.play('m\n' + 'd' * 29 + 'ss\ne\n3\n1\n2\nb\n0\n', '--text')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual((farm.player_x, farm.player_y), (39, 9))
        self.assertEqual(farm.friendships['an'], 1)
        self.assertEqual(farm.day, 1)
        self.assertIn('Đồng Hoa', result.stdout)

    def test_dialogue_level_up_points_and_sale_bonus_through_text_ui(self):
        farm = Farm(xp=39, player_x=28, player_y=6, facing='up')
        farm.produce['ca_rot'] = 2
        save_game(farm, self.path)
        result = self.play('m\ne\n1\n1\n2\nc\n1\n4\n0\nb\n5\n0\n', '--text')
        self.assertEqual(result.returncode, 0, result.stderr)
        restored = load_game(self.path)
        self.assertEqual(restored.level, 2)
        self.assertEqual(restored.xp, 42)
        self.assertEqual(restored.attributes['endurance'], 1)
        self.assertEqual(restored.skills['farming'], 1)
        self.assertEqual((restored.attribute_points, restored.skill_points), (0, 1))
        self.assertEqual(restored.energy_limit, 24)
        self.assertEqual((restored.coins, restored.sales), (172, 52))
        self.assertIn('Bạn:', result.stdout)
        self.assertIn('Lan:', result.stdout)

    def test_existing_crop_can_be_watered_on_distant_field(self):
        farm = Farm(player_x=26, player_y=42, facing='left')
        farm.plant('A1', 'lua_mi')
        save_game(farm, self.path)
        result = self.play('m\ne\nb\n0\n', '--text')
        self.assertEqual(result.returncode, 0, result.stderr)
        restored = load_game(self.path)
        self.assertTrue(restored.plots['A1'].watered)
        self.assertEqual(restored.energy, 17)
        self.assertIn('Cánh đồng', result.stdout)


if __name__ == "__main__":
    unittest.main()
