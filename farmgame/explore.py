"""Immediate-key village interface. Importing this module does not load curses."""

from __future__ import annotations

import os
import sys
import time
import unicodedata
from pathlib import Path

from .catalog import CROPS, WEATHER, ITEMS
from .model import GameError
from .progression import (ATTRIBUTES, SKILLS, character_lines, sale_price,
                          action_cost, exchange_points, upgrade_attribute,
                          upgrade_skill)
from .storage import SaveError, save_game
from . import tui, world


def fit_text(text: str, width: int) -> str:
    """Clip by terminal cells, retaining Vietnamese combining marks."""
    result = []
    used = 0
    for char in str(text):
        if unicodedata.category(char).startswith("C"):
            char = " "
        cells = 0 if unicodedata.combining(char) else (2 if unicodedata.east_asian_width(char) in "WF" else 1)
        if used + cells > width:
            break
        result.append(char)
        used += cells
    return "".join(result)


def wrap_cells(text: str, width: int) -> list[str]:
    """Wrap paragraphs by terminal cells, preserving combining sequences."""
    lines = []
    for paragraph in text.split('\n'):
        remaining = ' '.join(paragraph.split())
        if not remaining:
            lines.append('')
        while remaining:
            chunk = fit_text(remaining, max(2, width))
            # Prefer complete words, but split long names that exceed a line.
            if len(chunk) < len(remaining) and remaining[len(chunk)] != ' ':
                boundary = chunk.rfind(' ')
                if boundary > 0:
                    chunk = chunk[:boundary]
            lines.append(chunk.rstrip())
            remaining = remaining[len(chunk):].lstrip()
    return lines


def viewport(area_width, area_height, x, y, width, height, *, cell=None):
    """Camera rectangle in world cells, reserving HUD and footer rows."""
    if cell is None:
        cell = 2 if width >= 64 else 1
    cols = min(area_width, max(1, width // cell))
    rows = min(area_height, max(1, height - 9))
    left = max(0, min(x - cols // 2, area_width - cols))
    top = max(0, min(y - rows // 2, area_height - rows))
    return left, top, cols, rows, cell


def overview_rows(farm, width, height, *, unicode=False):
    """Scale the whole village, overlaying landmarks, then NPCs, then player."""
    from .villagers import NPCS
    cols = max(1, min(world.VILLAGE_WIDTH, width))
    rows = max(1, min(world.VILLAGE_HEIGHT, height))
    def projected(x, y):
        return (min(cols - 1, x * cols // world.VILLAGE_WIDTH),
                min(rows - 1, y * rows // world.VILLAGE_HEIGHT))
    from .map_art import terrain_glyph
    grid = [[terrain_glyph(world.tile_at('village', x * world.VILLAGE_WIDTH // cols,
                           y * world.VILLAGE_HEIGHT // rows, farm.size), unicode=unicode)
             for x in range(cols)] for y in range(rows)]
    # Nearby world locations may share a scaled cell. Keep markers visible by
    # placing later markers in the nearest free cell (coordinates stay in HUD/J).
    occupied = set()
    def marker(position, glyph):
        target_x, target_y = projected(*position)
        candidates = ((x, y) for y in range(rows) for x in range(cols)
                      if (x, y) not in occupied)
        spot = min(candidates, key=lambda pos: (abs(pos[0] - target_x)
                   + abs(pos[1] - target_y), pos[1], pos[0]), default=None)
        if spot is not None:
            x, y = spot
            occupied.add(spot)
            grid[y][x] = glyph
    marker((farm.player_x, farm.player_y) if farm.area == 'village'
           else (world.LANDMARKS['mine'][1] if farm.area == 'mine'
                 else world.HOME_DOOR), farm.avatar)
    for npc in NPCS.values():
        marker(npc.position, npc.glyph)
    for key, (_, position) in world.LANDMARKS.items():
        marker(position, {'farm': ':', 'home': 'H', 'shop': 'M', 'barn': 'B',
                          'meadow': ',', 'square': 'O', 'forest': 'T',
                          'lake': '~', 'hill': '^', 'valley': 'v',
                          'tea': 't', 'floodplain': ';', 'beach': '~',
                          'mine': '◉' if unicode else 'O'}.get(key, '?'))
    return [''.join(row) for row in grid]


def directory_lines(farm):
    from .villagers import NPCS
    return [f'{npc.glyph}. {npc.name} · {npc.role} · ({npc.position[0]}, {npc.position[1]})'
            f' · Thân {farm.friendships[npc.id]}/10' for npc in NPCS.values()]


class ExplorerGame:
    def __init__(self, farm, save_path, color=True, clear_screen=True, intro=False,
                 ascii_only=False):
        self.farm = farm
        self.save_path = Path(save_path)
        self.color = bool(color) and "NO_COLOR" not in os.environ
        self.clear_screen = clear_screen
        self.play_intro = intro
        self.messages: list[str] = ["Chào mừng đến Mossbrook Meadow! WASD di chuyển, E tương tác, H trợ giúp."]
        self.map_expanded = False
        self.return_to_menu = False
        self.quit_to_menu = True
        from .toast import ToastCenter
        self.toasts = ToastCenter()
        self._screen = None
        self._curses = None
        self._colors = {}
        self._save_error = ""
        self._dim_base = False
        from .map_art import supports_unicode
        self.unicode_map = not ascii_only and supports_unicode()
        from .tutorial_ui import TutorialCoach
        self.coach = TutorialCoach(self, farm, self._save) if farm is not None else None
        from .activity_ui import ActivityUI
        self.activities = ActivityUI(self, farm, self._save) if farm is not None else None

    def _log(self, message, *, toast=True, kind=None):
        if message:
            text = str(message)
            self.messages.append(text)
            del self.messages[:-100]
            if toast:
                self.toasts.push(text, kind)

    def _toggle_map_style(self):
        from .map_art import supports_unicode
        if not self.unicode_map and not supports_unicode():
            self._log('Terminal không hỗ trợ bộ ký tự này; đang dùng ASCII thường.')
            return
        self.unicode_map = not self.unicode_map
        self._log('Bản đồ: ký tự Unicode.' if self.unicode_map else 'Bản đồ: ASCII thường.')

    def _toggle_map_width(self):
        """Expand the camera frame to narrow cells so twice the world fits."""
        if self.activities.running:
            self._log('Hãy dừng auto trước khi đổi khung bản đồ rộng.')
            return
        self.map_expanded = not self.map_expanded
        self._log('Khung bản đồ: RỘNG (nhiều ô hơn).' if self.map_expanded
                  else 'Khung bản đồ: tiêu chuẩn.')

    def _save(self):
        try:
            save_game(self.farm, self.save_path)
        except (SaveError, OSError) as error:
            self._save_error = str(error)
            self._log(self._save_error)
            return False
        self._save_error = ""
        return True

    def _action(self, action, *args):
        try:
            message = action(*args)
        except GameError as error:
            self._log(error)
            return False
        self._log(message)
        self._save()
        return True

    def run(self) -> int:
        try:
            import curses
        except ImportError:
            print("Terminal này không hỗ trợ curses. Hãy chạy lại với --text.", file=sys.stderr)
            return 1
        self._curses = curses
        try:
            return curses.wrapper(self._loop)
        except (KeyboardInterrupt, EOFError):
            if self._save():
                return 0
            print(self._save_error, file=sys.stderr)
            return 1
        except Exception as error:
            # wrapper has restored echo/cursor before showing a terminal failure.
            saved = self._save()
            print(f"Giao diện terminal gặp lỗi: {error}. Hãy chạy lại với --text.", file=sys.stderr)
            if not saved:
                print(self._save_error, file=sys.stderr)
            else:
                print(f"Ván chơi đã lưu tại {self.save_path}.", file=sys.stderr)
            return 1

    def _loop(self, screen):
        self._screen = screen
        screen.keypad(True)
        screen.timeout(100)
        try:
            self._curses.curs_set(0)
        except self._curses.error:
            pass
        if self.color and self._curses.has_colors():
            self._colors = tui.init_colors(self._curses, self.color)
        if self.play_intro:
            self._draw()
            from .start_screen import CursesUI
            opening = CursesUI(self.color, self.clear_screen)
            opening._screen = screen
            opening._curses = self._curses
            opening._colors = self._colors
            if opening.intro(self.farm):
                self.farm.intro_seen = True
                self._save()
            self.play_intro = False
            screen.timeout(100)
        self.coach.offer()
        self.coach.sync()
        redraw = True
        last_draw = 0.0
        while True:
            now = time.monotonic()
            redraw |= self.toasts.tick(now)
            redraw |= self.activities.tick(now)
            if redraw and (not self.activities.running or now - last_draw >= 0.035):
                self._draw()
                last_draw, redraw = now, False
            screen.timeout(self.activities.read_timeout_ms)
            key = self._read()
            redraw |= key is not None
            if not self.handle_key(key):
                return 0

    def _read(self):
        try:
            return self._screen.get_wch()
        except self._curses.error:
            return None

    def handle_key(self, key):
        """One immediate key; returns False only after a successful save/quit."""
        directions = {"w": "up", "a": "left", "s": "down", "d": "right"}
        if self._curses:
            directions.update({self._curses.KEY_UP: "up", self._curses.KEY_DOWN: "down",
                               self._curses.KEY_LEFT: "left", self._curses.KEY_RIGHT: "right"})
        key = key.lower() if isinstance(key, str) else key
        if self.activities.control(key):
            return True
        if key in directions:
            before_x, before_y = self.farm.player_x, self.farm.player_y
            before_page = None
            if getattr(self.farm, 'map_pages', False):
                from .pages import page_for_coord
                page = page_for_coord(before_x, before_y)
                before_page = page.key if page is not None else None
            try:
                moved = world.move(self.farm, directions[key])
            except GameError as error:
                self._log(error)
            else:
                if moved:
                    self.coach.event('move', from_x=before_x, from_y=before_y)
                    if getattr(self.farm, 'map_pages', False):
                        from .pages import page_for_coord
                        after = page_for_coord(self.farm.player_x,
                                               self.farm.player_y)
                        if after is not None and after.key != before_page:
                            self._log(f'Đã sang {after.name}.')
                self.coach.sync()
                self._save()  # Facing changes even when a wall blocks movement.
        elif key == "q":
            if not self._save():
                return True
            self.return_to_menu = bool(getattr(self, 'quit_to_menu', True))
            return False
        elif key == "p" or (self._curses and key == self._curses.KEY_F5):
            if self._save():
                self._log("Đã lưu ván chơi.")
        elif key == "e":
            try:
                self._interact()
            except GameError as error:
                self._log(error)
        elif key == "m":
            self._overview()
        elif key == "r":
            self._regions()
        elif key == "j":
            self._directory()
        elif key == "c":
            self._character()
        elif key == "t":
            self.coach.panel()
        elif key == "n":
            self.activities.daily_menu()
        elif key == "o":
            self.activities.open_auto()
        elif key == "g":
            self._toggle_map_style()
        elif key == "z":
            self._toggle_map_width()
        elif key == "i":
            self._inventory(False)
        elif key == "f":
            self._farm()
        elif key == "b":
            self._barn()
        elif key == "k":
            self._fish_collection()
        elif key in ("h", "?"):
            self._help()
        return True

    def _put(self, y, x, text, color="", bold=False):
        height, width = self._screen.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            return
        # Never write the terminal's lower-right cell, which some curses reject.
        available = width - x - int(y == height - 1)
        if available <= 0:
            return
        if color == 'selected':
            attr = (self._colors.get('yellow', 0)
                    | getattr(self._curses, 'A_REVERSE', 0))
        else:
            attr = self._colors.get(color, 0)
        if color in ('dim', 'shadow'):
            attr |= getattr(self._curses, 'A_DIM', 0)
        if getattr(self, '_dim_base', False):
            attr |= getattr(self._curses, 'A_DIM', 0)
        if bold:
            attr |= getattr(self._curses, 'A_BOLD', 0)
        try:
            self._screen.addnstr(y, x, fit_text(str(text), available), available, attr)
        except (self._curses.error, UnicodeError):
            pass

    def _clear(self):
        self._screen.erase()

    def _refresh(self):
        try:
            self._screen.refresh()
        except self._curses.error:
            pass

    def _draw(self, refresh=True, size=None):
        from .map_art import map_cell, map_legend
        from .map_view import map_layout, frame_lines, objective_line, status_line
        from .artwork import symbol
        from . import pages
        self._clear()
        height, width = size if size is not None else self._screen.getmaxyx()
        farm = self.farm
        expanded = bool(getattr(self, 'map_expanded', False))
        g = tui.glyphs(self.unicode_map)
        place = symbol('home' if farm.area == 'home' else 'map',
                       unicode=self.unicode_map)
        location = f"{place} {world.location_name(farm)} · ({farm.player_x}, {farm.player_y})"
        self._put(0, 0, tui.ellipsize(location, width, unicode=self.unicode_map),
                  "yellow", True)
        brand = f"{g['icon']} MOSSBROOK MEADOW"
        if width >= tui.cells(location) + tui.cells(brand) + 4:
            self._put(0, width - tui.cells(brand) - 1, brand, 'dim')
        status_color = ('red' if farm.hp <= max(1, farm.max_hp // 3)
                        else 'cyan')
        self._put(1, 0,
                  tui.ellipsize(status_line(farm, width, unicode=self.unicode_map),
                                width, unicode=self.unicode_map), status_color)
        if not expanded:
            goal = objective_line(farm, width, unicode=self.unicode_map)
            self._put(2, 0, tui.ellipsize(goal, width, unicode=self.unicode_map),
                      "green" if not (farm.attribute_points or farm.skill_points)
                      else "yellow")
        if height < 10 or width < 22:
            self._put(3, 0, "Hãy mở rộng terminal.", "yellow")
            self._put(4, 0, "Q về menu · I túi")
            if self._save_error:
                self._put(height - 2, 0, self._save_error, "red")
            self.activities.draw_curses()
            if refresh:
                self._refresh()
            return
        layout = map_layout(farm, width, height, expanded=expanded)
        path = (self.activities.path_points() if self.activities.running
                else self.coach.path_points())
        if layout.framed:
            top, bottom, side = frame_lines(
                layout, farm.area, unicode=self.unicode_map,
                page_name=pages.page_name(farm))
            self._put(layout.y - 1, layout.x - 1, top, 'cyan')
            self._put(layout.y + layout.rows, layout.x - 1, bottom, 'cyan')
            for row in range(layout.rows):
                self._put(layout.y + row, layout.x - 1, side, 'cyan')
                self._put(layout.y + row, layout.x + layout.cols * layout.cell, side, 'cyan')
        for row in range(layout.rows):
            for col in range(layout.cols):
                x, y = col + layout.left, row + layout.top
                art = map_cell(farm, x, y, unicode=self.unicode_map, path=path)
                self._put(row + layout.y, layout.x + col * layout.cell,
                          art.glyph + (art.tail if layout.cell == 2 else ''), art.color, art.bold)
        legends = map_legend(farm, unicode=self.unicode_map)
        if expanded:
            _, hint = world.context(farm)
            if self.activities.running:
                hint = self.activities.status_lines()[0]
            line = self._save_error and ('LỖI LƯU: ' + self._save_error) or hint
            self._put(2, 0, tui.ellipsize(line, width, unicode=self.unicode_map),
                      'red' if self._save_error else 'yellow', True)
            if not getattr(self, '_dim_base', False):
                from .toast import draw_toasts
                now = time.monotonic()
                draw_toasts(self, width, height, self.toasts.visible(now),
                            unicode=self.unicode_map, top=3, now=now)
            if refresh:
                self._refresh()
            return
        if layout.framed and len(legends) > 1 and width >= 64:
            caption = fit_text(f' {legends[0]} ', layout.cols * layout.cell - 2)
            self._put(layout.y + layout.rows, layout.x + 1, caption, 'green')
            legend = legends[1]
        else:
            legend = legends[-1] if world.target_plot(farm) else legends[0]
        self._put(height - 6, 0,
                  tui.ellipsize(legend, width, unicode=self.unicode_map), "green")
        _, hint = world.context(farm)
        self._put(height - 5, 0,
                  tui.ellipsize(hint, width, unicode=self.unicode_map),
                  "yellow", True)
        for row, line in enumerate(self.messages[-3:]):
            self._put(height - 4 + row, 0,
                      tui.ellipsize(line, width, unicode=self.unicode_map))
        if self._save_error:
            self._put(height - 2, 0, "LỖI LƯU: " + self._save_error, "red", True)
        controls = (f"{g['icon']} Q về menu · WASD đi · E dùng · R khu vực · F ruộng · B chuồng · K cá · N/O · T tân thủ · G · Z rộng"
                    if width >= 90 else f"{g['icon']} Q · E · R khu vực · F/B/K · N/O · T tân thủ · G/Z"
                    if width >= 48 else f"{g['icon']} Q · E · R · T tân thủ · G/Z"
                    if width >= 30 else f"{g['icon']} Q · E · G")
        self._put(height - 1, 0, controls, "cyan")
        self.coach.draw_curses()
        self.activities.draw_curses()
        if not getattr(self, '_dim_base', False):
            from .toast import draw_toasts
            now = time.monotonic()
            draw_toasts(self, width, height, self.toasts.visible(now),
                        unicode=self.unicode_map, top=3, now=now)
        if refresh:
            self._refresh()

    def _draw_modal_backdrop(self, height, width):
        """Redraw the village dimmed so a floating panel has real depth."""
        if self._screen is None or self.farm is None:
            return
        self._dim_base = True
        try:
            self._draw(refresh=False, size=(height, width))
        finally:
            self._dim_base = False

    def _draw_status_bar(self, height, width, controls, message=None):
        if message is None:
            message = (f"LỖI LƯU: {self._save_error}" if self._save_error
                       else (self.messages[-1] if self.messages else ''))
        tui.draw_status_bar(self, height, width, controls, message,
                            unicode=self.unicode_map, error=bool(self._save_error))

    def _choose(self, title, options, details=(), art=(), close_keys=()):
        """Scrollable floating dialog. Returns option index or None; all keys stay immediate."""
        selected = 0
        art = tuple(art)
        while True:
            height, width = self._screen.getmaxyx()
            if height < 8 or width < 20:
                self._clear()
                self._put(0, 0, tui.ellipsize(title, width, unicode=self.unicode_map),
                          "yellow", True)
                art_rows = min(len(art), max(0, height - 5))
                for row, line in enumerate(art[:art_rows], 1):
                    self._put(row, 0, tui.clip(line, width), 'magenta')
                room = max(1, height - 3 - art_rows)
                start = max(0, min(selected - room + 1, max(0, len(options) - room)))
                for offset, option in enumerate(options[start:start + room]):
                    index = start + offset
                    self._put(1 + art_rows + offset, 0,
                              tui.ellipsize(f"{'>' if index == selected else ' '} "
                                            f"{index + 1}. {option}", width,
                                            unicode=self.unicode_map),
                              "selected" if index == selected else "",
                              index == selected)
                self._put(height - 2, 0,
                          "↑↓ chọn · Enter dùng · Esc quay lại" if self.unicode_map
                          else "W/S chọn · Enter dùng · Esc quay lại", "cyan")
                if self.messages:
                    self._put(height - 1, 0, tui.ellipsize(self.messages[-1], width,
                                                           unicode=self.unicode_map))
                self._refresh()
                option_room = room
            else:
                self._draw_modal_backdrop(height, width)
                wrapped_details = []
                for line in details:
                    wrapped_details.extend(wrap_cells(line, max(2, min(width - 10, 72))))
                content_width = max(
                    [tui.cells(title)]
                    + [tui.cells(line) for line in wrapped_details]
                    + [tui.cells(line) for line in art]
                    + [tui.cells(option) + 6 for option in options]
                )
                rect = tui.panel_geometry(
                    height, width,
                    content_width=min(width, content_width + 8),
                    content_height=len(art) + len(wrapped_details) + len(options) + 4,
                    margin_x=3 if width >= 50 else 1, margin_y=1,
                    bottom_reserve=2, min_width=30, min_height=7)
                body = tui.draw_panel(self, rect, title=title,
                                      unicode=self.unicode_map, accent='cyan',
                                      title_color='yellow', shadow=True,
                                      bounds=(height, width))
                inner_w, inner_h = body.width, body.height
                text_w = max(1, inner_w - 2)
                art_rows = min(len(art), max(0, inner_h - 3))
                for row, line in enumerate(art[:art_rows]):
                    self._put(body.y + row, body.x + 1,
                              tui.ellipsize(line, text_w, unicode=self.unicode_map),
                              'magenta')
                remaining_h = max(1, inner_h - art_rows)
                wrapped_details = []
                for line in details:
                    wrapped_details.extend(wrap_cells(line, text_w))
                min_option_room = min(len(options), 3)
                detail_room = min(len(wrapped_details),
                                  max(0, remaining_h - min_option_room - 1))
                separator = 1 if wrapped_details and detail_room else 0
                option_room = max(1, remaining_h - detail_room - separator)
                if wrapped_details and option_room < 1:
                    detail_room = max(0, detail_room - 1)
                    separator = 1 if detail_room else 0
                    option_room = max(1, remaining_h - detail_room - separator)
                detail_start = body.y + art_rows
                for row, line in enumerate(wrapped_details[:detail_room]):
                    text = line
                    if row == detail_room - 1 and detail_room < len(wrapped_details):
                        extra = len(wrapped_details) - detail_room
                        suffix = f" · +{extra} dòng"
                        text = (tui.ellipsize(text, max(1, text_w - tui.cells(suffix)),
                                             unicode=self.unicode_map) + suffix)
                    self._put(detail_start + row, body.x + 1, text, 'cyan')
                option_start = detail_start + detail_room + separator
                g = tui.glyphs(self.unicode_map)
                if separator:
                    self._put(detail_start + detail_room, body.x + 1,
                              g['h'] * max(0, text_w), 'dim')
                start = max(0, min(selected - option_room + 1,
                                   max(0, len(options) - option_room)))
                for offset, option in enumerate(options[start:start + option_room]):
                    index = start + offset
                    label = f"{'>' if index == selected else ' '} {index + 1}. {option}"
                    row = option_start + offset
                    if index == selected:
                        self._put(row, body.x, ' ' * inner_w, 'selected')
                        self._put(row, body.x + 1,
                                  tui.ellipsize(label, text_w, unicode=self.unicode_map),
                                  'selected', True)
                    else:
                        self._put(row, body.x + 1,
                                  tui.ellipsize(label, text_w, unicode=self.unicode_map))
                quick = '1–9' if self.unicode_map else '1-9'
                nav = '↑↓/W/S' if self.unicode_map else 'W/S'
                controls = (f"{nav} chọn · Enter/E dùng · {quick} chọn nhanh · Esc/Q quay lại"
                            if width >= 64 else
                            f"{nav if self.unicode_map else 'W/S'} chọn · Enter dùng · Esc quay lại")
                if len(options) > option_room:
                    counter = f"Mục {selected + 1}/{len(options)}"
                    if width >= 50:
                        # The long hint would push the counter off-screen.
                        nav = '↑↓/W/S' if self.unicode_map else 'W/S'
                        controls = (f"{nav} chọn · Enter/E dùng · {counter}"
                                    " · Esc/Q")
                    else:
                        controls += f" · {counter}"
                self._draw_status_bar(height, width, controls)
                self._refresh()
            key = self._read()
            if key in ("q", "Q", "\x1b") or key in close_keys:
                return None
            if key in (getattr(self._curses, 'KEY_UP', -1), "w", "W", "k", "K"):
                selected = max(0, selected - 1)
            elif key in (getattr(self._curses, 'KEY_DOWN', -1), "s", "S", "j", "J"):
                selected = min(len(options) - 1, selected + 1)
            elif key == getattr(self._curses, 'KEY_PPAGE', -1):
                selected = max(0, selected - option_room)
            elif key == getattr(self._curses, 'KEY_NPAGE', -1):
                selected = min(len(options) - 1, selected + option_room)
            elif key in ("\n", "\r", "e", "E", getattr(self._curses, 'KEY_ENTER', -1)):
                return selected if options else None
            elif isinstance(key, str) and key in "123456789" and int(key) <= len(options):
                return int(key) - 1

    def _number(self, title, maximum=None):
        value = ""
        while True:
            height, width = self._screen.getmaxyx()
            if height < 12 or width < 34:
                self._clear()
                self._put(1, 0, tui.ellipsize(title, width, unicode=self.unicode_map),
                          "yellow", True)
                self._put(3, 0, "Số lượng: " + value + "_")
                self._put(5, 0, "Enter xác nhận · * tất cả · Esc/Q hủy", "cyan")
                self._refresh()
            else:
                self._draw_modal_backdrop(height, width)
                rect = tui.panel_geometry(
                    height, width,
                    content_width=max(36, tui.cells(title) + 8),
                    content_height=10, margin_x=3, margin_y=1,
                    bottom_reserve=2, min_width=34, min_height=9)
                body = tui.draw_panel(self, rect, title=title,
                                      unicode=self.unicode_map, accent='cyan',
                                      title_color='yellow', bounds=(height, width))
                self._put(body.y, body.x + 1, 'Số lượng cần nhập', 'dim')
                field = ' ' + value + '_'
                self._put(body.y + 2, body.x + 1, ' ' * max(1, body.width - 2),
                          'selected')
                self._put(body.y + 2, body.x + 2,
                          tui.ellipsize(field, max(1, body.width - 4),
                                        unicode=self.unicode_map),
                          'selected', True)
                if maximum is not None:
                    self._put(body.y + 4, body.x + 1,
                              tui.ellipsize(f"Tối đa: {maximum} · * chọn tất cả",
                                            max(1, body.width - 2),
                                            unicode=self.unicode_map), 'cyan')
                self._draw_status_bar(
                    height, width,
                    "Enter xác nhận · * tất cả · ⌫ xóa · Esc/Q hủy")
                self._refresh()
            key = self._read()
            if key in ("q", "Q", "\x1b"):
                return None
            if key == "*" and maximum is not None:
                return maximum
            if key in ("\n", "\r", getattr(self._curses, 'KEY_ENTER', -1)):
                if value and int(value) > 0:
                    return int(value)
            elif key in ("\x7f", "\b", getattr(self._curses, 'KEY_BACKSPACE', -1)):
                value = value[:-1]
            elif isinstance(key, str) and key in "0123456789" and len(value) < 7:
                value += key

    def _interact(self):
        action, hint = world.context(self.farm)
        if action == "home":
            if self._action(world.enter_home, self.farm):
                self.coach.event('enter_home')
        elif action == "exit":
            self._action(world.leave_home, self.farm)
        elif action == "tv":
            self._log(self.farm.forecast_report())
            self.coach.event('tv')
        elif action == "bed":
            thirsty = sum(1 for key, plot in self.farm.plots.items()
                          if plot.crop and not plot.dead and not plot.ready and not self.farm.is_watered(key))
            if thirsty and self._choose(f"Còn {thirsty} cây thiếu nước. Ngủ luôn?", ["Quay lại tưới cây", "Ngủ sang ngày mới"]) != 1:
                return
            self._action(self.farm.sleep)
        elif action == "npc":
            self._conversation()
        elif action == "plot":
            self._plot()
        elif action == "chest":
            self._inventory(True)
        elif action == "kitchen":
            self._cooking()
        elif action == "shop":
            self._shop()
        elif action == "barn":
            self._barn()
        elif action == "mine":
            self._action(world.enter_mine, self.farm)
        elif action == "mine_exit":
            self._action(world.leave_mine, self.farm)
        elif action == "rock":
            rock = world.target_rock(self.farm)
            if rock is not None:
                from .mining import mine_rock
                self._action(mine_rock, self.farm, *rock)
        elif action == "forge":
            self._forge()
        elif action == "dungeon_gate":
            self._dungeon()
        elif action == "fish":
            self._fish()
        elif action == "forest":
            self._action(self.farm.work)
        else:
            self._log(hint)

    def _reader(self, title, message, *, close_keys=None):
        """Read every line of a reply inside a floating document window."""
        close_keys = tuple(close_keys or ('q', 'Q', '\x1b'))
        offset = 0
        pinned_end = False
        while True:
            height, width = self._screen.getmaxyx()
            if height < 8 or width < 20:
                self._clear()
                lines = wrap_cells(message, max(1, width - 1))
                room = max(1, height - 4)
                offset = max(0, len(lines) - room) if pinned_end else min(offset, max(0, len(lines) - room))
                self._put(0, 0, tui.ellipsize(title, width, unicode=self.unicode_map),
                          "yellow", True)
                for row, line in enumerate(lines[offset:offset + room], 2):
                    self._put(row, 0, line)
                dash = '–' if self.unicode_map else '-'
                nav = '↑↓/W/S' if self.unicode_map else 'W/S'
                self._put(height - 2, 0, f"Dòng {offset + 1}{dash}{min(len(lines), offset + room)}/{len(lines)}", "cyan")
                self._put(height - 1, 0, f"{nav} cuộn · Space tiếp · Q/Esc về", "cyan")
                self._refresh()
            else:
                self._draw_modal_backdrop(height, width)
                margin_x = 1 if width >= 20 else 0
                rect = tui.Rect(margin_x, 0, width - 2 * margin_x, height)
                body = tui.draw_panel(self, rect, title=title,
                                      unicode=self.unicode_map, accent='cyan',
                                      title_color='yellow', shadow=margin_x > 0,
                                      bounds=(height, width))
                text_w = max(1, body.width - 2)
                lines = wrap_cells(message, text_w)
                room = max(1, height - 4)
                offset = (max(0, len(lines) - room) if pinned_end
                          else min(offset, max(0, len(lines) - room)))
                for row, line in enumerate(lines[offset:offset + room], 2):
                    self._put(row, body.x + 1, line)
                g = tui.glyphs(self.unicode_map)
                dash = '–' if self.unicode_map else '-'
                nav = '↑↓/W/S' if self.unicode_map else 'W/S'
                status = f"Dòng {offset + 1}{dash}{min(len(lines), offset + room)}/{len(lines)}"
                self._put(height - 2, rect.x,
                          tui.pad(' ' + status, rect.width), 'cyan')
                controls = f"{nav} cuộn · Space tiếp · Q/Esc về"
                label = tui.clip(' ' + controls + ' ', max(0, rect.width - 3))
                rest = rect.width - 3 - tui.cells(label)
                bottom = (g['bl'] + g['h'] + label + g['h'] * max(0, rest) + g['br']
                          if rest >= 0 else g['bl'] + label + g['br'])
                self._put(height - 1, rect.x, bottom, 'cyan')
                self._refresh()
            key = self._read()
            if key in close_keys:
                return False
            if key in ('\n', '\r', 'e', 'E', getattr(self._curses, 'KEY_ENTER', -1)):
                return True
            if key in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                offset = min(max(0, len(lines) - room), offset + 1)
            elif key in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                pinned_end = False
                offset = max(0, offset - 1)
            elif key in (' ', getattr(self._curses, 'KEY_NPAGE', -1)):
                if offset + room >= len(lines):
                    return True
                offset += room
            elif key == getattr(self._curses, 'KEY_PPAGE', -1):
                pinned_end = False
                offset = max(0, offset - room)
            elif key == getattr(self._curses, 'KEY_END', -1):
                pinned_end = True
                offset = max(0, len(lines) - room)
            elif key == getattr(self._curses, 'KEY_HOME', -1):
                pinned_end = False
                offset = 0

    def _conversation(self):
        from .villagers import TOPICS, bond_title, nearby_npc
        from .dialogue import begin_dialogue, choose_response, dialogue_node
        from .artwork import hearts, npc_portrait
        npc = nearby_npc(self.farm)
        if npc is None:
            return
        topics = list(TOPICS)
        portrait = npc_portrait(npc.id, unicode=self.unicode_map) if self._screen else ()
        while True:
            friendship = self.farm.friendships[npc.id]
            title = (f'{npc.name} · {npc.role} · {bond_title(friendship)} · '
                     f'{hearts(friendship, unicode=self.unicode_map)} {friendship}/10')
            details = [
                f'“{npc.motto}”',
                f'Thích: {npc.likes}',
                f'Lịch sinh hoạt: {npc.schedule}',
                npc.description,
            ]
            index = self._choose(title, [TOPICS[key] for key in topics], details,
                                 art=portrait)
            if index is None:
                return
            conversation = begin_dialogue(self.farm, npc.id, topics[index])
            while not conversation.done:
                node = dialogue_node(conversation)
                available = '\n'.join(f'{number}. {choice.text}'
                                      for number, choice in enumerate(node.choices, 1))
                readable = ('\n\n'.join(conversation.history)
                            + '\n\nBạn có thể trả lời:\n' + available)
                if self._reader(f'{npc.name} · Space/Enter để trả lời',
                                readable) is False:
                    return
                response = self._choose(
                    f'{npc.name} đang chờ bạn trả lời · {TOPICS[topics[index]]}',
                    [choice.text for choice in node.choices],
                    [f'Thân {friendship}/10 · {bond_title(friendship)} · Chọn một hướng trò chuyện.'],
                    art=portrait)
                if response is None:
                    return
                reply = choose_response(self.farm, conversation, node.choices[response].id)
                self._log(reply)
                self._save()
            self._reader(f'{npc.name} · Kết thúc cuộc trò chuyện',
                         '\n\n'.join(conversation.history)
                         + f'\n\n{hearts(self.farm.friendships[npc.id], unicode=self.unicode_map)} '
                           f'{self.farm.friendships[npc.id]}/10 · {bond_title(self.farm.friendships[npc.id])}')
            self.coach.event('talk', npc_id=npc.id, done=conversation.done)

    def _character(self):
        """Open the illustrated character sheet, with a list fallback."""
        self.coach.event('character')
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 20 or width < 64:
            self._character_list()
        else:
            self._character_sheet()

    @staticmethod
    def _character_definitions():
        return [*[(key, info, True) for key, info in ATTRIBUTES.items()],
                *[(key, info, False) for key, info in SKILLS.items()]]

    def _character_list(self):
        definitions = self._character_definitions()
        while True:
            labels = []
            for key, info, is_attribute in definitions:
                value = (self.farm.attributes if is_attribute else self.farm.skills)[key]
                labels.append(f'{info.name} {value}/5 · '
                              f'{"Thuộc tính" if is_attribute else "Tay nghề"} · 1 điểm')
            labels.append('Đọc mọi chỉ số và hiệu quả từng bậc')
            can_exchange = (all(value >= 5 for value in self.farm.attributes.values())
                            and all(value >= 5 for value in self.farm.skills.values())
                            and (self.farm.attribute_points or self.farm.skill_points))
            if can_exchange:
                labels.append('Đổi toàn bộ điểm dư thành xu')
            labels.append('Tab Trang bị và sức chiến đấu')
            labels.append('Tab Túi đồ đang mang')
            index = self._choose(
                f'NHÂN VẬT · {self.farm.avatar} {self.farm.player_name} · Cấp {self.farm.level} · XP {self.farm.xp % 40}/40',
                labels,
                [f'Còn {self.farm.attribute_points} điểm thuộc tính / {self.farm.skill_points} điểm tay nghề',
                 f'Sức {self.farm.energy}/{self.farm.energy_limit} · Mỗi cấp +1 thuộc tính, +2 tay nghề'],
                close_keys=('c', 'C'))
            if index is None:
                return
            if index == len(definitions):
                self._reader('CHỈ SỐ NHÂN VẬT', '\n\n'.join(character_lines(self.farm)))
                continue
            if can_exchange and index == len(definitions) + 1:
                self._action(exchange_points, self.farm)
                continue
            extra = 2 if can_exchange else 1
            if index == len(definitions) + extra:
                from .forge import gear_lines
                self._reader('TRANG BỊ · SỨC CHIẾN ĐẤU',
                             '\n\n'.join(gear_lines(self.farm)))
                continue
            if index == len(definitions) + extra + 1:
                from .inventory import inventory_rows
                rows = [f'{name}: {bag}' for _, name, bag, _ in
                        inventory_rows(self.farm) if bag]
                self._reader('TÚI ĐỒ ĐANG MANG',
                             '\n'.join(rows) if rows else 'Túi đang trống.')
                continue
            key, info, is_attribute = definitions[index]
            if self._choose(f'{info.name} · hiệu quả',
                            ['Nâng 1 bậc (tốn 1 điểm)', 'Quay lại'],
                            wrap_cells(info.description, max(2, self._screen.getmaxyx()[1] - 1))) == 0:
                self._action(upgrade_attribute if is_attribute else upgrade_skill, self.farm, key)

    def _character_sheet(self):
        """Character profile with tabs for stats, equipment and the bag."""
        from .artwork import (icon_for, player_portrait, pips, stat_icon,
                              symbol, weather_icon)
        from .catalog import GEAR, MAX_GEAR, WEATHER
        from .forge import (attack_power, defense_power, gear_lines,
                            mining_bonus, mining_energy_cost, recipe_for,
                            recipe_label)
        from .identity import BACKGROUNDS, OUTFITS
        from .inventory import inventory_rows
        definitions = self._character_definitions()
        tabs = ('HỒ SƠ', 'TRANG BỊ', 'TÚI ĐỒ')
        tab = 0
        selected = 0
        gear_selected = 0
        bag_selected = 0
        bag_offset = 0
        gear_keys = list(GEAR)
        while True:
            height, width = self._screen.getmaxyx()
            if height < 20 or width < 64:
                self._character_list()
                return
            bag_rows = [row for row in inventory_rows(self.farm) if row[2]]
            if bag_rows:
                bag_selected = max(0, min(bag_selected, len(bag_rows) - 1))
            else:
                bag_selected = 0
            self._draw_modal_backdrop(height, width)
            g = tui.glyphs(self.unicode_map)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 92),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=64, min_height=18)
            nav = '↑↓' if self.unicode_map else 'W/S'
            status_nav = f'{nav}/W/S' if self.unicode_map else 'W/S'
            if tab == 0:
                controls = (f'{status_nav} chọn · 1–7 chọn nhanh · Enter nâng · '
                            'Tab đổi tab · Space hồ sơ · Esc đóng'
                            if width >= 80 else
                            f'{status_nav} chọn · Enter nâng · Tab · Space · Esc')
            elif tab == 1:
                controls = (f'{status_nav} chọn · A/D hoặc Tab đổi tab · '
                            'Enter xem đầy đủ · Esc đóng'
                            if width >= 80 else
                            f'{status_nav} chọn · A/D đổi tab · Esc đóng')
            else:
                controls = (f'{status_nav} chọn · A/D hoặc Tab đổi tab · '
                            'I mở túi đầy đủ · Esc đóng'
                            if width >= 80 else
                            f'{status_nav} chọn · A/D đổi tab · Esc đóng')
            body = tui.draw_panel(
                self, rect,
                title=(f'HỒ SƠ NÔNG DÂN · {self.farm.avatar} {self.farm.player_name}'
                       f' · Cấp {self.farm.level}'),
                footer=controls,
                unicode=self.unicode_map, accent='green', title_color='yellow',
                bounds=(height, width))
            # Tabs share the panel with the portrait; content starts one row
            # lower so the same sheet feels continuous on every tab.
            tab_x = body.x + 1
            for index, name in enumerate(tabs):
                label = f' {name} '
                active = index == tab
                self._put(body.y, tab_x, label,
                          'selected' if active else 'dim', active)
                tab_x += tui.cells(label)
                if index < len(tabs) - 1:
                    self._put(body.y, tab_x, g['v'], 'dim')
                    tab_x += 1
            top = body.y + 1
            left_w = min(36, max(26, body.width * 2 // 5))
            right_x = body.x + left_w + 1
            right_w = max(8, body.right - right_x + 1)

            # The portrait and identity stay visible on every tab.
            portrait = player_portrait(self.farm.avatar, unicode=self.unicode_map)
            for row, line in enumerate(portrait):
                self._put(top + row, body.x + 1, line, self.farm.outfit, True)
            info_y = top + len(portrait)
            weather = weather_icon(self.farm.weather, unicode=self.unicode_map)
            lines = [
                (f'{self.farm.avatar} {self.farm.player_name}', 'yellow', True),
                (f'Nông trại {self.farm.name}', 'green', False),
                (f'{BACKGROUNDS[self.farm.background]} · {OUTFITS[self.farm.outfit]}', 'dim', False),
                (f'{weather} {WEATHER[self.farm.weather]} · '
                 f'{symbol("coin", unicode=self.unicode_map)} {self.farm.coins} xu', 'cyan', False),
                (f'{symbol("heart", unicode=self.unicode_map)} '
                 f'{self.farm.energy}/{self.farm.energy_limit} sức · '
                 f'{symbol("chart", unicode=self.unicode_map)} cấp {self.farm.level}', 'cyan', False),
            ]
            for row, (line, color, bold) in enumerate(lines):
                if info_y + row >= body.y + body.height - 2:
                    break
                self._put(info_y + row, body.x + 1,
                          tui.ellipsize(line, max(1, left_w - 2),
                                        unicode=self.unicode_map), color, bold)
            xp_y = info_y + len(lines)
            if xp_y < body.y + body.height - 1:
                bar_width = max(4, left_w - 12)
                xp = self.farm.xp % 40
                self._put(xp_y, body.x + 1,
                          tui.ellipsize(
                              f'XP {xp:>2}/40 {tui.progress_bar(xp / 40, bar_width, unicode=self.unicode_map)}',
                              max(1, left_w - 2), unicode=self.unicode_map), 'magenta')
            points_y = xp_y + 1
            point_lines = (
                f'{symbol("star", unicode=self.unicode_map)} '
                f'{self.farm.attribute_points} điểm thuộc tính',
                f'{symbol("gear", unicode=self.unicode_map)} '
                f'{self.farm.skill_points} điểm tay nghề',
            )
            for offset, line in enumerate(point_lines):
                if points_y + offset >= body.y + body.height - 1:
                    break
                self._put(points_y + offset, body.x + 1,
                          tui.ellipsize(line, max(1, left_w - 2),
                                        unicode=self.unicode_map), 'cyan')

            bottom = body.y + body.height
            if tab == 0:
                row = top
                self._put(row, right_x, ' THUỘC TÍNH ', 'dim')
                row += 1
                for index, (key, info, is_attribute) in enumerate(definitions):
                    if index == 3:
                        row += 1
                        if row < bottom - 3:
                            self._put(row, right_x, ' TAY NGHỀ ', 'dim')
                        row += 1
                    if row >= bottom - 3:
                        break
                    value = (self.farm.attributes if is_attribute else self.farm.skills)[key]
                    icon = stat_icon(key, unicode=self.unicode_map)
                    available = (self.farm.attribute_points if is_attribute
                                 else self.farm.skill_points)
                    point = (symbol('star', unicode=self.unicode_map)
                             if available and value < 5 else ' ')
                    text = (f'{g["arrow"] if index == selected else " "} {icon} {info.name:<9} '
                            f'{pips(value, unicode=self.unicode_map)} {value}/5{point}')
                    if index == selected:
                        self._put(row, right_x, ' ' * right_w, 'selected')
                        self._put(row, right_x,
                                  tui.ellipsize(text, max(1, right_w - 1),
                                                unicode=self.unicode_map), 'selected', True)
                    else:
                        color = 'dim' if value >= 5 else ''
                        self._put(row, right_x,
                                  tui.ellipsize(text, max(1, right_w - 1),
                                                unicode=self.unicode_map), color)
                    row += 1

                detail_y = bottom - 3
                self._put(detail_y, right_x, g['h'] * right_w, 'dim')
                key, info, is_attribute = definitions[selected]
                description = wrap_cells(info.description, max(2, right_w - 2))
                detail = description[:2]
                if len(description) > 2:
                    detail[-1] = tui.ellipsize(detail[-1] + ' …', right_w - 2,
                                               unicode=self.unicode_map)
                for offset, line in enumerate(detail):
                    if detail_y + 1 + offset >= bottom:
                        break
                    self._put(detail_y + 1 + offset, right_x, line, 'cyan')
            elif tab == 1:
                row = top
                self._put(row, right_x, ' TRANG BỊ ', 'dim')
                row += 1
                for index, key in enumerate(gear_keys):
                    info = GEAR[key]
                    rank = self.farm.gear.get(key, 0)
                    icon = info.icon if self.unicode_map else info.ascii_icon
                    if row >= bottom - 5:
                        break
                    text = (f'{g["arrow"] if index == gear_selected else " "} '
                            f'{icon} {info.name:<8} {pips(rank, unicode=self.unicode_map)} '
                            f'{rank}/{MAX_GEAR}')
                    if index == gear_selected:
                        self._put(row, right_x, ' ' * right_w, 'selected')
                        self._put(row, right_x,
                                  tui.ellipsize(text, max(1, right_w - 1),
                                                unicode=self.unicode_map), 'selected', True)
                    else:
                        self._put(row, right_x,
                                  tui.ellipsize(text, max(1, right_w - 1),
                                                unicode=self.unicode_map))
                    row += 1
                    effect = wrap_cells(info.effect, max(2, right_w - 3))
                    if row < bottom - 5 and effect:
                        self._put(row, right_x + 2,
                                  tui.ellipsize(effect[0], max(1, right_w - 3),
                                                unicode=self.unicode_map), 'dim')
                        row += 1
                    recipe = recipe_for(self.farm, key)
                    if row < bottom - 5:
                        next_text = ('Đã đạt bậc tối đa.' if recipe is None
                                     else 'Kế: ' + recipe_label(recipe))
                        self._put(row, right_x + 2,
                                  tui.ellipsize(next_text, max(1, right_w - 3),
                                                unicode=self.unicode_map), 'cyan')
                        row += 1
                if row < bottom - 3:
                    self._put(row, right_x, g['h'] * right_w, 'dim')
                    row += 1
                summary = (
                    f'Sát thương {attack_power(self.farm)} · '
                    f'phòng thủ {defense_power(self.farm)}',
                    f'Đào {mining_energy_cost(self.farm)} sức · '
                    f'thêm {mining_bonus(self.farm)} quặng · '
                    f'máu tối đa {self.farm.max_hp}',
                    'Rèn tại lò rèn trong mỏ: đứng cạnh F rồi nhấn E.',
                )
                for line in summary:
                    if row >= bottom - 1:
                        break
                    self._put(row, right_x,
                              tui.ellipsize(line, max(1, right_w - 1),
                                            unicode=self.unicode_map), 'cyan')
                    row += 1
            else:
                total = sum(row[2] for row in bag_rows)
                value = sum(sale_price(self.farm, key) * bag
                            for key, _, bag, _ in bag_rows
                            if sale_price(self.farm, key))
                row = top
                self._put(row, right_x,
                          tui.ellipsize(f' TÚI ĐỒ · {total} món · {value} xu ',
                                        max(1, right_w - 1),
                                        unicode=self.unicode_map), 'dim')
                list_top = top + 1
                detail_y = bottom - 3
                available = max(1, detail_y - list_top)
                bag_offset = max(0, min(bag_offset,
                                        max(0, len(bag_rows) - available)))
                if bag_selected < bag_offset:
                    bag_offset = bag_selected
                elif bag_selected >= bag_offset + available:
                    bag_offset = bag_selected - available + 1
                if not bag_rows:
                    self._put(list_top, right_x + 1,
                              'Túi đang trống. Hãy thu hoạch hoặc đào quặng.',
                              'dim')
                for slot, (key, name, bag, stored) in enumerate(
                        bag_rows[bag_offset:bag_offset + available]):
                    index = bag_offset + slot
                    selected_row = index == bag_selected
                    marker = ('▸ ' if self.unicode_map else '> ') if selected_row else '  '
                    text = f'{marker}{icon_for(key, unicode=self.unicode_map)} {name} ×{bag}'
                    if stored:
                        text += f' · rương {stored}'
                    if selected_row:
                        self._put(list_top + slot, right_x, ' ' * right_w, 'selected')
                        self._put(list_top + slot, right_x,
                                  tui.ellipsize(text, max(1, right_w - 1),
                                                unicode=self.unicode_map), 'selected', True)
                    else:
                        self._put(list_top + slot, right_x,
                                  tui.ellipsize(text, max(1, right_w - 1),
                                                unicode=self.unicode_map))
                self._put(detail_y, right_x, g['h'] * right_w, 'dim')
                if bag_rows:
                    key, name, _, _ = bag_rows[bag_selected]
                    note = wrap_cells(self._inventory_note(key), max(2, right_w - 2))
                    for offset, line in enumerate(note[:2]):
                        if detail_y + 1 + offset >= bottom:
                            break
                        self._put(detail_y + 1 + offset, right_x, line, 'dim')

            self._draw_status_bar(height, width, controls)
            self._refresh()

            key_name = self._read()
            if key_name in ('q', 'Q', 'c', 'C', '\x1b'):
                return
            if key_name == '\t' or key_name in ('d', 'D', getattr(self._curses, 'KEY_RIGHT', -1)):
                tab = (tab + 1) % len(tabs)
                continue
            if key_name in ('a', 'A', getattr(self._curses, 'KEY_LEFT', -1),
                            getattr(self._curses, 'KEY_BTAB', -1)):
                tab = (tab - 1) % len(tabs)
                continue
            if tab == 2 and key_name in ('i', 'I'):
                self._inventory(False)
                continue
            if tab == 0 and key_name in (' ', 'i', 'I'):
                self._reader('HỒ SƠ NÔNG DÂN · TOÀN BỘ CHỈ SỐ',
                             '\n\n'.join(character_lines(self.farm)))
                continue
            if tab == 0 and key_name in ('x', 'X'):
                self._action(exchange_points, self.farm)
                continue
            if key_name in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                if tab == 0:
                    selected = max(0, selected - 1)
                elif tab == 1:
                    gear_selected = max(0, gear_selected - 1)
                else:
                    bag_selected = max(0, bag_selected - 1)
            elif key_name in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                if tab == 0:
                    selected = min(len(definitions) - 1, selected + 1)
                elif tab == 1:
                    gear_selected = min(len(gear_keys) - 1, gear_selected + 1)
                else:
                    bag_selected = min(max(0, len(bag_rows) - 1), bag_selected + 1)
            elif key_name == getattr(self._curses, 'KEY_PPAGE', -1):
                if tab == 0:
                    selected = max(0, selected - 3)
                elif tab == 2:
                    bag_selected = max(0, bag_selected - 5)
            elif key_name == getattr(self._curses, 'KEY_NPAGE', -1):
                if tab == 0:
                    selected = min(len(definitions) - 1, selected + 3)
                elif tab == 2:
                    bag_selected = min(max(0, len(bag_rows) - 1), bag_selected + 5)
            elif tab == 0 and isinstance(key_name, str) and key_name in '1234567':
                selected = int(key_name) - 1
            elif key_name in ('\n', '\r', 'e', 'E',
                              getattr(self._curses, 'KEY_ENTER', -1)):
                if tab == 0:
                    key, info, is_attribute = definitions[selected]
                    self._action(upgrade_attribute if is_attribute else upgrade_skill,
                                 self.farm, key)
                elif tab == 1:
                    key = gear_keys[gear_selected]
                    self._reader(f'TRANG BỊ · {GEAR[key].name}',
                                 '\n\n'.join(gear_lines(self.farm)))
                elif bag_rows:
                    key, name, _, _ = bag_rows[bag_selected]
                    self._reader(f'VẬT PHẨM · {name}',
                                 self._inventory_note(key))

    def _directory(self):
        from .villagers import NPCS, bond_title
        from .artwork import hearts, npc_portrait
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 16 or width < 56:
            self._reader('DÂN LÀNG · Hãy đến gần và nhấn E để trò chuyện',
                         '\n\n'.join(directory_lines(self.farm)))
            return
        offset = 0
        npcs = list(NPCS.values())
        while True:
            height, width = self._screen.getmaxyx()
            self._draw_modal_backdrop(height, width)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 84),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=56, min_height=14)
            nav = '↑↓' if self.unicode_map else 'W/S'
            body = tui.draw_panel(
                self, rect, title=f'DÂN LÀNG · {len(npcs)} người · J/M đóng',
                footer=f'E khi đứng kề để trò chuyện · {nav} cuộn danh sách',
                unicode=self.unicode_map, accent='magenta', title_color='yellow',
                bounds=(height, width))
            block_h = 6
            visible = max(1, body.height // block_h)
            offset = max(0, min(offset, max(0, len(npcs) - visible)))
            for slot, npc in enumerate(npcs[offset:offset + visible]):
                top = body.y + slot * block_h
                friendship = self.farm.friendships[npc.id]
                portrait = npc_portrait(npc.id, unicode=self.unicode_map)
                for row, line in enumerate(portrait):
                    self._put(top + row, body.x + 1, line, 'magenta')
                info_x = body.x + 13
                info_w = max(4, body.right - info_x)
                self._put(top, info_x,
                          tui.ellipsize(f'{npc.glyph} · {npc.name} · {npc.role}',
                                        info_w, unicode=self.unicode_map),
                          'yellow', True)
                self._put(top + 1, info_x,
                          tui.ellipsize(f'{hearts(friendship, unicode=self.unicode_map)} '
                                        f'{friendship}/10 · {bond_title(friendship)}',
                                        info_w, unicode=self.unicode_map),
                          'red' if friendship else 'dim')
                self._put(top + 2, info_x,
                          tui.ellipsize(f'“{npc.motto}”', info_w,
                                        unicode=self.unicode_map), 'cyan')
                distance = (abs(npc.position[0] - self.farm.player_x)
                            + abs(npc.position[1] - self.farm.player_y))
                where = (f'Vị trí {npc.position} · cách {distance} bước'
                         if self.farm.area == 'village'
                         else f'Vị trí {npc.position} · đang ở ngoài làng')
                self._put(top + 3, info_x,
                          tui.ellipsize(f'{where} · Thích: {npc.likes}', info_w,
                                        unicode=self.unicode_map), 'dim')
                self._put(top + 4, info_x,
                          tui.ellipsize(f'Lịch: {npc.schedule}', info_w,
                                        unicode=self.unicode_map), 'dim')
            g = tui.glyphs(self.unicode_map)
            dash = '–' if self.unicode_map else '-'
            self._put(body.y + body.height - 1, body.x,
                      tui.ellipsize(f'{g["icon"]} {offset + 1}{dash}'
                                    f'{min(len(npcs), offset + visible)}/{len(npcs)}',
                                    body.width, unicode=self.unicode_map), 'cyan')
            self._draw_status_bar(
                height, width,
                f'{nav} cuộn · J/Esc/Enter đóng · E khi đứng kề để nói chuyện')
            self._refresh()
            key = self._read()
            if key in ('j', 'J', 'q', 'Q', '\x1b', '\n', '\r',
                       getattr(self._curses, 'KEY_ENTER', -1)):
                return
            if key in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                offset = max(0, offset - 1)
            elif key in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                offset = min(max(0, len(npcs) - visible), offset + 1)
            elif key == getattr(self._curses, 'KEY_PPAGE', -1):
                offset = max(0, offset - visible)
            elif key in (' ', getattr(self._curses, 'KEY_NPAGE', -1)):
                offset = min(max(0, len(npcs) - visible), offset + visible)

    def _regions(self):
        """Fast-travel directory for the named regions of the village."""
        from . import regions
        self.coach.event('map')
        cards = []
        for region in regions.travel_regions(self.farm):
            icon = region.icon if self.unicode_map else region.ascii_icon
            lock = ('' if regions.can_travel(self.farm, region)
                    else f' · cần cấp {region.level}')
            cards.append((region, f'{icon} {region.name} · {region.description}{lock}'))
        details = [
            f'{self.farm.avatar} Đang ở: {world.location_name(self.farm)}',
            'Đi nhanh không tốn năng lượng. Chọn một khu vực để dịch chuyển.',
        ]
        labels = [label for _, label in cards]
        if not getattr(self.farm, 'map_pages', False):
            details.append('Bản đồ cũ đang hiển thị toàn làng; có thể bật bản đồ theo trang.')
            labels.append('Bật bản đồ theo khu vực (mỗi lần một trang)')
        choice = self._choose('KHU VỰC · ĐI NHANH', labels,
                              details=details, close_keys=('r', 'R', 'm', 'M'))
        if choice is None:
            return
        if choice == len(cards):
            self.farm.map_pages = True
            self._log('Đã bật bản đồ theo khu vực. Đi qua đường ở rìa để sang trang tiếp.')
            self._save()
            return
        region, _ = cards[choice]
        self._action(regions.travel, self.farm, region.key)

    def _cooking(self):
        """Open the home kitchen: a compact card list on normal terminals."""
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 18 or width < 60:
            self._cooking_list()
        else:
            self._cooking_sheet()

    def _cooking_list(self):
        from .cooking import cook, ingredient_line, recipe_rows
        self.coach.event('cook')
        rows = recipe_rows(self.farm)
        options = []
        details = [f'{self.farm.avatar} Bếp nhà · nấu ăn không tốn năng lượng.',
                   'Món chín được cất vào túi và có thể bán ở cửa hàng.']
        for recipe, missing in rows:
            if self.farm.level < recipe.level:
                status = f'mở cấp {recipe.level}'
            elif missing:
                status = 'thiếu ' + ', '.join(
                    f'{ITEMS[item].name} ×{amount}'
                    for item, amount in missing.items())
            else:
                status = 'sẵn sàng'
            options.append(f'{recipe.name} · {status}')
            details.append(f'{recipe.name}: {ingredient_line(recipe, missing)} '
                           f'· +{recipe.energy} năng lượng · +{recipe.xp} XP')
        choice = self._choose('BẾP NHÀ · NẤU ĂN', options, details=details,
                              close_keys=('b', 'B', 'k', 'K', 'q', 'Q'))
        if choice is None:
            return
        recipe, _ = rows[choice]
        self._action(cook, self.farm, recipe.key)

    def _cooking_sheet(self):
        """Two-column cookbook: recipes on the left, selected dish on the right."""
        from .cooking import cook, ingredient_line, recipe_rows
        from .artwork import art_for, icon_for, symbol
        self.coach.event('cook')
        selected = 0
        offset = 0
        while True:
            height, width = self._screen.getmaxyx()
            if height < 18 or width < 60:
                self._cooking_list()
                return
            rows = recipe_rows(self.farm)
            selected = max(0, min(selected, len(rows) - 1))
            self._draw_modal_backdrop(height, width)
            g = tui.glyphs(self.unicode_map)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 88),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=60, min_height=17)
            nav = '↑↓' if self.unicode_map else 'W/S'
            body = tui.draw_panel(
                self, rect, title='BẾP NHÀ · NẤU ĂN',
                footer=(f'{nav} chọn · Enter nấu · B/K/Esc đóng'
                        if width < 72 else
                        f'{nav} chọn · Enter nấu món · B/K/Esc đóng'),
                unicode=self.unicode_map, accent='yellow', title_color='yellow',
                bounds=(height, width))
            left_w = min(38, max(30, body.width * 2 // 5))
            right_x = body.x + left_w + 1
            right_w = max(10, body.right - right_x + 1)
            coin = symbol('coin', unicode=self.unicode_map)
            self._put(body.y, body.x + 1,
                      tui.ellipsize(f'{coin} {self.farm.coins} xu · '
                                    f'{len(rows)} công thức · cấp {self.farm.level}',
                                    max(1, body.width - 2),
                                    unicode=self.unicode_map), 'cyan')
            visible = max(1, body.height - 3)
            if selected < offset:
                offset = selected
            elif selected >= offset + visible:
                offset = selected - visible + 1
            for row, (recipe, missing) in enumerate(rows[offset:offset + visible]):
                index = offset + row
                ready = not missing and self.farm.level >= recipe.level
                if self.farm.level < recipe.level:
                    status = f'cấp {recipe.level}'
                elif missing:
                    status = f'thiếu {len(missing)}'
                else:
                    status = 'sẵn sàng'
                icon = icon_for(recipe.key, unicode=self.unicode_map)
                label = (f'{g["arrow"] if index == selected else " "} '
                         f'{icon} {recipe.name} · {status}')
                line_y = body.y + 1 + row
                if index == selected:
                    self._put(line_y, body.x, ' ' * left_w, 'selected')
                    self._put(line_y, body.x + 1,
                              tui.ellipsize(label, max(1, left_w - 2),
                                            unicode=self.unicode_map),
                              'selected', True)
                else:
                    self._put(line_y, body.x + 1,
                              tui.ellipsize(label, max(1, left_w - 2),
                                            unicode=self.unicode_map),
                              'green' if ready else 'dim')
            recipe, missing = rows[selected]
            art = art_for(recipe.key, unicode=self.unicode_map)
            for row, line in enumerate(art):
                if row < body.height - 2:
                    self._put(body.y + row, right_x, line, 'yellow')
            detail_y = body.y + len(art)
            lines = [
                (f'{recipe.name}', 'selected' if selected == selected else 'yellow', True),
                (f'Món nấu · cấp {recipe.level} · bán {ITEMS[recipe.key].sell_price} xu',
                 'cyan', False),
                (f'Hồi {recipe.energy} năng lượng · +{recipe.xp} XP', 'green', False),
                (ingredient_line(recipe, missing), 'cyan', False),
                ('Sẵn sàng nấu.' if not missing else 'Còn thiếu nguyên liệu.',
                 'green' if not missing else 'red', False),
            ]
            for row, (line, color, bold) in enumerate(lines):
                max_w = max(1, right_w - 1)
                wrapped = wrap_cells(line, max_w)
                for part in wrapped:
                    if detail_y >= body.y + body.height - 1:
                        break
                    self._put(detail_y, right_x,
                              tui.ellipsize(part, max_w, unicode=self.unicode_map),
                              color, bold)
                    detail_y += 1
                if detail_y >= body.y + body.height - 1:
                    break
            self._draw_status_bar(
                height, width,
                (f'{nav} chọn · Enter nấu · B/K/Esc đóng'
                 if width < 72 else
                 f'{nav} chọn · Enter nấu món · B/K/Esc đóng'))
            self._refresh()
            key = self._read()
            if key in ('b', 'B', 'k', 'K', 'q', 'Q', '\x1b'):
                return
            if key in ('w', 'W', 'k', getattr(self._curses, 'KEY_UP', -1)):
                selected = max(0, selected - 1)
            elif key in ('s', 'S', 'j', getattr(self._curses, 'KEY_DOWN', -1)):
                selected = min(len(rows) - 1, selected + 1)
            elif key == getattr(self._curses, 'KEY_PPAGE', -1):
                selected = max(0, selected - visible)
            elif key == getattr(self._curses, 'KEY_NPAGE', -1):
                selected = min(len(rows) - 1, selected + visible)
            elif key in ('\n', '\r', 'e', 'E',
                         getattr(self._curses, 'KEY_ENTER', -1)):
                recipe, missing = rows[selected]
                if missing:
                    self._log('Còn thiếu nguyên liệu cho món này.')
                    continue
                try:
                    message = cook(self.farm, recipe.key)
                except GameError as error:
                    self._log(error)
                    continue
                self._log(message)
                self._save()

    def _overview(self):
        self.coach.event('map')
        while True:
            height, width = self._screen.getmaxyx()
            if height < 10 or width < 30:
                self._clear()
                self._put(0, 0, f'BẢN ĐỒ LÀNG · ({self.farm.player_x}, {self.farm.player_y})', 'yellow', True)
                for row, line in enumerate(overview_rows(self.farm, max(1, width - 1),
                                                         max(1, height - 5),
                                                         unicode=self.unicode_map), 1):
                    self._put(row, 0, line, 'green')
                dash = '–' if self.unicode_map else '-'
                self._put(height - 3, 0,
                          f'{self.farm.avatar} bạn · 1{dash}5 dân làng · H nhà · M tiệm · B chuồng · : ruộng')
                self._put(height - 2, 0, ', Đồng Hoa · O quảng trường · T rừng · ~ hồ/biển · ^ đồi · v thung lũng · t trà · ◉ mỏ')
                self._put(height - 1, 0, 'M/Q quay lại · R khu vực · J dân làng · G đổi ký tự', 'cyan')
                self._refresh()
            else:
                self._draw_modal_backdrop(height, width)
                rect = tui.panel_geometry(
                    height, width, content_width=width - 8,
                    content_height=height - 4, margin_x=2, margin_y=1,
                    bottom_reserve=0, min_width=30, min_height=10)
                controls = 'M/Q quay lại · R khu vực · J dân làng · G đổi ký tự'
                body = tui.draw_panel(
                    self, rect,
                    title=f'BẢN ĐỒ LÀNG · ({self.farm.player_x}, {self.farm.player_y})',
                    footer=controls, unicode=self.unicode_map, accent='green',
                    title_color='yellow', bounds=(height, width))
                legend_room = 2 if body.height >= 8 else 0
                map_height = max(1, body.height - legend_room - 1)
                rows = overview_rows(self.farm, max(1, body.width - 2),
                                     map_height, unicode=self.unicode_map)
                for row, line in enumerate(rows, 1):
                    self._put(body.y + row, body.x + 1, line, 'green')
                if legend_room:
                    legends = [
                        f'{self.farm.avatar} bạn · 1{"–" if self.unicode_map else "-"}5 dân làng · H nhà · M tiệm · B chuồng · : ruộng',
                        ', Đồng Hoa · O quảng trường · T rừng · ~ hồ/biển · ^ đồi · v thung lũng · t trà · ◉ mỏ',
                    ]
                    for index, line in enumerate(legends[-legend_room:]):
                        self._put(body.y + body.height - legend_room + index,
                                  body.x + 1,
                                  tui.ellipsize(line, max(1, body.width - 2),
                                                unicode=self.unicode_map), 'dim')
                self._refresh()
            key = self._read()
            if key in ('m', 'M', 'q', 'Q', '\x1b', '\n', '\r'):
                return
            if key in ('j', 'J'):
                self._directory()
            if key in ('r', 'R'):
                self._regions()
            if key in ('g', 'G'):
                self._toggle_map_style()

    def _plot(self):
        coordinate = world.target_plot(self.farm)
        if coordinate:
            self._plot_menu(coordinate)

    def _plot_menu(self, coordinate):
        """One plot's action, shared by the map hotkey and the field window."""
        from .artwork import icon_for
        plot = self.farm.plots[coordinate]
        if plot.dead:
            self._action(self.farm.clear, coordinate)
        elif plot.ready:
            self._action(self.farm.harvest, coordinate)
        elif plot.crop:
            self._action(self.farm.water, coordinate)
        else:
            keys = [key for key, crop in CROPS.items()
                    if crop.level <= self.farm.level]
            index = self._choose(
                f"Gieo hạt tại {coordinate}",
                [f"{icon_for('seed:' + key, unicode=self.unicode_map)} "
                 f"{CROPS[key].name} · còn {self.farm.seeds[key]} hạt · "
                 f"{CROPS[key].days} đêm" for key in keys])
            if index is not None:
                self._action(self.farm.plant, coordinate, keys[index])

    def _farm(self):
        """Open the illustrated field board, with a compact list fallback."""
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 18 or width < 54:
            self._farm_list()
        else:
            self._farm_sheet()

    def _farm_summary(self):
        farm = self.farm
        ready = sum(plot.ready for plot in farm.plots.values())
        dead = sum(plot.dead for plot in farm.plots.values())
        empty = sum(not plot.crop for plot in farm.plots.values())
        thirsty = sum(bool(plot.crop) and not plot.dead and not plot.ready
                      and not farm.is_watered(key)
                      for key, plot in farm.plots.items())
        growing = sum(bool(plot.crop) and not plot.dead and not plot.ready
                      for plot in farm.plots.values())
        return ready, dead, empty, thirsty, growing

    def _farm_list(self):
        ready, dead, empty, thirsty, growing = self._farm_summary()
        coordinates = list(self.farm.plots)
        labels = []
        for coordinate in coordinates:
            plot = self.farm.plots[coordinate]
            if plot.dead:
                status = 'héo · cần dọn'
            elif plot.ready:
                status = f'{CROPS[plot.crop].name} · chín'
            elif plot.crop:
                info = CROPS[plot.crop]
                status = (f'{info.name} {plot.growth}/{info.days} · '
                          f'{"đủ nước" if self.farm.is_watered(coordinate) else "cần tưới"}')
            else:
                status = 'trống · gieo hạt'
            labels.append(f'{coordinate} · {status}')
        index = self._choose(
            f'CÁNH ĐỒNG · {self.farm.size}×{self.farm.size}',
            labels,
            [f'{ready} chín · {growing} đang lớn · {thirsty} cần tưới · '
             f'{empty} trống · {dead} héo',
             'Chọn một ô để gieo, tưới, thu hoạch hoặc dọn cây.'],
            close_keys=('f', 'F'))
        if index is not None:
            self._plot_menu(coordinates[index])

    def _plot_card(self, top, left, width, coordinate, selected):
        """Draw one field cell for the field board."""
        g = tui.glyphs(self.unicode_map)
        plot = self.farm.plots[coordinate]
        box_w = max(6, width - 1)
        box_h = 5
        base = 'selected' if selected else 'yellow'
        border = 'selected' if selected else 'dim'
        self._put(top, left, g['tl'] + g['h'] * (box_w - 2) + g['tr'],
                  border)
        for row in range(1, box_h - 1):
            self._put(top + row, left, g['v'] + ' ' * (box_w - 2) + g['v'],
                      border)
        self._put(top + box_h - 1, left,
                  g['bl'] + g['h'] * (box_w - 2) + g['br'], border)
        if plot.dead:
            glyph = '×' if self.unicode_map else 'x'
            status = 'Héo · dọn' if box_w >= 12 else 'Héo'
            color = 'red'
        elif plot.ready:
            glyph = '✦' if self.unicode_map else '*'
            status = 'Chín · thu' if box_w >= 15 else 'Chín'
            color = 'yellow'
        elif plot.crop:
            info = CROPS[plot.crop]
            wet = self.farm.is_watered(coordinate)
            glyph = ('♠' if plot.growth else '╵') if self.unicode_map else (
                't' if plot.growth else "'")
            glyph += '~' if wet else ''
            status = ((f'{plot.growth}/{info.days} · '
                       f'{"đủ nước" if wet else "cần tưới"}')
                      if box_w >= 16 else
                      f'{plot.growth}/{info.days} {"ướt" if wet else "khát"}')
            color = 'cyan' if wet else 'red'
        else:
            glyph = '░' if self.unicode_map else ':'
            if self.farm.is_watered(coordinate):
                glyph += '~'
            status = 'Trống · gieo' if box_w >= 15 else 'Trống'
            color = 'green'
        marker = ('▸ ' if self.unicode_map else '> ') if selected else ''
        self._put(top + 1, left + 1,
                  tui.ellipsize(f'{marker}{coordinate} {glyph}', box_w - 2,
                                unicode=self.unicode_map), base, True)
        name = CROPS[plot.crop].name if plot.crop else 'Đất trống'
        self._put(top + 2, left + 1,
                  tui.ellipsize(name, box_w - 2, unicode=self.unicode_map),
                  color if selected else '')
        self._put(top + 3, left + 1,
                  tui.ellipsize(status, box_w - 2, unicode=self.unicode_map),
                  'selected' if selected else 'dim')

    def _farm_sheet(self):
        selected = 0
        offset = 0
        while True:
            height, width = self._screen.getmaxyx()
            if height < 18 or width < 54:
                self._farm_list()
                return
            self._draw_modal_backdrop(height, width)
            g = tui.glyphs(self.unicode_map)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 92),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=54, min_height=16)
            nav = '↑↓/←→' if self.unicode_map else 'W/S/A/D'
            controls = (f'{nav} chọn ô · Enter chăm · PgUp/PgDn cuộn · F/Esc đóng'
                        if width >= 68 else
                        f'{nav} chọn · Enter · PgUp/Dn · F/Esc')
            body = tui.draw_panel(
                self, rect,
                title=(f'CÁNH ĐỒNG · {self.farm.size}'
                       f'{"×" if self.unicode_map else "x"}{self.farm.size} · '
                       f'{self.farm.level} cấp'),
                footer=controls if height >= 22 else '',
                unicode=self.unicode_map, accent='green', title_color='yellow',
                bounds=(height, width))
            ready, dead, empty, thirsty, growing = self._farm_summary()
            thirsty_label = 'khát' if body.width < 58 else 'cần tưới'
            self._put(body.y, body.x + 1,
                      tui.ellipsize(
                          f'{ready} chín · {growing} lớn · {thirsty} {thirsty_label} · '
                          f'{empty} trống · {dead} héo',
                          max(1, body.width - 2), unicode=self.unicode_map),
                      'cyan')
            coordinates = list(self.farm.plots)
            cols = min(self.farm.size,
                       max(2, (body.width - 2) // 12))
            cell_w = max(9, (body.width - 2) // cols)
            cell_h = 5
            rows = max(1, (body.height - 2) // cell_h)
            per_page = cols * rows
            offset = max(0, min(offset, max(0, len(coordinates) - per_page)))
            if selected < offset:
                offset = selected - selected % cols
            elif selected >= offset + per_page:
                offset = (selected // cols) * cols
            for index in range(offset, min(len(coordinates), offset + per_page)):
                slot = index - offset
                row, col = divmod(slot, cols)
                top = body.y + 2 + row * cell_h
                left = body.x + 1 + col * cell_w
                if top + cell_h > body.y + body.height:
                    break
                self._plot_card(top, left, cell_w, coordinates[index],
                                index == selected)
            self._draw_status_bar(height, width, controls)
            self._refresh()
            key_name = self._read()
            if key_name in ('f', 'F', 'q', 'Q', '\x1b'):
                return
            if key_name in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                selected = max(0, selected - cols)
            elif key_name in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                selected = min(len(coordinates) - 1, selected + cols)
            elif key_name in ('a', 'A', getattr(self._curses, 'KEY_LEFT', -1)):
                selected = max(0, selected - 1)
            elif key_name in ('d', 'D', getattr(self._curses, 'KEY_RIGHT', -1)):
                selected = min(len(coordinates) - 1, selected + 1)
            elif key_name == getattr(self._curses, 'KEY_PPAGE', -1):
                selected = max(0, selected - per_page)
            elif key_name == getattr(self._curses, 'KEY_NPAGE', -1):
                selected = min(len(coordinates) - 1, selected + per_page)
            elif key_name in ('\n', '\r', 'e', 'E',
                              getattr(self._curses, 'KEY_ENTER', -1)):
                self._plot_menu(coordinates[selected])

    def _inventory(self, chest):
        """Open the illustrated bag, with a compact list fallback."""
        if not chest:
            self.coach.event('bag')
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 20 or width < 64:
            self._inventory_list(chest)
        else:
            self._inventory_sheet(chest)

    def _inventory_list(self, chest):
        from .inventory import inventory_rows, deposit_all
        from .artwork import icon_for, symbol
        while True:
            rows = inventory_rows(self.farm)
            visible = [row for row in rows if row[2] or row[3]] or rows
            sellable = sum(sale_price(self.farm, key) * bag
                           for key, _, bag, _ in rows
                           if sale_price(self.farm, key))
            labels = []
            for key, name, bag, stored in visible:
                price = sale_price(self.farm, key)
                labels.append(
                    f'{icon_for(key, unicode=self.unicode_map)} {name}'
                    f' · túi {bag} · rương {stored}'
                    + (f' · bán {price} xu' if price else ' · không bán'))
            if chest:
                labels.append(symbol('bag', unicode=self.unicode_map)
                              + ' Gửi tất cả đồ trong túi vào rương')
            details = [
                f'{symbol("coin", unicode=self.unicode_map)} {self.farm.coins} xu'
                f' · túi bán được {sellable} xu · {len(visible)} loại đang có',
                ('Chọn một món để gửi vào rương hoặc rút ra túi. '
                 'Đồ trong rương luôn được giữ khi bán hàng.'
                 if chest else
                 'Mang sản phẩm ra chợ để bán; cất đồ quý vào rương trong nhà.'),
            ]
            index = self._choose(
                'RƯƠNG · gửi / rút' if chest else 'TÚI ĐỒ · thu hoạch, cá và vật phẩm',
                labels, details, close_keys=('i', 'I'))
            if index is None or not chest:
                return
            if index == len(visible):
                self._action(deposit_all, self.farm)
                continue
            key, name, bag, stored = visible[index]
            self._inventory_transfer(key, name, bag, stored)

    def _inventory_transfer(self, key, name, bag, stored):
        """Ask direction and quantity for one inventory row."""
        from .inventory import transfer_item
        from .artwork import icon_for
        if not bag and not stored:
            return
        if not bag:
            direction = 1
        elif not stored:
            direction = 0
        else:
            direction = self._choose(
                name, [f'Gửi từ túi ({bag})', f'Rút từ rương ({stored})'],
                [f'{icon_for(key, unicode=self.unicode_map)} {name} · '
                 f'giá bán {sale_price(self.farm, key)} xu/cái'
                 if sale_price(self.farm, key) else
                 f'{icon_for(key, unicode=self.unicode_map)} {name} · '
                 'vật phẩm dùng trong nông trại'],
                close_keys=('i', 'I'))
            if direction is None:
                return
        count = self._number('Gửi ' + name if direction == 0 else 'Rút ' + name,
                             bag if direction == 0 else stored)
        if count is not None:
            self._action(transfer_item, self.farm, key, count,
                         'deposit' if direction == 0 else 'withdraw')

    @staticmethod
    def _inventory_section_icon(section, unicode_map):
        rich, plain = {
            'all': ('▤', 'b'), 'seed': ('❦', '+'), 'crop': ('❧', '%'),
            'fish': ('◈', 'o'), 'other': ('▥', 'o'),
        }.get(section, ('▤', 'b'))
        return rich if unicode_map else plain

    def _inventory_note(self, key):
        """Short useful description for the selected inventory item."""
        from .catalog import CROPS, FISH_TYPES
        if key.startswith('seed:'):
            crop = CROPS[key.split(':', 1)[1]]
            return (f'Gieo ở ruộng · chín sau {crop.days} đêm · '
                    f'mua {crop.seed_price} xu.')
        if key.startswith('crop:'):
            crop = CROPS[key.split(':', 1)[1]]
            return f'Nông sản · bán {crop.sell_price} xu/cái · +{crop.xp} XP khi thu hoạch.'
        if key in FISH_TYPES:
            fish = FISH_TYPES[key]
            return (f'{fish.rarity} · {fish.points} điểm sưu tầm. {fish.hint}')
        notes = {
            'feed': 'Cho một vật nuôi ăn trong ngày.',
            'wood': 'Vật liệu kiếm được khi làm thuê trong làng.',
            'egg': 'Sản phẩm chăn nuôi, bán ở chợ làng.',
            'milk': 'Sản phẩm chăn nuôi, bán ở chợ làng.',
            'wool': 'Sản phẩm chăn nuôi, bán ở chợ làng.',
            'fur': 'Lông thỏ mềm, bán ở chợ làng.',
            'truffle': 'Nấm củ heo tìm được, nguyên liệu quý.',
            'da': 'Đá đào từ mỏ; nguyên liệu cơ bản cho mọi bậc rèn.',
            'quang_dong': 'Quặng đồng, dùng rèn cuốc/kiếm/giáp bậc đầu.',
            'quang_sat': 'Quặng sắt, cần cho trang bị bậc trung và cao.',
            'quang_vang': 'Quặng vàng quý, dùng rèn trang bị bậc cao.',
            'kim_cuong': 'Tinh thể hang sâu, chỉ rơi ở tầng sâu hoặc tảng đá hiếm.',
            'thuoc': 'Uống trong Hang Sâu để hồi 12 máu.',
        }
        from .cooking import RECIPES
        if key in RECIPES:
            recipe = RECIPES[key]
            return (f'Món nấu tại bếp · hồi {recipe.energy} năng lượng · '
                    f'+{recipe.xp} XP khi nấu · bán {ITEMS[key].sell_price} xu.')
        return notes.get(key, 'Vật phẩm nông trại.')

    def _inventory_sheet(self, chest):
        """Two-column bag with category tabs, illustrations and item details."""
        from .inventory import (SECTION_NAMES, SECTION_ORDER, deposit_all,
                                inventory_rows, item_section, section_rows)
        from .artwork import art_for, icon_for, symbol
        section = 'all'
        selected = 0
        offset = 0
        while True:
            height, width = self._screen.getmaxyx()
            if height < 20 or width < 64:
                self._inventory_list(chest)
                return
            rows = inventory_rows(self.farm)
            present = [row for row in rows if row[2] or row[3]]
            counts = {name: len(section_rows(present, name))
                      for name in SECTION_ORDER}
            visible = section_rows(present, section)
            if visible:
                selected = max(0, min(selected, len(visible) - 1))
            else:
                selected = 0
                offset = 0
            self._draw_modal_backdrop(height, width)
            g = tui.glyphs(self.unicode_map)
            nav = '↑↓' if self.unicode_map else 'W/S'
            tab_range = '1–5' if self.unicode_map else '1-5'
            title = ('RƯƠNG · GỬI / RÚT' if chest else 'TÚI ĐỒ')
            if chest:
                controls = (f'{nav} chọn · PgUp/Dn · Tab/{tab_range} lọc · '
                            'Enter gửi/rút · G gửi tất cả · I/Esc đóng'
                            if width >= 80 else
                            f'{nav} · PgUp/Dn · Tab lọc · Enter · G · I/Esc')
            else:
                controls = (f'{nav} chọn · PgUp/Dn · Tab/{tab_range} lọc · I/Esc đóng'
                            if width >= 48 else
                            f'{nav} · PgUp/Dn · Tab lọc · I/Esc')
            body = tui.draw_panel(
                self, rect=tui.panel_geometry(
                    height, width, content_width=min(width - 2, 92),
                    content_height=height - 3, margin_x=1, margin_y=1,
                    bottom_reserve=2, min_width=64, min_height=18),
                title=f'{title} · {len(present)} loại',
                footer=controls if height >= 22 else '',
                unicode=self.unicode_map, accent='cyan', title_color='yellow',
                bounds=(height, width))
            bag_total = sum(row[2] for row in present)
            chest_total = sum(row[3] for row in present)
            sell_bag = sum(sale_price(self.farm, key) * bag
                           for key, _, bag, _ in present
                           if sale_price(self.farm, key))
            summary = (f'{symbol("coin", unicode=self.unicode_map)} '
                       f'{self.farm.coins} xu · túi {bag_total} món · '
                       f'rương {chest_total} món · bán được {sell_bag} xu')
            self._put(body.y, body.x + 1,
                      tui.ellipsize(summary, max(1, body.width - 2),
                                    unicode=self.unicode_map), 'cyan')

            # Category tabs, with counts so empty sections are obvious.
            tab_x = body.x + 1
            tab_limit = body.x + body.width - 1
            for index, name in enumerate(SECTION_ORDER):
                if tab_x >= tab_limit:
                    break
                icon = self._inventory_section_icon(name, self.unicode_map)
                compact_tabs = body.width < 68
                section_label = (SECTION_NAMES[name] if not compact_tabs else
                                 {'all': 'Tất cả', 'seed': 'Hạt', 'crop': 'N.Sản',
                                  'fish': 'Cá', 'other': 'Khác'}[name])
                label = f'{index + 1}{icon} {section_label} {counts[name]}'
                label = tui.ellipsize(label, max(1, tab_limit - tab_x),
                                      unicode=self.unicode_map)
                self._put(body.y + 1, tab_x, label,
                          'selected' if name == section else 'cyan',
                          name == section)
                tab_x += tui.cells(label) + 1

            list_top = body.y + 2
            list_bottom = body.y + body.height - 1
            left_w = min(40, max(32, body.width * 2 // 5))
            available = max(1, list_bottom - list_top)
            offset = max(0, min(offset, max(0, len(visible) - available)))
            if selected < offset:
                offset = selected
            elif selected >= offset + available:
                offset = selected - available + 1
            sep_x = body.x + left_w
            for row in range(list_top, list_bottom):
                self._put(row, sep_x, g['v'], 'dim')
            for slot, (key, name, bag, stored) in enumerate(
                    visible[offset:offset + available]):
                row_y = list_top + slot
                index = offset + slot
                is_selected = index == selected
                marker = ('▸ ' if self.unicode_map else '> ') if is_selected else '  '
                label = (f'{marker}{icon_for(key, unicode=self.unicode_map)} '
                         f'{name} · {bag}/{stored}')
                if is_selected:
                    self._put(row_y, body.x + 1,
                              ' ' * max(1, left_w - 1), 'selected')
                self._put(row_y, body.x + 1,
                          tui.ellipsize(label, max(1, left_w - 2),
                                        unicode=self.unicode_map),
                          'selected' if is_selected else
                          ('dim' if not bag and stored else ''),
                          is_selected)
            if not visible:
                empty_text = ('Túi và rương đang trống.' if not present
                              else f'Mục {SECTION_NAMES[section]} chưa có vật phẩm.')
                self._put(list_top, body.x + 2,
                          tui.ellipsize(empty_text, max(1, left_w - 3),
                                        unicode=self.unicode_map), 'dim')

            detail_x = sep_x + 2
            detail_w = max(10, body.right - detail_x + 1)
            if visible:
                key, name, bag, stored = visible[selected]
                art = art_for(key, unicode=self.unicode_map)
                art_top = list_top + max(0, (4 - len(art)) // 2)
                for row, line in enumerate(art):
                    self._put(art_top + row, detail_x + 1,
                              tui.pad(line.center(max(1, detail_w - 2)),
                                      max(1, detail_w - 2)), 'magenta')
                price = sale_price(self.farm, key)
                info_top = art_top + len(art) + 1
                info = [
                    (name, 'yellow', True),
                    (f'{SECTION_NAMES[item_section(key)]} · '
                     f'{price} xu/cái' if price else
                     f'{SECTION_NAMES[item_section(key)]} · không bán',
                     'cyan', False),
                    (f'Túi {bag} · Rương {stored}', 'white', False),
                ]
                for row, (line, color, bold) in enumerate(info):
                    if info_top + row >= list_bottom:
                        break
                    self._put(info_top + row, detail_x,
                              tui.ellipsize(line, detail_w,
                                            unicode=self.unicode_map), color, bold)
                note_y = info_top + len(info) + 1
                for offset_line, line in enumerate(
                        wrap_cells(self._inventory_note(key),
                                   max(2, detail_w - 1))[:3]):
                    if note_y + offset_line >= list_bottom:
                        break
                    self._put(note_y + offset_line, detail_x, line, 'dim')
            else:
                empty_detail = ('Chưa có vật phẩm trong túi hoặc rương.'
                                if not present else
                                f'{SECTION_NAMES[section]} đang trống.')
                self._put(list_top + 1, detail_x,
                          tui.ellipsize(empty_detail, detail_w,
                                        unicode=self.unicode_map), 'dim')
            self._draw_status_bar(height, width, controls)
            self._refresh()
            key_name = self._read()
            if key_name in ('i', 'I', 'q', 'Q', '\x1b'):
                return
            if key_name == '\t' or (isinstance(key_name, str)
                                    and key_name in '12345'):
                if key_name == '\t':
                    index = (SECTION_ORDER.index(section) + 1) % len(SECTION_ORDER)
                else:
                    index = int(key_name) - 1
                section = SECTION_ORDER[index]
                selected = 0
                offset = 0
                continue
            if key_name in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                selected = max(0, selected - 1)
            elif key_name in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                selected = min(max(0, len(visible) - 1), selected + 1)
            elif key_name == getattr(self._curses, 'KEY_PPAGE', -1):
                selected = max(0, selected - available)
            elif key_name == getattr(self._curses, 'KEY_NPAGE', -1):
                selected = min(max(0, len(visible) - 1), selected + available)
            elif key_name in ('\n', '\r', 'e', 'E',
                              getattr(self._curses, 'KEY_ENTER', -1)):
                if chest and visible:
                    _, name, bag, stored = visible[selected]
                    self._inventory_transfer(visible[selected][0], name,
                                             bag, stored)
            elif key_name in ('g', 'G') and chest:
                self._action(deposit_all, self.farm)

    def _shop(self):
        """Open the illustrated shop; tiny terminals keep a readable list."""
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 18 or width < 54:
            self._shop_list()
        else:
            self._shop_grid()

    def _shop_list(self):
        from .shop import shop_categories
        from .artwork import icon_for
        categories = list(shop_categories(self.farm, unicode=self.unicode_map))
        while True:
            labels = [f'{category.icon} {category.name} · {len(category.entries)} mục'
                      for category in categories]
            index = self._choose(f'CHỢ LÀNG · {self.farm.coins} xu', labels,
                                 [category.hint for category in categories],
                                 close_keys=('m', 'M'))
            if index is None:
                return
            category = categories[index]
            while True:
                labels = [f'{icon_for(entry.art_key, unicode=self.unicode_map)} {entry.name}'
                          f' · {entry.price} xu · {entry.meta}'
                          for entry in category.entries]
                choice = self._choose(
                    f'{category.name.upper()} · {self.farm.coins} xu', labels,
                    [entry.detail for entry in category.entries],
                    close_keys=('m', 'M'))
                if choice is None:
                    break
                self._shop_take(category.entries[choice])
                categories = list(shop_categories(self.farm, unicode=self.unicode_map))
                category = categories[index]

    def _shop_quantity(self, entry):
        from .shop import sellable_rows
        if entry.action == 'buy_seed':
            maximum = (self.farm.coins // entry.price) if entry.price else 0
            if maximum < 1:
                self._log(f'Cần {entry.price} xu để mua {entry.name}.')
                return False
            return self._number(f'Mua {entry.name}', maximum)
        if entry.action == 'buy_feed':
            if entry.payload != '1':
                return int(entry.payload)
            maximum = (self.farm.coins // entry.price) if entry.price else 0
            if maximum < 1:
                self._log(f'Cần {entry.price} xu để mua thức ăn.')
                return False
            return self._number('Mua thức ăn chăn nuôi', maximum)
        if entry.action == 'buy_item':
            maximum = (self.farm.coins // entry.price) if entry.price else 0
            if maximum < 1:
                self._log(f'Cần {entry.price} xu để mua {entry.name}.')
                return False
            return self._number(f'Mua {entry.name}', maximum)
        if entry.action == 'sell_item':
            maximum = next((quantity for key, quantity, _ in sellable_rows(self.farm)
                            if key == entry.payload), 0)
            return self._number(f'Bán {entry.name}', maximum)
        return None

    def _shop_take(self, entry):
        """Run one card, asking for only the input that card actually needs."""
        from .shop import perform
        from .artwork import art_for
        if entry.disabled:
            self._log(f'{entry.name}: đã đạt mức tối đa.'
                      if entry.action == 'upgrade' else entry.detail)
            return False
        if entry.locked:
            self._log(f'{entry.name} chưa mở ở cấp hiện tại.')
            return False
        quantity = self._shop_quantity(entry)
        if quantity is False:
            return False
        if entry.action in ('buy_seed', 'buy_feed', 'buy_item', 'sell_item') and quantity is None:
            return False
        if entry.action in ('buy_animal', 'upgrade', 'sell_all', 'seed_bundle'):
            price_line = (f'{entry.price} xu · ' if entry.price else '')
            confirmed = self._choose(
                entry.name, ['Xác nhận', 'Quay lại'],
                [price_line + entry.detail],
                art=art_for(entry.art_key, unicode=self.unicode_map))
            if confirmed != 0:
                return False
        return self._action(perform, self.farm, entry, quantity)

    def _shop_grid(self, category_key=None):
        from .shop import CATEGORY_ORDER, shop_categories
        category_key = category_key or CATEGORY_ORDER[0]
        selected = 0
        categories = list(shop_categories(self.farm, unicode=self.unicode_map))
        while True:
            categories = list(shop_categories(self.farm, unicode=self.unicode_map))
            category = next((item for item in categories if item.key == category_key),
                            categories[0])
            category_key = category.key
            entries = category.entries
            selected = max(0, min(selected, len(entries) - 1)) if entries else 0
            height, width = self._screen.getmaxyx()
            if height < 18 or width < 54:
                self._shop_list()
                return
            self._draw_modal_backdrop(height, width)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 92),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=54, min_height=16)
            usable = max(1, rect.width - 4)
            cols = max(1, min(3, usable // 24))
            card_w = usable // cols
            card_h = 7
            rows = max(1, (rect.height - 5) // card_h)
            capacity = max(1, cols * rows)
            page = (selected // capacity) * capacity
            shown_end = min(len(entries), page + capacity)
            focus = entries[selected] if entries else None
            dash = '–' if self.unicode_map else '-'
            footer = (f'{page + 1}{dash}{shown_end}/{len(entries)}  ·  '
                      f'{focus.detail if focus else category.hint}')
            body = tui.draw_panel(
                self, rect, title=f'CHỢ LÀNG · {self.farm.coins} xu · {category.name}',
                footer=footer, unicode=self.unicode_map, accent='yellow',
                title_color='yellow', bounds=(height, width))

            # Category tabs, scrolled horizontally around the active one.
            available = max(4, body.width - 2)
            pieces = [f'{index + 1}{item.icon} {item.name}'
                      for index, item in enumerate(categories)]
            active = CATEGORY_ORDER.index(category_key)
            def tab_span(items):
                return sum(tui.cells(piece) + 2 for piece in items) - 2
            start = 0
            while start < active and tab_span(pieces[start:]) > available:
                start += 1
            cursor = body.x + 1
            limit = body.x + body.width - 1
            left_arrow = '‹' if self.unicode_map else '<'
            right_arrow = '›' if self.unicode_map else '>'
            if start > 0:
                self._put(body.y, cursor, left_arrow, 'dim')
                cursor += 2
            for index in range(start, len(categories)):
                label = f' {pieces[index]} '
                reserve = 2 if index + 1 < len(categories) else 0
                if cursor + tui.cells(label) + reserve > limit:
                    if index < len(categories) and cursor < limit:
                        self._put(body.y, max(cursor, limit - 1), right_arrow, 'dim')
                    break
                color = 'selected' if index == active else 'cyan'
                self._put(body.y, cursor, label, color, index == active)
                cursor += tui.cells(label) + 1

            for slot, entry in enumerate(entries[page:page + capacity]):
                col, row = slot % cols, slot // cols
                x = body.x + 1 + col * card_w
                y = body.y + 2 + row * card_h
                self._shop_card(x, y, card_w, card_h, entry,
                                page + slot == selected)
            if not entries:
                self._put(body.y + 3, body.x + 2, 'Quầy này đang trống.', 'dim')
            nav = '←→/↑↓' if self.unicode_map else 'A/D/W/S'
            quick = '1–5' if self.unicode_map else '1-5'
            controls = (f'{nav} chọn · Tab hoặc {quick} đổi quầy · Enter dùng · Esc ra'
                        if width >= 68 else f'{nav} · Tab quầy · Enter · Esc')
            self._draw_status_bar(height, width, controls)
            self._refresh()

            key = self._read()
            if key in ('q', 'Q', 'm', 'M', '\x1b'):
                return
            if key in ('\t', ']', '.'):
                index = (CATEGORY_ORDER.index(category_key) + 1) % len(CATEGORY_ORDER)
                category_key = CATEGORY_ORDER[index]
                selected = 0
                continue
            if key in ('[', ',', getattr(self._curses, 'KEY_BTAB', -1)):
                index = (CATEGORY_ORDER.index(category_key) - 1) % len(CATEGORY_ORDER)
                category_key = CATEGORY_ORDER[index]
                selected = 0
                continue
            if isinstance(key, str) and key in '12345':
                category_key = CATEGORY_ORDER[int(key) - 1]
                selected = 0
                continue
            if key in ('a', 'A', getattr(self._curses, 'KEY_LEFT', -1)):
                selected = max(0, selected - 1)
            elif key in ('d', 'D', getattr(self._curses, 'KEY_RIGHT', -1)):
                selected = min(len(entries) - 1, selected + 1)
            elif key in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                selected = max(0, selected - cols)
            elif key in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                selected = min(len(entries) - 1, selected + cols)
            elif key == getattr(self._curses, 'KEY_PPAGE', -1):
                selected = max(0, selected - capacity)
            elif key == getattr(self._curses, 'KEY_NPAGE', -1):
                selected = min(len(entries) - 1, selected + capacity)
            elif key in ('\n', '\r', getattr(self._curses, 'KEY_ENTER', -1)):
                if entries:
                    self._shop_take(entries[selected])
                    # The live catalogue may have shrunk after selling.
                    categories = list(shop_categories(self.farm, unicode=self.unicode_map))
                    refreshed = next((item for item in categories
                                      if item.key == category_key), categories[0])
                    selected = min(selected, max(0, len(refreshed.entries) - 1))

    def _shop_card(self, x, y, width, height, entry, selected):
        from .artwork import art_for
        g = tui.glyphs(self.unicode_map)
        inner = width - 2
        border = 'yellow' if selected else 'shadow'
        fill = 'selected' if selected else ''
        name_color = 'selected' if selected else 'yellow'
        meta_color = 'selected' if selected else 'cyan'
        art_color = 'selected' if selected else ('dim' if entry.disabled else 'green')
        self._put(y, x, g['tl'] + g['h'] * inner + g['tr'], border, selected)
        for row in range(1, height - 1):
            self._put(y + row, x, g['v'] + ' ' * inner + g['v'], border, selected)
            if selected:
                self._put(y + row, x, ' ' * width, fill)
                self._put(y + row, x, g['v'], border, True)
                self._put(y + row, x + width - 1, g['v'], border, True)
        self._put(y + height - 1, x, g['bl'] + g['h'] * inner + g['br'], border,
                  selected)
        art = art_for(entry.art_key, unicode=self.unicode_map)[:3]
        art_top = 1 + max(0, (3 - len(art)) // 2)
        for row, line in enumerate(art):
            self._put(y + art_top + row, x + 1,
                      tui.pad(line.center(inner), inner), art_color, selected)
        self._put(y + 4, x + 1, tui.pad(' ' + tui.ellipsize(
            entry.name, max(1, inner - 2), unicode=self.unicode_map), inner),
            name_color, selected)
        price_text = {
            'sell_all': (f'Tổng {entry.price} xu' if entry.price else 'Chưa có gì'),
        }.get(entry.action, f'{entry.price} xu' if entry.price else '')
        meta = (f'{price_text} · {entry.meta}' if price_text else entry.meta)
        prefix = ('▸ ' if self.unicode_map else '> ') if selected else '  '
        self._put(y + 5, x + 1, tui.pad(
            prefix + tui.ellipsize(meta, max(1, inner - 3), unicode=self.unicode_map),
            inner), meta_color, selected)

    def _upgrades(self):
        """Compatibility entry point: open the shop on its upgrade counter."""
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 18 or width < 54:
            from .shop import shop_categories
            categories = list(shop_categories(self.farm, unicode=self.unicode_map))
            category = next(item for item in categories if item.key == 'upgrades')
            labels = [f'{entry.name} · {entry.meta} · {entry.detail}'
                      for entry in category.entries]
            index = self._choose('NÂNG CẤP', labels)
            if index is not None:
                self._shop_take(category.entries[index])
            return
        self._shop_grid('upgrades')

    def _forge(self):
        """The mine forge: spend ore to raise pickaxe, sword or armour."""
        from .artwork import art_for
        from .catalog import GEAR, ITEMS
        from .forge import forge, missing_for, recipe_for, recipe_label
        from .mining import mine_summary
        keys = list(GEAR)
        while True:
            labels, details = [], []
            for key in keys:
                info = GEAR[key]
                level = self.farm.gear.get(key, 0)
                recipe = recipe_for(self.farm, key)
                labels.append(f'{info.icon} {info.name} · bậc {level}/5'
                              + ('' if recipe is None else f' · {recipe_label(recipe)}'))
                missing = missing_for(self.farm, key, recipe)
                if recipe is None:
                    state = 'Đã rèn tối đa.'
                elif missing:
                    state = 'Thiếu: ' + ', '.join(
                        f'{amount} {"xu" if item == "coins" else ITEMS[item].name}'
                        for item, amount in missing.items())
                else:
                    state = 'Sẵn sàng rèn.'
                details.append(f'{info.description} {info.effect} {state}')
            available, total = mine_summary(self.farm)
            index = self._choose(
                f'LÒ RÈN · {self.farm.coins} xu · mỏ còn {available}/{total} tảng',
                labels, details, art=art_for('forge', unicode=self.unicode_map),
                close_keys=('f', 'F'))
            if index is None:
                return
            self._action(forge, self.farm, keys[index])

    def _dungeon(self):
        """Turn-based Hang Sâu encounter UI shared by every floor."""
        from .artwork import art_for
        from .dungeon import (MAX_DEPTH, advance, flee, player_attack,
                              start_run, status_lines, use_potion)
        try:
            run = start_run(self.farm)
        except GameError as error:
            self._log(error)
            return
        self._log(f'Bạn bước vào Hang Sâu. Kiếm bậc '
                  f'{self.farm.gear.get("sword", 0)}/5, máu {self.farm.hp}/{self.farm.max_hp}.')
        self._save()
        while True:
            height, width = self._screen.getmaxyx()
            lines = status_lines(self.farm, run, unicode=self.unicode_map)
            if run.phase == 'battle':
                controls = '1/Enter tấn công · 2 uống thuốc · 3 rút lui · Q đóng'
            elif run.phase == 'floor':
                controls = '1/Enter xuống tầng · 2/Q trở về'
            else:
                controls = 'Enter/Q đóng · ngủ để hồi máu trước chuyến sau'
            if height < 12 or width < 36:
                self._clear()
                for row, line in enumerate(lines[:height - 4]):
                    self._put(row, 0, tui.ellipsize(line, width,
                                                  unicode=self.unicode_map),
                              'yellow' if row == 0 else 'cyan')
                self._put(height - 3, 0, tui.ellipsize(controls, width,
                                                      unicode=self.unicode_map), 'cyan')
                if run.log:
                    self._put(height - 2, 0,
                              tui.ellipsize(run.log[-1], width,
                                            unicode=self.unicode_map), 'green')
                self._refresh()
            else:
                self._draw_modal_backdrop(height, width)
                rect = tui.panel_geometry(
                    height, width, content_width=min(width - 2, 74),
                    content_height=min(height - 3, 20), margin_x=1, margin_y=1,
                    bottom_reserve=2, min_width=44, min_height=12)
                body = tui.draw_panel(
                    self, rect,
                    title=f'HANG SÂU · TẦNG {run.depth}/{MAX_DEPTH}',
                    footer=controls if height >= 18 else '',
                    unicode=self.unicode_map, accent='red', title_color='yellow',
                    bounds=(height, width))
                self._put(body.y, body.x + 1,
                          tui.ellipsize(lines[0], max(1, body.width - 2),
                                        unicode=self.unicode_map), 'yellow', True)
                enemy = run.current()
                art_w = 15 if body.width >= 58 else 0
                if enemy is not None and run.phase == 'battle' and art_w:
                    art = art_for('monster:' + enemy.key, unicode=self.unicode_map)
                    for row, line in enumerate(art[:4]):
                        self._put(body.y + 2 + row, body.x + 1, line, 'red')
                text_x = body.x + (art_w + 1 if art_w else 1)
                text_w = max(8, body.right - text_x)
                for row, line in enumerate(lines[1:], 2):
                    if row >= body.y + body.height - 4:
                        break
                    self._put(row, text_x,
                              tui.ellipsize(line, text_w,
                                            unicode=self.unicode_map),
                              'cyan' if row == 2 else 'dim')
                log_top = body.y + body.height - 5
                for row, line in enumerate(run.log[-3:]):
                    if log_top + row >= body.y + body.height - 1:
                        break
                    self._put(log_top + row, body.x + 1,
                              tui.ellipsize(line, max(1, body.width - 2),
                                            unicode=self.unicode_map), 'green')
                self._draw_status_bar(height, width, controls)
                self._refresh()
            key = self._read()
            if run.phase == 'battle':
                if key in ('1', ' ', 'e', 'E', '\n', '\r',
                           getattr(self._curses, 'KEY_ENTER', -1)):
                    self._action(player_attack, self.farm, run)
                elif key == '2':
                    self._action(use_potion, self.farm, run)
                elif key in ('3', 'q', 'Q', '\x1b'):
                    self._log(flee(self.farm, run))
                    self._save()
                    return
                elif key == 't':
                    self._help()
            elif run.phase == 'floor':
                if key in ('1', ' ', 'e', 'E', '\n', '\r',
                           getattr(self._curses, 'KEY_ENTER', -1)):
                    self._action(advance, self.farm, run)
                elif key in ('2', 'q', 'Q', '\x1b'):
                    return
            else:
                if run.phase == 'done':
                    self._reader('HANG SÂU · CHINH PHỤC',
                                 f'Bạn đã phá đảo Hang Sâu {MAX_DEPTH} tầng!\n\n'
                                 f'Kỷ lục: tầng {self.farm.dungeon_best}/{MAX_DEPTH}\n'
                                 f'Tổng nhận: {run.total_coins} xu, {run.total_xp} XP.\n\n'
                                 + '\n'.join(run.log[-8:]))
                return

    def _barn(self):
        """Open the livestock board, grouped into level-gated zones."""
        height, width = self._screen.getmaxyx() if self._screen else (0, 0)
        if height < 18 or width < 58:
            self._barn_list()
        else:
            self._barn_sheet()

    def _barn_list(self):
        from .animals import (ANIMAL_TYPES, buy_animal, feed_animals,
                              pet_animal, collect_products, buy_feed,
                              product_name, zone_for, zone_unlocked)
        from .artwork import icon_for
        while True:
            animals = self.farm.animals
            details = [f"{icon_for(animal.kind, unicode=self.unicode_map)} {animal.name}"
                       f" · {ANIMAL_TYPES[animal.kind].name}"
                       f" · {zone_for(animal.kind).name}"
                       f" · {'đã ăn' if animal.fed else 'ĐÓI'}"
                       f" · {animal.age} ngày · thân {animal.friendship}/5"
                       f" · {animal.produce} {product_name(animal.kind)}"
                       for animal in animals]
            def mark(rich, plain):
                return rich if self.unicode_map else plain
            labels = [f"{mark('▤', 'f')} Cho cả đàn ăn",
                      f"{mark('◇', 'o')} Thu sản phẩm",
                      f"{mark('▴', 'a')} Mua vật nuôi",
                      f"{mark('▤', 'f')} Mua thức ăn · {ITEMS['feed'].buy_price} xu/phần",
                      f"{mark('⌂', '^')} Nâng chuồng · 280 xu"]
            labels += [mark('♥', '*') + " Vuốt ve " + animal.name
                       + (" (đã vuốt hôm nay)" if animal.petted else "")
                       for animal in animals]
            index = self._choose(
                f"CHUỒNG · {len(animals)}/{self.farm.barn_capacity} chỗ · "
                f"{self.farm.items['feed']} thức ăn", labels, details,
                close_keys=('b', 'B'))
            if index is None:
                return
            if index == 0:
                self._action(feed_animals, self.farm)
            elif index == 1:
                self._action(collect_products, self.farm)
            elif index == 2:
                keys = list(ANIMAL_TYPES)
                choice = self._choose(
                    "Mua con non",
                    [f"{icon_for(key, unicode=self.unicode_map)} {ANIMAL_TYPES[key].name}"
                     f" · {ANIMAL_TYPES[key].price} xu"
                     + ('' if zone_unlocked(self.farm, zone_for(key))
                        else f' · mở cấp {zone_for(key).level}')
                     for key in keys],
                    [f"{ANIMAL_TYPES[key].name}: {zone_for(key).name}, trưởng thành sau "
                     f"{ANIMAL_TYPES[key].mature_days} ngày, cho "
                     f"{product_name(key).lower()} mỗi "
                     f"{ANIMAL_TYPES[key].interval} ngày."
                     for key in keys],
                    close_keys=('b', 'B'))
                if choice is not None:
                    self._action(buy_animal, self.farm, keys[choice])
            elif index == 3:
                count = self._number("Mua thức ăn chăn nuôi")
                if count is not None:
                    self._action(buy_feed, self.farm, count)
            elif index == 4:
                self._action(self.farm.upgrade, "barn")
            else:
                self._action(pet_animal, self.farm, index - 5)

    def _barn_sheet(self):
        from .animals import (ANIMAL_TYPES, ANIMAL_ZONES, buy_animal, buy_feed,
                              collect_products, feed_animals, pet_animal,
                              product_name, zone_animals)
        from .artwork import art_for, hearts, icon_for
        zones = list(ANIMAL_ZONES.values())
        zone_index = next((index for index, zone in enumerate(zones)
                           if zone_animals(self.farm, zone)), 0)
        selected = 0
        offset = 0
        while True:
            height, width = self._screen.getmaxyx()
            if height < 18 or width < 58:
                self._barn_list()
                return
            self._draw_modal_backdrop(height, width)
            g = tui.glyphs(self.unicode_map)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 90),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=58, min_height=16)
            nav = '↑↓' if self.unicode_map else 'W/S'
            controls = (f'{nav} chọn · Tab/1–3 khu · Enter vuốt · A/C/M/F/U · Esc đóng'
                        if width >= 72 else
                        f'{nav} · Tab khu · Enter · A/C/M/F/U · Esc')
            body = tui.draw_panel(
                self, rect,
                title=(f'CHUỒNG · {len(self.farm.animals)}/'
                       f'{self.farm.barn_capacity} chỗ · '
                       f'{self.farm.items["feed"]} thức ăn'),
                footer=controls if height >= 22 else '',
                unicode=self.unicode_map, accent='yellow', title_color='yellow',
                bounds=(height, width))
            tab_x = body.x + 1
            tab_limit = body.x + body.width - 1
            for index, zone in enumerate(zones):
                if tab_x >= tab_limit:
                    break
                count = len(zone_animals(self.farm, zone))
                unlocked = self.farm.level >= zone.level
                text = f'{index + 1}. {zone.name} {count}/{zone.capacity}'
                if not unlocked and width >= 72:
                    text += f' (cấp {zone.level})'
                text = tui.ellipsize(text, max(1, tab_limit - tab_x),
                                     unicode=self.unicode_map)
                self._put(body.y, tab_x, text,
                          'selected' if index == zone_index else
                          ('dim' if not unlocked else 'cyan'),
                          index == zone_index)
                tab_x += tui.cells(text) + 2
            zone = zones[zone_index]
            unlocked = self.farm.level >= zone.level
            animals = zone_animals(self.farm, zone)
            if not animals:
                selected = 0
                offset = 0
            else:
                selected = max(0, min(selected, len(animals) - 1))
            if unlocked or animals:
                card_start = 2 if not unlocked else 1
                visible = max(1, (body.height - card_start) // 4)
                offset = max(0, min(offset, max(0, len(animals) - visible)))
                if selected < offset:
                    offset = selected
                elif selected >= offset + visible:
                    offset = selected - visible + 1
            else:
                visible = 0
            if not unlocked and not animals:
                self._put(body.y + 1, body.x + 2,
                          tui.ellipsize(
                              f'Khu này mở ở cấp {zone.level}. '
                              f'Hiện tại bạn ở cấp {self.farm.level}.',
                              max(1, body.width - 4), unicode=self.unicode_map),
                          'red', True)
                self._put(body.y + 3, body.x + 2,
                          tui.ellipsize(zone.description,
                                        max(1, body.width - 4),
                                        unicode=self.unicode_map), 'dim')
            elif not animals:
                self._put(body.y + 1, body.x + 2,
                          tui.ellipsize(
                              f'{zone.name} đang trống. Nhấn M để mua vật nuôi.',
                              max(1, body.width - 4), unicode=self.unicode_map),
                          'cyan')
                self._put(body.y + 3, body.x + 2,
                          tui.ellipsize(zone.description,
                                        max(1, body.width - 4),
                                        unicode=self.unicode_map), 'dim')
            else:
                if not unlocked:
                    self._put(body.y + 1, body.x + 2,
                              tui.ellipsize(
                                  f'Khu mở ở cấp {zone.level}; đàn cũ vẫn được chăm.',
                                  max(1, body.width - 4), unicode=self.unicode_map),
                              'red')
                for slot, animal in enumerate(animals[offset:offset + visible]):
                    index = offset + slot
                    top = body.y + (2 if not unlocked else 1) + slot * 4
                    is_selected = index == selected
                    if is_selected:
                        for row in range(4):
                            self._put(top + row, body.x + 1,
                                      ' ' * max(1, body.width - 2), 'selected')
                    color = 'selected' if is_selected else ''
                    if is_selected:
                        self._put(top, body.x + 1,
                                  '▸' if self.unicode_map else '>', 'selected', True)
                    art = art_for(animal.kind, unicode=self.unicode_map)[:3]
                    for row, line in enumerate(art):
                        self._put(top + row, body.x + 2, line, color, is_selected)
                    info_x = body.x + 14
                    info_w = max(8, body.right - info_x)
                    info = ANIMAL_TYPES[animal.kind]
                    self._put(top, info_x,
                              tui.ellipsize(
                                  f'{animal.name} · {info.name} · {animal.age} ngày',
                                  info_w, unicode=self.unicode_map),
                              'selected' if is_selected else 'yellow', True)
                    self._put(top + 1, info_x,
                              tui.ellipsize(
                                  f'{"Đã ăn" if animal.fed else "ĐÓI"} · '
                                  f'thân {hearts(animal.friendship, maximum=5, unicode=self.unicode_map)}',
                                  info_w, unicode=self.unicode_map),
                              'selected' if is_selected else
                              ('red' if not animal.fed else 'cyan'))
                    self._put(top + 2, info_x,
                              tui.ellipsize(
                                  f'{product_name(animal.kind)} ×{animal.produce}'
                                  + (' · đã vuốt' if animal.petted else ''),
                                  info_w, unicode=self.unicode_map),
                              'selected' if is_selected else 'dim')
            self._draw_status_bar(height, width, controls)
            self._refresh()
            key_name = self._read()
            if key_name in ('b', 'B', 'q', 'Q', '\x1b'):
                return
            if key_name == '\t' or key_name in ('1', '2', '3'):
                if key_name == '\t':
                    zone_index = (zone_index + 1) % len(zones)
                else:
                    zone_index = int(key_name) - 1
                selected = 0
                offset = 0
                continue
            if key_name in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                selected = max(0, selected - 1)
            elif key_name in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                selected = min(max(0, len(animals) - 1), selected + 1)
            elif key_name in ('a', 'A'):
                self._action(feed_animals, self.farm)
            elif key_name in ('c', 'C'):
                self._action(collect_products, self.farm)
            elif key_name in ('f', 'F'):
                count = self._number('Mua thức ăn chăn nuôi')
                if count is not None:
                    self._action(buy_feed, self.farm, count)
            elif key_name in ('u', 'U'):
                self._action(self.farm.upgrade, 'barn')
            elif key_name in ('m', 'M'):
                if not unlocked:
                    self._log(f'{zone.name} mở ở cấp {zone.level}.')
                    continue
                keys = list(zone.species)
                choice = self._choose(
                    f'MUA VẬT NUÔI · {zone.name}',
                    [f'{icon_for(key, unicode=self.unicode_map)} '
                     f'{ANIMAL_TYPES[key].name} · {ANIMAL_TYPES[key].price} xu'
                     for key in keys],
                    [f'{ANIMAL_TYPES[key].name}: trưởng thành sau '
                     f'{ANIMAL_TYPES[key].mature_days} ngày, cho '
                     f'{product_name(key).lower()} mỗi '
                     f'{ANIMAL_TYPES[key].interval} ngày.'
                     for key in keys])
                if choice is not None:
                    self._action(buy_animal, self.farm, keys[choice])
            elif key_name in ('\n', '\r', 'e', 'E',
                              getattr(self._curses, 'KEY_ENTER', -1)):
                if animals:
                    self._action(pet_animal, self.farm, selected)

    def _fish(self):
        from .fishing import start_fishing, finish_fishing
        fishing = start_fishing(self.farm)
        self._log(f"Đã quăng cần (-{action_cost(self.farm, 'fish')} sức). Nhấn/giữ Space để nâng thanh.")
        if not self._save():
            self._log("Đã dừng câu; hãy lưu lại bằng P trước khi tiếp tục.")
            return
        previous = time.monotonic()
        last_space = float("-inf")
        while not fishing.done:
            now = time.monotonic()
            key = self._read()
            now = time.monotonic()
            if key in ("q", "Q", "\x1b"):
                self._log("Đã thu cần. Lượt này không nhận cá.")
                return
            if key == " ":
                last_space = now
            fishing.step(min(now - previous, 0.2), now - last_space < 0.22)
            previous = now
            if self._screen is None:
                continue
            height, width = self._screen.getmaxyx()
            if height < 10 or width < 24:
                self._clear()
                self._put(0, 0, "CÂU CÁ · Space nâng thanh, thả để hạ · Q thu cần", "cyan", True)
                bar_height = max(3, min(14, height - 7))
                for row in range(bar_height):
                    position = 1 - row / max(1, bar_height - 1)
                    inside = abs(position - fishing.bar) <= fishing.bar_width / 2
                    fish_here = abs(position - fishing.target) <= 0.5 / max(1, bar_height - 1)
                    self._put(row + 2, max(0, min(width - 10, width // 2 - 3)),
                              "|" + (" >< " if fish_here else "====" if inside else "    ") + "|",
                              "yellow" if fish_here else "green" if inside else "")
                progress = max(0, min(100, int(fishing.progress * 100)))
                self._put(height - 3, 0, f"Giữ cá >< trong thanh ====   Tiến độ {progress}%", "yellow")
                self._put(height - 2, 0, "Nhấn liên tiếp hoặc giữ Space; thả phím để thanh hạ xuống.")
                self._refresh()
            else:
                self._draw_modal_backdrop(height, width)
                rect = tui.panel_geometry(
                    height, width, content_width=46, content_height=18,
                    margin_x=3, margin_y=1, bottom_reserve=0,
                    min_width=30, min_height=10)
                body = tui.draw_panel(
                    self, rect, title='CÂU CÁ',
                    footer='Space nâng thanh · thả để hạ · Q thu cần',
                    unicode=self.unicode_map, accent='cyan', title_color='yellow',
                    bounds=(height, width))
                progress = max(0, min(100, int(fishing.progress * 100)))
                self._put(body.y, body.x + 1,
                          tui.ellipsize('Giữ cá >< trong thanh để kéo tiến độ lên 100%',
                                        max(1, body.width - 2),
                                        unicode=self.unicode_map), 'dim')
                bar_width = max(4, body.width - 10)
                self._put(body.y + 2, body.x + 2,
                          tui.progress_bar(fishing.progress, bar_width,
                                           unicode=self.unicode_map), 'green', True)
                self._put(body.y + 2, body.x + 3 + bar_width,
                          f'{progress}%', 'yellow', True)
                bar_height = max(3, min(12, body.height - 6))
                left = body.x + max(1, (body.width - 6) // 2)
                for row in range(bar_height):
                    position = 1 - row / max(1, bar_height - 1)
                    inside = abs(position - fishing.bar) <= fishing.bar_width / 2
                    fish_here = abs(position - fishing.target) <= 0.5 / max(1, bar_height - 1)
                    self._put(body.y + 4 + row, left,
                              "│" + (" >< " if fish_here else "====" if inside else "    ") + "│",
                              "yellow" if fish_here else "green" if inside else "")
                self._put(body.y + body.height - 1, body.x + 1,
                          tui.ellipsize('Nhấn liên tiếp hoặc giữ Space; thả phím để thanh hạ xuống.',
                                        max(1, body.width - 2),
                                        unicode=self.unicode_map), 'cyan')
                self._refresh()
        self._action(finish_fishing, self.farm, fishing)

    def _fish_collection(self):
        """A fishing journal with rarity, catch counts and collection points."""
        from .catalog import EXTRA_ITEMS, FISH_TYPES
        from .artwork import art_for, icon_for
        entries = list(FISH_TYPES)
        if self._screen is None:
            return
        height, width = self._screen.getmaxyx()
        if height < 22 or width < 68:
            lines = [f'Bộ sưu tầm: {self.farm.fish_species}/{len(entries)} loài · '
                     f'{self.farm.fish_points} điểm']
            for key in entries:
                fish = FISH_TYPES[key]
                count = self.farm.fish_collection.get(key, 0)
                state = (f'{count} lần' if count else
                         ('chưa câu' if self.farm.level >= fish.level
                          else f'mở cấp {fish.level}'))
                lines.append(f'{icon_for(key, unicode=self.unicode_map)} '
                             f'{fish.name} · {fish.rarity} · {state} · {fish.points} điểm')
            self._reader('BỘ SƯU TẦM CÁ', '\n'.join(lines),
                         close_keys=('k', 'K', 'q', 'Q', '\x1b'))
            return
        selected = 0
        while True:
            height, width = self._screen.getmaxyx()
            if height < 22 or width < 68:
                self._fish_collection()
                return
            self._draw_modal_backdrop(height, width)
            g = tui.glyphs(self.unicode_map)
            rect = tui.panel_geometry(
                height, width, content_width=min(width - 2, 86),
                content_height=height - 3, margin_x=1, margin_y=1,
                bottom_reserve=2, min_width=54, min_height=14)
            nav = '↑↓' if self.unicode_map else 'W/S'
            controls = (f'{nav} chọn · K/Esc đóng · câu thêm để nâng điểm'
                        if width >= 76 else f'{nav} chọn · K/Esc đóng')
            body = tui.draw_panel(
                self, rect, title='BỘ SƯU TẦM CÁ · HỒ SEN',
                footer=controls if height >= 22 else '',
                unicode=self.unicode_map, accent='cyan', title_color='yellow',
                bounds=(height, width))
            self._put(
                body.y, body.x + 1,
                tui.ellipsize(
                    f'{self.farm.fish_species}/{len(entries)} loài · '
                    f'{self.farm.fish_points} điểm sưu tầm · '
                    f'{self.farm.fish_collection_value} xu · '
                    f'{self.farm.fish_caught} lần câu',
                    max(1, body.width - 2), unicode=self.unicode_map), 'cyan')
            left_w = min(48, max(34, body.width * 3 // 5))
            x = body.x + 1
            for index, key in enumerate(entries):
                fish = FISH_TYPES[key]
                row = body.y + 2 + index
                if row >= body.y + body.height - 1:
                    break
                count = self.farm.fish_collection.get(key, 0)
                locked = self.farm.level < fish.level
                if locked:
                    state = f'cấp {fish.level}'
                    color = 'dim'
                elif count:
                    state = f'{count} lần'
                    color = 'yellow'
                else:
                    state = 'chưa câu'
                    color = ''
                mark = ('✓' if count else ('·' if not locked else '×')
                        if self.unicode_map else
                        ('v' if count else ('.' if not locked else 'x')))
                full = (f'{mark} {icon_for(key, unicode=self.unicode_map)} '
                        f'{fish.name} · {fish.rarity} · {state} · {fish.points}đ')
                short_state = (f'{count}x' if count else state)
                compact = (f'{mark} {fish.name} · {fish.rarity} · '
                           f'{short_state} · {fish.points}đ')
                text = (compact if left_w < 42 or tui.cells(full) > max(1, left_w - 2)
                        else full)
                if index == selected:
                    marker = '▸ ' if self.unicode_map else '> '
                    self._put(row, x, ' ' * max(1, left_w - 1), 'selected')
                    self._put(row, x, tui.ellipsize(
                        marker + text, max(1, left_w - 2), unicode=self.unicode_map),
                        'selected', True)
                else:
                    self._put(row, x, tui.ellipsize(
                        text, max(1, left_w - 2), unicode=self.unicode_map),
                        color)
            detail_x = body.x + left_w + 2
            detail_w = max(10, body.right - detail_x)
            key = entries[selected]
            fish = FISH_TYPES[key]
            art = art_for(key, unicode=self.unicode_map)
            art_top = body.y + 2 + max(0, (4 - len(art)) // 2)
            for row, line in enumerate(art):
                self._put(art_top + row, detail_x + 1,
                          tui.pad(line.center(max(1, detail_w - 2)),
                                  max(1, detail_w - 2)), 'magenta')
            info_top = art_top + len(art) + 1
            info = [
                (fish.name, 'yellow', True),
                (f'{fish.rarity} · {fish.points} điểm', 'cyan', False),
                (f'Giá bán: {EXTRA_ITEMS[key].sell_price} xu', 'green', False),
                (f'Đã câu: {self.farm.fish_collection.get(key, 0)} lần',
                 'white', False),
                (('Đã mở khóa' if self.farm.level >= fish.level
                  else f'Mở khóa ở cấp {fish.level}'), 'dim', False),
            ]
            for row, (line, color, bold) in enumerate(info):
                if info_top + row >= body.y + body.height - 1:
                    break
                self._put(info_top + row, detail_x,
                          tui.ellipsize(line, detail_w,
                                        unicode=self.unicode_map), color, bold)
            hint_y = info_top + len(info) + 1
            for offset, line in enumerate(
                    wrap_cells(fish.hint, max(1, detail_w - 1))[:2]):
                if hint_y + offset >= body.y + body.height - 1:
                    break
                self._put(hint_y + offset, detail_x, line, 'dim')
            self._draw_status_bar(height, width, controls)
            self._refresh()
            key_name = self._read()
            if key_name in ('k', 'K', 'q', 'Q', '\x1b'):
                return
            if key_name in ('w', 'W', getattr(self._curses, 'KEY_UP', -1)):
                selected = max(0, selected - 1)
            elif key_name in ('s', 'S', getattr(self._curses, 'KEY_DOWN', -1)):
                selected = min(len(entries) - 1, selected + 1)

    def _help(self):
        lines = [
            "WASD/mũi tên: đi ngay; S luôn là đi xuống.",
            "T: Lan dẫn từng bước; hiện đường đi, mục tiêu và phím cần nhấn.",
            "N: bốn nhiệm vụ mỗi ngày; làm xong rồi nhận xu/XP, ngủ để đổi nhiệm vụ.",
            "G: đổi bản đồ Unicode/ASCII; ký hiệu, khung và thanh thể lực tự đổi theo.",
            "O: auto toàn bộ/trồng trọt/chăn nuôi/câu cá/đào khoáng/hang; chọn ngày và tốc độ.",
            "Auto: Space/P tạm dừng, O/Esc dừng, +/- tốc độ; WASD lấy lại điều khiển.",
            "E: dùng đồ/ô ruộng hoặc trò chuyện với dân làng kề bên.",
            "C: cấp, XP, điểm thuộc tính và tay nghề; nâng bằng điểm nhận khi lên cấp.",
            "Cánh đồng ở (26,42), xa nhà về phía nam; M xem vị trí để đi theo đường.",
            "M: bản đồ toàn làng; J: danh sách dân làng và độ thân.",
            "F: bảng cánh đồng dạng ô; chọn ô rồi Enter để gieo, tưới, thu hoặc dọn.",
            "Ruộng: E gieo hạt, tưới cây, thu cây chín hoặc dọn cây héo khi đứng kề.",
            "H nhà: cửa vào; Z giường: ngủ; V tivi: dự báo ngày mai.",
            "C rương: gửi/rút đồ; I: túi hai cột, tab lọc, Enter gửi/rút.",
            "M chợ: quầy Hạt giống, Vật nuôi, Vật tư, Bán hàng, Nâng cấp; mỗi món có hình minh họa.",
            "Chợ: ←→/↑↓ chọn ô, Tab hoặc 1–5 đổi quầy, Enter mua bán; Esc ra.",
            "B: sổ chuồng có 3 khu mở theo cấp: Sân Gà Vịt (1), Đồng Cỏ (2), Đồi Dê (4).",
            "Trong sổ chuồng: Tab/1–3 đổi khu, Enter vuốt, A cho ăn, C thu, M mua, U nâng.",
            "~ hồ: E quăng cần; Space nâng thanh, thả để hạ. K: bộ sưu tầm cá và điểm.",
            "NPC: chọn chủ đề (chào hỏi, công việc, làng, ước mơ, kỷ niệm), đọc rồi chọn lời đáp.",
            "J: thẻ dân làng có chân dung, mức thân, sở thích và lịch sinh hoạt.",
            "Đi bộ không tốn sức. Chỉ ngủ tại giường mới sang ngày.",
            "Mỏ Khoáng ở Đồi Gió (76,6): E vào mỏ; đứng cạnh đá rồi E để đào quặng.",
            "Trong mỏ: F lò rèn (cuốc/kiếm/giáp), G Hang Sâu, D ra ngoài; ngủ để mỏ hồi đầy.",
            "Lò rèn tiêu quặng và xu để tăng bậc; kiếm bậc 1 mở Hang Sâu, giáp tăng máu.",
            "Hang Sâu: 1/Enter tấn công, 2 uống thuốc, 3 rút lui; kỷ lục lưu theo ván.",
            "Z: khung bản đồ rộng, ô hẹp để nhìn được nhiều đất hơn quanh nhân vật.",
            "Biểu tượng: ☀/☁/☂ thời tiết · ♥ sức/độ thân · ◆ xu · ✧ XP · ▤ túi · ⌖ bản đồ.",
            "Tay nghề: ⚘ trồng trọt · ≈ câu cá · ♱ chăn nuôi · ⚒ kiếm sống · ☾ tập trung.",
            "Tự lưu sau thao tác; P/F5 lưu; Q lưu và về menu chính.",
        ]
        if not self.unicode_map:
            lines = [line.replace('←→/↑↓', 'A/D/W/S')
                      .replace('↑↓', 'W/S').replace('←→', 'A/D')
                      .replace('–', '-') for line in lines]
        index = self._choose("SỔ TAY MOSSBROOK",
                             ["Trở lại làng", "Đọc toàn bộ sổ tay (cuộn)"],
                             lines, close_keys=('h', 'H'))
        if index == 1:
            self._reader("SỔ TAY MOSSBROOK", chr(10).join(lines))
