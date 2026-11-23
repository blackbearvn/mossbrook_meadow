# Character and Conversations Implementation Plan

**Goal:** Nhân vật nâng chỉ số/tay nghề, map128×64 với ruộng xa nhà, đối thoại2chiều.
**Architecture:** Independent progression/world/dialogue rule modules;
Farm shared state; version4 atomic save; curses/text clients consume same rules.
**Tech Stack:** Python3.10+, stdlib dataclasses/curses/json/unittest/PTY.
**Spec:** docs/superpowers/specs/2026-11-21-character-and-conversations-design.md.

## Constraints

- Không thư viện ngoài, lời thoại tiếng Việt, giữ file lưu1/2/3.
- Tác vụ song song chỉ sửa file được giao, theo hợp đồng spec.
- Không Git repo, không tạo commit/worktree.

## Tasks

- [x] Progression agent: progression.py/model.py/animals.py/fishing.py và tests
  liên quan. TDD cho điểm/cấp/bonus/cap/atomic; thay XP/chi phí/limit đúng spec.
- [x] World agent: world.py/tests/test_world.py, map128×64, ruộng26,42, vùng/đường
  mới; giữ static walkability, cập nhật test tọa độ cũ do yêu cầu mới.
- [x] Dialogue agent: dialogue.py/villagers.py/tests/test_dialogue.py, Conversation
  graph2choices2turns cho15nhánh, XP/quan hệ1lần/ngày, không mutate khi hủy.
- [x] Root: storage.py migration4/validation/oldschemas tests, profileUI+actual
  sale prices/energy_limit và dialogueUI cho curses/text, sửa các test cũ theo
  hành vi mới đã chủ động thay đổi.
- [x] Root: README hướng dẫn C/nâng điểm/ruộng xa/đối thoại, chạy unittest và
  compileall, chơi main.py trong PTY profile/map/đối thoại/save/reload.
- [x] Rà soát độc lập, xác minh/sửa lỗi, chạy kiểm tra cuối và cập nhật plan.

## Verification record

- 148 unittest tests pass, compileall succeeds, CLI --help shows current keys.
- Progression tests cover attribute/skill budgets, caps, every rank's actual
  effect, focus once per action, atomic failures and effective energy cap.
- World tests cover connected128×64 terrain, fields26,42 distant from home,
  all landmarks/NPCs and preservation of every old static walkable position.
- Dialogue tests traverse all15 topics ×4 complete branches with2 player
  turns; invalid/cancel/daily repeat cannot duplicate rewards.
- JSON schemas1/2/3 migrate to4 without losing plants/position/inventory/
  relations/XP; existing level supplies unspent points, spent points roundtrip.
- main.py PTY: load oldv3, speak2turns withLan tolevel2, upgrade endurance
  andfarming, resize, walk todistantfield/water migratedA1, returnhome/sleep
  to24energy, save/reload/Ctrl+C preserve allpoints andcrop.
- Independent review found2displayissues (stale baseline guidance and clipped
  response options on narrow screens). Both reproduced/corrected; re-review
  confirmed allrank labels and complete answer previews, no related residuals.
- README updated withC/profile/budgets/effects, fieldroute and2sided controls.
