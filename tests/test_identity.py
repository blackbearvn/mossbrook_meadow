import unittest
from dataclasses import asdict

from farmgame import identity
from farmgame.model import Farm


class IdentityTests(unittest.TestCase):
    def test_name_normalization_and_validation(self):
        self.assertEqual(identity.normalize_name('  Ma\u0302y  ', 24, 'Tên'), 'Mây')
        self.assertEqual(identity.normalize_name('a' * 24, 24, 'Tên'), 'a' * 24)
        for value in ('', '   ', 'a' * 25, 'a\nb', '\x1b[2J', None, 12):
            with self.subTest(value=value), self.assertRaises(ValueError):
                identity.normalize_name(value, 24, 'Tên')

    def test_creation_keeps_gameplay_defaults_for_every_background(self):
        baseline = asdict(Farm())
        profile = {'name', 'player_name', 'avatar', 'outfit', 'background', 'intro_seen', 'tutorial'}
        for background in ('gardener', 'angler', 'traveler'):
            farm = identity.create_character('  An  ', '  Vườn An  ', '&', 'cyan', background)
            self.assertEqual((farm.player_name, farm.name, farm.avatar, farm.outfit),
                             ('An', 'Vườn An', '&', 'cyan'))
            self.assertEqual(farm.background, background)
            self.assertFalse(farm.intro_seen)
            self.assertEqual({k: v for k, v in asdict(farm).items() if k not in profile},
                             {k: v for k, v in baseline.items() if k not in profile})
        self.assertTrue(Farm().intro_seen)

    def test_new_character_offers_tutorial_without_starting_it(self):
        farm = identity.create_character('An', 'Vườn')
        self.assertEqual(farm.tutorial.status, 'pending')
        self.assertEqual(farm.tutorial.step, 0)
        self.assertEqual(farm.tutorial.moves, 0)
        self.assertFalse(farm.tutorial.reward_given)
        self.assertEqual(Farm().tutorial.status, 'off')

    def test_invalid_choices_and_farm_names_fail_before_creation(self):
        for changes in ({'avatar': '?'}, {'avatar': []}, {'outfit': 'red'},
                        {'background': 'king'}, {'farm_name': 'a' * 29},
                        {'player_name': 'a' * 25}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                identity.create_character(**{'player_name': 'An', 'farm_name': 'Vườn', **changes})

    def test_intro_has_three_personalized_pages_and_never_changes_farm(self):
        stories = []
        for background in ('gardener', 'angler', 'traveler'):
            farm = identity.create_character('Bình', 'Vườn Nắng', background=background)
            before = asdict(farm)
            pages = identity.intro_pages(farm)
            self.assertEqual(len(pages), 3)
            self.assertTrue(all(isinstance(p, tuple) and len(p) == 2 and all(p) for p in pages))
            story = '\n'.join(title + body for title, body in pages)
            for text in ('Bình', 'Vườn Nắng', 'Lan', '26', '42', 'WASD', 'E', 'C'):
                self.assertIn(text, story)
            self.assertEqual(asdict(farm), before)
            stories.append(story)
        self.assertEqual(len(set(stories)), 3)

    def test_intro_field_hint_matches_starting_area_and_destination(self):
        from farmgame.world import FIELD_ORIGIN
        farm = identity.create_character('An', 'Vườn')
        pages = identity.intro_pages(farm)
        self.assertEqual(farm.area, 'village')
        self.assertGreater(FIELD_ORIGIN[1], farm.player_y)
        self.assertIn('đầu làng', pages[1][1])
        self.assertIn('Từ khu nhà, theo đường làng về phía nam', pages[2][1])
        self.assertIn(str(FIELD_ORIGIN), pages[2][1])
