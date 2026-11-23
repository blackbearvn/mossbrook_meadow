# Terminal Farm Implementation Plan

> **For agentic workers:** Execute inline with superpowers:executing-plans;
> use superpowers:test-driven-development and verify each deliverable.

**Goal:** Hoàn thành game nông trại Python chơi được ngay trong terminal.

**Architecture:** Luật chơi độc lập giao diện; lưu JSON nguyên tử;
menu nhập theo dòng dùng được trên terminal thật và đầu vào chuyển hướng.

**Tech Stack:** Python 3.10+, dataclasses, json, pathlib, unittest, ANSI.

**Spec:** `docs/superpowers/specs/2026-11-21-terminal-farm-design.md`

## Global Constraints

- Python 3.10 trở lên, chỉ dùng thư viện chuẩn, giao diện tiếng Việt.
- Chạy bằng `python3 main.py`; không cần mạng, tài khoản hoặc cài thư viện.
- Không ghi đè file lưu lỗi; `--new` sao lưu file lưu cũ.
- Không tạo Git worktree hoặc commit: thư mục hiện tại không phải Git repo.

## Task 1: Luật chơi

**Files:** `farmgame/__init__.py`, `farmgame/model.py`, `tests/test_model.py`.

**Interfaces:** `Farm`, `Plot`, `GameError`, `CROPS`; `Farm.plant(coordinate,
crop)`, `water(coordinate)`, `harvest(coordinate)`, `clear(coordinate)`,
`sleep(next_weather)`, `buy_seeds(crop, quantity)`, `sell_all()`,
`upgrade(kind)`, `work()` trả thông báo tiếng Việt hoặc ném `GameError`.

- [x] Viết test vòng chơi và các ranh giới tài nguyên. Ví dụ:
  ```python
  farm.plant("A1", "ca_rot")
  farm.water("A1")
  farm.sleep("sunny")
  farm.water("A1")
  farm.sleep("sunny")
  farm.harvest("A1")
  farm.sell_all()
  self.assertEqual(farm.coins, 144)
  self.assertEqual(farm.harvested, 1)
  ```
- [x] Chạy `python3 -m unittest discover -s tests -p test_model.py -v`
  để thấy lỗi do thiếu mô hình.
- [x] Cài đặt mô hình theo spec: 5 giống cây; các thao tác kiểm tra điều kiện
  trước khi trừ tài nguyên; qua ngày xử lý cây bằng thời tiết ngày cũ;
  mở rộng giữ tọa độ cây hiện có; làm thuê tốn 4 năng lượng, nhận 6 xu.
- [x] Chạy lại cùng lệnh và sửa đến khi mọi test đạt.

## Task 2: Lưu game

**Files:** `farmgame/storage.py`, `tests/test_storage.py`.

**Interfaces:** `save_game(farm, path)`, `load_game(path) -> Farm`,
`backup_save(path) -> Path`, `SaveError`.

- [x] Viết test chu trình ghi/đọc giữ nguyên tiến trình, file JSON lỗi,
  dữ liệu sai, phiên bản không hỗ trợ và sao lưu trước ván mới.
  ```python
  save_game(farm, path)
  restored = load_game(path)
  self.assertEqual(restored.plots["A1"].crop, "ca_rot")
  self.assertEqual(restored.coins, farm.coins)
  ```
- [x] Chạy `python3 -m unittest discover -s tests -p test_storage.py -v`
  và xác nhận chức năng còn thiếu.
- [x] Cài đặt JSON phiên bản 1, kiểm tra các giá trị trước khi tạo `Farm`,
  ghi file tạm trong cùng thư mục rồi thay thế nguyên tử; sao lưu tên có
  thời gian để giữ ván cũ.
- [x] Chạy lại test lưu game và toàn bộ test mô hình.

## Task 3: Terminal và hướng dẫn

**Files:** `farmgame/terminal.py`, `main.py`, `tests/test_cli.py`,
`README.md`, `.gitignore`.

**Interfaces:** `TerminalGame(farm, save_path, color, clear_screen).run()`;
`main()` trả mã thoát, `--save`, `--new`, `--name`, `--no-color`,
`--no-clear`, `--help`.

- [x] Viết test subprocess cho trồng/tưới/ngủ/thu hoạch/bán/lưu,
  tiếp tục file cũ, đầu vào sai, EOF và `--new` bảo toàn ván trước.
  ```python
  result = subprocess.run(
      [sys.executable, "main.py", "--save", str(path), "--no-color"],
      input="0\n", text=True, capture_output=True, timeout=10,
  )
  self.assertEqual(result.returncode, 0)
  self.assertTrue(path.exists())
  ```
- [x] Chạy `python3 -m unittest discover -s tests -p test_cli.py -v`
  và xác nhận CLI còn thiếu.
- [x] Cài đặt dashboard ruộng, trạng thái cây, túi đồ, mục tiêu, menu số,
  chọn nhiều tọa độ hoặc `all`, thông báo tự lưu, hướng dẫn và thoát an toàn.
- [x] Viết README tiếng Việt có lệnh chạy, điều khiển, luật thời tiết và lưu.
- [x] Chạy `python3 -m unittest discover -s tests -v`,
  `python3 -m compileall -q main.py farmgame tests`, và smoke test TTY thật.
- [x] Đối chiếu spec, cập nhật các checkbox và báo lệnh chạy cho người dùng.

## Verification Notes

- 35 bài kiểm tra hành vi, lưu file và CLI; không cần thư viện kiểm thử ngoài.
- Đã chơi vòng lúa mì trồng–tưới–ngủ–thu hoạch–bán trong TTY.
- PTY có controlling terminal xác nhận màu ANSI và Ctrl+C tạo file lưu,
  kết thúc với mã 0. Màn hình ban đầu chiếm 22 dòng, tối đa 79 cột.
- Rà soát mã độc lập không phát hiện lỗi cần sửa. Kiểm tra bổ sung đã sửa
  thông báo lưu thủ công: chỉ báo thành công khi ghi file thành công.
