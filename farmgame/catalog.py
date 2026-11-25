"""Shared crop, weather and item descriptions, with no game-state imports."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Crop:
    name: str
    symbol: str
    seed_price: int
    sell_price: int
    days: int
    xp: int
    level: int


CROPS = {
    "ca_rot": Crop("Cà rốt", "CR", 8, 24, 2, 5, 1),
    "lua_mi": Crop("Lúa mì", "LM", 5, 12, 1, 3, 1),
    "ca_chua": Crop("Cà chua", "CC", 15, 48, 3, 8, 2),
    "khoai_tay": Crop("Khoai tây", "KT", 18, 55, 2, 7, 2),
    "dua_hau": Crop("Dưa hấu", "DH", 22, 72, 3, 10, 2),
    "bap": Crop("Bắp", "BP", 24, 80, 4, 12, 3),
    "dau_tay": Crop("Dâu tây", "DT", 35, 105, 3, 12, 3),
    "bi_ngo": Crop("Bí ngô", "BN", 40, 140, 5, 18, 4),
    "hoa_hong": Crop("Hoa hồng", "HH", 30, 95, 4, 14, 5),
}
WEATHER = {"sunny": "Nắng ấm", "cloudy": "Nhiều mây", "rainy": "Mưa rào"}


@dataclass(frozen=True, slots=True)
class Fish:
    name: str
    rarity: str
    points: int
    level: int
    weight: int
    hint: str


FISH_TYPES = {
    "ca_ro": Fish("Cá rô", "Thường", 1, 1, 45,
                  "Loài cá nhỏ ven bờ, dễ gặp ở mọi cấp."),
    "ca_chep": Fish("Cá chép", "Thường", 2, 1, 30,
                    "Thân tròn, khỏe; hay quẫy mạnh khi kéo."),
    "ca_tram": Fish("Cá trắm", "Khá hiếm", 3, 2, 22,
                    "Bơi thành đàn ở tầng giữa hồ."),
    "ca_hoi": Fish("Cá hồi", "Hiếm", 5, 1, 12,
                   "Cần dòng nước mát và một chút kiên nhẫn."),
    "ca_mang": Fish("Cá măng", "Quý hiếm", 6, 3, 9,
                    "Loài cá nhanh, chỉ xuất hiện khi tay nghề đã cao."),
    "ca_vang": Fish("Cá vàng", "Huyền thoại", 10, 1, 3,
                    "Ánh vàng lấp ló dưới đáy hồ; rất khó câu."),
    "ca_lang": Fish("Cá lăng", "Cực hiếm", 12, 4, 5,
                    "Cá lớn ở hố sâu, là bảo vật của hồ Sen."),
}


def empty_fish_collection() -> dict[str, int]:
    return dict.fromkeys(FISH_TYPES, 0)


@dataclass(frozen=True, slots=True)
class Item:
    name: str
    sell_price: int = 0
    buy_price: int = 0


EXTRA_ITEMS = {
    "ca_ro": Item("Cá rô", 18),
    "ca_chep": Item("Cá chép", 28),
    "ca_tram": Item("Cá trắm", 55),
    "ca_hoi": Item("Cá hồi", 65),
    "ca_mang": Item("Cá măng", 85),
    "ca_vang": Item("Cá vàng", 90),
    "ca_lang": Item("Cá lăng", 140),
    "egg": Item("Trứng gà", 18),
    "milk": Item("Sữa bò", 45),
    "wool": Item("Len cừu", 60),
    "fur": Item("Lông thỏ", 70),
    "truffle": Item("Nấm củ", 110),
    "feed": Item("Thức ăn vật nuôi", buy_price=5),
    "wood": Item("Gỗ", 4),
    "herb": Item("Rau thơm rừng", 12),
    "berry": Item("Quả mọng rừng", 18),
    "mushroom": Item("Nấm rừng", 22),
    "tea_leaf": Item("Búp trà", 16),
    "shell": Item("Vỏ sò", 14),
    "honey": Item("Mật ong rừng", 35),
    # Cooked dishes.  They are ordinary items so chest, selling and the
    # inventory panel keep one shared model.
    "banh_mi": Item("Bánh mì nướng", 65),
    "salad_vuon": Item("Salad vườn", 90),
    "nuoc_dua_hau": Item("Nước dưa hấu", 95),
    "cha_ca": Item("Chả cá", 145),
    "chao_trung": Item("Cháo trứng", 120),
    "sup_bi": Item("Súp bí ngô", 230),
    "sinh_to_dau": Item("Sinh tố dâu", 260),
    "tra_hoa_hong": Item("Trà hoa hồng", 180),
    "sup_nam": Item("Súp nấm rừng", 105),
    "tra_rung": Item("Trà rừng mật ong", 130),
    "mut_rung": Item("Mứt quả mọng", 160),
    # --- mining and forging ---------------------------------------------
    "da": Item("Đá", 6),
    "quang_dong": Item("Quặng đồng", 32),
    "quang_sat": Item("Quặng sắt", 64),
    "quang_vang": Item("Quặng vàng", 120),
    "kim_cuong": Item("Tinh thể hang sâu", 200),
    "thuoc": Item("Thuốc hồi sức", 20, 40),
}


@dataclass(frozen=True, slots=True)
class Gear:
    name: str
    icon: str
    ascii_icon: str
    description: str
    effect: str


MAX_GEAR = 4  # internal index; display rank is level + 1 (five tiers)
RARITY_NAMES = ('Bình thường', 'Hiếm', 'Sử thi', 'Truyền thuyết', 'Huyền thoại')
RARITY_COLORS = ('white', 'cyan', 'magenta', 'yellow', 'red')
GEAR = {
    "hat": Gear(
        "Mũ thợ mỏ", "^", "H",
        "Chiếc mũ bảo vệ đầu khi vào mỏ và giúp đào quặng hiệu quả hơn.",
        "Mỗi bậc giảm sức đào và tăng lượng quặng nhận được."),
    "sword": Gear(
        "Kiếm rèn", "/", "/",
        "Vũ khí cần có để bước vào Hang Sâu.",
        "Mỗi bậc tăng sát thương khi chiến đấu."),
    "armor": Gear(
        "Giáp da", "A", "A",
        "Áo giáp bảo vệ thân mình trong những tầng hang nguy hiểm.",
        "Mỗi bậc tăng máu tối đa và phòng thủ."),
    "pants": Gear(
        "Quần da", "|", "|",
        "Quần bọc da giúp chịu đòn tốt hơn khi đi sâu vào lòng đất.",
        "Mỗi bậc tăng máu tối đa và phòng thủ."),
    "shoes": Gear(
        "Giày da", "_", "_",
        "Đôi giày bền giữ bước chân vững trên đá ẩm của hang sâu.",
        "Mỗi bậc tăng máu tối đa và phòng thủ."),
}

# Four upgrades per slot: Bình thường → Hiếm → Sử thi → Truyền thuyết →
# Huyền thoại.  ``coins`` is the forge fee; every other key is an item.
FORGE_RECIPES = {
    "hat": (
        {"da": 3, "quang_dong": 1, "coins": 20},
        {"da": 4, "quang_dong": 3, "coins": 45},
        {"da": 3, "quang_dong": 4, "quang_sat": 2, "coins": 80},
        {"quang_sat": 3, "quang_vang": 3, "kim_cuong": 1, "coins": 240},
    ),
    "sword": (
        {"da": 2, "quang_dong": 2, "coins": 30},
        {"quang_dong": 3, "quang_sat": 2, "coins": 70},
        {"quang_sat": 4, "quang_vang": 1, "coins": 120},
        {"quang_vang": 4, "kim_cuong": 2, "coins": 320},
    ),
    "armor": (
        {"da": 4, "quang_dong": 1, "coins": 25},
        {"quang_dong": 5, "coins": 50},
        {"quang_dong": 5, "quang_sat": 3, "coins": 90},
        {"quang_sat": 5, "quang_vang": 3, "kim_cuong": 1, "coins": 260},
    ),
    "pants": (
        {"da": 3, "quang_dong": 1, "coins": 22},
        {"quang_dong": 3, "da": 3, "coins": 45},
        {"quang_sat": 3, "quang_dong": 3, "coins": 85},
        {"quang_sat": 5, "quang_vang": 2, "kim_cuong": 1, "coins": 250},
    ),
    "shoes": (
        {"da": 2, "quang_dong": 1, "coins": 18},
        {"quang_dong": 2, "da": 2, "coins": 40},
        {"quang_sat": 2, "quang_dong": 2, "coins": 75},
        {"quang_vang": 3, "kim_cuong": 1, "coins": 210},
    ),
}


def empty_gear() -> dict[str, int]:
    return dict.fromkeys(GEAR, 0)


ITEMS = {
    **{f"seed:{key}": Item(f"Hạt {crop.name}", buy_price=crop.seed_price)
       for key, crop in CROPS.items()},
    **{f"crop:{key}": Item(crop.name, crop.sell_price)
       for key, crop in CROPS.items()},
    **EXTRA_ITEMS,
}


def starting_items() -> dict[str, int]:
    return {**dict.fromkeys(EXTRA_ITEMS, 0), "feed": 8}


def empty_chest() -> dict[str, int]:
    return dict.fromkeys(ITEMS, 0)
