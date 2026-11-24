import unittest
from dataclasses import asdict

from farmgame.model import Farm, GameError
from farmgame.villagers import NPCS, nearby_npc, npc_at, talk


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.farm = Farm(player_x=28, player_y=4, facing='down')

    def test_topics_have_distinct_responses_and_friendship_increases_once_daily(self):
        farm = self.farm
        first = talk(farm, 'lan', 'greet')
        second = talk(farm, 'lan', 'work')
        third = talk(farm, 'lan', 'village')
        self.assertIn('Lan', first)
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(farm.friendships['lan'], 1)
        self.assertEqual(farm.talked_on['lan'], 1)
        self.assertEqual((farm.day, farm.energy, farm.coins, farm.xp), (1, 20, 120, 0))

    def test_new_day_changes_conversation_and_allows_one_more_point(self):
        first = talk(self.farm, 'lan')
        self.farm.sleep('rainy')
        second = talk(self.farm, 'lan')
        self.assertNotEqual(first, second)
        self.assertIn('mưa', second.lower())
        self.assertEqual(self.farm.friendships['lan'], 2)
        self.assertEqual(self.farm.talked_on['lan'], 2)

    def test_friendship_caps_at_ten_without_blocking_conversation(self):
        for _ in range(12):
            talk(self.farm, 'lan')
            self.farm.sleep()
        self.assertEqual(self.farm.friendships['lan'], 10)
        self.assertTrue(talk(self.farm, 'lan', 'work'))

    def test_invalid_id_topic_or_distance_never_changes_state(self):
        for npc_id, topic in (('missing', 'greet'), ('lan', 'missing'), ('mai', 'greet')):
            before = asdict(self.farm)
            with self.assertRaises(GameError):
                talk(self.farm, npc_id, topic)
            self.assertEqual(asdict(self.farm), before)
        self.farm.area = 'home'
        before = asdict(self.farm)
        with self.assertRaises(GameError):
            talk(self.farm, 'lan')
        self.assertEqual(asdict(self.farm), before)

    def test_every_villager_can_be_found_and_has_its_own_dialogue(self):
        replies = set()
        for key, npc in NPCS.items():
            farm = Farm(player_x=npc.position[0], player_y=npc.position[1] + 1)
            self.assertEqual(npc_at(*npc.position).id, key)
            self.assertIsNone(npc_at(*npc.position, area='home'))
            self.assertEqual(nearby_npc(farm).id, key)
            replies.add(talk(farm, key, 'work'))
            self.assertEqual(farm.friendships[key], 1)
        self.assertEqual(len(replies), len(NPCS))

    def test_legacy_player_on_npc_tile_can_chat_and_leave(self):
        self.farm.player_x, self.farm.player_y = NPCS['lan'].position
        self.assertEqual(nearby_npc(self.farm).id, 'lan')
        talk(self.farm, 'lan')
        self.assertEqual(self.farm.friendships['lan'], 1)


if __name__ == '__main__':
    unittest.main()
