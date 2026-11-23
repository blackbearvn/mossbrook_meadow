"""Visible character upgrades and two-sided conversation controllers."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from farmgame.explore import ExplorerGame
from farmgame.model import Farm
from farmgame import text_activities


class CharacterAndDialogueUITests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm(xp=80, player_x=28, player_y=6, facing='up')
        self.game = ExplorerGame(self.farm, Path('/tmp/character-ui-unused.json'))

    @patch('farmgame.explore.save_game')
    def test_character_sheet_upgrades_attribute_and_skill_then_saves(self, save):
        self.game._screen = Mock()
        self.game._screen.getmaxyx.return_value = (24, 80)
        self.game._curses = SimpleNamespace(
            KEY_UP=259, KEY_DOWN=258, KEY_LEFT=260, KEY_RIGHT=261,
            KEY_ENTER=343, KEY_PPAGE=339, KEY_NPAGE=338,
            KEY_F5=269, error=RuntimeError)
        self.game._clear = Mock()
        self.game._put = Mock()
        self.game._refresh = Mock()
        self.game._read = Mock(side_effect=['\n', 's', 's', 's', '\n', 'q'])
        self.game.handle_key('c')
        self.assertEqual(self.farm.attributes['endurance'], 1)
        self.assertEqual(self.farm.skills['farming'], 1)
        self.assertEqual(self.farm.energy_limit, 24)
        self.assertEqual(self.farm.attribute_points, 1)
        self.assertEqual(self.farm.skill_points, 3)
        self.assertEqual(save.call_count, 2)

    @patch('farmgame.explore.save_game')
    def test_conversation_records_both_player_replies_and_npc_reactions(self, save):
        self.game._choose = Mock(side_effect=[0, 0, 1, None])
        self.game._reader = Mock(return_value=True)
        self.game.handle_key('e')
        final_transcript = self.game._reader.call_args_list[-1].args[1]
        self.assertEqual(final_transcript.count('Bạn:'), 2)
        self.assertGreaterEqual(final_transcript.count('Lan:'), 3)
        self.assertEqual(self.farm.friendships['lan'], 1)
        self.assertEqual(self.farm.xp, 83)
        self.assertEqual(save.call_count, 2)

    @patch('farmgame.explore.save_game')
    def test_cancelling_before_first_reply_never_awards_xp(self, save):
        self.game._choose = Mock(side_effect=[0, None])
        self.game._reader = Mock(return_value=False)
        self.game.handle_key('e')
        self.assertEqual(self.farm.xp, 80)
        self.assertEqual(self.farm.friendships['lan'], 0)
        save.assert_not_called()

    @patch('farmgame.explore.save_game')
    def test_full_answer_text_can_be_read_before_selecting(self, save):
        self.game._choose = Mock(side_effect=[0, None])
        self.game._reader = Mock(return_value=True)
        self.game.handle_key('e')
        readable = self.game._reader.call_args_list[0].args[1]
        self.assertIn('Một giỏ đầy màu sắc, nhìn là muốn trồng ngay.', readable)
        self.assertIn('Mình thích bảng ghi rõ giống và thời gian lớn.', readable)
        self.assertEqual(self.farm.friendships['lan'], 0)
        save.assert_not_called()

    def test_text_character_menu_changes_real_budget(self):
        ui = Mock(farm=self.farm)
        ui.ask.side_effect = ['1', '4', '0']
        text_activities.character_menu(ui)
        self.assertEqual(self.farm.attributes['endurance'], 1)
        self.assertEqual(self.farm.skills['farming'], 1)
        self.assertEqual(self.farm.attribute_points, 1)


if __name__ == '__main__':
    unittest.main()
