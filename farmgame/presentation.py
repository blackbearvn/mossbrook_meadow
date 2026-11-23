"""Time-driven story presentation shared by the in-game terminal interfaces."""
from __future__ import annotations

from collections import deque
from contextlib import contextmanager
import math
import os
import sys
import time
import unicodedata

from .identity import intro_pages


class Typewriter:
    """Reveal Unicode letters with their combining marks using elapsed seconds."""

    def __init__(self, text: str, chars_per_second: float = 38.0):
        if not math.isfinite(chars_per_second) or chars_per_second <= 0:
            raise ValueError('Typing speed must be finite and positive.')
        self._speed = chars_per_second
        self._units: list[str] = []
        for char in text:
            if unicodedata.category(char).startswith('M') and self._units:
                self._units[-1] += char
            else:
                self._units.append(char)
        self._progress = 0.0
        self._count = 0

    @property
    def visible(self) -> str:
        return ''.join(self._units[:self._count])

    @property
    def done(self) -> bool:
        return self._count == len(self._units)

    def advance(self, dt: float) -> str:
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('Elapsed time must be finite and nonnegative.')
        self._progress = min(len(self._units), self._progress + dt * self._speed)
        self._count = int(self._progress)
        return self.visible

    def reveal(self) -> str:
        self._progress = self._count = len(self._units)
        return self.visible


_TEXT_FOOTER = 'Enter/Space: hiện hết/tiếp · P/⌫: trước · S/Q/Esc: bỏ qua'
_FOOTER = _TEXT_FOOTER + ' · ↑↓ cuộn'


def play_curses_intro(ui, farm) -> bool:
    """Animate on an attached curses screen; each page waits for a user key."""
    from .explore import wrap_cells

    pages = intro_pages(farm)
    writers = [Typewriter(body) for _, body in pages]
    page, offset = 0, 0
    manual_scroll = False
    previous = time.monotonic()
    ui._screen.timeout(25)
    try:
        while page < len(pages):
            now = time.monotonic()
            writer = writers[page]
            writer.advance(max(0, now - previous))
            previous = now
            height, width = ui._screen.getmaxyx()
            lines = wrap_cells(writer.visible, max(4, width - 6))
            room = max(1, height - 5)
            if not manual_scroll:
                offset = max(0, len(lines) - room)
            nav = '↑↓' if getattr(ui, 'unicode_map', True) else 'W/S'
            footer = _TEXT_FOOTER + f' · {nav} cuộn'
            room, offset = ui.paint(f'{pages[page][0]} · {page + 1}/{len(pages)}',
                                    lines, footer, scroll=offset)
            key = ui.key()
            if isinstance(key, str):
                key = key.lower()
            if key in ('s', 'q', '\x1b'):
                return True
            if key in ('p', '\b', '\x7f', ui._curses.KEY_BACKSPACE):
                page = max(0, page - 1)
                offset, manual_scroll = 0, False
                previous = time.monotonic()
            elif key in (' ', '\n', '\r', ui._curses.KEY_ENTER):
                if writer.done:
                    page += 1
                    offset, manual_scroll = 0, False
                    previous = time.monotonic()
                else:
                    writer.reveal()
            elif key in (ui._curses.KEY_UP, ui._curses.KEY_DOWN,
                         ui._curses.KEY_PPAGE, ui._curses.KEY_NPAGE):
                delta = {ui._curses.KEY_UP: -1, ui._curses.KEY_DOWN: 1,
                         ui._curses.KEY_PPAGE: -room,
                         ui._curses.KEY_NPAGE: room}[key]
                offset = max(0, min(max(0, len(lines) - room), offset + delta))
                manual_scroll = True
        return True
    finally:
        ui._screen.timeout(100)


@contextmanager
def _terminal_keys():
    """Yield a timed single-key reader and restore terminal input on all exits."""
    if os.name == 'nt':
        import msvcrt

        def read(timeout):
            deadline = time.monotonic() + timeout
            while not msvcrt.kbhit():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                time.sleep(min(.005, remaining))
            key = msvcrt.getwch()
            if key in ('\x00', '\xe0'):
                return {'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right',
                        'I': 'page_up', 'Q': 'page_down', 'G': 'home',
                        'O': 'end'}.get(msvcrt.getwch(), 'extended')
            return _check_control_key(key)
        yield read
    else:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        original = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)

            pending = deque()
            escapes = {
                b'\x1b[A': 'up', b'\x1b[B': 'down',
                b'\x1b[C': 'right', b'\x1b[D': 'left',
                b'\x1bOA': 'up', b'\x1bOB': 'down',
                b'\x1bOC': 'right', b'\x1bOD': 'left',
                b'\x1b[5~': 'page_up', b'\x1b[6~': 'page_down',
                b'\x1b[H': 'home', b'\x1b[F': 'end',
                b'\x1bOH': 'home', b'\x1bOF': 'end',
                b'\x1b[1~': 'home', b'\x1b[4~': 'end',
            }

            def byte(timeout):
                if pending:
                    return pending.popleft()
                if not select.select([fd], [], [], timeout)[0]:
                    return None
                value = os.read(fd, 1)
                if not value:
                    raise EOFError
                return value

            def read(timeout):
                value = byte(timeout)
                if value is None:
                    return None
                if value == b'\x1b':
                    # ESC alone remains a skip key. Give a complete ANSI key
                    # a bounded interval, preserving bytes of unknown input.
                    sequence = value
                    deadline = time.monotonic() + .035
                    while any(code.startswith(sequence) for code in escapes):
                        if sequence in escapes:
                            return escapes[sequence]
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        suffix = byte(remaining)
                        if suffix is None:
                            break
                        sequence += suffix
                    pending.extendleft(bytes([part]) for part in reversed(sequence[1:]))
                    return '\x1b'
                return _check_control_key(value.decode('utf-8', errors='ignore'))
            yield read
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)


def _check_control_key(key):
    if key == '\x03':
        raise KeyboardInterrupt
    if key == '\x04':
        raise EOFError
    return key


def play_text_intro(ui, farm) -> bool:
    """Use immediate line input for pipes and interruptible typing for a TTY."""
    pages = intro_pages(farm)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        page = 0
        while page < len(pages):
            title, body = pages[page]
            print(f'\n{title} · {page + 1}/{len(pages)}\n{body}')
            key = input('Enter/Space: tiếp · P/Backspace: trước · S/Q/Esc: bỏ qua > ').lower()
            if key in ('s', 'q', '\x1b'):
                return True
            if key in ('p', '\b', '\x7f'):
                page = max(0, page - 1)
            elif key in ('', ' '):
                page += 1
        return True

    writers = [Typewriter(body) for _, body in pages]
    page = 0
    with _terminal_keys() as read_key:
        while page < len(pages):
            title, _ = pages[page]
            writer = writers[page]
            print(f'\n{title} · {page + 1}/{len(pages)}\n{_TEXT_FOOTER}\n', flush=True)
            printed = ''
            previous = time.monotonic()
            while True:
                now = time.monotonic()
                visible = writer.advance(max(0, now - previous))
                previous = now
                if visible != printed:
                    print(visible[len(printed):], end='', flush=True)
                    printed = visible
                key = read_key(.025)
                if isinstance(key, str):
                    key = key.lower()
                if key in ('s', 'q', '\x1b'):
                    print()
                    return True
                if key in ('p', '\b', '\x7f'):
                    page = max(0, page - 1)
                    print()
                    break
                if key in (' ', '\n', '\r'):
                    if writer.done:
                        page += 1
                        print()
                        break
                    writer.reveal()
    return True
