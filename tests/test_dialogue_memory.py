"""Remember completed choices while keeping visits and rewards predictable."""

from copy import deepcopy
from dataclasses import asdict
import unittest

from farmgame import dialogue
from farmgame.model import Farm, GameError
from farmgame.villagers import NPCS, TOPICS


class DialogueMemoryTests(unittest.TestCase):
    def near(self, npc_id='lan', **kwargs):
        x, y = NPCS[npc_id].position
        return Farm(player_x=x, player_y=y + 1, **kwargs)

    def finish(self, farm, npc_id, topic, first='warm', second='try'):
        current = dialogue.begin_dialogue(farm, npc_id, topic)
        dialogue.choose_response(farm, current, first)
        dialogue.choose_response(farm, current, second)
        return current

    def line(self, farm, npc_id, topic='greet'):
        if npc_id in dialogue.LIGHT_NPC_IDS:
            return dialogue.opening_line(farm, npc_id, topic)
        return dialogue.dialogue_node(
            dialogue.begin_dialogue(farm, npc_id, topic)).npc_line

    def test_completed_choice_changes_next_day_reply_about_that_topic(self):
        farm = self.near()
        self.finish(farm, 'lan', 'greet', 'practical', 'try')
        self.assertEqual(getattr(farm, 'dialogue_memory', {}),
                         {'lan:greet': 'practical_try'})
        farm.day = 2
        remembered = self.line(farm, 'lan')
        without_memory = deepcopy(farm)
        without_memory.dialogue_memory.clear()
        self.assertNotEqual(remembered, self.line(without_memory, 'lan'))
        self.assertIn('giá', remembered.lower())
        # Other topics still tell their own story.
        self.assertEqual(self.line(farm, 'lan', 'secret'),
                         self.line(without_memory, 'lan', 'secret'))

    def test_all_four_routes_are_remembered_for_every_topic(self):
        for npc_id in dialogue.BRANCHING_NPC_IDS:
            for topic in TOPICS:
                callbacks = set()
                for first, second in (('warm', 'try'), ('warm', 'ask'),
                                      ('practical', 'try'), ('practical', 'ask')):
                    with self.subTest(npc=npc_id, topic=topic, route=(first, second)):
                        farm = self.near(npc_id)
                        current = self.finish(farm, npc_id, topic, first, second)
                        self.assertEqual(getattr(farm, 'dialogue_memory', {}).get(
                            f'{npc_id}:{topic}'), f'{first}_{second}')
                        self.assertEqual(len(current.history), 5)
                        farm.day = 2
                        callbacks.add(self.line(farm, npc_id, topic))
                self.assertEqual(len(callbacks), 4, (npc_id, topic))

    def test_cancelled_and_invalid_choices_do_not_replace_completed_memory(self):
        farm = self.near()
        self.finish(farm, 'lan', 'work', 'warm', 'ask')
        saved = deepcopy(getattr(farm, 'dialogue_memory', {}))
        before = asdict(farm)
        abandoned = dialogue.begin_dialogue(farm, 'lan', 'work')
        self.assertEqual(asdict(farm), before)
        dialogue.choose_response(farm, abandoned, 'practical')
        self.assertEqual(getattr(farm, 'dialogue_memory', {}), saved)
        for choice_id in ('invalid', [], None):
            before, snapshot = asdict(farm), deepcopy(abandoned)
            with self.assertRaises(GameError):
                dialogue.choose_response(farm, abandoned, choice_id)
            self.assertEqual(asdict(farm), before)
            self.assertEqual(abandoned, snapshot)
        self.assertEqual(saved, {'lan:work': 'warm_ask'})

    def test_repeating_and_replacing_memories_never_repeats_daily_rewards(self):
        farm = self.near()
        self.finish(farm, 'lan', 'future')
        for topic in TOPICS:
            self.finish(farm, 'lan', topic, 'practical', 'ask')
        self.assertEqual((farm.xp, farm.friendships['lan']), (3, 1))
        self.assertEqual(getattr(farm, 'dialogue_memory', {}).get('lan:future'),
                         'practical_ask')
        farm.day += 1
        self.finish(farm, 'lan', 'future', 'warm', 'ask')
        self.assertEqual((farm.xp, farm.friendships['lan']), (6, 2))

    def test_light_chats_react_to_rain_and_keep_daily_rewards(self):
        for npc_id in dialogue.LIGHT_NPC_IDS:
            with self.subTest(npc=npc_id):
                farm = self.near(npc_id, day=2)
                plain = self.line(farm, npc_id)
                farm.weather = 'rainy'
                rainy = self.line(farm, npc_id)
                self.assertNotEqual(plain, rainy)
                self.assertIn('mưa', rainy.lower())
                for _ in range(3):
                    current = dialogue.begin_light_chat(farm, npc_id)
                    self.assertTrue(current.done)
                    self.assertNotIn('?', dialogue.dialogue_node(current).npc_line)
                self.assertEqual((farm.xp, farm.friendships[npc_id]), (3, 1))

    def test_gifts_help_and_letters_have_personal_replies_for_all_eight(self):
        from farmgame.bonds import deliver_request, give_gift, help_favour
        for action in ('gift', 'help', 'letter', 'pending_letter'):
            replies = set()
            for npc_id in NPCS:
                with self.subTest(action=action, npc=npc_id):
                    farm = self.near(npc_id, day=2)
                    plain = self.line(farm, npc_id, 'work')
                    if action == 'gift':
                        farm.items['banh_mi'] = 1
                        give_gift(farm, npc_id, 'banh_mi')
                    elif action == 'help':
                        farm.items['wood'] = 1
                        help_favour(farm, npc_id)
                    else:
                        farm.request_day, farm.request_npc = 2, npc_id
                        farm.request_item, farm.request_count = 'crop:ca_rot', 1
                        farm.request_done = False
                        if action == 'letter':
                            farm.produce['ca_rot'] = 1
                            deliver_request(farm, npc_id)
                    contextual = self.line(farm, npc_id, 'work')
                    self.assertNotEqual(plain, contextual)
                    if action in ('letter', 'pending_letter'):
                        self.assertIn('cà rốt', contextual.lower())
                    replies.add(contextual)
            self.assertEqual(len(replies), 8)

    def test_all_dialogue_nodes_freeze_context_when_the_conversation_opens(self):
        farm = self.near(day=2)
        original = dialogue.begin_dialogue(farm, 'lan', 'secret')
        nodes = deepcopy(original._nodes)
        farm.day, farm.weather, farm.friendships['lan'] = 3, 'rainy', 8
        farm.gifted_on['lan'] = farm.day
        dialogue.choose_response(farm, original, 'warm')
        dialogue.choose_response(farm, original, 'ask')
        self.assertEqual(original._nodes, nodes)
        self.assertEqual(original.history[-1], 'Lan: ' + nodes['warm_ask'].npc_line)

    def test_finished_village_projects_reach_all_eight_voices(self):
        projects = {'lan': 'greenhouse', 'tu': 'pier', 'an': 'orchard',
                    'mai': 'archive', 'son': 'sanctuary', 'hai': 'mill',
                    'minh': 'lighthouse', 'ha': 'workshop'}
        replies = set()
        for npc_id, project in projects.items():
            with self.subTest(npc=npc_id):
                farm = self.near(npc_id, day=2)
                original = self.line(farm, npc_id, 'village')
                farm.restoration[project] = 2
                self.assertEqual(self.line(farm, npc_id, 'village'), original)
                farm.restoration[project] = 3
                changed = self.line(farm, npc_id, 'village')
                self.assertNotEqual(changed, original)
                replies.add(changed)
        self.assertEqual(len(replies), 8)

    def test_three_hearts_add_familiarity_without_replacing_the_story(self):
        for npc_id in NPCS:
            with self.subTest(npc=npc_id):
                farm = self.near(npc_id, day=2)
                original = self.line(farm, npc_id, 'work')
                farm.friendships[npc_id] = 3
                familiar = self.line(farm, npc_id, 'work')
                self.assertNotEqual(original, familiar)
                if npc_id in dialogue.BRANCHING_NPC_IDS:
                    current = dialogue.begin_dialogue(farm, npc_id, 'work')
                    self.assertEqual([choice.id for choice in dialogue.dialogue_node(current).choices],
                                     ['warm', 'practical'])


if __name__ == '__main__':
    unittest.main()
