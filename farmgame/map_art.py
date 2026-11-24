"""Read-only terminal art for the world's existing logical map.

Every glyph and tail occupies one terminal cell. Renderers may join them for
two-column tiles, or use just the glyph when the terminal needs a tighter map.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
import sys
from typing import TYPE_CHECKING
import unicodedata

from . import world
from .villagers import npc_at

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class MapCell:
    glyph: str
    color: str = 'green'
    bold: bool = False
    tail: str = ' '

    def __post_init__(self) -> None:
        for char in (self.glyph, self.tail):
            if not isinstance(char, str) or not _valid_cell_char(char):
                raise ValueError('Map glyphs must occupy one printable terminal cell.')


@lru_cache(maxsize=512)
def _valid_cell_char(char: object) -> bool:
    return (isinstance(char, str) and len(char) == 1
            and char.isprintable()
            and not unicodedata.category(char).startswith(('C', 'M'))
            and unicodedata.east_asian_width(char) not in 'WF')


_ARROWS = {'up': '↑', 'down': '↓', 'left': '←', 'right': '→'}
_ASCII_ARROWS = {'up': '^', 'down': 'v', 'left': '<', 'right': '>'}
_TERRAIN = {
    '.': '.', 'T': '♣', '~': '≈', 'S': '≈', 's': '·', ',': '✿',
    ':': '░', '=': '─', '#': '▒', 'V': '▣', 'Z': '▰', 'C': '▤',
    'K': '⚙', 'D': '⇥', 'O': '◉', 'R': '◆', 'F': '⚒', 'G': '☠',
}
# Every outdoor terrain cell gets a semantic role, not an ad-hoc colour.
# The terminal palette maps these roles to 256-colour values when available
# and to the basic eight colours otherwise.  In particular:
#   sand/beach = golden, lake = light green, sea = deep blue.
MAP_COLORS = {
    '.': 'grass',
    'T': 'forest',
    '~': 'lake',
    'S': 'sea',
    's': 'sand',
    ',': 'flower',
    ':': 'soil',
    '=': 'path',
    '#': 'stone',
    'H': 'building',
    'M': 'building',
    'B': 'building',
    'V': 'furniture',
    'Z': 'furniture',
    'C': 'furniture',
    'K': 'furniture',
    'D': 'door',
    'O': 'building',
    'R': 'stone',
    'F': 'furniture',
    'G': 'magenta',
}
_COLORS = dict(MAP_COLORS)
# Connection bits, clockwise from north: 1, 2, 4, 8.
_LINES = ('─', '│', '─', '└', '│', '│', '┌', '├',
          '─', '┘', '─', '┴', '┐', '┤', '┬', '┼')
_BUILDINGS = ((2, 1, 6, 3), (24, 1, 28, 3), (13, 4, 17, 6))
_ASCII_ART = {'╱': '/', '╲': '\\', '─': '-', '│': '|',
              '└': '+', '┘': '+', '▣': 'o'}
_UNICODE_PALETTE = (''.join(_TERRAIN.values()) + ''.join(_ARROWS.values())
                    + ''.join(_LINES) + '╱╲╵♠✦×·╭╮╰╯▱')


def supports_unicode(stream=None, term=None) -> bool:
    """Check whether the output encoding can carry the complete map palette."""
    if term is None:
        term = os.environ.get('TERM', '')
    if str(term).strip().lower() == 'dumb':
        return False
    if stream is None:
        stream = sys.stdout
    encoding = getattr(stream, 'encoding', None)
    if not encoding:
        return False
    try:
        _UNICODE_PALETTE.encode(encoding)
    except (UnicodeEncodeError, LookupError, TypeError):
        return False
    return True


def terrain_glyph(tile: str, *, unicode: bool = True) -> str:
    """Translate overview terrain while preserving landmark and actor markers."""
    return _TERRAIN.get(tile, tile) if unicode else tile


def _line_cell(area: str, size: int, x: int, y: int, *, unicode: bool,
               wall: bool = False) -> MapCell:
    width, height = world.dimensions(area)
    row = world.terrain_row(area, y, size)
    mask = 0
    connections = '#D' if wall else '='
    for bit, dx, dy in ((1, 0, -1), (2, 1, 0), (4, 0, 1), (8, -1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            glyph = row[nx] if ny == y else world.terrain_row(area, ny, size)[nx]
            if glyph in connections:
                mask |= bit
    if unicode:
        glyph = _LINES[mask]
        tail = '─' if mask & 2 else ' '
    else:
        horizontal, vertical = bool(mask & 10), bool(mask & 5)
        glyph = '+' if horizontal and vertical else ('|' if vertical else '-')
        tail = '-' if mask & 2 else ' '
    return MapCell(glyph, 'stone' if wall else 'path', tail=tail)


def _building_cell(x: int, y: int, *, unicode: bool) -> MapCell | None:
    for left, top, right, bottom in _BUILDINGS:
        if not (left <= x <= right and top <= y <= bottom):
            continue
        color, tail = 'stone', ' '
        if y == top:
            glyph = '╱' if x == left else ('╲' if x == right else '─')
            color, tail = 'roof', '─' if x < right else ' '
        elif y == bottom:
            glyph = '└' if x == left else ('┘' if x == right else '─')
            tail = '─' if x < right else ' '
        elif x in (left, right):
            glyph = '│'
        elif x in (left + 1, right - 1):
            glyph, color = '▣', 'furniture'
        else:
            glyph = ' '
        if not unicode:
            glyph = _ASCII_ART.get(glyph, glyph)
            tail = '-' if tail == '─' else tail
        return MapCell(glyph, color, tail=tail)
    return None


def _nature_cell(x: int, y: int, tile: str, unicode: bool,
                 phase: int) -> MapCell:
    """Living art for water and flower tiles.

    Phase 0 matches ``_static_cell`` exactly; later phases drift the wave
    crest across lakes and the sea and cycle the flower blooms in place.
    """
    if tile == ',':
        texture = (x * 11 + y * 17 + phase) % 13
        if unicode:
            glyph = '❀' if texture == 0 else ('✾' if texture == 1 else '✿')
            return MapCell(glyph, 'flower', bold=texture < 2)
        glyph = '%' if texture == 0 else ('*' if texture == 4 else ',')
        return MapCell(glyph, 'flower', bold=glyph != ',')
    texture = (x * 7 + y * 11 + phase * 7) % 23
    wave = ('≋' if texture == 0 else '≈') if unicode else '~'
    return MapCell(wave, 'lake' if tile == '~' else 'sea', tail=wave)


@lru_cache(maxsize=4096)
def _static_cell(area: str, size: int, unicode: bool, x: int, y: int,
                 tile: str) -> MapCell:
    """Cache terrain art that does not depend on changing farm state."""
    if tile == '=':
        return _line_cell(area, size, x, y, unicode=unicode)
    if tile == '#':
        if area == 'village':
            building = _building_cell(x, y, unicode=unicode)
            if building is not None:
                return building
        elif area == 'home' and 0 <= x < world.HOME_WIDTH and 0 <= y < world.HOME_HEIGHT:
            return _line_cell(area, size, x, y, unicode=unicode, wall=True)
    if tile == 'T':
        if unicode:
            texture = (x * 13 + y * 7) % 23
            glyph = '♠' if texture == 0 else ('♤' if texture == 1 else '♣')
            return MapCell(glyph, 'forest', bold=glyph != '♣')
        texture = (x * 13 + y * 7) % 19
        glyph = 'Y' if texture == 0 else ('t' if texture == 1 else 'T')
        return MapCell(glyph, 'forest', bold=glyph == 'Y')
    if tile == ',':
        texture = (x * 11 + y * 17) % 13
        if unicode:
            glyph = '❀' if texture == 0 else ('✾' if texture == 1 else '✿')
            return MapCell(glyph, 'flower', bold=texture < 2)
        glyph = '%' if texture == 0 else ('*' if texture == 4 else ',')
        return MapCell(glyph, 'flower', bold=glyph != ',')
    if tile == '.':
        texture = (x * 17 + y * 31) % 29
        if texture < 2:
            glyph = '.'
        elif texture == 2:
            glyph = '`'
        elif texture == 3:
            glyph = '"'
        elif texture == 4:
            glyph = "'"
        elif texture == 5:
            glyph = ';'
        else:
            glyph = ' '
        return MapCell(glyph, 'grass')
    if tile == 's':
        return MapCell('·' if unicode else 's', 'sand')
    if tile in ('~', 'S'):
        texture = (x * 7 + y * 11) % 23
        wave = ('≋' if texture == 0 else '≈') if unicode else '~'
        return MapCell(wave, 'lake' if tile == '~' else 'sea', tail=wave)
    if area == 'village' and tile in 'HMB':
        return MapCell(tile, _COLORS[tile], True,
                       tail='─' if unicode else '-')
    if area == 'home' and tile == 'D':
        return MapCell('⇥' if unicode else 'D', 'cyan', True,
                       tail='─' if unicode else '-')
    return MapCell(terrain_glyph(tile, unicode=unicode), _COLORS.get(tile, 'green'))


def map_cell(farm: Farm, x: int, y: int, *, unicode: bool = True,
             path=frozenset(), tile: str | None = None,
             phase: int = 0) -> MapCell:
    """Style a logical tile without progressing quests, crops, time, or RNG.

    The renderer can pass an already-validated ``tile`` from a cached terrain
    grid, which avoids repeating coordinate validation for every visible cell.
    ``phase`` steps the living nature art (drifting waves, blooming flowers);
    phase 0 reproduces the static art exactly, keeping renders repeatable.
    """
    if tile is None:
        # Validate through the world before an actor or route can mask bad inputs.
        tile = world.tile_at(farm.area, x, y, farm.size)
    if (x, y) == (farm.player_x, farm.player_y):
        arrows = _ARROWS if unicode else _ASCII_ARROWS
        return MapCell(farm.avatar, farm.outfit, True, arrows.get(farm.facing, ' '))
    if farm.area == 'village':
        npc = npc_at(x, y, farm.area)
        if npc is not None:
            return MapCell(npc.glyph, 'magenta', True)
    if farm.area == 'village' and tile == ':':
        coordinate = world.plot_at(x, y, farm.size)
        plot = farm.plots[coordinate]
        if plot.dead:
            return MapCell('×' if unicode else 'x', 'red')
        if plot.ready:
            return MapCell('✦' if unicode else '*', 'yellow', True)
        watered = farm.is_watered(coordinate)
        tail = '~' if watered else ' '
        if plot.crop:
            # ASCII 't' reads as a young plant; '+' is reserved for guidance.
            glyph = ('♠' if unicode else 't') if plot.growth else ('╵' if unicode else "'")
            return MapCell(glyph, 'cyan' if watered else 'green', tail=tail)
        return MapCell('░' if unicode else ':', 'cyan' if watered else 'yellow',
                       tail=tail)
    if (x, y) in path and tile in ('.', '=', ',', ':'):
        return MapCell('·' if unicode else '+', 'yellow', True)
    if phase and farm.area == 'village' and tile in (',', '~', 'S'):
        return _nature_cell(x, y, tile, unicode, phase)
    if farm.area == 'mine' and tile == 'R':
        from .mining import rock_exhausted
        from . import world as mine_world
        if rock_exhausted(farm, x, y):
            return MapCell('·' if unicode else '.', 'stone')
        kind = mine_world.mine_rock_kind(x, y)
        color = {'quang_dong': 'soil', 'quang_sat': 'stone',
                 'quang_vang': 'sand', 'kim_cuong': 'flower'}[kind]
        glyph = ('✦' if kind == 'kim_cuong' else '◆') if unicode else '*'
        return MapCell(glyph, color, bold=kind in ('quang_vang', 'kim_cuong'))
    return _static_cell(farm.area, farm.size, unicode, x, y, tile)

def map_legend(farm: Farm, *, unicode: bool = True) -> list[str]:
    """One or two compact Vietnamese lines matching the active symbol palette."""
    from .villagers import NPCS
    arrow = (_ARROWS if unicode else _ASCII_ARROWS).get(farm.facing, ' ')
    player = f'{farm.avatar}{arrow} bạn'
    guide = '·' if unicode else '+'
    if farm.area == 'home':
        tv, bed, chest, kitchen, exit = (('▣', '▰', '▤', '⚙', '⇥')
                                         if unicode else ('V', 'Z', 'C', 'K', 'D'))
        return [f'{player} | {tv} tivi  {bed} giường  {chest} rương  '
                f'{kitchen} bếp  {exit} ra làng | {guide} lối dẫn']
    if farm.area == 'mine':
        from .mining import mine_summary
        available, total = mine_summary(farm)
        forge, gate, exit = (('⚒', '☠', '⇥') if unicode else ('F', 'G', 'D'))
        rock = '◆' if unicode else '*'
        return [f'{player} | {forge} lò rèn  {gate} hang sâu  {exit} ra mỏ | '
                f'{rock} đá {available}/{total} tảng còn quặng',
                f'Đứng cạnh đá rồi nhấn E để đào; ngủ để mỏ hồi đầy. {guide} lối dẫn']
    soil, seedling, growing, ripe, wilt = (('░', '╵', '♠', '✦', '×') if unicode
                                          else (':', "'", 't', '*', 'x'))
    if unicode:
        tree, flower, water, sand = '♣♠', '✿❀', '≈', '·'
    else:
        tree, flower, water, sand = 'T/Y', ',/*', '~', 's'
    return [
        f'{player} | {len(NPCS)} dân làng | H nhà  M tiệm  B chuồng | {guide} lối dẫn',
        f'{soil} đất  {seedling} mầm  {growing} lớn  {ripe} chín  {wilt} héo | '
        f'{tree} cây  {flower} hoa  {water} hồ/biển  {sand} cát | ~ ướt',
    ]
