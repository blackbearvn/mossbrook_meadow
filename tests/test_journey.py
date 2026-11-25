"""Playable countryside content, community progression and save migration."""
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from farmgame import journey, pages, regions, world
from farmgame.inventory import count_item
from farmgame.model import Farm, GameError
from farmgame.storage import SaveError, load_game, save_game


class JourneyTests(unittest.TestCase):
    def at(self, key, **kwargs):
        site = journey.SITES[key]
        return Farm(player_x=site.position[0], player_y=site.position[1], **kwargs)

    def test_every_page_has_reachable_named_content_and_its_own_story(self):
        self.assertEqual(set(journey.SITES), set(pages.PAGES))
        self.assertEqual(len({site.story for site in journey.SITES.values()}), 31)
        for key, site in journey.SITES.items():
            with self.subTest(site=key):
                self.assertTrue(pages.PAGES[key].contains(*site.position))
                self.assertEqual(pages.page_for_coord(*site.position).key, key)
                self.assertTrue(world.walkable('village', *site.position))
                self.assertEqual(journey.nearby_site(self.at(key)).key, key)
                self.assertGreater(len(site.story), 60)
                self.assertEqual(len(site.gather), 4)
                farm = self.at(key)
                farm.facing = 'down'
                self.assertEqual(world.context(farm)[0], 'site')

    def test_discovery_is_once_only_and_reading_the_journal_is_pure(self):
        farm = self.at('east_wood')
        before = asdict(farm)
        self.assertTrue(journey.journal_lines(farm))
        self.assertEqual(asdict(farm), before)
        self.assertIn('Rừng Đông', journey.discover(farm))
        self.assertEqual(farm.discovered, {'east_wood': 1})
        self.assertEqual(journey.discover(farm), '')
        farm.area = 'home'
        self.assertEqual(journey.discover(farm), '')

    def test_movement_and_fast_travel_record_visits_without_reward_farming(self):
        farm = Farm()
        coins, xp = farm.coins, farm.xp
        world.move(farm, 'left')
        self.assertIn('residential', farm.discovered)
        regions.travel(farm, 'east_wood')
        self.assertIn('east_wood', farm.discovered)
        self.assertEqual((farm.coins, farm.xp), (coins, xp))

    def test_gathering_each_site_once_per_day_and_next_morning_regrows_it(self):
        farm = self.at('east_wood')
        site = journey.SITES['east_wood']
        item = site.gather[0]
        before = count_item(farm, item)
        journey.gather(farm, site.key)
        self.assertGreater(count_item(farm, item), before)
        self.assertEqual(farm.energy, 18)
        self.assertIn(site.key, farm.discovered)
        state = asdict(farm)
        with self.assertRaises(GameError):
            journey.gather(farm, site.key)
        self.assertEqual(asdict(farm), state)
        farm.sleep('sunny')
        journey.gather(farm, site.key)
        self.assertEqual(farm.gathered_on[site.key], 2)

    def test_invalid_gather_distance_and_energy_do_not_mutate_state(self):
        farm = Farm(energy=0)
        for key in ('east_wood', 'missing', [], None):
            before = asdict(farm)
            with self.assertRaises(GameError):
                journey.gather(farm, key)
            self.assertEqual(asdict(farm), before)
        farm = self.at('east_wood', energy=1)
        before = asdict(farm)
        with self.assertRaises(GameError):
            journey.gather(farm, 'east_wood')
        self.assertEqual(asdict(farm), before)

    def test_seasons_cycle_with_year_and_change_local_products(self):
        self.assertEqual([journey.season_name(Farm(day=d)) for d in
                          (1, 28, 29, 57, 85, 113)],
                         ['Xuân', 'Xuân', 'Hạ', 'Thu', 'Đông', 'Xuân'])
        site = journey.SITES['meadow']
        self.assertGreater(len(set(site.gather)), 1)
        for day in (1, 29, 57, 85):
            farm = self.at('meadow', day=day)
            item = site.gather[(day-1)//28]
            before = count_item(farm, item)
            journey.gather(farm, 'meadow')
            self.assertGreater(count_item(farm, item), before)

    def test_forage_can_be_cooked_and_the_finished_dishes_can_be_sold(self):
        from farmgame.cooking import cook
        from farmgame.shop import sell_item
        farm = Farm(area='home', player_x=11, player_y=6, energy=0)
        farm.items['mushroom'] = 2
        farm.items['milk'] = 1
        cook(farm, 'sup_nam')
        self.assertEqual((farm.items['mushroom'], farm.items['milk']), (0, 0))
        self.assertEqual(farm.items['sup_nam'], 1)
        self.assertGreater(farm.energy, 0)
        coins = farm.coins
        sell_item(farm, 'sup_nam', 1)
        self.assertGreater(farm.coins, coins)
        self.assertEqual(farm.items['sup_nam'], 0)

    def fund_stage(self, farm, project):
        stage = project.stages[farm.restoration.get(project.key, 0)]
        while farm.day < stage.day:
            farm.sleep('sunny')
        for item, amount in stage.materials.items():
            farm.chest[item] += amount
        farm.coins += stage.coins
        for key in stage.visits:
            farm.discovered[key] = farm.day

    def test_projects_take_bag_then_chest_and_award_once_per_stage(self):
        project = journey.PROJECTS['greenhouse']
        farm = self.at(project.site)
        self.fund_stage(farm, project)
        first_item = next(iter(project.stages[0].materials))
        # Split one required material across the bag and the chest.
        from farmgame.inventory import _bag_slot
        slot, key = _bag_slot(farm, first_item)
        slot[key] += 1
        farm.chest[first_item] -= 1
        before = count_item(farm, first_item) + farm.chest[first_item]
        required = project.stages[0].materials[first_item]
        journey.restore(farm, project.key)
        self.assertEqual(farm.restoration[project.key], 1)
        self.assertEqual(count_item(farm, first_item) + farm.chest[first_item], before-required)
        for _ in range(2):
            self.fund_stage(farm, project)
            journey.restore(farm, project.key)
        self.assertEqual(farm.restoration[project.key], 3)
        before = asdict(farm)
        with self.assertRaises(GameError):
            journey.restore(farm, project.key)
        self.assertEqual(asdict(farm), before)

    def test_missing_project_materials_or_visit_is_atomic(self):
        project = journey.PROJECTS['greenhouse']
        farm = self.at(project.site)
        before = asdict(farm)
        with self.assertRaises(GameError):
            journey.restore(farm, project.key)
        self.assertEqual(asdict(farm), before)
        self.fund_stage(farm, project)
        farm.discovered.clear()
        before = asdict(farm)
        with self.assertRaises(GameError):
            journey.restore(farm, project.key)
        self.assertEqual(asdict(farm), before)
        far = Farm(coins=9999)
        before = asdict(far)
        with self.assertRaises(GameError):
            journey.restore(far, project.key)
        self.assertEqual(asdict(far), before)

    def test_completed_mill_generates_feed_each_morning(self):
        farm = Farm(restoration={'mill': 3})
        before = farm.items['feed']
        message = farm.sleep('sunny')
        self.assertEqual(farm.items['feed'], before+2)
        self.assertIn('Cối xay', message)

    def test_archive_level_up_is_reported_and_new_health_limit_is_filled(self):
        farm = Farm(xp=38, hp=1, restoration={'archive': 3})
        message = farm.sleep('sunny')
        self.assertEqual(farm.level, 2)
        self.assertEqual(farm.hp, farm.max_hp)
        self.assertIn('LÊN CẤP 2', message)

    def test_restored_pier_reduces_real_fishing_cost(self):
        from farmgame.fishing import start_fishing
        from farmgame.progression import action_cost
        farm = Farm(player_x=21, player_y=9, restoration={'pier': 3})
        cost = action_cost(Farm(), 'fish')
        start_fishing(farm)
        self.assertEqual(farm.energy, 20-max(1, cost-1))

    def test_restoration_waits_for_later_days_before_spending_materials(self):
        project = journey.PROJECTS['greenhouse']
        farm = self.at(project.site, restoration={'greenhouse': 1})
        before = asdict(farm)
        with self.assertRaisesRegex(GameError, 'ngày 3'):
            journey.restore(farm, project.key)
        self.assertEqual(asdict(farm), before)

    def test_page_travel_reaches_every_countryside_page(self):
        farm = Farm(map_pages=True)
        for page in pages.PAGES.values():
            destinations = regions.travel_regions(farm)
            self.assertTrue(any(pages.page_for_coord(*r.spawn).key == page.key
                                for r in destinations), page.key)
            self.assertTrue(regions.can_travel(farm, page.key))
            regions.travel(farm, page.key)
            self.assertEqual(pages.page_for_coord(farm.player_x, farm.player_y).key,
                             page.key)

    def test_travel_to_site_and_map_marker_are_shared_and_pure(self):
        from farmgame.map_art import map_cell
        from farmgame.explore import overview_rows
        farm = Farm()
        journey.travel_to_site(farm, 'south_3_3')
        site = journey.SITES['south_3_3']
        self.assertEqual((farm.player_x, farm.player_y), site.position)
        self.assertEqual(world.context(farm)[0], 'site')
        farm.player_x -= 1
        before = asdict(farm)
        self.assertEqual(map_cell(farm, *site.position, unicode=False).glyph, '!')
        self.assertGreaterEqual(''.join(overview_rows(farm, 160, 50)).count('!'), 31)
        self.assertEqual(asdict(farm), before)

    def test_site_markers_remain_visible_during_all_animation_phases(self):
        from farmgame.map_art import map_cell
        farm = Farm()
        for site in journey.SITES.values():
            for phase in (0, 1, 17, 298):
                with self.subTest(site=site.key, phase=phase):
                    self.assertEqual(map_cell(farm, *site.position,
                                              unicode=False, phase=phase).glyph, '!')

    def test_spring_has_all_living_materials_for_early_restoration(self):
        available = {site.gather[0] for site in journey.SITES.values()}
        self.assertTrue(set(journey.FORAGE_ITEMS) <= available)

    def test_all_projects_complete_through_real_stage_and_morning_rules(self):
        farm = Farm()
        for project in journey.PROJECTS.values():
            journey.travel_to_site(farm, project.site)
            for phase in range(3):
                self.fund_stage(farm, project)
                journey.restore(farm, project.key)
                self.assertEqual(farm.restoration[project.key], phase+1)
        before_feed, before_seeds = farm.items['feed'], sum(farm.seeds.values())
        before_coins, before_xp, before_berry = farm.coins, farm.xp, farm.items['berry']
        farm.sleep('sunny')
        self.assertEqual(farm.items['feed'], before_feed+2)
        self.assertEqual(sum(farm.seeds.values()), before_seeds+2)
        self.assertEqual(farm.coins, before_coins+10)
        self.assertEqual(farm.xp, before_xp+5)
        self.assertGreater(farm.items['berry'], before_berry)

    def test_same_festival_can_return_next_year(self):
        farm = self.at('square', day=119, festivals_on={'spring': 7})
        farm.produce['lua_mi'] = 2
        journey.attend_festival(farm)
        self.assertEqual(farm.festivals_on['spring'], 119)

    def test_festivals_require_the_right_day_and_place_and_cannot_repeat(self):
        farm = self.at('square', day=7)
        farm.produce['lua_mi'] = 2
        journey.attend_festival(farm)
        self.assertEqual(farm.festivals_on['spring'], 7)
        before = asdict(farm)
        with self.assertRaises(GameError):
            journey.attend_festival(farm)
        self.assertEqual(asdict(farm), before)
        wrong_day = self.at('square', day=8)
        before = asdict(wrong_day)
        with self.assertRaises(GameError):
            journey.attend_festival(wrong_day)
        self.assertEqual(asdict(wrong_day), before)

    def test_journal_records_all_sites_and_each_project_next_requirements(self):
        farm = self.at('east_wood')
        journey.discover(farm)
        text = '\n'.join(journey.journal_lines(farm))
        self.assertIn('1/31', text)
        for site in journey.SITES.values():
            self.assertIn(site.name, text)
        for project in journey.PROJECTS.values():
            self.assertIn(project.name, text)


class JourneySaveTests(unittest.TestCase):
    def test_new_progress_round_trips_and_old_version_seven_gets_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'farm.json'
            farm = Farm(discovered={'east_wood': 1}, gathered_on={'east_wood': 1},
                        restoration={'greenhouse': 1},
                        dialogue_memory={'lan:greet': 'warm_try'},
                        festivals_on={'spring': 1})
            save_game(farm, path)
            self.assertEqual(asdict(load_game(path)), asdict(farm))
            document = json.loads(path.read_text())
            for key in ('discovered', 'gathered_on', 'restoration',
                        'dialogue_memory', 'festivals_on'):
                del document['farm'][key]
            document['farm']['items'] = {k: v for k, v in document['farm']['items'].items()
                                         if k not in journey.FORAGE_ITEMS}
            document['farm']['chest'] = {k: v for k, v in document['farm']['chest'].items()
                                         if k not in journey.FORAGE_ITEMS}
            path.write_text(json.dumps(document))
            restored = load_game(path)
            self.assertEqual(restored.discovered, {})
            self.assertEqual(restored.restoration, {})
            self.assertTrue(all(restored.items[key] == 0 for key in journey.FORAGE_ITEMS))

    def test_malformed_progress_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'farm.json'
            save_game(Farm(), path)
            original = json.loads(path.read_text())
            for key, value in [('discovered', {'missing': 1}),
                               ('discovered', {'east_wood': True}),
                               ('gathered_on', {'east_wood': 2}),
                               ('restoration', {'greenhouse': 4}),
                               ('dialogue_memory', {'lan:greet': 'unknown'}),
                               ('dialogue_memory', {'missing:greet': 'warm_try'}),
                               ('festivals_on', {'spring': -1})]:
                with self.subTest(field=key, value=value):
                    doc = deepcopy(original)
                    doc['farm'][key] = value
                    path.write_text(json.dumps(doc))
                    with self.assertRaises(SaveError):
                        load_game(path)
