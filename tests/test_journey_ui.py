"""Real terminal entry points expose countryside and community actions."""
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from farmgame import journey, journey_ui
from farmgame.explore import ExplorerGame
from farmgame.model import Farm
from farmgame.storage import load_game
from farmgame.terminal import TerminalGame
from farmgame.text_activities import interact


class JourneyUITests(unittest.TestCase):
    def test_explorer_u_routes_to_journal_and_cancelling_is_pure(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = ExplorerGame(Farm(), Path(tmp)/'farm.json')
            before = asdict(game.farm)
            with patch.object(game, '_choose', return_value=None) as choose:
                self.assertTrue(game.handle_key('u'))
                self.assertTrue(choose.called)
                self.assertIn('HÀNH TRÌNH', choose.call_args.args[0])
            self.assertEqual(asdict(game.farm), before)

    def test_explorer_site_gather_uses_world_context_and_saves_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'farm.json'
            farm = Farm()
            journey.travel_to_site(farm, 'east_wood')
            game = ExplorerGame(farm, path)
            with patch.object(game, '_choose', return_value=0):
                game._interact()
            self.assertEqual(farm.gathered_on['east_wood'], farm.day)
            self.assertEqual(load_game(path).gathered_on, farm.gathered_on)

    def test_text_site_can_read_then_gather(self):
        with tempfile.TemporaryDirectory() as tmp:
            farm = Farm()
            journey.travel_to_site(farm, 'meadow')
            ui = TerminalGame(farm, Path(tmp)/'farm.json', color=False)
            with patch.object(ui, 'ask', return_value='1'), redirect_stdout(StringIO()) as output:
                self.assertTrue(interact(ui))
            self.assertIn(journey.SITES['meadow'].story, ' '.join(output.getvalue().split()))
            self.assertEqual(farm.gathered_on['meadow'], 1)

    def test_cancelling_project_confirmation_does_not_spend_goods(self):
        with tempfile.TemporaryDirectory() as tmp:
            farm = Farm()
            journey.travel_to_site(farm, 'field')
            game = ExplorerGame(farm, Path(tmp)/'farm.json')
            before = asdict(farm)
            # Site action 1: restore; confirmation 0: keep materials.
            with patch.object(game, '_choose', side_effect=[1, 0]):
                game._interact()
            self.assertEqual(asdict(farm), before)

    def test_text_journal_can_travel_to_the_last_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            farm = Farm()
            ui = TerminalGame(farm, Path(tmp)/'farm.json', color=False)
            with patch.object(ui, 'ask', side_effect=['2', '31']), redirect_stdout(StringIO()):
                self.assertTrue(journey_ui.text_journal(ui))
            self.assertEqual((farm.player_x, farm.player_y), journey.SITES['south_3_3'].position)

    def test_site_has_a_scrollable_full_story_for_small_terminals(self):
        with tempfile.TemporaryDirectory() as tmp:
            farm = Farm()
            journey.travel_to_site(farm, 'east_wood')
            game = ExplorerGame(farm, Path(tmp)/'farm.json')
            with patch.object(game, '_choose', return_value=2), \
                    patch.object(game, '_reader') as reader:
                game._interact()
            reader.assert_called_once()
            self.assertIn(journey.SITES['east_wood'].story, reader.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
