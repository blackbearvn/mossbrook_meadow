"""Connected village and home maps with terminal-independent rules.

Coordinates are zero based. Doors and furniture are solid interaction targets;
only their orthogonal neighbours can use them. Fields remain walkable as the
farm expands, so every plot can always be reached.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Farm

# The playable village now spans a 1280 x 720 logical world.  The original
# 128 x 64 village keeps its layout in the north-west corner so retired plots,
# landmarks and old saves keep working; three edge gates join it to the open
# countryside, forests, lakes and long coast extending east and south.
VILLAGE_WIDTH = 1280
VILLAGE_HEIGHT = 720
LEGACY_WIDTH = 128
LEGACY_HEIGHT = 64
HOME_WIDTH = 16
HOME_HEIGHT = 9

# Roads cross the old map edge at these gates, joining the wider world.
EXPANSION_GATES = frozenset({(127, 55), (26, 63), (39, 63)})
SOUTH_PAGE_HEIGHT = 164
EAST_BOUNDARIES = (416, 704, 992)
SOUTH_BOUNDARIES = (320, 640, 960)
SOUTH_ROAD_ROWS = (146, 228, 310, 392, 474, 556, 638)

# The mine is a connected indoor map carved into Đồi Gió. Rocks are solid;
# the player mines one by standing on an orthogonal neighbour and pressing E.
MINE_WIDTH = 40
MINE_HEIGHT = 16
MINE_ENTRY = (2, 13)
MINE_BACK = (76, 7)
MINE_DOOR = (76, 6)
MINE_EXIT = (1, 14)
MINE_FORGE = (5, 14)
DUNGEON_GATE = (36, 3)
MINE_ROWS = (
    "########################################",
    "#......................................#",
    "#..R...R......RR......R....R....R......#",
    "#......................................#",
    "#.....R....R......R.......R....R.......#",
    "#......................................#",
    "#..R.......RR........R........R....R...#",
    "#......................................#",
    "#.....R........RR.........R....R.......#",
    "#......................................#",
    "#..R....R.........R.......R....R.......#",
    "#......................................#",
    "#....R.......R.........R.......R....R..#",
    "#......................................#",
    "#......................................#",
    "########################################",
)
MINE_ROCKS = frozenset(
    (x, y)
    for y, row in enumerate(MINE_ROWS)
    for x, tile in enumerate(row)
    if tile == 'R'
)
MINE_ROCK_NAMES = {
    'quang_dong': 'Quặng đồng',
    'quang_sat': 'Quặng sắt',
    'quang_vang': 'Quặng vàng',
    'kim_cuong': 'Tinh thể hang sâu',
}
HOME_DOOR = (4, 3)
BARN_DOOR = (15, 6)
SHOP_DOOR = (26, 3)
TV = (3, 2)
BED = (12, 2)
CHEST = (3, 5)
KITCHEN = (11, 5)
EXIT = (8, 8)
FIELD_ORIGIN = (26, 42)
LANDMARKS = {
    'farm': ('Cánh đồng', (27, 41)),
    'home': ('Nhà', HOME_DOOR),
    'shop': ('Cửa hàng', SHOP_DOOR),
    'barn': ('Chuồng', BARN_DOOR),
    'meadow': ('Đồng Hoa', (39, 10)),
    'square': ('Quảng trường', (55, 20)),
    'forest': ('Rừng Thông', (20, 25)),
    'lake': ('Hồ Sen', (53, 28)),
    'hill': ('Đồi Gió', (72, 6)),
    'valley': ('Thung Lũng Đông', (96, 22)),
    'tea': ('Đồi Trà', (110, 10)),
    'floodplain': ('Bãi Bồi', (100, 50)),
    'beach': ('Bãi Biển', (108, 50)),
    'mine': ('Mỏ Khoáng', (76, 6)),
}

_DIRECTIONS = {'up': (0, -1), 'down': (0, 1),
               'left': (-1, 0), 'right': (1, 0)}
_DIMENSIONS = {'village': (VILLAGE_WIDTH, VILLAGE_HEIGHT),
               'home': (HOME_WIDTH, HOME_HEIGHT),
               'mine': (MINE_WIDTH, MINE_HEIGHT)}
_OBJECTS = {
    'home': ('village', HOME_DOOR, 'H'),
    'barn': ('village', BARN_DOOR, 'B'),
    'shop': ('village', SHOP_DOOR, 'M'),
    'mine': ('village', MINE_DOOR, 'O'),
    'tv': ('home', TV, 'V'),
    'bed': ('home', BED, 'Z'),
    'chest': ('home', CHEST, 'C'),
    'kitchen': ('home', KITCHEN, 'K'),
    'exit': ('home', EXIT, 'D'),
    'mine_exit': ('mine', MINE_EXIT, 'D'),
    'forge': ('mine', MINE_FORGE, 'F'),
    'dungeon_gate': ('mine', DUNGEON_GATE, 'G'),
}
_LABELS = {
    'home': 'E: vào nhà', 'barn': 'E: chăm vật nuôi',
    'shop': 'E: mở cửa hàng', 'tv': 'E: xem dự báo thời tiết',
    'bed': 'E: ngủ sang ngày mới', 'chest': 'E: mở rương',
    'kitchen': 'E: nấu ăn', 'exit': 'E: ra làng',
    'mine': 'E: vào mỏ khoáng', 'mine_exit': 'E: ra khỏi mỏ',
    'forge': 'E: mở lò rèn', 'dungeon_gate': 'E: vào hang sâu',
    'fish': 'E: câu cá',
    'forest': 'E: giúp hàng xóm nhặt củi',
    'rock': 'E: đào khoáng sản',
    'none': 'WASD / mũi tên: đi bộ · R: khu vực · I: túi đồ · Q: lưu và về menu',
}


def _invalid(message: str) -> None:
    from .model import GameError
    raise GameError(message)


def _validate_size(size: int) -> None:
    if type(size) is not int or not 4 <= size <= 6:
        _invalid('Kích thước ruộng phải từ 4 đến 6.')


def _validate_tile(area: str, x: int, y: int, size: int) -> None:
    if area not in _DIMENSIONS:
        _invalid('Khu vực không hợp lệ.')
    if type(x) is not int or type(y) is not int:
        _invalid('Tọa độ phải là số nguyên.')
    _validate_size(size)


def _validate_farm(farm: 'Farm') -> None:
    _validate_tile(farm.area, farm.player_x, farm.player_y, farm.size)
    width, height = _DIMENSIONS[farm.area]
    if not (0 <= farm.player_x < width and 0 <= farm.player_y < height):
        _invalid('Vị trí người chơi nằm ngoài bản đồ.')
    if farm.facing not in _DIRECTIONS:
        _invalid('Hướng nhìn không hợp lệ.')


def plot_at(x: int, y: int, size: int) -> str | None:
    """Translate an active outdoor field tile to its farming coordinate."""
    _validate_tile('village', x, y, size)
    column, row = x - FIELD_ORIGIN[0], y - FIELD_ORIGIN[1]
    if 0 <= column < size and 0 <= row < size:
        return f'{chr(65 + column)}{row + 1}'
    return None


def tile_at(area: str, x: int, y: int, size: int = 4) -> str:
    """Return one map glyph; coordinates outside the map render as a wall."""
    _validate_tile(area, x, y, size)
    width, height = _DIMENSIONS[area]
    if not (0 <= x < width and 0 <= y < height):
        return '#'
    return _terrain_grid(area, size)[y][x]


def terrain_grid(area: str, size: int = 4) -> tuple[str, ...]:
    """Return immutable static map rows, shared by rendering and navigation."""
    _validate_tile(area, 0, 0, size)
    return _terrain_grid(area, size)


@lru_cache(maxsize=12)
def _terrain_grid(area: str, size: int) -> tuple[str, ...]:
    # Two outdoor sizes plus two indoor maps stay cached for the whole session.
    if area == 'village':
        return _village_grid(size)
    width, height = _DIMENSIONS[area]
    return tuple(''.join(_terrain_tile(area, x, y, size)
                         for x in range(width)) for y in range(height))


@lru_cache(maxsize=3)
def _legacy_core_grid(size: int) -> tuple[str, ...]:
    objects = {(x, y): glyph for area, (x, y), glyph in _OBJECTS.values()
               if area == 'village'}

    def tile(x: int, y: int) -> str:
        if (x, y) in EXPANSION_GATES:
            return '='
        return objects.get((x, y)) or _legacy_outdoor_tile(x, y, size)

    return tuple(''.join(tile(x, y) for x in range(LEGACY_WIDTH))
                 for y in range(LEGACY_HEIGHT))


@lru_cache(maxsize=1)
def _village_grid(size: int) -> tuple[str, ...]:
    expansion = _expansion_rows()
    return tuple(
        (_legacy_core_grid(size)[y] + expansion[y][LEGACY_WIDTH:]
         if y < LEGACY_HEIGHT else expansion[y])
        for y in range(VILLAGE_HEIGHT))


def _terrain_tile(area: str, x: int, y: int, size: int) -> str:
    """Compute one in-bounds glyph while constructing an already-validated map."""
    width, height = _DIMENSIONS[area]
    for object_area, point, glyph in _OBJECTS.values():
        if area == object_area and (x, y) == point:
            return glyph
    if area == 'mine':
        return MINE_ROWS[y][x]
    if area == 'home':
        if x in (0, width - 1) or y in (0, height - 1):
            return '#'
        # A small solid table leaves corridors on either side.
        if y == 3 and x in (7, 8):
            return '#'
        return '.'
    if (x, y) in EXPANSION_GATES:
        return '='
    if 0 <= x < LEGACY_WIDTH and 0 <= y < LEGACY_HEIGHT:
        return _legacy_outdoor_tile(x, y, size)
    return _expanded_outdoor_tile(x, y)


def _legacy_outdoor_tile(x: int, y: int, size: int) -> str:
    """The original 128 x 64 village, preserved exactly for old saves."""
    if x in (0, LEGACY_WIDTH - 1) or y in (0, LEGACY_HEIGHT - 1):
        return 'T'
    # A short bridge carries the old coast road to the eastern expansion gate.
    if y == 55 and 116 <= x < LEGACY_WIDTH:
        return '='
    if (FIELD_ORIGIN[0] <= x < FIELD_ORIGIN[0] + size
            and FIELD_ORIGIN[1] <= y < FIELD_ORIGIN[1] + size):
        return ':'
    if x < 32 and y < 14:
        return _original_village_tile(x, y)
    # Keep the old outer tree line, with gates onto the extended roads.
    if ((x == 79 and y < 36) or (y == 35 and x < 80)):
        if ((x == 79 and y in (7, 21, 32))
                or (y == 35 and x in (26, 39))):
            return '='
        return 'T'
    if x == 26 and 21 <= y <= 41:
        return '='
    if x < 80 and y < 36:
        return _countryside_tile(x, y)
    return _outer_countryside_tile(x, y)


def _expanded_outdoor_tile(x: int, y: int) -> str:
    """One cell of the wider countryside, backed by cached row strings."""
    return _expansion_row(y)[x]


_LAKES = ((780, 310, 150, 90), (245, 505, 110, 65), (480, 145, 120, 70))


@lru_cache(maxsize=1)
def _lake_ranges() -> dict[int, tuple[tuple[int, int], ...]]:
    ranges: dict[int, list[tuple[int, int]]] = {}
    for cx, cy, rx, ry in _LAKES:
        for y in range(cy - ry, cy + ry + 1):
            ratio = 1.0 - ((y - cy) / ry) ** 2
            if ratio < 0:
                continue
            half = int(rx * (ratio ** 0.5))
            if half > 0:
                ranges.setdefault(y, []).append((cx - half, cx + half))
    return {y: tuple(values) for y, values in ranges.items()}


@lru_cache(maxsize=720)
def _expansion_row(y: int) -> str:
    """Build one row in O(width) with cheap local branches."""
    width = VILLAGE_WIDTH
    if y in (0, VILLAGE_HEIGHT - 1):
        return 'T' * width
    if y == 55 or y in SOUTH_ROAD_ROWS:
        return 'T' + '=' * (width - 2) + 'T'
    band = (y - LEGACY_HEIGHT) // SOUTH_PAGE_HEIGHT
    if y < LEGACY_HEIGHT:
        row = [('T' if (x * 7 + y * 5) % 31 < 3 else
                ',' if (x * 13 + y * 3) % 23 == 0 else '.')
               for x in range(width)]
    elif band == 0:
        row = [',' if (x * 13 + y * 7) % 19 < 3 else '.' for x in range(width)]
    elif band == 1:
        row = ['T' if ((x // 5) * 13 + (y // 7) * 17) % 29 < 11 else '.'
               for x in range(width)]
    elif band == 2:
        row = ['T' if ((x // 7) * 11 + (y // 9) * 5) % 37 < 7 else
               ',' if (x + y * 3) % 21 == 0 else '.'
               for x in range(width)]
    else:
        row = ['T' if ((x // 6) * 7 + (y // 8) * 13) % 31 < 9 else ','
               for x in range(width)]
    # Lakes are precomputed per row so no exponentiation runs per cell.
    for left, right in _lake_ranges().get(y, ()):
        left, right = max(1, left), min(width - 2, right)
        if left <= right:
            row[left:right + 1] = ['~'] * (right - left + 1)
    coast = 1114 + (y * 17) % 82
    if coast < width - 1:
        row[coast:coast + 26] = ['s'] * max(0, min(26, width - 1 - coast))
        if coast + 26 < width - 1:
            row[coast + 26:width - 1] = ['S'] * (width - 1 - coast - 26)
    bay = 742 + (y * 11) % 118
    if y >= 646 and bay < width - 1:
        end = min(width - 1, bay + 24)
        row[bay:end] = ['s'] * (end - bay)
        if end < width - 1:
            row[end:width - 1] = ['S'] * (width - 1 - end)
    # Roads are laid last so they always form bridge crossings.
    if y >= LEGACY_HEIGHT:
        for x in (26, 39, *SOUTH_BOUNDARIES):
            row[x] = '='
    else:
        for x in EAST_BOUNDARIES:
            row[x] = '='
    row[0] = row[-1] = 'T'
    return ''.join(row)


@lru_cache(maxsize=1)
def _expansion_rows() -> tuple[str, ...]:
    return tuple(_expansion_row(y) for y in range(VILLAGE_HEIGHT))


def _original_village_tile(x: int, y: int) -> str:
    """Keep the village courtyard and the three original countryside gates."""
    if (x, y) in ((31, 7), (10, 13), (26, 13)):
        return '='
    if x == 31 or y == 13:
        return 'T'
    # House, barn and shop each open onto the connected village paths.
    if ((2 <= x <= 6 and 1 <= y <= 3)
            or (13 <= x <= 17 and 4 <= y <= 6)
            or (24 <= x <= 28 and 1 <= y <= 3)):
        return '#'
    if ((y == 8 and 24 <= x <= 28)
            or (9 <= y <= 11 and 22 <= x <= 29)):
        return '~'
    if ((10 <= y <= 12 and 17 <= x <= 20)
            or (y in (10, 11) and x in (2, 3))
            or (y == 1 and x in (13, 14, 18, 19))):
        return 'T'
    if (x == 10 or (y == 7 and 2 <= x <= 29)
            or (y == 3 and 7 <= x <= 23)
            or (x == 26 and 4 <= y <= 7)
            or (x == 7 and 2 <= y <= 4)
            or (y == 4 and 4 <= x <= 10)):
        return '='
    return '.'


def _countryside_tile(x: int, y: int) -> str:
    # Roads are tested before terrain so both river crossings form bridges.
    if ((y == 7 and 31 <= x <= 79)
            or (y == 21 and 10 <= x <= 79)
            or (x in (10, 26) and 13 <= y <= 21)
            or (x == 39 and 7 <= y <= 35)
            or (y == 25 and 10 <= x <= 39)
            or (x == 20 and 21 <= y <= 31)
            or (x in (50, 55, 68) and 13 <= y <= 23)
            or (y in (13, 23) and 50 <= x <= 68)
            or (x == 53 and 21 <= y <= 32)
            or (y == 32 and 49 <= x <= 79)
            or (x == 72 and 4 <= y <= 11)):
        return '='
    if 45 <= x <= 47 or (54 <= x <= 72 and 26 <= y <= 31):
        return '~'
    if 32 <= x <= 44 and 3 <= y <= 16:
        return ',' if (x + 2 * y) % 5 != 0 else '.'
    if 2 <= x <= 34 and 17 <= y <= 33:
        # Scattered pines leave generous glades on either side of the paths.
        return 'T' if (x * 7 + y * 11) % 9 < 5 else '.'
    if 49 <= x <= 68 and 12 <= y <= 23:
        # A flower border surrounds an open village square.
        if x in (49, 68) or y in (12, 23):
            return ','
        return '.'
    if 69 <= x <= 76 and 3 <= y <= 11:
        return 'T' if x in (69, 76) and y % 3 == 0 else ','
    return '.'


def _outer_countryside_tile(x: int, y: int) -> str:
    """Roads cross the streams before the surrounding terrain is drawn."""
    if ((y in (7, 21) and 79 <= x <= 121)
            or (y == 32 and 79 <= x <= 96)
            or (y == 41 and 26 <= x <= 116)
            or (y == 55 and 26 <= x <= 116)
            or (x == 26 and 35 <= y <= 55)
            or (x == 39 and 35 <= y <= 55)
            or (x == 96 and 21 <= y <= 41)
            or (x == 110 and 7 <= y <= 21)
            or (x == 100 and 41 <= y <= 55)
            or (x == 116 and 21 <= y <= 55)):
        return '='
    if 45 <= x <= 47 or 90 <= x <= 92:
        return '~'
    if 24 <= x <= 34 and 39 <= y <= 50:
        # Open grass around the largest field keeps every plot approachable.
        return '.'
    if 82 <= x <= 104 and 15 <= y <= 32:
        return ',' if (x + y) % 6 == 0 else '.'
    if 102 <= x <= 122 and 3 <= y <= 16:
        # Tea terraces leave broad walking lanes between rows of shrubs.
        return 'T' if y % 4 == 0 and x % 6 not in (0, 1) else ','
    if 105 <= x <= 126 and 36 <= y <= 63:
        # A broad golden beach and a wide blue sea open east of the reeds.
        # Roads and bridges were drawn before this branch, so the coast stays
        # reachable on foot.
        if x <= 111:
            return 's'
        return 'S'
    if 82 <= x <= 104 and 43 <= y <= 59:
        # Reed beds and shallow pools surround the floodplain's paths.
        return '~' if 91 <= x <= 97 and 47 <= y <= 52 else ','
    return '.'


def walkable(area: str, x: int, y: int, size: int = 4) -> bool:
    return tile_at(area, x, y, size) in ('.', ':', '=', ',', 's')


def page_step_allowed(area: str, size: int, x: int, y: int,
                      nx: int, ny: int, map_pages: bool) -> bool:
    """Mirror the opt-in page gate without importing pages at module load."""
    if not map_pages or area != 'village':
        return True
    from .pages import page_for_coord
    current = page_for_coord(x, y)
    target = page_for_coord(nx, ny)
    if current is None or target is None:
        return False
    if current.key == target.key:
        return True
    # Only roads may cross between map pages, matching manual movement.
    return (tile_at(area, x, y, size) == '='
            or tile_at(area, nx, ny, size) == '=')


def move(farm: 'Farm', direction: str) -> bool:
    """Turn even at obstacles; a successful step costs no energy or time.

    In page mode a walkable step over a page boundary enters the neighbouring
    page only where a road crosses the border.  Coordinates remain global, so
    plots, NPCs and old saves keep their existing positions while the frame
    can still show nearby parts of the wider world.
    """
    _validate_farm(farm)
    if direction not in _DIRECTIONS:
        _invalid('Hướng di chuyển không hợp lệ.')
    dx, dy = _DIRECTIONS[direction]
    farm.facing = direction
    x, y = farm.player_x + dx, farm.player_y + dy
    if not walkable(farm.area, x, y, farm.size):
        return False
    from .villagers import npc_at
    if npc_at(x, y, farm.area) is not None:
        return False
    # Page mode is deliberately opt-in for old saves: direct world helpers and
    # the legacy map keep their historical coordinates and behaviour.
    if not page_step_allowed(farm.area, farm.size, farm.player_x, farm.player_y,
                             x, y, getattr(farm, 'map_pages', False)):
        return False
    farm.player_x, farm.player_y = x, y
    return True


def target_plot(farm: 'Farm') -> str | None:
    _validate_farm(farm)
    if farm.area != 'village':
        return None
    dx, dy = _DIRECTIONS[farm.facing]
    return (plot_at(farm.player_x + dx, farm.player_y + dy, farm.size)
            or plot_at(farm.player_x, farm.player_y, farm.size))


def is_near(farm: 'Farm', kind: str) -> bool:
    """Interactions require one orthogonal step, regardless of facing."""
    _validate_farm(farm)
    if kind in _OBJECTS:
        area, (x, y), _ = _OBJECTS[kind]
        return (farm.area == area
                and abs(x - farm.player_x) + abs(y - farm.player_y) == 1)
    if kind not in ('water', 'forest'):
        _invalid('Điểm tương tác không hợp lệ.')
    if farm.area != 'village':
        return False
    glyph = '~' if kind == 'water' else 'T'
    return any(tile_at(farm.area, farm.player_x + dx, farm.player_y + dy,
                       farm.size) == glyph for dx, dy in _DIRECTIONS.values())


def target_rock(farm: 'Farm') -> tuple[int, int] | None:
    """Nearest mine rock, preferring the tile the farmer is facing."""
    if farm.area != 'mine':
        return None
    dx, dy = _DIRECTIONS.get(farm.facing, (0, 0))
    ahead = (farm.player_x + dx, farm.player_y + dy)
    if ahead in MINE_ROCKS:
        return ahead
    for ddx, ddy in _DIRECTIONS.values():
        point = (farm.player_x + ddx, farm.player_y + ddy)
        if point in MINE_ROCKS:
            return point
    return None


def mine_rock_kind(x: int, y: int) -> str:
    """Stable ore type for a rock; deeper eastern rocks are richer."""
    code = (x * 13 + y * 7) % 20
    if x >= 34 and code < 5:
        return 'kim_cuong'
    if x >= 28 and code < 8:
        return 'quang_vang'
    if x >= 17 and code < 10:
        return 'quang_sat'
    return 'quang_dong'


def context(farm: 'Farm') -> tuple[str, str]:
    """Resolve the most useful nearby action and a Vietnamese help label."""
    _validate_farm(farm)
    for kind in _OBJECTS:
        if is_near(farm, kind):
            return kind, _LABELS[kind]
    from .villagers import nearby_npc
    npc = nearby_npc(farm)
    if npc is not None:
        return 'npc', f'E: trò chuyện với {npc.name}'
    plot = target_plot(farm)
    if plot is not None:
        return 'plot', f'E: chăm ruộng {plot}'
    if farm.area == 'mine':
        rock = target_rock(farm)
        if rock is not None:
            return 'rock', _LABELS['rock']
    for kind, action in (('water', 'fish'), ('forest', 'forest')):
        if is_near(farm, kind):
            return action, _LABELS[action]
    return 'none', _LABELS['none']


def enter_home(farm: 'Farm') -> str:
    if not is_near(farm, 'home'):
        _invalid('Hãy đứng cạnh cửa nhà để vào.')
    farm.area, farm.player_x, farm.player_y = 'home', 8, 7
    farm.facing = 'up'
    return 'Bạn đã vào nhà. Giường, tivi và rương đang chờ!'


def leave_home(farm: 'Farm') -> str:
    if not is_near(farm, 'exit'):
        _invalid('Hãy đứng cạnh cửa ra để về làng.')
    farm.area, farm.player_x, farm.player_y = 'village', 4, 4
    farm.facing = 'down'
    return 'Bạn đã ra làng.'


def enter_mine(farm: 'Farm') -> str:
    if not is_near(farm, 'mine'):
        _invalid('Hãy đứng cạnh cửa mỏ khoáng để vào.')
    farm.area = 'mine'
    farm.player_x, farm.player_y = MINE_ENTRY
    farm.facing = 'up'
    return 'Bạn đã vào Mỏ Khoáng. Đứng cạnh đá và nhấn E để đào quặng.'


def leave_mine(farm: 'Farm') -> str:
    if not is_near(farm, 'mine_exit'):
        _invalid('Hãy đứng cạnh cửa mỏ để ra ngoài.')
    farm.area = 'village'
    farm.player_x, farm.player_y = MINE_BACK
    farm.facing = 'down'
    return 'Bạn đã ra khỏi mỏ, trở lại Đồi Gió.'


def location_name(farm: 'Farm') -> str:
    _validate_farm(farm)
    if farm.area == 'home':
        return 'Trong nhà'
    if farm.area == 'mine':
        if farm.player_x <= 10:
            region = 'Cửa Mỏ'
        elif farm.player_x >= 30:
            region = 'Vực Thẳm'
        else:
            region = 'Hầm Quặng'
        return f'Mỏ Khoáng / {region}'
    if 75 <= farm.player_x <= 77 and 5 <= farm.player_y <= 8:
        return 'Làng Mossbrook Meadow / Cửa Mỏ'
    if getattr(farm, 'map_pages', False):
        from .pages import page_for_coord
        page = page_for_coord(farm.player_x, farm.player_y)
        if page is not None:
            return page.name
    x, y = farm.player_x, farm.player_y
    if x >= LEGACY_WIDTH or y >= LEGACY_HEIGHT:
        from .regions import region_name
        return f'Làng Mossbrook Meadow / {region_name("village", x, y)}'
    if 24 <= x <= 34 and 39 <= y <= 50:
        region = 'Cánh đồng'
    elif 102 <= x <= 122 and 3 <= y <= 16:
        region = 'Đồi Trà'
    elif 82 <= x <= 104 and 15 <= y <= 32:
        region = 'Thung Lũng Đông'
    elif 105 <= x <= 127 and 43 <= y <= 63:
        region = 'Bãi Biển'
    elif 82 <= x <= 104 and 43 <= y <= 59:
        region = 'Bãi Bồi'
    elif x < 32 and y < 14:
        region = 'Nông trại'
    elif 32 <= x <= 44 and 3 <= y <= 16:
        region = 'Đồng Hoa'
    elif 2 <= x <= 34 and 17 <= y <= 33:
        region = 'Rừng Thông'
    elif 49 <= x <= 68 and 12 <= y <= 23:
        region = 'Quảng trường'
    elif 53 <= x <= 73 and 25 <= y <= 32:
        region = 'Hồ Sen'
    elif 69 <= x <= 76 and 3 <= y <= 11:
        region = 'Đồi Gió'
    elif 45 <= x <= 47:
        region = 'Suối'
    else:
        region = 'Đường làng'
    return f'Làng Mossbrook Meadow / {region}'
