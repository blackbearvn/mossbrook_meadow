"""Character advancement and shared activity bonuses, without runtime model imports."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .catalog import ITEMS, RARITY_COLORS

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class Definition:
    name: str
    description: str


ATTRIBUTES = {
    'endurance': Definition('Thể lực', '+4 năng lượng tối đa và hồi ngay 4 mỗi bậc (tối đa +20).'),
    'dexterity': Definition('Khéo léo', 'Bậc 1–2 luyện tay; từ bậc 3 giảm 1 sức trồng và thu hoạch (tối thiểu 1); bậc 4–5 giữ hiệu quả này.'),
    'focus': Definition('Tập trung', '+1 XP mỗi lần kiếm kinh nghiệm cho mỗi bậc (tối đa +5).'),
}
SKILLS = {
    'farming': Definition('Trồng trọt', '+10% giá bán nông sản mỗi bậc (tối đa +50%); từ bậc 3 thêm 1 nông sản mỗi ô.'),
    'fishing': Definition('Câu cá', '+0,025 độ rộng thanh câu mỗi bậc; sức câu bậc 1–5: 3/2/2/1/1.'),
    'ranching': Definition('Chăn nuôi', '+10% giá bán trứng, sữa, len mỗi bậc (tối đa +50%); từ bậc 3 thêm 1 sản phẩm mỗi lượt, cộng dồn thân thiết.'),
    'foraging': Definition('Kiếm sống', 'Làm thuê bậc 1–5: xu 8/10/12/14/16; gỗ 1/2/2/3/3; sức 4/3/3/2/2. Nhận 2 XP cơ bản.'),
}


def stat_color(value: int) -> str:
    """Tier colour for a 0-5 attribute or skill rank; 0 stays muted."""
    value = max(0, min(5, int(value)))
    return 'dim' if value == 0 else RARITY_COLORS[value - 1]


def level_color(level: int) -> str:
    """Colour a player level in five broad brackets."""
    bracket = min(4, max(0, (int(level) - 1) // 5))
    return RARITY_COLORS[bracket]


def empty_attributes() -> dict[str, int]:
    return dict.fromkeys(ATTRIBUTES, 0)


def empty_skills() -> dict[str, int]:
    return dict.fromkeys(SKILLS, 0)


def attribute_points(farm: 'Farm') -> int:
    raw = farm.level - 1 - sum(farm.attributes.values())
    return max(0, raw - getattr(farm, 'retired_attribute_points', 0))


def skill_points(farm: 'Farm') -> int:
    raw = 2 * (farm.level - 1) - sum(farm.skills.values())
    return max(0, raw - getattr(farm, 'retired_skill_points', 0))


def energy_limit(farm: 'Farm') -> int:
    return farm.max_energy + 4 * farm.attributes['endurance']


def action_cost(farm: 'Farm', action: str) -> int:
    from .model import GameError

    if action in ('plant', 'harvest'):
        return 1 if farm.attributes['dexterity'] >= 3 else 2
    if action == 'fish':
        return max(1, 3 - farm.skills['fishing'] // 2)
    if action == 'work':
        return max(1, 4 - farm.skills['foraging'] // 2)
    if action in ('water', 'clear'):
        return 1
    raise GameError('Không có thao tác này.')


def sale_price(farm: 'Farm', item_key: str) -> int:
    from .model import GameError

    if item_key not in ITEMS:
        raise GameError('Không có vật phẩm này.')
    rank = 0
    if item_key.startswith('crop:'):
        rank = farm.skills['farming']
    elif item_key in ('egg', 'milk', 'wool', 'fur', 'truffle'):
        rank = farm.skills['ranching']
    return ITEMS[item_key].sell_price * (10 + rank) // 10


def gain_xp(farm: 'Farm', amount: int) -> str:
    from .model import GameError

    if type(amount) is not int or amount < 0:
        raise GameError('Kinh nghiệm phải là số nguyên không âm.')
    if amount == 0:
        return '+0 kinh nghiệm.'
    previous_level = farm.level
    earned = amount + farm.attributes['focus']
    farm.xp += earned
    message = f'+{earned} kinh nghiệm.'
    levels = farm.level - previous_level
    if levels:
        message += (f' LÊN CẤP {farm.level}! Nhận {levels} điểm thuộc tính'
                    f' và {2 * levels} điểm tay nghề. Mở bảng nhân vật để nâng cấp.')
        # If every stat is already maxed, retire any points above the reserve
        # immediately instead of letting the counters grow during a long run.
        retired = settle_excess_points(farm)
        if retired:
            message += f' Điểm dư vượt mức đã đổi thành {retired} xu.'
    return message


def _upgrade(farm: 'Farm', key: str, *, attribute: bool) -> str:
    from .model import GameError

    definitions = ATTRIBUTES if attribute else SKILLS
    values = farm.attributes if attribute else farm.skills
    points = attribute_points(farm) if attribute else skill_points(farm)
    if key not in definitions:
        raise GameError('Không có thuộc tính hoặc tay nghề này.')
    if values[key] >= 5:
        raise GameError(f'{definitions[key].name} đã đạt bậc tối đa 5.')
    if points < 1:
        raise GameError('Chưa đủ điểm nâng cấp. Hãy kiếm XP để lên cấp.')
    values[key] += 1
    if attribute and key == 'endurance':
        farm.energy = min(energy_limit(farm), farm.energy + 4)
    from .tutorial import record_event
    tutorial_message = record_event(farm, 'upgrade')
    return (f'{definitions[key].name} tăng lên bậc {values[key]}/5. (-1 điểm)'
            + (f' {tutorial_message}' if tutorial_message else ''))


def upgrade_attribute(farm: 'Farm', key: str) -> str:
    return _upgrade(farm, key, attribute=True)


def upgrade_skill(farm: 'Farm', key: str) -> str:
    return _upgrade(farm, key, attribute=False)


POINT_SOFT_CAP = 99
POINT_EXCHANGE = {'attribute': 20, 'skill': 10}


def _all_maxed(values: dict[str, int], maximum: int = 5) -> bool:
    return bool(values) and all(value >= maximum for value in values.values())


def settle_excess_points(farm: 'Farm') -> int:
    """Keep a small reserve when every stat is maxed; exchange the rest.

    A long-lived farm can reach a level far beyond the five ranks available in
    each attribute and skill.  Without a sink the derived point counters grow
    forever.  While every definition is maxed, points above the reserve are
    retired to coins once and recorded on the farm, so loading and saving the
    same file is stable.
    """
    if not (_all_maxed(farm.attributes) and _all_maxed(farm.skills)):
        return 0
    earned = 0
    for kind, values, retired_name in (
        ('attribute', farm.attributes, 'retired_attribute_points'),
        ('skill', farm.skills, 'retired_skill_points'),
    ):
        available = attribute_points(farm) if kind == 'attribute' else skill_points(farm)
        excess = max(0, available - POINT_SOFT_CAP)
        if excess:
            setattr(farm, retired_name, getattr(farm, retired_name, 0) + excess)
            earned += excess * POINT_EXCHANGE[kind]
    farm.coins += earned
    return earned


def exchange_points(farm: 'Farm') -> str:
    """Player-triggered exchange of the remaining reserve into coins."""
    from .model import GameError

    if not (_all_maxed(farm.attributes) and _all_maxed(farm.skills)):
        raise GameError('Chỉ có thể đổi điểm dư khi mọi thuộc tính và tay nghề đã đạt bậc 5.')
    total = attribute_points(farm) * POINT_EXCHANGE['attribute']
    total += skill_points(farm) * POINT_EXCHANGE['skill']
    if not total:
        raise GameError('Không còn điểm dư để đổi.')
    farm.coins += total
    farm.retired_attribute_points += attribute_points(farm)
    farm.retired_skill_points += skill_points(farm)
    return f'Đã đổi toàn bộ điểm dư thành {total} xu.'


def character_lines(farm: 'Farm') -> list[str]:
    from .identity import BACKGROUNDS, OUTFITS
    lines = [f'{farm.avatar} {farm.player_name} · Nông trại {farm.name} · Cấp {farm.level} · XP {farm.xp} ({farm.xp % 40}/40 đến cấp tiếp)',
             f'Năng lượng {farm.energy}/{energy_limit(farm)} · Máu {farm.hp}/{farm.max_hp}',
             f'Còn {attribute_points(farm)} điểm thuộc tính, {skill_points(farm)} điểm tay nghề.',
             ('Đã tối đa mọi bậc; X đổi điểm dư thành xu.'
              if _all_maxed(farm.attributes) and _all_maxed(farm.skills)
              else 'Mỗi lần lên cấp: +1 điểm thuộc tính, +2 điểm tay nghề.'),
             'Mỗi lần nâng tốn 1 điểm tương ứng; tối đa bậc 5.',
             f'Xuất thân: {BACKGROUNDS[farm.background]} · Áo: {OUTFITS[farm.outfit]}']
    retired_attributes = getattr(farm, 'retired_attribute_points', 0)
    retired_skills = getattr(farm, 'retired_skill_points', 0)
    if retired_attributes or retired_skills:
        lines.append(f'Điểm dư đã đổi: {retired_attributes} thuộc tính, '
                     f'{retired_skills} tay nghề.')
    for definitions, values in ((ATTRIBUTES, farm.attributes), (SKILLS, farm.skills)):
        for key, definition in definitions.items():
            lines.append(f'{definition.name}: {values[key]}/5 — {definition.description}')
    from .catalog import GEAR
    from .forge import tier_label
    for key, info in GEAR.items():
        lines.append(f'{info.name}: {tier_label(farm.gear.get(key, 0))} — {info.effect}')
    lines.append(f'Hang Sâu: kỷ lục tầng {farm.dungeon_best}/5.')
    return lines
