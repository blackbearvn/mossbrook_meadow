"""Read-only developer credits, independent of game state and persistence."""
from __future__ import annotations

import shutil
import sys
import time
import unicodedata
from pathlib import Path


def credits_lines() -> tuple[str, ...]:
    """Load the UTF-8 credits beside this module, regardless of working directory."""
    return tuple(Path(__file__).with_name('credits.txt').read_text(encoding='utf-8').splitlines())


def _wrap_cells(text: str, width: int) -> list[str]:
    """Wrap words by display cells while keeping combining marks with their base."""
    width = max(1, width)
    result, line, used = [], '', 0
    for word in text.split():
        cells = sum(0 if unicodedata.combining(c) else
                    2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
                    for c in word)
        if line and used + 1 + cells > width:
            result.append(line)
            line, used = '', 0
        if cells > width:
            for char in word:
                size = (0 if unicodedata.combining(char) else
                        2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1)
                if line and used + size > width:
                    result.append(line)
                    line, used = '', 0
                line += char
                used += size
        else:
            if line:
                line += ' '
                used += 1
            line += word
            used += cells
    if line or not result:
        result.append(line)
    return result


def _layout(source, width):
    """Return wrapped rows with source-line and normalized character anchors."""
    rows, anchors = [], []
    for index, line in enumerate(source):
        normalized = ' '.join(line.split())
        character = 0
        for row in _wrap_cells(normalized, width):
            rows.append(row)
            anchors.append((index, character))
            character += len(row)
            while character < len(normalized) and normalized[character].isspace():
                character += 1
    return rows, anchors


def play_curses_credits(ui) -> None:
    """Scroll the credits until the reader explicitly returns to the title."""
    source = credits_lines()
    curses = ui._curses
    offset, paused, elapsed = 0, False, 0.0
    previous = time.monotonic()
    dimensions, anchors = None, []
    ui._screen.timeout(25)
    try:
        while True:
            size = ui._screen.getmaxyx()
            room = max(1, size[0] - 5)
            if size != dimensions:
                anchor = anchors[min(offset, len(anchors) - 1)] if anchors else (0, 0)
                rows, anchors = _layout(source, max(1, size[1] - 6))
                offset = min(range(len(anchors)),
                             key=lambda i: (abs(anchors[i][0] - anchor[0]),
                                            abs(anchors[i][1] - anchor[1]))) if anchors else 0
                dimensions = size
            end = max(0, len(rows) - room)
            now = time.monotonic()
            if not paused:
                elapsed += max(0.0, now - previous)
                steps = int(elapsed / 0.45)
                offset += steps
                elapsed -= steps * 0.45
            previous = now
            offset = min(end, max(0, offset))
            if offset == end:
                paused = True
            status = 'Tạm dừng' if paused else 'Tự cuộn'
            nav = '↑↓' if getattr(ui, 'unicode_map', True) else 'W/S'
            ui.paint('Credit nhà phát triển', rows,
                     f'{status} · Space: dừng/chạy · {nav}/PgUp/PgDn · Home/End · Q/Esc/Enter: về',
                     scroll=offset)
            key = ui.key()
            if key in ('q', 'Q', '\x1b', '\n', '\r', getattr(curses, 'KEY_ENTER', 343)):
                return
            if key == ' ':
                paused = not paused
                elapsed = 0.0
                previous = time.monotonic()
            moves = {curses.KEY_UP: -1, curses.KEY_DOWN: 1,
                     curses.KEY_PPAGE: -room, curses.KEY_NPAGE: room}
            if key in moves:
                offset += moves[key]
                paused, elapsed = True, 0.0
            elif key == curses.KEY_HOME:
                offset, paused, elapsed = 0, True, 0.0
            elif key == curses.KEY_END:
                offset, paused, elapsed = end, True, 0.0
            offset = min(end, max(0, offset))
    finally:
        ui._screen.timeout(100)


def play_text_credits(ui) -> None:
    """Read wrapped pages; an exhausted redirected input prints the remainder."""
    source = tuple(' '.join(line.split()) for line in credits_lines())
    position, history, automatic = (0, 0), [], False
    while True:
        width, height = shutil.get_terminal_size(fallback=(80, 24))
        line, character = position
        remaining = (source[line][character:], *source[line + 1:])
        rows, anchors = _layout(remaining, max(1, width - 2))
        room = max(1, height - 5)
        print('\nCredit nhà phát triển')
        print('\n'.join(rows[:room]))
        if automatic:
            key = ''
        else:
            try:
                key = input('Enter: tiếp · B: trước · Q: về > ').strip().lower()
            except EOFError:
                if sys.stdin.isatty():
                    return
                automatic, key = True, ''
        if key in ('q', '\x1b'):
            return
        if key == 'b':
            if history:
                position = history.pop()
        elif not key:
            if room >= len(rows):
                return
            history.append(position)
            next_line, next_character = anchors[room]
            position = (line + next_line,
                        next_character + (character if next_line == 0 else 0))
