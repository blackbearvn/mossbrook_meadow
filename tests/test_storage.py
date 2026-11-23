import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from farmgame.model import Farm
from farmgame.storage import SaveError, backup_save, load_game, save_game

PROFILE_FIELDS = {'player_name', 'avatar', 'outfit', 'background', 'intro_seen'}


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "saves" / "farm.json"

    def test_round_trip_preserves_active_crops_inventory_and_upgrades(self):
        farm = Farm(name="Vườn nhà", coins=1000)
        farm.upgrade("land")
        farm.upgrade("energy")
        farm.plant("E5", "ca_rot")
        farm.water("E5")
        farm.sleep("rainy")
        farm.buy_seeds("lua_mi", 3)
        save_game(farm, self.path)
        restored = load_game(self.path)
        self.assertEqual(asdict(restored), asdict(farm))
        restored.sleep("sunny")
        restored.harvest("E5")
        restored.sell_all()
        self.assertEqual(restored.sales, 24)

    def test_save_replaces_existing_file_and_leaves_no_temp_files(self):
        farm = Farm()
        save_game(farm, self.path)
        farm.work()
        save_game(farm, self.path)
        self.assertEqual(load_game(self.path).coins, 126)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_failed_replacement_preserves_previous_save_and_cleans_temp_file(self):
        farm = Farm()
        save_game(farm, self.path)
        original = self.path.read_bytes()
        farm.work()
        with patch("pathlib.Path.replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(SaveError):
                save_game(farm, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_backup_keeps_previous_game_when_new_save_is_written(self):
        farm = Farm(day=9, coins=450)
        save_game(farm, self.path)
        backup = backup_save(self.path)
        save_game(Farm(), self.path)
        self.assertEqual(load_game(backup).day, 9)
        self.assertEqual(load_game(backup).coins, 450)
        self.assertEqual(load_game(self.path).day, 1)

    def test_invalid_json_and_non_utf8_are_readable_errors(self):
        self.path.parent.mkdir()
        for content in (b"{invalid", b"\xff\xfe"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_missing_save_is_a_readable_error(self):
        with self.assertRaises(SaveError):
            load_game(self.path)

    def test_new_save_uses_schema_seven_for_daily_progress(self):
        save_game(Farm(), self.path)
        document = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(document['version'], 7)
        self.assertIn('daily', document['farm'])

    def test_invalid_game_state_is_rejected_before_play(self):
        save_game(Farm(), self.path)
        original = self.path.read_text(encoding="utf-8")
        changes = [
            ("coins", -1), ("coins", True), ("energy", 100),
            ("max_energy", 0), ("size", 99), ("day", 0),
            ("weather", "snow"), ("weather", []), ("xp", 1.5),
            ("sprinkler", "false"), ("name", "bad\x1b[2J"),
            ("seeds", {"lua_mi": 1}), ("plots", {}),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value):
                data = json.loads(original)
                data["farm"][field] = value
                self.path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_invalid_plots_cannot_crash_the_renderer(self):
        farm = Farm()
        farm.plant("A1", "ca_rot")
        save_game(farm, self.path)
        original = self.path.read_text(encoding="utf-8")
        for field, value in (("crop", "unknown"), ("crop", []),
                             ("growth", 99), ("growth", -1),
                             ("watered", 1), ("dead", "yes"),
                             ("dry_days", -1)):
            with self.subTest(field=field, value=value):
                data = json.loads(original)
                data["farm"]["plots"]["A1"][field] = value
                self.path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_unknown_version_and_non_object_root_are_rejected(self):
        self.path.parent.mkdir()
        for data in ([], None, {"version": 999, "farm": {}},
                     {"version": True, "farm": {}}, {"version": 1}):
            with self.subTest(data=data):
                self.path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_version_one_migrates_without_losing_original_progress(self):
        self.path.parent.mkdir()
        plots = {f'{column}{row}': {
            'crop': None, 'growth': 0, 'watered': False,
            'dry_days': 0, 'dead': False,
        } for row in range(1, 5) for column in 'ABCD'}
        plots['A1'] = {'crop': 'ca_rot', 'growth': 1, 'watered': True,
                       'dry_days': 0, 'dead': False}
        legacy = {
            'name': 'Vườn cũ', 'day': 12, 'coins': 275, 'energy': 12,
            'max_energy': 20, 'xp': 37, 'size': 4, 'weather': 'sunny',
            'sprinkler': False, 'harvested': 17, 'sales': 432,
            'seeds': {'ca_rot': 3, 'lua_mi': 5, 'ca_chua': 0, 'bap': 0, 'bi_ngo': 0},
            'produce': {'ca_rot': 2, 'lua_mi': 0, 'ca_chua': 0, 'bap': 0, 'bi_ngo': 0},
            'plots': plots,
        }
        self.path.write_text(json.dumps({'version': 1, 'farm': legacy}), encoding='utf-8')
        restored = load_game(self.path)
        self.assertEqual((restored.day, restored.coins, restored.xp), (12, 275, 37))
        self.assertEqual(restored.produce['ca_rot'], 2)
        self.assertEqual(restored.plots['A1'].growth, 1)
        self.assertEqual(restored.items['feed'], 8)
        self.assertEqual((restored.area, restored.player_x, restored.player_y),
                         ('village', 10, 7))
        self.assertEqual(sum(restored.chest.values()), 0)
        self.assertEqual(restored.animals, [])
        save_game(restored, self.path)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['version'], 7)

    def test_home_forecast_items_and_chest_survive_save(self):
        farm = Farm(area='home', player_x=8, player_y=7, facing='up', forecast='rainy')
        farm.items['ca_vang'] = 2
        farm.chest['milk'] = 3
        farm.chest['seed:ca_rot'] = 4
        save_game(farm, self.path)
        restored = load_game(self.path)
        self.assertEqual(asdict(restored), asdict(farm))
        restored.sleep()
        self.assertEqual(restored.weather, 'rainy')

    def test_invalid_new_fields_are_rejected(self):
        save_game(Farm(), self.path)
        original = self.path.read_text(encoding='utf-8')
        for field, value in (
            ('area', 'sky'), ('player_x', -1), ('player_y', 99),
            ('facing', 'diagonal'), ('forecast', []), ('fish_caught', True),
            ('items', {}), ('chest', {}), ('barn_capacity', 999),
            ('animals', [{'kind': 'dragon'}]),
        ):
            with self.subTest(field=field, value=value):
                data = json.loads(original)
                data['farm'][field] = value
                self.path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_livestock_survives_reload_and_produces_through_real_sleep(self):
        from farmgame.animals import buy_animal, collect_products, feed_animals
        farm = Farm(coins=1000, xp=40)
        for kind in ('chicken', 'cow', 'sheep'):
            buy_animal(farm, kind)
        feed_animals(farm)
        farm.sleep()
        feed_animals(farm)
        farm.sleep()
        save_game(farm, self.path)
        restored = load_game(self.path)
        self.assertEqual(asdict(restored), asdict(farm))
        restored.buy_item('feed', 6)
        feed_animals(restored)
        restored.sleep()
        collect_products(restored)
        self.assertEqual(restored.items['egg'], 2)
        self.assertEqual(restored.items['milk'], 1)
        self.assertEqual(restored.items['wool'], 0)
        self.assertEqual(restored.animals[1].age, 3)
        self.assertFalse(restored.animals[1].fed)

    def test_version_two_gains_npc_state_and_preserves_the_farm(self):
        old_farm = Farm(day=9, coins=413, xp=47, player_x=21, player_y=9)
        old_farm.items['ca_chep'] = 2
        old_farm.chest['seed:ca_rot'] = 3
        data = asdict(old_farm)
        data.pop('daily', None)
        data.pop('tutorial', None)
        del data['friendships']
        del data['talked_on']
        data.pop('attributes', None)
        data.pop('skills', None)
        for key in PROFILE_FIELDS:
            data.pop(key, None)
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({'version': 2, 'farm': data}), encoding='utf-8')
        restored = load_game(self.path)
        self.assertEqual((restored.day, restored.coins, restored.xp), (9, 413, 47))
        self.assertEqual((restored.player_x, restored.player_y), (21, 9))
        self.assertEqual(restored.items['ca_chep'], 2)
        self.assertEqual(restored.chest['seed:ca_rot'], 3)
        self.assertEqual(sum(restored.friendships.values()), 0)
        self.assertEqual(sum(restored.talked_on.values()), 0)
        save_game(restored, self.path)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['version'], 7)

    def test_reloading_does_not_allow_duplicate_daily_friendship(self):
        from farmgame.villagers import talk
        farm = Farm(player_x=28, player_y=4)
        talk(farm, 'lan')
        save_game(farm, self.path)
        restored = load_game(self.path)
        talk(restored, 'lan', 'work')
        self.assertEqual(restored.friendships['lan'], 1)
        self.assertEqual(restored.talked_on['lan'], 1)
        restored.sleep()
        talk(restored, 'lan')
        self.assertEqual(restored.friendships['lan'], 2)

    def test_invalid_npc_memory_is_rejected(self):
        save_game(Farm(), self.path)
        original = self.path.read_text(encoding='utf-8')
        for field, key, value in (
            ('friendships', 'lan', True), ('friendships', 'lan', 11),
            ('friendships', 'lan', -1), ('talked_on', 'mai', 2),
            ('talked_on', 'tu', -1), ('talked_on', 'son', 'yesterday'),
            ('friendships', 'unknown', 1),
        ):
            with self.subTest(field=field, key=key, value=value):
                data = json.loads(original)
                data['farm'][field][key] = value
                self.path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_version_three_receives_unspent_points_and_preserves_crops(self):
        farm = Farm(xp=120, player_x=3, player_y=4)
        farm.plant('A1', 'ca_rot')
        farm.water('A1')
        farm.friendships['lan'] = 3
        data = asdict(farm)
        data.pop('daily', None)
        data.pop('tutorial', None)
        data.pop('attributes', None)
        data.pop('skills', None)
        for key in PROFILE_FIELDS:
            data.pop(key, None)
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({'version': 3, 'farm': data}), encoding='utf-8')
        restored = load_game(self.path)
        self.assertEqual(restored.attribute_points, 3)
        self.assertEqual(restored.skill_points, 6)
        self.assertEqual(restored.plots['A1'].crop, 'ca_rot')
        self.assertTrue(restored.plots['A1'].watered)
        self.assertEqual(restored.friendships['lan'], 3)
        self.assertEqual((restored.player_x, restored.player_y), (3, 4))

    def test_attributes_skills_and_effective_energy_survive_save(self):
        from farmgame.progression import upgrade_attribute, upgrade_skill
        farm = Farm(xp=200)
        upgrade_attribute(farm, 'endurance')
        upgrade_attribute(farm, 'endurance')
        upgrade_skill(farm, 'farming')
        farm.sleep()
        save_game(farm, self.path)
        restored = load_game(self.path)
        self.assertEqual(asdict(restored), asdict(farm))
        self.assertEqual(restored.energy, 28)
        self.assertEqual(restored.attribute_points, 3)
        self.assertEqual(restored.skill_points, 9)

    def test_invalid_or_overspent_character_points_are_rejected(self):
        save_game(Farm(), self.path)
        original = self.path.read_text(encoding='utf-8')
        for field, key, value in (
            ('attributes', 'endurance', 1), ('skills', 'farming', 1),
            ('attributes', 'focus', True), ('skills', 'fishing', -1),
            ('attributes', 'dexterity', 6), ('skills', 'unknown', 1),
        ):
            with self.subTest(field=field, key=key, value=value):
                data = json.loads(original)
                data['farm'].setdefault(field, {})[key] = value
                self.path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_schema_seven_preserves_profile_and_all_progress(self):
        from farmgame.identity import create_character
        farm = create_character('An', 'Vườn An', 'o', 'magenta', 'angler')
        farm.xp = 200
        farm.attributes['endurance'] = 2
        farm.skills['fishing'] = 3
        farm.items['ca_chep'] = 4
        farm.chest['seed:ca_rot'] = 7
        farm.friendships['lan'] = 2
        farm.plant('A1', 'ca_rot')
        save_game(farm, self.path)
        self.assertEqual(json.loads(self.path.read_text())['version'], 7)
        self.assertEqual(asdict(load_game(self.path)), asdict(farm))

    def test_legacy_schemas_get_profile_defaults_without_rewriting(self):
        from farmgame.storage import LEGACY_FIELDS, VERSION_TWO_FIELDS, VERSION_THREE_FIELDS
        version_four_fields = VERSION_THREE_FIELDS | {'attributes', 'skills'}
        farm = Farm(day=8, coins=456, xp=200)
        farm.items['ca_chep'] = 3
        farm.friendships['lan'] = 4
        farm.attributes['endurance'] = 2
        farm.skills['fishing'] = 3
        self.path.parent.mkdir()
        for version, keys in ((1, LEGACY_FIELDS), (2, VERSION_TWO_FIELDS),
                              (3, VERSION_THREE_FIELDS), (4, version_four_fields)):
            with self.subTest(version=version):
                data = {key: value for key, value in asdict(farm).items() if key in keys}
                original = json.dumps({'version': version, 'farm': data}).encode()
                self.path.write_bytes(original)
                restored = load_game(self.path)
                self.assertEqual(self.path.read_bytes(), original)
                self.assertEqual(restored.tutorial.status, 'off')
                self.assertEqual((restored.player_name, restored.avatar, restored.outfit,
                                  restored.background, restored.intro_seen),
                                 ('Người làm vườn', '@', 'green', 'gardener', True))
                for key, value in data.items():
                    self.assertEqual(asdict(restored)[key], value)

    def test_version_five_preserves_every_field_and_never_rewrites(self):
        from farmgame.identity import create_character
        farm = create_character('Bình', 'Vườn Nắng', 'o', 'magenta', 'angler')
        farm.day = 7
        farm.xp = 200
        farm.attributes['endurance'] = 2
        farm.skills['fishing'] = 3
        farm.items['ca_chep'] = 4
        farm.chest['seed:ca_rot'] = 7
        farm.friendships['lan'] = 2
        farm.talked_on['lan'] = 6
        farm.plant('A1', 'ca_rot')
        data = asdict(farm)
        data.pop('daily', None)
        data.pop('tutorial', None)
        self.path.parent.mkdir()
        original = json.dumps({'version': 5, 'farm': data}).encode()
        self.path.write_bytes(original)
        restored = load_game(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        restored_data = asdict(restored)
        self.assertEqual(restored_data.pop('daily'), {'day': 0, 'tasks': []})
        self.assertEqual(restored_data.pop('tutorial')['status'], 'off')
        self.assertEqual(restored_data, data)

    def test_tutorial_progress_reward_and_pause_survive_reload(self):
        from farmgame.tutorial import TutorialState
        farm = Farm(day=7, xp=40)
        farm.plant('A1', 'lua_mi')
        for status, step, reward in (('active', 7, False), ('paused', 14, True),
                                     ('completed', 15, True), ('skipped', 14, True)):
            with self.subTest(status=status):
                farm.tutorial = TutorialState(status=status, step=step, moves=4,
                                              plot='A1', planted_on=6,
                                              watered_on=7, reward_given=reward)
                save_game(farm, self.path)
                restored = load_game(self.path)
                self.assertIsInstance(restored.tutorial, TutorialState)
                self.assertEqual(asdict(restored), asdict(farm))
                self.assertEqual(restored.xp, 40)
                save_game(restored, self.path)
                self.assertEqual(asdict(load_game(self.path)), asdict(farm))

    def test_schema_six_decodes_each_tutorial_status_and_boundary(self):
        base = asdict(Farm(day=7))
        base.pop('daily')
        tutorial = dict(status='off', step=0, moves=0, plot=None,
                        planted_on=0, watered_on=0, reward_given=False)
        self.path.parent.mkdir()
        for status in ('off', 'pending', 'active', 'paused', 'skipped', 'completed'):
            with self.subTest(status=status):
                state = {**tutorial, 'status': status,
                         'step': 15 if status == 'completed' else 14,
                         'moves': 4, 'plot': 'D4', 'planted_on': 7,
                         'watered_on': 7, 'reward_given': True}
                self.path.write_text(json.dumps({'version': 6,
                                                 'farm': {**base, 'tutorial': state}}))
                self.assertEqual(asdict(load_game(self.path).tutorial), state)

    def test_invalid_tutorial_state_is_rejected(self):
        base = asdict(Farm(day=7))
        base.pop('daily')
        tutorial = dict(status='active', step=7, moves=4, plot='A1',
                        planted_on=6, watered_on=7, reward_given=False)
        invalid = [None, [], 'active', {}, {**tutorial, 'unknown': 0}]
        invalid += [{key: value for key, value in tutorial.items() if key != missing}
                    for missing in tutorial]
        invalid += [{**tutorial, key: value} for key, value in (
            ('status', 'unknown'), ('status', []), ('status', True),
            ('step', -1), ('step', 15), ('step', True), ('step', 1.0),
            ('moves', -1), ('moves', 5), ('moves', True), ('moves', '4'),
            ('plot', 'E5'), ('plot', ''), ('plot', []), ('plot', 1),
            ('planted_on', -1), ('planted_on', 8), ('planted_on', True),
            ('watered_on', -1), ('watered_on', 8), ('watered_on', 1.0),
            ('reward_given', 1), ('reward_given', 'false'),
        )]
        invalid += [{**tutorial, 'status': 'completed', 'step': value}
                    for value in (0, 14, 16, True)]
        self.path.parent.mkdir()
        for state in invalid:
            with self.subTest(state=state):
                self.path.write_text(json.dumps({'version': 6,
                                                 'farm': {**base, 'tutorial': state}}))
                with self.assertRaises(SaveError):
                    load_game(self.path)
        self.path.write_text(json.dumps({'version': 6,
                                         'farm': {k: v for k, v in base.items()
                                                  if k != 'tutorial'}}))
        with self.assertRaises(SaveError):
            load_game(self.path)

    def test_invalid_profile_data_is_rejected(self):
        save_game(Farm(), self.path)
        original = json.loads(self.path.read_text())
        for key, value in (('player_name', ''), ('player_name', 'a' * 25),
                           ('player_name', ' An '), ('player_name', 'a\nb'),
                           ('player_name', 'Ma\u0302y'), ('avatar', '?'),
                           ('avatar', []), ('outfit', 'red'), ('outfit', None),
                           ('background', 'king'), ('background', {}),
                           ('intro_seen', 1), ('intro_seen', 'true')):
            with self.subTest(key=key, value=value):
                data = {**original, 'farm': {**original['farm'], key: value}}
                self.path.write_text(json.dumps(data))
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_legacy_schemas_reject_extra_current_fields(self):
        self.path.parent.mkdir()
        for version in (1, 2, 3, 4, 5, 6):
            with self.subTest(version=version):
                self.path.write_text(json.dumps({'version': version, 'farm': asdict(Farm())}))
                with self.assertRaises(SaveError):
                    load_game(self.path)

    def test_schema_seven_fills_crops_animal_goods_and_cooked_slots(self):
        farm = Farm(day=7, coins=513, xp=80)
        data = asdict(farm)
        new_crop_keys = {'khoai_tay', 'dua_hau', 'dau_tay', 'hoa_hong'}
        new_goods = {'fur', 'truffle'}
        cooked = {'banh_mi', 'salad_vuon', 'nuoc_dua_hau', 'cha_ca',
                  'chao_trung', 'sup_bi', 'sinh_to_dau', 'tra_hoa_hong'}
        for key in new_crop_keys:
            data['seeds'].pop(key)
            data['produce'].pop(key)
        for key in list(data['items']):
            if key in new_goods | cooked:
                data['items'].pop(key)
        for key in list(data['chest']):
            if (key.startswith('seed:') or key.startswith('crop:')) and key.split(':', 1)[1] in new_crop_keys:
                data['chest'].pop(key)
            elif key in new_goods | cooked:
                data['chest'].pop(key)
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({'version': 7, 'farm': data}))
        restored = load_game(self.path)
        for key in new_crop_keys:
            self.assertEqual(restored.seeds[key], 0)
            self.assertEqual(restored.produce[key], 0)
            self.assertIn(f'seed:{key}', restored.chest)
            self.assertIn(f'crop:{key}', restored.chest)
        for key in new_goods | cooked:
            self.assertEqual(restored.items[key], 0)
            self.assertIn(key, restored.chest)

    def test_schema_six_adds_daily_board_without_changing_any_old_field(self):
        farm = Farm(day=7, coins=513, xp=80)
        farm.tutorial.status = 'paused'
        farm.tutorial.step = 14
        farm.tutorial.reward_given = True
        farm.items['milk'] = 3
        data = asdict(farm)
        data.pop('daily')
        self.path.parent.mkdir()
        original = json.dumps({'version': 6, 'farm': data}).encode()
        self.path.write_bytes(original)
        restored = load_game(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        current = asdict(restored)
        self.assertEqual(current.pop('daily'), {'day': 0, 'tasks': []})
        self.assertEqual(current, data)

    def test_daily_progress_and_claim_survive_reload_without_duplicate_reward(self):
        from farmgame.daily import ensure_daily, claim_quest
        farm = Farm()
        ensure_daily(farm)
        for key in ('A1', 'B1', 'C1'):
            farm.plant(key, 'lua_mi')
        self.assertEqual(farm.daily.tasks[0].progress, 3)
        save_game(farm, self.path)
        restored = load_game(self.path)
        self.assertEqual(asdict(restored), asdict(farm))
        claim_quest(restored, 0)
        self.assertEqual((restored.coins, restored.xp), (135, 3))
        save_game(restored, self.path)
        restored = load_game(self.path)
        from farmgame.model import GameError
        with self.assertRaises(GameError):
            claim_quest(restored, 0)
        self.assertEqual((restored.coins, restored.xp), (135, 3))
        restored.sleep()
        self.assertEqual(restored.daily.day, 2)
        self.assertFalse(any(task.claimed for task in restored.daily.tasks))

    def test_invalid_daily_data_is_rejected_before_play(self):
        from farmgame.daily import ensure_daily
        farm = Farm()
        ensure_daily(farm)
        base = asdict(farm)
        board = base['daily']
        task = board['tasks'][0]
        invalid = [None, [], {}, {**board, 'day': True}, {**board, 'day': 2},
                   {**board, 'day': 0}, {**board, 'tasks': []},
                   {**board, 'tasks': board['tasks'] * 2},
                   {**board, 'tasks': [task] * 4}]
        invalid_tasks = [None, {}, {**task, 'extra': 1}]
        invalid_tasks += [{**task, key: value} for key, value in (
            ('kind', []), ('kind', 'unknown'), ('target', True), ('target', 0),
            ('target', 4), ('progress', -1), ('progress', 4),
            ('progress', True), ('claimed', 1), ('claimed', True))]
        invalid += [{**board, 'tasks': [invalid_task, *board['tasks'][1:]]}
                    for invalid_task in invalid_tasks]
        self.path.parent.mkdir()
        for value in invalid:
            with self.subTest(value=value):
                self.path.write_text(json.dumps({'version': 7,
                                                 'farm': {**base, 'daily': value}}))
                with self.assertRaises(SaveError):
                    load_game(self.path)


if __name__ == "__main__":
    unittest.main()
