# Intro sau bắt đầu, typewriting và credit

## Yêu cầu

Intro chỉ chạy sau khi đã chọn bắt đầu/tiếp tục ván, trong giao diện chơi;
chữ hiện dần theo thời gian. Credit nhà phát triển có hơn100 dòng nội dung,
đọc được trọn vẹn và vào từ menu chính. Python3.10+ stdlib, tiếng Việt.

## Luồng

Menu3 thay 'Xem intro' thành 'Credit nhà phát triển'. Menu/wizard không gọi
intro. Xác nhận tạo mới backup+atomic save(intro_seenFalse), trả StartupResult
với play_introTrue. Tiếp tục pendingintro cũng trảflag này, không chạy ngay
trongtitle. --skip-intro tạo/tiếp tục markseenTrue khi chọn vào game; --intro
buộc play_introTrue. Cancel trước confirm không đổi trạng thái như cũ.

ExplorerGame/TerminalGame constructor thêm intro=False. main truyềnflag
sau tạo đối tượng, runtime vẽ map/dashboard một lần trước khi mở intro.
Explorer sử dụng cùng screen/curses qua CursesUI.attach, không nestedwrapper;
Terminal dùngTextUI. Hoàn tất/skip intro mới markintro_seenTrue rồi save;
CtrlC/EOF khi đangintro đểFalse, runtime thoát và lưu tiến trình đã commit.
Các ván cũ intro_seenTrue không tự xem lại. --intro direct cũng dùngruntime.

## API mô-đun độc lập

`presentation.py`: Typewriter(text,chars_per_second=38.0), advance(dt)->str,
reveal()->str, visible:str, done:bool. Đơn vị chữ giữ nguyên các combining
marks cùng chữ gốc, không cắt đôi tênUnicode. Validate finite dt>=0/speed>0.
Không dùng wallclock trongcontroller, chỉ người render đọc monotonic.

play_curses_intro(ui,farm)->bool và play_text_intro(ui,farm)->bool nhận
ui có paint(title,lines,footer,selected=None,scroll=0), key(), _screen,
_curses; nội dung từidentity.intro_pages. True=done/skip, interrupt propagate.
advance theo monotonic; timeoutframe25ms rồi finally restore100ms.
Enter/Space khi đangtyping chỉreveal, khiđãfull sangtrang; P/Backspace quay
trang; S/Q/Esc skiptoànintro. ↑↓/PgUp/PgDn cuộn, reflow khiresize; auto-scroll
theochữ khi không manuallyscroll. Một trang chỉ đổi do user, khôngautonext.
TextUI pipe hiển thịtrangfullkhôngdelay, giữEnter/Space next nhưtrước;
TextUI TTY chữchạytừtừ, có reveal/skip không chờ hết trang bằng cbreak
termios/select (Windows có thể msvcrt), luônrestoreinputmode khiinterrupt.

`credits.py` + `credits.txt`: credits_lines()->tuple[str,...] >=101nonempty
dòng meaningful, khônglặpdòngđệmcưỡngép; tác giả ghi 'Chủ dự án Mossbrook Meadow',
'Hỗ trợ lập trình: Codex', không tự bịa tênngười/nhóm. Dữ liệu gồm sáng
tạo/phát triển/nội dung/gameplay/map/NPC/âm hưởngterminal/test/triân.
play_curses_credits(ui)->None: paint/viewer, tựcuộn0.45s/dòng, Space pause,
↑↓/PgUp/PgDn manualpause, Home/End vềđầu/cuối, Q/Esc/Enter vềtitle.
Tới cuối dừng chođọc, không tựthoát; resize không làm mất dòng nào.
play_text_credits(ui)->None: phân trang theo terminalheight và wrap_cells,
Enter next/B previous/Q back, đọc hết >100lines kể cả redirected.
Không importcurses top-level, không dùng save hay Farm đểcreditread-only.

start_screen.CursesUI.intro/TextUI.intro delegatepresentation; thêm credits()
delegatecredits. _startup menu3 gọiui.credits, khôngthayFarm/save.
show_intro compatibilityhelper có thể giữ nhưngmain khônggọitrướcgame.

## Kiểm tra

Controlleradvance/reveal/combining/dtinvalid, keyreveal khôngadvancepage,
skip khiđangtyping ngaylập tức, prevpage/resize/fulltext, timeoutrestore.
Credit>100 actualreadablelines, manualend/start/pause/resize & textpages.
Startup confirmfileFalse rồi runtimeintroTrue; titlecredit không đổi save;
runtimeEOF pendingflagFalse, resumeoneintro; --skip-intro direct nointro.
Existing189tests cập nhật những tests chủ động đổi timing/menu3. PTY
maintitle->creditpause/end->wizard->runtime->typingwait/reveal/next/skip->
save/resume; inspect visibleprefix atdifferent elapsedtimes, nofakeanimations.
Ràsoát độc lập và chạyfullunittest/compileall.
