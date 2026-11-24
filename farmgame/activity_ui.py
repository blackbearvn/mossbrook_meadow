"""Daily board and interruptible automation shared by both terminal frontends."""

import math
import time

from .model import GameError


MODES = {'all': '❋ Toàn bộ nông trại', 'farm': '❦ Trồng trọt',
         'ranch': '▴ Chăm vật nuôi', 'fish': '◈ Câu cá',
         'mine': '▣ Đào khoáng sản', 'dungeon': '☠ Hang Sâu'}
SPEEDS = (('Chậm', 0.18), ('Vừa', 0.06), ('Nhanh', 0.008),
          ('Siêu nhanh', 0.003))
# A fast auto loop produces a message every tick. Only milestones deserve a
# toast; routine walking, mining and combat stay in the message log.
AUTO_TOAST_MARKERS = ('lò rèn', 'lên cấp', 'chào ngày', 'hang sâu',
                      'ngã xuống', 'chủ hang', 'mua ', 'thuốc',
                      'nhận ', 'hoàn tất', 'dừng', 'lỗi', 'không thể',
                      'sạch bóng', 'chinh phục', 'kỷ lục')


class ActivityUI:
    def __init__(self, ui, farm, save_callback, *, text=False):
        self.ui = ui
        self.farm = farm
        self.save_callback = save_callback
        self.text = text
        self.auto = None
        self.speed = 1
        self._last_tick = None
        self._last_checkpoint = None
        self._moves_since_save = 0
        self._dirty = False

    @property
    def running(self):
        return self.auto is not None

    @property
    def read_timeout_ms(self):
        if not self.running or self.auto.paused:
            return 100
        return min(100, max(1, math.ceil(SPEEDS[self.speed][1] * 1000)))

    def _log(self, message, *, toast=True):
        if not message:
            return
        if self.text:
            self.ui.messages.append(str(message))
            del self.ui.messages[:-100]
        else:
            self.ui._log(message, toast=toast)

    def _choose(self, title, options, details=(), **kwargs):
        if not self.text:
            return self.ui._choose(title, options, details, **kwargs)
        self.ui.say(title, 'title')
        for line in details:
            self.ui.wrapped(line)
        for index, label in enumerate(options, 1):
            self.ui.wrapped(f'[{index}] {label}')
        self.ui.wrapped('[0] Quay lại')
        while True:
            answer = self.ui.ask('Chọn số: ').lower()
            if answer in ('', '0', 'q', 'esc'):
                return None
            if answer.isdecimal() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.ui.wrapped('Chọn số trong danh sách hoặc 0 để quay lại.')

    def _daily_board(self):
        from .daily import QUESTS
        from .artwork import quest_icon, symbol
        from .catalog import FISH_TYPES
        from .tui import progress_bar
        unicode = getattr(self.ui, 'unicode_map', True)
        lines = []
        for index, task in enumerate(self.farm.daily.tasks, 1):
            definition = QUESTS[task.kind]
            if task.claimed:
                status = 'Đã nhận'
            elif task.progress >= task.target:
                status = f'nhận {definition.coins} xu + {definition.xp} XP'
            else:
                status = 'đang làm'
            unit = ' xu' if task.kind == 'sell' else ''
            bar = progress_bar(task.progress / task.target, 8, unicode=unicode)
            lines.append(
                f'{quest_icon(task.kind, unicode=unicode)} {index}. {definition.name}  '
                f'{bar} {task.progress}/{task.target}{unit} · {status}')
        lines.append(f'{symbol("star", unicode=unicode)} Làm xong rồi chọn nhận thưởng; ngủ để đổi bảng.')
        lines.append(f'{symbol("fish", unicode=unicode)} Bộ sưu tầm cá: '
                     f'{self.farm.fish_species}/{len(FISH_TYPES)} loài · '
                     f'{self.farm.fish_points} điểm · nhấn K để xem.')
        return lines

    def daily_menu(self):
        from .daily import ensure_daily, claim_all, claim_quest, QUESTS
        from .artwork import symbol
        unicode = getattr(self.ui, 'unicode_map', True)
        coin = symbol('coin', unicode=unicode)
        before_day = self.farm.daily.day
        ensure_daily(self.farm)
        if self.farm.daily.day != before_day:
            self.save_callback()
        while True:
            ready = [(index, task) for index, task in enumerate(self.farm.daily.tasks)
                     if task.progress >= task.target and not task.claimed]
            options = [f'{coin} Nhận tất cả thưởng đã hoàn thành']
            options += [f'{coin} Nhận thưởng: {QUESTS[task.kind].name}'
                        for _, task in ready]
            choice = self._choose(f'NHIỆM VỤ NGÀY {self.farm.day}', options,
                                  self._daily_board(), close_keys=('n', 'N'))
            if choice is None:
                return False
            try:
                message = (claim_all(self.farm) if choice == 0
                           else claim_quest(self.farm, ready[choice - 1][0]))
                self._log(message)
                if ready:
                    self.save_callback()
            except GameError as error:
                self._log(error)

    def open_auto(self):
        if self.running:
            self.stop()
            return False
        choice = self._choose('CHẾ ĐỘ AUTO', list(MODES.values()), [
            'Auto tự đi bộ và thực hiện thao tác thật, dùng năng lượng/vật phẩm đang có.',
            'Toàn bộ: việc ngày (đào, rèn, nấu, Hang Sâu), ruộng, vật nuôi, câu cá, giao tiếp, mua/bán, nâng cấp và ngủ.',
            'Đào khoáng: tự vào mỏ, đào đá, rèn cúp và mang quặng về ngủ.',
            'Hang Sâu: tự rèn kiếm/giáp, mua thuốc và chiến đấu từng tầng.',
            'Chế độ riêng chỉ làm lĩnh vực đã chọn, rồi nghỉ sang ngày tiếp theo.',
            'Auto giữ quặng và thuốc để rèn, không bán mất nguyên liệu quý.',
            'Chỉ Toàn bộ mới hoàn tất hướng dẫn đang chạy; chế độ riêng không tự phân bổ điểm.',
        ])
        if choice is None:
            return False
        mode = tuple(MODES)[choice]
        duration = self._choose('AUTO · THỜI GIAN', [
            '1 ngày', '3 ngày', '7 ngày', 'Liên tục đến khi bạn dừng',
        ])
        if duration is None:
            return False
        speed = self._choose('AUTO · TỐC ĐỘ', [label for label, _ in SPEEDS], [
            'Space/P: tạm dừng · O/Esc: dừng · +/-: tốc độ · WASD: lấy lại điều khiển.',
            'Chế độ dòng dùng p, o, +, - rồi Enter; giữ đầu vào mở khi xem auto.',
        ])
        if speed is None:
            return False
        from .automation import AutoOptions
        self.start(AutoOptions(mode=mode, days=(1, 3, 7, 0)[duration]), speed=speed)
        if self.text and self.running:
            self.run_text_auto()
        return False

    def start(self, options, *, speed=1):
        from .automation import Automation
        if self.running:
            self.stop()
        self.auto = Automation(self.farm, options)
        self.speed = max(0, min(len(SPEEDS) - 1, speed))
        self._last_tick = self._last_checkpoint = None
        self._moves_since_save = 0
        self._dirty = False
        self._log(f'AUTO · {MODES[options.mode]} · '
                  + (f'{options.days} ngày.' if options.days else 'Chạy liên tục.'))
        if not self.save_callback():
            self._save_failed()

    def _save_failed(self):
        if self.auto:
            self.auto.stop()
        self.auto = None
        self._log('Auto đã dừng vì chưa lưu được tiến trình. Kiểm tra lỗi lưu trước khi chạy tiếp.')

    def _checkpoint(self, now=None):
        if not self.save_callback():
            self._save_failed()
            return False
        self._dirty = False
        self._moves_since_save = 0
        self._last_checkpoint = now
        return True

    def stop(self):
        if not self.running:
            return
        summary = self.auto.summary
        self.auto.stop()
        self.auto = None
        self._log(f'Đã dừng auto. {summary}')
        self._checkpoint()

    def control(self, key):
        """Consume auto controls; ordinary movement stops auto and falls through."""
        if not self.running:
            return False
        key = key.lower() if isinstance(key, str) else key
        if key in (' ', 'p'):
            self.auto.paused = not self.auto.paused
            self._last_tick = None
            self._log('Auto tạm dừng.' if self.auto.paused else 'Auto tiếp tục.')
            self._checkpoint()
            return True
        if key in ('o', '\x1b'):
            self.stop()
            return True
        if key in ('+', '='):
            self.speed = min(len(SPEEDS) - 1, self.speed + 1)
            return True
        if key == '-':
            self.speed = max(0, self.speed - 1)
            return True
        directions = {'w', 'a', 's', 'd', 'e', 'q', 'f', 'b', 'k'}
        curses = getattr(self.ui, '_curses', None)
        if curses is not None:
            directions.update(getattr(curses, name, None) for name in
                              ('KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT'))
            directions.discard(None)
        if key in directions:
            self.stop()
        return False

    def tick(self, now=None):
        if not self.running or self.auto.paused:
            return False
        now = time.monotonic() if now is None else now
        if self._last_tick is not None and now - self._last_tick < SPEEDS[self.speed][1]:
            return False
        self._last_tick = now
        if self._last_checkpoint is None:
            self._last_checkpoint = now
        result = self.auto.step()
        message = str(result.message)
        important = any(marker in message.lower()
                        for marker in AUTO_TOAST_MARKERS)
        self._log(result.message, toast=important)
        self._dirty |= result.changed or result.moved
        self._moves_since_save += int(result.moved)
        if result.changed or (self._dirty and (self._moves_since_save >= 12
                                              or now - self._last_checkpoint >= 2)):
            if not self._checkpoint(now):
                return True
        if result.done:
            summary = self.auto.summary
            self.auto = None
            self._log(f'AUTO HOÀN TẤT · {summary}')
            self._checkpoint(now)
        return True

    def path_points(self):
        return self.auto.path_points() if self.running else set()

    def status_lines(self):
        if not self.running:
            return []
        state = 'TẠM DỪNG' if self.auto.paused else 'ĐANG CHẠY'
        lines = [f'AUTO {state} · {MODES[self.auto.options.mode]} · {SPEEDS[self.speed][0]}',
                 f'{self.auto.current_task} · {self.auto.summary}',
                 'Space/P: tạm dừng · O/Esc: dừng · +/-: tốc độ · WASD: chơi tay']
        round_ = self.auto.fishing_round
        if round_ is not None and not round_.done:
            lines[1] = (f'Đang câu: {round_.progress:.0%} · '
                        f'Cá {round_.target:.0%} / thanh {round_.bar:.0%}')
        return lines

    def draw_curses(self):
        if not self.running:
            return
        height, width = self.ui._screen.getmaxyx()
        lines = self.status_lines()
        if height < 10 or width < 22:
            self.ui._put(2, 0, 'AUTO · O/Esc dừng', 'yellow')
            return
        for row, line in zip((2, height - 4, height - 3), lines):
            self.ui._put(row, 0, line.ljust(width), 'yellow')

    def run_text_auto(self):
        """Poll the same complete-line queue used by all manual text prompts."""
        from .text_activities import _draw_map
        self.ui.wrapped('AUTO: p = tạm dừng/tiếp tục; o = dừng; +/- = tốc độ (gõ rồi Enter).')
        last_draw = 0.0
        try:
            while self.running:
                now = time.monotonic()
                stepped = self.tick(now)
                if stepped and now - last_draw >= 0.35:
                    _draw_map(self.ui)
                    last_draw = now
                if not self.running:
                    break
                timeout = min(0.1, SPEEDS[self.speed][1])
                command = self.ui.poll_input(timeout)
                if command is None:
                    continue
                command = command.strip().lower()
                if command in ('q', '0'):
                    self.stop()
                    break
                self.control(command)
        except (EOFError, KeyboardInterrupt):
            self.stop()
            raise
