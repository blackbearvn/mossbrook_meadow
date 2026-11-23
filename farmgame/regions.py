"""Named regions for the large connected village map.

The village is one continuous walkable map, but players think in places.  This
module gives every area a name, a short description and a safe fast-travel
point.  It is deliberately independent of curses so both frontends and tests
share the same geography.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class Region:
    key: str
    name: str
    icon: str
    ascii_icon: str
    description: str
    spawn: tuple[int, int]
    bounds: tuple[int, int, int, int] | None = None
    level: int = 1


# Ordered from the most specific rectangles to the broad roads/outskirts.
# Bounds are (left, top, right, bottom), inclusive, in village coordinates.
REGIONS = {
    'home': Region(
        'home', 'Trong nhà', '⌂', 'H',
        'Bếp, giường, tivi và rương đồ của bạn.',
        (8, 7), None),
    'farm': Region(
        'farm', 'Khu Sinh Sống', '⌂', 'H',
        'Nhà ở, chuồng, cửa hàng và lối vào ruộng.',
        (10, 7), (0, 0, 31, 16)),
    'meadow': Region(
        'meadow', 'Đồng Hoa', '✿', ',',
        'Thảm hoa quanh con suối, nơi ong bướm ghé thăm.',
        (39, 10), (32, 2, 48, 17)),
    'forest': Region(
        'forest', 'Rừng Thông', '♣', 'T',
        'Nhặt củi, nghe chim hót và gặp những lối mòn cũ.',
        (20, 25), (2, 17, 39, 34)),
    'square': Region(
        'square', 'Quảng Trường', '◆', 'O',
        'Tâm điểm của làng: gặp gỡ, trao đổi và nghe tin mới.',
        (55, 20), (49, 11, 68, 24)),
    'lake': Region(
        'lake', 'Hồ Sen · Ao Cá', '≈', '~',
        'Mặt nước phẳng lặng với bảy loài cá quý.',
        (53, 28), (40, 25, 73, 34)),
    'mine': Region(
        'mine', 'Cửa Mỏ', '◉', 'O',
        'Lối vào Mỏ Khoáng: đào quặng, rèn đồ và xuống Hang Sâu.',
        (76, 7), (75, 5, 77, 8)),
    'hill': Region(
        'hill', 'Đồi Gió', '^', '^',
        'Đỉnh đồi lộng gió, nhìn được toàn cảnh Mossbrook Meadow.',
        (72, 6), (69, 2, 80, 12)),
    'field': Region(
        'field', 'Ruộng Cánh Đồng', ':', ':',
        'Luống rau và ruộng lúa, trái tim của nông trại.',
        (27, 41), (22, 36, 36, 52)),
    'valley': Region(
        'valley', 'Thung Lũng Đông', 'v', 'v',
        'Đồng cỏ rộng, nơi đường làng uốn theo chân núi.',
        (96, 22), (82, 13, 105, 34)),
    'tea': Region(
        'tea', 'Đồi Trà', 't', 't',
        'Những luống trà xanh mướt trên sườn đồi phía đông.',
        (110, 10), (102, 2, 126, 17)),
    'floodplain': Region(
        'floodplain', 'Bãi Bồi', ';', ';',
        'Rặng lau và vũng nông trước khi ra tới biển.',
        (100, 50), (82, 43, 104, 63)),
    'beach': Region(
        'beach', 'Bãi Biển', '~', '~',
        'Bãi cát, rặng lau và tiếng sóng vỗ ngoài khơi xa.',
        (108, 50), (105, 43, 127, 63)),
}

REGION_ORDER = tuple(REGIONS)
TRAVEL_ORDER = tuple(key for key in REGION_ORDER if key != 'home')


def region_at(area: str, x: int, y: int) -> Region:
    """Return the named region containing a tile, with nearby fallbacks."""
    if area == 'home':
        return REGIONS['home']
    for key in REGION_ORDER:
        region = REGIONS[key]
        if region.bounds is None:
            continue
        left, top, right, bottom = region.bounds
        if left <= x <= right and top <= y <= bottom:
            return region
    return Region('road', 'Đường làng', '·', '.',
                  'Con đường nối các khu vực trong làng.', (10, 7))


def region_name(area: str, x: int, y: int) -> str:
    return region_at(area, x, y).name


def travel_regions(farm: 'Farm') -> list[Region]:
    """Regions shown in the fast-travel panel, including locked destinations."""
    return [REGIONS[key] for key in TRAVEL_ORDER]


def travel_cost(farm: 'Farm', region: Region) -> int:
    """Fast travel is free for now; this hook keeps the UI future-proof."""
    return 0


def can_travel(farm: 'Farm', region: Region | str) -> bool:
    region = REGIONS[region] if isinstance(region, str) else region
    return farm.level >= region.level


def travel(farm: 'Farm', key: str) -> str:
    """Move the player to a region's safe spawn without spending energy."""
    from .model import GameError
    from .world import walkable

    if key not in REGIONS:
        raise GameError('Khu vực không hợp lệ.')
    region = REGIONS[key]
    if not can_travel(farm, region):
        raise GameError(f'{region.name} mở ở cấp {region.level}.')
    x, y = region.spawn
    if not walkable('village', x, y, farm.size):
        raise GameError('Điểm đến đang bị chặn. Hãy thử lại sau.')
    farm.area = 'village'
    farm.player_x, farm.player_y = x, y
    farm.facing = 'down'
    return f'Đã đến {region.name}. {region.description}'


def travel_lines(farm: 'Farm', *, unicode: bool = True) -> list[str]:
    lines = []
    for region in travel_regions(farm):
        icon = region.icon if unicode else region.ascii_icon
        lock = '' if can_travel(farm, region) else f' · mở cấp {region.level}'
        lines.append(f'{icon} {region.name} · {region.description}{lock}')
    return lines
