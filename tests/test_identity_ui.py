"""Identity appears in the actual map and conversations."""

import unittest
from unittest.mock import Mock

from farmgame.dialogue import begin_dialogue
from farmgame.explore import ExplorerGame, overview_rows
from farmgame.identity import create_character
from farmgame.progression import character_lines


class IdentityUITests(unittest.TestCase):
    def setUp(self):
        self.farm = create_character('Linh', 'Vườn Sớm', '&', 'magenta', 'traveler')

    def test_map_uses_selected_glyph_and_outfit(self):
        game = ExplorerGame(self.farm, '/tmp/identity-unused.json')
        game._screen = Mock()
        game._screen.getmaxyx.return_value = (24, 80)
        game._clear = Mock()
        game._refresh = Mock()
        game._put = Mock()
        game._draw()
        player = [call for call in game._put.call_args_list if call.args[2].startswith('&')]
        self.assertEqual(len(player), 1)
        self.assertEqual(player[0].args[3], 'magenta')
        self.assertIn('&', '\n'.join(overview_rows(self.farm, 79, 19)))

    def test_character_sheet_and_greeting_use_player_identity(self):
        sheet = '\n'.join(character_lines(self.farm))
        self.assertIn('Linh', sheet)
        self.assertIn('Vườn Sớm', sheet)
        self.assertIn('Tím hồng', sheet)
        self.farm.player_x, self.farm.player_y = 28, 6
        conversation = begin_dialogue(self.farm, 'lan')
        self.assertIn('Linh', conversation.history[0])
        self.assertIn('Vườn Sớm', conversation.history[0])


if __name__ == '__main__':
    unittest.main()
