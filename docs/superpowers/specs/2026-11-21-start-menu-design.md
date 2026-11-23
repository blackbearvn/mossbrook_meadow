# Menu bắt đầu, tạo nhân vật và intro

## Trải nghiệm

Mặc định khi chạy trên terminal tương tác, mở màn tiêu đề MOSSBROOK MEADOW với phong
cảnh ASCII và menu Tiếp tục / Hành trình mới – tạo nhân vật / Xem intro /
Hướng dẫn / Thoát. Tiếp tục hiển thị tên nhân vật/nông trại/ngày/cấp và chỉ
vào đúng file lưu được chọn. File hỏng hiển thị lỗi, không tự ghi đè.

Tạo nhân vật theo bước: tên người chơi (24ký tự), tên nông trại (28), biểu
tượng @/&/o, màu áo green/cyan/yellow/magenta, xuất thân gardener/angler/
traveler. Xuất thân phục vụ câu chuyện, không thay đổi điểm/XP/tài nguyên.
Có bản xem trước, chỉnh lại hoặc xác nhận bắt đầu. Esc/0/CtrlC/EOF hủy trước
xác nhận không đổi save cũ. Chỉ khi xác nhận cuối mới tạo Farm, sao lưu file
cũ và ghi file mới nguyên tử. Nếu ghi lỗi báo rõ và vẫn ở menu, không launch.

Intro3trang: lá thư về nông trại; chuyến xe vào Mossbrook Meadow; lời chào của Lan
và các phím cơ bản/đường tới ruộng. Nội dung dùng tên người chơi, nông trại,
xuất thân. Enter/Space tiếp, Backspace/P quay lại, S/Q/Esc bỏ qua. Không tự
delay. Xem intro ở menu chỉ preview; không đổi save. Chơi mới tự intro một
lần; tiếp tục oldsave không intro lại; --intro cho xem khi vào game.

## Hợp đồng tích hợp

`identity.py` không import model runtime: AVATARS mapping{'@':'Nhà nông',
'&':'Người khám phá','o':'Người lữ hành'}, OUTFITS mappinggreen/cyan/yellow/
magenta nhãn tiếng Việt, BACKGROUNDS mappinggardener/angler/traveler nhãn;
normalize_name(value,limit,label)->str normalizeNFC/strip/validate printable;
create_character(player_name,farm_name,avatar='@',outfit='green',
background='gardener')->Farm, mới ngày1xp0đồ mặc định, intro_seen=False;
intro_pages(farm)->list[tuple[str,str]], đúng3trang, nội dung tiếng Việt.

Farm thêm player_name='Người làm vườn',avatar='@',outfit='green',
background='gardener',intro_seen=True (giữ compatibility Farm() dùng trực
tiếp). create_character mới setFalse. Các thông tin hiện trong C/nhân vật;
avatar/outfit dùng vẽ nhân vật thay @; tên người chơi dùng chào NPC.
Save schema5, migration1..4 thêm profiledefaults/intro_seenTrue, giữ mọi
dữ liệu cũ. Fieldsets của từng schema phải explicit dựa legacyfields để
không vô tình thêm fields hiện tại vào schema cũ. Validate profileenums,
name24, intro_seenbool trước tạo Farm.

`start_screen.py`: StartupResult(farm:Farm|None,created=False),
run_startup(save_path:Path,*,graphical:bool,color=True,clear_screen=True,
default_name='Mossbrook Meadow',force_new=False,force_intro=False)->StartupResult.
run_startup trả farm=None khi thoát/hủyCtrlC/EOF ở title/wizard.
Có thể thêm lớp/hàm công khai cho kiểm thử, không import curses trừ khi
graphical. Lớp curses tái dùng ExplorerGame._put/_reader/fit_text/wrap_cells
nhưng không kế thừa handlingrun tự lưu placeholder Farm khi hủy ở title.
Force_new vào wizardngay; hủy về menu. Normal Tiếp tục không ghi lại save.
Actual new confirmation gọi backup_save nếu existing rồi save_game trước
intro. Khi intro xong/skip markintro_seenTrue và lưu. CtrlC/EOF lúc intro
sau tạo phải giữ newFarm đã lưu, không trở về placeholder; trảNone để thoát
nếu cần. Preview intro tuyệt đối không sửa profile/state/ngày.
Graphical UI Esc cancels tên, chữUnicode/backspace, phím số/mũi tên,
resize/viewport đọc hết nội dung. Text wizard từng dòng, 0 để hủy, Enter
dùng default. Confirmation1 bắt đầu /2 chỉnh lại /0 hủy.

`main.py` root tích hợp: menu khi stdin/stdoutTTY (cả --text) hoặc --menu;
redirected input giữ đường direct cũ; --quick bỏ menu; --new mở wizard khi
menuactive, còn directCLI giữ cách cũ và name. --intro hiệnintro khi chọn
tiếp tục hoặc direct. --skip-intro bỏ intro khi menu tạo mới (run_startup
thêm skip_intro=False keyword để mainpass). --menu + --quick xung đột
argparse; --intro + --skip-intro xung đột. --help không launch/write.
Direct --new vẫn backupoldsave. Không thay đổi cácflags cũ.

## Kiểm chứng

Unit test identity/migration5/roundtrip/cancel/invalid/finalconfirmbackup,
textCLI --menu quit/create/continue/preview/EOF. Existing CLI tests giữ
directflow (PTY fallback test thêm --quick để giữ scope fallback).
PTY main defaulttitle/continue, newcreationcancelpreserve, Unicode wizard,
avatarcolorintro/skip, resize, intropreviewnowrite, newgameautosave/profileC.
Rà soát độc lập rồi chạy unittest/compileall.
