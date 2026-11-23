"""Read-only terminal art for the world's existing logical map.

Every glyph and tail occupies one terminal cell. Renderers may join them for
two-column tiles, or use just the glyph when the terminal needs a tighter map.
"""

from __future__ import annotations

from dataclasses import dataclass
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
            if (not isinstance(char, str) or len(char) != 1
                    or not char.isprintable()
                    or unicodedata.category(char).startswith(('C', 'M'))
                    or unicodedata.east_asian_width(char) in 'WF'):
                raise ValueError('Map glyphs must occupy one printable terminal cell.')


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


def _line_cell(farm: Farm, x: int, y: int, *, unicode: bool,
               wall: bool = False) -> MapCell:
    grid = world.terrain_grid(farm.area, farm.size)
    height, width = len(grid), len(grid[0])
    mask = 0
    connections = '#D' if wall else '='
    for bit, dx, dy in ((1, 0, -1), (2, 1, 0), (4, 0, 1), (8, -1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] in connections:
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


def map_cell(farm: Farm, x: int, y: int, *, unicode: bool = True,
             path=frozenset()) -> MapCell:
    """Style a logical tile without progressing quests, crops, time, or RNG."""
    # Validate through the world before an actor or route can mask bad inputs.
    tile = world.tile_at(farm.area, x, y, farm.size)
    if (x, y) == (farm.player_x, farm.player_y):
        arrows = _ARROWS if unicode else _ASCII_ARROWS
        return MapCell(farm.avatar, farm.outfit, True, arrows.get(farm.facing, ' '))
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
    if tile == '=':
        return _line_cell(farm, x, y, unicode=unicode)
    if tile == '#':
        if farm.area == 'village':
            building = _building_cell(x, y, unicode=unicode)
            if building is not None:
                return building
        elif (farm.area == 'home' and 0 <= x < world.HOME_WIDTH
              and 0 <= y < world.HOME_HEIGHT):
            return _line_cell(farm, x, y, unicode=unicode, wall=True)
    if tile == 'T':
        if unicode:
            texture = (x * 13 + y * 7) % 23
            glyph = '♠' if texture == 0 else ('♤' if texture == 1 else '♣')
            return MapCell(glyph, 'forest', bold=glyph != '♣')
        # A stable mix of pines, broadleaf trees and saplings keeps the
        # ASCII forest readable without turning it into visual noise.
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
        # Coordinate texture is sparse and stable, without touching random state.
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
        # Keep every beach cell visible: a space would erase the golden
        # foreground colour and make the coast look like a gap in the map.
        return MapCell('·' if unicode else 's', 'sand')
    if tile in ('~', 'S'):
        # Lake and sea share wave shapes but get different semantic colours.
        texture = (x * 7 + y * 11) % 23
        wave = ('≋' if texture == 0 else '≈') if unicode else '~'
        return MapCell(wave, 'lake' if tile == '~' else 'sea', tail=wave)
    if farm.area == 'village' and tile in 'HMB':
        # Doors sit on the bottom edge of their buildings.  Joining them to the
        # wall keeps the house readable as one solid footprint.
        return MapCell(tile, _COLORS[tile], True,
                       tail='─' if unicode else '-')
    if farm.area == 'home' and tile == 'D':
        # The exit is a doorway in the bottom wall, not a hole in it.
        return MapCell('⇥' if unicode else 'D', 'cyan', True,
                       tail='─' if unicode else '-')
    return MapCell(terrain_glyph(tile, unicode=unicode), _COLORS.get(tile, 'green'))


def map_legend(farm: Farm, *, unicode: bool = True) -> list[str]:
    """One or two compact Vietnamese lines matching the active symbol palette."""
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
        f'{player} | 1-5 dân làng | H nhà  M tiệm  B chuồng | {guide} lối dẫn',
        f'{soil} đất  {seedling} mầm  {growing} lớn  {ripe} chín  {wilt} héo | '
        f'{tree} cây  {flower} hoa  {water} hồ/biển  {sand} cát | ~ ướt',
    ]
