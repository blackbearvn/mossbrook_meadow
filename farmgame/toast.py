"""Short-lived notification cards shared by the terminal frontends.

Toasts are deliberately engine-free: callers push text and a semantic kind,
and the renderer decides where to place the active stack.  A clock function can
be injected in tests, and identical messages are merged so a fast auto loop
never floods the screen.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from .tui import cells, ellipsize, pad


TTL = {
    'info': 3.0,
    'success': 3.6,
    'reward': 4.2,
    'error': 5.0,
    'auto': 2.4,
}

ICONS = {
    'info': ('◆', 'i'),
    'success': ('✓', '+'),
    'reward': ('✦', '*'),
    'error': ('!', '!'),
    'auto': ('⚙', 'A'),
}

COLORS = {
    'info': 'cyan',
    'success': 'green',
    'reward': 'yellow',
    'error': 'red',
    'auto': 'magenta',
}


@dataclass(slots=True)
class Toast:
    text: str
    kind: str
    created: float
    ttl: float
    repeat: int = 1

    def remaining(self, now: float) -> float:
        return max(0.0, self.ttl - (now - self.created))

    def age_ratio(self, now: float) -> float:
        return 0.0 if self.ttl <= 0 else min(1.0, max(0.0, (now - self.created) / self.ttl))


def classify(message: str) -> str:
    """Best-effort semantic kind for an ordinary game message."""
    text = ' '.join(str(message).lower().split())
    if not text:
        return 'info'
    if text.startswith('auto'):
        return 'auto'
    error_words = ('lỗi', 'không thể', 'không có', 'chưa đủ', 'cần ', 'thiếu ',
                   'hết ', 'đã héo', 'bị chặn', 'quá yếu', 'thất bại')
    if any(word in text for word in error_words):
        return 'error'
    reward_words = ('lên cấp', 'nhận ', 'thưởng', '+', 'thu hoạch', 'thu được',
                    'đã bán', 'bán ', 'mua ', 'rèn', 'chinh phục', 'hạ ',
                    'đào được', 'câu được', 'nhặt được')
    if any(word in text for word in reward_words):
        return 'reward'
    success_words = ('đã lưu', 'đã trồng', 'đã tưới', 'đã dọn', 'đã đến',
                     'đã vào', 'đã ra', 'hoàn tất', 'sẵn sàng', 'thành công')
    if any(word in text for word in success_words):
        return 'success'
    return 'info'


class ToastCenter:
    def __init__(self, *, clock=time.monotonic, max_visible: int = 3):
        self._clock = clock
        self.max_visible = max(1, int(max_visible))
        self._items: list[Toast] = []

    def _now(self, now: float | None) -> float:
        return self._clock() if now is None else float(now)

    def push(self, message: str, kind: str | None = None, *, now=None) -> bool:
        text = ' '.join(str(message).split())
        if not text:
            return False
        now = self._now(now)
        kind = kind if kind in TTL else classify(text)
        for toast in list(self._items):
            if toast.text == text and now - toast.created <= 1.4:
                toast.created = now
                toast.repeat += 1
                return True
        self._items.append(Toast(text, kind, now, TTL[kind]))
        del self._items[:-max(5, self.max_visible + 1)]
        return True

    def tick(self, now=None) -> bool:
        now = self._now(now)
        before = len(self._items)
        self._items = [item for item in self._items
                       if now - item.created < item.ttl]
        return len(self._items) != before

    def visible(self, now=None, *, limit: int | None = None) -> list[Toast]:
        now = self._now(now)
        limit = self.max_visible if limit is None else max(0, int(limit))
        active = [item for item in self._items
                  if now - item.created < item.ttl]
        return list(reversed(active))[:limit]

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


def toast_text(toast: Toast, *, unicode: bool = True) -> str:
    icon = ICONS.get(toast.kind, ICONS['info'])[0 if unicode else 1]
    suffix = f' ×{toast.repeat}' if toast.repeat > 1 else ''
    return f'{icon} {toast.text}{suffix}'


def draw_toasts(ui, width: int, height: int, toasts, *, unicode: bool = True,
                top: int = 3, max_width: int = 42, now: float | None = None) -> None:
    """Paint a right-aligned... left-aligned stack of single-line pills.

    The stack sits below the three HUD rows and avoids the bottom message area.
    Tiny terminals silently skip toasts so the map and controls stay usable.
    """
    if width < 30 or height < 12 or not toasts:
        return
    room = max(0, min(len(toasts), height - top - 7))
    if room <= 0:
        return
    limit = max(12, min(max_width, width - 4))
    for index, toast in enumerate(toasts[:room]):
        text = toast_text(toast, unicode=unicode)
        inner = max(1, min(limit, cells(text) + 2))
        label = ' ' + ellipsize(text, max(1, inner - 1), unicode=unicode)
        color = COLORS.get(toast.kind, 'cyan')
        if now is not None and toast.age_ratio(now) > 0.65:
            color = 'dim'
        if unicode:
            line = '╭' + pad(label, inner) + '╮'
        else:
            line = '[' + pad(label, inner) + ']'
        ui._put(top + index, 0, line, color, toast.kind in ('reward', 'error'))
