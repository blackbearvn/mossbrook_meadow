# Village Expansion Implementation Plan

> Execute independent modules with superpowers:dispatching-parallel-agents,
> integrate in the current workspace, use test-driven-development and final review.

**Goal:** Chơi nông trại qua bản đồ di chuyển, câu cá, chăn nuôi, nhà/tivi/rương.
**Architecture:** Shared catalog and Farm state; pure world/activity modules;
curses exploration UI plus compatible text menu; versioned atomic JSON saves.
**Tech Stack:** Python 3.10+, dataclasses, curses, json, unittest, PTY.
**Spec:** `docs/superpowers/specs/2026-11-21-village-expansion-design.md`.

## Global Constraints

- Python 3.10+, chỉ thư viện chuẩn, giao diện tiếng Việt.
- Tôn trọng các API chính xác trong spec; tránh vòng import.
- Không Git commit/worktree: thư mục hiện tại không phải Git repo.
- Mỗi tác vụ chỉ sửa file mình sở hữu, không ghi đè thay đổi của tác vụ khác.
- Các tác vụ không phụ thuộc triển khai nội bộ của nhau, chỉ hợp đồng API.

## 1. Trạng thái, kho đồ và migration — root

Files: catalog.py, model.py, inventory.py, storage.py, main.py, terminal.py,
tests/test_inventory.py, tests/test_storage.py, tests/test_cli.py, README.md.

- [x] Viết test dự báo/cất-rút/bán đồ và migration v1, thấy fail trước khi thêm API.
  ```python
  farm.items['milk'] = 2
  transfer_item(farm, 'milk', 1, 'deposit')
  farm.sell_all()
  self.assertEqual(farm.chest['milk'], 1)
  self.assertEqual(farm.coins, 165)
  tomorrow = farm.forecast
  farm.sleep()
  self.assertEqual(farm.weather, tomorrow)
  ```
- [x] Chuyển catalog, thêm Farm fields và chuyển đồ có kiểm tra trước khi đổi.
- [x] Nối ngủ/vật nuôi, bán hàng mới, dự báo cố định và nâng chuồng.
- [x] Lưu schema 2, đọc schema 1; kiểm tra tọa độ, vật nuôi, đồ và phiên bản.
- [x] Giữ menu cũ, thêm text commands cho map/nhà/tivi/túi/rương/chuồng/câu cá;
  chọn curses mặc định ở TTY, --text cho menu dòng, cập nhật hướng dẫn.

## 2. Bản đồ — tác vụ riêng

Files: world.py, tests/test_world.py.

- [x] Viết test đi/chặn, tọa độ ruộng khi nâng cấp, vào/ra nhà, các điểm tương tác.
- [x] Triển khai đúng API world trong spec, không sửa model/UI/storage.
- [x] Kiểm tra kết nối bản đồ bằng BFS và tương tác của từng nơi, báo kết quả.

## 3. Câu cá và gia súc — tác vụ riêng

Files: animals.py, fishing.py, tests/test_activities.py.

- [x] Viết test ăn/vuốt ve một lần/ngày, lớn/cho sản phẩm, không trừ tài nguyên khi lỗi.
- [x] Triển khai các API animals; inventory update qua farm.items.
- [x] Viết test câu cá có tiến độ, thành công/thất bại/thưởng đúng một lần.
- [x] Triển khai FishingRound thuần dt và các hàm bắt đầu/kết thúc.
- [x] Chạy test riêng, báo giao diện và kết quả; không sửa model/world/UI/storage.

## 4. Giao diện khám phá — tác vụ riêng

Files: explore.py, tests/test_explore.py (nếu cần, ưu tiên PTY thật).

- [x] Triển khai ExplorerGame theo hợp đồng đã khóa trong spec.
- [x] Map WASD/mũi tên, contextual E, màn hình nội thất, menus/mua/bán/nâng cấp.
- [x] Túi/rương gửi-rút, TV, giường, chuồng và câu cá thời gian thực.
- [x] Giữ thông báo lỗi lưu, không báo lưu thành công khi thất bại, xử lý resize/Ctrl+C.
- [x] Smoke test trong PTY sau khi các mô-đun đã sẵn sàng, báo kết quả.

## 5. Tích hợp và kiểm chứng — root

- [x] Xem lại từng mô-đun so với hợp đồng, chạy toàn bộ unittest và compileall.
- [x] Chơi thử thực tế vòng khám phá → vào nhà → tivi/rương → ra hồ/chuồng;
  thử resize và khôi phục save cũ/mới.
- [x] Yêu cầu rà soát mã độc lập, xử lý vấn đề được xác minh và chạy lại kiểm tra.
- [x] Đánh dấu hoàn thành và báo lệnh chạy/điều khiển cho người dùng.

## Kết quả kiểm chứng

- 88 bài unittest đạt; compileall hoàn tất không có lỗi.
- Toàn bộ 35 bài kiểm tra bản cũ tiếp tục đạt; có migration JSON v1 sang v2.
- Chạy main.py trong PTY thật: WASD, resize 30×10/80×24, vào/ra nhà, xem TV,
  gửi 2 hạt vào rương, ngủ đúng dự báo, mua/cho ăn/vuốt ve gà, quăng/hủy câu,
  thoát và đọc lại trạng thái. Ctrl+C tạo file lưu cho ván chưa lưu trước đó.
- Rà soát độc lập xác minh hai lỗi đã sửa: menu thấp không che lựa chọn,
  terminal không hỗ trợ curses tự chuyển sang menu dòng. Kiểm tra lại sạch.
- Quyết định tích hợp: --no-clear dùng menu dòng để giữ lịch sử; WASD trong
  bản đồ trực tiếp không cần Enter, S là xuống, P/F5 là lưu.
