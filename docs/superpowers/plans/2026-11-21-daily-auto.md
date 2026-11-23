# Daily Tasks and Auto Implementation Plan

**Goal:** Nhiệm vụ ngày có thưởng, auto có thể ngắt và tìm đường tối ưu.
**Architecture:** Model emits daily events; runtime automation executes one
real action/move per tick; both UIs share menus/controller; schema 7 stores
daily state only. A* and static terrain caches are shared with tutorial.
**Tech Stack:** Python 3.10+, stdlib, unittest, curses, PTY, perf_counter.
**Spec:** `docs/superpowers/specs/2026-11-21-daily-auto-design.md`.

## Constraints

- User authorized implementation; proceed with routine design decisions.
- No real Git repository; use this checkout without worktree/commit.
- Each worker edits only its assigned files, uses tests before code, and
  reports covering commands/results. Root integrates and verifies.
- Existing saves and resource/energy rules remain compatible; auto is an
  optional controller using real actions. No network or dependencies.

## Task 1 — Daily engine

- [x] Own `daily.py`, model daily field/hooks, animals/fishing/villagers hooks,
  and `tests/test_daily.py`. Do not edit storage or UI.
- [x] `DailyQuest(kind,target,progress=0,claimed=False)`,
  `DailyState(day=0,tasks=[])`, fixed `QUESTS` definitions with target/rewards.
  API: `ensure_daily(farm)`, `record_daily(farm,kind,amount=1)`,
  `claim_quest(farm,index)`, `claim_all(farm)`, `daily_lines(farm)`.
- [x] Four unique tasks/day generated from day and farm, fixed until next
  day. Failed/no-op actions do not count; rewards manual and once only.
  Model sleep resets after day advances. Tests cover real actions/rewards.

## Task 2 — Shared navigation/performance

- [x] Own `navigation.py`, `world.py`, tutorial route adapter, and navigation
  tests/benchmark. Record baseline before changes.
- [x] `route(farm, target_area, target, *, kind='') -> tuple[target,path,key]`
  compatible with tutorial route; cross-area target becomes door; kind plot
  respects target_plot; kind forest respects context. Add kind tile (exact
  walkable target), water (actionable water edge), and npc interaction.
- [x] A* with Manhattan lower bound, bounded caches, static tile lookup.
  Verify actual routes, shortest lengths against independent BFS, facing,
  NPC avoidance, expansions for 4/5/6 plots, home exits and unreachable goals.

## Task 3 — Automation engine

- [x] Own `automation.py` and `tests/test_automation.py`, no shared file edits.
- [x] `AutoOptions(mode='all', days=1)`, `Automation(farm, options, rng=None)`;
  `step() -> AutoResult(message,changed=False,moved=False,done=False)`;
  `paused`, `stop()`, `summary`, and `path_points()` for runtime UI.
- [x] Reuse route API; deque path survives ticks. Every step at most one
  move/action/physics interval. Planner prioritizes watering/harvest and
  reserves enough energy to water newly planted crops, feed animals and
  buy supplies, works/fishes/trades/socializes, claims daily rewards, rests.
- [x] All mode buys animals/upgrades and balances attribute/skill points;
  modes farm/ranch/fish limit work. All mode follows active tutorial using
  real actions/events and actual two-turn conversations. Bounded fallback
  prevents stuck loops; stop finite runs after selected days with saveable
  state. Test multi-day, no funds/energy, rain, house, minigame and cancel.

## Task 4 — Root integration and save migration

- [x] Shared activity UI for N/O; controls, summaries, pause/speed/stop;
  curses idle ticks and equivalent text controls. Add tests for real keys,
  save coalescing/errors and CLI end-to-end.
- [x] Schema 7 adds validated daily dataclasses; versions 1–6 migrate without
  writes. Validate task count/kinds/targets/progress/claimed/day, strict types.
- [x] README/control help, compileall, full suite, CLI/PTY playtest, review
  by independent agent; record measured performance and final evidence.

## Implementation and verification record

- Daily engine: 29 real action/eligibility/reward tests. Sprinklers count
  crops actually watered, without rerolling the board or granting rewards.
- Automation engine: 25 scenarios, including 36 slow-growing plants with
  20 energy. Watering prioritizes longest-dry plots, then distance, so it
  rotates scarce energy fairly. Existing livestock are cared for during
  guided all mode. The action budget keeps its route home between ticks.
- Save 7: strict daily structure, four distinct tasks, bounded targets and
  progress, coherent claim flags/day, typed reconstruction and 1–6 migration.
- Root UI: N/O keys, real menus and controls; immediate action saves,
  movement checkpoints every 12 steps or 2 seconds, flush on stop/quit,
  automation stops after a failed checkpoint. Auto state is never persisted.
- Input review found a buffered-line/fd-readiness mismatch. `line_input.py`
  now shares a request-driven line queue between manual prompts and auto;
  partial lines do not block simulation, queued stop works with an open
  pipe, EOF/SIGINT save and exit, and pending input survives finite completion.
- Specialist modes with an active tutorial keep their selected scope and
  do not allocate character points; all mode can perform the guided course.
- Final full suite: `python3 -m unittest discover -s tests -q` — 337 tests,
  OK (9.570 s). `python3 -m compileall -q main.py farmgame tests tools` and
  `python3 main.py --help` both exit 0.
- Actual curses PTY: board N; O all/3 days/fast; walking, pause, resume and
  speed controls; 15 guided objectives; farming, trade, fishing, animal
  purchase and character upgrades; day 4 board, save 7 and manual reload.
  The recorded run ended day 4 with 1 harvest, 84 sales, 2 fish, 1 animal,
  97 XP. Random weather and fish vary on later runs.
- Real CLI pipe/PTY checks cover queued stop, partial line, finite finish,
  next manual action, EOF and Ctrl+C. Independent review additionally ran
  80 varied three-day simulations and per-action save/load checks.
- Independent scoped re-review confirmed both reported P2 findings fixed:
  specialist scope/point spending and queued line controls. Twelve focused
  input/UI checks plus the final seven input tests passed; no new critical
  breakage was found in the fixes.
- Performance evidence is in `tools/navigation_benchmark_results.md`:
  cold route batch 890.917 → 233.485 ms, walking replans 2869.639 → 211.658 ms,
  static map lookups 728.351 → 583.805 ms. The cached-call wrapper is slower
  by about 12 microseconds/call to validate inputs and read live NPC positions.
  Paths retain shortest lengths verified against independent BFS; timings
  are observations on a shared host, without brittle test thresholds.
