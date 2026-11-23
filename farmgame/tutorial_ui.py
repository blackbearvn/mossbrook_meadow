"""Optional, persistent coaching for both terminal frontends.

The coach observes real actions; menus and rendering never perform game actions.
"""
from copy import deepcopy

from .tutorial import (STEPS, pause_tutorial, record_event, resume_tutorial,
                       skip_tutorial, start_tutorial, sync_tutorial,
                       tutorial_hint, tutorial_lines)


class TutorialCoach:
    def __init__(self, ui, farm, save_callback, *, text=False):
        self.ui = ui
        self.farm = farm
        self.save_callback = save_callback
        self.text = text

    def _log(self, message):
        if not message:
            return
        if self.text:
            self.ui.messages.append(str(message))
        else:
            self.ui._log(message)

    def _change(self, action, *args, **details):
        before = deepcopy(self.farm.tutorial)
        message = action(self.farm, *args, **details)
        self._log(message)
        if self.farm.tutorial != before:
            self.save_callback()
        return message

    def event(self, name, **details):
        return self._change(record_event, name, **details)

    def sync(self):
        return self._change(sync_tutorial)

    def _choose(self, title, options, details=()):
        if not self.text:
            return self.ui._choose(title, options, details)
        self.ui.say(title, 'title')
        for line in details:
            self.ui.wrapped(line)
        for index, option in enumerate(options, 1):
            self.ui.wrapped(f'[{index}] {option}')
        self.ui.wrapped('[0] Quay lại')
        while True:
            answer = self.ui.ask('Chọn số [0 = quay lại]: ').strip().lower()
            if answer in ('', '0', 'q', 'esc'):
                return None
            if answer.isdecimal() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.ui.wrapped(f'Chọn từ 1 đến {len(options)}, hoặc 0 để quay lại.')

    def offer(self):
        if self.farm.tutorial.status != 'pending':
            return
        choice = self._choose('Để Lan dẫn từng bước nhé?',
                              ['Bắt đầu', 'Tự khám phá'],
                              ['15 bước thực hành; T mở hướng dẫn bất cứ lúc nào.',
                               'Bạn tự di chuyển và thao tác. Có thể tạm ẩn hoặc bỏ qua.'])
        self._change(start_tutorial if choice == 0 else skip_tutorial)

    def _title(self):
        state = self.farm.tutorial
        if state.status == 'completed':
            return 'Lan · Hoàn tất 15/15 bước'
        status = {'paused': ' · Tạm ẩn', 'off': ' · Chưa bắt đầu',
                  'pending': ' · Chưa bắt đầu', 'skipped': ' · Đã bỏ qua'}.get(state.status, '')
        return f'Lan · {min(state.step + 1, len(STEPS))}/{len(STEPS)} · {STEPS[min(state.step, len(STEPS) - 1)].title}{status}'

    def _details(self):
        lines = list(tutorial_lines(self.farm))
        lines.extend(['', 'T mở bảng này; tạm ẩn chỉ tắt chỉ dẫn trên bản đồ.',
                      'Bước thực hành vẫn được ghi nhận khi tạm ẩn.',
                      'Chỉ khi tự mở C ở bước nhân vật, bạn mới nhận 40 XP nhập môn một lần.',
                      'Dùng điểm thuộc tính hoặc tay nghề để tự nâng một chỉ số.'])
        return '\n'.join(lines)

    def _read_details(self):
        if self.text:
            for line in self._details().splitlines():
                self.ui.wrapped(line)
            self.ui.ask('Enter để quay lại... ')
        else:
            self.ui._reader(self._title(), self._details())

    def panel(self):
        while True:
            status = self.farm.tutorial.status
            if status in ('active', 'paused'):
                options = ['Đọc chỉ dẫn đầy đủ',
                           'Tiếp tục hiện hướng dẫn' if status == 'paused' else 'Tạm ẩn hướng dẫn',
                           'Bỏ qua hướng dẫn']
            elif status == 'completed':
                options = ['Đọc tổng kết và lộ trình']
            else:
                options = ['Bắt đầu hướng dẫn từng bước', 'Đọc lộ trình đầy đủ']
            choice = self._choose(self._title(), options,
                                  ['T: hướng dẫn · 0/Q/Esc: quay lại'])
            if choice is None:
                return
            if status in ('active', 'paused'):
                if choice == 0:
                    self._read_details()
                    continue
                self._change((resume_tutorial if status == 'paused' else pause_tutorial)
                             if choice == 1 else skip_tutorial)
                return
            if status == 'completed' or choice == 1:
                self._read_details()
                continue
            self._change(start_tutorial)
            return

    def path_points(self):
        if self.farm.tutorial.status != 'active':
            return set()
        hint = tutorial_hint(self.farm)
        return set(hint.path) if hint and hint.area == self.farm.area else set()

    def draw_curses(self):
        if self.farm.tutorial.status != 'active':
            return
        hint = tutorial_hint(self.farm)
        if hint is None:
            return
        height, width = self.ui._screen.getmaxyx()
        # The base map uses a compact fallback with controls on row 4.
        if height < 10 or width < 22:
            return
        for row, text, color in ((2, self._title(), 'yellow'),
                                 (height - 4, hint.body, 'cyan'),
                                 (height - 3, f'{hint.key} · T: hướng dẫn', 'yellow')):
            self.ui._put(row, 0, text.ljust(width), color)

    def draw_text(self):
        if self.farm.tutorial.status != 'active':
            return
        hint = tutorial_hint(self.farm)
        if hint is not None:
            self.ui.wrapped(self._title(), 'gold')
            self.ui.wrapped(hint.body)
            self.ui.wrapped(f'{hint.key} · T: hướng dẫn', 'dim')
