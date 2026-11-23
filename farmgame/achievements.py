"""Persistent milestone achievements, grouped into five-tier families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .catalog import GEAR, MAX_GEAR, RARITY_NAMES

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class Achievement:
    id: str
    name: str
    description: str
    target: int
    reward: int
    progress: Callable[['Farm'], int]
    family: str = 'misc'
    tier: int = 1

    def current(self, farm: 'Farm') -> int:
        return max(0, int(self.progress(farm)))


FAMILY_NAMES = {
    'harvest': 'Thu hoạch',
    'sales': 'Kinh doanh',
    'fishing': 'Câu cá',
    'mining': 'Khai mỏ',
    'forge': 'Rèn trang bị',
    'mythic': 'Trang bị Huyền thoại',
    'friend': 'Tình bạn',
    'community': 'Cả làng',
    'dungeon': 'Hang Sâu',
    'animals': 'Vật nuôi',
    'species': 'Bộ sưu tầm cá',
    'level': 'Cấp độ',
}


def _gear_upgrades(farm: 'Farm') -> int:
    return sum(max(0, int(level)) for level in farm.gear.values())


def _mythic_gear(farm: 'Farm') -> int:
    return sum(1 for key in GEAR if farm.gear.get(key, 0) >= MAX_GEAR)


def _friends_best(farm: 'Farm') -> int:
    return max(farm.friendships.values(), default=0)


def _friends_all(farm: 'Farm') -> int:
    return min(farm.friendships.values(), default=0)


def _animals(farm: 'Farm') -> int:
    return len(farm.animals)


def _fish_species(farm: 'Farm') -> int:
    return sum(bool(count) for count in farm.fish_collection.values())


def _a(achievement_id, name, description, target, reward, progress,
       family, tier):
    return Achievement(achievement_id, name, description, target, reward,
                       progress, family, tier)


ACHIEVEMENTS = (
    # Harvest: five ranks from the first sprout to a true farm owner.
    _a('first_harvest', 'Mầm xanh đầu tiên',
       'Thu hoạch vụ mùa đầu tiên.', 1, 10,
       lambda farm: farm.harvested, 'harvest', 1),
    _a('harvest_5', 'Người vun luống',
       'Thu hoạch 5 nông sản.', 5, 20,
       lambda farm: farm.harvested, 'harvest', 2),
    _a('harvest_15', 'Mùa màng đơm hoa',
       'Thu hoạch 15 nông sản.', 15, 35,
       lambda farm: farm.harvested, 'harvest', 3),
    _a('harvest_30', 'Một mùa bội thu',
       'Thu hoạch 30 nông sản.', 30, 55,
       lambda farm: farm.harvested, 'harvest', 4),
    _a('harvest_100', 'Chủ nông trại thực thụ',
       'Thu hoạch 100 nông sản.', 100, 90,
       lambda farm: farm.harvested, 'harvest', 5),

    # Sales.
    _a('sales_100', 'Món hời đầu tiên',
       'Bán được tổng cộng 100 xu.', 100, 10,
       lambda farm: farm.sales, 'sales', 1),
    _a('sales_500', 'Người bán khéo',
       'Bán được tổng cộng 500 xu.', 500, 20,
       lambda farm: farm.sales, 'sales', 2),
    _a('sales_1000', 'Gian hàng nhỏ',
       'Bán được tổng cộng 1.000 xu.', 1000, 35,
       lambda farm: farm.sales, 'sales', 3),
    _a('sales_5000', 'Thương nhân Mossbrook',
       'Bán được tổng cộng 5.000 xu.', 5000, 55,
       lambda farm: farm.sales, 'sales', 4),
    _a('sales_10000', 'Ông trùm chợ làng',
       'Bán được tổng cộng 10.000 xu.', 10000, 90,
       lambda farm: farm.sales, 'sales', 5),

    # Fishing.
    _a('first_fish', 'Cần câu may mắn',
       'Câu được con cá đầu tiên.', 1, 10,
       lambda farm: farm.fish_caught, 'fishing', 1),
    _a('fish_5', 'Bạn của mặt hồ',
       'Câu được 5 con cá.', 5, 20,
       lambda farm: farm.fish_caught, 'fishing', 2),
    _a('fish_10', 'Người đọc nước',
       'Câu được 10 con cá.', 10, 35,
       lambda farm: farm.fish_caught, 'fishing', 3),
    _a('fish_20', 'Tay câu cứng cỏi',
       'Câu được 20 con cá.', 20, 55,
       lambda farm: farm.fish_caught, 'fishing', 4),
    _a('fish_50', 'Huyền thoại hồ Sen',
       'Câu được 50 con cá.', 50, 90,
       lambda farm: farm.fish_caught, 'fishing', 5),

    # Mining.
    _a('mine_1', 'Cuốc đá đầu tiên',
       'Đào lượt quặng đầu tiên trong mỏ.', 1, 10,
       lambda farm: farm.mined_total, 'mining', 1),
    _a('mine_10', 'Thợ mỏ tập sự',
       'Đào 10 lượt quặng trong mỏ.', 10, 20,
       lambda farm: farm.mined_total, 'mining', 2),
    _a('mine_30', 'Người hiểu lòng đất',
       'Đào 30 lượt quặng trong mỏ.', 30, 35,
       lambda farm: farm.mined_total, 'mining', 3),
    _a('mine_60', 'Thợ mỏ Hang Sâu',
       'Đào 60 lượt quặng trong mỏ.', 60, 55,
       lambda farm: farm.mined_total, 'mining', 4),
    _a('mine_100', 'Bậc thầy khoáng sản',
       'Đào 100 lượt quặng trong mỏ.', 100, 90,
       lambda farm: farm.mined_total, 'mining', 5),

    # Forge.
    _a('forge_first', 'Lò rèn bén lửa',
       'Rèn thành công một món trang bị.', 1, 10,
       _gear_upgrades, 'forge', 1),
    _a('forge_3', 'Người nâng cấp',
       'Nâng tổng cộng 3 bậc trang bị.', 3, 20,
       _gear_upgrades, 'forge', 2),
    _a('forge_6', 'Thợ rèn làng',
       'Nâng tổng cộng 6 bậc trang bị.', 6, 35,
       _gear_upgrades, 'forge', 3),
    _a('forge_10', 'Bàn tay sắt',
       'Nâng tổng cộng 10 bậc trang bị.', 10, 55,
       _gear_upgrades, 'forge', 4),
    _a('forge_15', 'Bậc thầy rèn',
       'Nâng tổng cộng 15 bậc trang bị.', 15, 90,
       _gear_upgrades, 'forge', 5),

    # Mythic equipment collection.
    _a('forge_mythic', 'Huyền thoại rực lửa',
       'Rèn một món trang bị lên Huyền thoại.', 1, 10,
       _mythic_gear, 'mythic', 1),
    _a('mythic_2', 'Bộ sưu tầm Huyền thoại',
       'Sở hữu 2 món Huyền thoại.', 2, 20,
       _mythic_gear, 'mythic', 2),
    _a('mythic_3', 'Ba món Huyền thoại',
       'Sở hữu 3 món Huyền thoại.', 3, 35,
       _mythic_gear, 'mythic', 3),
    _a('mythic_4', 'Gần đủ Huyền thoại',
       'Sở hữu 4 món Huyền thoại.', 4, 55,
       _mythic_gear, 'mythic', 4),
    _a('mythic_5', 'Toàn bộ Huyền thoại',
       'Sở hữu cả 5 món Huyền thoại.', 5, 90,
       _mythic_gear, 'mythic', 5),

    # Friendship with one villager.
    _a('friend_1', 'Người quen mới',
       'Đạt 1 điểm thân thiết với một dân làng.', 1, 10,
       _friends_best, 'friend', 1),
    _a('friend_3', 'Bạn quen',
       'Đạt 3 điểm thân thiết với một dân làng.', 3, 20,
       _friends_best, 'friend', 2),
    _a('friend_5', 'Người bạn thân',
       'Đạt 5 điểm thân thiết với một dân làng.', 5, 35,
       _friends_best, 'friend', 3),
    _a('friend_7', 'Bạn tri kỷ',
       'Đạt 7 điểm thân thiết với một dân làng.', 7, 55,
       _friends_best, 'friend', 4),
    _a('friend_10', 'Tri kỷ của làng',
       'Đạt 10 điểm thân thiết với một dân làng.', 10, 90,
       _friends_best, 'friend', 5),

    # Friendship across the whole village.
    _a('friend_all_1', 'Một lời chào',
       'Đạt ít nhất 1 điểm thân thiết với tất cả dân làng.', 1, 10,
       _friends_all, 'community', 1),
    _a('friend_all_2', 'Hàng xóm thân thiện',
       'Đạt ít nhất 2 điểm thân thiết với tất cả dân làng.', 2, 20,
       _friends_all, 'community', 2),
    _a('friend_all_3', 'Cả làng quý mến',
       'Đạt ít nhất 3 điểm thân thiết với tất cả dân làng.', 3, 35,
       _friends_all, 'community', 3),
    _a('friend_all_5', 'Người được cả làng nhớ',
       'Đạt ít nhất 5 điểm thân thiết với tất cả dân làng.', 5, 55,
       _friends_all, 'community', 4),
    _a('friend_all_8', 'Trái tim Mossbrook',
       'Đạt ít nhất 8 điểm thân thiết với tất cả dân làng.', 8, 90,
       _friends_all, 'community', 5),

    # Dungeon.
    _a('dungeon_1', 'Bước chân vào Hang Sâu',
       'Hoàn thành tầng đầu tiên của Hang Sâu.', 1, 10,
       lambda farm: farm.dungeon_best, 'dungeon', 1),
    _a('dungeon_2', 'Người đi sâu',
       'Hoàn thành tầng 2 của Hang Sâu.', 2, 20,
       lambda farm: farm.dungeon_best, 'dungeon', 2),
    _a('dungeon_3', 'Vượt ba tầng',
       'Hoàn thành tầng 3 của Hang Sâu.', 3, 35,
       lambda farm: farm.dungeon_best, 'dungeon', 3),
    _a('dungeon_4', 'Gần chạm đáy',
       'Hoàn thành tầng 4 của Hang Sâu.', 4, 55,
       lambda farm: farm.dungeon_best, 'dungeon', 4),
    _a('dungeon_5', 'Chinh phục lòng đất',
       'Hoàn thành toàn bộ 5 tầng Hang Sâu.', 5, 90,
       lambda farm: farm.dungeon_best, 'dungeon', 5),

    # Animals.
    _a('animal_first', 'Người bạn bốn chân',
       'Nuôi vật nuôi đầu tiên.', 1, 10,
       _animals, 'animals', 1),
    _a('animal_2', 'Đàn nhỏ',
       'Nuôi 2 vật nuôi.', 2, 20,
       _animals, 'animals', 2),
    _a('animal_4', 'Nông trại rộn ràng',
       'Nuôi 4 vật nuôi.', 4, 35,
       _animals, 'animals', 3),
    _a('animal_6', 'Chuồng đầy ấm áp',
       'Nuôi 6 vật nuôi.', 6, 55,
       _animals, 'animals', 4),
    _a('animal_8', 'Trang trại sung túc',
       'Nuôi 8 vật nuôi.', 8, 90,
       _animals, 'animals', 5),

    # Fish collection.
    _a('species_1', 'Mẻ cá đầu tiên',
       'Sưu tầm được loài cá đầu tiên.', 1, 10,
       _fish_species, 'species', 1),
    _a('species_2', 'Hai loài mới',
       'Sưu tầm được 2 loài cá.', 2, 20,
       _fish_species, 'species', 2),
    _a('species_3', 'Bộ sưu tầm nhỏ',
       'Sưu tầm được 3 loài cá.', 3, 35,
       _fish_species, 'species', 3),
    _a('species_4', 'Người hiểu hồ',
       'Sưu tầm được 4 loài cá.', 4, 55,
       _fish_species, 'species', 4),
    _a('fish_species_5', 'Bộ sưu tầm sông nước',
       'Sưu tầm được 5 loài cá.', 5, 90,
       _fish_species, 'species', 5),

    # Player level.
    _a('level_2', 'Nông dân tập sự',
       'Đạt cấp 2.', 2, 10,
       lambda farm: farm.level, 'level', 1),
    _a('level_3', 'Nông dân quen việc',
       'Đạt cấp 3.', 3, 20,
       lambda farm: farm.level, 'level', 2),
    _a('level_5', 'Nông dân trưởng thành',
       'Đạt cấp 5.', 5, 35,
       lambda farm: farm.level, 'level', 3),
    _a('level_7', 'Chủ trang trại',
       'Đạt cấp 7.', 7, 55,
       lambda farm: farm.level, 'level', 4),
    _a('level_10', 'Huyền thoại Mossbrook',
       'Đạt cấp 10.', 10, 90,
       lambda farm: farm.level, 'level', 5),
)

ACHIEVEMENT_IDS = tuple(item.id for item in ACHIEVEMENTS)
ACHIEVEMENT_BY_ID = {item.id: item for item in ACHIEVEMENTS}


def tier_name(tier: int) -> str:
    return RARITY_NAMES[max(0, min(len(RARITY_NAMES) - 1, int(tier) - 1))]


def tier_label(tier: int) -> str:
    return f'{tier_name(tier)} ({max(1, min(5, int(tier)))}/5)'


def family_name(family: str) -> str:
    return FAMILY_NAMES.get(family, 'Khác')


def empty_achievements() -> dict[str, bool]:
    return dict.fromkeys(ACHIEVEMENT_IDS, False)


def achievement_rows(farm: 'Farm') -> list[tuple[Achievement, int, bool]]:
    return [(item, min(item.target, item.current(farm)),
             bool(farm.achievements.get(item.id)))
            for item in ACHIEVEMENTS]


def unlocked_count(farm: 'Farm') -> int:
    return sum(bool(farm.achievements.get(item.id)) for item in ACHIEVEMENTS)


def sync_achievements(farm: 'Farm') -> list[Achievement]:
    """Mark milestones that are complete but not yet recorded."""
    if not isinstance(getattr(farm, 'achievements', None), dict):
        farm.achievements = empty_achievements()
    else:
        for item in ACHIEVEMENTS:
            farm.achievements.setdefault(item.id, False)
    unlocked = []
    for item in ACHIEVEMENTS:
        if farm.achievements.get(item.id):
            continue
        if item.current(farm) >= item.target:
            farm.achievements[item.id] = True
            unlocked.append(item)
    return unlocked


def achievement_score(farm: 'Farm') -> int:
    return sum(item.reward for item in ACHIEVEMENTS
               if farm.achievements.get(item.id))


def achievement_lines(farm: 'Farm', *, unicode: bool = True) -> list[str]:
    opened = '✓' if unicode else 'x'
    locked = '○' if unicode else 'o'
    lines = [f'THÀNH TỰU · {unlocked_count(farm)}/{len(ACHIEVEMENTS)}'
             f' · {achievement_score(farm)} điểm']
    for item, current, unlocked in achievement_rows(farm):
        mark = opened if unlocked else locked
        state = 'đã mở khóa' if unlocked else f'{current}/{item.target}'
        lines.append(f'{mark} {item.name} · {tier_label(item.tier)} · '
                     f'{state} · +{item.reward} điểm')
        if not unlocked:
            lines.append(f'   {item.description}')
    return lines
