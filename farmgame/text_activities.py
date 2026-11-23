"""Exploration and item menus for terminals without curses support."""

import shutil

from typing import TYPE_CHECKING

from .animals import (ANIMAL_TYPES, buy_animal, collect_products, feed_animals,
                      pet_animal, product_name)
from .catalog import CROPS, ITEMS
from .fishing import finish_fishing, start_fishing
from .inventory import count_item, deposit_all, inventory_rows, transfer_item
from . import regions
from . import tui
from .model import GameError
from .progression import (ATTRIBUTES, SKILLS, character_lines, exchange_points,
                          sale_price, upgrade_attribute, upgrade_skill)
from . import world

if TYPE_CHECKING:
    from .terminal import TerminalGame


def _quantity(ui: 'TerminalGame', maximum: int | None = None) -> int:
    answer = ui.ask('Số lượng [Enter = 1, all = tất cả]: ')
    if answer.lower() == 'all' and maximum is not None:
        return maximum
    try:
        value = int(answer or '1')
    except ValueError:
        raise GameError('Số lượng phải là số nguyên dương.') from None
    if value <= 0:
        raise GameError('Số lượng phải là số nguyên dương.')
    return value


def show_inventory(ui: 'TerminalGame') -> bool:
    from .artwork import icon_for, symbol
    from .inventory import (SECTION_NAMES, SECTION_ORDER, inventory_rows,
                            section_rows)
    ui.coach.event('bag')
    unicode_map = getattr(ui, 'unicode_map', True)
    ui.say('TÚI ĐỒ / RƯƠNG TRONG NHÀ', 'title')
    rows = inventory_rows(ui.farm)
    present = [row for row in rows if row[2] or row[3]]
    bag_total = sum(row[2] for row in present)
    chest_total = sum(row[3] for row in present)
    bag_value = sum(sale_price(ui.farm, key) * bag
                    for key, _, bag, _ in present
                    if sale_price(ui.farm, key))
    chest_value = sum(sale_price(ui.farm, key) * stored
                      for key, _, _, stored in present
                      if sale_price(ui.farm, key))
    ui.wrapped(f'{symbol("coin", unicode=unicode_map)} {ui.farm.coins} xu · '
               f'túi {bag_total} món · rương {chest_total} món', 'cyan')
    ui.wrapped(f'Giá trị bán được: túi {bag_value} xu · rương {chest_value} xu',
               'cyan')
    icons = {'seed': ('❦', '+'), 'crop': ('❧', '%'),
             'fish': ('◈', 'o'), 'other': ('▥', 'o')}
    if present:
        ui.wrapped('  Vật phẩm                   Túi / Rương', 'gold')
    for section in SECTION_ORDER[1:]:
        items = section_rows(present, section)
        if not items:
            continue
        rich, plain = icons[section]
        ui.say(f'{rich if unicode_map else plain} {SECTION_NAMES[section]} '
               f'· {len(items)} loại', 'green')
        for key, name, bag, stored in items:
            value = sale_price(ui.farm, key)
            icon = icon_for(key, unicode=unicode_map)
            ui.wrapped(f'  {icon} {name:<23} {bag:>4} / {stored:<4}'
                       + (f' · bán {value} xu/cái' if value else ''))
    if not present:
        ui.wrapped('Túi và rương đang trống.', 'dim')
    ui.wrapped('Đồ trong rương không bị bán khi bán hàng ở chợ.', 'dim')
    ui.ask('Enter để quay lại... ')
    return False


def show_farm(ui: 'TerminalGame') -> bool:
    """Readable field overview for the text frontend."""
    from .artwork import icon_for
    from .catalog import CROPS
    ui.say(f'CÁNH ĐỒNG · {ui.farm.size}×{ui.farm.size}', 'title')
    ready = sum(plot.ready for plot in ui.farm.plots.values())
    thirsty = sum(bool(plot.crop) and not plot.dead and not plot.ready
                  and not ui.farm.is_watered(key)
                  for key, plot in ui.farm.plots.items())
    ui.wrapped(f'{ready} chín · {thirsty} cần tưới · '
               f'{sum(not plot.crop for plot in ui.farm.plots.values())} trống',
               'cyan')
    for coordinate, plot in ui.farm.plots.items():
        if plot.dead:
            state = 'héo · cần dọn'
        elif plot.ready:
            state = f'{CROPS[plot.crop].name} · chín'
        elif plot.crop:
            info = CROPS[plot.crop]
            state = (f'{info.name} {plot.growth}/{info.days} · '
                     f'{"đủ nước" if ui.farm.is_watered(coordinate) else "cần tưới"}')
        else:
            state = 'trống'
        icon = icon_for('crop:' + plot.crop if plot.crop else 'mixed_seeds',
                        unicode=getattr(ui, 'unicode_map', True))
        ui.wrapped(f'{coordinate} {icon} {state}')
    ui.wrapped('Dùng 1 trồng, 2 tưới, 3 thu hoạch/dọn; F mở lại bảng này.', 'dim')
    ui.ask('Enter để quay lại... ')
    return False


def show_barn(ui: 'TerminalGame') -> bool:
    from .animals import (ANIMAL_TYPES, ANIMAL_ZONES, product_name,
                          zone_animals)
    from .artwork import hearts, icon_for
    ui.say('CHUỒNG · CÁC KHU CHĂN NUÔI', 'title')
    for zone in ANIMAL_ZONES.values():
        unlocked = ui.farm.level >= zone.level
        animals = zone_animals(ui.farm, zone)
        state = (f'{len(animals)}/{zone.capacity} chỗ' if unlocked
                 else f'khoá · mở cấp {zone.level}')
        zone_icon = zone.icon if getattr(ui, 'unicode_map', True) else {
            '⌂': 'H', '⚘': '&', '↟': '^'}.get(zone.icon, '*')
        ui.say(f'{zone_icon} {zone.name} · {state}', 'green' if unlocked else 'dim')
        if not unlocked:
            ui.wrapped(zone.description, 'dim')
            continue
        for animal in animals:
            ui.wrapped(f'  {icon_for(animal.kind, unicode=getattr(ui, "unicode_map", True))} '
                       f'{animal.name} · {ANIMAL_TYPES[animal.kind].name} · '
                       f'{animal.age} ngày · {"đã ăn" if animal.fed else "ĐÓI"} · '
                       f'{hearts(animal.friendship, maximum=5, unicode=getattr(ui, "unicode_map", True))} · '
                       f'{product_name(animal.kind)} ×{animal.produce}')
        if not animals:
            ui.wrapped('  Chưa có vật nuôi trong khu này.', 'dim')
    ui.wrapped(f'Tổng {len(ui.farm.animals)}/{ui.farm.barn_capacity} chỗ · '
               f'{ui.farm.items["feed"]} thức ăn.', 'cyan')
    ui.ask('Enter để quay lại... ')
    return False


def show_fish_collection(ui: 'TerminalGame') -> bool:
    from .catalog import EXTRA_ITEMS, FISH_TYPES
    from .artwork import icon_for
    unicode = getattr(ui, 'unicode_map', True)
    ui.say('BỘ SƯU TẦM CÁ · HỒ SEN', 'title')
    ui.wrapped(f'{ui.farm.fish_species}/{len(FISH_TYPES)} loài · '
               f'{ui.farm.fish_points} điểm · '
               f'giá trị {ui.farm.fish_collection_value} xu · '
               f'{ui.farm.fish_caught} lần câu', 'cyan')
    for key, fish in FISH_TYPES.items():
        count = ui.farm.fish_collection.get(key, 0)
        if ui.farm.level < fish.level:
            state = f'mở cấp {fish.level}'
        elif count:
            state = f'{count} lần'
        else:
            state = 'chưa câu'
        ui.wrapped(f'{icon_for(key, unicode=unicode)} {fish.name} · {fish.rarity} · '
                   f'{state} · {fish.points} điểm · bán {EXTRA_ITEMS[key].sell_price} xu')
    ui.wrapped('Câu gần hồ Sen bằng E; mỗi loài mới cộng điểm sưu tầm.', 'dim')
    ui.ask('Enter để quay lại... ')
    return False


def character_menu(ui: 'TerminalGame') -> bool:
    from .artwork import pips, player_portrait, stat_icon
    ui.coach.event('character')
    definitions = [*[(key, info, True) for key, info in ATTRIBUTES.items()],
                   *[(key, info, False) for key, info in SKILLS.items()]]
    while True:
        ui.say(f'NHÂN VẬT / {ui.farm.player_name} · Cấp {ui.farm.level}', 'title')
        for line in player_portrait(ui.farm.avatar, unicode=getattr(ui, 'unicode_map', True)):
            ui.say('   ' + line, 'blue')
        for line in character_lines(ui.farm)[:5]:
            ui.wrapped(line)
        for index, (key, info, is_attribute) in enumerate(definitions, 1):
            values = ui.farm.attributes if is_attribute else ui.farm.skills
            icon = stat_icon(key, unicode=getattr(ui, 'unicode_map', True))
            dots = pips(values[key], unicode=getattr(ui, 'unicode_map', True))
            ui.wrapped(f'[{index}] {icon} {info.name} {dots} {values[key]}/5 · {info.description}')
        can_exchange = (all(value >= 5 for value in ui.farm.attributes.values())
                        and all(value >= 5 for value in ui.farm.skills.values())
                        and (ui.farm.attribute_points or ui.farm.skill_points))
        if can_exchange:
            ui.wrapped('[8] Đổi toàn bộ điểm dư thành xu')
        ui.wrapped('[g] Trang bị và sức chiến đấu · [i] Túi đồ · '
                   '[a] Thành tựu')
        choice = ui.ask('Chọn [1-7 nâng, g trang bị, i túi, a thành tựu, '
                        '8 đổi điểm, 0/q về]: ').lower()
        if choice in ('0', 'q', ''):
            return False
        if choice == 'g':
            from .forge import gear_lines
            for line in gear_lines(ui.farm):
                ui.wrapped(line)
            continue
        if choice == 'a':
            from .achievements import achievement_lines
            for line in achievement_lines(ui.farm, unicode=getattr(ui, 'unicode_map', True)):
                ui.wrapped(line)
            continue
        if choice == 'i':
            from .inventory import inventory_rows
            rows = [f'{name}: {bag}' for _, name, bag, _ in
                    inventory_rows(ui.farm) if bag]
            ui.say('TÚI ĐỒ ĐANG MANG', 'title')
            if rows:
                for line in rows:
                    ui.wrapped(line)
            else:
                ui.wrapped('Túi đang trống.')
            continue
        if can_exchange and choice == '8':
            try:
                ui.messages = [exchange_points(ui.farm)]
            except GameError as error:
                ui.wrapped(str(error), 'red')
            else:
                ui.persist()
                ui.wrapped(ui.messages[-1], 'green')
            continue
        if choice not in tuple(str(i) for i in range(1, 8)):
            ui.wrapped('Chọn 1–7, g, i, a hoặc 0 để quay lại.')
            continue
        key, info, is_attribute = definitions[int(choice) - 1]
        try:
            result = (upgrade_attribute if is_attribute else upgrade_skill)(ui.farm, key)
        except GameError as error:
            ui.wrapped(str(error), 'red')
        else:
            ui.messages = [result]
            ui.persist()
            ui.wrapped(result, 'green')


def chest_menu(ui: 'TerminalGame') -> bool:
    ui.say('RƯƠNG ĐỒ', 'title')
    ui.wrapped('[1] Gửi đồ  [2] Lấy đồ  [3] Cất toàn bộ túi  [0] Quay lại')
    choice = ui.ask('Chọn: ')
    if choice == '0':
        return False
    if choice == '3':
        ui.messages = [deposit_all(ui.farm)]
        return True
    if choice not in ('1', '2'):
        raise GameError('Chọn 1, 2 hoặc 3 để dùng rương.')
    direction = 'deposit' if choice == '1' else 'withdraw'
    available = [(key, name, bag if choice == '1' else stored)
                 for key, name, bag, stored in inventory_rows(ui.farm)
                 if (bag if choice == '1' else stored) > 0]
    if not available:
        raise GameError('Không có vật phẩm để chuyển theo hướng này.')
    for index, (_, name, amount) in enumerate(available, 1):
        ui.wrapped(f'[{index}] {name}: {amount}')
    answer = ui.ask('Chọn vật phẩm [0 = quay lại]: ')
    if answer == '0':
        return False
    if not answer.isdecimal() or not 1 <= int(answer) <= len(available):
        raise GameError('Số vật phẩm không hợp lệ.')
    key, _, amount = available[int(answer) - 1]
    ui.messages = [transfer_item(ui.farm, key, _quantity(ui, amount), direction)]
    return True


def buy_animal_menu(ui: 'TerminalGame') -> bool:
    from .animals import zone_for, zone_unlocked
    from .artwork import icon_for
    ui.say('MUA VẬT NUÔI', 'title')
    keys = list(ANIMAL_TYPES)
    for index, key in enumerate(keys, 1):
        info = ANIMAL_TYPES[key]
        zone = zone_for(key)
        lock = ('' if zone_unlocked(ui.farm, zone)
                else f' · mở cấp {zone.level}')
        ui.wrapped(f'[{index}] {icon_for(key, unicode=getattr(ui, "unicode_map", True))} {info.name}: {info.price} xu · '
                   f'{zone.name} · trưởng thành sau {info.mature_days} ngày · '
                   f'{product_name(key)} mỗi {info.interval} ngày{lock}')
    choice = ui.ask(f'Chọn [1–{len(keys)}, 0 = quay lại]: ')
    if choice == '0':
        return False
    if not choice.isdecimal() or not 1 <= int(choice) <= len(keys):
        raise GameError(f'Chọn một vật nuôi từ 1 đến {len(keys)}.')
    key = keys[int(choice) - 1]
    ui.messages = [buy_animal(ui.farm, key)]
    return True


def barn_menu(ui: 'TerminalGame') -> bool:
    farm = ui.farm
    ui.say(f'CHUỒNG: {len(farm.animals)}/{farm.barn_capacity} chỗ · '
           f'{farm.items["feed"]} phần thức ăn', 'title')
    from .animals import zone_for
    for index, animal in enumerate(farm.animals, 1):
        info = ANIMAL_TYPES[animal.kind]
        ui.wrapped(f'{index}. {animal.name} · {zone_for(animal.kind).name} · '
                   f'{animal.age} ngày · {"Đã ăn" if animal.fed else "Đói"} · '
                   f'Thân {animal.friendship}/5 · {animal.produce} {product_name(animal.kind)}')
    ui.wrapped('[1] Cho cả đàn ăn  [2] Vuốt ve  [3] Lấy sản phẩm  [4] Mua con mới  [0] Về')
    choice = ui.ask('Chọn: ')
    if choice == '0':
        return False
    if choice == '1':
        ui.messages = [feed_animals(farm)]
    elif choice == '2':
        answer = ui.ask('Số vật nuôi muốn vuốt ve: ')
        if not answer.isdecimal():
            raise GameError('Nhập số thứ tự vật nuôi.')
        ui.messages = [pet_animal(farm, int(answer) - 1)]
    elif choice == '3':
        ui.messages = [collect_products(farm)]
    elif choice == '4':
        return buy_animal_menu(ui)
    else:
        raise GameError('Chọn thao tác từ 1 đến 4.')
    return True


def forge_menu(ui: 'TerminalGame') -> bool:
    """Line-based forge panel for the mine camp."""
    from .catalog import GEAR, ITEMS
    from .forge import forge, missing_for, recipe_for, recipe_label, tier_label
    keys = list(GEAR)
    while True:
        ui.say(f'LÒ RÈN · {ui.farm.coins} xu', 'title')
        for index, key in enumerate(keys, 1):
            info = GEAR[key]
            level = ui.farm.gear.get(key, 0)
            recipe = recipe_for(ui.farm, key)
            missing = missing_for(ui.farm, key, recipe)
            if recipe is None:
                state = 'đã tối đa'
            elif missing:
                state = 'thiếu ' + ', '.join(
                    f'{amount} {"xu" if item == "coins" else ITEMS[item].name}'
                    for item, amount in missing.items())
            else:
                state = 'sẵn sàng rèn'
            ui.wrapped(f'[{index}] {info.icon} {info.name} · {tier_label(level)} · {state}')
            ui.wrapped(f'    {info.effect} {recipe_label(recipe)}', 'dim')
        ui.wrapped('[0] Quay lại', 'dim')
        answer = ui.ask('Chọn trang bị muốn rèn: ').strip()
        if answer in ('', '0', 'q', 'esc'):
            return False
        if not answer.isdecimal() or not 1 <= int(answer) <= len(keys):
            ui.wrapped(f'Chọn trang bị từ 1 đến {len(keys)} hoặc 0 để quay lại.')
            continue
        key = keys[int(answer) - 1]
        try:
            result = forge(ui.farm, key)
        except GameError as error:
            ui.wrapped(str(error), 'red')
            continue
        ui.messages = [result]
        ui.persist()
        ui.wrapped(result, 'gold')


def dungeon_menu(ui: 'TerminalGame') -> bool:
    """Line-based Hang Sâu mode with the same rules as the curses panel."""
    from .dungeon import (MAX_DEPTH, advance, flee, player_attack,
                          player_defend, player_skill, start_run, status_lines,
                          use_potion)
    farm = ui.farm
    try:
        run = start_run(farm)
    except GameError as error:
        ui.messages = [str(error)]
        return False
    ui.messages = ['Bước vào Hang Sâu.']
    ui.persist()
    while True:
        ui.say(f'HANG SÂU · TẦNG {run.depth}/{MAX_DEPTH}', 'title')
        for line in status_lines(farm, run, unicode=getattr(ui, 'unicode_map', True)):
            ui.wrapped(line)
        if run.log:
            ui.wrapped(run.log[-1], 'green')
        if run.phase == 'battle':
            answer = ui.ask('1 tấn công · 2 uống thuốc · 3 rút lui · '
                            '4 đỡ đòn · 5 kỹ năng: ').strip().lower()
            try:
                if answer in ('3', '0', 'q', 'esc'):
                    ui.messages = [flee(farm, run)]
                    break
                if answer == '2':
                    ui.messages = [use_potion(farm, run)]
                elif answer in ('4', 'd', 'defend', 'đỡ'):
                    ui.messages = [player_defend(farm, run)]
                elif answer in ('5', 'k', 'skill', 'kỹ năng'):
                    ui.messages = [player_skill(farm, run)]
                elif answer in ('', '1', 'e', ' '):
                    ui.messages = [player_attack(farm, run)]
                else:
                    ui.wrapped('Chọn 1, 2, 3, 4 hoặc 5.')
                    continue
            except GameError as error:
                ui.wrapped(str(error), 'red')
                continue
        elif run.phase == 'floor':
            answer = ui.ask('1 xuống tầng tiếp · 2 trở về: ').strip().lower()
            if answer in ('2', '0', 'q', 'esc'):
                break
            try:
                ui.messages = [advance(farm, run)]
            except GameError as error:
                ui.wrapped(str(error), 'red')
                continue
        else:
            ui.wrapped('Nhấn Enter để trở về mỏ.', 'dim')
            break
        ui.persist()
    ui.persist()
    return True


def market_menu(ui: 'TerminalGame') -> bool:
    from .artwork import art_for
    ui.say('CỬA HÀNG LÀNG · QUẦY HÀNG', 'title')
    ui.wrapped('[1] ❦ Hạt giống   [2] ◆ Bán đồ trong túi   [3] ▤ Thức ăn (5 xu/phần)')
    ui.wrapped('[4] ▴ Vật nuôi     [5] ⌂ Nâng cấp           [6] ❦ Túi hạt hỗn hợp')
    ui.wrapped('[7] ▤ Bao thức ăn 10 phần   [8] ✚ Thuốc hồi sức (40 xu)')
    ui.wrapped('[0] Quay lại')
    ui.wrapped('Mỗi quầy có biểu tượng riêng; chế độ đồ họa hiển thị thẻ có hình minh họa.', 'dim')
    choice = ui.ask('Chọn: ')
    if choice == '0':
        return False
    if choice == '1':
        return ui.shop()
    if choice == '2':
        return ui.sell()
    if choice == '3':
        ui.messages = [ui.farm.buy_item('feed', _quantity(ui))]
        return True
    if choice == '4':
        return buy_animal_menu(ui)
    if choice == '5':
        return ui.upgrade()
    if choice == '6':
        from .shop import buy_seed_bundle
        unlocked = [key for key, crop in CROPS.items() if crop.level <= ui.farm.level]
        ui.messages = [buy_seed_bundle(ui.farm, ','.join(unlocked))]
        return True
    if choice == '7':
        ui.messages = [ui.farm.buy_item('feed', 10)]
        return True
    if choice == '8':
        ui.messages = [ui.farm.buy_item('thuoc', _quantity(ui))]
        return True
    raise GameError('Chọn thao tác từ 1 đến 8.')


def fishing(ui: 'TerminalGame') -> bool:
    round_ = start_fishing(ui.farm)
    ui.persist()
    ui.wrapped('CÂU CÁ: r nâng cần, Enter thả. Giữ cá > trong thanh = để bắt; q hủy.', 'title')
    while not round_.done:
        track = [' '] * 36
        for index in range(36):
            if abs(index / 35 - round_.bar) <= round_.bar_width / 2:
                track[index] = '='
        track[min(35, int(round_.target * 35))] = '>'
        ui.say(f'[{"".join(track)}] {round_.progress:.0%}')
        answer = ui.ask('[r / Enter / q]: ').lower()
        if answer in ('q', '0'):
            round_.done = True
            break
        if answer not in ('r', ''):
            ui.wrapped('Chọn r hoặc Enter để điều khiển cần câu.')
            continue
        round_.step(0.25, answer == 'r')
    ui.messages = [finish_fishing(ui.farm, round_)]
    return True


def cook_menu(ui: 'TerminalGame') -> bool:
    """Home kitchen for the line-based frontend."""
    from .cooking import cook, ingredient_line, recipe_rows
    ui.say('BẾP NHÀ · NẤU ĂN', 'title')
    rows = recipe_rows(ui.farm)
    for index, (recipe, missing) in enumerate(rows, 1):
        if ui.farm.level < recipe.level:
            state = f'mở cấp {recipe.level}'
        elif missing:
            state = 'thiếu ' + ', '.join(
                f'{ITEMS[item].name} ×{amount}'
                for item, amount in missing.items())
        else:
            state = 'sẵn sàng'
        ui.wrapped(f'[{index}] {recipe.name} · {state}')
        ui.wrapped(f'    {ingredient_line(recipe, missing)} · '
                   f'+{recipe.energy} năng lượng · +{recipe.xp} XP')
    ui.wrapped('[0] Quay lại', 'dim')
    answer = ui.ask('Chọn món để nấu: ').strip()
    if answer in ('', '0', 'q', 'esc'):
        return False
    if not answer.isdecimal() or not 1 <= int(answer) <= len(rows):
        raise GameError(f'Chọn món từ 1 đến {len(rows)} hoặc 0 để quay lại.')
    recipe, _ = rows[int(answer) - 1]
    ui.messages = [cook(ui.farm, recipe.key)]
    return True


def show_regions(ui: 'TerminalGame') -> bool:
    """Fast-travel directory shared with the curses region panel."""
    ui.say('KHU VỰC · ĐI NHANH', 'title')
    cards = regions.travel_regions(ui.farm)
    for index, region in enumerate(cards, 1):
        lock = '' if regions.can_travel(ui.farm, region) else f' · mở cấp {region.level}'
        icon = region.icon if getattr(ui, 'unicode_map', True) else region.ascii_icon
        ui.wrapped(f'[{index}] {icon} {region.name} · {region.description}{lock}')
    pages_choice = None
    if not getattr(ui.farm, 'map_pages', False):
        pages_choice = len(cards) + 1
        ui.wrapped(f'[{pages_choice}] Bật bản đồ theo khu vực (mỗi lần một trang)', 'green')
    ui.wrapped('[0] Quay lại', 'dim')
    answer = ui.ask('Chọn khu vực: ').strip()
    if answer in ('', '0', 'q', 'esc'):
        return False
    if not answer.isdecimal():
        raise GameError('Chọn khu vực bằng số hoặc 0 để quay lại.')
    choice = int(answer)
    if pages_choice is not None and choice == pages_choice:
        ui.farm.map_pages = True
        ui.messages = ['Đã bật bản đồ theo khu vực.']
        return True
    if not 1 <= choice <= len(cards):
        raise GameError(f'Chọn khu vực từ 1 đến {len(cards)} hoặc 0 để quay lại.')
    ui.messages = [regions.travel(ui.farm, cards[choice - 1].key)]
    return True


def interact(ui: 'TerminalGame') -> bool:
    farm = ui.farm
    action, hint = world.context(farm)
    if action == 'home':
        ui.messages = [world.enter_home(farm)]
        ui.coach.event('enter_home')
    elif action == 'exit':
        ui.messages = [world.leave_home(farm)]
    elif action == 'tv':
        ui.messages = [farm.forecast_report()]
        ui.coach.event('tv')
        return False
    elif action == 'bed':
        return ui.sleep()
    elif action == 'chest':
        return chest_menu(ui)
    elif action == 'kitchen':
        return cook_menu(ui)
    elif action == 'barn':
        return barn_menu(ui)
    elif action == 'mine':
        ui.messages = [world.enter_mine(farm)]
    elif action == 'mine_exit':
        ui.messages = [world.leave_mine(farm)]
    elif action == 'rock':
        from .mining import mine_rock
        rock = world.target_rock(farm)
        if rock is None:
            ui.messages = ['Hãy đứng sát tảng đá rồi nhấn e.']
            return False
        ui.messages = [mine_rock(farm, *rock)]
    elif action == 'forge':
        return forge_menu(ui)
    elif action == 'dungeon_gate':
        return dungeon_menu(ui)
    elif action == 'shop':
        return market_menu(ui)
    elif action == 'fish':
        return fishing(ui)
    elif action == 'forest':
        return ui.work()
    elif action == 'npc':
        return conversation(ui)
    elif action == 'plot':
        key = world.target_plot(farm)
        plot = farm.plots[key]
        if plot.dead:
            ui.messages = [farm.clear(key)]
        elif plot.ready:
            ui.messages = [farm.harvest(key)]
        elif plot.crop:
            ui.messages = [farm.water(key)]
        else:
            crop = ui.choose_crop(planting=True)
            if crop is None:
                return False
            ui.messages = [farm.plant(key, crop)]
    else:
        ui.messages = ['Không có gì để tương tác ở đây. ' + hint]
        return False
    return True


def _dialogue_box_text(ui: 'TerminalGame', npc, node) -> None:
    """Render one RPG-style dialogue box in the line interface."""
    from .explore import wrap_cells
    unicode = getattr(ui, 'unicode_map', True)
    g = tui.glyphs(unicode)
    width = max(32, min(getattr(ui, 'width', 80), 88))
    inner = max(20, width - 2)
    raw_title = f' {npc.name} · {npc.role} '
    title = tui.ellipsize(raw_title, inner - 2, unicode=unicode)
    ui.say(g['tl'] + g['h'] + title + g['h'] * max(0, inner - 1 - tui.cells(title)) + g['tr'],
           'cyan')
    for line in wrap_cells(node.npc_line, max(12, inner - 2)):
        ui.say(g['v'] + ' ' + tui.pad(line, inner - 2) + ' ' + g['v'], 'white')
    if node.choices:
        ui.say(g['v'] + ' ' + tui.pad('', inner - 2) + ' ' + g['v'], 'dim')
        for index, choice in enumerate(node.choices, 1):
            for offset, line in enumerate(wrap_cells(
                    f'{index}. {choice.text}', max(12, inner - 2))):
                ui.say(g['v'] + ' ' + tui.pad(line, inner - 2) + ' ' + g['v'],
                       'white')
    ui.say(g['bl'] + g['h'] * inner + g['br'], 'cyan')


def conversation(ui: 'TerminalGame') -> bool:
    from .villagers import TOPICS, nearby_npc
    from .dialogue import begin_dialogue, choose_response, dialogue_node
    npc = nearby_npc(ui.farm)
    if npc is None:
        raise GameError('Hãy đến gần một dân làng để trò chuyện.')
    from .artwork import hearts, npc_portrait
    from .villagers import bond_title
    friendship = ui.farm.friendships[npc.id]
    ui.say(f'{npc.name} · {npc.role} · {bond_title(friendship)} · '
           f'{hearts(friendship, unicode=getattr(ui, "unicode_map", True))} {friendship}/10', 'title')
    for line in npc_portrait(npc.id, unicode=getattr(ui, 'unicode_map', True)):
        ui.say('   ' + line, 'blue')
    ui.wrapped(npc.description)
    ui.wrapped(f'“{npc.motto}” · Thích: {npc.likes}')
    topics = list(TOPICS)
    for index, key in enumerate(topics, 1):
        ui.wrapped(f'[{index}] {TOPICS[key]}')
    choice = ui.ask(f'Chủ đề [1–{len(topics)}, 0/q = quay lại]: ').lower()
    if choice in ('0', 'q', '', '\x1b'):
        return False
    if not choice.isdecimal() or not 1 <= int(choice) <= len(topics):
        raise GameError(f'Chọn chủ đề từ 1 đến {len(topics)}.')
    current = begin_dialogue(ui.farm, npc.id, topics[int(choice) - 1])
    changed = False
    while not current.done:
        node = dialogue_node(current)
        _dialogue_box_text(ui, npc, node)
        answer = ui.ask('Bạn trả lời [1/2, 0/q = dừng trò chuyện]: ').lower()
        if answer in ('0', 'q', '', '\x1b'):
            break
        if answer not in tuple(str(i) for i in range(1, len(node.choices) + 1)):
            ui.wrapped('Chọn một câu trả lời có trong danh sách.')
            continue
        reply = choose_response(ui.farm, current, node.choices[int(answer) - 1].id)
        changed = True
        ui.messages = [reply]
        ui.persist()
        ui.wrapped(reply, 'blue')
    if changed:
        ui.messages = ['\n'.join(current.history)]
    if current.done:
        ui.coach.event('talk', npc_id=npc.id, done=True)
    return changed


def show_directory(ui: 'TerminalGame') -> bool:
    from .artwork import hearts, npc_portrait
    from .villagers import NPCS, bond_title
    ui.say('DÂN LÀNG · CHÂN DUNG VÀ QUAN HỆ', 'title')
    for npc in NPCS.values():
        friendship = ui.farm.friendships[npc.id]
        ui.say(f'{npc.glyph} · {npc.name} · {npc.role} · '
               f'{hearts(friendship, unicode=getattr(ui, "unicode_map", True))} {friendship}/10 · {bond_title(friendship)}', 'green')
        for line in npc_portrait(npc.id, unicode=getattr(ui, 'unicode_map', True)):
            ui.say('   ' + line, 'blue')
        ui.wrapped(f'“{npc.motto}” · Thích: {npc.likes}')
        ui.wrapped(f'Lịch: {npc.schedule} · Vị trí: {npc.position}', 'dim')
        distance = (abs(npc.position[0] - ui.farm.player_x)
                    + abs(npc.position[1] - ui.farm.player_y))
        ui.wrapped(f'Cách bạn {distance} bước.' if ui.farm.area == 'village'
                   else 'Hiện bạn đang ở ngoài làng.', 'dim')
    ui.wrapped('Hãy đến gần và nhấn E để trò chuyện.', 'dim')
    ui.ask('Enter để quay lại... ')
    return False


def show_atlas(ui: 'TerminalGame') -> bool:
    ui.coach.event('map')
    from .explore import overview_rows
    size = shutil.get_terminal_size((80, 24))
    ui.say('BẢN ĐỒ TOÀN LÀNG', 'title')
    for row in overview_rows(ui.farm, max(1, size.columns - 1), max(1, size.lines - 6),
                             unicode=getattr(ui, 'unicode_map', True)):
        ui.say(row)
    ui.wrapped(f'{ui.farm.avatar} bạn · 1–5 dân làng · H nhà · M tiệm · B chuồng · : ruộng', 'dim')
    ui.wrapped(', đồng hoa · O quảng trường · T rừng · ~ hồ/biển · ^ đồi · v thung lũng · t đồi trà · ◉ Cửa Mỏ (76,6)', 'dim')
    ui.wrapped('R khu vực · đi nhanh giữa các vùng của làng.', 'dim')
    ui.ask('Enter để quay lại... ')
    return False


def _draw_map(ui: 'TerminalGame') -> str:
    """Draw one screenful and return the prompt whose row is reserved below it."""
    from .explore import fit_text
    from .map_art import map_cell, map_legend, supports_unicode
    from .map_view import (map_layout, frame_lines, objective_line,
                           status_line, cells)
    from .tutorial import tutorial_hint
    farm = ui.farm
    if ui.clear_screen:
        print('\033[2J\033[H', end='')
    terminal = shutil.get_terminal_size((80, 24))
    width = max(1, terminal.columns - 1)
    unicode_map = getattr(ui, 'unicode_map', supports_unicode())
    prompts = (
        'Q về menu · WASD đi · E dùng · R khu vực · Z rộng · N/O · G hình · T dẫn · M bản đồ · B menu > ',
        'Q · WASD · E · R khu vực · Z rộng · G hình · N/O · T · M · B > ',
        'Q · E · R · G hình · T · M > ',
        'Q · G hình > ',
    )
    prompt = next((text for text in prompts if cells(text) <= width), '> ')
    expanded = bool(getattr(ui, 'map_expanded', False))
    layout = map_layout(farm, width, terminal.lines, expanded=expanded)
    activities = getattr(ui, 'activities', None)
    path = (activities.path_points() if activities and activities.running
            else ui.coach.path_points())
    # Every HUD entry occupies one physical line. Keep errors, next-step keys
    # and auto controls before giving optional legends and old logs any space.
    footer = [(0, objective_line(farm, width, unicode=unicode_map), 'green')]
    footer.extend((2, legend, 'dim')
                  for legend in map_legend(farm, unicode=unicode_map))
    action, context = world.context(farm)
    if action == 'none' and width < 40:
        context = 'WASD đi E dùng T dẫn'
    footer.append((0, context, 'gold'))
    messages = ui.messages[-3:]
    for index, message in enumerate(messages):
        latest = index == len(messages) - 1
        priority = (0 if ui.unsaved else 1) if latest else 3
        footer.append((priority, message, 'red' if latest and ui.unsaved else 'blue'))
    hint = tutorial_hint(farm) if farm.tutorial.status == 'active' else None
    if hint is not None:
        key = hint.key.replace(' / mũi tên', '')
        footer.extend(((0, f'T dẫn · {key} · {hint.title}', 'gold'),
                       (4, hint.body, 'dim')))
    if activities and activities.running:
        auto_lines = activities.status_lines()
        controls = 'AUTO P nghỉ O dừng'
        if width >= 40:
            controls += ' · +/- tốc độ'
        if width >= 70:
            controls += ' | ' + auto_lines[0].partition(' · ')[2]
        summary = auto_lines[1]
        for prefix in ('Auto đang chạy · ', 'Auto tạm dừng · '):
            if summary.startswith(prefix):
                summary = summary[len(prefix):]
                break
        if activities.auto.paused:
            summary = 'Nghỉ · ' + summary
        footer.extend(((0, controls, 'gold'), (0, summary, 'gold')))
    if ui.unsaved:
        footer.append((0, 'CHƯA LƯU ĐƯỢC · Q thử lưu lại', 'red'))
    available = max(1, terminal.lines - 3 - 2 * int(layout.framed))
    required = sum(priority == 0 for priority, _, _ in footer)
    budget = min(max(0, available - 1), max(required, available // 2))
    chosen = {index for index, _ in sorted(enumerate(footer),
              key=lambda item: (item[1][0], item[0]))[:budget]}
    footer = [line for index, line in enumerate(footer) if index in chosen]
    if expanded:
        footer = [line for line in footer if line[0] == 0][:1]
    layout = map_layout(farm, width, terminal.lines,
                        reserved_rows=3 + len(footer), expanded=expanded)
    ui.say(fit_text(f'{world.location_name(farm)} · ({farm.player_x}, {farm.player_y})', width), 'title')
    status = status_line(farm, width, unicode=unicode_map)
    if width < 30:
        status = f'Ngày {farm.day} · Sức {farm.energy}/{farm.energy_limit}'
    ui.say(fit_text(status, width),
           'red' if farm.hp <= max(1, farm.max_hp // 3) else 'blue')
    if expanded:
        for _, text, style in footer:
            ui.say(fit_text(text, width), style)
    side = ''
    if layout.framed:
        from . import pages
        top, bottom, side = frame_lines(layout, farm.area, unicode=unicode_map,
                                        page_name=pages.page_name(farm))
        ui.say(top, 'blue')
    paint = getattr(ui, 'paint', None)
    # Map roles are styled directly by TerminalGame.paint; keep the old
    # aliases for UI accents that still use the basic colour names.
    styles = {'cyan': 'blue', 'yellow': 'gold', 'magenta': 'gold'}
    for y in range(layout.top, layout.top + layout.rows):
        row = []
        for x in range(layout.left, layout.left + layout.cols):
            art = map_cell(farm, x, y, unicode=unicode_map, path=path)
            text = art.glyph + (art.tail if layout.cell == 2 else '')
            row.append(paint(text, styles.get(art.color, art.color)) if callable(paint) else text)
        ui.say(side + ''.join(row) + side)
    if layout.framed:
        ui.say(bottom, 'blue')
    if not expanded:
        for _, text, style in footer:
            ui.say(fit_text(text, width), style)
    return prompt


def map_mode(ui: 'TerminalGame') -> bool:
    ui.coach.event('map')
    directions = {'w': 'up', 's': 'down', 'a': 'left', 'd': 'right'}
    while True:
        prompt = _draw_map(ui)
        command = ui.ask(prompt).lower()
        try:
            if command == 'b':
                return False
            if command in ('q', '0'):
                raise EOFError
            if command == 'i':
                show_inventory(ui)
            elif command == 'c':
                character_menu(ui)
            elif command == 't':
                ui.coach.panel()
            elif command == 'n':
                ui.activities.daily_menu()
            elif command == 'o':
                ui.activities.open_auto()
            elif command == 'g':
                ui.toggle_map_style()
            elif command == 'z':
                ui.map_expanded = not getattr(ui, 'map_expanded', False)
                ui.messages = ['Khung bản đồ: RỘNG (nhiều ô hơn).'
                               if ui.map_expanded else 'Khung bản đồ: tiêu chuẩn.']
            elif command in ('m', 'atlas'):
                show_atlas(ui)
            elif command == 'j':
                show_directory(ui)
            elif command == 'r':
                if show_regions(ui):
                    ui.persist()
            elif command == 'e':
                if interact(ui):
                    ui.persist()
            elif command and all(char in directions for char in command):
                moved = 0
                old_page = None
                if getattr(ui.farm, 'map_pages', False):
                    from .pages import page_for_coord
                    page = page_for_coord(ui.farm.player_x, ui.farm.player_y)
                    old_page = page.key if page is not None else None
                for char in command:
                    before_x, before_y = ui.farm.player_x, ui.farm.player_y
                    if world.move(ui.farm, directions[char]):
                        moved += 1
                        ui.coach.event('move', from_x=before_x, from_y=before_y)
                        ui.coach.sync()
                message = f'Đã đi {moved} bước.'
                if getattr(ui.farm, 'map_pages', False):
                    from .pages import page_for_coord
                    page = page_for_coord(ui.farm.player_x, ui.farm.player_y)
                    if page is not None and page.key != old_page:
                        message = f'Đã sang {page.name}.'
                ui.messages = [message]
                ui.persist()
            elif command:
                raise GameError('Dùng w/a/s/d, e, m/atlas, r khu vực, n, o, t, c, j, i, b hoặc q trong bản đồ.')
        except GameError as error:
            ui.messages = [str(error)]
