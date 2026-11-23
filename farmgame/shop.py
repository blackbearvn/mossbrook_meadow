"""Pure shop catalogue: categories, cards and safe actions.

The terminal frontends decide *how* to draw these entries; this module only
describes what the village shop sells and performs the mutations when a card
is chosen.  Keeping it free of curses makes the catalogue unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .animals import (ANIMAL_TYPES, buy_animal, buy_feed, product_name,
                      zone_for)
from .catalog import CROPS, FISH_TYPES, ITEMS
from .model import GameError
from .progression import sale_price

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class ShopEntry:
    art_key: str
    name: str
    price: int
    meta: str
    detail: str
    action: str
    payload: str = ''
    locked: bool = False
    disabled: bool = False


@dataclass(frozen=True, slots=True)
class ShopCategory:
    key: str
    name: str
    icon: str
    hint: str
    entries: tuple[ShopEntry, ...]


CATEGORY_ORDER = ('seeds', 'animals', 'supplies', 'sell', 'upgrades')

_UPGRADES = (
    ('land', 'Mở rộng ruộng', 'Mỗi bậc thêm một hàng và một cột đất canh tác.'),
    ('energy', 'Tăng thể lực', 'Nâng giới hạn năng lượng lên 30 và hồi ngay 10.'),
    ('sprinkler', 'Tưới tự động', 'Toàn bộ ruộng luôn đủ nước, kể cả ngày nắng.'),
    ('barn', 'Mở rộng chuồng', 'Chuồng đủ chỗ cho 8 vật nuôi thay vì 4.'),
)


def _seed_entry(farm: 'Farm', key: str) -> ShopEntry:
    crop = CROPS[key]
    locked = farm.level < crop.level
    return ShopEntry(
        art_key=f'seed:{key}',
        name=f'Hạt {crop.name}',
        price=crop.seed_price,
        meta=(f'C{crop.level} · {crop.days} đêm' if not locked
              else f'Cần cấp {crop.level}'),
        detail=(f'{crop.days} đêm được tưới để chín · bán {sale_price(farm, "crop:" + key)} xu'
                f' · +{crop.xp} XP khi thu hoạch · túi đang có {farm.seeds[key]} hạt'),
        action='buy_seed',
        payload=key,
        locked=locked,
    )


def _animal_entry(farm: 'Farm', key: str) -> ShopEntry:
    info = ANIMAL_TYPES[key]
    zone = zone_for(key)
    product = product_name(key).lower()
    locked = farm.level < zone.level
    return ShopEntry(
        art_key=key,
        name=info.name,
        price=info.price,
        meta=(f'{zone.name} · {info.mature_days} ngày · {product}'
              if not locked else f'{zone.name} · mở cấp {zone.level}'),
        detail=(f'Khu {zone.name}: trưởng thành sau {info.mature_days} ngày được cho ăn · '
                f'sản phẩm {product} mỗi {info.interval} ngày · '
                f'vuốt ve để thêm thân thiết.'),
        action='buy_animal',
        payload=key,
        locked=locked,
    )


def _supply_entries(farm: 'Farm') -> tuple[ShopEntry, ...]:
    feed_price = ITEMS['feed'].buy_price
    entries = [
        ShopEntry(
            art_key='feed',
            name='Thức ăn chăn nuôi',
            price=feed_price,
            meta=f'Túi {farm.items["feed"]}',
            detail='Mỗi phần nuôi một vật nuôi trong ngày. Mua theo số lượng ở bước sau.',
            action='buy_feed',
            payload='1',
        ),
        ShopEntry(
            art_key='feed',
            name='Bao thức ăn 10 phần',
            price=feed_price * 10,
            meta=f'10 phần · túi {farm.items["feed"]}',
            detail='Một bao đủ cho cả đàn nhỏ trong vài ngày; vẫn rẻ như mua lẻ.',
            action='buy_feed',
            payload='10',
        ),
        ShopEntry(
            art_key='thuoc',
            name='Thuốc hồi sức',
            price=ITEMS['thuoc'].buy_price,
            meta=f'Túi {farm.items["thuoc"]} · +12 máu',
            detail='Uống trong Hang Sâu để hồi 12 máu. Mua theo số lượng ở bước sau.',
            action='buy_item',
            payload='thuoc',
        ),
    ]
    unlocked = [key for key, crop in CROPS.items() if crop.level <= farm.level]
    if unlocked:
        price = sum(CROPS[key].seed_price for key in unlocked)
        entries.append(ShopEntry(
            art_key='mixed_seeds',
            name='Túi hạt hỗn hợp',
            price=price,
            meta=f'{len(unlocked)} giống · 1 hạt/giống',
            detail='Một hạt của từng giống đang mở, hợp để thử vụ mới mà không chọn mãi.',
            action='seed_bundle',
            payload=','.join(unlocked),
        ))
    return tuple(entries)


def sellable_rows(farm: 'Farm') -> list[tuple[str, int, int]]:
    """(key, quantity, unit price) for everything the shop will buy."""
    rows = []
    for crop, count in farm.produce.items():
        if count:
            key = f'crop:{crop}'
            rows.append((key, count, sale_price(farm, key)))
    for key, item in ITEMS.items():
        if item.sell_price and farm.items.get(key, 0):
            rows.append((key, farm.items[key], sale_price(farm, key)))
    return rows


def sell_total(farm: 'Farm') -> int:
    return sum(quantity * unit for _, quantity, unit in sellable_rows(farm))


def _sell_entries(farm: 'Farm') -> tuple[ShopEntry, ...]:
    entries = []
    for key, quantity, unit in sellable_rows(farm):
        name = ITEMS[key].name
        total = quantity * unit
        entries.append(ShopEntry(
            art_key=key,
            name=name,
            price=unit,
            meta=f'×{quantity} = {total} xu',
            detail=f'Bán từng phần hoặc chọn "Bán tất cả" bên dưới.',
            action='sell_item',
            payload=key,
        ))
    total = sell_total(farm)
    entries.append(ShopEntry(
        art_key='coins',
        name='Bán tất cả sản phẩm',
        price=total,
        meta='Túi đồ · rương được giữ nguyên',
        detail=(f'Thu về {total} xu từ mọi nông sản, cá và sản phẩm vật nuôi trong túi.'
                if total else 'Túi chưa có gì để bán. Hãy thu hoạch, câu cá hoặc lấy sản phẩm chuồng.'),
        action='sell_all',
        disabled=not total,
    ))
    return tuple(entries)


def _upgrade_entries(farm: 'Farm') -> tuple[ShopEntry, ...]:
    entries = []
    for kind, name, detail in _UPGRADES:
        try:
            price = farm.upgrade_cost(kind)
            disabled = False
            meta = f'{price} xu'
        except GameError:
            price = 0
            disabled = True
            meta = 'Đã tối đa'
        entries.append(ShopEntry(
            art_key=f'upgrade:{kind}',
            name=name,
            price=price,
            meta=meta,
            detail=detail,
            action='upgrade',
            payload=kind,
            disabled=disabled,
        ))
    return tuple(entries)


def shop_categories(farm: 'Farm', *, unicode: bool = True) -> tuple[ShopCategory, ...]:
    """Build the live catalogue shown in the shop for the current farm state."""
    icon = (lambda ch: ch) if unicode else (lambda ch: {
        '❦': '+', '▴': 'a', '▤': 'f', '◆': '$', '⌂': '^'}.get(ch, '*'))
    return (
        ShopCategory('seeds', 'Hạt giống', icon('❦'),
                     'Chọn giống theo cấp, thời gian chín và giá bán.',
                     tuple(_seed_entry(farm, key) for key in CROPS)),
        ShopCategory('animals', 'Vật nuôi', icon('▴'),
                     'Mỗi vật nuôi cho sản phẩm riêng; cho ăn và vuốt ve mỗi ngày.',
                     tuple(_animal_entry(farm, key) for key in ANIMAL_TYPES)),
        ShopCategory('supplies', 'Vật tư', icon('▤'),
                     'Thức ăn, bao lớn và túi hạt tiện cho một vụ mới.',
                     _supply_entries(farm)),
        ShopCategory('sell', 'Bán hàng', icon('◆'),
                     'Rương trong nhà luôn được giữ lại, chỉ bán đồ trong túi.',
                     _sell_entries(farm)),
        ShopCategory('upgrades', 'Nâng cấp', icon('⌂'),
                     'Đầu tư dài hạn để ruộng, chuồng và sức lực tốt hơn.',
                     _upgrade_entries(farm)),
    )


def buy_seed_bundle(farm: 'Farm', payload: str) -> str:
    keys = [key for key in payload.split(',') if key in CROPS]
    if not keys:
        raise GameError('Túi hạt hỗn hợp không còn giống nào phù hợp.')
    total = sum(CROPS[key].seed_price for key in keys)
    if farm.coins < total:
        raise GameError(f'Cần {total} xu cho túi hạt hỗn hợp, hiện có {farm.coins} xu.')
    bought = []
    for key in keys:
        farm.buy_seeds(key, 1)
        bought.append(CROPS[key].name)
    return f'Túi hạt hỗn hợp: {", ".join(bought)}. (-{total} xu)'


def sell_item(farm: 'Farm', key: str, quantity: int) -> str:
    """Sell part of one bag slot without touching the protected chest."""
    if key not in ITEMS or ITEMS[key].sell_price <= 0:
        raise GameError('Cửa hàng không thu mua vật phẩm này.')
    if type(quantity) is not int or quantity < 1:
        raise GameError('Số lượng phải là số nguyên dương.')
    if key.startswith('seed:'):
        raise GameError('Hạt giống để trồng, cửa hàng không mua lại.')
    if key.startswith('crop:'):
        crop = key.split(':', 1)[1]
        available = farm.produce.get(crop, 0)
        slot = farm.produce
        slot_key = crop
    else:
        available = farm.items.get(key, 0)
        slot = farm.items
        slot_key = key
    if quantity > available:
        raise GameError(f'Chỉ có {available} {ITEMS[key].name} trong túi.')
    unit = sale_price(farm, key)
    revenue = unit * quantity
    from .daily import ensure_daily, record_daily
    from .tutorial import record_event

    ensure_daily(farm)
    slot[slot_key] -= quantity
    farm.coins += revenue
    farm.sales += revenue
    record_daily(farm, 'sell', revenue)
    if key in FISH_TYPES:
        record_daily(farm, 'sell_fish', quantity)
    record_event(farm, 'sell')
    return f'Đã bán {quantity} {ITEMS[key].name}, nhận {revenue} xu.'


def perform(farm: 'Farm', entry: ShopEntry, quantity: int | None = None) -> str:
    """Run the action behind a shop card; raises ``GameError`` unchanged."""
    if entry.disabled:
        if entry.action == 'upgrade':
            raise GameError(f'{entry.name}: đã đạt mức tối đa.')
        raise GameError(entry.detail)
    if entry.locked:
        raise GameError(f'{entry.name} chưa mở ở cấp hiện tại.')
    if entry.action == 'buy_seed':
        if quantity is None:
            raise GameError('Hãy chọn số lượng hạt muốn mua.')
        return farm.buy_seeds(entry.payload, quantity)
    if entry.action == 'buy_animal':
        return buy_animal(farm, entry.payload)
    if entry.action == 'buy_feed':
        amount = int(entry.payload) if quantity is None else quantity
        return buy_feed(farm, amount)
    if entry.action == 'buy_item':
        amount = 1 if quantity is None else quantity
        return farm.buy_item(entry.payload, amount)
    if entry.action == 'seed_bundle':
        return buy_seed_bundle(farm, entry.payload)
    if entry.action == 'sell_item':
        if quantity is None:
            raise GameError('Hãy chọn số lượng muốn bán.')
        return sell_item(farm, entry.payload, quantity)
    if entry.action == 'sell_all':
        return farm.sell_all()
    if entry.action == 'upgrade':
        return farm.upgrade(entry.payload)
    raise GameError('Quầy hàng này chưa mở.')
