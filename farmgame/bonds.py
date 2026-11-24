"""Ways to grow a bond besides talking: gifts, small help and request letters.

Everything here is deterministic (day arithmetic, never the shared random
stream), validated like every other action, and emotional in tone: gifts are
received with real reactions, help is a small everyday favour, and the letter
asks for one concrete item the farm can actually provide.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .catalog import CROPS, EXTRA_ITEMS, ITEMS
from .model import GameError
from .villagers import NPCS, relative_of

if TYPE_CHECKING:
    from .model import Farm


# Items each villager truly loves; anything else gift-worthy is still welcome.
_GIFT_LOVES = {
    'lan': ('seed:lua_mi', 'seed:ca_rot', 'crop:hoa_hong', 'banh_mi'),
    'tu': ('ca_vang', 'ca_hoi', 'tra_hoa_hong', 'chao_trung'),
    'an': ('crop:hoa_hong', 'crop:ca_chua', 'salad_vuon', 'crop:dua_hau'),
    'mai': ('wool', 'banh_mi', 'tra_hoa_hong', 'crop:lua_mi'),
    'son': ('wood', 'da', 'tra_hoa_hong', 'chao_trung'),
    'hai': ('tra_hoa_hong', 'milk', 'chao_trung', 'crop:lua_mi'),
    'minh': ('banh_mi', 'egg', 'crop:ca_rot', 'wood'),
    'ha': ('wood', 'da', 'quang_dong', 'milk'),
}

# One small favour per villager per day.  Wood helpers want wood, the rest
# only need a spare moment of the farmer's day.
_HELP_FLAVOUR = {
    'lan': ('giúp sắp lại giỏ hạt ngoài hiên', 0),
    'tu': ('giúp bác Tư châm trà và thu cần', 0),
    'an': ('giúp An tạt nước luống hoa ven đường', 0),
    'mai': ('giúp Mai nâng thùng sách ra quảng trường', 0),
    'son': ('giúp Sơn châm dọn cành khô trên lối mòn', 1),
    'hai': ('giúp Bác Hai khuấy ấm chén trà', 0),
    'minh': ('giúp Minh chờ chuyến hàng xuống xe', 0),
    'ha': ('giúp Hà sửa chiếc ghế gãy của quảng trường', 1),
}

# Request letters: one concrete item the farm can provide, per villager.
_REQUEST_POOL = {
    'lan': ('crop:ca_rot', 'crop:lua_mi', 'crop:bap', 'banh_mi'),
    'tu': ('ca_ro', 'ca_chep', 'ca_hoi', 'crop:lua_mi'),
    'an': ('crop:hoa_hong', 'crop:ca_chua', 'crop:dua_hau', 'salad_vuon'),
    'mai': ('crop:lua_mi', 'egg', 'wool', 'banh_mi'),
    'son': ('wood', 'da', 'quang_dong', 'crop:ca_rot'),
    'hai': ('milk', 'egg', 'tra_hoa_hong', 'crop:ca_rot'),
    'minh': ('egg', 'crop:ca_rot', 'banh_mi', 'wood'),
    'ha': ('wood', 'da', 'crop:bap', 'milk'),
}

_GIFT_THANKS = {
    'lan': ('Lan ôm {item} trước ngực: \"Đúng thứ tớ đang cần. Cậu để ý thật đấy\".',
            'Lan đặt {item} lên quầy, lau tay mới chạm vào: \"Cảm ơn cậu. Tớ để chỗ dễ thấy\".'),
    'tu': ('Bác Tư cầm {item} ngắm thật lâu: \"Thứ này quý. Cháu để ý bác thật\".',
           'Bác Tư gật đầu: \"Cháu để ý bác thật đấy. Bác cất kỹ, để dành\".'),
    'an': ('An ôm {item} sát mũi hít một hơi: \"Mùi này! Cậu chọn đúng thứ tớ thích rồi\".',
           'An cười sáng cả mặt: \"Tớ sẽ trồng lại thứ này ven đường, để người đi qua cũng thấy\".'),
    'mai': ('Mai nhận {item} bằng hai tay: \"Tớ sẽ ghi món này vào sổ, cả tên cậu nữa\".',
            'Mai khẽ cười: \"Có chuyện để kể thì món quà nhớ lâu hơn\".'),
    'son': ('Sơn cầm {item} lật lên lật xuống: \"Thứ này chắc. Tớ dùng được, cảm ơn cậu\".',
            'Sơn gật đầu: \"Tớ để chỗ dễ thấy. Cậu tặng thì tớ dùng, đừng để phí\".'),
    'hai': ('Bác Hai cười hiền: \"Được, để bác pha trà mời lại\".',
            'Bác Hai đặt {item} vào giỏ mây: \"Cháu chu đáo thật. Bác giữ món này\".'),
    'minh': ('Minh nhún nhảy: \"Em sẽ khoe chị Lan món này! Cảm ơn anh/chị nha\".',
             'Minh cầm {item} vừa đi vừa ngắm: \"Được quà giữa đường chở hàng là vui nhất ngày\".'),
    'ha': ('Hà lau tay trên tạp dề rồi mới nhận: \"Cảm ơn cậu. Món này tớ nhận bằng cả hai tay\".',
           'Hà cười gật gù: \"Coi như tớ nợ cậu một lần sửa đồ miễn phí nhé. Giữ lời đấy\".'),
}

_GIFT_NORMAL = (
    'Cảm ơn nhé, món này quý lắm.',
    'Cảm ơn nhé. Món quà kèm lời hỏi thăm thì quý hơn.',
    'Cảm ơn nhé. Có món quà với lời hỏi thăm là vui rồi.',
)

_THANKS_FAMILY = {
    'tu': 'Bác Tư', 'hai': 'Bác Hai',
    'lan': 'chị Lan', 'minh': 'Minh',
    'son': 'Sơn', 'ha': 'Hà',
    'mai': 'Mai', 'an': 'An',
}


def _near(farm: 'Farm', npc_id: str) -> None:
    npc = NPCS.get(npc_id)
    if npc is None:
        raise GameError('Không có người dân này.')
    if (farm.area != 'village'
            or abs(npc.position[0] - farm.player_x)
            + abs(npc.position[1] - farm.player_y) > 1):
        raise GameError(f'Hãy đứng cạnh {npc.name} để trao đổi.')


def _source(farm: 'Farm', key: str) -> dict[str, int]:
    if key.startswith('crop:'):
        crop = key[5:]
        if crop in CROPS:
            return farm.produce
    elif key.startswith('seed:'):
        seed = key[5:]
        if seed in CROPS:
            return farm.seeds
    elif key in EXTRA_ITEMS:
        return farm.items
    raise GameError('Món quà này không có trong túi.')


def item_name(key: str) -> str:
    return ITEMS.get(key, key).name if key in ITEMS else key


def gift_options(farm: 'Farm') -> list[tuple[str, str]]:
    """Giftable (key, label) pairs from the farmer's own pockets."""
    options = []
    for key in ITEMS:
        source = _source(farm, key)
        plain = key.split(':', 1)[-1] if ':' in key else key
        count = source.get(plain, 0)
        if count > 0:
            options.append((key, f'{item_name(key)} ×{count}'))
    return options


def give_gift(farm: 'Farm', npc_id: str, key: str) -> str:
    """Hand over one item; the reaction and bond change with how well it fits."""
    _near(farm, npc_id)
    npc = NPCS[npc_id]
    if farm.gifted_on.get(npc_id) == farm.day:
        raise GameError(f'Bạn đã tặng quà {npc.name} hôm nay rồi.')
    source = _source(farm, key)
    plain = key.split(':', 1)[-1] if ':' in key else key
    if source.get(plain, 0) < 1:
        raise GameError(f'Túi bạn không còn {item_name(key)} để tặng.')
    source[plain] -= 1
    loved = key in _GIFT_LOVES.get(npc_id, ())
    gain = 2 if loved else 1
    before = farm.friendships[npc_id]
    farm.friendships[npc_id] = min(10, before + gain)
    farm.gifted_on[npc_id] = farm.day
    lines = []
    if loved:
        lines.append(_GIFT_THANKS[npc_id][farm.day % len(_GIFT_THANKS[npc_id])]
                     .format(item=item_name(key)))
        gain_xp = 4
    else:
        lines.append(f'{npc.name} nhận {item_name(key)}: '
                     + _GIFT_NORMAL[farm.day % len(_GIFT_NORMAL)])
        gain_xp = 2
    lines.append(f'Bạn tặng {npc.name} {item_name(key)} · '
                 f'Thân {farm.friendships[npc_id]}/10'
                 f' (+{farm.friendships[npc_id] - before}).')
    # Family warmth travels: the relative smiles a little too.
    relative = relative_of(npc_id)
    if relative is not None:
        rel_before = farm.friendships[relative]
        if farm.gifted_on.get(relative) != farm.day and rel_before < 10:
            farm.friendships[relative] = rel_before + 1
            lines.append(f'{_THANKS_FAMILY.get(relative, NPCS[relative].name)} '
                         f'nghe tin cũng vui theo '
                         f'(Thân {farm.friendships[relative]}/10).')
    xp_status = farm.award_xp(gain_xp)
    if xp_status:
        lines.append(xp_status)
    return '\n'.join(lines)


def help_available(farm: 'Farm', npc_id: str) -> bool:
    return farm.helped_on.get(npc_id) != farm.day


def help_favour(farm: 'Farm', npc_id: str) -> str:
    """One small everyday favour per day; wood-helpers want a piece of wood."""
    _near(farm, npc_id)
    npc = NPCS[npc_id]
    if not help_available(farm, npc_id):
        raise GameError(f'Bạn đã giúp {npc.name} hôm nay rồi. Họ bảo bạn nghỉ ngơi.')
    flavour, wood_cost = _HELP_FLAVOUR[npc_id]
    if wood_cost:
        if farm.items.get('wood', 0) < 1:
            raise GameError('Cần 1 khúc gỗ để giúp việc này (nhặt củi ở rừng).')
        farm.items['wood'] -= 1
        cost_note = '· dùng 1 khúc gỗ'
    else:
        if farm.energy < 1:
            raise GameError('Bạn quá mệt để giúp việc này.')
        farm.energy -= 1
        cost_note = '· tốn 1 năng lượng'
    before = farm.friendships[npc_id]
    farm.friendships[npc_id] = min(10, before + 1)
    farm.helped_on[npc_id] = farm.day
    lines = [f'Bạn {flavour}.',
             f'{npc.name} cười: \"Có người giúp thì việc gì cũng nhẹ.\" '
             f'Thân {farm.friendships[npc_id]}/10 (+{farm.friendships[npc_id] - before}) {cost_note}.']
    xp_status = farm.award_xp(3)
    if xp_status:
        lines.append(xp_status)
    return '\n'.join(lines)


def ensure_request(farm: 'Farm') -> str:
    """Today's request letter, generated lazily and deterministically.

    Returns the letter line the first time it is created for this day, so the
    morning can announce it like real mail.
    """
    if farm.request_day == farm.day and farm.request_npc:
        return ''
    npc_ids = tuple(NPCS)
    npc_id = npc_ids[(farm.day * 7 + 3) % len(npc_ids)]
    pool = _REQUEST_POOL[npc_id]
    key = pool[(farm.day * 11 + 5) % len(pool)]
    cheap = (key.startswith('crop:lua_mi')
             or key in ('wood', 'da', 'egg', 'ca_ro'))
    count = 2 if cheap else 1
    npc = NPCS[npc_id]
    farm.request_day = farm.day
    farm.request_npc = npc_id
    farm.request_item = key
    farm.request_count = count
    farm.request_done = False
    return (f'Thư nhờ giúp đỡ từ {npc.name}: "{item_name(key)}'
            + (f'×{count}' if count > 1 else '')
            + '. Cảm ơn trước nhé!"')


def request_ready(farm: 'Farm', npc_id: str) -> bool:
    return (farm.request_npc == npc_id and not farm.request_done
            and farm.request_day == farm.day)


def request_line(farm: 'Farm', npc_id: str) -> str:
    npc = NPCS[npc_id]
    if request_ready(farm, npc_id):
        return (f'Thư nhờ: cần {item_name(farm.request_item)}'
                + (f'×{farm.request_count}' if farm.request_count > 1 else ''))
    if farm.request_npc == npc_id and farm.request_done:
        return 'Việc nhờ hôm nay đã xong, họ gửi lời cảm ơn.'
    return ''


def deliver_request(farm: 'Farm', npc_id: str) -> str:
    _near(farm, npc_id)
    if not request_ready(farm, npc_id):
        raise GameError('Không có món nào được nhờ hôm nay.')
    if farm.request_npc != npc_id:
        raise GameError('Việc nhờ này là của người khác.')
    npc = NPCS[npc_id]
    source = _source(farm, farm.request_item)
    plain = (farm.request_item.split(':', 1)[-1]
             if ':' in farm.request_item else farm.request_item)
    if source.get(plain, 0) < farm.request_count:
        raise GameError(f'Túi bạn chưa đủ {farm.request_count} '
                        f'{item_name(farm.request_item)}.')
    source[plain] -= farm.request_count
    farm.request_done = True
    before = farm.friendships[npc_id]
    farm.friendships[npc_id] = min(10, before + 2)
    value = ITEMS[farm.request_item].sell_price * farm.request_count
    coins = max(10, int(value * 1.5))
    farm.coins += coins
    lines = [f'Bạn đưa {farm.request_count} {item_name(farm.request_item)} cho {npc.name}.',
             f'{npc.name}: \"Đúng thứ đang cần. Cảm ơn nhé.\" '
             f'Thân {farm.friendships[npc_id]}/10 (+{farm.friendships[npc_id] - before}) · '
             f'+{coins} xu cảm ơn.']
    xp_status = farm.award_xp(6)
    if xp_status:
        lines.append(xp_status)
    return '\n'.join(lines)
