#!/usr/bin/env python3
"""Start Mossbrook Meadow with Python 3.10 or newer."""

import argparse
import os
import sys
import unicodedata
from pathlib import Path

from farmgame.model import Farm
from farmgame.storage import SaveError, backup_save, load_game
from farmgame.terminal import TerminalGame


ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mossbrook Meadow — game nông trại tiếng Việt trên terminal.",
        epilog="WASD đi, E tương tác, U hành trình và khôi phục làng, Z khung rộng, N nhiệm vụ, O auto, G hình, C nhân vật, M bản đồ, I túi, T tân thủ, Q lưu và về menu; mỏ khoáng ở Đồi Gió.",
    )
    parser.add_argument("--save", type=Path, default=ROOT / "saves" / "farm.json",
                        metavar="PATH", help="đường dẫn file lưu JSON")
    parser.add_argument("--new", action="store_true",
                        help="bắt đầu ván mới, sao lưu ván cũ trước")
    parser.add_argument("--name", default="Mossbrook Meadow", metavar="NAME",
                        help="tên nông trại cho ván mới (tối đa 28 ký tự)")
    parser.add_argument("--no-color", action="store_true", help="tắt màu ANSI")
    parser.add_argument("--ascii", action="store_true",
                        help="dùng ký tự ASCII đơn giản cho bản đồ (G để đổi)")
    parser.add_argument("--no-clear", action="store_true",
                        help="giữ lịch sử màn hình, dùng menu dòng")
    parser.add_argument("--text", action="store_true", help="dùng menu dòng thay cho bản đồ trực tiếp")
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument('--menu', action='store_true', help='hiện menu bắt đầu cả khi nhập theo dòng')
    startup.add_argument('--quick', action='store_true', help='vào thẳng ván đang lưu, bỏ menu bắt đầu')
    opening = parser.add_mutually_exclusive_group()
    opening.add_argument('--intro', action='store_true', help='xem đoạn mở đầu khi vào game')
    opening.add_argument('--skip-intro', action='store_true', help='bỏ qua đoạn mở đầu khi tạo nhân vật')
    args = parser.parse_args(argv)
    name = unicodedata.normalize("NFC", args.name.strip())
    if not 1 <= len(name) <= 28 or not name.isprintable():
        parser.error("Tên nông trại phải có 1–28 ký tự hiển thị được.")
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    explore = (not args.text and not args.no_clear and interactive
               and os.environ.get('TERM') not in (None, '', 'dumb'))
    if explore:
        try:
            import curses  # Available in the standard library on Unix terminals.
        except ImportError:
            explore = False
        else:
            try:
                curses.setupterm(term=os.environ['TERM'], fd=sys.stdout.fileno())
            except (curses.error, OSError, ValueError):
                explore = False
    try:
        save_path = args.save.expanduser().resolve()
        use_menu = args.menu or (interactive and not args.quick)
        force_new = args.new
        force_intro = args.intro
        while True:
            backup = None
            if use_menu:
                from farmgame.start_screen import run_startup
                result = run_startup(
                    save_path, graphical=explore, color=not args.no_color,
                    clear_screen=not args.no_clear, default_name=name,
                    force_new=force_new, force_intro=force_intro,
                    skip_intro=args.skip_intro, ascii_only=args.ascii,
                )
                if result.farm is None:
                    return result.exit_code
                farm = result.farm
                continuing = not result.created
                play_intro = result.play_intro
                force_new = force_intro = False
            else:
                continuing = save_path.exists() and not force_new
                if continuing:
                    farm = load_game(save_path)
                else:
                    if force_new and save_path.exists():
                        backup = backup_save(save_path)
                    farm = Farm(name=name, map_pages=True)
                play_intro = ((force_intro or not farm.intro_seen)
                              and not args.skip_intro)
                if args.skip_intro:
                    farm.intro_seen = True
                force_new = force_intro = False
            if explore:
                from farmgame.explore import ExplorerGame
                game = ExplorerGame(farm, save_path, color=not args.no_color,
                                    intro=play_intro, ascii_only=args.ascii)
            else:
                game = TerminalGame(farm, save_path, color=not args.no_color,
                                    clear_screen=not args.no_clear,
                                    intro=play_intro, ascii_only=args.ascii)
            # An explicit --quick session keeps its old one-shot exit; a game
            # opened from the title returns there when the player presses Q.
            game.quit_to_menu = use_menu
            if backup:
                game.messages = [f"Ván mới đã sẵn sàng. Bản sao ván cũ: {backup}"]
            elif continuing:
                game.messages = [f"Chào mừng trở lại {farm.name}! Tiếp tục ngày {farm.day}."]
            code = game.run()
            if getattr(game, 'return_to_menu', False):
                use_menu = True
                force_new = force_intro = False
                continue
            return code
    except (EOFError, KeyboardInterrupt):
        return 0
    except (SaveError, OSError) as error:
        print(f"Lỗi: {error}", file=sys.stderr)
        print("Dùng --new để tạo ván mới và giữ bản sao file lưu cũ.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
