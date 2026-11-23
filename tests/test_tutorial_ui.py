"""Hands-on coaching preserves player control and persists actual progress."""
from copy import deepcopy
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from farmgame.model import Farm
from farmgame.explore import ExplorerGame
from farmgame.terminal import TerminalGame
from farmgame.tutorial import start_tutorial
from farmgame.tutorial_ui import TutorialCoach
from farmgame import world


class Screen:
    def __init__(self, height=12, width=48):
        self.height, self.width = height, width
        self.rows = [' ' * width for _ in range(height)]

    def getmaxyx(self):
        return self.height, self.width

    def addnstr(self, row, col, text, count, attributes):
        line = self.rows[row]
        text = text[:count]
        self.rows[row] = line[:col] + text + line[col + len(text):]


class TutorialCoachTests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm()
        self.ui = ExplorerGame(self.farm, Path('/tmp/tutorial-ui-unused.json'))
        self.saved = []
        self.coach = TutorialCoach(self.ui, self.farm,
                                   lambda: self.saved.append(deepcopy(self.farm)))

    def test_offer_leaves_existing_save_untouched(self):
        before = deepcopy(self.farm)
        self.coach.offer()
        self.assertEqual(self.farm, before)
        self.assertEqual(self.saved, [])

    def test_cancel_offer_skips_without_reward_and_never_offers_again(self):
        self.farm.tutorial.status = 'pending'
        self.ui._choose = Mock(return_value=None)
        self.coach.offer()
        self.assertEqual(self.farm.tutorial.status, 'skipped')
        self.assertEqual(self.farm.xp, 0)
        self.assertFalse(self.farm.tutorial.reward_given)
        self.assertEqual(self.saved[-1].tutorial.status, 'skipped')
        self.ui._choose = Mock(side_effect=AssertionError('Repeated offer'))
        self.coach.offer()

    def test_events_persist_progress_even_before_step_completes(self):
        start_tutorial(self.farm)
        self.coach.event('bag')
        self.assertEqual(self.saved, [])
        self.coach.event('map')
        self.assertEqual(self.saved[-1].tutorial.step, 1)
        old = self.farm.player_x, self.farm.player_y
        self.assertTrue(world.move(self.farm, 'right'))
        self.coach.event('move', from_x=old[0], from_y=old[1])
        self.assertEqual(self.saved[-1].tutorial.moves, 1)
        self.assertEqual(len(self.saved), 2)

    def test_panel_details_are_readable_without_granting_character_reward(self):
        start_tutorial(self.farm)
        self.farm.tutorial.step = 13
        self.ui._choose = Mock(side_effect=[0, None])
        readable = []
        self.ui._reader = lambda title, body: readable.append((title, body))
        self.coach.panel()
        self.assertGreater(len(readable[0][1]), 100)
        self.assertIn('C', readable[0][1])
        self.assertEqual(self.farm.xp, 0)
        self.assertFalse(self.farm.tutorial.reward_given)
        self.assertEqual(self.saved, [])

    def test_pause_hides_route_but_keeps_tracking_and_resume_restores_it(self):
        start_tutorial(self.farm)
        self.farm.tutorial.step = 2
        route = self.coach.path_points()
        self.assertTrue(route)
        self.ui._choose = Mock(return_value=1)
        self.coach.panel()
        self.assertEqual(self.farm.tutorial.status, 'paused')
        self.assertEqual(self.coach.path_points(), set())
        self.coach.event('talk', npc_id='lan', done=True)
        self.assertEqual(self.saved[-1].tutorial.step, 3)
        self.coach.panel()
        self.assertEqual(self.farm.tutorial.status, 'active')

    def test_small_curses_overlay_preserves_controls_and_save_error(self):
        start_tutorial(self.farm)
        screen = Screen(height=10, width=35)
        self.ui._screen = screen
        self.ui._curses = SimpleNamespace(A_BOLD=1, error=RuntimeError)
        self.ui._put(9, 0, 'E dung / Q thoat')
        self.ui._put(8, 0, 'LOI LUU: disk full')
        self.coach.draw_curses()
        self.assertIn('1/15', screen.rows[2])
        self.assertIn('T', screen.rows[7])
        self.assertIn('E dung / Q thoat', screen.rows[9])
        self.assertIn('LOI LUU: disk full', screen.rows[8])

    def test_tiny_window_keeps_compact_controls_visible(self):
        start_tutorial(self.farm)
        screen = Screen(height=8, width=20)
        self.ui._screen = screen
        self.ui._curses = SimpleNamespace(A_BOLD=1, error=RuntimeError)
        self.ui._put(4, 0, 'Q luu / I tui')
        self.coach.draw_curses()
        self.assertIn('Q luu / I tui', screen.rows[4])

    def test_sync_saves_arrival_and_event_saves_real_character_reward(self):
        start_tutorial(self.farm)
        self.farm.tutorial.step = 5
        self.farm.player_x, self.farm.player_y = 26, 42
        self.farm.facing = 'left'
        self.coach.sync()
        self.assertEqual(self.saved[-1].tutorial.step, 6)
        self.farm.tutorial.step = 13
        xp = self.farm.xp
        self.coach.event('character')
        self.assertEqual(self.saved[-1].xp, xp + 40)
        self.assertTrue(self.saved[-1].tutorial.reward_given)
        self.coach.event('character')
        self.assertEqual(self.farm.xp, xp + 40)
        self.assertEqual(len(self.saved), 2)

    def test_text_offer_reprompts_invalid_input_then_starts(self):
        self.farm.tutorial.status = 'pending'
        ui = TerminalGame(self.farm, Path('/tmp/tutorial-unused.json'), color=False)
        ui.ask = Mock(side_effect=['garbage', '1'])
        coach = TutorialCoach(ui, self.farm, lambda: self.saved.append(deepcopy(self.farm)), text=True)
        with redirect_stdout(StringIO()) as output:
            coach.offer()
            coach.draw_text()
        self.assertEqual(self.farm.tutorial.status, 'active')
        self.assertEqual(self.saved[-1].tutorial.step, 0)
        self.assertIn('1/15', output.getvalue())
        self.assertIn('M', output.getvalue())

    def test_text_map_key_finishes_the_exact_instruction_it_shows(self):
        from farmgame.text_activities import map_mode
        start_tutorial(self.farm)
        ui = TerminalGame(self.farm, Path('/tmp/tutorial-unused.json'), color=False)
        ui.ask = Mock(return_value='b')
        ui.persist = Mock(return_value=True)
        ui.coach.save_callback = ui.persist
        with redirect_stdout(StringIO()):
            map_mode(ui)
        self.assertEqual(self.farm.tutorial.step, 1)

    def test_text_viewport_draws_real_route_points(self):
        from farmgame.text_activities import _draw_map
        start_tutorial(self.farm)
        self.farm.tutorial.step = 2
        ui = TerminalGame(self.farm, Path('/tmp/tutorial-unused.json'), color=False)
        with redirect_stdout(StringIO()) as output:
            _draw_map(ui)
        self.assertIn('· ', output.getvalue())
        self.assertTrue(ui.coach.path_points())

    def test_text_map_accepts_m_after_starting_guide_in_map(self):
        from farmgame.text_activities import map_mode
        ui = TerminalGame(self.farm, Path('/tmp/tutorial-unused.json'), color=False)
        ui.ask = Mock(side_effect=['t', '1', 'm', '', 'b'])
        ui.persist = Mock(return_value=True)
        ui.coach.save_callback = ui.persist
        with redirect_stdout(StringIO()):
            map_mode(ui)
        self.assertEqual(self.farm.tutorial.status, 'active')
        self.assertEqual(self.farm.tutorial.step, 1)
        ui.persist.assert_called()


if __name__ == '__main__':
    unittest.main()
