"""Mining rules for the Mỏ Khoáng map.

Every rock refills each morning.  Pickaxe rank lowers the energy cost and adds
extra chunks, while the foraging skill adds one more chunk at rank three.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import world
from .catalog import ITEMS
from .forge import mining_bonus, mining_energy_cost

if TYPE_CHECKING:
    from .model import Farm


_ORE_XP = {'quang_dong': 3, 'quang_sat': 5, 'quang_vang': 8, 'kim_cuong': 12}


def rock_capacity(farm: 'Farm') -> int:
    return 2 + int(farm.gear.get('pickaxe', 0) >= 3)


def rock_key(x: int, y: int) -> str:
    return f'{x},{y}'


def rock_remaining(farm: 'Farm', x: int, y: int) -> int:
    used = farm.mine_used.get(rock_key(x, y), 0)
    return max(0, rock_capacity(farm) - used)


def rock_exhausted(farm: 'Farm', x: int, y: int) -> bool:
    return rock_remaining(farm, x, y) <= 0


def mine_rock(farm: 'Farm', x: int, y: int) -> str:
    """Mine one adjacent rock, spending energy and recording the daily goal."""
    from .model import GameError

    if farm.area != 'mine':
        raise GameError('Bạn chỉ đào được đá trong mỏ khoáng.')
    if (x, y) not in world.MINE_ROCKS:
        raise GameError('Chỗ đó không có đá để đào.')
    if abs(x - farm.player_x) + abs(y - farm.player_y) != 1:
        raise GameError('Hãy đứng sát tảng đá rồi nhấn E.')
    if rock_exhausted(farm, x, y):
        raise GameError('Tảng đá này đã hết quặng hôm nay. Ngủ qua ngày để mỏ hồi đầy.')
    cost = mining_energy_cost(farm)
    if farm.energy < cost:
        raise GameError(f'Cần {cost} năng lượng để đào. Hãy ngủ để hồi sức.')
    kind = world.mine_rock_kind(x, y)
    key = rock_key(x, y)
    index = farm.mine_used.get(key, 0)

    bonus = mining_bonus(farm)
    if farm.skills.get('foraging', 0) >= 3:
        bonus += 1
    stones = 1 + bonus
    ore = 1 + (1 if farm.gear.get('pickaxe', 0) >= 2 else 0)
    if kind == 'kim_cuong':
        ore = 1 + (1 if farm.gear.get('pickaxe', 0) >= 5 else 0)
    farm._spend_energy(cost)
    if index % 2 == 1:
        # Every second swing in the same rock also yields a little copper.
        farm.items['quang_dong'] += 1
    farm.items['da'] += stones
    farm.items[kind] += ore
    farm.mine_used[key] = index + 1
    from .daily import ensure_daily, record_daily
    ensure_daily(farm)
    record_daily(farm, 'mine')
    xp_message = farm.award_xp(_ORE_XP[kind] + bonus)
    name = world.MINE_ROCK_NAMES.get(kind, ITEMS[kind].name)
    left = rock_remaining(farm, x, y)
    tail = f' Còn {left} lần đào ở tảng này.' if left else ' Tảng đá đã cạn trong hôm nay.'
    return (f'Đào được {stones} đá và {ore} {name} (-{cost} năng lượng). '
            f'{xp_message}{tail}')


def mine_summary(farm: 'Farm') -> tuple[int, int]:
    """(rocks still available today, total rocks in the mine)."""
    available = sum(not rock_exhausted(farm, x, y) for x, y in world.MINE_ROCKS)
    return available, len(world.MINE_ROCKS)
