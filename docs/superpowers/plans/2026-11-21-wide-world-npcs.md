# Wide World and NPC Implementation Plan

**Goal:** Map 80×36 và 5 dân làng có thể trò chuyện, lưu được thân thiết.
**Architecture:** Pure world/villagers rules, Farm state and version3 saves,
existing curses/text clients consume the same APIs.
**Tech Stack:** Python 3.10+, stdlib, curses, unittest, PTY.
**Spec:** `docs/superpowers/specs/2026-11-21-wide-world-npcs-design.md`.

## Constraints

- Chỉ thư viện chuẩn, lời thoại/giao diện tiếng Việt.
- Giữ toàn bộ vị trí và tiến trình cũ; migration JSON v1/v2/v3.
- Làm trực tiếp ở thư mục hiện tại, không có Git repository.
- Các tác vụ song song chỉ sửa các file được giao, theo API trong spec.

## Tasks

- [x] Root: viết tests trò chuyện trước, thấy thiếu module, tạo villagers.py,
  thêm Farm.friendships/talked_on; tăng thân một lần/ngày, clamp10, validate
  gần NPC/topic trước khi đổi trạng thái.
  ```python
  farm = Farm(player_x=28, player_y=4)
  talk(farm, 'lan', 'greet')
  talk(farm, 'lan', 'work')
  self.assertEqual(farm.friendships['lan'], 1)
  self.assertEqual(farm.day, 1)
  ```
- [x] World agent: world.py/tests/test_world.py; mở map80×36, địa hình/khu/cầu,
  LANDMARKS, NPC collision/context, BFS mọi nơi, giữ tọa độ cũ.
- [x] UI agent: explore.py/text_activities.py/tests/test_explore.py; camera,
  số NPC, hội thoại có wrap, M atlas, J dân làng, viewport dòng.
- [x] Root: test migration v2 + roundtripv3; sửa storage.py, schema3 đọc v1/v2,
  kiểm tra maps friendship/day, cập nhật kỳ vọng schema trong tests cũ.
- [x] Root: kiểm tra tích hợp textCLI/PTY gần NPC và đi sang vùng mới, sửa
  README, chạy unittest/compileall và rà soát độc lập.
- [x] Đối chiếu spec, cập nhật kết quả, báo lệnh chạy và cách trò chuyện.

## Verification

- 115 unittest tests pass; compileall completes without errors.
- Occupancy-aware BFS confirms all non-NPC walkable tiles and every NPC
  approach reachable for field sizes 4/5/6. Original terrain preserved except
  three gates; both river bridges connect the new regions.
- main.py PTY journey: walk to Lan, choose topic, resize dialogue to 30×10,
  restore 80×24, M atlas/J directory, east gate to An, bridge to Mai, chat,
  save/reload. Daily friendship stays1 after another topic on resumed save.
- Version1 and version2 saves migrate to version3 with progress preserved.
- Independent review found a wide-character dialogue wrap issue; reproduced
  before fixing cell-aware wrapping, regression now passes. Scoped re-review
  confirmed full CJK/combining preservation at21/29/63/79 cells, no residuals.
- README documents all new areas, NPC coordinates, topics, friendship and keys.
