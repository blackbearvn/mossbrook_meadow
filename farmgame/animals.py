"""Daily animal care and production, independent of the terminal UI."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .daily import ensure_daily, record_daily

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class AnimalType:
    name: str
    price: int
    product: str
    mature_days: int
    interval: int


ANIMAL_TYPES = {
    "chicken": AnimalType("Gà", 80, "egg", 2, 1),
    "duck": AnimalType("Vịt", 120, "egg", 2, 1),
    "cow": AnimalType("Bò", 240, "milk", 3, 1),
    "rabbit": AnimalType("Thỏ", 160, "fur", 2, 2),
    "sheep": AnimalType("Cừu", 200, "wool", 3, 2),
    "goat": AnimalType("Dê", 300, "milk", 3, 2),
    "pig": AnimalType("Heo", 420, "truffle", 3, 2),
}


@dataclass(frozen=True, slots=True)
class AnimalZone:
    key: str
    name: str
    level: int
    capacity: int
    species: tuple[str, ...]
    icon: str
    description: str


ANIMAL_ZONES = {
    "coop": AnimalZone(
        "coop", "Sân Gà Vịt", 1, 4, ("chicken", "duck", "rabbit"), "⌂",
        "Khu đầu tiên: gà, vịt cho trứng và thỏ cho lông mềm."),
    "pasture": AnimalZone(
        "pasture", "Đồng Cỏ", 2, 4, ("cow", "sheep", "pig"), "⚘",
        "Bò cho sữa, cừu cho len, heo tìm nấm củ; mở ở cấp 2."),
    "highland": AnimalZone(
        "highland", "Đồi Dê", 4, 2, ("goat",), "↟",
        "Dê núi leo dốc giỏi, cho sữa dê thơm; mở ở cấp 4."),
}

_SPECIES_ZONE = {kind: zone.key for zone in ANIMAL_ZONES.values()
                 for kind in zone.species}


def zone_for(kind: str) -> AnimalZone:
    return ANIMAL_ZONES[_SPECIES_ZONE[kind]]


def zone_unlocked(farm: "Farm", zone: AnimalZone | str) -> bool:
    zone = ANIMAL_ZONES[zone] if isinstance(zone, str) else zone
    return farm.level >= zone.level


def zone_animals(farm: "Farm", zone: AnimalZone | str) -> list["Animal"]:
    zone = ANIMAL_ZONES[zone] if isinstance(zone, str) else zone
    return [animal for animal in farm.animals if animal.kind in zone.species]


def zone_capacity(zone: AnimalZone | str) -> int:
    zone = ANIMAL_ZONES[zone] if isinstance(zone, str) else zone
    return zone.capacity


def next_zone(farm: "Farm") -> AnimalZone | None:
    return next((zone for zone in ANIMAL_ZONES.values()
                 if farm.level < zone.level), None)
PRODUCT_NAMES = {
    "chicken": "Trứng gà",
    "duck": "Trứng vịt",
    "rabbit": "Lông thỏ",
    "cow": "Sữa bò",
    "sheep": "Len cừu",
    "goat": "Sữa dê",
    "pig": "Nấm củ",
}


def product_name(kind: str) -> str:
    """Species-specific label even when two species share one inventory item."""
    if kind in PRODUCT_NAMES:
        return PRODUCT_NAMES[kind]
    return kind.replace('_', ' ').title()


@dataclass(slots=True)
class Animal:
    kind: str
    name: str
    age: int = 0
    fed: bool = False
    petted: bool = False
    friendship: int = 0
    produce: int = 0
    days_since_product: int = 0


def buy_animal(farm: "Farm", kind: str, name: str | None = None) -> str:
    from .model import GameError

    if kind not in ANIMAL_TYPES:
        raise GameError("Không có vật nuôi này.")
    info = ANIMAL_TYPES[kind]
    zone = zone_for(kind)
    if farm.level < zone.level:
        raise GameError(f"{zone.name} mở ở cấp {zone.level}. "
                        f"Hãy lên cấp rồi quay lại.")
    if len(zone_animals(farm, zone)) >= zone.capacity:
        raise GameError(f"{zone.name} đã đủ {zone.capacity} chỗ.")
    if len(farm.animals) >= farm.barn_capacity:
        raise GameError("Chuồng đã đầy. Hãy nâng cấp chuồng trước.")
    if farm.coins < info.price:
        raise GameError(f"Cần {info.price} xu để mua {info.name}.")
    if name is not None and (not isinstance(name, str)
                             or not 1 <= len(name.strip()) <= 24
                             or not name.strip().isprintable()):
        raise GameError("Tên vật nuôi cần 1–24 ký tự hiển thị được.")
    animal_name = name.strip() if name is not None else f"{info.name} {len(farm.animals) + 1}"
    farm.coins -= info.price
    farm.animals.append(Animal(kind, animal_name))
    return f"Đón {animal_name} về chuồng! (-{info.price} xu)"


def buy_feed(farm: "Farm", quantity: int) -> str:
    return farm.buy_item("feed", quantity)


def feed_animals(farm: "Farm") -> str:
    from .model import GameError

    hungry = [animal for animal in farm.animals if not animal.fed]
    if not hungry:
        raise GameError("Không có vật nuôi cần cho ăn hôm nay.")
    if farm.items["feed"] < len(hungry):
        raise GameError(f"Cần {len(hungry)} phần thức ăn cho đàn vật nuôi.")
    ensure_daily(farm)
    farm.items["feed"] -= len(hungry)
    for animal in hungry:
        animal.fed = True
    record_daily(farm, 'feed', len(hungry))
    return f"Đã cho {len(hungry)} vật nuôi ăn."


def pet_animal(farm: "Farm", index: int) -> str:
    from .model import GameError

    if type(index) is not int or not 0 <= index < len(farm.animals):
        raise GameError("Vật nuôi không hợp lệ.")
    animal = farm.animals[index]
    if animal.petted:
        raise GameError(f"Bạn đã vuốt ve {animal.name} hôm nay rồi.")
    ensure_daily(farm)
    animal.petted = True
    animal.friendship = min(5, animal.friendship + 1)
    record_daily(farm, 'pet')
    return f"{animal.name} vui vẻ! Thân thiết: {animal.friendship}/5."


def collect_products(farm: "Farm") -> str:
    from .model import GameError

    quantity = sum(animal.produce for animal in farm.animals)
    if not quantity:
        raise GameError("Chưa có trứng, sữa hoặc len để lấy.")
    ensure_daily(farm)
    for animal in farm.animals:
        farm.items[ANIMAL_TYPES[animal.kind].product] += animal.produce
        animal.produce = 0
    xp_message = farm.award_xp(quantity * 3)
    record_daily(farm, 'collect', quantity)
    return f"Đã lấy {quantity} sản phẩm vật nuôi, {xp_message}"


def advance_animals(farm: "Farm") -> str:
    """Resolve the day just ended; babies grow even when unfed."""
    produced = 0
    for animal in farm.animals:
        info = ANIMAL_TYPES[animal.kind]
        animal.age += 1
        if animal.fed and animal.age >= info.mature_days:
            animal.days_since_product += 1
            if animal.days_since_product >= info.interval:
                amount = 2 if animal.friendship >= 4 else 1
                amount += int(farm.skills['ranching'] >= 3)
                animal.produce += amount
                produced += amount
                animal.days_since_product = 0
        animal.fed = False
        animal.petted = False
    return f"Chuồng có thêm {produced} sản phẩm." if produced else ""
