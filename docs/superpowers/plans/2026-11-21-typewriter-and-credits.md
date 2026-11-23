# Typewriter Intro and Credits Implementation Plan

**Goal:** Intro chạy trong ván đã bắt đầu với chữ gõ dần; credit>100dòng.
**Spec:** docs/superpowers/specs/2026-11-21-typewriter-and-credits-design.md.
**Architecture:** Pure typewriter controller + curses/text presentation;
independent credits resource/viewer; startup returns runtime playback intent.
**Tech Stack:** Python3.10+, stdlib, curses, monotonic, unittest/PTY.

## Constraints

- Chỉ sửa đúng file được giao, không Git repo.
- Credit không đổi save, không tự bịa tác giả; introinterrupt giữ pendingflag.
- Các viewer cóskip/reveal và xử lýresize, không chờ không thể ngắt.

## Tasks

- [x] Presentation agent: presentation.py/tests/test_presentation.py; testred
  Typewriter clock/grapheme + viewercontrols, implementcurses/textTTYnontty.
- [x] Credits agent: credits.py/credits.txt/tests/test_credits.py; >100meaningful
  lines, realauto/manualscroll pause/end+textpagination, no save writes.
- [x] Root: start_screen/main/explore/terminal timingstate+wiring, tests theo
  yêu cầu mới, keepflag=Falseuntilruntimefinished andsafeoldsavebackup.
- [x] Root: READMEkeys/runtimeflow, fullunittest/compileall, actualPTYanimation
  prefix/reveal/skip/creditreadthrough/save/resume.
- [x] Review độc lập, sửa findingsđãxácminh, kết quả cuối và plancomplete.

## Verification record

- 218 unittest tests pass; compileall succeeds. Credit resource has143 unique,
  nonempty original Vietnamese lines, including project owner and Codex credit.
- main.py realPTY: creditautoscroll/pause/Endlastline/resize/return withsave
  byte-identical; nointrotitle/wizard; confirm→runtime_map→typewriting;
  distincttimeprefix updates without keys, firstSpace revealonly, secondnext,
  resize, immediateskip→seenTrue save. CtrlCtyping keepspendingintroFalse.
- TextTTY reveal/next/skip restores inputline mode for gameplay.
- Independentreview3findings allfixed with regression evidence: ANSIarrows
  decoded instead ofskip, textcredits preserve sourcecharacteranchor onresize,
  cursesEOF handledlikeinterrupt. Scoped29testre-review clean.
- README documents runtimeintro timing/typewriting38cps, keyreveal/skip,
  credit143lines menu3 withpause/manual/HomeEnd andtextpagination.
