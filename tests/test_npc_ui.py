"""Viewport, modal readability and NPC controller contracts."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from pathlib import Path

from farmgame.model import Farm
from farmgame.explore import ExplorerGame
from farmgame import text_activities


class WideWorldUITests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm()
        self.game = ExplorerGame(self.farm, Path('/tmp/npc-ui-test.json'))

    def test_map_key_and_directory_do_not_move_player(self):
        before = (self.farm.player_x, self.farm.player_y)
        self.game._overview = Mock()
        self.game._directory = Mock()
        self.game.handle_key('M')
        self.game.handle_key('J')
        self.game._overview.assert_called_once()
        self.game._directory.assert_called_once()
        self.assertEqual((self.farm.player_x, self.farm.player_y), before)

    def test_camera_uses_double_cells_at_64_columns_and_follows_both_axes(self):
        from farmgame.explore import viewport
        left, top, cols, rows, cell = viewport(80, 36, 70, 28, 64, 10)
        self.assertEqual(cell, 2)
        self.assertLessEqual(left, 70)
        self.assertLess(70, left + cols)
        self.assertLessEqual(top, 28)
        self.assertLess(28, top + rows)
        self.assertEqual(viewport(80, 36, 70, 28, 63, 10)[-1], 1)

    def test_reader_can_scroll_to_last_word_after_resize(self):
        self.game._screen = Mock()
        self.game._screen.getmaxyx.side_effect = [(12, 32), (10, 22), (10, 22)]
        self.game._curses = SimpleNamespace(KEY_UP=259, KEY_DOWN=258, KEY_NPAGE=338,
                                          KEY_PPAGE=339, KEY_END=360, KEY_HOME=262,
                                          KEY_ENTER=343)
        rendered = []
        self.game._put = lambda y, x, text, *args: rendered.append((y, text))
        self.game._clear = Mock()
        self.game._refresh = Mock()
        self.game._read = Mock(side_effect=[360, 'q'])
        self.game._reader('Lan', ' '.join(['lời chuyện'] * 100) + ' KẾT_THÚC')
        self.assertTrue(any('KẾT_THÚC' in text for _, text in rendered))
        self.assertTrue(all(0 <= row < 12 for row, _ in rendered))

    def test_reader_preserves_every_character_of_wide_name_after_cell_clipping(self):
        from farmgame.villagers import talk
        self.farm.name = '天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏闰余成岁'
        self.farm.player_x, self.farm.player_y = 28, 6
        reply = talk(self.farm, 'lan') + ' a\u0301 e\u0302\u0301'
        self.game._screen = Mock()
        self.game._screen.getmaxyx.return_value = (10, 22)
        self.game._curses = SimpleNamespace(KEY_UP=259, KEY_DOWN=258, KEY_NPAGE=338,
                                          KEY_PPAGE=339, KEY_END=360, KEY_HOME=262,
                                          KEY_ENTER=343, A_BOLD=0, error=RuntimeError)
        rows = {}
        observed = []
        self.game._screen.erase.side_effect = rows.clear
        self.game._screen.addnstr.side_effect = lambda y, x, text, *args: rows.update({y: text})
        def read():
            if not observed:
                observed.extend(rows[y] for y in range(2, 8))
            else:
                observed.append(rows[7])
            # The reader reports the last visible line before the total.
            status = rows[8].split('/')
            end = int(status[0].split('–')[1])
            return 'q' if end == int(status[1]) else 258
        self.game._read = read
        self.game._reader('Lan', reply)
        self.assertEqual(''.join(''.join(observed).split()), ''.join(reply.split()))

    def test_text_viewport_does_not_dump_entire_world(self):
        ui = SimpleNamespace(farm=self.farm, clear_screen=False, width=60,
                             messages=[], unsaved=False, say=Mock(), wrapped=Mock())
        from farmgame.tutorial_ui import TutorialCoach
        ui.coach = TutorialCoach(ui, self.farm, lambda: None, text=True)
        with patch('farmgame.text_activities.shutil.get_terminal_size',
                   return_value=SimpleNamespace(columns=60, lines=16)):
            text_activities._draw_map(ui)
        map_lines = [c.args[0] for c in ui.say.call_args_list[1:]]
        # Includes the compact status/footer; reserve the title and input row.
        self.assertLessEqual(len(map_lines), 14)
        self.assertTrue(any('@' in row for row in map_lines))

class NPCDialogueUITests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm()
        self.farm.player_x, self.farm.player_y = 28, 6
        self.farm.facing = 'up'
        self.game = ExplorerGame(self.farm, '/tmp/npc-ui-unused.json')

    @patch('farmgame.explore.save_game')
    def test_topic_cancel_does_not_gain_friendship_or_save(self, save):
        self.game._choose = Mock(return_value=None)
        self.game.handle_key('e')
        self.assertEqual(self.farm.friendships['lan'], 0)
        save.assert_not_called()

    @patch('farmgame.explore.save_game')
    def test_each_topic_shows_complete_reply_and_autosaves(self, save):
        self.game._choose = Mock(side_effect=[0, 0, 1, None])
        self.game._reader = Mock(return_value=True)
        self.game.handle_key('e')
        self.assertEqual(save.call_count, 2)
        self.assertEqual(self.farm.friendships['lan'], 1)
        self.assertEqual(self.game._reader.call_count, 3)
        transcript = self.game._reader.call_args_list[-1].args[1]
        self.assertEqual(transcript.count('Bạn:'), 2)
        self.assertEqual(transcript.count('Lan:'), 3)
        self.assertEqual(self.farm.xp, 3)

    def test_text_cancel_and_two_player_replies(self):
        ui = SimpleNamespace(farm=self.farm, say=Mock(), wrapped=Mock(),
                             ask=Mock(return_value='0'), messages=[], persist=Mock())
        from farmgame.tutorial_ui import TutorialCoach
        ui.coach = TutorialCoach(ui, self.farm, ui.persist, text=True)
        self.assertFalse(text_activities.interact(ui))
        self.assertEqual(self.farm.friendships['lan'], 0)
        ui.ask = Mock(side_effect=['2', '1', '2'])
        self.assertTrue(text_activities.interact(ui))
        self.assertIn('Lan:', ui.messages[0])
        self.assertEqual(ui.messages[0].count('Bạn:'), 2)
        self.assertEqual(self.farm.friendships['lan'], 1)
        self.assertEqual(ui.ask.call_count, 3)

    def test_directory_contains_full_profiles_and_has_no_remote_talk(self):
        from farmgame.explore import directory_lines
        from farmgame.villagers import NPCS
        lines = directory_lines(self.farm)
        for npc, line in zip(NPCS.values(), lines):
            self.assertIn(npc.name, line)
            self.assertIn(npc.role, line)
            self.assertIn(str(npc.position[0]), line)
            self.assertIn('0/10', line)
        self.assertEqual(sum(self.farm.friendships.values()), 0)

    def test_overview_shows_all_npcs_and_player_at_ten_rows(self):
        from farmgame.explore import overview_rows
        from farmgame.villagers import NPCS
        for width, height in ((79, 19), (21, 5)):
            rendered = '\n'.join(overview_rows(self.farm, width, height))
            self.assertIn('@', rendered)
            for npc in NPCS.values():
                self.assertIn(npc.glyph, rendered)
            self.assertLessEqual(len(rendered.splitlines()), height)
            self.assertTrue(all(len(line) <= width for line in rendered.splitlines()))


class RenderingOverlayTests(unittest.TestCase):
    def test_camera_draws_npc_under_player_and_preserves_footer_at_ten_rows(self):
        from farmgame.villagers import NPCS
        farm = Farm()
        game = ExplorerGame(farm, '/tmp/ui-no-save.json')
        game._screen = Mock()
        game._screen.getmaxyx.return_value = (10, 80)
        game._clear = Mock()
        game._refresh = Mock()
        cells = {}
        game._put = lambda y, x, text, *args: cells.update({(y, x): text})
        for npc in NPCS.values():
            farm.player_x, farm.player_y = npc.position
            game._draw()
            self.assertTrue(any(text.startswith('@') for (y, x), text in cells.items() if y == 3))
            self.assertIn(str(npc.position[0]), cells[0, 0])
            self.assertIn('tân thủ', cells[9, 0])
        farm.player_x, farm.player_y = 54, 20
        game._screen.getmaxyx.return_value = (20, 80)
        cells.clear()
        game._draw()
        glyphs = [text.strip() for (y, x), text in cells.items() if 3 <= y < 14]
        self.assertIn('4', glyphs)
        self.assertTrue(any(glyph.startswith('@') for glyph in glyphs))


if __name__ == '__main__':
    unittest.main()
