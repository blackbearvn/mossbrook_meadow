"""Game rules, independent of terminal input and save files."""

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .catalog import (CROPS, WEATHER, EXTRA_ITEMS, FISH_TYPES, MAX_GEAR, Crop,
                      empty_chest, empty_fish_collection, empty_gear,
                      starting_items)
from .villagers import empty_friendships, empty_talked_on
from .tutorial import TutorialState
from .daily import DailyState, ensure_daily, record_daily
from .progression import (action_cost, attribute_points, empty_attributes,
                          empty_skills, energy_limit, gain_xp, sale_price,
                          skill_points)
from .achievements import ACHIEVEMENTS, empty_achievements

if TYPE_CHECKING:
    from .animals import Animal


class GameError(ValueError):
    """An action the farmer cannot currently perform."""


def coordinates(size: int) -> list[str]:
    return [f"{chr(65 + col)}{row + 1}"
            for row in range(size) for col in range(size)]


def empty_inventory() -> dict[str, int]:
    return dict.fromkeys(CROPS, 0)


def starting_seeds() -> dict[str, int]:
    return {**empty_inventory(), "ca_rot": 6, "lua_mi": 6}


@dataclass(slots=True)
class Plot:
    crop: str | None = None
    growth: int = 0
    watered: bool = False
    dry_days: int = 0
    dead: bool = False

    @property
    def ready(self) -> bool:
        return bool(self.crop and not self.dead
                    and self.growth >= CROPS[self.crop].days)


@dataclass(slots=True)
class Farm:
    name: str = "Mossbrook Meadow"
    day: int = 1
    coins: int = 120
    energy: int = 20
    max_energy: int = 20
    xp: int = 0
    size: int = 4
    weather: str = "sunny"
    sprinkler: bool = False
    harvested: int = 0
    sales: int = 0
    seeds: dict[str, int] = field(default_factory=starting_seeds)
    produce: dict[str, int] = field(default_factory=empty_inventory)
    plots: dict[str, Plot] = field(default_factory=dict)
    area: str = "village"
    player_x: int = 10
    player_y: int = 7
    facing: str = "down"
    forecast: str = "cloudy"
    items: dict[str, int] = field(default_factory=starting_items)
    chest: dict[str, int] = field(default_factory=empty_chest)
    animals: list["Animal"] = field(default_factory=list)
    barn_capacity: int = 4
    fish_caught: int = 0
    friendships: dict[str, int] = field(default_factory=empty_friendships)
    talked_on: dict[str, int] = field(default_factory=empty_talked_on)
    attributes: dict[str, int] = field(default_factory=empty_attributes)
    skills: dict[str, int] = field(default_factory=empty_skills)
    player_name: str = 'Người làm vườn'
    avatar: str = '@'
    outfit: str = 'green'
    background: str = 'gardener'
    intro_seen: bool = True
    tutorial: TutorialState = field(default_factory=TutorialState)
    daily: DailyState = field(default_factory=DailyState)
    fish_collection: dict[str, int] = field(default_factory=empty_fish_collection)
    # Points automatically retired after every base stat is maxed.  Keeping
    # them on the farm (rather than hiding them in the UI) makes the derived
    # point formula stable and auditable.
    retired_attribute_points: int = 0
    retired_skill_points: int = 0
    # New games use small map pages; old saves keep the legacy full map until
    # they are migrated or the player starts a new journey.
    map_pages: bool = False
    # Mining, forging and the dungeon share a small persistent state.  Fields
    # default to safe values so schema-seven saves keep loading unchanged.
    hp: int = 20
    gear: dict[str, int] = field(default_factory=empty_gear)
    mine_used: dict[str, int] = field(default_factory=dict)
    dungeon_best: int = 0
    mined_total: int = 0
    achievements: dict[str, bool] = field(default_factory=empty_achievements)

    def __post_init__(self) -> None:
        if not self.plots:
            self.plots = {key: Plot() for key in coordinates(self.size)}
        if not isinstance(self.gear, dict):
            self.gear = empty_gear()
        else:
            legacy_hat = self.gear.get('pickaxe', 0)
            normalized = {}
            for key in empty_gear():
                value = self.gear.get(key, 0)
                normalized[key] = (max(0, min(MAX_GEAR, value))
                                   if type(value) is int else value)
            if not normalized.get('hat') and type(legacy_hat) is int:
                normalized['hat'] = max(0, min(MAX_GEAR, legacy_hat))
            self.gear = normalized
        if not isinstance(self.achievements, dict):
            self.achievements = empty_achievements()
        else:
            self.achievements = {
                item.id: bool(self.achievements.get(item.id, False))
                for item in ACHIEVEMENTS}
        self.mined_total = max(0, int(self.mined_total))

    @property
    def level(self) -> int:
        return 1 + self.xp // 40

    @property
    def energy_limit(self) -> int:
        return energy_limit(self)

    @property
    def max_hp(self) -> int:
        """Health grows with armour and levels, independently of energy."""
        return (20 + 4 * self.gear.get('armor', 0)
                + 2 * self.gear.get('pants', 0)
                + self.gear.get('shoes', 0)
                + 2 * (self.level - 1))

    @property
    def attribute_points(self) -> int:
        return attribute_points(self)

    @property
    def skill_points(self) -> int:
        return skill_points(self)

    def award_xp(self, amount: int) -> str:
        return gain_xp(self, amount)

    @property
    def fish_points(self) -> int:
        return sum(FISH_TYPES[key].points * count
                   for key, count in self.fish_collection.items())

    @property
    def fish_species(self) -> int:
        return sum(bool(count) for count in self.fish_collection.values())

    @property
    def fish_collection_value(self) -> int:
        return sum(EXTRA_ITEMS[key].sell_price * count
                   for key, count in self.fish_collection.items())

    @property
    def goal_complete(self) -> bool:
        return self.harvested >= 30 and self.sales >= 1000

    def _plot(self, coordinate: str) -> tuple[str, Plot]:
        key = coordinate.strip().upper()
        if key not in self.plots:
            last = f"{chr(64 + self.size)}{self.size}"
            raise GameError(f"Ô '{coordinate}' không hợp lệ. Chọn từ A1 đến {last}.")
        return key, self.plots[key]

    def _crop(self, crop: str) -> Crop:
        if crop not in CROPS:
            raise GameError("Không có giống cây này.")
        return CROPS[crop]

    def _spend_energy(self, amount: int) -> None:
        if self.energy < amount:
            raise GameError(f"Cần {amount} năng lượng. Về nhà ngủ để hồi sức (7 ở menu dòng).")
        self.energy -= amount

    def is_watered(self, coordinate: str) -> bool:
        _, plot = self._plot(coordinate)
        return plot.watered or self.weather == "rainy" or self.sprinkler

    def plant(self, coordinate: str, crop: str) -> str:
        key, plot = self._plot(coordinate)
        info = self._crop(crop)
        if plot.crop:
            raise GameError(f"{key} đã có cây. Hãy thu hoạch hoặc dọn cây héo trước.")
        if self.level < info.level:
            raise GameError(f"{info.name} mở khóa ở cấp {info.level}.")
        if self.seeds[crop] < 1:
            raise GameError(f"Hết hạt {info.name}. Mua thêm ở cửa hàng (phím 4).")
        self._spend_energy(action_cost(self, 'plant'))
        ensure_daily(self)
        self.seeds[crop] -= 1
        self.plots[key] = Plot(crop=crop)
        record_daily(self, 'plant')
        if self.sprinkler:
            record_daily(self, 'water')
        from .tutorial import record_event
        record_event(self, 'plant', coordinate=key, crop=crop)
        return f"{key}: đã trồng {info.name}. Nhớ tưới trước khi ngủ!"

    def water(self, coordinate: str) -> str:
        key, plot = self._plot(coordinate)
        if not plot.crop:
            raise GameError(f"{key} chưa có cây.")
        if plot.dead:
            raise GameError(f"{key} đã héo. Dọn cây bằng phím 3.")
        if plot.ready:
            raise GameError(f"{key} đã chín, có thể thu hoạch ngay (phím 3).")
        if self.is_watered(key):
            raise GameError(f"{key} đã đủ nước hôm nay.")
        self._spend_energy(1)
        ensure_daily(self)
        plot.watered = True
        record_daily(self, 'water')
        from .tutorial import record_event
        record_event(self, 'water', coordinate=key)
        return f"{key}: đã tưới nước."

    def harvest(self, coordinate: str) -> str:
        key, plot = self._plot(coordinate)
        if not plot.crop:
            raise GameError(f"{key} chưa có cây.")
        if plot.dead:
            raise GameError(f"{key} đã héo. Hãy dọn cây để trồng lại.")
        info = CROPS[plot.crop]
        if not plot.ready:
            raise GameError(f"{key} cần thêm {info.days - plot.growth} đêm được tưới.")
        self._spend_energy(action_cost(self, 'harvest'))
        ensure_daily(self)
        quantity = 2 if self.skills['farming'] >= 3 else 1
        self.produce[plot.crop] += quantity
        self.harvested += quantity
        xp_message = self.award_xp(info.xp)
        self.plots[key] = Plot()
        record_daily(self, 'harvest', quantity)
        from .tutorial import record_event
        record_event(self, 'harvest', coordinate=key)
        return f"{key}: thu hoạch {quantity} {info.name}, {xp_message}"

    def clear(self, coordinate: str) -> str:
        key, plot = self._plot(coordinate)
        if not plot.dead:
            raise GameError(f"{key} không có cây héo cần dọn.")
        self._spend_energy(1)
        ensure_daily(self)
        self.plots[key] = Plot()
        record_daily(self, 'clear')
        return f"{key}: đã dọn cây héo, sẵn sàng trồng lại."

    def sleep(self, next_weather: str | None = None) -> str:
        if next_weather is None:
            next_weather = self.forecast
        if next_weather not in WEATHER:
            raise GameError("Thời tiết không hợp lệ.")
        grew = ripened = wilted = 0
        for key, plot in self.plots.items():
            if plot.crop and not plot.dead and not plot.ready:
                if self.is_watered(key):
                    plot.growth += 1
                    plot.dry_days = 0
                    grew += 1
                    ripened += int(plot.ready)
                else:
                    plot.dry_days += 1
                    if plot.dry_days >= 3:
                        plot.dead = True
                        wilted += 1
            plot.watered = False
        animal_report = ""
        if self.animals:
            from .animals import advance_animals
            animal_report = advance_animals(self)
        self.day += 1
        self.energy = self.energy_limit
        self.hp = self.max_hp
        self.mine_used = {}
        self.weather = next_weather
        self.forecast = random.choices(list(WEATHER), weights=[5, 2, 3], k=1)[0]
        ensure_daily(self)
        message = (f"Chào ngày {self.day}! {WEATHER[next_weather]}. "
                   f"Đã hồi đầy {self.energy_limit} năng lượng.")
        if grew:
            message += f" {grew} cây đã lớn."
        if ripened:
            message += f" {ripened} cây vừa chín!"
        if wilted:
            message += f" {wilted} cây héo vì thiếu nước 3 ngày."
        if next_weather == "rainy":
            message += " Mưa tưới ruộng hôm nay, bạn có thể nghỉ tay."
        if animal_report:
            message += f" {animal_report}"
        from .tutorial import record_event
        record_event(self, 'sleep')
        return message

    def forecast_report(self) -> str:
        advice = ("Mưa sẽ tưới toàn bộ ruộng, có thể dành sức đi câu."
                  if self.forecast == "rainy"
                  else "Nhớ tưới cây trước khi ngủ; mây không thay cho nước tưới.")
        return (f"TV MOSSBROOK · Dự báo ngày {self.day + 1}: "
                f"{WEATHER[self.forecast]}. {advice}")

    def buy_seeds(self, crop: str, quantity: int) -> str:
        info = self._crop(crop)
        if type(quantity) is not int or quantity < 1:
            raise GameError("Số lượng phải là số nguyên dương.")
        if self.level < info.level:
            raise GameError(f"{info.name} mở khóa ở cấp {info.level}.")
        cost = info.seed_price * quantity
        if self.coins < cost:
            raise GameError(f"Cần {cost} xu, hiện có {self.coins} xu.")
        self.coins -= cost
        self.seeds[crop] += quantity
        ensure_daily(self)
        record_daily(self, 'buy', quantity)
        from .tutorial import record_event
        record_event(self, 'buy', crop=crop, quantity=quantity)
        return f"Mua {quantity} hạt {info.name}, hết {cost} xu."

    def sell_all(self, keep=()) -> str:
        """Sell bag goods; ``keep`` protects crafting or quest materials."""
        keep = set(keep)
        sellable = {key: count for key, count in self.items.items()
                    if EXTRA_ITEMS[key].sell_price and count and key not in keep}
        quantity = sum(self.produce.values()) + sum(sellable.values())
        if not quantity:
            raise GameError("Túi chưa có nông sản, cá hoặc sản phẩm để bán.")
        revenue = sum(sale_price(self, f'crop:{crop}') * count
                      for crop, count in self.produce.items())
        revenue += sum(sale_price(self, key) * count
                       for key, count in sellable.items())
        fish_quantity = sum(count for key, count in sellable.items()
                            if key in FISH_TYPES)
        ensure_daily(self)
        self.coins += revenue
        self.sales += revenue
        self.produce = empty_inventory()
        for key in sellable:
            self.items[key] = 0
        record_daily(self, 'sell', revenue)
        if fish_quantity:
            record_daily(self, 'sell_fish', fish_quantity)
        from .tutorial import record_event
        record_event(self, 'sell')
        return f"Đã bán {quantity} sản phẩm trong túi, nhận {revenue} xu!"

    def buy_item(self, key: str, quantity: int) -> str:
        if key not in EXTRA_ITEMS or EXTRA_ITEMS[key].buy_price <= 0:
            raise GameError("Cửa hàng không bán vật phẩm này.")
        if type(quantity) is not int or quantity < 1:
            raise GameError("Số lượng phải là số nguyên dương.")
        info = EXTRA_ITEMS[key]
        cost = info.buy_price * quantity
        if self.coins < cost:
            raise GameError(f"Cần {cost} xu, hiện có {self.coins} xu.")
        self.coins -= cost
        self.items[key] += quantity
        return f"Mua {quantity} {info.name}, hết {cost} xu."

    def upgrade_cost(self, kind: str) -> int:
        if kind == "land":
            if self.size >= 6:
                raise GameError("Ruộng đã đạt kích thước tối đa 6 × 6.")
            return 150 * (self.size - 3)
        if kind == "energy":
            if self.max_energy >= 30:
                raise GameError("Thể lực đã được nâng tối đa.")
            return 180
        if kind == "sprinkler":
            if self.sprinkler:
                raise GameError("Bạn đã có hệ thống tưới tự động.")
            return 300
        if kind == "barn":
            if self.barn_capacity >= 8:
                raise GameError("Chuồng đã có tối đa 8 chỗ.")
            return 280
        raise GameError("Không có nâng cấp này.")

    def upgrade(self, kind: str) -> str:
        cost = self.upgrade_cost(kind)
        if self.coins < cost:
            raise GameError(f"Cần {cost} xu, hiện có {self.coins} xu.")
        self.coins -= cost
        if kind == "land":
            self.size += 1
            for key in coordinates(self.size):
                self.plots.setdefault(key, Plot())
            ensure_daily(self)
            record_daily(self, 'upgrade')
            return f"Ruộng đã rộng {self.size} × {self.size}! (-{cost} xu)"
        if kind == "energy":
            self.max_energy = 30
            self.energy = min(self.energy_limit, self.energy + 10)
            ensure_daily(self)
            record_daily(self, 'upgrade')
            return f"Thể lực tối đa tăng lên {self.energy_limit}, hồi ngay 10 năng lượng! (-180 xu)"
        if kind == "barn":
            self.barn_capacity = 8
            ensure_daily(self)
            record_daily(self, 'upgrade')
            return "Chuồng đã mở rộng lên 8 chỗ! (-280 xu)"
        ensure_daily(self)
        watered = sum(bool(plot.crop) and not plot.dead and not plot.ready
                      and not self.is_watered(key)
                      for key, plot in self.plots.items())
        self.sprinkler = True
        record_daily(self, 'water', watered)
        record_daily(self, 'upgrade')
        return "Đã lắp hệ thống tưới! Cây luôn đủ nước từ bây giờ. (-300 xu)"

    def work(self) -> str:
        cost = action_cost(self, 'work')
        self._spend_energy(cost)
        ensure_daily(self)
        rank = self.skills['foraging']
        coins, wood = 6 + 2 * rank, 1 + rank // 2
        self.coins += coins
        self.items['wood'] += wood
        xp_message = self.award_xp(2)
        record_daily(self, 'work')
        return (f"Giúp hàng xóm nhặt củi, nhận {coins} xu, {wood} gỗ. "
                f"(-{cost} năng lượng) {xp_message}")
