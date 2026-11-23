"""Small terminal illustrations for cards, portraits and relationship meters.

Every drawing is plain ASCII at its core so it renders in any terminal and in
both the Unicode and ASCII themes.  A few Unicode variants add texture without
changing the drawing's width, which keeps card layouts stable.
"""

from __future__ import annotations


ART_WIDTH = 13

# Curated single-cell glyphs for the themed frontends.  Every rich glyph is
# narrow and printable, every plain glyph is one ASCII cell.  Wide emoji,
# emoji-presentation selectors and combining marks are deliberately excluded:
# terminals disagree about their width, which shifts the whole layout.
SYMBOLS = {
    'sun': ('☀', '*'),
    'cloud': ('☁', '~'),
    'rain': ('☂', '/'),
    'storm': ('↯', '!'),
    'moon': ('☾', ')'),
    'snow': ('❄', '*'),
    'flower': ('⚘', '&'),
    'cross': ('♱', '+'),
    'spark': ('↟', '^'),
    'gear': ('⚙', 'o'),
    'hammer': ('⚒', 'T'),
    'flag': ('⚑', '!'),
    'star': ('✧', '+'),
    'heart': ('♥', '#'),
    'heart_empty': ('♡', '-'),
    'coin': ('◆', '$'),
    'bag': ('▤', 'b'),
    'map': ('⌖', 'M'),
    'home': ('⌂', 'H'),
    'fish': ('≈', '~'),
    'chart': ('☗', 'C'),
    'scale': ('⚖', '='),
    'leaf': ('❧', '%'),
    'sun_alt': ('☼', '*'),
    'cloud_alt': ('☁', '~'),
    'moon_alt': ('☽', ')'),
}

WEATHER_ICONS = {
    'sunny': ('☀', '*'),
    'cloudy': ('☁', '~'),
    'rainy': ('☂', '/'),
}

QUEST_ICONS = {
    'plant': ('⚘', '&'),
    'water': ('☂', '/'),
    'harvest': ('✧', '+'),
    'work': ('⚒', 'T'),
    'fish': ('≈', '~'),
    'talk': ('☗', 'C'),
    'sell': ('◆', '$'),
    'feed': ('▤', 'f'),
    'pet': ('♥', '#'),
    'collect': ('◇', 'o'),
    'clear': ('⚒', 'x'),
    'buy': ('❦', '+'),
    'upgrade': ('⚙', 'o'),
    'catch_new': ('✧', '+'),
    'sell_fish': ('≈', '~'),
    'mine': ('⚒', 'T'),
}

STAT_ICONS = {
    'endurance': ('♥', '#'),
    'dexterity': ('↟', '^'),
    'focus': ('☾', ')'),
    'farming': ('⚘', '&'),
    'fishing': ('≈', '~'),
    'ranching': ('♱', '+'),
    'foraging': ('⚒', 'T'),
}


def symbol(name: str, *, unicode: bool = True) -> str:
    """One-cell icon with a readable ASCII fallback."""
    rich, plain = SYMBOLS.get(name, ('◆', '*'))
    return rich if unicode else plain


def weather_icon(weather: str, *, unicode: bool = True) -> str:
    rich, plain = WEATHER_ICONS.get(str(weather), ('☁', '~'))
    return rich if unicode else plain


def quest_icon(kind: str, *, unicode: bool = True) -> str:
    rich, plain = QUEST_ICONS.get(str(kind), ('◆', '*'))
    return rich if unicode else plain


def stat_icon(key: str, *, unicode: bool = True) -> str:
    rich, plain = STAT_ICONS.get(str(key), ('◆', '*'))
    return rich if unicode else plain


def pips(value: int, maximum: int = 5, *, unicode: bool = True) -> str:
    value = max(0, min(int(maximum), int(value)))
    full, empty = ('▰', '▱') if unicode else ('#', '-')
    return full * value + empty * (maximum - value)

# Three-line illustrations.  Each line is at most ``ART_WIDTH`` cells and the
# set is intentionally ASCII-only: the richer Unicode theme overlays a handful
# of variants below, but never depends on them.
_ART = {
    # --- seeds -----------------------------------------------------------
    'seed:ca_rot': (
        r"   .^.    ",
        r"  ( # )   ",
        r"   '-'    ",
    ),
    'seed:lua_mi': (
        r"  \|/|/   ",
        r"  -+-+    ",
        r"   / \    ",
    ),
    'seed:ca_chua': (
        r"   .-.    ",
        r"  ( * )   ",
        r"   '-'    ",
    ),
    'seed:khoai_tay': (
        r"   .-.    ",
        r"  ( o )   ",
        r"   '-'    ",
        r"   o o    ",
    ),
    'seed:dua_hau': (
        r"   ___    ",
        r"  /o o\   ",
        r"  \_w_/   ",
    ),
    'seed:dau_tay': (
        r"   .-.    ",
        r"  ( * )   ",
        r"  \|/    ",
    ),
    'seed:hoa_hong': (
        r"   .-.    ",
        r"  ( @ )   ",
        r"   /|\    ",
    ),
    'seed:bap': (
        r"   |||    ",
        r"  <|||>   ",
        r"   |||    ",
    ),
    'seed:bi_ngo': (
        r"  .---.   ",
        r" ( o o )  ",
        r"  '---'   ",
    ),
    # --- crops and produce ----------------------------------------------
    'ca_rot': (
        r"   \|/    ",
        r"  \_|_/   ",
        r"  (###)   ",
        r"   '-'    ",
    ),
    'lua_mi': (
        r"  \ | /   ",
        r"   \|/    ",
        r"   /|\    ",
        r"  /_|_\   ",
    ),
    'ca_chua': (
        r"   ,-.    ",
        r"  (###)   ",
        r"  (###)   ",
        r"   '-'    ",
    ),
    'bap': (
        r"   ,-.    ",
        r"  /|||\   ",
        r"  |||||   ",
        r"  \___/   ",
    ),
    'bi_ngo': (
        r"  ,---.   ",
        r" / o o \  ",
        r" \  ~  /  ",
        r"  '---'   ",
    ),
    'khoai_tay': (
        r"   .-.    ",
        r"  ( o )   ",
        r"  ( o )   ",
        r"   '-'    ",
    ),
    'dua_hau': (
        r"   ___    ",
        r"  /o o\   ",
        r"  \_w_/   ",
        r"   ~~~    ",
    ),
    'dau_tay': (
        r"   .-.    ",
        r"  ( * )   ",
        r"  (***)   ",
        r"   \|/    ",
    ),
    'hoa_hong': (
        r"   .-.    ",
        r"  ( @ )   ",
        r"  ( @ )   ",
        r"   /|\    ",
    ),
    # --- fish and animal goods ------------------------------------------
    'ca_ro': (
        r"    __    ",
        r"  ><(((`> ",
        r"     \\   ",
    ),
    'ca_chep': (
        r"   ____   ",
        r" ><((((`> ",
        r"    //    ",
    ),
    'ca_tram': (
        r"  ______  ",
        r" ><((((=> ",
        r"    //    ",
    ),
    'ca_hoi': (
        r"  ______  ",
        r" ><(((()> ",
        r"    \\    ",
    ),
    'ca_mang': (
        r"   ____   ",
        r" ><(((((> ",
        r"   //     ",
    ),
    'ca_vang': (
        r"   .-.    ",
        r" ><(o o)> ",
        r"    \\    ",
    ),
    'ca_lang': (
        r"   ____   ",
        r" ><((((#> ",
        r"   \\     ",
    ),
    'egg': (
        r"   ,-.    ",
        r"  ( o )   ",
        r"   '-'    ",
    ),
    'milk': (
        r"   ___    ",
        r"   | |    ",
        r"   |_|    ",
        r"   / \    ",
    ),
    'wool': (
        r"   (##)   ",
        r"  (####)  ",
        r"   (##)   ",
    ),
    'fur': (
        r"   ~~~    ",
        r"  (###)   ",
        r"   ~~~    ",
    ),
    'truffle': (
        r"   ___    ",
        r"  (o o)   ",
        r"  (___)   ",
    ),
    # --- cooked dishes ---------------------------------------------------
    'banh_mi': (
        r"   ___    ",
        r"  /___\   ",
        r"  ( o )   ",
        r"   ___    ",
    ),
    'salad_vuon': (
        r"  \___/   ",
        r"  ( * )   ",
        r"  /|_|\   ",
    ),
    'nuoc_dua_hau': (
        r"   | |    ",
        r"  /o o\   ",
        r"  \_w_/   ",
        r"   |_|    ",
    ),
    'cha_ca': (
        r"   ___    ",
        r"  (###)   ",
        r"  (###)   ",
        r"   ~~~    ",
    ),
    'chao_trung': (
        r"   .-.    ",
        r"  ( o )   ",
        r"  ( ~ )   ",
        r"   '-'    ",
    ),
    'sup_bi': (
        r"   .-.    ",
        r"  /###\   ",
        r"  |~~~|   ",
        r"   '-'    ",
    ),
    'sinh_to_dau': (
        r"   | |    ",
        r"  ( * )   ",
        r"  (***)   ",
        r"   |_|    ",
    ),
    'tra_hoa_hong': (
        r"   .-.    ",
        r"  ( @ )   ",
        r"  \___/   ",
        r"   |_|    ",
    ),
    # --- home station ----------------------------------------------------
    'kitchen': (
        r"  ,---.   ",
        r"  |[] |   ",
        r"  |___|   ",
        r"  ~ ~ ~   ",
    ),
    'feed': (
        r"   ,--.   ",
        r"   |::|   ",
        r"   |__|   ",
    ),
    'wood': (
        r"   |\_    ",
        r"   |  \   ",
        r"   |___\  ",
    ),
    # --- animals ---------------------------------------------------------
    'chicken': (
        r"    _     ",
        r"   (o>    ",
        r"  _/|_    ",
    ),
    'cow': (
        r"   (__)   ",
        r"   (oo)   ",
        r"  /|  |\  ",
    ),
    'sheep': (
        r"   (##)   ",
        r"  (####)  ",
        r"   /  \   ",
    ),
    'duck': (
        r"    __    ",
        r"  <(o )   ",
        r"   _/|_   ",
    ),
    'goat': (
        r"   (\/)   ",
        r"   /||\   ",
        r"   |__|   ",
    ),
    'rabbit': (
        r"   (\/)   ",
        r"  (o o)   ",
        r"  /|_|\   ",
    ),
    'pig': (
        r"   .--.   ",
        r"  (oo o)  ",
        r"  /|__|\  ",
    ),
    # --- services and upgrades ------------------------------------------
    'coins': (
        r"    __    ",
        r"   / $ \  ",
        r"   \_$_/  ",
    ),
    'mixed_seeds': (
        r"  ,-.-.   ",
        r"  |!|!|   ",
        r"  '---'   ",
    ),
    'upgrade:land': (
        r"  ___ ___ ",
        r" |___|___|",
        r" |___|___|",
    ),
    'upgrade:energy': (
        r"    _     ",
        r"   /+\    ",
        r"   \_/    ",
    ),
    'upgrade:sprinkler': (
        r"    |     ",
        r"  --+--   ",
        r"  ~ ~ ~   ",
    ),
    'upgrade:barn': (
        r"   /-\    ",
        r"  |[] |   ",
        r"  |_[]_|  ",
    ),
    # --- mining, forging and the dungeon --------------------------------
    'da': (
        r"   .--.   ",
        r"  (    )  ",
        r"   '--'   ",
    ),
    'quang_dong': (
        r"   .--.   ",
        r"  ( ## )  ",
        r"   '--'   ",
    ),
    'quang_sat': (
        r"   .--.   ",
        r"  ( @@ )  ",
        r"   '--'   ",
    ),
    'quang_vang': (
        r"   .--.   ",
        r"  ( $$ )  ",
        r"   '--'   ",
    ),
    'kim_cuong': (
        r"    /\    ",
        r"   <  >   ",
        r"    \/    ",
    ),
    'thuoc': (
        r"   .--.   ",
        r"   |++|   ",
        r"   '--'   ",
    ),
    'forge': (
        r"   ,--.   ",
        r"  /##/|   ",
        r"  \__\|   ",
        r"   ~ ~    ",
    ),
    'gear:pickaxe': (
        r"   ___    ",
        r"  /___\   ",
        r"    |     ",
        r"    |     ",
    ),
    'gear:sword': (
        r"    /\    ",
        r"   /  \   ",
        r"   \  /   ",
        r"    \/    ",
    ),
    'gear:armor': (
        r"   /--\   ",
        r"  |    |  ",
        r"  |____|  ",
    ),
    'monster:slime': (
        r"   .--.   ",
        r"  ( oo )  ",
        r"   '--'   ",
    ),
    'monster:bat': (
        r"  \    /  ",
        r"   \oo/   ",
        r"    \/    ",
    ),
    'monster:golem': (
        r"   /\/\   ",
        r"  ( oo )  ",
        r"  /|__|\  ",
    ),
    'monster:wisp': (
        r"   .--.   ",
        r"  ( ** )  ",
        r"   /  \   ",
    ),
    'monster:boss': (
        r"  \ ^^ /  ",
        r"   (oo)   ",
        r"  /|##|\  ",
    ),
}

# Optional Unicode texture.  Keys mirror ``_ART``; lines keep their width.
_UNICODE = {
    'lua_mi': (
        "  ╲ │ ╱   ",
        "   ╲│╱    ",
        "   ╱│╲    ",
    ),
    'ca_vang': (
        "   ◉ ◉    ",
        " ▸◖●◗◂    ",
    ),
    'coins': (
        "   ╭─╮    ",
        "  │◆ │    ",
        "   ╰─╯    ",
    ),
    'upgrade:energy': (
        "   ╭─╮    ",
        "   │+│    ",
        "   ╰─╯    ",
    ),
    'upgrade:sprinkler': (
        "   ╷╷╷    ",
        "  ═╪═╪═   ",
        "  ∼ ∼ ∼   ",
    ),
    'chicken': (
        "   ╭─╮    ",
        "  (o▸     ",
        "   ╱│╲    ",
    ),
    'cow': (
        "   ╭──╮   ",
        "   (oo)   ",
        "  ╱│  │╲  ",
    ),
    'sheep': (
        "   ☁☁     ",
        "  ☁☁☁    ",
        "   ╱ ╲    ",
    ),
    'duck': (
        "   ╭╮     ",
        "  ◁(o▸    ",
        "   ╱│╲    ",
    ),
    'goat': (
        "   ╲╱     ",
        "   ╱│╲    ",
        "   ╰─╯    ",
    ),
    'wood': (
        "   │╲     ",
        "   │ ╲    ",
        "   │__╲   ",
    ),
    'milk': (
        "   ╭─╮    ",
        "   │ │    ",
        "   ╰─╯    ",
        "   ╱ ╲    ",
    ),
}


def art_for(key: str, *, unicode: bool = True) -> tuple[str, ...]:
    """Return a short illustration for an item, crop, animal or upgrade."""
    key = str(key)
    if key.startswith('crop:'):
        key = key.split(':', 1)[1]
    if unicode and key in _UNICODE:
        return tuple(_UNICODE[key])
    if key in _ART:
        return tuple(_ART[key])
    if key.startswith('seed:'):
        return tuple(_ART['mixed_seeds'])
    return tuple(_ART['mixed_seeds'])


def icon_for(key: str, *, unicode: bool = True) -> str:
    """One-cell icon for compact list rows."""
    key = str(key)
    if key.startswith('crop:'):
        key = key.split(':', 1)[1]
    if unicode:
        icons = {
            'seed:ca_rot': '❦', 'seed:lua_mi': '❦', 'seed:ca_chua': '❦',
            'seed:bap': '❦', 'seed:bi_ngo': '❦', 'mixed_seeds': '❦',
            'seed:khoai_tay': '❦', 'seed:dua_hau': '❦',
            'seed:dau_tay': '❦', 'seed:hoa_hong': '❦',
            'ca_rot': '✦', 'lua_mi': '✦', 'ca_chua': '✦', 'bap': '✦',
            'bi_ngo': '✦', 'khoai_tay': '✦', 'dua_hau': '✦',
            'dau_tay': '✦', 'hoa_hong': '✦',
            'ca_ro': '◈', 'ca_chep': '◈', 'ca_tram': '◈',
            'ca_hoi': '◈', 'ca_mang': '◈', 'ca_vang': '◈', 'ca_lang': '◈',
            'egg': '○', 'milk': '◇', 'wool': '☁', 'fur': '☁',
            'truffle': '◈',
            'feed': '▤', 'wood': '▥', 'chicken': '▴', 'cow': '▴',
            'sheep': '▴', 'duck': '▴', 'goat': '▴', 'rabbit': '▴',
            'pig': '▴', 'coins': '◆',
            'banh_mi': '◍', 'salad_vuon': '❧', 'nuoc_dua_hau': '◍',
            'cha_ca': '◍', 'chao_trung': '◍', 'sup_bi': '◍',
            'sinh_to_dau': '◍', 'tra_hoa_hong': '✿', 'kitchen': '⚙',
            'upgrade:land': '▦', 'upgrade:energy': '◉',
            'upgrade:sprinkler': '≋', 'upgrade:barn': '⌂',
            'da': '◇', 'quang_dong': '◆', 'quang_sat': '◆',
            'quang_vang': '◆', 'kim_cuong': '✦', 'thuoc': '✚',
            'forge': '⚒', 'monster:slime': 's', 'monster:bat': 'b',
            'monster:golem': 'g', 'monster:wisp': 'w', 'monster:boss': '@',
        }
        return icons.get(key, '◆')
    icons = {
        'seed:ca_rot': '+', 'seed:lua_mi': '+', 'seed:ca_chua': '+',
        'seed:bap': '+', 'seed:bi_ngo': '+', 'mixed_seeds': '+',
        'seed:khoai_tay': '+', 'seed:dua_hau': '+',
        'seed:dau_tay': '+', 'seed:hoa_hong': '+',
        'ca_rot': '*', 'lua_mi': '*', 'ca_chua': '*', 'bap': '*',
        'bi_ngo': '*', 'khoai_tay': '*', 'dua_hau': '*',
        'dau_tay': '*', 'hoa_hong': '*',
        'ca_ro': '<', 'ca_chep': '<', 'ca_tram': '<',
        'ca_hoi': '<', 'ca_mang': '<', 'ca_vang': '<', 'ca_lang': '<',
        'egg': 'o', 'milk': 'd', 'wool': 'w', 'fur': 'w',
        'truffle': 'n',
        'feed': 'f', 'wood': 'w', 'chicken': 'a', 'cow': 'a',
        'sheep': 'a', 'duck': 'a', 'goat': 'a', 'rabbit': 'a',
        'pig': 'a', 'coins': '$',
        'banh_mi': 'o', 'salad_vuon': '%', 'nuoc_dua_hau': 'o',
        'cha_ca': 'o', 'chao_trung': 'o', 'sup_bi': 'o',
        'sinh_to_dau': 'o', 'tra_hoa_hong': '*', 'kitchen': '&',
        'upgrade:land': '#', 'upgrade:energy': '+',
        'upgrade:sprinkler': '~', 'upgrade:barn': '^',
        'da': 'o', 'quang_dong': '*', 'quang_sat': '*',
        'quang_vang': '*', 'kim_cuong': '+', 'thuoc': '+',
        'forge': 'F', 'monster:slime': 's', 'monster:bat': 'b',
        'monster:golem': 'g', 'monster:wisp': 'w', 'monster:boss': '@',
    }
    return icons.get(key, '*')


# Five-line portraits used by the conversation and villager directory cards.
_PORTRAITS = {
    'lan': (
        r"   .---.  ",
        r"  ( o o ) ",
        r"   \ - /  ",
        r"  /|   |\ ",
        r"   |___|  ",
    ),
    'tu': (
        r"    ___   ",
        r"   /___\  ",
        r"  ( o o ) ",
        r"   \ ~ /  ",
        r"   _|_|_  ",
    ),
    'an': (
        r"   .-*-.  ",
        r"  ( ^ ^ ) ",
        r"   \ u /  ",
        r"  /|   |\ ",
        r"   |___|  ",
    ),
    'mai': (
        r"  .------.",
        r"  ([-][-]) ",
        r"   \  v  / ",
        r"  /|   |\ ",
        r"   |___|  ",
    ),
    'son': (
        r"   .----. ",
        r"  ( o o ) ",
        r"   \ # #/ ",
        r"  /|   |\ ",
        r"   |___|  ",
    ),
}
_ASCII_PORTRAITS = {
    'lan': (
        "   .---.  ",
        "  ( o o ) ",
        "   \\ - /  ",
        "  /|   |\\ ",
        "   |___|  ",
    ),
    'tu': (
        "    ___   ",
        "   /___\\  ",
        "  ( o o ) ",
        "   \\ ~ /  ",
        "   _|_|_  ",
    ),
    'an': (
        "   .-*-.  ",
        "  ( ^ ^ ) ",
        "   \\ u /  ",
        "  /|   |\\ ",
        "   |___|  ",
    ),
    'mai': (
        "  .------.",
        "  ([-][-]) ",
        "   \\  v  / ",
        "  /|   |\\ ",
        "   |___|  ",
    ),
    'son': (
        "   .----. ",
        "  ( o o ) ",
        "   \\ # #/ ",
        "  /|   |\\ ",
        "   |___|  ",
    ),
}


def npc_portrait(npc_id: str, *, unicode: bool = True) -> tuple[str, ...]:
    if not unicode:
        return tuple(_ASCII_PORTRAITS.get(npc_id, _ASCII_PORTRAITS['lan']))
    return tuple(_PORTRAITS.get(npc_id, _PORTRAITS['lan']))


def player_portrait(avatar: str = '@', *, unicode: bool = True) -> tuple[str, ...]:
    """Small six-line portrait that keeps the chosen player glyph as the face."""
    avatar = str(avatar)[:1] or '@'
    if unicode:
        return (
            '   .---.   ',
            '  /     \\  ',
            f' |  ({avatar})  | ',
            '  \\  ~  /  ',
            '  /|   |\\  ',
            '   |___|   ',
        )
    return (
        '   .---.   ',
        '  /     \\  ',
        f' |  ({avatar})  | ',
        '  \\  ~  /  ',
        '  /|   |\\  ',
        '   |___|   ',
    )


def hearts(value: int, maximum: int = 10, *, unicode: bool = True) -> str:
    """Compact 0..maximum relationship meter."""
    value = max(0, min(int(maximum), int(value)))
    full, empty = ('♥', '♡') if unicode else ('#', '-')
    return full * value + empty * (maximum - value)
