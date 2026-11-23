"""Versioned JSON saves with validation and atomic file replacement."""

import json
import os
import shutil
import tempfile
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path

from .animals import ANIMAL_TYPES, Animal
from .catalog import (EXTRA_ITEMS, FISH_TYPES, GEAR, ITEMS, MAX_GEAR,
                      empty_fish_collection, empty_gear)
from .model import CROPS, WEATHER, Farm, Plot, coordinates
from .world import MINE_HEIGHT, MINE_ROCKS, MINE_WIDTH, walkable
from .villagers import NPCS
from .progression import ATTRIBUTES, SKILLS
from .identity import AVATARS, OUTFITS, BACKGROUNDS, normalize_name
from .cooking import COOKED_ITEMS


_OLD_CROPS = {'ca_rot', 'lua_mi', 'ca_chua', 'bap', 'bi_ngo'}
_NEW_CROPS = set(CROPS) - _OLD_CROPS
_NEW_FISH = {'ca_tram', 'ca_mang', 'ca_lang'}
_NEW_GOODS = {'fur', 'truffle'}
_NEW_MINING = {'da', 'quang_dong', 'quang_sat', 'quang_vang', 'kim_cuong',
               'thuoc'}
_COOKED = set(COOKED_ITEMS)
_OLD_EXTRAS = (set(EXTRA_ITEMS) - _NEW_FISH - _NEW_GOODS - _COOKED
               - _NEW_MINING)


def _historical_sets(field: str) -> set[frozenset[str]]:
    """Known inventory shapes from earlier content versions.

    New crops, fish, animal goods and cooked dishes were added over time.  A
    save is accepted only when its keys match a real historical shape; a
    truncated or hand-edited inventory is still rejected.
    """
    if field in ('seeds', 'produce'):
        return {frozenset(_OLD_CROPS), frozenset(CROPS)}
    if field == 'items':
        base = set(_OLD_EXTRAS)
    else:
        base = ({f'seed:{key}' for key in _OLD_CROPS}
                | {f'crop:{key}' for key in _OLD_CROPS}
                | _OLD_EXTRAS)
    shapes = set()
    from itertools import product
    for (crop_group, fish_group, good_group, cooked_group,
         mining_group) in product((False, True), repeat=5):
        keys = set(base)
        if field == 'chest' and crop_group:
            keys |= {f'seed:{key}' for key in _NEW_CROPS}
            keys |= {f'crop:{key}' for key in _NEW_CROPS}
        if fish_group:
            keys |= _NEW_FISH
        if good_group:
            keys |= _NEW_GOODS
        if cooked_group:
            keys |= _COOKED
        if mining_group:
            keys |= _NEW_MINING
        shapes.add(frozenset(keys))
    return shapes


LEGACY_FIELDS = {
    'name', 'day', 'coins', 'energy', 'max_energy', 'xp', 'size', 'weather',
    'sprinkler', 'harvested', 'sales', 'seeds', 'produce', 'plots',
}
VERSION_TWO_FIELDS = LEGACY_FIELDS | {
    'area', 'player_x', 'player_y', 'facing', 'forecast', 'items', 'chest',
    'animals', 'barn_capacity', 'fish_caught',
}
VERSION_THREE_FIELDS = VERSION_TWO_FIELDS | {'friendships', 'talked_on'}
VERSION_FOUR_FIELDS = VERSION_THREE_FIELDS | {'attributes', 'skills'}
VERSION_FIVE_FIELDS = VERSION_FOUR_FIELDS | {
    'player_name', 'avatar', 'outfit', 'background', 'intro_seen',
}
VERSION_SIX_FIELDS = VERSION_FIVE_FIELDS | {'tutorial'}
VERSION_SIX_FISH_FIELDS = VERSION_SIX_FIELDS | {'fish_collection'}


class SaveError(Exception):
    """A save could not be read or written; safe to show to the player."""


def _integer(value: object, minimum: int = 0,
             maximum: int | None = None) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError("Giá trị số không hợp lệ.")
    if maximum is not None and value > maximum:
        raise ValueError("Giá trị số vượt giới hạn.")


def _inventory(value: object, keys=CROPS) -> None:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("Túi đồ không hợp lệ.")
    for count in value.values():
        _integer(count)


def _decode_animals(raw_animals: object, capacity: int) -> list[Animal]:
    if not isinstance(raw_animals, list) or len(raw_animals) > capacity:
        raise ValueError('Đàn vật nuôi vượt quá sức chứa hoặc sai dữ liệu.')
    animals = []
    for raw in raw_animals:
        if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(Animal)}:
            raise ValueError('Thiếu dữ liệu vật nuôi.')
        if not isinstance(raw['kind'], str) or raw['kind'] not in ANIMAL_TYPES:
            raise ValueError('Loại vật nuôi không hợp lệ.')
        name = raw['name']
        if (not isinstance(name, str) or not name or len(name) > 24
                or not name.isprintable() or name.strip() != name):
            raise ValueError('Tên vật nuôi không hợp lệ.')
        for key in ('age', 'produce'):
            _integer(raw[key])
        _integer(raw['friendship'], maximum=5)
        _integer(raw['days_since_product'],
                 maximum=ANIMAL_TYPES[raw['kind']].interval - 1)
        if type(raw['fed']) is not bool or type(raw['petted']) is not bool:
            raise ValueError('Trạng thái chăm vật nuôi không hợp lệ.')
        animals.append(Animal(**raw))
    return animals



def _legacy_fields(data: object, expected: set[str], message: str) -> dict:
    """Accept an old schema plus the new fishing field, then strip it.

    The journal is optional in older saves; all other fields must match the
    historical schema exactly so malformed files still fail loudly.
    """
    if not isinstance(data, dict):
        raise ValueError(message)
    optional = {'fish_collection', 'retired_attribute_points',
                'retired_skill_points', 'map_pages', 'hp', 'gear',
                'mine_used', 'dungeon_best'}
    keys = set(data)
    if keys >= expected and keys - expected <= optional:
        data = {key: value for key, value in data.items()
                if key not in optional}
        keys = set(data)
    if keys != expected:
        raise ValueError(message)
    return dict(data)

def _migrate_version_one(data: object) -> dict:
    data = _legacy_fields(data, LEGACY_FIELDS,
                          'File lưu cũ thiếu dữ liệu hoặc không đúng cấu trúc.')
    # Defaults are added in memory; reading never overwrites the old file.
    return {**asdict(Farm()), **data}


def _migrate_version_two(data: object) -> dict:
    data = _legacy_fields(data, VERSION_TWO_FIELDS,
                          'File lưu phiên bản 2 thiếu dữ liệu hoặc không đúng cấu trúc.')
    return {**asdict(Farm()), **data}


def _migrate_version_three(data: object) -> dict:
    data = _legacy_fields(data, VERSION_THREE_FIELDS,
                          'File lưu phiên bản 3 thiếu dữ liệu hoặc không đúng cấu trúc.')
    return {**asdict(Farm()), **data}


def _decode_tutorial(raw: object, plots: dict, day: int):
    from .tutorial import STEPS, TutorialState

    if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(TutorialState)}:
        raise ValueError('Dữ liệu hướng dẫn thiếu trường hoặc không đúng cấu trúc.')
    status = raw['status']
    if not isinstance(status, str) or status not in (
            'off', 'pending', 'active', 'paused', 'skipped', 'completed'):
        raise ValueError('Trạng thái hướng dẫn không hợp lệ.')
    _integer(raw['step'], maximum=len(STEPS) if status == 'completed' else len(STEPS) - 1)
    if status == 'completed' and raw['step'] != len(STEPS):
        raise ValueError('Bước hoàn tất hướng dẫn không hợp lệ.')
    _integer(raw['moves'], maximum=4)
    plot = raw['plot']
    if plot is not None and (not isinstance(plot, str) or plot not in plots):
        raise ValueError('Ô ruộng hướng dẫn không hợp lệ.')
    for key in ('planted_on', 'watered_on'):
        _integer(raw[key], maximum=day)
    if type(raw['reward_given']) is not bool:
        raise ValueError('Trạng thái thưởng hướng dẫn không hợp lệ.')
    return TutorialState(**raw)


def _decode_daily(raw: object, day: int):
    from .daily import DailyState, DailyQuest, QUESTS

    if not isinstance(raw, dict) or set(raw) != {'day', 'tasks'}:
        raise ValueError('Dữ liệu nhiệm vụ ngày không đúng cấu trúc.')
    _integer(raw['day'], maximum=day)
    if raw['day'] not in (0, day) or not isinstance(raw['tasks'], list):
        raise ValueError('Ngày nhiệm vụ không khớp nông trại.')
    if raw['day'] == 0:
        if raw['tasks']:
            raise ValueError('Bảng nhiệm vụ chưa tạo phải để trống.')
        return DailyState()
    if len(raw['tasks']) != 4:
        raise ValueError('Mỗi ngày cần đúng bốn nhiệm vụ.')
    tasks = []
    seen = set()
    for task in raw['tasks']:
        if not isinstance(task, dict) or set(task) != {'kind', 'target', 'progress', 'claimed'}:
            raise ValueError('Nhiệm vụ thiếu trường hoặc không đúng cấu trúc.')
        kind = task['kind']
        if not isinstance(kind, str) or kind not in QUESTS or kind in seen:
            raise ValueError('Loại nhiệm vụ không hợp lệ hoặc bị trùng.')
        seen.add(kind)
        _integer(task['target'], 1, QUESTS[kind].target)
        if kind not in ('plant', 'water') and task['target'] != QUESTS[kind].target:
            raise ValueError('Mục tiêu nhiệm vụ không hợp lệ.')
        _integer(task['progress'], maximum=task['target'])
        if type(task['claimed']) is not bool or (task['claimed'] and task['progress'] != task['target']):
            raise ValueError('Trạng thái nhận thưởng nhiệm vụ không hợp lệ.')
        tasks.append(DailyQuest(**task))
    return DailyState(raw['day'], tasks)



def _fill_new_inventory(data: dict) -> dict:
    """Fill slots introduced after a save was written.

    The historical dictionaries are accepted only when their keys match a
    known older shape, so a truncated or hand-edited inventory still fails.
    """
    current = {
        'seeds': set(CROPS),
        'produce': set(CROPS),
        'items': set(EXTRA_ITEMS),
        'chest': set(ITEMS),
        'fish_collection': set(FISH_TYPES),
    }
    data = dict(data)
    for field, expected in current.items():
        value = data.get(field)
        if not isinstance(value, dict):
            continue
        keys = frozenset(value)
        historical = (_historical_sets(field) if field != 'fish_collection'
                      else {frozenset(FISH_TYPES) - _NEW_FISH,
                            frozenset(FISH_TYPES)})
        if keys in historical and keys != frozenset(expected):
            data[field] = {**dict.fromkeys(expected, 0), **value}
    return data

def _decode_farm(data: object) -> Farm:
    expected = {f.name for f in fields(Farm)}
    if isinstance(data, dict):
        # Older schema-seven saves lack the point-retirement counters.
        for field, default in (('fish_collection', empty_fish_collection),
                               ('retired_attribute_points', int),
                               ('retired_skill_points', int),
                               ('map_pages', bool),
                               ('hp', lambda: 20),
                               ('gear', empty_gear),
                               ('mine_used', dict),
                               ('dungeon_best', int)):
            if field not in data:
                data = {**data, field: default()}
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError("Thiếu dữ liệu nông trại hoặc có trường không hỗ trợ.")
    data = _fill_new_inventory(data)
    if normalize_name(data['player_name'], 24, 'Tên người chơi') != data['player_name']:
        raise ValueError('Tên người chơi phải chuẩn hóa NFC và không có khoảng trắng thừa.')
    for key, choices in (('avatar', AVATARS), ('outfit', OUTFITS),
                         ('background', BACKGROUNDS)):
        if not isinstance(data[key], str) or data[key] not in choices:
            raise ValueError('Thông tin nhân vật không hợp lệ.')
    if type(data['intro_seen']) is not bool:
        raise ValueError('Trạng thái intro không hợp lệ.')
    name = data["name"]
    if (not isinstance(name, str) or not 1 <= len(name) <= 28
            or not name.isprintable() or name.strip() != name):
        raise ValueError("Tên nông trại không hợp lệ.")
    _integer(data["day"], 1)
    for key in ("coins", "xp", "harvested", "sales"):
        _integer(data[key])
    if type(data["max_energy"]) is not int or data["max_energy"] not in (20, 30):
        raise ValueError("Giới hạn năng lượng không hợp lệ.")
    for key, definitions, budget in (
        ('attributes', ATTRIBUTES, data['xp'] // 40),
        ('skills', SKILLS, 2 * (data['xp'] // 40)),
    ):
        values = data[key]
        if not isinstance(values, dict) or set(values) != set(definitions):
            raise ValueError('Dữ liệu thuộc tính hoặc tay nghề không hợp lệ.')
        for value in values.values():
            _integer(value, maximum=5)
        if sum(values.values()) > budget:
            raise ValueError('Điểm nâng cấp vượt quá số điểm của cấp độ hiện tại.')
    _integer(data["energy"], maximum=data["max_energy"] + 4 * data['attributes']['endurance'])
    _integer(data["size"], 4, 6)
    if not isinstance(data["weather"], str) or data["weather"] not in WEATHER:
        raise ValueError("Thời tiết không hợp lệ.")
    if type(data["sprinkler"]) is not bool:
        raise ValueError("Nâng cấp tưới không hợp lệ.")
    _inventory(data["seeds"])
    _inventory(data["produce"])
    _inventory(data['items'], EXTRA_ITEMS)
    _inventory(data['chest'], ITEMS)
    _inventory(data['fish_collection'], FISH_TYPES)
    _integer(data['fish_caught'])
    _integer(data['retired_attribute_points'])
    _integer(data['retired_skill_points'])
    if type(data['map_pages']) is not bool:
        raise ValueError('Chế độ bản đồ không hợp lệ.')
    gear = data['gear']
    if not isinstance(gear, dict) or set(gear) != set(GEAR):
        raise ValueError('Dữ liệu trang bị không hợp lệ.')
    for value in gear.values():
        _integer(value, maximum=MAX_GEAR)
    max_hp = 20 + 4 * gear.get('armor', 0) + 2 * (data['xp'] // 40)
    _integer(data['hp'], 1, max_hp)
    _integer(data['dungeon_best'], maximum=5)
    mine_used = data['mine_used']
    if not isinstance(mine_used, dict):
        raise ValueError('Dữ liệu khai thác mỏ không hợp lệ.')
    for key, value in mine_used.items():
        _integer(value, maximum=4)
        if not isinstance(key, str) or ',' not in key:
            raise ValueError('Tọa độ mỏ đã khai thác không hợp lệ.')
        try:
            x_text, y_text = key.split(',', 1)
            x, y = int(x_text), int(y_text)
        except (TypeError, ValueError):
            raise ValueError('Tọa độ mỏ đã khai thác không hợp lệ.') from None
        if not (0 <= x < MINE_WIDTH and 0 <= y < MINE_HEIGHT
                and (x, y) in MINE_ROCKS):
            raise ValueError('Tọa độ mỏ đã khai thác không hợp lệ.')
    for key, maximum in (('friendships', 10), ('talked_on', data['day'])):
        values = data[key]
        if not isinstance(values, dict) or set(values) != set(NPCS):
            raise ValueError('Dữ liệu quan hệ dân làng không hợp lệ.')
        for value in values.values():
            _integer(value, maximum=maximum)
    if type(data['barn_capacity']) is not int or data['barn_capacity'] not in (4, 8):
        raise ValueError('Sức chứa chuồng không hợp lệ.')
    animals = _decode_animals(data['animals'], data['barn_capacity'])
    if not isinstance(data['forecast'], str) or data['forecast'] not in WEATHER:
        raise ValueError('Dự báo thời tiết không hợp lệ.')
    if data['area'] not in ('village', 'home', 'mine'):
        raise ValueError('Khu vực người chơi không hợp lệ.')
    if data['facing'] not in ('up', 'down', 'left', 'right'):
        raise ValueError('Hướng nhìn không hợp lệ.')
    _integer(data['player_x'])
    _integer(data['player_y'])
    if not walkable(data['area'], data['player_x'], data['player_y'], data['size']):
        raise ValueError('Vị trí người chơi bị chặn hoặc ngoài bản đồ.')
    raw_plots = data["plots"]
    if (not isinstance(raw_plots, dict)
            or set(raw_plots) != set(coordinates(data["size"]))):
        raise ValueError("Kích thước ruộng không khớp dữ liệu.")
    plots = {}
    for key in coordinates(data["size"]):
        raw = raw_plots[key]
        if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(Plot)}:
            raise ValueError(f"Dữ liệu ô {key} không hợp lệ.")
        crop = raw["crop"]
        if crop is not None and (not isinstance(crop, str) or crop not in CROPS):
            raise ValueError(f"Giống cây ở ô {key} không hợp lệ.")
        _integer(raw["growth"], maximum=CROPS[crop].days if crop else 0)
        _integer(raw["dry_days"], maximum=3)
        if type(raw["watered"]) is not bool or type(raw["dead"]) is not bool:
            raise ValueError(f"Trạng thái ô {key} không hợp lệ.")
        if crop is None and (raw["growth"] or raw["dry_days"]
                             or raw["watered"] or raw["dead"]):
            raise ValueError(f"Ô trống {key} có dữ liệu cây.")
        if raw["dead"] and (raw["dry_days"] != 3
                            or raw["growth"] >= CROPS[crop].days):
            raise ValueError(f"Trạng thái cây héo ở {key} không hợp lệ.")
        if not raw["dead"] and raw["dry_days"] >= 3:
            raise ValueError(f"Số ngày thiếu nước ở {key} không hợp lệ.")
        plots[key] = Plot(**raw)
    tutorial = _decode_tutorial(data['tutorial'], plots, data['day'])
    daily = _decode_daily(data['daily'], data['day'])
    return Farm(**{**data, "plots": plots, 'animals': animals,
                   'tutorial': tutorial, 'daily': daily})


def load_game(path: Path) -> Farm:
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict) or set(document) != {"version", "farm"}:
            raise ValueError("Cấu trúc file lưu không hợp lệ.")
        if type(document["version"]) is not int or document["version"] not in (1, 2, 3, 4, 5, 6, 7):
            raise ValueError("Phiên bản file lưu chưa được hỗ trợ.")
        data = document['farm']
        if document['version'] == 1:
            data = _migrate_version_one(data)
        elif document['version'] == 2:
            data = _migrate_version_two(data)
        elif document['version'] == 3:
            data = _migrate_version_three(data)
        elif document['version'] == 4:
            data = _legacy_fields(data, VERSION_FOUR_FIELDS,
                                  'File lưu phiên bản 4 thiếu dữ liệu hoặc không đúng cấu trúc.')
            data = {**asdict(Farm()), **data}
        elif document['version'] == 5:
            data = _legacy_fields(data, VERSION_FIVE_FIELDS,
                                  'File lưu phiên bản 5 thiếu dữ liệu hoặc không đúng cấu trúc.')
            data = {**asdict(Farm()), **data}
        elif document['version'] == 6:
            optional = {'fish_collection', 'retired_attribute_points',
                        'retired_skill_points', 'map_pages', 'hp', 'gear',
                        'mine_used', 'dungeon_best'}
            if (not isinstance(data, dict)
                    or not set(data) >= VERSION_SIX_FIELDS
                    or set(data) - VERSION_SIX_FIELDS - optional):
                raise ValueError('File lưu phiên bản 6 thiếu dữ liệu hoặc không đúng cấu trúc.')
            data = {**asdict(Farm()), **data}
        farm = _decode_farm(data)
        from .progression import settle_excess_points
        settle_excess_points(farm)
        return farm
    except (OSError, ValueError, UnicodeError) as error:
        raise SaveError(f"Không thể đọc file lưu {path}: {error}") from error


def save_game(farm: Farm, path: Path) -> None:
    path = Path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump({"version": 7, "farm": asdict(farm)}, handle,
                      ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except (OSError, TypeError, ValueError) as error:
        raise SaveError(f"Không thể lưu game tại {path}: {error}") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def backup_save(path: Path) -> Path:
    path = Path(path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"{path.name}.bak-{timestamp}")
    try:
        shutil.copy2(path, backup)
    except OSError as error:
        raise SaveError(f"Không thể sao lưu ván cũ: {error}") from error
    return backup
