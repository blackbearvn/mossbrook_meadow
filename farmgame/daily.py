"""Daily action goals and manually claimed rewards, without UI dependencies."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .catalog import CROPS, FISH_TYPES, MAX_GEAR

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class QuestDefinition:
    name: str
    target: int
    coins: int
    xp: int


QUESTS = {
    'plant': QuestDefinition('Trồng cây', 3, 15, 3),
    'water': QuestDefinition('Tưới cây', 3, 12, 3),
    'harvest': QuestDefinition('Thu hoạch nông sản', 1, 18, 4),
    'work': QuestDefinition('Giúp hàng xóm nhặt củi', 2, 12, 3),
    'fish': QuestDefinition('Câu được cá', 1, 15, 4),
    'talk': QuestDefinition('Hỏi thăm người dân', 2, 10, 3),
    'sell': QuestDefinition('Bán hàng kiếm xu', 40, 15, 3),
    'feed': QuestDefinition('Cho vật nuôi ăn', 1, 10, 2),
    'pet': QuestDefinition('Vuốt ve vật nuôi', 1, 8, 2),
    'collect': QuestDefinition('Lấy sản phẩm vật nuôi', 1, 12, 3),
    'clear': QuestDefinition('Dọn cây héo', 1, 10, 2),
    'buy': QuestDefinition('Mua hạt giống', 3, 10, 2),
    'upgrade': QuestDefinition('Nâng cấp nông trại', 1, 20, 5),
    'catch_new': QuestDefinition('Câu loài cá mới', 1, 25, 5),
    'sell_fish': QuestDefinition('Bán cá cho chợ', 2, 18, 4),
    'mine': QuestDefinition('Đào khoáng sản', 2, 16, 4),
    'forge': QuestDefinition('Rèn trang bị', 1, 20, 5),
    'cook': QuestDefinition('Nấu một món ăn', 1, 16, 4),
    'dungeon': QuestDefinition('Hạ quái trong Hang Sâu', 1, 25, 6),
    'animal': QuestDefinition('Mua vật nuôi mới', 1, 20, 4),
}


@dataclass(slots=True)
class DailyQuest:
    kind: str
    target: int
    progress: int = 0
    claimed: bool = False


@dataclass(slots=True)
class DailyState:
    day: int = 0
    tasks: list[DailyQuest] = field(default_factory=list)


def ensure_daily(farm: 'Farm') -> DailyState:
    """Create four goals once per day; opening the board never rerolls them.

    Rotation uses only the day and available activities, without consuming the
    weather or fishing random stream. Targets fit the field's usable space.
    """
    if farm.daily.day == farm.day and farm.daily.tasks:
        return farm.daily

    plantable = sum(not plot.crop or plot.dead or plot.ready
                    for plot in farm.plots.values())
    waterable = plantable + sum(bool(plot.crop) and not plot.dead
                               and not plot.ready and not plot.watered
                               for plot in farm.plots.values())
    available = dict.fromkeys(QUESTS, True)
    available['plant'] = bool(plantable)
    available['water'] = (bool(waterable) and farm.weather != 'rainy'
                          and not farm.sprinkler)
    available['harvest'] = any(plot.ready for plot in farm.plots.values())
    available['feed'] = any(not animal.fed for animal in farm.animals)
    available['pet'] = any(not animal.petted for animal in farm.animals)
    available['collect'] = any(animal.produce for animal in farm.animals)
    available['clear'] = any(plot.dead for plot in farm.plots.values())
    available['buy'] = any(crop.level <= farm.level for crop in CROPS.values())
    available['upgrade'] = (farm.size < 6 or farm.max_energy < 30
                            or not farm.sprinkler or farm.barn_capacity < 8)
    available['catch_new'] = any(
        farm.fish_collection.get(key, 0) == 0 and info.level <= farm.level
        for key, info in FISH_TYPES.items())
    available['sell_fish'] = any(farm.items.get(key, 0) for key in FISH_TYPES)
    available['forge'] = any(farm.gear.get(key, 0) < MAX_GEAR for key in farm.gear)
    from .cooking import RECIPES
    available['cook'] = any(recipe.level <= farm.level
                            for recipe in RECIPES.values())
    available['dungeon'] = (farm.gear.get('sword', 0) >= 1
                            and farm.hp >= 2)
    from .animals import ANIMAL_TYPES, zone_for
    available['animal'] = (len(farm.animals) < farm.barn_capacity
                           and any(farm.level >= zone_for(kind).level
                                   and farm.coins >= info.price
                                   for kind, info in ANIMAL_TYPES.items()))
    kinds = [kind for kind in QUESTS if available[kind]]
    offset = (farm.day - 1) % len(kinds)
    selected = (kinds[offset:] + kinds[:offset])[:4]
    targets = {'plant': plantable, 'water': waterable}
    farm.daily = DailyState(farm.day, [
        DailyQuest(kind, min(QUESTS[kind].target,
                             targets.get(kind, QUESTS[kind].target)))
        for kind in selected
    ])
    return farm.daily


def record_daily(farm: 'Farm', kind: str, amount: int = 1) -> None:
    """Count a completed action; callers validate and perform the action first."""
    if kind not in QUESTS or type(amount) is not int or amount < 1:
        return
    for task in ensure_daily(farm).tasks:
        if task.kind == kind and not task.claimed:
            task.progress = min(task.target, task.progress + amount)


def claim_quest(farm: 'Farm', index: int) -> str:
    """Claim one completed goal using a zero-based board index."""
    from .model import GameError

    if type(index) is not int or not 0 <= index < 4:
        raise GameError('Nhiệm vụ không hợp lệ. Chọn từ 1 đến 4.')
    if farm.daily.day != farm.day or not farm.daily.tasks:
        raise GameError('Nhiệm vụ chưa hoàn thành.')
    task = farm.daily.tasks[index]
    if task.claimed:
        raise GameError('Bạn đã nhận thưởng nhiệm vụ này rồi.')
    if task.progress < task.target:
        raise GameError('Nhiệm vụ chưa hoàn thành.')
    definition = QUESTS[task.kind]
    task.claimed = True
    farm.coins += definition.coins
    xp_message = farm.award_xp(definition.xp)
    return f'{definition.name}: nhận {definition.coins} xu, {xp_message}'


def claim_all(farm: 'Farm') -> str:
    """Claim every available reward once; safe to call with nothing ready."""
    messages = [claim_quest(farm, index)
                for index, task in enumerate(ensure_daily(farm).tasks)
                if task.progress >= task.target and not task.claimed]
    return ' '.join(messages) or 'Chưa có nhiệm vụ hoàn thành để nhận thưởng.'


def daily_lines(farm: 'Farm') -> list[str]:
    board = ensure_daily(farm)
    lines = [f'NHIỆM VỤ NGÀY {board.day} · Đổi nhiệm vụ sau khi ngủ.']
    for index, task in enumerate(board.tasks, 1):
        definition = QUESTS[task.kind]
        if task.claimed:
            status = 'Đã nhận'
        elif task.progress >= task.target:
            status = 'Nhận thưởng'
        else:
            status = 'Đang làm'
        unit = ' xu' if task.kind == 'sell' else ''
        lines.append(f'{index}. {definition.name}: {task.progress}/{task.target}{unit}'
                     f' · {definition.coins} xu + {definition.xp} XP · {status}')
    return lines
