"""Vietnamese, line-based terminal interface; no external packages needed."""

import os
import re
import shutil
import sys
import textwrap
from itertools import zip_longest
from pathlib import Path

from .model import CROPS, WEATHER, Farm, GameError
from .line_input import LineInput
from .progression import action_cost, sale_price
from .storage import SaveError, save_game


STYLES = {
    "title": "1;38;5;156",
    "green": "38;5;114",
    "gold": "38;5;222",
    "blue": "38;5;81",
    "red": "38;5;203",
    "dim": "38;5;245",
    "white": "1;38;5;255",
    # Semantic map roles.  The text client uses the same landscape palette
    # as the curses renderer so sand/lake/sea remain recognisable.
    "grass": "38;5;34",
    "forest": "38;5;28",
    "flower": "38;5;201",
    "soil": "38;5;130",
    "sand": "38;5;220",
    "lake": "38;5;121",
    "sea": "38;5;27",
    "path": "38;5;250",
    "stone": "38;5;244",
    "building": "38;5;214",
    "roof": "38;5;160",
    "furniture": "38;5;39",
    "door": "38;5;45",
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


class TerminalGame:
    def __init__(self, farm: Farm, save_path: Path, color: bool = True,
                 clear_screen: bool = True, intro: bool = False,
                 ascii_only: bool = False):
        self.farm = farm
        self.save_path = save_path
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        capable = os.environ.get("TERM") != "dumb"
        self.color = color and interactive and capable and "NO_COLOR" not in os.environ
        self.clear_screen = clear_screen and interactive and capable
        self.play_intro = intro
        from .map_art import supports_unicode
        self.unicode_map = not ascii_only and supports_unicode()
        self.unsaved = False
        self.return_to_menu = False
        self.quit_to_menu = True
        self.map_expanded = False
        self.messages = [
            "Bắt đầu: 1 trồng → 2 tưới → 7 ngủ. Gõ all để chọn cả ruộng."
        ]
        self.width = 80
        self._line_input = LineInput()
        from .tutorial_ui import TutorialCoach
        self.coach = TutorialCoach(self, farm, self.persist, text=True)
        from .activity_ui import ActivityUI
        self.activities = ActivityUI(self, farm, self.persist, text=True)

    def paint(self, text: str, style: str) -> str:
        return f"\033[{STYLES[style]}m{text}\033[0m" if self.color else text

    def say(self, text: str = "", style: str | None = None) -> None:
        print(self.paint(text, style) if style else text)

    def wrapped(self, text: str, style: str | None = None) -> None:
        for line in textwrap.wrap(text, width=self.width) or [""]:
            self.say(line, style)

    def ask(self, prompt: str) -> str:
        return self._line_input.read(self.paint(prompt, "blue")).strip()

    def poll_input(self, timeout: float) -> str | None:
        """Share buffered menu lines without blocking on a partial auto control."""
        return self._line_input.read(timeout=timeout)

    def _board(self) -> list[str]:
        farm = self.farm
        cell = min(9, max(4, (self.width - 5) // farm.size - 1))
        heading = "    " + "".join(f"{chr(65 + col):^{cell + 1}}"
                                    for col in range(farm.size))
        top = "   ┌" + "┬".join("─" * cell for _ in range(farm.size)) + "┐"
        lines = [self.paint(heading, "dim"), self.paint(top, "dim")]
        for row in range(farm.size):
            parts = [self.paint(f" {row + 1} │", "dim")]
            for col in range(farm.size):
                key = f"{chr(65 + col)}{row + 1}"
                plot = farm.plots[key]
                if not plot.crop:
                    label, style = "·", "dim"
                elif plot.dead:
                    label, style = f"{CROPS[plot.crop].symbol} !", "red"
                elif plot.ready:
                    label, style = f"{CROPS[plot.crop].symbol} *", "gold"
                else:
                    info = CROPS[plot.crop]
                    wet = farm.is_watered(key)
                    marker = "~" if wet else "."
                    label = (f"{info.symbol} {plot.growth}/{info.days}{marker}"
                             if cell >= 7 else f"{info.symbol}{plot.growth}{marker}")
                    style = "blue" if wet else "green"
                parts.append(self.paint(f"{label:^{cell}}", style))
                parts.append(self.paint("│", "dim"))
            lines.append("".join(parts))
        bottom = "   └" + "┴".join("─" * cell for _ in range(farm.size)) + "┘"
        lines.append(self.paint(bottom, "dim"))
        return lines

    def _inventory(self) -> list[str]:
        lines = [self.paint("KHO NHÀ         Hạt / Nông sản", "white")]
        for key, crop in CROPS.items():
            label = (f"{crop.symbol} {crop.name:<8} "
                     f"{self.farm.seeds[key]:>4} / {self.farm.produce[key]:<4}")
            lines.append(self.paint(label, "green" if self.farm.level >= crop.level
                                    else "dim"))
        total = sum(sale_price(self.farm, 'crop:' + key) * count
                    for key, count in self.farm.produce.items())
        lines.append(self.paint(f"Giá trị nông sản: {money(total)} xu", "gold"))
        return lines

    def draw(self) -> None:
        self.width = max(35, min(110, shutil.get_terminal_size((80, 24)).columns - 1))
        if self.clear_screen:
            print("\033[2J\033[H", end="")
        farm = self.farm
        self.wrapped(f"NÔNG TRẠI / {farm.name.upper()}", "title")
        self.say("─" * self.width, "dim")
        self.wrapped(f"NGÀY {farm.day:02} · {WEATHER[farm.weather]} · "
                     f"{money(farm.coins)} xu · Cấp {farm.level} ({farm.xp % 40}/40 KN)",
                     "gold")
        filled = farm.energy * 10 // farm.energy_limit
        bar = "█" * filled + "░" * (10 - filled)
        self.wrapped(f"Năng lượng [{bar}] {farm.energy}/{farm.energy_limit}"
                     f" · Máu {farm.hp}/{farm.max_hp}"
                     + (" · Tưới tự động: BẬT" if farm.sprinkler else ""), "green")
        board, inventory = self._board(), self._inventory()
        board_width = len(ANSI.sub("", board[1]))
        side_width = max(len(ANSI.sub("", line)) for line in inventory)
        if board_width + 3 + side_width <= self.width:
            for left, right in zip_longest(board, inventory, fillvalue=""):
                padding = " " * (board_width - len(ANSI.sub("", left)) + 3)
                self.say(left + padding + right)
        else:
            for line in board:
                self.say(line)
            stock = " · ".join(f"{crop.symbol}: {farm.seeds[key]}h/{farm.produce[key]}sp"
                               for key, crop in CROPS.items())
            self.wrapped(stock, "dim")
        self.wrapped(" · ".join(f"{crop.symbol} {crop.name}" for crop in CROPS.values()),
                     "dim")
        self.wrapped("· ô trống   ~ đủ nước   . cần tưới   * chín   ! héo", "dim")
        if farm.goal_complete:
            self.wrapped("CHÚC MỪNG! Bạn đã thành Chủ nông trại. Tiếp tục xây vườn nhé!", "title")
        else:
            self.wrapped(f"Mục tiêu: {farm.harvested}/30 thu hoạch · "
                         f"{money(farm.sales)}/1.000 xu doanh thu", "gold")
        self.say("─" * self.width, "dim")
        for line in (
            "[1] Trồng cây     [2] Tưới nước    [3] Thu hoạch / dọn cây héo",
            "[4] Mua hạt       [5] Bán tất cả   [6] Nâng cấp",
            f"[7] Ngủ / qua ngày   [8] Làm thuê (+{6 + 2 * farm.skills['foraging']} xu, "
            f"+{1 + farm.skills['foraging'] // 2} gỗ, -{action_cost(farm, 'work')} NL)",
            "[h] Hướng dẫn     [s] Lưu game     [0] Lưu & về menu",
            "[m] Bản đồ làng   [r] Khu vực / đi nhanh",
            "[i] Túi đồ / kho  [c] Nhân vật / nâng điểm",
            "[f] Bảng cánh đồng  [b] Khu chuồng  [k] Bộ sưu tầm cá",
            "Mỏ khoáng: vào từ Đồi Gió (76,6); đào quặng, rèn đồ và vào Hang Sâu bằng e.",
            "Trong nhà: đứng cạnh bếp K rồi e để nấu ăn",
            "[t] Lan hướng dẫn tân thủ từng bước",
            "[n] Nhiệm vụ hằng ngày   [o] Chế độ auto",
            "[g] Đổi hình bản đồ Unicode / ASCII   [z] Khung bản đồ rộng",
        ):
            self.wrapped(line)
        self.say("─" * self.width, "dim")
        for message in self.messages:
            self.wrapped(message, "blue")
        if self.unsaved:
            self.wrapped("CHƯA LƯU ĐƯỢC: sửa lỗi đường dẫn/quyền ghi rồi nhấn s để thử lại.", "red")
        self.coach.draw_text()

    def choose_crop(self, planting: bool = False) -> str | None:
        self.say()
        self.say("HẠT GIỐNG" if planting else "CỬA HÀNG HẠT GIỐNG", "title")
        quantity = 2 if self.farm.skills['farming'] >= 3 else 1
        self.wrapped(f"Mỗi cây cho {quantity} nông sản. Số ngày = số đêm được tưới nước.", "dim")
        for number, (key, crop) in enumerate(CROPS.items(), 1):
            lock = f"KHÓA: cấp {crop.level}" if self.farm.level < crop.level else ""
            self.wrapped(f"[{number}] {crop.name:<8} · Hạt {crop.seed_price} xu · "
                         f"Bán {sale_price(self.farm, 'crop:' + key)} xu · {crop.days} ngày · "
                         f"Có {self.farm.seeds[key]} hạt {lock}",
                         "dim" if lock else "green")
        choice = self.ask("Chọn giống [1–5, 0 = hủy]: ")
        if choice == "0":
            self.messages = ["Đã hủy chọn giống."]
            return None
        if choice not in {str(i) for i in range(1, 6)}:
            raise GameError("Chọn một giống từ 1 đến 5, hoặc 0 để hủy.")
        key = list(CROPS)[int(choice) - 1]
        if self.farm.level < CROPS[key].level:
            raise GameError(f"{CROPS[key].name} mở khóa ở cấp {CROPS[key].level}.")
        return key

    def choose_plots(self, eligible) -> list[str]:
        answer = self.ask("Chọn ô (A1 A2, all; Enter = all; 0 = hủy): ")
        if answer == "0":
            return []
        if answer.lower() in ("", "all", "tatca", "tất cả"):
            return [key for key, plot in self.farm.plots.items() if eligible(key, plot)]
        keys = list(dict.fromkeys(answer.upper().replace(",", " ").split()))
        for key in keys:
            if key not in self.farm.plots:
                raise GameError(f"Ô '{key}' không hợp lệ. Chưa thực hiện thao tác nào.")
        return keys

    def batch(self, label: str, keys: list[str], action) -> bool:
        if not keys:
            self.messages = ["Không có ô phù hợp hoặc bạn đã hủy thao tác."]
            return False
        successes, errors = [], []
        previous_level = self.farm.level
        for key in keys:
            try:
                successes.append(action(key))
            except GameError as error:
                if str(error) not in errors:
                    errors.append(str(error))
        self.messages = []
        if successes:
            self.messages.append(successes[0] if len(keys) == 1
                                 else f"{label}: {len(successes)}/{len(keys)} ô.")
        if self.farm.level > previous_level:
            self.messages.append(f"LÊN CẤP {self.farm.level}! Đã mở thêm giống cây mới.")
        if errors:
            self.messages.append(errors[0])
        return bool(successes)

    def plant(self) -> bool:
        key = self.choose_crop(planting=True)
        if key is None:
            return False
        if self.farm.seeds[key] == 0:
            raise GameError("Bạn đã hết hạt giống này. Mua thêm bằng phím 4.")
        targets = self.choose_plots(lambda _, plot: plot.crop is None)
        return self.batch(f"Trồng {CROPS[key].name}", targets,
                          lambda coordinate: self.farm.plant(coordinate, key))

    def water(self) -> bool:
        targets = self.choose_plots(lambda key, plot: plot.crop and not plot.dead
                                    and not plot.ready and not self.farm.is_watered(key))
        return self.batch("Tưới nước", targets, self.farm.water)

    def harvest(self) -> bool:
        targets = self.choose_plots(lambda _, plot: plot.ready or plot.dead)
        return self.batch("Thu hoạch / dọn cây héo", targets,
                          lambda key: self.farm.clear(key) if self.farm.plots[key].dead
                          else self.farm.harvest(key))

    def shop(self) -> bool:
        key = self.choose_crop()
        if key is None:
            return False
        answer = self.ask("Số hạt muốn mua [Enter = 1, max = mua tối đa, 0 = hủy]: ")
        if answer == "0":
            self.messages = ["Đã hủy mua hạt."]
            return False
        if answer.lower() == "max":
            quantity = self.farm.coins // CROPS[key].seed_price
        else:
            try:
                quantity = int(answer or "1")
            except ValueError:
                raise GameError("Số lượng phải là số nguyên dương.") from None
        self.messages = [self.farm.buy_seeds(key, quantity)]
        return True

    def sell(self) -> bool:
        self.messages = [self.farm.sell_all()]
        return True

    def upgrade(self) -> bool:
        self.say()
        self.say("GÓC NÂNG CẤP", "title")
        options = [
            ("land", f"Mở rộng ruộng lên {min(6, self.farm.size + 1)} × "
             f"{min(6, self.farm.size + 1)}"),
            ("energy", f"Tăng năng lượng tối đa lên {30 + 4 * self.farm.attributes['endurance']}"),
            ("sprinkler", "Tưới tự động cho toàn bộ ruộng, vĩnh viễn"),
            ("barn", "Mở rộng chuồng lên 8 chỗ"),
        ]
        for number, (kind, label) in enumerate(options, 1):
            try:
                price = f"{self.farm.upgrade_cost(kind)} xu"
            except GameError:
                price = "ĐÃ TỐI ĐA"
            self.wrapped(f"[{number}] {label} · {price}", "green")
        answer = self.ask("Chọn nâng cấp [1–4, 0 = hủy]: ")
        if answer == "0":
            self.messages = ["Đã hủy nâng cấp."]
            return False
        if answer not in ("1", "2", "3", "4"):
            raise GameError("Chọn nâng cấp từ 1 đến 4.")
        self.messages = [self.farm.upgrade(options[int(answer) - 1][0])]
        return True

    def sleep(self) -> bool:
        thirsty = sum(bool(plot.crop and not plot.dead and not plot.ready
                           and not self.farm.is_watered(key))
                      for key, plot in self.farm.plots.items())
        if thirsty:
            answer = self.ask(f"Còn {thirsty} cây chưa được tưới. Vẫn ngủ? [y/N]: ")
            if answer.lower() not in ("y", "yes", "c", "co", "có"):
                self.messages = ["Chưa qua ngày. Tưới cây bằng phím 2 nhé!"]
                return False
        self.messages = [self.farm.sleep()]
        return True

    def work(self) -> bool:
        self.messages = [self.farm.work()]
        return True

    def toggle_map_style(self) -> bool:
        from .map_art import supports_unicode
        if not self.unicode_map and not supports_unicode():
            self.messages = ['Terminal không hỗ trợ bộ ký tự này; đang dùng ASCII thường.']
            return False
        self.unicode_map = not self.unicode_map
        self.messages = ['Bản đồ: ký tự Unicode.' if self.unicode_map else 'Bản đồ: ASCII thường.']
        return False

    def toggle_map_width(self) -> bool:
        self.map_expanded = not self.map_expanded
        self.messages = ['Khung bản đồ: RỘNG (nhiều ô hơn).'
                         if self.map_expanded else 'Khung bản đồ: tiêu chuẩn.']
        return False

    def help(self) -> bool:
        self.say()
        self.say("SỔ TAY NHÀ NÔNG", "title")
        for line in (
            "1. Trồng: nhấn 1, chọn giống, rồi nhập ô (A1) hoặc nhiều ô (A1 A2).",
            "2. Tưới: nhấn 2 và nhập all để tưới mọi cây cần nước. Mưa tự tưới.",
            "3. Ngủ: nhấn 7. Cây được tưới lớn thêm 1 bước, năng lượng hồi đầy.",
            "4. Thu hoạch: cây có dấu * đã chín; nhấn 3 rồi all. Nhấn 5 để bán.",
            "5. Mua hạt bằng phím 4; kiếm kinh nghiệm để mở giống sinh lời hơn.",
            "6. Nâng cấp bằng phím 6. Hệ thống tưới hoạt động ngay khi mua.",
            "Cây thiếu nước 3 đêm liên tiếp sẽ héo (!). Phím 3 dọn cây héo.",
            "Cây đã chín không cần tưới và không héo. Tay nghề trồng trọt bậc 3 cho 2 sản phẩm.",
            f"Trồng/thu: {action_cost(self.farm, 'plant')} NL; tưới/dọn: 1 NL. "
            f"Làm thuê: {action_cost(self.farm, 'work')} NL → {6 + 2 * self.farm.skills['foraging']} xu.",
            "Ô có CR 1/2~: cà rốt lớn 1/2 bước, đã đủ nước. Dấu . là cần tưới.",
            "Terminal hẹp hiển thị CR1~: số là số đêm cây đã lớn.",
            "Mục tiêu: thu 30 nông sản và bán tổng cộng 1.000 xu. Không giới hạn ngày.",
            "Game tự lưu sau mỗi hành động. s lưu ngay; 0 lưu và về menu.",
            "Ctrl+C hoặc hết đầu vào cũng lưu rồi thoát. Enter/all chọn mọi ô phù hợp.",
            "m mở bản đồ: w/a/s/d đi, e tương tác, i xem túi, b trở về menu.",
            "Vào nhà H để xem TV V, dùng rương C, bếp K nấu ăn và giường Z. Dự báo khớp ngày mai.",
            "Chuồng B nuôi gà/vịt/thỏ/bò/cừu/dê/heo; đứng cạnh hồ ~ và nhấn e để câu cá.",
            "Bản đồ chia trang; cánh đồng ở (26,42), xa nhà về phía nam. Đi qua đường ở rìa trang để sang khu kế; R đi nhanh.",
            "NPC là số 1–5: đứng kề rồi e để chào hỏi, công việc, chuyện làng, ước mơ, kỷ niệm.",
            "Trong bản đồ dòng, atlas xem toàn cảnh, j xem chân dung, sở thích và quan hệ dân làng.",
            "f xem bảng cánh đồng; b xem 3 khu chuồng mở theo cấp; k xem bộ sưu tầm cá.",
            "c mở nhân vật: XP lên cấp nhận điểm nâng thuộc tính và tay nghề; X đổi điểm dư khi đã tối đa.",
            "Biểu tượng: ☀/☁/☂ thời tiết · ♥ sức/Độ thân · ◆ xu · ✧ XP · ▤ túi · ⌖ bản đồ.",
            "Tay nghề: ⚘ trồng trọt · ≈ câu cá · ♱ chăn nuôi · ⚒ kiếm sống · ☾ tập trung.",
            "NPC hỏi, bạn chọn câu đáp, rồi NPC phản hồi và hỏi tiếp; 0 hủy hội thoại.",
            "t bật hướng dẫn thực hành: Lan chỉ đường và đợi bạn làm đúng từng bước.",
            "g đổi ký tự bản đồ Unicode/ASCII; --ascii mở game bằng bản đồ đơn giản.",
            "Màu map: cát vàng, hồ xanh lục nhạt, biển xanh dương, rừng xanh đậm.",
            "n xem 4 nhiệm vụ/ngày và nhận thưởng xu, XP; ngủ sẽ đổi nhiệm vụ.",
            "o mở auto: toàn bộ/trồng trọt/chăn nuôi/câu cá/đào khoáng/hang, chọn ngày và tốc độ.",
            "Mỏ Khoáng ở Đồi Gió (76,6): e để vào, đứng cạnh đá và e để đào quặng.",
            "Trong mỏ: F lò rèn 5 slot (mũ, kiếm, giáp, quần, giày), G hang sâu, D ra ngoài.",
            "Quặng dùng để rèn; ngủ qua ngày sẽ làm đầy lại các tảng đá trong mỏ.",
            "Hang Sâu cần kiếm bậc Hiếm: 1/Enter tấn công, 2 uống thuốc, 3 rút lui, 4 đỡ đòn, 5 kỹ năng (3 MP).",
            "Thành tựu: mở c rồi chọn a; quái báo ý định trước mỗi lượt.",
            "z đổi khung bản đồ rộng (ô hẹp, nhìn được nhiều đất hơn).",
            "Auto dòng: p tạm dừng, o dừng, +/- đổi tốc độ, gõ rồi Enter.",
        ):
            self.wrapped(line)
        self.wrapped(f"File lưu: {self.save_path}", "dim")
        self.ask("Nhấn Enter để về ruộng... ")
        self.messages = ["Chúc bạn một mùa bội thu!"]
        return False

    def persist(self) -> bool:
        try:
            save_game(self.farm, self.save_path)
            self.unsaved = False
            return True
        except SaveError as error:
            self.unsaved = True
            self.messages.append(str(error))
            return False

    def check_achievements(self) -> None:
        from .achievements import sync_achievements
        unlocked = sync_achievements(self.farm)
        if not unlocked:
            return
        for achievement in unlocked:
            self.messages.append(
                f'Mở khóa thành tựu: {achievement.name} '
                f'(+{achievement.reward} điểm)!')
        self.persist()

    def finish(self) -> int:
        if self.persist():
            self.wrapped(f"Đã lưu game tại {self.save_path}. Hẹn gặp lại!", "green")
            return 0
        self.wrapped(self.messages[-1], "red")
        self.wrapped("Tiến trình chưa được lưu.", "red")
        return 1

    def run(self) -> int:
        from .text_activities import (character_menu, map_mode, show_barn,
                                  show_farm, show_fish_collection, show_inventory,
                                  show_regions)
        actions = {
            "1": self.plant, "2": self.water, "3": self.harvest,
            "4": self.shop, "5": self.sell, "6": self.upgrade,
            "7": self.sleep, "8": self.work, "h": self.help,
            "m": lambda: map_mode(self), "r": lambda: show_regions(self),
            "i": lambda: show_inventory(self),
            "f": lambda: show_farm(self), "b": lambda: show_barn(self),
            "k": lambda: show_fish_collection(self),
            "c": lambda: character_menu(self),
            "t": lambda: self.coach.panel(),
            "n": self.activities.daily_menu,
            "o": self.activities.open_auto,
            "g": self.toggle_map_style,
            "z": self.toggle_map_width,
        }
        try:
            if self.play_intro:
                self.draw()
                from .start_screen import TextUI
                if TextUI().intro(self.farm):
                    self.farm.intro_seen = True
                    self.persist()
                self.play_intro = False
            self.coach.offer()
            self.coach.sync()
            while True:
                self.draw()
                choice = self.ask("Bạn muốn làm gì? > ").lower()
                try:
                    if choice in ("0", "q", "quit", "exit"):
                        if self.persist():
                            if self.quit_to_menu:
                                self.return_to_menu = True
                                self.wrapped("Đã lưu. Trở về menu chính.", "green")
                            else:
                                self.wrapped(f"Đã lưu game tại {self.save_path}. Hẹn gặp lại!", "green")
                            return 0
                        continue
                    if choice in ("s", "save"):
                        self.messages = []
                        if self.persist():
                            self.messages = ["Đã lưu tiến trình."]
                        continue
                    if not choice:
                        continue
                    if choice not in actions:
                        raise GameError("Chọn 1–8, m bản đồ, r khu vực, f ruộng, b chuồng, "
                                    "k cá, n nhiệm vụ, o auto, t tân thủ, z khung rộng, h trợ giúp "
                                    "hoặc 0 lưu và về menu.")
                    if actions[choice]():
                        self.persist()
                    self.check_achievements()
                except GameError as error:
                    self.messages = [str(error)]
        except (EOFError, KeyboardInterrupt):
            self.say()
            return self.finish()
        finally:
            self._line_input.close()
