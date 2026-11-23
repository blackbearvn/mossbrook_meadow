"""Turn-based dungeon encounters below the mine.

A run is session state: leaving the game or closing the dungeon abandons the
current floor, while the deepest cleared floor is stored on the farm.  Combat
is deterministic apart from the fixed turn counter, which keeps it testable
and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .forge import attack_power, defense_power

if TYPE_CHECKING:
    from .model import Farm


MAX_DEPTH = 5
POTION_HEAL = 12


@dataclass(frozen=True, slots=True)
class Monster:
    key: str
    name: str
    glyph: str
    ascii_glyph: str
    hp: int
    attack: int
    xp: int
    coins: int
    drops: dict[str, int]
    hint: str


MONSTERS = {
    'slime': Monster(
        'slime', 'Nhớt Xanh', 's', 's', 12, 3, 8, 12,
        {'da': 2}, 'Chậm chạp nhưng dai, thích hợp cho người mới.'),
    'bat': Monster(
        'bat', 'Dơi Hang', 'b', 'b', 9, 5, 10, 14,
        {'quang_dong': 1}, 'Bay nhanh, đánh đau; hạ nó trước khi bị vây.'),
    'golem': Monster(
        'golem', 'Thạch Yêu', 'g', 'G', 28, 8, 22, 35,
        {'quang_sat': 2}, 'Lớp đá dày cần kiếm tốt mới xuyên qua.'),
    'wisp': Monster(
        'wisp', 'Ma Trơi', 'w', 'w', 18, 10, 18, 28,
        {'quang_vang': 1}, 'Ánh sáng xanh dụ dỗ; giáp tốt giúp chịu đòn.'),
    'boss': Monster(
        'boss', 'Hang Chúa', '@', '&', 60, 14, 60, 120,
        {'kim_cuong': 2, 'quang_vang': 2},
        'Chúa tể tầng cuối, canh giữ tinh thể hang sâu.'),
}

FLOOR_PLAN = (
    ('slime', 'bat', 'slime'),
    ('bat', 'slime', 'golem'),
    ('golem', 'wisp', 'bat'),
    ('wisp', 'golem', 'golem'),
    ('boss',),
)


@dataclass(slots=True)
class Enemy:
    key: str
    name: str
    hp: int
    max_hp: int
    attack: int
    xp: int
    coins: int
    drops: dict[str, int]

    @property
    def glyph(self) -> str:
        return MONSTERS[self.key].glyph

    @property
    def ascii_glyph(self) -> str:
        return MONSTERS[self.key].ascii_glyph

    @property
    def hint(self) -> str:
        return MONSTERS[self.key].hint


@dataclass(slots=True)
class DungeonRun:
    depth: int = 1
    enemies: list[Enemy] = field(default_factory=list)
    index: int = 0
    turn: int = 0
    phase: str = 'battle'  # battle | floor | done | defeated | fled
    log: list[str] = field(default_factory=list)
    total_xp: int = 0
    total_coins: int = 0
    loot: dict[str, int] = field(default_factory=dict)

    @property
    def finished(self) -> bool:
        return self.phase in ('done', 'defeated', 'fled')

    def current(self) -> Enemy | None:
        if 0 <= self.index < len(self.enemies):
            return self.enemies[self.index]
        return None

    def say(self, message: str) -> None:
        if message:
            self.log.append(message)
            del self.log[:-40]


def _enemy(key: str, depth: int) -> Enemy:
    base = MONSTERS[key]
    hp = base.hp + (depth - 1) * 6
    attack = base.attack + (depth - 1)
    return Enemy(
        key=key,
        name=base.name,
        hp=hp,
        max_hp=hp,
        attack=attack,
        xp=base.xp + depth,
        coins=base.coins + depth * 4,
        drops=dict(base.drops),
    )


def floor_plan(depth: int) -> tuple[str, ...]:
    return FLOOR_PLAN[max(0, min(len(FLOOR_PLAN), depth) - 1)]


def start_run(farm: 'Farm') -> DungeonRun:
    """Create a fresh run at floor one; the farm only needs a real sword."""
    from .model import GameError

    if farm.gear.get('sword', 0) < 1:
        raise GameError('Cần rèn ít nhất một thanh kiếm ở lò rèn trước khi vào hang sâu.')
    if farm.hp < 2:
        raise GameError('Bạn quá yếu để vào hang. Hãy ngủ hoặc uống thuốc hồi sức.')
    run = DungeonRun(depth=1, enemies=[_enemy(key, 1) for key in floor_plan(1)])
    run.say(f'Bước vào Hang Sâu tầng 1. {len(run.enemies)} quái vật đang chờ.')
    return run


def _award(farm: 'Farm', run: DungeonRun, enemy: Enemy) -> str:
    farm.coins += enemy.coins
    run.total_coins += enemy.coins
    for item, amount in enemy.drops.items():
        farm.items[item] = farm.items.get(item, 0) + amount
        run.loot[item] = run.loot.get(item, 0) + amount
    xp_message = farm.award_xp(enemy.xp)
    run.total_xp += enemy.xp
    from .catalog import ITEMS
    drop_text = ', '.join(f'{amount} {ITEMS[item].name}'
                          for item, amount in enemy.drops.items())
    return (f'Hạ {enemy.name}: +{enemy.coins} xu, +{drop_text}, {xp_message}')


def _enemy_attack(farm: 'Farm', run: DungeonRun) -> str:
    enemy = run.current()
    if enemy is None:
        return ''
    raw = max(1, enemy.attack - defense_power(farm))
    farm.hp = max(0, farm.hp - raw)
    if farm.hp <= 0:
        lost = min(farm.coins, max(1, farm.coins // 10))
        farm.coins -= lost
        farm.hp = 1
        run.phase = 'defeated'
        return f'{enemy.name} quật ngã bạn. Mất {lost} xu; bạn tỉnh dậy ở cửa mỏ.'
    return f'{enemy.name} phản đòn, bạn mất {raw} máu.'


def player_attack(farm: 'Farm', run: DungeonRun) -> str:
    """Attack the current enemy and let it retaliate while it lives."""
    from .model import GameError

    if run.phase != 'battle':
        raise GameError('Không có trận đánh nào đang diễn ra.')
    enemy = run.current()
    if enemy is None:
        raise GameError('Không còn quái vật trong tầng này.')
    variance = (run.turn * 3 + run.depth) % 3
    damage = max(1, attack_power(farm) - (run.depth - 1) + variance)
    enemy.hp = max(0, enemy.hp - damage)
    run.turn += 1
    attack_text = f'Bạn đánh {enemy.name} mất {damage} máu.'
    run.say(attack_text)
    if enemy.hp <= 0:
        award_text = _award(farm, run, enemy)
        run.say(award_text)
        run.index += 1
        if run.index >= len(run.enemies):
            run.phase = 'floor'
            farm.dungeon_best = max(farm.dungeon_best, run.depth)
            if run.depth >= MAX_DEPTH:
                run.phase = 'done'
                bonus = 200
                farm.coins += bonus
                farm.dungeon_best = MAX_DEPTH
                run.say(f'Bạn chinh phục Hang Sâu! Thưởng thêm {bonus} xu.')
            else:
                run.say(f'Tầng {run.depth} đã sạch. Có thể xuống tầng tiếp theo.')
        else:
            next_enemy = run.current()
            if next_enemy is not None:
                run.say(f'{next_enemy.name} lao tới!')
        return award_text
    counter = _enemy_attack(farm, run)
    run.say(counter)
    return f'{attack_text} {counter}'


def use_potion(farm: 'Farm', run: DungeonRun) -> str:
    """Drink one potion; the enemy still gets its turn."""
    from .model import GameError

    if not run.finished and farm.hp >= farm.max_hp:
        raise GameError('Máu đang đầy, chưa cần uống thuốc.')
    if farm.items.get('thuoc', 0) < 1:
        raise GameError('Túi không có thuốc hồi sức. Mua ở chợ hoặc chế ở lò rèn.')
    if run.finished:
        raise GameError('Trận đánh đã kết thúc.')
    farm.items['thuoc'] -= 1
    healed = min(POTION_HEAL, farm.max_hp - farm.hp)
    farm.hp += healed
    heal_text = f'Uống thuốc hồi {healed} máu.'
    run.say(heal_text)
    if run.phase == 'battle':
        counter = _enemy_attack(farm, run)
        run.say(counter)
        return f'{heal_text} {counter}'
    return heal_text


def advance(farm: 'Farm', run: DungeonRun) -> str:
    """Go down one floor after clearing the current one."""
    from .model import GameError

    if run.phase != 'floor':
        raise GameError('Hãy dọn sạch tầng hiện tại trước.')
    if run.depth >= MAX_DEPTH:
        raise GameError('Bạn đã ở tầng sâu nhất của hang.')
    run.depth += 1
    run.enemies = [_enemy(key, run.depth) for key in floor_plan(run.depth)]
    run.index = 0
    run.phase = 'battle'
    heal = max(4, farm.max_hp // 4)
    farm.hp = min(farm.max_hp, farm.hp + heal)
    run.say(f'Xuống tầng {run.depth}. Hồi {heal} máu; {len(run.enemies)} quái vật xuất hiện.')
    return run.log[-1]


def flee(farm: 'Farm', run: DungeonRun) -> str:
    if run.finished:
        return 'Bạn đã rời hang.'
    run.phase = 'fled'
    run.say('Bạn rút lui khỏi hang. Chiến lợi phẩm đã nhặt vẫn được giữ.')
    return run.log[-1]


def status_lines(farm: 'Farm', run: DungeonRun, *, unicode: bool = True) -> list[str]:
    full, empty = ('▰', '▱') if unicode else ('#', '-')
    rows = [f'Hang Sâu · tầng {run.depth}/{MAX_DEPTH} · '
            f'máu {farm.hp}/{farm.max_hp} · kiếm {farm.gear.get("sword", 0)}/5'
            f' · giáp {farm.gear.get("armor", 0)}/5']
    enemy = run.current()
    if run.phase == 'battle' and enemy is not None:
        width = 12
        filled = max(0, min(width, round(width * enemy.hp / max(1, enemy.max_hp))))
        rows.append(f'{enemy.name} · {full * filled}{empty * (width - filled)} '
                    f'{enemy.hp}/{enemy.max_hp}')
        rows.append(enemy.hint)
    elif run.phase == 'floor':
        rows.append('Tầng đã sạch. Chọn xuống tầng tiếp theo hoặc trở về.')
    elif run.phase == 'done':
        rows.append(f'Chinh phục hoàn toàn! Kỷ lục tầng {farm.dungeon_best}/{MAX_DEPTH}.')
    elif run.phase == 'defeated':
        rows.append('Bạn đã gục ngã. Hãy hồi sức trước khi quay lại.')
    return rows
