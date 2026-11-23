"""Complete Lan's actual lessons through the text game, not synthetic events."""

import os
import subprocess
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

from farmgame import world
from farmgame.storage import load_game, save_game
from farmgame.model import Farm
from farmgame.tutorial import TutorialState
from farmgame.villagers import npc_at

ROOT = Path(__file__).resolve().parents[1]


def route(start, destination, area='village'):
    queue = deque([(start, '')])
    seen = {start}
    while queue:
        (x, y), keys = queue.popleft()
        if (x, y) == destination:
            return keys + '\n'
        for key, dx, dy in (('w', 0, -1), ('a', -1, 0), ('s', 0, 1), ('d', 1, 0)):
            point = x + dx, y + dy
            if point not in seen and world.walkable(area, *point) and npc_at(*point, area) is None:
                seen.add(point)
                queue.append((point, keys + key))
    raise AssertionError('No playable route')


class HandsOnCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'farm.json'

    def play(self, commands, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / 'main.py'), '--text', '--save', str(self.path), *args],
            input=commands, capture_output=True, text=True, timeout=25,
            cwd=self.directory.name, env={**os.environ, 'COLUMNS': '80', 'LINES': '24'},
        )

    def test_all_fifteen_lessons_through_real_actions(self):
        commands = '2\nLinh\nVườn Tân\n1\n1\n1\n1\n1\nm\natlas\n\ndddd\n'
        commands += route((14, 7), (28, 6)) + 'e\n1\n1\n2\ni\n\n'
        commands += route((28, 6), (26, 4)) + 'e\n1\n2\n1\n'
        commands += route((26, 4), (26, 41)) + 'e\n2\ne\n'
        commands += route((26, 41), (4, 4)) + 'e\n'
        commands += route((8, 7), (3, 3), 'home') + 'e\n'
        commands += route((3, 3), (12, 3), 'home') + 'e\n'
        commands += route((12, 3), (8, 7), 'home') + 'e\n'
        commands += route((4, 4), (26, 41)) + 'e\n'
        commands += route((26, 41), (26, 4)) + 'e\n2\nc\n1\n0\nb\n0\n'
        result = self.play(commands, '--menu', '--skip-intro')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.tutorial.status, 'completed', result.stdout[-5000:])
        self.assertEqual(farm.tutorial.step, 15)
        self.assertTrue(farm.tutorial.reward_given)
        self.assertEqual(farm.day, 2)
        self.assertEqual((farm.harvested, farm.sales), (1, 12))
        self.assertEqual(farm.attributes['endurance'], 1)
        self.assertEqual(farm.xp, 46)
        self.assertEqual(farm.level, 2)
        self.assertIn('Lan', result.stdout)
        resumed = self.play('c\n0\n0\n')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(load_game(self.path).xp, 46)

    def test_pause_resume_and_failed_movement_preserve_saved_progress(self):
        farm = Farm(player_x=1, player_y=1,
                    tutorial=TutorialState(status='active', step=1))
        save_game(farm, self.path)
        result = self.play('m\nw\nt\n2\nb\n0\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        farm = load_game(self.path)
        self.assertEqual(farm.tutorial.status, 'paused')
        self.assertEqual(farm.tutorial.moves, 0)
        resumed = self.play('t\n2\n0\n')
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(load_game(self.path).tutorial.status, 'active')


if __name__ == '__main__':
    unittest.main()
