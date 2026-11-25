"""Home cooking: recipes, ingredient handling and small energy rewards.

The kitchen is a home station.  Recipes use produce, fish and animal goods
from the bag or the chest; cooked dishes become ordinary items so the shop,
chest and inventory panels keep working without a second inventory model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .catalog import ITEMS
from .inventory import count_item

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class Recipe:
    key: str
    name: str
    ingredients: dict[str, int]
    energy: int
    xp: int
    level: int
    description: str
    icon: str = '◇'
    ascii_icon: str = 'o'


RECIPES = {
    'banh_mi': Recipe(
        'banh_mi', 'Bánh mì nướng',
        {'crop:lua_mi': 2, 'egg': 1}, 8, 8, 1,
        'Bánh mì giòn với trứng ốp la, bữa sáng quen thuộc.'),
    'salad_vuon': Recipe(
        'salad_vuon', 'Salad vườn',
        {'crop:ca_rot': 2, 'crop:ca_chua': 1}, 10, 10, 1,
        'Cà rốt và cà chua tươi trộn giấm mật ong.'),
    'nuoc_dua_hau': Recipe(
        'nuoc_dua_hau', 'Nước dưa hấu',
        {'crop:dua_hau': 1}, 12, 12, 2,
        'Ly nước mát lạnh cho những trưa nắng trên đồng.'),
    'cha_ca': Recipe(
        'cha_ca', 'Chả cá',
        {'ca_ro': 2, 'egg': 1}, 12, 14, 2,
        'Cá rô quết nhuyễn với trứng, chiên vàng hai mặt.'),
    'chao_trung': Recipe(
        'chao_trung', 'Cháo trứng',
        {'crop:lua_mi': 2, 'egg': 1, 'milk': 1}, 16, 15, 2,
        'Cháo nóng nấu bằng sữa tươi, thêm trứng và hành lá.'),
    'sup_bi': Recipe(
        'sup_bi', 'Súp bí ngô',
        {'crop:bi_ngo': 2, 'milk': 1}, 14, 18, 3,
        'Bí ngô nghiền mịn với sữa, thơm mùi bơ và tiêu.'),
    'sinh_to_dau': Recipe(
        'sinh_to_dau', 'Sinh tố dâu',
        {'crop:dau_tay': 2, 'milk': 1}, 18, 20, 3,
        'Dâu tây xay cùng sữa, món quà của mùa hè.'),
    'tra_hoa_hong': Recipe(
        'tra_hoa_hong', 'Trà hoa hồng',
        {'crop:hoa_hong': 1, 'crop:dau_tay': 1}, 15, 16, 4,
        'Cánh hồng sấy nhẹ pha cùng trà, hương thơm dịu.'),
    'sup_nam': Recipe(
        'sup_nam', 'Súp nấm rừng',
        {'mushroom': 2, 'milk': 1}, 10, 8, 1,
        'Nấm từ lối rừng nấu cùng sữa, món Hà mang cho người sửa mái.'),
    'tra_rung': Recipe(
        'tra_rung', 'Trà rừng mật ong',
        {'tea_leaf': 2, 'herb': 1, 'honey': 1}, 12, 10, 2,
        'Búp trà già và mật ong, pha theo cách Bác Hai vẫn mời khách.'),
    'mut_rung': Recipe(
        'mut_rung', 'Mứt quả mọng',
        {'berry': 3, 'honey': 1}, 14, 12, 2,
        'Giữ lại hương quả trong hũ nhỏ để dành cho ngày lạnh.'),
}

COOKED_ITEMS = tuple(RECIPES)
_RATE = {'attribute': 20, 'skill': 10}


def _total(farm: 'Farm', key: str) -> int:
    """Ingredients can come from the bag or the protected chest."""
    return count_item(farm, key) + farm.chest.get(key, 0)


def missing_ingredients(farm: 'Farm', recipe: Recipe) -> dict[str, int]:
    return {key: quantity - _total(farm, key)
            for key, quantity in recipe.ingredients.items()
            if quantity > _total(farm, key)}


def can_cook(farm: 'Farm', recipe: Recipe) -> bool:
    return farm.level >= recipe.level and not missing_ingredients(farm, recipe)


def available_recipes(farm: 'Farm') -> list[tuple[Recipe, dict[str, int]]]:
    return [(recipe, missing_ingredients(farm, recipe))
            for recipe in RECIPES.values()]


def _take(farm: 'Farm', key: str, quantity: int) -> None:
    """Take from the bag first, then from the chest."""
    slot = None
    if key.startswith('seed:'):
        slot = farm.seeds
        slot_key = key.split(':', 1)[1]
    elif key.startswith('crop:'):
        slot = farm.produce
        slot_key = key.split(':', 1)[1]
    else:
        slot = farm.items
        slot_key = key
    from_bag = min(quantity, slot[slot_key])
    slot[slot_key] -= from_bag
    remaining = quantity - from_bag
    if remaining:
        farm.chest[key] -= remaining


def cook(farm: 'Farm', key: str) -> str:
    from .model import GameError

    recipe = RECIPES.get(key)
    if recipe is None:
        raise GameError('Không có công thức nấu ăn này.')
    if farm.level < recipe.level:
        raise GameError(f'{recipe.name} mở ở cấp {recipe.level}.')
    missing = missing_ingredients(farm, recipe)
    if missing:
        names = ', '.join(f'{ITEMS[item].name} ×{amount}'
                          for item, amount in missing.items())
        raise GameError(f'Còn thiếu: {names}.')
    # Validate everything before touching inventory so failed cooking is atomic.
    for item, amount in recipe.ingredients.items():
        _take(farm, item, amount)
    farm.items[recipe.key] = farm.items.get(recipe.key, 0) + 1
    farm.energy = min(farm.energy_limit, farm.energy + recipe.energy)
    xp_message = farm.award_xp(recipe.xp)
    from .daily import ensure_daily, record_daily
    ensure_daily(farm)
    record_daily(farm, 'cook')
    return (f'Đã nấu {recipe.name}. Hồi {recipe.energy} năng lượng, '
            f'{xp_message} Món ăn đã được cất vào túi.')


def ingredient_line(recipe: Recipe, missing: dict[str, int]) -> str:
    parts = []
    for key, quantity in recipe.ingredients.items():
        have = max(0, quantity - missing.get(key, 0))
        parts.append(f'{ITEMS[key].name} {have}/{quantity}')
    return ' · '.join(parts)


def recipe_rows(farm: 'Farm') -> list[tuple[Recipe, dict[str, int]]]:
    return available_recipes(farm)
