import unittest
from copy import deepcopy
from dataclasses import asdict

from farmgame import dialogue
from farmgame.model import Farm, GameError
from farmgame.villagers import NPCS, TOPICS, talk


class BranchingDialogueTests(unittest.TestCase):
    def farm_near(self, npc_id='lan', **kwargs):
        x, y = NPCS[npc_id].position
        return Farm(player_x=x, player_y=y + 1, **kwargs)

    def test_every_conversation_has_two_meaningful_choice_turns(self):
        from farmgame.dialogue import BRANCHING_NPC_IDS
        openings = set()
        for npc_id in BRANCHING_NPC_IDS:
            for topic in TOPICS:
                farm = self.farm_near(npc_id)
                conversation = dialogue.begin_dialogue(farm, npc_id, topic)
                start = dialogue.dialogue_node(conversation)
                self.assertGreaterEqual(len(start.npc_line), 20)
                self.assertGreaterEqual(len(start.choices), 2)
                openings.add(start.npc_line)
                followups = set()
                conclusions = set()
                for first in start.choices:
                    branch = deepcopy(conversation)
                    dialogue.choose_response(farm, branch, first.id)
                    followup = dialogue.dialogue_node(branch)
                    self.assertFalse(branch.done)
                    self.assertGreaterEqual(len(followup.choices), 2)
                    followups.add(followup.npc_line)
                    for second in followup.choices:
                        ending = deepcopy(branch)
                        dialogue.choose_response(farm, ending, second.id)
                        final = dialogue.dialogue_node(ending)
                        self.assertTrue(ending.done)
                        self.assertEqual(final.choices, ())
                        conclusions.add(final.npc_line)
                        self.assertEqual(len(ending.history), 5)
                        self.assertTrue(ending.history[1].startswith('Bạn: '))
                        self.assertTrue(ending.history[3].startswith('Bạn: '))
                        for index in (0, 2, 4):
                            self.assertTrue(ending.history[index].startswith(NPCS[npc_id].name + ': '))
                self.assertEqual(len(followups), len(start.choices))
                self.assertEqual(len(conclusions), 4)
        self.assertEqual(len(openings), len(BRANCHING_NPC_IDS) * len(TOPICS))

    def test_topics_have_distinct_openings_without_scene_padding(self):
        from farmgame.dialogue import BRANCHING_NPC_IDS
        for npc_id in BRANCHING_NPC_IDS:
            farm = self.farm_near(npc_id)
            openings = {dialogue.dialogue_node(
                dialogue.begin_dialogue(farm, npc_id, topic)).npc_line
                for topic in TOPICS}
            self.assertEqual(len(openings), len(TOPICS))
            for line in openings:
                self.assertFalse(line.startswith('Trời '))
                self.assertLess(len(line), 200)

    def test_script_lines_are_not_repeated_across_topics(self):
        from farmgame.dialogue_content import SCRIPTS
        lines = []
        for topics in SCRIPTS.values():
            for opening, warm, practical in topics.values():
                lines.append(opening)
                for branch in (warm, practical):
                    lines.append(branch[1])
                    lines.extend((branch[2][1], branch[3][1]))
        self.assertEqual(len(lines), len(set(lines)))

    def test_extended_story_routes_are_wired_for_every_npc(self):
        extended = ('festival', 'secret', 'future')
        self.assertEqual([TOPICS[key] for key in extended],
                         ['Lễ hội mùa', 'Điều chưa kể', 'Chuyện ngày mai'])
        self.assertEqual(len(TOPICS), 8)
        from farmgame.dialogue import BRANCHING_NPC_IDS
        for npc_id in BRANCHING_NPC_IDS:
            for topic in extended:
                farm = self.farm_near(npc_id)
                conversation = dialogue.begin_dialogue(farm, npc_id, topic)
                node = dialogue.dialogue_node(conversation)
                self.assertEqual(len(node.choices), 2)
                ending = deepcopy(conversation)
                dialogue.choose_response(farm, ending, node.choices[0].id)
                followup = dialogue.dialogue_node(ending)
                dialogue.choose_response(farm, ending, followup.choices[0].id)
                self.assertTrue(ending.done)
                self.assertEqual(len(ending.history), 5)
                summary = talk(self.farm_near(npc_id), npc_id, topic)
                self.assertTrue(summary.strip())

    def test_opening_and_cancellation_do_not_touch_farm(self):
        farm = self.farm_near()
        before = asdict(farm)
        conversation = dialogue.begin_dialogue(farm, 'lan')
        self.assertEqual(asdict(farm), before)
        self.assertFalse(conversation.credited)
        self.assertEqual(len(conversation.history), 1)

    def test_invalid_begin_is_atomic(self):
        farm = self.farm_near()
        before = asdict(farm)
        for npc_id, topic in [('missing', 'greet'), ('lan', 'missing'), ('mai', 'work'), ([], 'greet'), ('lan', [])]:
            with self.assertRaises(GameError):
                dialogue.begin_dialogue(farm, npc_id, topic)
            self.assertEqual(asdict(farm), before)

    def test_bad_choice_distance_and_finished_conversation_are_atomic(self):
        farm = self.farm_near()
        conversation = dialogue.begin_dialogue(farm, 'lan')
        for choice_id in ('missing', [], 1, None):
            before, dialogue_before = asdict(farm), deepcopy(conversation)
            with self.assertRaises(GameError):
                dialogue.choose_response(farm, conversation, choice_id)
            self.assertEqual(asdict(farm), before)
            self.assertEqual(conversation, dialogue_before)
        for area, x, y in [('home', 28, 6), ('village', 4, 4)]:
            farm.area, farm.player_x, farm.player_y = area, x, y
            before, dialogue_before = asdict(farm), deepcopy(conversation)
            with self.assertRaises(GameError):
                dialogue.choose_response(farm, conversation, 'warm')
            self.assertEqual(asdict(farm), before)
            self.assertEqual(conversation, dialogue_before)
        farm.area, farm.player_x, farm.player_y = 'village', 28, 6
        dialogue.choose_response(farm, conversation, 'warm')
        dialogue.choose_response(farm, conversation, 'try')
        before, dialogue_before = asdict(farm), deepcopy(conversation)
        with self.assertRaises(GameError):
            dialogue.choose_response(farm, conversation, 'try')
        self.assertEqual(asdict(farm), before)
        self.assertEqual(conversation, dialogue_before)

    def test_reward_once_across_turns_topics_restart_and_next_day(self):
        farm = self.farm_near()
        conversation = dialogue.begin_dialogue(farm, 'lan')
        output = dialogue.choose_response(farm, conversation, 'warm')
        self.assertIn(conversation.history[-2], output)
        self.assertIn(conversation.history[-1], output)
        self.assertTrue(conversation.credited)
        self.assertEqual((farm.xp, farm.friendships['lan'], farm.talked_on['lan']), (3, 1, 1))
        dialogue.choose_response(farm, conversation, 'try')
        # A game restart uses the typed save decoder, including daily quests.
        import tempfile
        from pathlib import Path
        from farmgame.storage import load_game, save_game
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'farm.json'
            save_game(farm, path)
            restarted = load_game(path)
        # Daily eligibility survives the discarded conversation and real save load.
        for topic in TOPICS:
            again = dialogue.begin_dialogue(restarted, 'lan', topic)
            dialogue.choose_response(restarted, again, 'practical')
        self.assertEqual((restarted.xp, restarted.friendships['lan']), (3, 1))
        restarted.day += 1
        again = dialogue.begin_dialogue(restarted, 'lan')
        dialogue.choose_response(restarted, again, 'warm')
        self.assertEqual((restarted.xp, restarted.friendships['lan']), (6, 2))

    def test_legacy_talk_suppresses_reward_and_cap_still_awards_daily_xp(self):
        farm = self.farm_near()
        talk(farm, 'lan')
        conversation = dialogue.begin_dialogue(farm, 'lan')
        dialogue.choose_response(farm, conversation, 'warm')
        self.assertEqual((farm.xp, farm.friendships['lan']), (0, 1))
        farm.day += 1
        farm.friendships['lan'] = 10
        conversation = dialogue.begin_dialogue(farm, 'lan')
        dialogue.choose_response(farm, conversation, 'warm')
        self.assertEqual((farm.xp, farm.friendships['lan']), (3, 10))

    def test_greetings_vary_by_day_weather_and_friendship_and_freeze_in_session(self):
        from farmgame.dialogue import BRANCHING_NPC_IDS
        for npc_id in BRANCHING_NPC_IDS:
            farm = self.farm_near(npc_id)
            original = dialogue.begin_dialogue(farm, npc_id)
            original_line = dialogue.dialogue_node(original).npc_line
            farm.day = 2
            next_day = dialogue.dialogue_node(dialogue.begin_dialogue(farm, npc_id)).npc_line
            farm.weather = 'rainy'
            rain = dialogue.dialogue_node(dialogue.begin_dialogue(farm, npc_id)).npc_line
            farm.friendships[npc_id] = 6
            close = dialogue.dialogue_node(dialogue.begin_dialogue(farm, npc_id)).npc_line
            self.assertEqual(len({original_line, next_day, rain, close}), 4)
            self.assertIn('mưa', rain.lower())
            self.assertEqual(dialogue.dialogue_node(original).npc_line, original_line)


if __name__ == '__main__':
    unittest.main()
