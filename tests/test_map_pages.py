"""Page mode clips the camera to one map and transitions across its edge."""

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from farmgame import pages, world
from farmgame.map_view import map_layout
from farmgame.model import Farm
from farmgame.storage import load_game, save_game


class MapPageTests(unittest.TestCase):
    def test_pages_tile_the_whole_village_and_names_are_unique(self):
        for y in range(world.VILLAGE_HEIGHT):
            for x in range(world.VILLAGE_WIDTH):
                self.assertIsNotNone(pages.page_for_coord(x, y), (x, y))
        self.assertEqual(len({page.name for page in pages.PAGES.values()}),
                         len(pages.PAGES))
        for page in pages.PAGES.values():
            self.assertTrue(page.contains(*page.spawn))
            self.assertGreaterEqual(page.width, 1)
            self.assertGreaterEqual(page.height, 1)

    def test_camera_is_clipped_to_the_current_page(self):
        farm = Farm(map_pages=True, player_x=30, player_y=7)
        layout = map_layout(farm, 80, 24)
        page = pages.page_for_coord(30, 7)
        self.assertEqual(layout.left, page.bounds[0])
        self.assertLessEqual(layout.cols, page.width)
        self.assertLessEqual(layout.rows, page.height)
        self.assertEqual(world.location_name(farm), 'Khu Sinh Sống')

        farm.player_x, farm.player_y = 55, 20
        layout = map_layout(farm, 80, 24)
        self.assertGreaterEqual(layout.left, 40)
        self.assertLessEqual(layout.left + layout.cols - 1, 79)

    def test_walking_over_a_page_edge_enters_the_next_map(self):
        farm = Farm(map_pages=True, player_x=31, player_y=7)
        self.assertEqual(world.location_name(farm), 'Khu Sinh Sống')
        self.assertTrue(world.move(farm, 'right'))
        self.assertEqual((farm.area, farm.player_x, farm.player_y), ('village', 32, 7))
        self.assertEqual(world.location_name(farm), 'Đồng Hoa')
        self.assertEqual(pages.page_name(farm), 'Đồng Hoa')

        # Grass edges stop the player; only road crossings lead to another page.
        blocked = Farm(map_pages=True, player_x=31, player_y=14)
        self.assertFalse(world.move(blocked, 'right'))
        self.assertEqual((blocked.player_x, blocked.player_y), (31, 14))
        self.assertEqual(world.location_name(blocked), 'Khu Sinh Sống')

    def test_expansion_gates_open_onto_the_wider_world(self):
        east = Farm(map_pages=True, player_x=126, player_y=55)
        self.assertTrue(world.move(east, 'right'))
        self.assertEqual((east.player_x, east.player_y), (127, 55))
        self.assertTrue(world.move(east, 'right'))
        self.assertEqual((east.player_x, east.player_y), (128, 55))
        self.assertEqual(pages.page_name(east), 'Đồng Cỏ Đông')

        south = Farm(map_pages=True, player_x=26, player_y=62)
        self.assertTrue(world.move(south, 'down'))
        self.assertEqual((south.player_x, south.player_y), (26, 63))
        self.assertTrue(world.move(south, 'down'))
        self.assertEqual((south.player_x, south.player_y), (26, 64))
        self.assertEqual(pages.page_name(south), 'Đồng Cỏ Nam')

    def test_field_and_beach_pages_keep_their_landmarks(self):
        field = Farm(map_pages=True, player_x=26, player_y=42)
        self.assertEqual(world.location_name(field), 'Ruộng Cánh Đồng')
        self.assertEqual(world.target_plot(field), 'A2')
        self.assertEqual(pages.page_for_coord(108, 50).name, 'Bãi Biển')
        beach = Farm(map_pages=True, player_x=108, player_y=50)
        self.assertEqual(world.location_name(beach), 'Bãi Biển')

    def test_page_mode_survives_save_and_load(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'farm.json'
            farm = Farm(map_pages=True, player_x=55, player_y=20)
            save_game(farm, path)
            restored = load_game(path)
            self.assertTrue(restored.map_pages)
            self.assertEqual(asdict(restored), asdict(farm))
            self.assertEqual(world.location_name(restored), 'Quảng Trường')


if __name__ == '__main__':
    unittest.main()
