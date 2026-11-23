"""Safe startup transaction and title/wizard UIs; curses is loaded on demand."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .identity import (AVATARS, OUTFITS, BACKGROUNDS, BACKGROUND_HINTS,
                       create_character, intro_pages, normalize_name)
from .model import Farm
from .storage import SaveError, backup_save, load_game, save_game
from .explore import ExplorerGame, fit_text, wrap_cells
from . import tui


@dataclass
class StartupResult:
    farm: Farm | None
    created: bool = False
    exit_code: int = 0
    play_intro: bool = False


LANDSCAPE = (
    '           .--.                .--.       ',
    '        .-(    ).           .-(    ).    ',
    '       (___.__)__)         (___.__)__)   ',
    '    /\\          /\\             /\\      ',
    '   /  \\   /\\  /  \\    _/\\_   /  \\     ',
    '  /____\\ /__\\/____\\  /____\\ /____\\    ',
    '       T       T       | [] |      T     ',
    '  ~ ~ ~ ~ ~ ~ ~ ~ ~ ~  |____|  ~ ~ ~ ~  ',
)
CREATOR_FIELDS = (
    ('player_name', 'Tên bạn', 24),
    ('farm_name', 'Nông trại', 28),
    ('avatar', 'Biểu tượng', None),
    ('outfit', 'Màu áo', None),
    ('background', 'Xuất thân', None),
)
CREATOR_BUTTONS = (
    ('start', 'Bắt đầu hành trình'),
    ('cancel', 'Hủy'),
)
HELP = ('WASD / phím mũi tên: di chuyển. E: tương tác với người và địa điểm.\n'
        'G: đổi hình bản đồ Unicode/ASCII.\n'
        'N: nhiệm vụ hằng ngày. O: auto; Space/P tạm dừng, O/Esc dừng auto.\n'
        'F: bảng cánh đồng; B: sổ chuồng 3 khu theo cấp; K: bộ sưu tầm cá.\n'
        'C: hồ sơ hai cột, chân dung và thanh bậc; Enter nâng, Space xem đầy đủ, X đổi điểm dư.\n'
        'I: túi đồ/rương hai cột, tab lọc, minh họa và tổng xu. M: bản đồ. J: thẻ dân làng.\n'
        'R: đi nhanh giữa các khu vực; bản đồ theo trang chỉ hiện một khu, đi qua đường ở rìa để sang trang.\n'
        'Z: khung bản đồ rộng, hiện nhiều ô hơn quanh nhân vật.\n'
        'Mỏ Khoáng ở Đồi Gió (76,6): E vào mỏ, đứng cạnh đá rồi E để đào quặng.\n'
        'Trong mỏ: F lò rèn (cuốc/kiếm/giáp), G Hang Sâu, D ra ngoài; ngủ để mỏ hồi đầy.\n'
        'Hang Sâu: 1/Enter tấn công, 2 uống thuốc, 3 rút lui; cần kiếm bậc 1.\n'
        'Trong nhà, đứng cạnh bếp K rồi E để nấu ăn.\n'
        'Ruộng có 9 giống; chuồng có gà, vịt, thỏ, bò, cừu, dê, heo. Nấu món để hồi sức và bán.\n'
        'Biểu tượng: ☀☁☂ thời tiết · ♥ sức · ◆ xu · ✧ XP · ▤ túi; --ascii tự đổi ASCII.\n'
        'Màu map: cát vàng · hồ xanh lục nhạt · biển xanh dương · rừng xanh đậm.\n'
        'M tại cửa tiệm: chợ chia ô có hình minh họa; Tab đổi quầy, Enter chọn.\n'
        'H: hướng dẫn trong game. P: lưu. Q: lưu và về menu chính.\n'
        'Từ quảng trường, đi về ruộng ở (26, 42). Mỗi ngày là một khởi đầu mới.')


class TextUI:
    def choose(self, title, options, *, body='', default=None):
        while True:
            print('\n' + title)
            if body:
                print(body)
            for key, label in options:
                print(f'  {key}. {label}')
            value = input('Chọn > ').strip()
            if not value and default is not None:
                return default
            if value in dict(options):
                return value
            if value == '\x1b':
                return '0'
            print('Hãy chọn một số trong menu.')

    def name(self, title, default, limit):
        error = ''
        while True:
            print(f'\n{title} · tối đa {limit} ký tự · 0 để hủy')
            if error:
                print(error)
            value = input(f'[{default}] > ')
            if value.strip() == '0' or value == '\x1b':
                return None
            try:
                return normalize_name(value if value else default, limit, title)
            except ValueError as exc:
                error = str(exc)

    def reader(self, title, body):
        print('\n' + title + '\n' + body)
        input('Enter để trở lại > ')

    def intro(self, farm):
        from .presentation import play_text_intro
        return play_text_intro(self, farm)

    def credits(self):
        from .credits import play_text_credits
        play_text_credits(self)


class CursesUI(ExplorerGame):
    """Reuse cell-safe painting only, never ExplorerGame's autosaving run()."""
    def __init__(self, color=True, clear_screen=True):
        super().__init__(None, Path('.'), color, clear_screen)

    def attach(self, screen, curses):
        self._screen, self._curses = screen, curses
        screen.keypad(True)
        screen.timeout(100)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if self.color and curses.has_colors():
            self._colors = tui.init_colors(curses, self.color)

    def key(self):
        key = self._read()
        if key == '\x03':
            raise KeyboardInterrupt
        if key == '\x04':
            raise EOFError
        return key

    def paint(self, title, lines, footer, selected=None, scroll=0):
        self._screen.erase()
        height, width = self._screen.getmaxyx()
        if height < 6 or width < 20:
            self._put(0, 0, tui.ellipsize('M Â Y  N H Ỏ', width,
                                          unicode=self.unicode_map), 'green', True)
            self._put(1, 0, tui.ellipsize(title, width,
                                          unicode=self.unicode_map), 'yellow', True)
            room = max(1, height - 5)
            scroll = max(0, min(scroll, max(0, len(lines) - room)))
            for index, line in enumerate(lines[scroll:scroll + room], scroll):
                active = index == selected
                self._put(3 + index - scroll, 0,
                          tui.ellipsize((('› ' if self.unicode_map else '> ')
                                         if active else '  ') + line, width,
                                        unicode=self.unicode_map),
                          'selected' if active else
                          'green' if line in LANDSCAPE else '', active)
            self._put(height - 1, 0, tui.ellipsize(footer, width,
                                                   unicode=self.unicode_map), 'cyan')
            self._refresh()
            return room, scroll
        # A slim top rule frames the floating panel without competing with
        # its shadow at the bottom of the terminal.
        g = tui.glyphs(self.unicode_map)
        self._put(0, 0, g['h'] * width, 'shadow')
        self._put(0, 1, f" {g['icon']} MÂY NHỎ ", 'dim')
        margin_x = 2 if width >= 44 else 1 if width >= 22 else 0
        margin_y = 1 if height >= 8 else 0
        rect = tui.Rect(margin_x, margin_y, width - 2 * margin_x,
                        height - 2 * margin_y)
        body = tui.draw_panel(
            self, rect, title=title, footer=footer, unicode=self.unicode_map,
            accent='magenta', title_color='yellow', footer_color='cyan',
            shadow=margin_x > 0, bounds=(height, width))
        room = max(1, body.height)
        scroll = max(0, min(scroll, max(0, len(lines) - room)))
        for index, line in enumerate(lines[scroll:scroll + room], scroll):
            active = index == selected
            label = (('› ' if self.unicode_map else '> ') if active else '  ') + line
            row = body.y + index - scroll
            if active:
                self._put(row, body.x, ' ' * body.width, 'selected')
                self._put(row, body.x,
                          tui.ellipsize(label, body.width, unicode=self.unicode_map),
                          'selected', True)
            else:
                self._put(row, body.x,
                          tui.ellipsize(label, body.width, unicode=self.unicode_map),
                          'green' if line in LANDSCAPE else '')
        self._refresh()
        return room, scroll

    @staticmethod
    def _creator_value(profile, key):
        if key == 'avatar':
            return f"{profile[key]} {AVATARS[profile[key]]}"
        if key == 'outfit':
            return OUTFITS[profile[key]]
        if key == 'background':
            return BACKGROUNDS[profile[key]]
        return profile[key]

    @staticmethod
    def _creator_cycle(profile, field, step):
        choices = {'avatar': AVATARS, 'outfit': OUTFITS,
                   'background': BACKGROUNDS}[field]
        keys = list(choices)
        profile[field] = keys[(keys.index(profile[field]) + step) % len(keys)]

    def _creator_row(self, y, x, width, text, *, selected, color='', arrows=None):
        if width <= 0:
            return
        if selected:
            self._put(y, x, ' ' * width, 'selected')
        room = max(1, width - 2 - (4 if arrows else 0))
        self._put(y, x + 1, tui.ellipsize(text, room, unicode=self.unicode_map),
                  'selected' if selected else color, selected)
        if arrows and width >= 8:
            self._put(y, x + width - 4, arrows,
                      'selected' if selected else 'dim')

    def _creator_preview(self, profile, body, x, width, top, *, compact=False):
        bottom = body.y + body.height
        if top >= bottom or width < 10:
            return
        g = tui.glyphs(self.unicode_map)
        if compact:
            # In a short terminal a full card would be clipped; keep the live
            # identity visible without spending rows on a heading or border.
            text = (f"{profile['avatar']} {profile['player_name']}"
                    f" · {profile['farm_name']}")
            self._put(top, x + 1, tui.ellipsize(text, max(1, width - 2),
                                                unicode=self.unicode_map),
                      profile['outfit'], True)
            if top + 1 < bottom:
                text = (f"{OUTFITS[profile['outfit']]} · "
                        f"{BACKGROUNDS[profile['background']]}")
                self._put(top + 1, x + 1,
                          tui.ellipsize(text, max(1, width - 2),
                                        unicode=self.unicode_map), 'dim')
            return
        self._put(top, x + 1, 'XEM TRƯỚC', 'dim')
        y = top + 2
        card_w = min(width - 2, 26)
        card_h = 9
        card = width >= 18 and y + card_h <= bottom
        if card:
            from .artwork import player_portrait
            card_x = x + max(0, (width - card_w) // 2)
            self._put(y, card_x, g['tl'] + g['h'] * (card_w - 2) + g['tr'], 'cyan')
            for row in range(1, card_h - 1):
                self._put(y + row, card_x,
                          g['v'] + ' ' * (card_w - 2) + g['v'], 'cyan')
            self._put(y + card_h - 1, card_x,
                      g['bl'] + g['h'] * (card_w - 2) + g['br'], 'cyan')
            inner = card_w - 2
            portrait = player_portrait(profile['avatar'],
                                       unicode=self.unicode_map)
            for offset, line in enumerate(portrait, 1):
                self._put(y + offset,
                          card_x + 1 + max(0, (inner - tui.cells(line)) // 2),
                          line, profile['outfit'], True)
            name = tui.ellipsize(profile['player_name'], max(1, inner - 2),
                                 unicode=self.unicode_map)
            self._put(y + card_h - 2,
                      card_x + 1 + max(0, (inner - tui.cells(name)) // 2),
                      name, 'yellow', True)
            y += card_h + 1
        lines = []
        if not card:
            lines.append((f"{profile['avatar']}  {profile['player_name']}",
                          profile['outfit'], True))
        if width >= 24:
            # The form already shows these values; narrow previews use the
            # remaining rows for the origin hint instead of clipped duplicates.
            lines.extend([
                (f"Nông trại: {profile['farm_name']}", 'white', False),
                (f"Màu áo: {OUTFITS[profile['outfit']]}", 'white', False),
                (f"Xuất thân: {BACKGROUNDS[profile['background']]}", 'white', False),
            ])
        elif width >= 16:
            # Keep the essentials visible in a 20x60 terminal: the full labels
            # would consume the whole preview pane.
            lines.extend([
                (f"Trại: {profile['farm_name']}", 'white', False),
                (f"Áo: {OUTFITS[profile['outfit']]}", 'white', False),
                (f"Thân: {BACKGROUNDS[profile['background']]}", 'white', False),
            ])
        for text, color, bold in lines:
            if y >= bottom:
                break
            self._put(y, x + 1, tui.ellipsize(text, max(1, width - 2),
                                              unicode=self.unicode_map),
                      color, bold)
            y += 1
        for line in wrap_cells(BACKGROUND_HINTS[profile['background']],
                               max(2, width - 2)):
            if y >= bottom:
                break
            self._put(y, x + 1, line, 'dim')
            y += 1
        if y < bottom:
            self._put(y, x + 1, 'Ngày 1 · Cấp 1 · 120 xu', 'green')
            y += 1
        if y < bottom:
            self._put(y, x + 1, 'Bắt đầu sẽ sao lưu ván cũ.', 'yellow')
            y += 1
        for line in wrap_cells('Diện mạo và xuất thân chỉ đổi câu chuyện, '
                               'không đổi lối chơi.', max(2, width - 2)):
            if y >= bottom:
                break
            self._put(y, x + 1, line, 'dim')
            y += 1

    def _creator_draw(self, profile, selected, height, width):
        self._screen.erase()
        g = tui.glyphs(self.unicode_map)
        self._put(0, 0, g['h'] * width, 'shadow')
        self._put(0, 1, f" {g['icon']} MÂY NHỎ ", 'dim')
        margin_x = 2 if width >= 56 else 1 if width >= 40 else 0
        margin_y = 1 if height >= 10 else 0
        rect = tui.Rect(margin_x, margin_y, width - 2 * margin_x,
                        height - 2 * margin_y)
        nav = '↑↓' if self.unicode_map else 'W/S'
        side = '←→' if self.unicode_map else '<>'
        if width >= 70:
            footer = f'{nav} chọn · Enter sửa/chọn · {side} đổi · B bắt đầu · Esc hủy'
        elif width >= 46:
            footer = f'{nav} chọn · Enter sửa · {side} đổi · B · Esc'
        else:
            footer = f'{nav} chọn · Enter · {side} · B · Esc'
        body = tui.draw_panel(
            self, rect, title='TẠO NHÂN VẬT · MÂY NHỎ', footer=footer,
            unicode=self.unicode_map, accent='magenta', title_color='yellow',
            footer_color='cyan', shadow=margin_x > 0, bounds=(height, width))
        two_col = body.width >= 54 and body.height >= 10
        form_width = (min(40, max(34, body.width - 24))
                      if two_col else body.width)
        show_section = body.height >= 9
        show_blank = body.height >= (9 if show_section else 8)
        label_width = max(tui.cells(label) for _, label, _ in CREATOR_FIELDS) + 1
        marker = '› ' if self.unicode_map else '> '
        arrows = '‹ ›' if self.unicode_map else '< >'
        y = body.y
        if show_section:
            self._put(y, body.x + 1, 'HỒ SƠ', 'dim')
            y += 1
        for index, (key, label, limit) in enumerate(CREATOR_FIELDS):
            active = selected == index
            text = ((marker if active else '  ')
                    + tui.pad(label, label_width)
                    + self._creator_value(profile, key))
            self._creator_row(
                y, body.x, form_width, text, selected=active,
                color=profile['outfit'] if key == 'avatar' else 'white',
                arrows=arrows if limit is None else None)
            y += 1
        if show_blank:
            y += 1
        for offset, (key, label) in enumerate(CREATOR_BUTTONS):
            active = selected == len(CREATOR_FIELDS) + offset
            text = (marker if active else '  ') + '  ' + label
            self._creator_row(y, body.x, form_width, text, selected=active,
                              color='green' if key == 'start' else 'cyan')
            y += 1
        if two_col:
            divider_x = body.x + form_width
            for row in range(body.y, body.y + body.height):
                self._put(row, divider_x, g['v'], 'dim')
            self._creator_preview(profile, body, divider_x + 2,
                                  body.width - form_width - 2, body.y)
        else:
            remaining = body.y + body.height - y
            if remaining >= 9:
                self._creator_preview(profile, body, body.x, body.width, y + 1)
            elif remaining >= 3:
                self._creator_preview(profile, body, body.x, body.width, y + 1,
                                      compact=True)

    def character_wizard(self, default_name):
        """One live character-creation page; tiny terminals use the step wizard."""
        try:
            farm_name = normalize_name(default_name, 28, 'Tên nông trại')
        except ValueError:
            farm_name = 'Mây Nhỏ'
        profile = dict(player_name='Người làm vườn', farm_name=farm_name,
                       avatar='@', outfit='green', background='gardener')
        selected = 0
        total = len(CREATOR_FIELDS) + len(CREATOR_BUTTONS)
        while True:
            height, width = self._screen.getmaxyx()
            if height < 12 or width < 40:
                return _wizard_steps(self, default_name)
            self._creator_draw(profile, selected, height, width)
            self._refresh()
            key = self.key()
            if key in ('\x1b', 'q', 'Q'):
                return None
            if key in ('b', 'B'):
                return dict(profile)
            if key in ('\n', '\r', 'e', 'E',
                       getattr(self._curses, 'KEY_ENTER', -1)):
                if selected < len(CREATOR_FIELDS):
                    field, label, limit = CREATOR_FIELDS[selected]
                    if limit is not None:
                        value = self.name(label, profile[field], limit)
                        if value is not None:
                            profile[field] = value
                    else:
                        self._creator_cycle(profile, field, 1)
                elif selected == len(CREATOR_FIELDS):
                    return dict(profile)
                else:
                    return None
            elif key in (getattr(self._curses, 'KEY_UP', -1),
                         'w', 'W', 'k', 'K'):
                selected = (selected - 1) % total
            elif key in (getattr(self._curses, 'KEY_BTAB', -1),):
                selected = (selected - 1) % total
            elif key in (getattr(self._curses, 'KEY_DOWN', -1),
                         's', 'S', 'j', 'J', '\t'):
                selected = (selected + 1) % total
            elif key in (getattr(self._curses, 'KEY_LEFT', -1),
                         'a', 'A', 'h', 'H'):
                if selected < len(CREATOR_FIELDS):
                    field, _, limit = CREATOR_FIELDS[selected]
                    if limit is None:
                        self._creator_cycle(profile, field, -1)
            elif key in (getattr(self._curses, 'KEY_RIGHT', -1),
                         'd', 'D', 'l', 'L'):
                if selected < len(CREATOR_FIELDS):
                    field, _, limit = CREATOR_FIELDS[selected]
                    if limit is None:
                        self._creator_cycle(profile, field, 1)

    def choose(self, title, options, *, body='', default=None):
        selected = next((i for i, pair in enumerate(options) if pair[0] == default), 0)
        manual_scroll = None
        while True:
            width = max(4, self._screen.getmaxyx()[1] - 6)
            heading = []
            if title == 'MÂY NHỎ · Một cuộc sống chậm giữa mây trời':
                if self._screen.getmaxyx()[0] >= 25:
                    heading.extend(LANDSCAPE)
                    heading.append('')
            if body:
                heading.extend(wrap_cells(body, width))
                heading.append('')
            lines = heading + [f'{key}. {label}' for key, label in options]
            active = len(heading) + selected
            room = max(1, self._screen.getmaxyx()[0] - 5)
            scroll = max(0, active - room + 1) if manual_scroll is None else manual_scroll
            nav = '↑↓' if self.unicode_map else 'W/S'
            self.paint(title, lines,
                       f'{nav}: chọn · Enter/số: xác nhận · PgUp/PgDn: cuộn · Esc: hủy',
                       active, scroll)
            key = self.key()
            if key in dict(options):
                return key
            if key == '\x1b':
                return '0'
            if key in (self._curses.KEY_UP, 'k', 'w', 'W'):
                selected = (selected - 1) % len(options)
                manual_scroll = None
            elif key in (self._curses.KEY_DOWN, 'j', 's', 'S'):
                selected = (selected + 1) % len(options)
                manual_scroll = None
            elif key == self._curses.KEY_PPAGE:
                manual_scroll = max(0, scroll - room)
            elif key == self._curses.KEY_NPAGE:
                manual_scroll = min(max(0, len(lines) - room), scroll + room)
            elif key in ('\n', '\r', self._curses.KEY_ENTER):
                return options[selected][0]

    def name(self, title, default, limit):
        value, error = '', ''
        while True:
            width = max(4, self._screen.getmaxyx()[1] - 8)
            # Keep the caret and the end of the Unicode input visible; never
            # clip the actual value that will be normalized and validated.
            cursor = '▏' if self.unicode_map else '_'
            visible = value
            while visible and fit_text(visible + cursor, width) != visible + cursor:
                visible = visible[1:]
            lines = [f'Tối đa {limit} ký tự · Enter dùng mặc định',
                     *wrap_cells(f'Mặc định: {default}', width), '',
                     *wrap_cells(error, width), '> ' + visible + cursor]
            room = max(1, self._screen.getmaxyx()[0] - 5)
            self.paint(title, lines, 'Enter: tiếp · Backspace: xóa · Esc/0: hủy',
                       scroll=max(0, len(lines) - room))
            key = self.key()
            if key == '\x1b':
                return None
            if key in ('\n', '\r', self._curses.KEY_ENTER):
                if value.strip() == '0':
                    return None
                try:
                    return normalize_name(value if value else default, limit, title)
                except ValueError as exc:
                    error = str(exc)
            elif key in ('\b', '\x7f', self._curses.KEY_BACKSPACE):
                value = value[:-1]
            elif isinstance(key, str) and key.isprintable():
                value += key

    def reader(self, title, body):
        offset = 0
        while True:
            lines = wrap_cells(body, max(4, self._screen.getmaxyx()[1] - 6))
            nav = '↑↓' if self.unicode_map else 'W/S'
            room, offset = self.paint(title, lines,
                                      f'{nav}: cuộn · Enter/Esc: trở lại', scroll=offset)
            key = self.key()
            if key in ('\x1b', '\n', '\r', 'q', self._curses.KEY_ENTER):
                return
            if key in (self._curses.KEY_DOWN, 's', 'S', 'j', 'J'):
                offset += 1
            elif key in (self._curses.KEY_UP, 'w', 'W', 'k', 'K'):
                offset = max(0, offset - 1)
            elif key == self._curses.KEY_NPAGE:
                offset += room
            elif key == self._curses.KEY_PPAGE:
                offset = max(0, offset - room)

    def intro(self, farm):
        from .presentation import play_curses_intro
        return play_curses_intro(self, farm)

    def credits(self):
        from .credits import play_curses_credits
        play_curses_credits(self)


def _with_ui(callback, graphical, color, clear_screen):
    if not graphical:
        return callback(TextUI())
    import curses
    ui = CursesUI(color, clear_screen)
    def wrapped(screen):
        ui.attach(screen, curses)
        return callback(ui)
    return curses.wrapper(wrapped)


def show_intro(farm, *, graphical, color=True, clear_screen=True) -> bool:
    """Show personalized pages without changing farm state or writing a save."""
    try:
        return _with_ui(lambda ui: ui.intro(farm), graphical, color, clear_screen)
    except (KeyboardInterrupt, EOFError):
        return False
    except Exception as exc:
        if not graphical:
            raise
        print(f'Giao diện terminal gặp lỗi: {exc}. Hãy chạy lại với --text.', file=sys.stderr)
        return False


def _wizard(ui, default_name):
    creator = getattr(ui, 'character_wizard', None)
    if creator is not None:
        return creator(default_name)
    return _wizard_steps(ui, default_name)


def _wizard_steps(ui, default_name):
    profile = dict(player_name='Người làm vườn', farm_name=default_name,
                   avatar='@', outfit='green', background='gardener')
    while True:
        for field, label, limit in (('player_name', 'Tên người chơi', 24),
                                    ('farm_name', 'Tên nông trại', 28)):
            name = ui.name(label, profile[field], limit)
            if name is None:
                return None
            profile[field] = name
        for field, title, options in (('avatar', 'Biểu tượng', AVATARS),
                                      ('outfit', 'Màu áo', OUTFITS),
                                      ('background', 'Xuất thân', BACKGROUNDS)):
            keys = list(options)
            choices = [(str(i + 1), f'{key} · {options[key]}' if field == 'avatar' else options[key])
                       for i, key in enumerate(keys)]
            choice = ui.choose(title, choices + [('0', 'Hủy')],
                               default=str(keys.index(profile[field]) + 1))
            if choice == '0':
                return None
            profile[field] = keys[int(choice) - 1]
        preview = (f"{profile['avatar']}  {profile['player_name']}\n"
                   f"Nông trại: {profile['farm_name']}\n"
                   f"Màu áo: {OUTFITS[profile['outfit']]}\n"
                   f"Xuất thân: {BACKGROUNDS[profile['background']]}\n"
                   f"{BACKGROUND_HINTS[profile['background']]}\n"
                   'Ngày 1 · Cấp 1 · Một khởi đầu mới.\n'
                   'Bắt đầu sẽ sao lưu ván cũ trước khi tạo ván mới.')
        choice = ui.choose('Sẵn sàng lên đường?', [('1', 'Bắt đầu hành trình'),
                           ('2', 'Chỉnh lại'), ('0', 'Hủy')], body=preview, default='1')
        if choice == '1':
            return profile
        if choice == '0':
            return None



def confirm_exit(ui) -> bool:
    """Return True only when the player confirms leaving from the title."""
    try:
        choice = ui.choose(
            'THOÁT GAME?',
            [('1', 'Thoát game'), ('0', 'Ở lại')],
            body=('Tiến trình đã lưu vẫn còn trong file.\n'
                  'Bạn có chắc muốn đóng Mây Nhỏ không?'),
            default='0')
    except (EOFError, KeyboardInterrupt, StopIteration):
        # A redirected/closed menu input means the caller intended to leave.
        return True
    return choice == '1'

def _startup(ui, save_path, default_name, force_new, force_intro, skip_intro):
    message = ''
    while True:
        current, load_error = None, ''
        if save_path.exists():
            try:
                current = load_game(save_path)
            except (SaveError, OSError) as exc:
                load_error = str(exc)
        summary = (f'{current.player_name} · {current.name} · Ngày {current.day} · Cấp {current.level}'
                   if current else load_error or 'Chưa có ván chơi tại file lưu này.')
        body = f'{summary}\nFile lưu: {save_path}'
        if message:
            body += '\n' + message
        if force_new:
            choice, force_new = '2', False
        else:
            dash = '–' if getattr(ui, 'unicode_map', True) else '-'
            choice = ui.choose('MÂY NHỎ · Một cuộc sống chậm giữa mây trời',
                               [('1', 'Tiếp tục'),
                                ('2', f'Hành trình mới {dash} tạo nhân vật'),
                                ('3', 'Credit nhà phát triển'),
                                ('4', 'Hướng dẫn'), ('0', 'Thoát')], body=body)
        message = ''
        if choice == '0':
            if confirm_exit(ui):
                return StartupResult(None)
            continue
        if choice == '1':
            if current is None:
                message = load_error or 'Chưa có ván chơi. Chọn 2 để tạo nhân vật.'
                continue
            play_intro = (force_intro or not current.intro_seen) and not skip_intro
            if not current.intro_seen and skip_intro:
                current.intro_seen = True
                try:
                    save_game(current, save_path)
                except (SaveError, OSError) as exc:
                    message = str(exc)
                    continue
            return StartupResult(current, play_intro=play_intro)
        if choice == '2':
            profile = _wizard(ui, default_name)
            if profile is None:
                continue
            try:
                farm = create_character(**profile)
                farm.map_pages = True
                if save_path.exists():
                    backup_save(save_path)
                save_game(farm, save_path)
            except (SaveError, OSError, ValueError) as exc:
                message = str(exc)
                continue
            if skip_intro:
                farm.intro_seen = True
                try:
                    save_game(farm, save_path)
                except (SaveError, OSError) as exc:
                    message = str(exc)
                    continue
            return StartupResult(farm, created=True, play_intro=not skip_intro)
        if choice == '3':
            ui.credits()
        elif choice == '4':
            ui.reader('Những ngày đầu ở Mây Nhỏ', HELP)


def run_startup(save_path: Path, *, graphical: bool, color=True, clear_screen=True,
                default_name='Mây Nhỏ', force_new=False, force_intro=False,
                skip_intro=False) -> StartupResult:
    """Return a chosen farm only after a successful final-confirmation save."""
    try:
        return _with_ui(lambda ui: _startup(ui, Path(save_path), default_name,
                         force_new, force_intro, skip_intro), graphical, color, clear_screen)
    except (KeyboardInterrupt, EOFError):
        return StartupResult(None)
    except ImportError:
        print('Terminal không hỗ trợ curses. Hãy chạy lại với --text.', file=sys.stderr)
        return StartupResult(None, exit_code=1)
    except Exception as exc:
        if not graphical:
            raise
        # curses.wrapper has restored the terminal. This UI has no placeholder
        # farm and must never autosave on an input or rendering failure.
        print(f'Giao diện terminal gặp lỗi: {exc}. Hãy chạy lại với --text.', file=sys.stderr)
        return StartupResult(None, exit_code=1)
