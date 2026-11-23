# Start Menu Implementation Plan

**Goal:** Menu bắt đầu, tạo nhân vật có hình thức lưu được, intro có thể bỏ qua.
**Architecture:** Identity/profile pure functions, startup transaction + UI,
existing curses/text runtime launched after selection, schema5 migration.
**Spec:** docs/superpowers/specs/2026-11-21-start-menu-design.md.
**Tech Stack:** Python3.10+, stdlib, curses, unittest, PTY.

## Constraints

- Không thêm thư viện, giữ tiếng Việt và dữ liệu schema1..4.
- Chỉ xác nhận cuối mới thay save; luôn backup trước khi tạo ván mới.
- Tác vụ song song sửa đúng file được giao; thư mục không có Git repo.

## Tasks

- [x] Identity agent: identity.py/model.py/storage.py, identity/save tests;
  TDD profile defaults/newfactory3pages/validation/migration5.
- [x] Startup UI agent: start_screen.py/tests/test_start_screen.py;
  title ASCII/menu/wizardtext+curse/back/confirm/backup/errors/intro.
- [x] Root: tests CLI flags trước implementation, main.py menuactive vsquick,
  new/resume/preview/intro; profile shown C, map avatar/color, NPCname.
- [x] Root: README startupcontrols/flags; PTY title/create/intro/cancel/resume,
  resizeUnicode and profile persistence; preserve olderprogressiontests.
- [x] Rà soát độc lập, xử lý findings, unittest/compileall, update records.

## Verification record

- 189 unittest tests pass; compileall succeeds; --help documents all flags.
- Identity persists name/avatar/outfit/background/intro flag in schema5;
  explicit migrations1..4 preserve existing game state and never rewrite on read.
- Startup tests cover cancellation/EOF/Ctrl+C/no save mutation, final-only backup,
  corrupt save replacement, failed writes, pending intro resume/skip, Unicode
  editing/backspace, resizing and preview scrolling.
- main.py real PTY: title → Unicode wizard cancel → old save byte-identical;
  createLinh/VườnSớm/&/magenta/traveler → resize → confirm → one backup →
  three intro pages/back → custom map/profile → quit. Continue skips seenintro;
  preview+CtrlC leaves save unchanged. PTY process exit codes all0.
- Independent review found only graphical startup failure reporting success;
  fixed StartupResult.exit_code and main propagation, regression passed.
  Scoped re-review confirmed failure1/cancellation0 with no residual findings.
- README includes menu/creation/intro navigation, flags and schema5 behavior.
