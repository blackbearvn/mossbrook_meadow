"""An interruptible farmer that uses the same actions as manual play.

The controller has no clock, terminal, or persistence dependency. A runtime
calls ``step`` once per tick and owns input, rendering, and saving. Paths are
consumed from a deque; moving along a route does not run another search.
"""

from collections import deque
from dataclasses import dataclass
import random

from . import world
from .animals import (ANIMAL_TYPES, buy_animal, buy_feed, collect_products,
                      feed_animals, pet_animal, zone_animals, zone_for)
from .catalog import CROPS, EXTRA_ITEMS, GEAR
from .cooking import RECIPES, can_cook, cook
from .daily import claim_all, ensure_daily
from .dialogue import (BRANCHING_NPC_IDS, begin_dialogue, choose_response,
                       dialogue_node)
from .dungeon import (MAX_DEPTH, advance, flee, player_attack,
                      start_run, use_potion)
from .forge import (forge, mining_energy_cost, missing_for,
                    recipe_for)
from .fishing import finish_fishing, start_fishing
from .inventory import inventory_rows
from .mining import mine_rock, rock_exhausted
from .model import Farm, GameError
from .navigation import route
from .progression import (action_cost, character_lines, upgrade_attribute,
                          upgrade_skill)
from .tutorial import current_step, record_event, sync_tutorial
from .villagers import NPCS, npc_at


@dataclass(frozen=True, slots=True)
class AutoOptions:
    mode: str = 'all'
    days: int = 1

    def __post_init__(self):
        if (not isinstance(self.mode, str)
                or self.mode not in ('all', 'farm', 'ranch', 'fish', 'mine', 'dungeon')):
            raise ValueError('Chế độ auto phải là all, farm, ranch, fish, mine hoặc dungeon.')
        if type(self.days) is not int or self.days < 0:
            raise ValueError('Số ngày auto phải là số nguyên không âm; 0 là liên tục.')


@dataclass(frozen=True, slots=True)
class AutoResult:
    message: str
    changed: bool = False
    moved: bool = False
    done: bool = False


@dataclass(frozen=True, slots=True)
class _Intent:
    action: str
    area: str = ''
    target: tuple[int, int] | None = None
    kind: str = ''
    args: tuple = ()


class Automation:
    """Plan work, then perform at most one move/action/physics tick per step."""

    # Normal days need hundreds of ticks, including the fishing simulation.
    # An unusual map or repeatedly changing goal gets one bounded trip home.
    _DAY_STEP_LIMIT = 4000
    _HOME_STEP_LIMIT = 512
    _SPECIALIST_RESERVE = 100
    _DIRECTIONS = {(0, -1): 'up', (0, 1): 'down',
                   (-1, 0): 'left', (1, 0): 'right'}
    KEEP_FOR_CRAFTING = frozenset(('da', 'quang_dong', 'quang_sat',
                                   'quang_vang', 'kim_cuong', 'thuoc'))

    def __init__(self, farm: Farm, options: AutoOptions, rng=None):
        self.farm = farm
        self.options = options
        self.rng = rng if rng is not None else random.Random()
        self.paused = False
        self.fishing_round = None
        self.dungeon_run = None
        self._dungeon_daily = False
        self._conversation = None
        self._start_day = farm.day
        self._start_harvested = farm.harvested
        self._start_fish = farm.fish_caught
        self._start_sales = farm.sales
        self._start_best = farm.dungeon_best
        self._mined_total = 0
        self._day = farm.day
        self._day_steps = 0
        self._resting = False
        self._done = False
        self._intent = None
        self._intent_state = None
        self._path = deque()
        self._expected_position = None
        self._routed = False
        self._blocked = 0
        self._message = 'Auto đã sẵn sàng.'

    @property
    def done(self) -> bool:
        return self._done

    @property
    def summary(self) -> str:
        elapsed = max(0, self.farm.day - self._start_day)
        duration = 'liên tục' if not self.options.days else str(self.options.days)
        status = 'đã dừng' if self.done else ('tạm dừng' if self.paused else 'đang chạy')
        extra = f' · quặng {self._mined_total}' if self._mined_total else ''
        if self.farm.dungeon_best > self._start_best:
            extra += f' · hang tầng {self.farm.dungeon_best}'
        tasks = self.farm.daily.tasks
        if tasks:
            done = sum(task.claimed or task.progress >= task.target
                       for task in tasks)
            extra += f' · việc ngày {done}/{len(tasks)}'
        return (f'Auto {status} · {elapsed}/{duration} ngày · '
                f'thu hoạch {self.farm.harvested - self._start_harvested} · '
                f'cá {self.farm.fish_caught - self._start_fish} · '
                f'bán {self.farm.sales - self._start_sales} xu{extra} · {self._message}')

    @property
    def current_task(self) -> str:
        if self.dungeon_run is not None:
            run = self.dungeon_run
            phase = {'battle': 'chiến đấu', 'floor': 'chọn tầng',
                     'done': 'hoàn tất', 'defeated': 'thua',
                     'fled': 'rút lui'}.get(run.phase, run.phase)
            return f'Hang Sâu tầng {run.depth} · {phase}'
        if self.fishing_round is not None:
            return 'Đang câu cá'
        if self._conversation is not None:
            return 'Đang trò chuyện'
        intent = self._intent
        if intent is None:
            return 'Đang chọn việc'
        labels = {
            'plant': 'Gieo hạt', 'water': 'Tưới cây', 'harvest': 'Thu hoạch',
            'clear': 'Dọn cây', 'work': 'Làm thuê', 'sleep': 'Về nhà ngủ',
            'upgrade': 'Nâng cấp', 'buy': 'Mua hạt', 'buy_feed': 'Mua thức ăn',
            'buy_potion': 'Mua thuốc', 'sell_keep': 'Bán nông sản',
            'sell': 'Bán hàng', 'feed': 'Cho vật nuôi ăn', 'pet': 'Vuốt ve',
            'collect': 'Thu sản phẩm', 'animal': 'Mua vật nuôi',
            'attribute': 'Nâng thuộc tính', 'skill': 'Nâng tay nghề',
            'claim': 'Nhận thưởng', 'fish': 'Câu cá', 'talk': 'Trò chuyện',
            'mine_rock': 'Đào quặng', 'forge': 'Rèn trang bị',
            'cook': 'Nấu ăn', 'enter_mine': 'Đi tới mỏ',
            'dungeon': 'Vào Hang Sâu',
            'enter_home': 'Vào nhà', 'movement': 'Đi bộ',
        }
        return labels.get(intent.action, intent.action.replace('_', ' ').title())

    def path_points(self) -> set[tuple[int, int]]:
        return set(self._path)

    def stop(self) -> None:
        self._done = True
        self._message = 'Đã dừng auto. Bạn tiếp tục điều khiển thủ công.'
        self.fishing_round = None
        self.dungeon_run = None
        self._dungeon_daily = False
        self._conversation = None
        self._clear_intent()

    def _position(self):
        farm = self.farm
        return farm.area, farm.player_x, farm.player_y, farm.facing, farm.size

    def _state(self):
        """Persistent non-movement state, also detecting edits while paused."""
        farm = self.farm
        tutorial = farm.tutorial
        daily = farm.daily
        return (
            farm.day, farm.area, farm.size, farm.energy, farm.max_energy,
            farm.coins, farm.xp, farm.weather, farm.forecast, farm.sprinkler,
            farm.harvested, farm.sales, farm.fish_caught, farm.barn_capacity,
            farm.hp, tuple(farm.gear.items()), tuple(farm.mine_used.items()),
            farm.dungeon_best,
            tuple(farm.seeds.items()), tuple(farm.produce.items()),
            tuple(farm.items.items()), tuple(farm.attributes.items()),
            tuple(farm.skills.items()), tuple(farm.friendships.items()),
            tuple(farm.talked_on.items()),
            tuple((key, p.crop, p.growth, p.watered, p.dry_days, p.dead)
                  for key, p in farm.plots.items()),
            tuple((a.kind, a.name, a.age, a.fed, a.petted, a.friendship,
                   a.produce, a.days_since_product) for a in farm.animals),
            (tutorial.status, tutorial.step, tutorial.moves, tutorial.plot,
             tutorial.planted_on, tutorial.watered_on, tutorial.reward_given),
            (daily.day, tuple((q.kind, q.target, q.progress, q.claimed)
                              for q in daily.tasks)),
        )

    def _clear_intent(self):
        self._intent = None
        self._intent_state = None
        self._path.clear()
        self._routed = False
        self._expected_position = None

    def _result(self, message, before, *, moved=False):
        if self.farm.day != self._day:
            self._day = self.farm.day
            self._day_steps = 0
            self._resting = False
            self._blocked = 0
        if self.options.days and self.farm.day - self._start_day >= self.options.days:
            self._done = True
            message += f' Đã hoàn tất {self.options.days} ngày auto.'
        self._message = message
        if self._done:
            self._clear_intent()
        elif self._intent is not None:
            self._intent_state = self._state()
        return AutoResult(message, changed=before != self._state(), moved=moved, done=self._done)

    def step(self) -> AutoResult:
        if self.done:
            return AutoResult(self._message, done=True)
        if self.paused:
            return AutoResult('Auto tạm dừng. Space/P để tiếp tục.')
        before = self._state()
        try:
            ensure_daily(self.farm)
            if self.options.days and self.farm.day - self._start_day >= self.options.days:
                return self._result('Đã chạy đủ số ngày đã chọn.', before)
            self._day_steps += 1
            if self._day_steps > self._DAY_STEP_LIMIT + self._HOME_STEP_LIMIT:
                raise GameError('Không thể hoàn thành đường về nhà trong giới hạn auto.')
            if self._day_steps > self._DAY_STEP_LIMIT and not self._resting:
                self._resting = True
                self._clear_intent()
            if self.fishing_round is not None:
                return self._fish_step(before)
            if self.dungeon_run is not None:
                return self._dungeon_step(before)
            if self._conversation is not None:
                return self._talk_step(before)
            message = sync_tutorial(self.farm)
            if message:
                self._clear_intent()
                return self._result(message, before)
            if self._intent is not None and self._intent_state != self._state():
                self._clear_intent()
            if self._intent is None:
                self._intent = self._choose_intent()
                self._intent_state = self._state()
            return self._follow_intent(before)
        except Exception as error:
            self._done = True
            self.fishing_round = None
            self.dungeon_run = None
            self._dungeon_daily = False
            self._conversation = None
            return self._result(f'Auto dừng vì lỗi: {error}', before)

    @staticmethod
    def _plot_point(coordinate):
        return (world.FIELD_ORIGIN[0] + ord(coordinate[0]) - ord('A'),
                world.FIELD_ORIGIN[1] + int(coordinate[1:]) - 1)

    def _nearest_plot(self, predicate, *, urgent=False):
        farm = self.farm
        return min((key for key, plot in farm.plots.items() if predicate(key, plot)),
                   key=lambda key: (-farm.plots[key].dry_days if urgent else 0,
                                    abs(self._plot_point(key)[0] - farm.player_x)
                                    + abs(self._plot_point(key)[1] - farm.player_y), key),
                   default=None)

    def _plot_action(self, action, coordinate, *args):
        return _Intent(action, 'village', self._plot_point(coordinate),
                       'plot', (coordinate, *args))

    @staticmethod
    def _shop(action, *args):
        return _Intent(action, 'village', world.SHOP_DOOR, 'shop', args)

    @staticmethod
    def _barn(action, *args):
        return _Intent(action, 'village', world.BARN_DOOR, 'barn', args)

    @staticmethod
    def _sleep_intent():
        return _Intent('sleep', 'home', world.BED, 'bed')

    @staticmethod
    def _work_intent():
        return _Intent('work', 'village', (9, 13), 'forest')

    @staticmethod
    def _fish_intent():
        return _Intent('fish', 'village', (25, 8), 'water')

    @staticmethod
    def _talk_intent(npc_id, action='talk'):
        return _Intent(action, 'village', NPCS[npc_id].position, 'npc', (npc_id,))

    def _sellable(self):
        return (any(self.farm.produce.values())
                or any(count and EXTRA_ITEMS[key].sell_price
                       and key not in self.KEEP_FOR_CRAFTING
                       for key, count in self.farm.items.items()))

    def _sell_intent(self):
        return _Intent('sell_keep')

    def _forge_intent(self, slots=('hat',)):
        for key in slots:
            recipe = recipe_for(self.farm, key)
            if recipe is not None and not missing_for(self.farm, key, recipe):
                return _Intent('forge', 'mine', world.MINE_FORGE, 'forge', (key,))
        return None

    def _mine_intent(self, *, forge_slots=('hat',)):
        farm = self.farm
        cost = mining_energy_cost(farm)
        if farm.area != 'mine':
            if farm.energy < cost:
                return self._sleep_intent()
            return _Intent('enter_mine', 'village', world.MINE_DOOR, 'mine')
        forging = self._forge_intent(forge_slots)
        if forging is not None:
            return forging
        if farm.energy < cost:
            return self._sleep_intent()
        rocks = [(x, y) for x, y in world.MINE_ROCKS
                 if not rock_exhausted(farm, x, y)]
        if not rocks:
            return self._sleep_intent()
        point = min(rocks, key=lambda p: (abs(p[0] - farm.player_x)
                                          + abs(p[1] - farm.player_y), p[1], p[0]))
        return _Intent('mine_rock', 'mine', point, 'rock', point)

    def _dungeon_intent(self, *, daily=False):
        farm = self.farm
        if (not daily and farm.dungeon_best >= MAX_DEPTH
                and farm.gear.get('sword', 0) >= 3):
            return self._sleep_intent()
        if farm.hp < max(3, farm.max_hp // 3):
            return self._sleep_intent()
        if farm.gear.get('sword', 0) < 1:
            return self._mine_intent(forge_slots=('hat', 'sword', 'armor'))
        if (farm.items.get('thuoc', 0) < 2
                and farm.coins >= 2 * EXTRA_ITEMS['thuoc'].buy_price):
            return self._shop('buy_potion', 2)
        if farm.area != 'mine':
            return _Intent('enter_mine', 'village', world.MINE_DOOR, 'mine')
        forging = self._forge_intent(('sword', 'armor', 'pants', 'shoes'))
        if forging is not None:
            return forging
        return _Intent('dungeon', 'mine', world.DUNGEON_GATE, 'dungeon_gate')

    def _daily_left(self, kind):
        return max((max(0, q.target - q.progress) for q in self.farm.daily.tasks
                    if q.kind == kind and not q.claimed), default=0)

    def _daily_intent(self):
        """Work through today's board before optional farm chores.

        The daily board can ask for activities outside the normal ``all`` loop
        (mining, forging, cooking, a dungeon kill or buying an animal).  These
        are real game actions with the usual travel, energy and item costs, not
        shortcuts.  Impossible goals simply fall through to the next one.
        """
        farm = self.farm
        if self._daily_left('harvest'):
            ready = self._nearest_plot(lambda _key, plot: plot.ready)
            if ready and farm.energy >= action_cost(farm, 'harvest'):
                return self._plot_action('harvest', ready)
        if self._daily_left('clear'):
            dead = self._nearest_plot(lambda _key, plot: plot.dead)
            if dead and farm.energy >= 1:
                return self._plot_action('clear', dead)
        if self._daily_left('plant') or self._daily_left('water'):
            planting = self._planting()
            if planting:
                return planting
        if self._daily_left('buy'):
            buying = self._daily_buy()
            if buying:
                return buying
        if (self._daily_left('feed') or self._daily_left('pet')
                or self._daily_left('collect')):
            care = self._animal_care()
            if care:
                return care
        if self._daily_left('animal'):
            animal = self._daily_animal()
            if animal:
                return animal
        if self._daily_left('buy_feed'):
            feed = self._daily_feed()
            if feed:
                return feed
        if self._daily_left('upgrade'):
            upgrade = self._daily_upgrade()
            if upgrade:
                return upgrade
        if self._daily_left('cook'):
            cooking = self._cook_intent()
            if cooking:
                return cooking
        if self._daily_left('sell') and self._sellable():
            return self._sell_intent()
        if self._daily_left('sell_fish') and self._sellable():
            return self._sell_intent()
        if self._daily_left('work') and farm.energy >= action_cost(farm, 'work'):
            return self._work_intent()
        if (self._daily_left('fish') or self._daily_left('catch_new')) \
                and farm.energy >= action_cost(farm, 'fish'):
            return self._fish_intent()
        if self._daily_left('talk'):
            npc = self._talk_target()
            if npc is not None:
                return self._talk_intent(npc)
        if self._daily_left('mine'):
            return self._mine_intent()
        if self._daily_left('forge'):
            return self._mine_intent(forge_slots=tuple(GEAR))
        if self._daily_left('dungeon'):
            return self._dungeon_intent(daily=True)
        return None

    def _daily_buy(self):
        farm = self.farm
        left = self._daily_left('buy')
        if left <= 0:
            return None
        crops = [key for key, info in CROPS.items() if info.level <= farm.level]
        if not crops:
            return None
        crop = min(crops, key=lambda key: (CROPS[key].seed_price, key))
        price = CROPS[crop].seed_price
        if farm.coins < price:
            return None
        quantity = min(left, farm.coins // price)
        return self._shop('buy', crop, quantity)

    def _daily_animal(self):
        farm = self.farm
        if self._daily_left('animal') <= 0:
            return None
        owned = {animal.kind for animal in farm.animals}
        choices = []
        for kind, info in ANIMAL_TYPES.items():
            zone = zone_for(kind)
            if (farm.level >= zone.level
                    and len(zone_animals(farm, zone)) < zone.capacity
                    and len(farm.animals) < farm.barn_capacity
                    and farm.coins >= info.price):
                choices.append((kind in owned, info.price, kind))
        if not choices:
            return None
        return self._barn('animal', min(choices)[2])

    def _daily_feed(self):
        if self._daily_left('buy_feed') <= 0:
            return None
        if self.farm.coins < EXTRA_ITEMS['feed'].buy_price:
            return None
        return self._shop('buy_feed', 1)

    def _daily_upgrade(self):
        farm = self.farm
        if self._daily_left('upgrade') <= 0:
            return None
        choices = []
        for kind in ('land', 'energy', 'sprinkler', 'barn'):
            try:
                cost = farm.upgrade_cost(kind)
            except GameError:
                continue
            if farm.coins >= cost:
                choices.append((cost, kind))
        if not choices:
            return None
        return self._shop('upgrade', min(choices)[1])

    def _cook_intent(self):
        if self._daily_left('cook') <= 0:
            return None
        recipe = next((recipe for recipe in RECIPES.values()
                       if can_cook(self.farm, recipe)), None)
        if recipe is None:
            return None
        return _Intent('cook', 'home', world.KITCHEN, 'kitchen', (recipe.key,))

    def _talk_target(self):
        farm = self.farm
        neighbours = [npc for npc in NPCS.values()
                      if farm.talked_on[npc.id] != farm.day
                      and npc.id in BRANCHING_NPC_IDS]
        if not neighbours:
            return None
        return min(neighbours, key=lambda npc: (
            abs(farm.player_x - npc.position[0])
            + abs(farm.player_y - npc.position[1]), npc.id)).id

    def _claim_ready(self):
        return any(q.progress >= q.target and not q.claimed for q in self.farm.daily.tasks)

    def _allocation(self):
        farm = self.farm
        if farm.attribute_points > 0:
            keys = [key for key, value in farm.attributes.items() if value < 5]
            if keys:
                key = min(keys, key=lambda key: (farm.attributes[key],
                          ('endurance', 'dexterity', 'focus').index(key)))
                return _Intent('attribute', args=(key,))
        if farm.skill_points > 0:
            keys = [key for key, value in farm.skills.items() if value < 5]
            if keys:
                key = min(keys, key=lambda key: (farm.skills[key],
                          ('farming', 'fishing', 'ranching', 'foraging').index(key)))
                return _Intent('skill', args=(key,))
        return None

    def _animal_care(self):
        farm = self.farm
        hungry = sum(not animal.fed for animal in farm.animals)
        missing = max(0, hungry - farm.items['feed'])
        if hungry and not missing:
            return self._barn('feed')
        if missing and farm.coins >= missing * EXTRA_ITEMS['feed'].buy_price:
            return self._shop('buy_feed', missing)
        for index, animal in enumerate(farm.animals):
            if not animal.petted:
                return self._barn('pet', index)
        if any(animal.produce for animal in farm.animals):
            return self._barn('collect')
        if missing:
            if self._sellable():
                return self._sell_intent()
            if farm.energy >= action_cost(farm, 'work'):
                return self._work_intent()
        return None

    def _planting(self, *, wheat=False):
        farm = self.farm
        coordinate = self._nearest_plot(lambda _k, p: not p.crop)
        water_cost = int(farm.weather != 'rainy' and not farm.sprinkler)
        cost = action_cost(farm, 'plant') + water_cost
        if coordinate is None or farm.energy < cost:
            return None
        growing = sum(bool(p.crop and not p.dead and not p.ready) for p in farm.plots.values())
        if not farm.sprinkler and growing >= farm.energy_limit:
            return None
        crops = ['lua_mi'] if wheat else [key for key, crop in CROPS.items() if crop.level <= farm.level]
        crops.sort(key=lambda key: (CROPS[key].sell_price - CROPS[key].seed_price)
                   / (CROPS[key].days + action_cost(farm, 'plant') + action_cost(farm, 'harvest')),
                   reverse=True)
        crop = next((key for key in crops if farm.seeds[key]), None)
        if crop is not None:
            return self._plot_action('plant', coordinate, crop)
        affordable = next((key for key in crops if farm.coins >= CROPS[key].seed_price), None)
        if affordable:
            empty = sum(not p.crop for p in farm.plots.values())
            quantity = min(empty, max(1, farm.energy // cost),
                           farm.coins // CROPS[affordable].seed_price)
            return self._shop('buy', affordable, quantity)
        if self._sellable():
            return self._sell_intent()
        if farm.energy >= action_cost(farm, 'work') + cost:
            return self._work_intent()
        return None

    def _invest(self):
        farm = self.farm
        # Keep seed money and two days of feed before optional purchases.
        # Specialists hold a little more back so investing never drains the
        # budget of the activity the player explicitly selected.
        reserve = 20 + 2 * len(farm.animals) * EXTRA_ITEMS['feed'].buy_price
        if self.options.mode != 'all':
            reserve += self._SPECIALIST_RESERVE
        for kind, info in ANIMAL_TYPES.items():
            zone = zone_for(kind)
            if (farm.level >= zone.level
                    and len(zone_animals(farm, zone)) < zone.capacity
                    and not any(animal.kind == kind for animal in farm.animals)
                    and len(farm.animals) < farm.barn_capacity
                    and farm.coins >= info.price + reserve + 10):
                return self._barn('animal', kind)
        for kind in ('sprinkler', 'energy', 'land', 'barn'):
            try:
                cost = farm.upgrade_cost(kind)
            except GameError:
                continue
            if farm.coins >= cost + reserve:
                return self._shop('upgrade', kind)
        return None

    def _with_investment(self, intent):
        """Use spare coins for animals/upgrades instead of idling.

        Specialist runs still finish their chosen work first; investing only
        replaces the sleep intent, so it does not steal energy or steps from
        the selected activity.
        """
        if intent.action != 'sleep':
            return intent
        return self._invest() or intent

    def _choose_intent(self):
        farm = self.farm
        if self._resting:
            return _Intent('claim') if self._claim_ready() else self._sleep_intent()
        if self.options.mode == 'mine':
            return self._with_investment(self._mine_intent())
        if self.options.mode == 'dungeon':
            return self._with_investment(self._dungeon_intent())
        guided = (self.options.mode == 'all' and farm.tutorial.status == 'active'
                  and current_step(farm) is not None)
        grows = self.options.mode in ('all', 'farm') or guided
        if grows:
            thirsty = self._nearest_plot(lambda key, p: p.crop and not p.dead
                                         and not p.ready and not farm.is_watered(key), urgent=True)
            if thirsty:
                if farm.energy:
                    return self._plot_action('water', thirsty)
                if self._claim_ready():
                    return _Intent('claim')
                if self.options.mode == 'all' and farm.attribute_points > 0 and farm.attributes['endurance'] < 5:
                    return _Intent('attribute', args=('endurance',))
                return self._sleep_intent()
        if self._claim_ready():
            return _Intent('claim')
        if guided:
            if self.options.mode in ('all', 'ranch'):
                care = self._animal_care()
                if care:
                    return care
            return self._tutorial_intent()
        if grows:
            ready = self._nearest_plot(lambda _k, p: p.ready)
            if ready and farm.energy >= action_cost(farm, 'harvest'):
                return self._plot_action('harvest', ready)
            dead = self._nearest_plot(lambda _k, p: p.dead)
            if dead and farm.energy:
                return self._plot_action('clear', dead)
        if self.options.mode in ('all', 'ranch'):
            intent = self._animal_care()
            if intent:
                return intent
        if self.options.mode == 'all':
            allocation = self._allocation()
            if allocation:
                return allocation
            daily = self._daily_intent()
            if daily is not None:
                return daily
        if self._sellable():
            return self._sell_intent()
        if grows:
            planting = self._planting()
            if planting:
                return planting
        if self.options.mode == 'all':
            investment = self._invest()
            if investment:
                return investment
            npc = self._talk_target()
            if npc is not None:
                return self._talk_intent(npc)
        if self.options.mode in ('all', 'fish') and farm.energy >= action_cost(farm, 'fish'):
            return self._fish_intent()
        return self._with_investment(self._sleep_intent())

    def _tutorial_intent(self):
        farm = self.farm
        step = current_step(farm).id
        if step in ('map', 'bag', 'character'):
            return _Intent(step)
        if step == 'movement':
            return self._talk_intent('lan', 'movement')
        if step == 'talk':
            return self._talk_intent('lan')
        if step == 'home':
            return _Intent('enter_home', 'village', world.HOME_DOOR, 'home')
        if step == 'tv':
            return _Intent('tv', 'home', world.TV, 'tv')
        if step == 'sleep':
            return self._sleep_intent()
        if step == 'upgrade':
            return self._allocation() or self._tutorial_income()
        if step == 'sell':
            return self._sell_intent() if self._sellable() else self._tutorial_income()
        if step == 'buy' or (step == 'plant' and not farm.seeds['lua_mi']):
            if farm.coins >= CROPS['lua_mi'].seed_price:
                return self._shop('buy', 'lua_mi', 1)
            if self._sellable():
                return self._sell_intent()
            return self._tutorial_income()
        coordinate = farm.tutorial.plot or self._nearest_plot(lambda _k, p: not p.crop)
        if coordinate is None:
            coordinate = self._nearest_plot(lambda _k, p: p.dead or p.ready) or next(iter(farm.plots))
        plot = farm.plots[coordinate]
        if step == 'field':
            return self._plot_action('field', coordinate)
        if plot.dead:
            return self._plot_action('clear', coordinate) if farm.energy else self._sleep_intent()
        if plot.ready:
            return (self._plot_action('harvest', coordinate)
                    if farm.energy >= action_cost(farm, 'harvest') else self._sleep_intent())
        if plot.crop:
            return self._sleep_intent()
        required = action_cost(farm, 'plant') + int(farm.weather != 'rainy' and not farm.sprinkler)
        if farm.energy >= required:
            return self._plot_action('plant', coordinate, 'lua_mi')
        return self._sleep_intent()

    def _tutorial_income(self):
        return (self._work_intent() if self.farm.energy >= action_cost(self.farm, 'work')
                else self._sleep_intent())

    def _at_goal(self, intent):
        if intent.kind == 'plot':
            return (world.target_plot(self.farm) == intent.args[0]
                    and world.context(self.farm)[0] == 'plot')
        if intent.kind == 'npc':
            npc = NPCS[intent.args[0]]
            return (self.farm.area == 'village'
                    and abs(npc.position[0] - self.farm.player_x)
                    + abs(npc.position[1] - self.farm.player_y) <= 1)
        if intent.kind == 'forest':
            return world.context(self.farm)[0] == 'forest'
        if intent.kind == 'water':
            return world.context(self.farm)[0] == 'fish'
        if intent.kind == 'rock':
            return (world.context(self.farm)[0] == 'rock'
                    and world.target_rock(self.farm) == intent.target)
        return world.is_near(self.farm, intent.kind)

    def _follow_intent(self, before):
        intent = self._intent
        if intent.target is None:
            return self._perform(intent, before)
        if self._expected_position != self._position():
            self._path.clear()
            self._routed = False
        if not self._routed:
            _target, path, key = route(self.farm, intent.area, intent.target, kind=intent.kind)
            if key == 'M' and not path:
                self._clear_intent()
                if self._resting or intent.action == 'sleep':
                    raise GameError('Không tìm thấy đường đến giường. Hãy điều khiển thủ công.')
                self._resting = True
                return self._result('Không tìm thấy đường làm việc; auto đang thử về nhà nghỉ.', before)
            self._path.extend(path)
            self._routed = True
            self._expected_position = self._position()
        if self._path:
            point = self._path.popleft()
            dx, dy = point[0] - self.farm.player_x, point[1] - self.farm.player_y
            if (dx, dy) not in self._DIRECTIONS:
                raise GameError('Đường auto không còn liền kề với người chơi.')
            return self._move(self._DIRECTIONS[dx, dy], before)
        if self.farm.area != intent.area:
            if self.farm.area == 'home':
                message = world.leave_home(self.farm)
            elif self.farm.area == 'mine':
                message = world.leave_mine(self.farm)
            elif intent.area == 'home':
                message = world.enter_home(self.farm)
                record_event(self.farm, 'enter_home')
            elif intent.area == 'mine':
                message = world.enter_mine(self.farm)
            else:
                raise GameError('Auto không tìm thấy cửa sang khu vực đích.')
            self._clear_intent()
            return self._result(message, before)
        if not self._at_goal(intent):
            self._routed = False
            self._blocked += 1
            if self._blocked >= 3:
                raise GameError('Đường auto bị chặn; hãy điều khiển thủ công.')
            return self._result('Đích đã thay đổi, auto tìm lại đường.', before)
        self._blocked = 0
        return self._perform(intent, before)

    def _move(self, direction, before):
        farm = self.farm
        old_x, old_y, old_facing = farm.player_x, farm.player_y, farm.facing
        tutorial_step = farm.tutorial.step
        moved = world.move(farm, direction)
        if moved:
            record_event(farm, 'move', from_x=old_x, from_y=old_y)
            sync_tutorial(farm)
            self._expected_position = self._position()
            if farm.tutorial.step != tutorial_step:
                self._clear_intent()
            return self._result(f'Auto: đi tới ({farm.player_x}, {farm.player_y}).', before, moved=True)
        self._routed = False
        self._path.clear()
        self._blocked += 1
        if self._blocked >= 3:
            raise GameError('Đường auto bị chặn; hãy điều khiển thủ công.')
        result = self._result('Đường vừa bị chặn, auto tìm lại đường.', before)
        return AutoResult(result.message, changed=result.changed or old_facing != farm.facing,
                          done=result.done)

    def _perform(self, intent, before):
        farm = self.farm
        action, args = intent.action, intent.args
        self._clear_intent()
        if action in ('plant', 'water', 'harvest', 'clear', 'work', 'sleep', 'upgrade'):
            message = getattr(farm, action)(*args)
        elif action == 'buy':
            message = farm.buy_seeds(*args)
        elif action == 'sell':
            message = farm.sell_all()
        elif action == 'sell_keep':
            message = farm.sell_all(keep=self.KEEP_FOR_CRAFTING)
        elif action == 'buy_potion':
            message = farm.buy_item('thuoc', *args)
        elif action == 'mine_rock':
            before_ore = {key: farm.items.get(key, 0) for key in (
                'da', 'quang_dong', 'quang_sat', 'quang_vang', 'kim_cuong')}
            message = mine_rock(farm, *args)
            self._mined_total += sum(
                max(0, farm.items.get(key, 0) - before_ore[key])
                for key in before_ore)
        elif action == 'forge':
            message = forge(farm, *args)
        elif action == 'cook':
            message = cook(farm, *args)
        elif action == 'dungeon':
            self.dungeon_run = start_run(farm)
            self._dungeon_daily = (self.options.mode == 'all'
                                   and self._daily_left('dungeon') > 0)
            message = f'Auto bước vào Hang Sâu tầng {self.dungeon_run.depth}.'
        elif action == 'buy_feed':
            message = buy_feed(farm, *args)
        elif action == 'feed':
            message = feed_animals(farm)
        elif action == 'pet':
            message = pet_animal(farm, *args)
        elif action == 'collect':
            message = collect_products(farm)
        elif action == 'animal':
            message = buy_animal(farm, *args)
        elif action == 'attribute':
            message = upgrade_attribute(farm, *args)
        elif action == 'skill':
            message = upgrade_skill(farm, *args)
        elif action == 'claim':
            message = claim_all(farm)
        elif action == 'fish':
            self.fishing_round = start_fishing(farm, self.rng)
            message = 'Auto: đã quăng cần, đang giữ cá trong thanh câu.'
        elif action == 'talk':
            self._conversation = begin_dialogue(farm, *args)
            message = self._conversation.history[0]
        elif action == 'movement':
            for (dx, dy), direction in self._DIRECTIONS.items():
                if (world.walkable(farm.area, farm.player_x + dx, farm.player_y + dy, farm.size)
                        and npc_at(farm.player_x + dx, farm.player_y + dy, farm.area) is None):
                    return self._move(direction, before)
            raise GameError('Không có đường đi để thực hành di chuyển.')
        elif action == 'enter_home':
            message = world.enter_home(farm)
            record_event(farm, 'enter_home')
        elif action == 'enter_mine':
            message = world.enter_mine(farm)
        elif action == 'tv':
            message = farm.forecast_report()
            record_event(farm, 'tv')
        elif action == 'field':
            message = sync_tutorial(farm) or 'Auto: đã tới ô ruộng hướng dẫn.'
        elif action == 'map':
            message = 'Bản đồ làng: ' + ', '.join(label for label, _point in world.LANDMARKS.values())
            record_event(farm, 'map')
        elif action == 'bag':
            rows = inventory_rows(farm)
            message = 'Túi đồ: ' + ', '.join(f'{name} ×{amount}' for _key, name, amount, _stored in rows if amount)
            record_event(farm, 'bag')
        elif action == 'character':
            message = '\n'.join(character_lines(farm))
            reward = record_event(farm, 'character')
            if reward:
                message += '\n' + reward
        else:
            raise GameError('Auto không nhận ra thao tác tiếp theo.')
        return self._result(message, before)

    def _dungeon_step(self, before):
        run = self.dungeon_run
        if run is None:
            return self._result('Auto không còn trận Hang Sâu nào.', before)
        if (self._dungeon_daily and not run.finished
                and self._daily_left('dungeon') <= 0):
            return self._result(flee(self.farm, run), before)
        low_hp = self.farm.hp <= max(4, self.farm.max_hp // 3)
        if run.phase == 'battle':
            if low_hp and self.farm.items.get('thuoc', 0) > 0:
                message = use_potion(self.farm, run)
            elif low_hp:
                message = flee(self.farm, run)
            else:
                message = player_attack(self.farm, run)
        elif run.phase == 'floor':
            message = advance(self.farm, run)
        else:
            self.dungeon_run = None
            self._dungeon_daily = False
            if run.phase == 'defeated':
                message = 'Auto ngã xuống trong Hang Sâu; sẽ về nhà hồi sức.'
            elif run.phase == 'fled':
                message = (f'Auto rút lui khỏi Hang Sâu · {run.total_coins} xu, '
                           f'{run.total_xp} XP.')
            else:
                message = (f'Auto hoàn tất Hang Sâu · {run.total_coins} xu, '
                           f'{run.total_xp} XP.')
            return self._result(message, before)
        return self._result(message, before)

    def _fish_step(self, before):
        round_ = self.fishing_round
        if round_.done:
            message = finish_fishing(self.farm, round_)
            self.fishing_round = None
            return self._result(message, before)
        # A damped proportional controller operates only the real hold input.
        # It does not move the fish/bar, set progress, or grant the catch.
        holding = 8 * (round_.target - round_.bar) - 3 * round_.velocity > 0
        round_.step(0.1, holding)
        return self._result(f'Auto câu cá: {round_.progress:.0%}.', before)

    def _talk_step(self, before):
        conversation = self._conversation
        node = dialogue_node(conversation)
        message = choose_response(self.farm, conversation, node.choices[0].id)
        if conversation.done:
            tutorial_message = record_event(self.farm, 'talk', npc_id=conversation.npc_id, done=True)
            self._conversation = None
            if tutorial_message:
                message += '\n' + tutorial_message
        return self._result(message, before)
