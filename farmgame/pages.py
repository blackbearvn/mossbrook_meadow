"""Small connected map pages for the large village.

The world still uses one global coordinate space so farming, NPCs and saves
stay compatible.  When page mode is enabled, the camera is clipped to one
page and stepping over a page edge moves to the next map instead of showing
the whole 1280 x 720 world at once.  The original 128 x 64 village keeps its
old pages; the eastern and southern expansion is tiled by larger pages.
This module has no curses dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class Page:
    key: str
    name: str
    icon: str
    ascii_icon: str
    description: str
    bounds: tuple[int, int, int, int]  # left, top, right, bottom (inclusive)
    spawn: tuple[int, int]

    @property
    def width(self) -> int:
        return self.bounds[2] - self.bounds[0] + 1

    @property
    def height(self) -> int:
        return self.bounds[3] - self.bounds[1] + 1

    def contains(self, x: int, y: int) -> bool:
        left, top, right, bottom = self.bounds
        return left <= x <= right and top <= y <= bottom


# The original pages tile the 128 x 64 village without gaps.  Their
# boundaries follow the old roads (x=32/64/80, y=18/36) so walking out of one
# page naturally leads into the next one; the expansion pages below continue
# the grid across the wider 1280 x 720 world.
PAGES = {
    'residential': Page(
        'residential', 'Khu Sinh Sống', '⌂', 'H',
        'Nhà ở, cửa hàng, chuồng và khu vườn đầu làng.',
        (0, 0, 31, 17), (10, 7)),
    'meadow': Page(
        'meadow', 'Đồng Hoa', '✿', ',',
        'Thảm hoa và lối đi ven suối.',
        (32, 0, 63, 17), (39, 10)),
    'hill': Page(
        'hill', 'Đồi Gió', '^', '^',
        'Đỉnh đồi lộng gió nhìn xuống làng.',
        (64, 0, 79, 17), (72, 6)),
    'tea': Page(
        'tea', 'Đồi Trà', 't', 't',
        'Những luống trà xanh trên sườn đông.',
        (80, 0, 127, 17), (110, 10)),
    'forest': Page(
        'forest', 'Rừng Thông', '♣', 'T',
        'Rừng thông, lối mòn và tiếng chim.',
        (0, 18, 39, 35), (20, 25)),
    'square': Page(
        'square', 'Quảng Trường', '◆', 'O',
        'Quảng trường làng, nơi mọi người gặp nhau.',
        (40, 18, 79, 27), (55, 20)),
    'lake': Page(
        'lake', 'Hồ Sen · Ao Cá', '≈', '~',
        'Bờ hồ yên ả với bảy loài cá.',
        (40, 28, 79, 35), (53, 28)),
    'valley': Page(
        'valley', 'Thung Lũng Đông', 'v', 'v',
        'Đồng cỏ rộng dưới chân núi phía đông.',
        (80, 18, 127, 35), (96, 22)),
    'field': Page(
        'field', 'Ruộng Cánh Đồng', ':', ':',
        'Luống rau và ruộng lúa của nông trại.',
        (0, 36, 39, 63), (27, 41)),
    'floodplain': Page(
        'floodplain', 'Bãi Bồi', ';', ';',
        'Rặng lau và vũng nông trước cửa biển.',
        (40, 36, 104, 63), (55, 50)),
    'beach': Page(
        'beach', 'Bãi Biển', '~', '~',
        'Bãi cát, tiếng sóng và chân trời rộng.',
        (80, 36, 127, 63), (100, 50)),
}

# The expansion is split into pages whose borders sit on the generated road
# grid.  Every spawn is on a road so fast travel never strands the player.
EAST_PAGES = (
    Page('east_meadow', 'Đồng Cỏ Đông', '✿', ',',
         'Đồng cỏ rộng mở về phía đông của làng cũ.',
         (128, 0, 415, 63), (272, 55)),
    Page('east_wood', 'Rừng Đông', '♣', 'T',
         'Rừng thông non và những lối mòn mới.',
         (416, 0, 703, 63), (560, 55)),
    Page('east_lake', 'Hồ Lớn', '≈', '~',
         'Mặt hồ rộng phản chiếu bầu trời phía đông.',
         (704, 0, 991, 63), (848, 55)),
    Page('east_coast', 'Bờ Biển Đông', '~', '~',
         'Bãi cát dài và tiếng sóng ngoài khơi đông.',
         (992, 0, 1279, 63), (1136, 55)),
)
_SOUTH_NAMES = (
    ('Đồng Cỏ Nam', '✿', ','),
    ('Rừng Nam', '♣', 'T'),
    ('Thung Lũng Sương', 'v', 'v'),
    ('Cửa Biển Nam', '~', '~'),
    ('Đồi Đá', '^', '^'),
    ('Hồ Nước Sâu', '≈', '~'),
    ('Rừng Già', '♣', 'T'),
    ('Bãi Cát Vàng', '~', '~'),
    ('Cánh Đồng Xa', ':', ':'),
    ('Thác Nhỏ', '≈', '~'),
    ('Núi Mây', '^', '^'),
    ('Mũi Đá', '^', '^'),
    ('Đầm Lau', ';', ';'),
    ('Rừng Thấp', '♣', 'T'),
    ('Đồng Sương', ',', ','),
    ('Chân Trời', '.', '.'),
)
SOUTH_PAGES = []
for _row in range(4):
    _pages = []
    for _col in range(4):
        _name, _icon, _ascii = _SOUTH_NAMES[_row * 4 + _col]
        _left = _col * 320
        _top = 64 + _row * 164
        _pages.append(Page(
            f'south_{_row}_{_col}', _name, _icon, _ascii,
            f'Vùng đất phía nam: {_name.lower()}.',
            (_left, _top, _left + 319, _top + 163),
            (_left + 160, (146, 310, 474, 638)[_row])))
    SOUTH_PAGES.append(tuple(_pages))
LEGACY_PAGES = tuple(PAGES.values())
PAGES.update({page.key: page for page in EAST_PAGES})
PAGES.update({page.key: page for page in SOUTH_PAGES for page in page})
PAGE_ORDER = tuple(PAGES)
PAGE_BY_KEY = PAGES


def page_for_coord(x: int, y: int) -> Page | None:
    """Return the page containing a global village coordinate."""
    if type(x) is not int or type(y) is not int:
        return None
    if 0 <= x < 128 and 0 <= y < 64:
        for page in LEGACY_PAGES:
            if page.contains(x, y):
                return page
        return None
    if 128 <= x < 1280 and 0 <= y < 64:
        return EAST_PAGES[(x - 128) // 288]
    if 0 <= x < 1280 and 64 <= y < 720:
        return SOUTH_PAGES[(y - 64) // 164][x // 320]
    return None


def page_for_farm(farm: 'Farm') -> Page | None:
    """The active page, or None for legacy/full-map saves and indoor maps."""
    if not getattr(farm, 'map_pages', False) or farm.area != 'village':
        return None
    return page_for_coord(farm.player_x, farm.player_y)


def page_name(farm: 'Farm') -> str | None:
    page = page_for_farm(farm)
    return page.name if page is not None else None


def adjacent_page(farm: 'Farm', x: int, y: int) -> Page | None:
    """Page at a new coordinate, even when it differs from the current page."""
    if not getattr(farm, 'map_pages', False) or farm.area != 'village':
        return None
    return page_for_coord(x, y)


def travel_line(page: Page, *, unicode: bool = True) -> str:
    icon = page.icon if unicode else page.ascii_icon
    return f'{icon} {page.name} · {page.description}'
