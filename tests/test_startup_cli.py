"""Start-menu flows through the real command-line entry point."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from farmgame.model import Farm
from farmgame.storage import load_game, save_game

ROOT = Path(__file__).resolve().parents[1]


class StartupCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'farm.json'

    def launch(self, commands, *extra):
        return subprocess.run(
            [sys.executable, str(ROOT / 'main.py'), '--save', str(self.path),
             '--menu', '--text', *extra], input=commands, text=True,
            capture_output=True, timeout=10, cwd=self.directory.name,
        )

    def test_quit_or_eof_on_title_does_not_create_game(self):
        for command in ('0\n', ''):
            result = self.launch(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('MOSSBROOK MEADOW', result.stdout)
            self.assertFalse(self.path.exists())

    def test_new_character_keeps_custom_identity_and_enters_game(self):
        result = self.launch('2\nLinh\nVườn Sớm\n2\n4\n3\n1\n0\n', '--skip-intro')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.player_name, 'Linh')
        self.assertEqual(farm.name, 'Vườn Sớm')
        self.assertEqual((farm.avatar, farm.outfit, farm.background), ('&', 'magenta', 'traveler'))
        self.assertTrue(farm.intro_seen)
        self.assertEqual((farm.day, farm.xp, farm.coins), (1, 0, 120))

    def test_cancel_creation_keeps_existing_save_and_has_no_backup(self):
        save_game(Farm(day=14, coins=813), self.path)
        before = self.path.read_bytes()
        result = self.launch('2\nTên mới\n0\n0\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('farm.json.bak-*')), [])

    def test_continue_loads_previous_progress(self):
        save_game(Farm(day=11, coins=456, xp=120), self.path)
        result = self.launch('1\n0\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual((farm.day, farm.coins, farm.xp), (11, 456, 120))

    def test_confirm_new_game_keeps_a_backup_of_old_character(self):
        save_game(Farm(day=8, coins=765), self.path)
        result = self.launch('2\nMinh\nVườn mới\n1\n1\n1\n1\n0\n', '--skip-intro')
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list(self.path.parent.glob('farm.json.bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((load_game(backups[0]).day, load_game(backups[0]).coins), (8, 765))
        self.assertEqual(load_game(self.path).player_name, 'Minh')

    def test_q_returns_to_title_and_exit_asks_for_confirmation(self):
        from farmgame.tutorial import TutorialState
        save_game(Farm(tutorial=TutorialState(status='skipped')), self.path)
        result = self.launch('1\n0\n0\n1\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(
            result.stdout.count('MOSSBROOK MEADOW · Một cuộc sống chậm giữa mây trời'), 2)
        self.assertIn('THOÁT GAME?', result.stdout)
        self.assertIn('Trở về menu chính.', result.stdout)

    def test_credits_do_not_change_existing_save(self):
        save_game(Farm(day=7, coins=432), self.path)
        before = self.path.read_bytes()
        result = self.launch('3\nq\n0\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIn('CREDIT', result.stdout)

    def test_corrupt_save_can_be_replaced_after_confirmation_and_is_backed_up(self):
        self.path.write_text('broken old save', encoding='utf-8')
        result = self.launch('2\nLinh\nVườn mới\n1\n1\n1\n1\n0\n', '--skip-intro')
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list(self.path.parent.glob('farm.json.bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'broken old save')
        self.assertEqual(load_game(self.path).player_name, 'Linh')

    def test_conflicting_menu_options_fail_without_writing(self):
        result = self.launch('', '--quick')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.path.exists())

    def test_new_character_sees_intro_then_resumes_without_repeating_it(self):
        result = self.launch('2\nLinh\nVườn Sớm\n1\n2\n2\n1\n\n\n\n0\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Lá thư', result.stdout)
        self.assertIn('Chuyến xe', result.stdout)
        self.assertIn('Lan đón bạn', result.stdout)
        self.assertTrue(load_game(self.path).intro_seen)
        resumed = self.launch('1\n0\n')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertNotIn('Lá thư trong nắng', resumed.stdout)

    def test_forced_new_can_be_cancelled_before_save_changes(self):
        save_game(Farm(day=9, coins=555), self.path)
        before = self.path.read_bytes()
        result = self.launch('0\n0\n', '--new')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('farm.json.bak-*')), [])


if __name__ == '__main__':
    unittest.main()
