"""Quà tặng, giúp đỡ và thư nhờ giúp đỡ — các cách nâng thân tình mới."""
import unittest
from dataclasses import asdict

from farmgame import bonds
from farmgame.bonds import (deliver_request, ensure_request, gift_options,
                            give_gift, help_favour, help_available,
                            request_ready)
from farmgame.model import Farm, GameError
from farmgame.storage import load_game, save_game
from farmgame.villagers import NPCS, family_line, relative_of
from farmgame.villagers import _FAMILIES as FAMILIES


class FamilyTests(unittest.TestCase):
    def test_families_are_symmetric_and_positions_are_walkable(self):
        for npc_id, relative in FAMILIES.items():
            self.assertEqual(relative_of(relative), npc_id)
            self.assertIn(NPCS[relative].name, family_line(npc_id))
        for npc in NPCS.values():
            with self.subTest(npc=npc.id):
                from farmgame.world import walkable
                self.assertTrue(all(
                    walkable('village', *npc.position, size)
                    for size in (4, 5, 6)))


class GiftTests(unittest.TestCase):
    def farm(self, npc_id='an'):
        x, y = NPCS[npc_id].position
        farm = Farm(player_x=x, player_y=y + 1)
        farm.produce['hoa_hong'] = 2
        farm.items['ca_vang'] = 1
        return farm

    def test_family_thanks_name_the_relative_not_the_giver(self):
        for npc_id, relative in FAMILIES.items():
            with self.subTest(npc=npc_id):
                farm = self.farm(npc_id)
                farm.items['banh_mi'] = 1
                output = give_gift(farm, npc_id, 'banh_mi')
                self.assertIn(NPCS[relative].name, output)

    def test_gift_lines_keep_each_speakers_address(self):
        from farmgame.bonds import _GIFT_NORMAL, _GIFT_THANKS
        for line in _GIFT_NORMAL:
            self.assertNotIn('bạn', line.lower())
            self.assertNotIn('mình', line.lower())

        def spoken(npc_id):
            return ' '.join(
                part for line in _GIFT_THANKS[npc_id]
                for part in line.split('"')[1::2]).lower()

        for npc_id in ('lan', 'an', 'mai', 'son', 'ha'):
            joined = spoken(npc_id)
            self.assertNotIn('bạn', joined)
            self.assertNotIn('mình', joined)
        minh = spoken('minh')
        self.assertIn('anh/chị', minh)
        self.assertNotIn('bạn', minh)
        self.assertNotIn('mình', minh)
        self.assertNotIn('cậu', minh)
        for npc_id in ('tu', 'hai'):
            joined = spoken(npc_id)
            self.assertNotIn('bạn', joined)
            self.assertNotIn('mình', joined)

    def test_liked_gift_warms_two_hearts_and_consumes_one_item(self):
        farm = self.farm()
        options = gift_options(farm)
        self.assertIn(('crop:hoa_hong', 'Hoa hồng ×2'),
                      [(key, label) for key, label in options])
        output = give_gift(farm, 'an', 'crop:hoa_hong')
        self.assertEqual(farm.produce['hoa_hong'], 1)
        self.assertEqual(farm.friendships['an'], 2)
        self.assertIn('Hoa hồng', output)
        self.assertIn('+2', output)

    def test_one_gift_per_villager_per_day_is_atomic(self):
        farm = self.farm()
        give_gift(farm, 'an', 'crop:hoa_hong')
        before = asdict(farm)
        with self.assertRaises(GameError):
            give_gift(farm, 'an', 'ca_vang')
        self.assertEqual(asdict(farm), before)

    def test_family_warms_the_relative_too_once_a_day(self):
        farm = self.farm('hai')
        farm.items['tra_hoa_hong'] = 1
        self.assertIn('Bác Tư', give_gift(farm, 'hai', 'tra_hoa_hong'))
        self.assertEqual(farm.friendships['hai'], 2)
        self.assertEqual(farm.friendships['tu'], 1)


class HelpTests(unittest.TestCase):
    def test_daily_favour_costs_energy_for_most_villagers(self):
        farm = Farm(player_x=NPCS['lan'].position[0],
                    player_y=NPCS['lan'].position[1] + 1)
        output = help_favour(farm, 'lan')
        self.assertEqual(farm.energy, 19)
        self.assertEqual(farm.friendships['lan'], 1)
        self.assertIn('1/10', output)
        before = asdict(farm)
        with self.assertRaises(GameError):
            help_favour(farm, 'lan')
        self.assertEqual(asdict(farm), before)

    def test_repair_helper_asks_for_wood(self):
        farm = Farm(player_x=NPCS['ha'].position[0],
                    player_y=NPCS['ha'].position[1] + 1)
        with self.assertRaises(GameError):
            help_favour(farm, 'ha')
        farm.items['wood'] = 1
        help_favour(farm, 'ha')
        self.assertEqual(farm.items['wood'], 0)
        self.assertEqual(farm.friendships['ha'], 1)
        self.assertFalse(help_available(farm, 'ha'))


class RequestLetterTests(unittest.TestCase):
    def test_letter_is_deterministic_and_arrives_with_the_new_day(self):
        farm = Farm()
        first = ensure_request(farm)
        self.assertIn('Thư nhờ', first)
        before = asdict(farm)
        self.assertEqual(ensure_request(farm), '')
        self.assertEqual(asdict(farm), before)
        npc_id = farm.request_npc
        message = farm.sleep()
        self.assertIn('Thư nhờ', message)
        self.assertEqual(farm.request_day, farm.day)
        self.assertNotEqual(farm.request_npc, npc_id)
        self.assertTrue(request_ready(farm, farm.request_npc))

    def test_delivering_the_letter_warms_the_bond_and_pays_thanks(self):
        farm = Farm()
        ensure_request(farm)
        x, y = NPCS[farm.request_npc].position
        farm.player_x, farm.player_y = x, y + 1
        key = farm.request_item
        plain = key.split(':', 1)[-1]
        source = farm.produce if key.startswith('crop:') else (
            farm.seeds if key.startswith('seed:') else farm.items)
        source[plain] = farm.request_count
        coins_before = farm.coins
        output = deliver_request(farm, farm.request_npc)
        self.assertEqual(source[plain], 0)
        self.assertEqual(farm.friendships[farm.request_npc], 2)
        self.assertGreater(farm.coins, coins_before)
        self.assertTrue(farm.request_done)
        self.assertIn('Đúng thứ đang cần', output)
        # The same letter cannot be claimed twice.
        before = asdict(farm)
        with self.assertRaises(GameError):
            deliver_request(farm, farm.request_npc)
        self.assertEqual(asdict(farm), before)

    def test_letter_survives_save_and_reload(self):
        farm = Farm()
        ensure_request(farm)
        with __import__('tempfile').TemporaryDirectory() as temp:
            path = Path = __import__('pathlib').Path(temp) / 'farm.json'
            save_game(farm, path)
            restored = load_game(path)
        for key in ('request_day', 'request_npc', 'request_item',
                    'request_count', 'request_done'):
            self.assertEqual(getattr(restored, key), getattr(farm, key), key)


class LightChatTests(unittest.TestCase):
    def test_family_members_chat_without_quizzing_the_player(self):
        from farmgame.dialogue import begin_light_chat, dialogue_node
        for npc_id in ('hai', 'minh', 'ha'):
            with self.subTest(npc=npc_id):
                farm = Farm(player_x=NPCS[npc_id].position[0],
                            player_y=NPCS[npc_id].position[1] + 1)
                conversation = begin_light_chat(farm, npc_id)
                node = dialogue_node(conversation)
                self.assertFalse(node.choices)
                self.assertNotIn('?', node.npc_line)
                self.assertIn(NPCS[npc_id].name, conversation.history[0])
                # The visit still counts as talking to them once a day.
                self.assertEqual(farm.friendships[npc_id], 1)
                self.assertEqual(farm.xp, 3)
                self.assertEqual(farm.talked_on[npc_id], farm.day)


if __name__ == '__main__':
    unittest.main()
