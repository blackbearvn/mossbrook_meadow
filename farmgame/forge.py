"""Forge rules for mining tools and dungeon equipment.

The module is terminal independent so the curses panel, the line menu and the
automation tests all share the same recipes and effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .catalog import FORGE_RECIPES, GEAR, ITEMS, MAX_GEAR

if TYPE_CHECKING:
    from .model import Farm


def recipe_for(farm: 'Farm', key: str) -> dict[str, int] | None:
    """Recipe for the next rank of *key*, or ``None`` when it is maxed."""
    if key not in GEAR:
        from .model import GameError
        raise GameError('Trang bị này không có trong lò rèn.')
    level = farm.gear.get(key, 0)
    if level >= MAX_GEAR:
        return None
    return dict(FORGE_RECIPES[key][level])


def missing_for(farm: 'Farm', key: str, recipe: dict[str, int] | None = None) -> dict[str, int]:
    """Quantities still missing from the backpack (``coins`` included)."""
    recipe = recipe if recipe is not None else recipe_for(farm, key)
    if recipe is None:
        return {}
    missing: dict[str, int] = {}
    coins = recipe.get('coins', 0)
    if farm.coins < coins:
        missing['coins'] = coins - farm.coins
    for item, amount in recipe.items():
        if item == 'coins':
            continue
        have = farm.items.get(item, 0)
        if have < amount:
            missing[item] = amount - have
    return missing


def recipe_label(recipe: dict[str, int] | None) -> str:
    if recipe is None:
        return 'Đã đạt bậc tối đa 5.'
    parts = []
    for item, amount in recipe.items():
        name = 'xu' if item == 'coins' else ITEMS[item].name
        parts.append(f'{amount} {name}')
    return ' · '.join(parts)


def forge(farm: 'Farm', key: str) -> str:
    """Spend ores and coins to raise one equipment rank."""
    from .model import GameError

    if key not in GEAR:
        raise GameError('Lò rèn không có trang bị này.')
    level = farm.gear.get(key, 0)
    if level >= MAX_GEAR:
        raise GameError(f'{GEAR[key].name} đã đạt bậc tối đa {MAX_GEAR}.')
    recipe = recipe_for(farm, key)
    assert recipe is not None
    missing = missing_for(farm, key, recipe)
    if missing:
        labels = []
        for item, amount in missing.items():
            labels.append(f'{amount} {"xu" if item == "coins" else ITEMS[item].name}')
        raise GameError('Còn thiếu ' + ', '.join(labels) + '.')
    farm.coins -= recipe.get('coins', 0)
    for item, amount in recipe.items():
        if item != 'coins':
            farm.items[item] -= amount
    farm.gear[key] = level + 1
    farm.hp = min(farm.max_hp, farm.hp + (4 if key == 'armor' else 0))
    xp_message = farm.award_xp(3 + 2 * (level + 1))
    return (f'Lò rèn: {GEAR[key].name} lên bậc {level + 1}/{MAX_GEAR}. '
            f'{GEAR[key].effect} {xp_message}')


def attack_power(farm: 'Farm') -> int:
    """Damage dealt before the enemy's defence is applied."""
    return 3 + 2 * farm.gear.get('sword', 0) + farm.level // 2


def defense_power(farm: 'Farm') -> int:
    return 2 * farm.gear.get('armor', 0) + farm.level // 3


def mining_energy_cost(farm: 'Farm') -> int:
    """Better pickaxes make every swing cheaper, never free."""
    return max(1, 2 - farm.gear.get('pickaxe', 0) // 2)


def mining_bonus(farm: 'Farm') -> int:
    """Extra ore chunks from a higher-ranked pickaxe."""
    level = farm.gear.get('pickaxe', 0)
    return (level >= 2) + (level >= 4)


def gear_lines(farm: 'Farm') -> list[str]:
    rows = []
    for key, info in GEAR.items():
        level = farm.gear.get(key, 0)
        recipe = recipe_for(farm, key)
        rows.append(f'{info.icon} {info.name}: bậc {level}/{MAX_GEAR} · '
                    f'{info.effect}'
                    + ('' if recipe is None else f' Kế tiếp: {recipe_label(recipe)}.'))
    return rows
