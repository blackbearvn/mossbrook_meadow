"""Shortest actionable routes shared by the tutorial and automation.

Paths contain successful orthogonal moves, excluding the current position.
An empty path with ``E`` is ready; an empty path with ``M`` is unreachable.
Facing is part of the search state because field actions prefer the tile ahead.
"""
from functools import lru_cache
from heapq import heappop, heappush
from itertools import count
from types import SimpleNamespace
from typing import TYPE_CHECKING

from . import villagers, world

if TYPE_CHECKING:
    from .model import Farm

Point = tuple[int, int]
State = tuple[int, int, str]
Route = tuple[Point, tuple[Point, ...], str]
_DIRECTIONS = ((0, -1, 'up'), (0, 1, 'down'),
               (-1, 0, 'left'), (1, 0, 'right'))
_KEYS = {(0, -1): 'W / ↑', (0, 1): 'S / ↓',
         (-1, 0): 'A / ←', (1, 0): 'D / →'}
_KINDS = frozenset(('', 'plot', 'tile', 'water', 'forest', 'npc',
                    'home', 'barn', 'shop', 'tv', 'bed', 'chest', 'exit',
                    'kitchen', 'mine', 'mine_exit', 'rock', 'forge',
                    'dungeon_gate'))


def route(farm: 'Farm', target_area: str, target: Point, *, kind: str = '') -> Route:
    """Plan in the current area, stopping at a door for an area transition.

    ``plot`` selects the exact plot with the final facing; ``tile`` reaches the
    point itself. ``water`` and ``forest`` require a usable context beside that
    terrain tile. Other targets use ordinary orthogonal adjacency.
    """
    world._validate_farm(farm)
    if (not isinstance(target, tuple) or len(target) != 2
            or type(target[0]) is not int or type(target[1]) is not int):
        world._invalid('Đích đến phải là một cặp tọa độ nguyên.')
    if not isinstance(target_area, str) or target_area not in world._DIMENSIONS:
        world._invalid('Khu vực không hợp lệ.')
    if not isinstance(kind, str) or kind not in _KINDS:
        world._invalid('Loại đích đến không hợp lệ.')
    if farm.area != target_area:
        if farm.area == 'home':
            kind, target = 'exit', world.EXIT
        elif farm.area == 'mine':
            kind, target = 'mine_exit', world.MINE_EXIT
        elif target_area == 'mine':
            kind, target = 'mine', world.MINE_DOOR
        elif target_area == 'home':
            kind, target = 'home', world.HOME_DOOR
        else:
            kind, target = 'home', world.HOME_DOOR
    # Include NPC positions so a changed obstacle layout cannot reuse old paths.
    blockers = tuple(npc.position for npc in villagers.NPCS.values()) if farm.area == 'village' else ()
    return _navigate(farm.area, farm.size, farm.player_x, farm.player_y,
                     farm.facing, target, kind, blockers)


@lru_cache(maxsize=256)
def _goal_states(area: str, size: int, target: Point, kind: str,
                 blockers: tuple[Point, ...]) -> frozenset[State]:
    width, height = world.dimensions(area)
    tile = world.tile_at
    tx, ty = target
    if not (0 <= tx < width and 0 <= ty < height):
        return frozenset()
    if kind == 'plot' and (area != 'village' or world.plot_at(tx, ty, size) is None):
        return frozenset()
    if kind in ('forest', 'water'):
        glyph = 'T' if kind == 'forest' else '~'
        if area != 'village' or tile(area, tx, ty, size) != glyph:
            return frozenset()
    if kind == 'rock' and (area != 'mine' or (tx, ty) not in world.MINE_ROCKS):
        return frozenset()
    points = ((tx, ty),) if kind == 'tile' else tuple(
        (tx + dx, ty + dy) for dx, dy, _ in _DIRECTIONS)
    if kind == 'plot':
        points += ((tx, ty),)
    probe = SimpleNamespace(area=area, size=size)
    goals = set()
    for x, y in points:
        if not (0 <= x < width and 0 <= y < height
                and tile(area, x, y, size) in '.:=,' and (x, y) not in blockers):
            continue
        for _, _, facing in _DIRECTIONS:
            if kind in ('plot', 'forest', 'water', 'rock'):
                probe.player_x, probe.player_y, probe.facing = x, y, facing
                if kind == 'rock':
                    if (world.target_rock(probe) != (tx, ty)
                            or world.context(probe)[0] != 'rock'):
                        continue
                    action = 'rock'
                elif kind == 'plot':
                    if world.target_plot(probe) != world.plot_at(tx, ty, size):
                        continue
                    action = 'plot'
                else:
                    action = 'fish' if kind == 'water' else 'forest'
                if world.context(probe)[0] != action:
                    continue
            goals.add((x, y, facing))
    return frozenset(goals)


@lru_cache(maxsize=512)
def _navigate(area: str, size: int, player_x: int, player_y: int,
              facing: str, target: Point, kind: str,
              blockers: tuple[Point, ...]) -> Route:
    goals = _goal_states(area, size, target, kind, blockers)
    if not goals:
        return target, (), 'M'
    # Furniture, NPC adjacency and exact-tile goals do not depend on heading.
    # Merge their four equivalent states instead of searching each arrival.
    track_facing = kind in ('plot', 'forest', 'water', 'rock')
    if not track_facing:
        facing = ''
        goals = frozenset((x, y, '') for x, y, _ in goals)
    start = player_x, player_y, facing
    if start in goals:
        return target, (), 'E'
    width, height = world.dimensions(area)
    blocked = frozenset(blockers)
    tx, ty = target
    # Actionable goals are at most one step from the target. This Manhattan
    # lower bound stays admissible even when final facing requires a detour.
    radius = 0 if kind == 'tile' else 1

    def heuristic(x: int, y: int) -> int:
        return max(0, abs(x - tx) + abs(y - ty) - radius)

    serial = count()
    initial_h = heuristic(player_x, player_y)
    queue = [(initial_h, initial_h, next(serial), 0, start)]
    costs = {start: 0}
    previous = {}
    found = None
    while queue:
        _, _, _, cost, point = heappop(queue)
        if cost != costs[point]:
            continue
        if point in goals:
            found = point
            break
        x, y, _ = point
        for dx, dy, direction in _DIRECTIONS:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height
                    and world.tile_at(area, nx, ny, size) in '.:=,'
                    and (nx, ny) not in blocked):
                continue
            step = nx, ny, direction if track_facing else ''
            new_cost = cost + 1
            old_cost = costs.get(step)
            if old_cost is not None and new_cost >= old_cost:
                continue
            costs[step] = new_cost
            previous[step] = point
            distance = heuristic(nx, ny)
            heappush(queue, (new_cost + distance, distance, next(serial), new_cost, step))
    if found is None:
        return target, (), 'M'
    path = []
    cursor = found
    while cursor != start:
        path.append(cursor[:2])
        cursor = previous[cursor]
    path.reverse()
    dx, dy = path[0][0] - player_x, path[0][1] - player_y
    return target, tuple(path), _KEYS[dx, dy]
