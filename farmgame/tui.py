"""Floating-window primitives for the curses frontends.

The helpers are curses-free at import time.  They only need a *painter* with
``_put`` and ``_screen`` attributes, which both :class:`ExplorerGame` and
:class:`CursesUI` provide.  That keeps geometry and border rendering testable
with a tiny in-memory screen.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata


# ---------------------------------------------------------------------------
# Cell-aware text helpers
# ---------------------------------------------------------------------------

def cells(text: str) -> int:
    """Display width of *text* in terminal cells."""
    total = 0
    for char in str(text):
        if unicodedata.combining(char) or unicodedata.category(char).startswith('M'):
            continue
        total += 2 if unicodedata.east_asian_width(char) in 'WF' else 1
    return total


def clip(text: str, width: int) -> str:
    """Clip *text* by terminal cells, keeping combining marks with their base."""
    if width <= 0:
        return ''
    result, used = [], 0
    for char in str(text):
        if unicodedata.category(char).startswith('C'):
            char = ' '
        size = 0 if unicodedata.combining(char) else (
            2 if unicodedata.east_asian_width(char) in 'WF' else 1)
        if used + size > width:
            break
        result.append(char)
        used += size
    return ''.join(result)


def ellipsize(text: str, width: int, *, unicode: bool = True) -> str:
    """Clip *text* and add an ellipsis when it does not fit."""
    text = str(text)
    if cells(text) <= width:
        return text
    mark = '…' if unicode else '...'
    room = width - cells(mark)
    if room <= 0:
        return clip(mark, width)
    return clip(text, room).rstrip() + mark


def pad(text: str, width: int) -> str:
    """Pad *text* with spaces to *width* terminal cells."""
    text = clip(text, width)
    return text + ' ' * max(0, width - cells(text))


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x <= self.right and self.y <= y <= self.bottom


def panel_geometry(screen_height: int, screen_width: int, *,
                   content_width: int = 40, content_height: int = 10,
                   margin_x: int = 2, margin_y: int = 1,
                   bottom_reserve: int = 0,
                   min_width: int = 24, min_height: int = 5) -> Rect:
    """Return a centred panel rectangle inside the usable screen area.

    ``bottom_reserve`` keeps room for a global status bar.  On tiny terminals
    the panel shrinks instead of overflowing; callers can still fall back to a
    borderless layout when the result is too small to draw.
    """
    screen_height = max(1, int(screen_height))
    screen_width = max(1, int(screen_width))
    usable_h = max(1, screen_height - max(0, margin_y) * 2 - max(0, bottom_reserve))
    usable_w = max(1, screen_width - max(0, margin_x) * 2)
    width = max(1, min(usable_w, max(min_width, int(content_width))))
    height = max(1, min(usable_h, max(min_height, int(content_height))))
    x = max(0, (screen_width - width) // 2)
    area_h = max(1, screen_height - max(0, bottom_reserve))
    y = max(0, (area_h - height) // 2)
    return Rect(x, y, width, height)


# ---------------------------------------------------------------------------
# Glyphs and colours
# ---------------------------------------------------------------------------

def glyphs(unicode: bool = True) -> dict[str, str]:
    if unicode:
        return {
            'tl': '╭', 'tr': '╮', 'bl': '╰', 'br': '╯',
            'h': '─', 'v': '│', 'shadow': '░', 'icon': '◆',
            'marker': '>', 'dot': '·', 'arrow': '›',
        }
    return {
        'tl': '+', 'tr': '+', 'bl': '+', 'br': '+',
        'h': '-', 'v': '|', 'shadow': ':', 'icon': '*',
        'marker': '>', 'dot': '.', 'arrow': '>',
    }


def init_colors(curses, enabled: bool = True) -> dict[str, int]:
    """Initialise the shared palette and return name -> attribute mapping."""
    if not enabled:
        return {}
    try:
        if not curses.has_colors():
            return {}
        curses.start_color()
        try:
            curses.use_default_colors()
        except (curses.error, AttributeError):
            pass
        colors = {}
        basic = ('green', 'yellow', 'cyan', 'blue', 'magenta', 'red', 'white')
        for pair, name in enumerate(basic, 1):
            curses.init_pair(pair, getattr(curses, 'COLOR_' + name.upper()), -1)
            colors[name] = curses.color_pair(pair)
        # Semantic map colours.  The 256-colour values are deliberately
        # picked for the landscape: golden sand, pale-green lake, deep-blue sea,
        # dark forest, warm soil and a muted road/stone palette.
        palette = {
            'grass': ('GREEN', 34),
            'forest': ('GREEN', 28),
            'flower': ('MAGENTA', 201),
            'soil': ('YELLOW', 130),
            'sand': ('YELLOW', 220),
            'lake': ('CYAN', 121),
            'sea': ('BLUE', 27),
            'path': ('WHITE', 250),
            'stone': ('WHITE', 244),
            'building': ('YELLOW', 214),
            'roof': ('RED', 160),
            'furniture': ('CYAN', 39),
            'door': ('CYAN', 45),
        }
        rich = getattr(curses, 'COLORS', 0) >= 256
        pair = len(basic)
        for name, (basic_name, rich_index) in palette.items():
            pair += 1
            foreground = rich_index if rich else getattr(
                curses, 'COLOR_' + basic_name, getattr(curses, 'COLOR_WHITE', 7))
            try:
                curses.init_pair(pair, foreground, -1)
                colors[name] = curses.color_pair(pair)
            except (curses.error, AttributeError):
                # Very small colour tables still keep a usable fallback.
                colors[name] = colors.get(basic_name.lower(), 0)
        colors['shadow'] = colors.get('blue', 0) | getattr(curses, 'A_DIM', 0)
        colors['accent'] = colors.get('cyan', 0) | getattr(curses, 'A_BOLD', 0)
        return colors
    except (curses.error, AttributeError):
        return {}


# ---------------------------------------------------------------------------
# Painting
# ---------------------------------------------------------------------------

def draw_backdrop(ui, height: int, width: int, *, unicode: bool = True) -> None:
    """Draw a subtle frame around the whole terminal, behind a panel."""
    if height < 4 or width < 12:
        return
    g = glyphs(unicode)
    color = 'shadow'
    ui._put(0, 0, g['tl'] + g['h'] * max(0, width - 2) + g['tr'], color)
    ui._put(height - 1, 0, g['bl'] + g['h'] * max(0, width - 2) + g['br'], color)
    for row in range(1, height - 1):
        ui._put(row, 0, g['v'], color)
        ui._put(row, width - 1, g['v'], color)


def draw_panel(ui, rect: Rect, *, title: str = '', footer: str = '',
               unicode: bool = True, accent: str = 'cyan',
               title_color: str = 'yellow', footer_color: str = 'cyan',
               shadow: bool = True, icon: bool = True,
               bounds: tuple[int, int] | None = None) -> Rect:
    """Draw an opaque rounded panel and return its usable body rectangle.

    The title is embedded in the top border, the footer sits on the row just
    above the bottom border.  A soft block shadow is painted one cell to the
    right and below the panel when the terminal has room.
    """
    if rect.width < 2 or rect.height < 2:
        return Rect(rect.x, rect.y, max(0, rect.width), max(0, rect.height))

    g = glyphs(unicode)
    inner_w = rect.width - 2

    # Opaque fill first so the panel hides the dimmed map underneath.
    blank = ' ' * rect.width
    for row in range(rect.y, rect.y + rect.height):
        ui._put(row, rect.x, blank, '')

    # Top border with an embedded title.  Long headings are ellipsized so
    # narrow terminals do not look like they cut a word in half.
    if title and inner_w >= 2:
        raw = f" {g['icon'] + ' ' if icon else ''}{title} "
        label = (ellipsize(raw, inner_w - 1, unicode=unicode)
                 if cells(raw) > inner_w - 1 else raw)
        top = g['tl'] + g['h'] + label + g['h'] * max(0, inner_w - 1 - cells(label)) + g['tr']
        ui._put(rect.y, rect.x, top, accent)
        ui._put(rect.y, rect.x + 2, label, title_color, True)
    else:
        top = g['tl'] + g['h'] * inner_w + g['tr']
        ui._put(rect.y, rect.x, top, accent)

    # Side borders.
    for row in range(rect.y + 1, rect.y + rect.height - 1):
        ui._put(row, rect.x, g['v'], accent)
        ui._put(row, rect.right, g['v'], accent)

    # Footer inside the bottom edge.  Use an ellipsis instead of a hard
    # character cut so long card details still read as a complete phrase.
    if footer and rect.height >= 4 and inner_w >= 4:
        label = ' ' + ellipsize(footer, max(0, inner_w - 1), unicode=unicode)
        text = pad(label, inner_w)
        ui._put(rect.y + rect.height - 2, rect.x,
                g['v'] + text + g['v'], footer_color)

    # Bottom border.
    ui._put(rect.bottom, rect.x, g['bl'] + g['h'] * inner_w + g['br'], accent)

    # Soft shadow: one column right, one row below, clipped by the screen.
    if shadow:
        shadow_char = g['shadow']
        screen_h, screen_w = bounds if bounds is not None else (10 ** 6, 10 ** 6)
        if rect.right + 1 < screen_w:
            for row in range(rect.y + 1, min(rect.bottom + 1, screen_h - 1) + 1):
                ui._put(row, rect.right + 1, shadow_char, 'shadow')
        if rect.bottom + 1 < screen_h:
            ui._put(rect.bottom + 1, rect.x + 2,
                    shadow_char * max(0, rect.width - 1), 'shadow')

    body_height = rect.height - 2 - (1 if footer and rect.height >= 4 else 0)
    return Rect(rect.x + 1, rect.y + 1, inner_w, max(0, body_height))


def draw_status_bar(ui, height: int, width: int, controls: str,
                    message: str = '', *, unicode: bool = True,
                    error: bool = False) -> None:
    """Paint the two-line global status bar used by modal dialogs."""
    if height < 3:
        return
    g = glyphs(unicode)
    row = height - 2
    ui._put(row, 0, ' ' * width, '')
    ui._put(row, 1, ellipsize(f"{g['icon']} {controls}", max(1, width - 2),
                              unicode=unicode), 'cyan', True)
    if height >= 2:
        ui._put(height - 1, 0, ' ' * width, '')
        if message:
            ui._put(height - 1, 1,
                    ellipsize(message, max(1, width - 2), unicode=unicode),
                    'red' if error else 'green')
        else:
            ui._put(height - 1, 1,
                    ellipsize('Mây Nhỏ · một cuộc sống chậm giữa mây trời',
                              max(1, width - 2), unicode=unicode), 'dim')


def progress_bar(ratio: float, width: int, *, unicode: bool = True) -> str:
    """Return a compact filled bar that always occupies exactly *width* cells."""
    width = max(0, int(width))
    ratio = max(0.0, min(1.0, float(ratio)))
    filled = int(round(width * ratio))
    full, empty = ('▰', '▱') if unicode else ('#', '-')
    return full * filled + empty * (width - filled)
