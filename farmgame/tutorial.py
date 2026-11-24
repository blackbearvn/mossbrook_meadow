"""Lan's action-driven coach. Reading guidance never mutates the farm."""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .navigation import route as _shared_route

if TYPE_CHECKING:
    from .model import Farm


@dataclass(slots=True)
class TutorialState:
    status: str = 'off'
    step: int = 0
    moves: int = 0
    plot: str | None = None
    planted_on: int = 0
    watered_on: int = 0
    reward_given: bool = False


@dataclass(frozen=True, slots=True)
class Step:
    id: str
    title: str
    instructions: str


STEPS = (
    Step('map', 'Bản đồ làng', 'Nhấn M để xem bản đồ và tìm Nhà, Cửa hàng, Cánh đồng.'),
    Step('movement', 'Tập đi bộ', 'Đi 4 bước thành công bằng WASD hoặc mũi tên; va tường không tính.'),
    Step('talk', 'Chào Lan', 'Đến cạnh Lan (số 1), nhấn E và hoàn tất cả 2 lượt trò chuyện.'),
    Step('bag', 'Mở túi đồ', 'Nhấn I để xem hạt giống và sản phẩm đang mang.'),
    Step('buy', 'Mua hạt lúa mì', 'Đến cửa hàng, E → Mua hạt giống → Lúa mì → số lượng ít nhất 1.'),
    Step('field', 'Tới cánh đồng', 'Đi về Cánh đồng phía nam, đứng trên hoặc cạnh một ô ruộng.'),
    Step('plant', 'Trồng lúa mì', 'E trên ô ruộng → Trồng → Lúa mì. Ghi nhớ ô này để chăm và thu hoạch.'),
    Step('water', 'Tưới cây vừa trồng', 'E → Tưới nước cho đúng ô đã trồng. Mưa hoặc hệ thống tưới cũng đủ nước.'),
    Step('home', 'Về nhà', 'Đến cửa nhà, nhấn E để vào nhà.'),
    Step('tv', 'Xem dự báo', 'Đứng cạnh tivi, nhấn E. Xem tivi không làm qua ngày.'),
    Step('sleep', 'Ngủ sang ngày mới', 'Đến cạnh giường, E → xác nhận ngủ. Cây đủ nước sẽ lớn qua đêm.'),
    Step('harvest', 'Thu hoạch lúa mì', 'Quay lại đúng ô lúa mì, E → Thu hoạch khi cây chín.'),
    Step('sell', 'Bán sản phẩm', 'Đến cửa hàng, E → Bán tất cả sản phẩm trong túi.'),
    Step('character', 'Cấp độ và điểm nhân vật', 'Nhấn C để nhận 40 XP nhập môn một lần. Mỗi cấp cho 1 điểm thuộc tính và 2 điểm tay nghề.'),
    Step('upgrade', 'Tự nâng một chỉ số', 'Nhấn C → Thuộc tính hoặc Tay nghề → chọn một chỉ số để tiêu 1 điểm nâng bậc.'),
)


@dataclass(frozen=True, slots=True)
class Hint:
    title: str
    body: str
    key: str
    target: tuple[int, int] | None
    path: tuple[tuple[int, int], ...]
    area: str


def current_step(farm: 'Farm') -> Step | None:
    state = farm.tutorial
    return STEPS[state.step] if state.status in ('active', 'paused') and state.step < len(STEPS) else None


def start_tutorial(farm: 'Farm') -> str:
    state = farm.tutorial
    if state.status == 'completed':
        return 'Lan: Cậu đã hoàn tất 15 bước. Chúc nông trại luôn xanh!'
    if state.status in ('active', 'paused'):
        return resume_tutorial(farm)
    farm.tutorial = TutorialState(status='active', reward_given=state.reward_given)
    return 'Lan: Tớ với cậu cùng thực hành nhé! ' + STEPS[0].instructions


def pause_tutorial(farm: 'Farm') -> str:
    if farm.tutorial.status != 'active':
        return ''
    farm.tutorial.status = 'paused'
    return 'Lan: Đã tạm ẩn chỉ dẫn; các bước thực hành vẫn được ghi nhận. Nhấn T để tiếp tục.'


def resume_tutorial(farm: 'Farm') -> str:
    if farm.tutorial.status != 'paused':
        return ''
    farm.tutorial.status = 'active'
    return 'Lan: Tớ với cậu tiếp tục nhé!'


def skip_tutorial(farm: 'Farm') -> str:
    if farm.tutorial.status in ('skipped', 'completed'):
        return ''
    farm.tutorial.status = 'skipped'
    return 'Lan: Cậu cứ tự khám phá. Nhấn T nếu muốn tớ hướng dẫn lại.'


def _advance(farm: 'Farm') -> str:
    state = farm.tutorial
    state.step += 1
    if state.step == len(STEPS):
        state.status = 'completed'
        return 'Lan: Cậu đã hoàn tất 15 bước! Chúc nông trại luôn xanh; nhấn T để xem tổng kết.'
    return 'Lan: Tốt lắm! ' + STEPS[state.step].instructions


def sync_tutorial(farm: 'Farm') -> str:
    step = current_step(farm)
    if step is None:
        return ''
    state = farm.tutorial
    if 7 <= state.step <= 11:
        plot = farm.plots.get(state.plot)
        if plot is None or plot.crop != 'lua_mi' or plot.dead:
            state.step = 6
            if plot is None or (plot.crop and plot.crop != 'lua_mi' and not plot.dead):
                state.plot = None
            state.planted_on = state.watered_on = 0
            return 'Lan: Cây lúa mì đã mất hoặc héo. Dọn cây héo nếu cần rồi trồng lại; tớ sẽ hướng dẫn lại từ ô này.'
    if step.id == 'field':
        from .world import target_plot
        if target_plot(farm) is not None:
            return _advance(farm)
    if step.id == 'water' and farm.is_watered(state.plot):
        state.watered_on = farm.day
        return _advance(farm)
    return ''


def record_event(farm: 'Farm', event: str, **details) -> str:
    step = current_step(farm)
    if step is None:
        return ''
    state = farm.tutorial
    matches = event == step.id
    if step.id == 'movement':
        matches = False
        if event == 'move':
            old = details.get('from_x'), details.get('from_y')
            if (all(type(v) is int for v in old)
                    and abs(farm.player_x - old[0]) + abs(farm.player_y - old[1]) == 1):
                state.moves = min(4, state.moves + 1)
                matches = state.moves == 4
    elif step.id == 'talk':
        matches = event == 'talk' and details.get('npc_id') == 'lan' and details.get('done') is True
    elif step.id == 'buy':
        matches = (event == 'buy' and details.get('crop') == 'lua_mi'
                   and type(details.get('quantity')) is int and details['quantity'] >= 1)
    elif step.id == 'plant':
        coordinate = str(details.get('coordinate', '')).strip().upper()
        plot = farm.plots.get(coordinate)
        matches = (event == 'plant' and details.get('crop') == 'lua_mi'
                   and plot is not None and plot.crop == 'lua_mi' and not plot.dead
                   and (state.plot is None or coordinate == state.plot))
        if matches:
            state.plot = coordinate
            state.planted_on = farm.day
            state.watered_on = 0
    elif step.id in ('water', 'harvest'):
        matches = event == step.id and str(details.get('coordinate', '')).strip().upper() == state.plot
        if matches and event == 'water':
            matches = farm.is_watered(state.plot)
            if matches:
                state.watered_on = farm.day
    elif step.id == 'home':
        matches = event == 'enter_home'
    if not matches:
        return ''
    reward = ''
    if step.id == 'character' and not state.reward_given:
        state.reward_given = True
        reward = farm.award_xp(40) + ' '
    message = _advance(farm)
    if step.id == 'character' and all(v >= 5 for v in (*farm.attributes.values(), *farm.skills.values())):
        message = _advance(farm)
    # Rain and sprinklers satisfy watering immediately after a real planting.
    if step.id == 'plant':
        extra = sync_tutorial(farm)
        if extra:
            message += ' ' + extra
    return reward + message


def _plot_point(coordinate: str) -> tuple[int, int]:
    from .world import FIELD_ORIGIN
    return FIELD_ORIGIN[0] + ord(coordinate[0]) - ord('A'), FIELD_ORIGIN[1] + int(coordinate[1:]) - 1


def _route(farm: 'Farm', area: str, target: tuple[int, int], *, kind: str = ''):
    """Preserve the coach's route contract through the shared A* planner."""
    return _shared_route(farm, area, target, kind=kind)


def tutorial_hint(farm: 'Farm') -> Hint | None:
    step = current_step(farm)
    if step is None or farm.tutorial.status != 'active':
        return None
    from . import world
    from .catalog import CROPS
    from .progression import action_cost
    from .villagers import NPCS
    state = farm.tutorial
    body, key = step.instructions, 'E'
    area, target, kind = farm.area, None, ''
    if step.id in ('map', 'bag', 'character', 'upgrade', 'movement'):
        key = {'map': 'M', 'bag': 'I', 'character': 'C', 'upgrade': 'C', 'movement': 'WASD / mũi tên'}[step.id]
        if step.id == 'movement':
            body += f' Đã đi {state.moves}/4 bước.'
    elif step.id == 'talk':
        area, target, kind = 'village', NPCS['lan'].position, 'npc'
    elif step.id in ('buy', 'sell'):
        area, target, kind = 'village', world.SHOP_DOOR, 'shop'
    elif step.id == 'home':
        area, target, kind = 'village', world.HOME_DOOR, 'home'
    elif step.id in ('tv', 'sleep'):
        kind = 'tv' if step.id == 'tv' else 'bed'
        area, target = 'home', world.TV if kind == 'tv' else world.BED
    elif step.id in ('field', 'plant', 'water', 'harvest'):
        coordinate = state.plot or next((k for k, p in farm.plots.items() if not p.crop), None)
        if coordinate is None:
            coordinate = next((k for k, p in farm.plots.items() if p.ready or p.dead),
                              next((k for k in farm.plots if not farm.is_watered(k)), next(iter(farm.plots))))
            body = 'Ruộng đã đầy. '
        else:
            body += f' Ô hướng dẫn: {coordinate}.'
        area, target, kind = 'village', _plot_point(coordinate), 'plot'
        plot = farm.plots[coordinate]
        if step.id in ('field', 'plant') and plot.crop:
            prefix = 'Ruộng đã đầy. ' if all(p.crop for p in farm.plots.values()) else ''
            if plot.dead:
                body = prefix + f'Ô {coordinate}: E → Dọn cây héo, rồi trồng lúa mì vào ô trống.'
            elif plot.ready:
                body = prefix + f'Ô {coordinate}: E → Thu hoạch để có ô trống trồng lúa mì.'
            elif not farm.is_watered(coordinate):
                body = prefix + f'Ô {coordinate} chưa chín: E → Tưới nước, rồi ngủ; lặp lại đến khi chín để thu hoạch lấy ô trống.'
            else:
                body = prefix + f'Ô {coordinate} đã đủ nước: về giường ngủ để cây lớn; khi chín thu hoạch lấy ô trống trồng lúa mì.'
                area, target, kind = 'home', world.BED, 'bed'
        if step.id == 'plant' and plot.dead:
            body = f'Ô {coordinate} có cây héo: E → Dọn cây héo, rồi trồng lại lúa mì tại đây.'
        elif step.id == 'harvest' and plot.crop and not plot.ready:
            body = f'Ô {coordinate} chưa chín. Tưới đúng ô mỗi ngày rồi về giường ngủ; khi chín E → Thu hoạch.'
            if farm.is_watered(coordinate):
                area, target, kind = 'home', world.BED, 'bed'
    # Resource recovery takes precedence over the ordinary action target.
    action = {'plant': 'plant', 'water': 'water', 'harvest': 'harvest'}.get(step.id)
    if action and farm.energy < action_cost(farm, action):
        body = 'Bạn hết sức cho thao tác này. Về giường, E → Ngủ để hồi sức rồi quay lại ô hướng dẫn.'
        area, target, kind = 'home', world.BED, 'bed'
    elif step.id == 'plant' and farm.seeds['lua_mi'] < 1:
        body = 'Hết hạt lúa mì: đến cửa hàng, E → Mua hạt giống → Lúa mì.'
        area, target, kind = 'village', world.SHOP_DOOR, 'shop'
    if ((step.id == 'buy' or (step.id == 'plant' and farm.seeds['lua_mi'] < 1))
            and farm.coins < CROPS['lua_mi'].seed_price):
        if farm.energy < action_cost(farm, 'work'):
            body = 'Thiếu xu và sức: về giường ngủ hồi sức, rồi làm thuê để mua hạt lúa mì.'
            area, target, kind = 'home', world.BED, 'bed'
        else:
            body = 'Thiếu xu mua giống. Đến cạnh cây, E → Làm thuê để kiếm xu; sau đó mua hạt lúa mì.'
            area, target, kind = 'village', (9, 13), 'forest'
    path = ()
    if target is not None:
        destination_area = area
        target, path, key = _route(farm, area, target, kind=kind)
        if farm.area != destination_area:
            body = ('Ra cửa nhà, E để ra làng. ' if farm.area == 'home' else 'Vào cửa nhà bằng E. ') + body
        area = farm.area
    return Hint(f'Lan · {state.step + 1}/15 · {step.title}', body, key, target, path, farm.area)


def tutorial_lines(farm: 'Farm') -> list[str]:
    state = farm.tutorial
    lines = ['LAN HƯỚNG DẪN TÂN THỦ', f'Trạng thái: {state.status}',
             'Làm từng bước thật; chỉ đường không tốn sức hoặc qua ngày.',
             'Mỗi cấp: +1 điểm thuộc tính, +2 điểm tay nghề. Nhấn C để tự nâng chỉ số.']
    if state.status == 'completed':
        lines.append('Chúc mừng! Bạn đã hoàn tất cả 15 bước thực hành.')
    step = current_step(farm)
    if step:
        lines.append(f'Đang làm {state.step + 1}/15: {step.title} — {step.instructions}')
    hint = tutorial_hint(farm)
    if hint:
        lines.extend((hint.body, f'Phím tiếp theo: {hint.key}'))
    lines.extend(f'{i}. {s.title}: {s.instructions}' for i, s in enumerate(STEPS, 1))
    return lines
