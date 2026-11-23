"""Item transfers across seeds, produce, the backpack and a protected chest."""

from .catalog import FISH_TYPES, ITEMS
from .model import Farm, GameError


SECTION_ORDER = ('all', 'seed', 'crop', 'fish', 'other')
SECTION_NAMES = {
    'all': 'Tất cả',
    'seed': 'Hạt giống',
    'crop': 'Nông sản',
    'fish': 'Cá',
    'other': 'Khác',
}


def item_section(key: str) -> str:
    """Return the inventory tab that owns *key*."""
    if key.startswith('seed:'):
        return 'seed'
    if key.startswith('crop:'):
        return 'crop'
    if key in FISH_TYPES:
        return 'fish'
    return 'other'


def section_rows(rows, section: str):
    """Filter parsed inventory rows by a section name."""
    if section == 'all':
        return list(rows)
    return [row for row in rows if item_section(row[0]) == section]


def _bag_slot(farm: Farm, key: str) -> tuple[dict[str, int], str]:
    if key not in ITEMS:
        raise GameError("Không có vật phẩm này.")
    if key.startswith("seed:"):
        return farm.seeds, key.split(":", 1)[1]
    if key.startswith("crop:"):
        return farm.produce, key.split(":", 1)[1]
    return farm.items, key


def count_item(farm: Farm, key: str) -> int:
    inventory, slot = _bag_slot(farm, key)
    return inventory[slot]


def inventory_rows(farm: Farm) -> list[tuple[str, str, int, int]]:
    return [(key, item.name, count_item(farm, key), farm.chest[key])
            for key, item in ITEMS.items()]


def transfer_item(farm: Farm, key: str, quantity: int, direction: str) -> str:
    inventory, slot = _bag_slot(farm, key)
    if type(quantity) is not int or quantity < 1:
        raise GameError("Số lượng phải là số nguyên dương.")
    if direction not in ("deposit", "withdraw"):
        raise GameError("Chọn gửi vào rương hoặc lấy ra túi.")
    available = inventory[slot] if direction == "deposit" else farm.chest[key]
    if quantity > available:
        raise GameError(f"Chỉ có {available} {ITEMS[key].name} để chuyển.")
    change = -quantity if direction == "deposit" else quantity
    inventory[slot] += change
    farm.chest[key] -= change
    action = "Cất vào rương" if direction == "deposit" else "Lấy ra túi"
    return f"{action}: {quantity} {ITEMS[key].name}."


def deposit_all(farm: Farm) -> str:
    total = 0
    for key in ITEMS:
        inventory, slot = _bag_slot(farm, key)
        quantity = inventory[slot]
        farm.chest[key] += quantity
        inventory[slot] = 0
        total += quantity
    if not total:
        raise GameError("Túi đang trống, không có đồ cần cất.")
    return f"Đã cất {total} vật phẩm vào rương. Đồ trong rương được giữ khi bán hàng."
