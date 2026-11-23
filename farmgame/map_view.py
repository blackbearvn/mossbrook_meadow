"""Camera framing and compact status lines shared by terminal map views."""
from dataclasses import dataclass
import unicodedata

from . import world
from .catalog import WEATHER


@dataclass(frozen=True, slots=True)
class MapLayout:
    left: int
    top: int
    cols: int
    rows: int
    cell: int
    x: int
    y: int
    framed: bool


def objective_line(farm, width, *, unicode=True):
    """Merge the main goal and pending stat points into one calm HUD row."""
    from .tui import cells
    if farm.goal_complete:
        base = 'ĐÃ THÀNH CHỦ NÔNG TRẠI! Tiếp tục xây dựng ngôi làng nhé.'
    else:
        full = (f'Mục tiêu: {farm.harvested}/30 thu hoạch · '
                f'{farm.sales}/1.000 xu bán hàng · Cá: {farm.fish_caught}')
        short = (f'Mục tiêu: {farm.harvested}/30 · '
                 f'{farm.sales}/1k xu · Cá {farm.fish_caught}')
        base = full if width >= 60 and cells(full) <= width else short
    if not (farm.attribute_points or farm.skill_points):
        return base
    point_suffixes = (
        f' · C nâng: {farm.attribute_points} điểm thuộc tính / '
        f'{farm.skill_points} điểm tay nghề',
        f' · C: {farm.attribute_points} điểm TT / {farm.skill_points} TN',
        f' · C +{farm.attribute_points}TT/+{farm.skill_points}TN',
    )
    for suffix in point_suffixes:
        if cells(base + suffix) <= width:
            return base + suffix
    tiny = (f'Mục tiêu {farm.harvested}/30 · {farm.sales}/1k · '
            f'Cá {farm.fish_caught}')
    for suffix in point_suffixes:
        if cells(tiny + suffix) <= width:
            return tiny + suffix
    return tiny


MAX_MAP_CELLS = 1800


def map_layout(farm, width, height, *, reserved_rows=9, expanded=False):
    """Frame the camera; ``expanded`` swaps to narrow cells for a wide view."""
    from .explore import viewport
    cell_override = 1 if expanded else None
    if expanded:
        # Leave a title row, a status row and a context row above the frame,
        # plus one spare row below the bottom border so a final newline never
        # scrolls the terminal.
        reserved_rows = 4
    # Page mode still names the current area and gates walking across page
    # borders, but the camera fills the whole terminal frame.  Small legacy
    # pages used to shrink the frame to their own bounds, leaving wide unused
    # margins on a normal terminal.
    if farm.area == 'home':
        area_width, area_height = world.HOME_WIDTH, world.HOME_HEIGHT
    elif farm.area == 'mine':
        area_width, area_height = world.MINE_WIDTH, world.MINE_HEIGHT
    else:
        area_width, area_height = world.VILLAGE_WIDTH, world.VILLAGE_HEIGHT
    framed = width >= 30 and height >= 14
    if expanded:
        # Z is the full-terminal map: use every available row and column
        # (with only the frame border on tiny terminals removed).
        border = 2 if framed else 0
        cols = min(area_width, max(1, width - border))
        rows = min(area_height, max(1, height - border))
        left = max(0, min(farm.player_x - cols // 2, area_width - cols))
        top = max(0, min(farm.player_y - rows // 2, area_height - rows))
        full = (framed and cols == width - border
                and rows == height - border)
        x = 1 if full else max(0, (width - cols - border) // 2) + int(framed)
        y = 1 if full else max(0, (height - rows - border) // 2) + int(framed)
        return MapLayout(left, top, cols, rows, 1, x, y, framed)
    border = 2 if framed else 0
    left, top, cols, rows, cell = viewport(
        area_width, area_height, farm.player_x, farm.player_y,
        max(1, width - border),
        # viewport reserves nine rows for curses; text supplies its own HUD.
        max(1, height - border - reserved_rows) + 9,
        cell=cell_override)
    # A huge terminal can otherwise ask for tens of thousands of map cells;
    # each cell needs a glyph and colour lookup.  Keep the frame full-width but
    # cap its height so redraws stay smooth during held-key movement and auto.
    capped = cols * rows > MAX_MAP_CELLS
    if capped:
        rows = max(8, MAX_MAP_CELLS // max(1, cols))
        top = max(0, min(farm.player_y - rows // 2, area_height - rows))
    x = max(0, (width - cols * cell - border) // 2) + int(framed)
    y = 3 + int(framed)
    if capped:
        footer_top = max(y, height - 6)
        y = max(y, y + max(0, footer_top - y - rows) // 2)
    return MapLayout(left, top, cols, rows, cell, x, y, framed)


def cells(text):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in 'WF' else 1
               for char in text)


def frame_lines(layout, area, *, unicode=True, page_name=None, footer=None):
    from .explore import fit_text
    width = layout.cols * layout.cell
    name = (page_name or {'mine': 'MỎ KHOÁNG', 'home': 'NHÀ'}.get(area, 'LÀNG'))
    title = f' {name} · X{layout.left}–{layout.left + layout.cols - 1} Y{layout.top}–{layout.top + layout.rows - 1} '
    if not unicode:
        plain_name = (page_name or {'mine': 'MINE', 'home': 'HOME'}.get(area, 'MAP'))
        title = f' {plain_name} X{layout.left}:{layout.left + layout.cols - 1} Y{layout.top}:{layout.top + layout.rows - 1} '
    title = fit_text(title, max(0, width - 2))
    tl, tr, bl, br, horizontal, vertical = (('╭', '╮', '╰', '╯', '─', '│')
                                           if unicode else ('+', '+', '+', '+', '-', '|'))
    bottom = bl + horizontal * width + br
    if footer:
        label = fit_text(f' {footer} ', max(0, width - 2))
        bottom = (bl + horizontal + label
                  + horizontal * max(0, width - 1 - cells(label)) + br)
    return (tl + horizontal + title + horizontal * max(0, width - 1 - cells(title)) + tr,
            bottom, vertical)


def status_line(farm, width, *, unicode=True):
    """A status line that keeps the essentials readable in narrow windows."""
    from .artwork import symbol, weather_icon
    weather = weather_icon(farm.weather, unicode=unicode)
    coin = symbol("coin", unicode=unicode)
    heart = symbol("heart", unicode=unicode)
    if width < 42:
        base = (f'Ngày {farm.day} · {farm.coins} xu · '
                f'Sức {farm.energy}/{farm.energy_limit}')
        hp = f' · M{farm.hp}/{farm.max_hp}'
        return base + hp if cells(base + hp) <= width else base
    if width < 60:
        return (f'{weather} Ngày {farm.day} · {coin} {farm.coins} xu · '
                f'{heart} Sức {farm.energy}/{farm.energy_limit}')
    base = (f'{weather} Ngày {farm.day} · '
            f'{WEATHER[farm.weather]} · '
            f'{coin} {farm.coins} xu · '
            f'{heart} Sức {farm.energy}/{farm.energy_limit}')
    if cells(base) > width:
        return (f'{weather} Ngày {farm.day} · {coin} {farm.coins} xu · '
                f'{heart} Sức {farm.energy}/{farm.energy_limit}')
    if width >= 68:
        size = 6
        filled = min(size, max(0, farm.energy * size // farm.energy_limit))
        full, empty = ('▰', '▱') if unicode else ('#', '-')
        base += f' [{full * filled}{empty * (size - filled)}]'
    hp = (f' · Máu {farm.hp}/{farm.max_hp}' if unicode
          else f' · HP {farm.hp}/{farm.max_hp}')
    if width >= 50 and width >= cells(base + hp):
        base += hp
    level = (f' · {symbol("chart", unicode=unicode)} Cấp {farm.level}'
             f' XP {farm.xp % 40}/40')
    if width >= cells(base + level):
        base += level
    else:
        compact_level = f' · C{farm.level}'
        if width >= cells(base + compact_level):
            base += compact_level
    return base
