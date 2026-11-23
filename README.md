# Nông trại Mây Nhỏ

Game nông trại tiếng Việt bằng Python trong terminal: đi bộ trên bản đồ,
trồng cây, câu cá, nuôi gà/vịt/thỏ/bò/cừu/dê/heo, nấu ăn, về nhà xem tivi, cất đồ trong rương và
đối thoại với những người hàng xóm trên bản đồ rộng **128 × 64 ô**.
Đào quặng trong Mỏ Khoáng, rèn cuốc/kiếm/giáp và chinh phục **Hang Sâu** 5 tầng.
Kiếm XP, lên cấp và tự phân bổ điểm thuộc tính, tay nghề cho nhân vật.
Chỉ dùng thư viện chuẩn, không cần mạng hoặc cài thêm gói.

## Chạy game

Cần **Python 3.10 trở lên**. Trong thư mục dự án:

```bash
python3 main.py
```

Trên terminal Linux/macOS, game mở bản đồ điều khiển trực tiếp, **không cần
Enter khi di chuyển**, sau màn hình bắt đầu. Terminal 80 × 24 trở lên cho bố cục dễ đọc nhất;
bản đồ có viewport khi cửa sổ hẹp. Mở rộng cửa sổ nếu màn hình quá nhỏ.

Nếu terminal không hỗ trợ curses (chẳng hạn Python Windows mặc định), game
chuyển sang menu dòng. Có thể chọn chế độ này bằng `python3 main.py --text`,
hoặc `py main.py --text` trên Windows. Chế độ này vẫn có bản đồ và đầy đủ
các hoạt động mới.

## Giao diện TUI và cửa sổ nổi

Bản curses dùng bố cục TUI mới: khung nổi bo tròn `╭ ╮ ╰ ╯`, tiêu đề gắn
trên viền, bóng đổ `░` và nền che mờ bản đồ làng phía sau. Túi đồ, chợ,
chuồng, nhân vật, nhiệm vụ, auto, sổ tay, câu cá, bản đồ tổng quan, cuộc trò
chuyện và màn hình bắt đầu đều mở trong cửa sổ nổi thay vì xóa cả màn hình.
Hai dòng cuối dành cho phím tắt và thông báo mới nhất; nội dung dài tự xuống
dòng, cuộn bằng ↑↓/PgUp/PgDn và không che mất lựa chọn đang chọn. Ba dòng
HUD phía trên gộp ngày, thời tiết, xu, năng lượng, máu, cấp và mục tiêu dài
hạn vào một chỗ; dòng mục tiêu tự rút gọn và luôn hiện điểm thuộc tính còn
lại khi terminal đủ rộng.

Thông báo ngắn hiện thành **thẻ toast** ở góc trái bản đồ rồi tự tan sau vài
giây: ✓ thành công, ✦ phần thưởng, ! lỗi, ⚙ auto. Thẻ trùng được gộp với
nhãn `×2`, `×3`; thẻ mới đè lên bản đồ nhưng không che thanh nhiệm vụ hay
dòng nhập. Chế độ dòng dùng khung thông báo quen thuộc thay cho toast để
không phá nhịp cuộn.

Khung, bóng và thanh tiến trình dùng Unicode. Nhấn **G** để đổi toàn bộ vỏ
giao diện sang ASCII (`+ - | :`); `--ascii` bật ngay từ đầu. Terminal quá nhỏ
tự chuyển về bố cục một cột không viền, vẫn giữ đủ nội dung và phím tắt.

### Bảng nhân vật, túi đồ và bộ biểu tượng

**C** mở hồ sơ hai cột với ba tab: **Hồ sơ / Trang bị / Túi đồ**. Tab
**Hồ sơ** giữ chân dung, tên, nông trại, xuất thân, thời tiết, xu, thể lực,
máu, XP và điểm còn lại; bên phải là ba thuộc tính và bốn tay nghề với thanh
`▰▱`, bậc `/5`, dấu `✧` khi có điểm nâng được. Chọn bằng ↑↓/W/S hoặc phím
1–7, **Enter** nâng một bậc, **Space** mở bản đầy đủ, **X** đổi điểm dư thành
xu khi mọi bậc đã tối đa. Tab **Trang bị** xem bậc cuốc/kiếm/giáp, hiệu ứng,
công thức kế tiếp, sát thương, phòng thủ, máu và chi phí đào. Tab **Túi đồ**
liệt kê vật phẩm đang mang, số lượng, giá bán và mô tả; **I** mở túi đầy đủ.
Đổi tab bằng **Tab**, **A/D** hoặc ←/→; **Esc** đóng. Terminal hẹp tự dùng
danh sách có thêm mục Trang bị và Túi đồ.

**I** mở túi đồ dạng hai cột: tab **Tất cả / Hạt giống / Nông sản / Cá /
Khác** (Tab hoặc 1–5), danh sách cuộn bên trái và hình minh họa, giá bán,
số lượng túi/rương cùng mô tả công dụng bên phải. Mỗi dòng có dấu chọn và
số lượng `túi/rương`; phím **PgUp/PgDn** cuộn khi có nhiều món. Khi mở rương
trong nhà, **Enter** gửi/rút món đang chọn và **G** gửi toàn bộ túi vào rương.
Terminal hẹp tự chuyển về danh sách một cột. Bảng nhiệm vụ ngày dùng thanh
tiến trình và biểu tượng theo loại việc; thanh trạng thái thêm biểu tượng
thời tiết, xu, thể lực và cấp.

Bộ biểu tượng được chọn lọc để **luôn rộng đúng 1 ô** trên terminal Unicode:

| Nhóm | Ký hiệu | Dự phòng ASCII |
| --- | --- | --- |
| Thời tiết | `☀ ☁ ☂ ↯ ☾ ❄` | `* ~ / ! ) *` |
| Thuộc tính | `♥ ↟ ☾` | `# ^ )` |
| Tay nghề | `⚘ ≈ ♱ ⚒` | `% ~ + T` |
| Tiền / XP / túi | `◆ ✧ ▤` | `$ + b` |
| Bản đồ / nhà | `⌖ ⌂` | `M H` |
| Thanh bậc | `▰ ▱` | `# -` |

Các ký hiệu có nguy cơ rộng 2 ô hoặc có dấu kết hợp như `⚡`, emoji `🌥 🌨`,
biến thể `☀︎`/`⚡︎` và `𖣂࣪` không được dùng vì dễ làm lệch khung. Mọi biểu tượng đều
có bản ASCII một ký tự; chế độ `--ascii` vì thế vẽ được toàn bộ giao diện.

## Bản đồ ký tự đặc biệt

Bản đồ dùng nét nối và khung **Unicode** để tạo đường làng, mái nhà,
cửa sổ và nội thất. Rừng có `♣ ♠ ♤`, đồng hoa có `✿ ❀ ✾`, mặt hồ có `≈ ≋`,
ruộng `░`; mỗi loại có màu riêng. Cỏ cũng có vài nét chấm, phẩy, nháy thưa
ổn định theo tọa độ để bản đồ bớt trống mà không bị nhấp nháy.
Mùa vụ hiện `╵` mầm, `♠` cây đang lớn, `✦` đã chín, `×` héo; dấu `~`
bên cạnh cho biết ô đủ nước. Nhân vật giữ biểu tượng đã chọn và có mũi tên
chỉ hướng nhìn. NPC vẫn dùng số 1–5, cửa nhà/tiệm/chuồng là H/M/B.

Khung bản đồ hiển thị phạm vi camera; thanh thể lực và chú giải nằm ngoài
vùng đi lại. Giao diện tự thu gọn theo kích thước terminal, dùng một hoặc
hai cột cho mỗi ô. Bản đồ tổng quan M và chế độ dòng cũng dùng bộ ký tự mới.

Nhấn **Z** để đổi **khung bản đồ rộng**: mỗi ô chỉ chiếm một cột, nhờ đó
nhìn được gần gấp đôi số ô ngang và nhiều hàng hơn quanh nhân vật. Khung
rộng giữ nguyên tiêu đề, thanh trạng thái và dòng hành động ở ba hàng trên,
viền dưới nằm sát đáy terminal. Nhấn Z lần nữa để trở lại khung tiêu chuẩn.
Trong chế độ dòng, gõ `z` khi đang ở bản đồ để đổi khung.

### Màu bản đồ

Màu được định nghĩa theo **vai trò địa hình** thay vì gán rời từng ô:

| Địa hình | Màu |
| --- | --- |
| Cỏ | Xanh lá |
| Rừng thông | Xanh lá đậm |
| Hoa | Hồng / tím |
| Ruộng, đất | Vàng nâu |
| Đường làng | Trắng xám |
| Đá, tường | Xám |
| **Cát bãi biển** | **Vàng** |
| **Hồ Sen** | **Xanh lục nhạt** |
| **Biển** | **Xanh dương** |
| Mái nhà | Đỏ gạch |
| Cửa, nội thất | Xanh ngọc |

Terminal hỗ trợ 256 màu dùng bảng màu chi tiết; terminal 8 màu tự hạ xuống
màu gần nhất. Bãi Biển có cát `s` màu vàng, nước biển `S` màu xanh dương;
hồ và suối dùng `~` màu xanh lục nhạt nên dễ phân biệt với biển.

Ở chế độ ASCII, rừng dùng **T/Y/t**, hoa **,/%**, mặt nước `~`, ruộng `:`,
cây đang lớn `t`, cây chín `*`, cây héo `x`; nhà có mái `/---\`, tường `|`
và cửa sổ `o`. Các ký hiệu được chọn theo tọa độ nhưng luôn ổn định, nên bản
đồ có thêm chi tiết mà không bị nhấp nháy khi vẽ lại.

Nhấn **G** để đổi giữa Unicode và **ASCII thường** trong lúc chơi. Nếu font
terminal hiển thị ô vuông hoặc nét bị lệch, có thể mở bằng:

```bash
python3 main.py --ascii
python3 main.py --text --ascii --no-color
```

Game tự chọn ASCII cho terminal `dumb` hoặc encoding không hỗ trợ bộ ký tự.
Tùy chọn chỉ đổi cách vẽ; vị trí, va chạm, đường dẫn, ruộng và ván lưu vẫn
hoạt động như trước.

## Lan hướng dẫn tân thủ tận tay

Sau intro của nhân vật mới, chọn **Bắt đầu** ở câu hỏi **“Để Lan dẫn từng
bước nhé?”**. Lan sẽ nhắc mục tiêu đang làm, phím tiếp theo và vẽ **đường
chấm `·`** dẫn tới đúng người hoặc địa điểm cần đến. Bạn tự điều khiển;
game chỉ chuyển bước sau khi bạn thực hiện đúng hành động.

Chuỗi thực hành gồm **15 bước**:

1. Mở bản đồ làng.
2. Đi bốn bước bằng WASD/mũi tên; va vào tường không tính.
3. Tới Lan và hoàn tất cuộc trò chuyện hai lượt.
4. Mở túi đồ.
5. Đến cửa hàng, mua ít nhất một hạt lúa mì.
6. Đi theo đường chấm tới cánh đồng phía nam.
7. Trồng lúa mì vào một ô trống.
8. Tưới đúng ô vừa trồng; mưa hoặc tưới tự động cũng được tính.
9. Về nhà, tương tác cửa để vào.
10. Xem dự báo trên tivi.
11. Đến giường ngủ sang ngày mới.
12. Trở lại thu hoạch đúng luống lúa mì đã chăm.
13. Bán sản phẩm ở cửa hàng.
14. Mở bảng C để tìm hiểu cấp, XP và nhận **40 XP nhập môn một lần**.
15. Tự dùng một điểm nâng thuộc tính hoặc tay nghề.

**T** mở hướng dẫn mọi lúc: đọc đầy đủ, tạm ẩn, hiện lại hoặc bỏ qua. Tạm
ẩn chỉ tắt chỉ dẫn; những bước thực hành vẫn được ghi nhận. Bỏ qua không
mất tiến trình nông trại. Ván cũ dùng T → Bắt đầu nếu muốn học lại; hướng
dẫn không tự bật khi tải ván cũ. Đã hoàn tất thì T mở tổng kết.

Làm sai ô hoặc mua sai giống không hoàn thành bước. Khi hết sức, hết hạt,
thiếu tiền, cây héo hoặc ruộng đầy, Lan hướng dẫn hồi sức/mua giống/làm
thuê/dọn cây. Game không tự di chuyển, xóa cây hoặc tặng vật phẩm thay bạn.
Trong nhà, đường dẫn sẽ đưa ra cửa trước khi tiếp tục ngoài làng.

Tiến độ và phần thưởng được lưu lại. Đóng game rồi mở tiếp vẫn học đúng
bước; bỏ qua rồi bật lại không nhận lặp phần thưởng nhập môn. Tập trung
có thể cộng XP theo thuộc tính như những hành động kiếm XP khác.

Trong **chế độ dòng**, `t` mở bảng hướng dẫn, `m` mở bản đồ, nhập từng
phím `w/a/s/d` rồi Enter hoặc nhiều bước liền nhau. Đi theo đường chấm,
dùng `e` để tương tác; `atlas` xem toàn cảnh, `i` túi, `c` nhân vật.

## Nhiệm vụ hằng ngày và auto

Nhấn **N** để xem **4 nhiệm vụ trong ngày**, tiến độ và phần thưởng xu/XP.
Kho nhiệm vụ có 15 loại và luân phiên theo điều kiện nông trại: trồng, tưới,
thu hoạch, dọn cây héo, mua hạt, nâng cấp, nhặt củi, câu cá, câu loài mới,
bán cá, hỏi thăm, bán hàng, cho ăn, vuốt ve và lấy sản phẩm. Làm xong thì
chọn **Nhận tất cả thưởng đã hoàn thành**. Mỗi nhiệm vụ nhận một lần; ngủ
sang ngày mới sẽ đổi bảng. Tiến độ và phần thưởng đã nhận được lưu lại.

Nhấn **O** để chọn chế độ tự động:

| Chế độ | Công việc |
| --- | --- |
| Toàn bộ nông trại | Chăm ruộng và vật nuôi, làm nhiệm vụ, câu cá, trò chuyện, mua/bán, nâng cấp và nghỉ |
| Trồng trọt | Tưới, thu hoạch, dọn cây héo, trồng, mua giống, bán và nghỉ |
| Chăm vật nuôi | Mua thức ăn, cho ăn, vuốt ve, thu sản phẩm, bán và nghỉ |
| Câu cá | Đi tới hồ, điều khiển minigame, bán cá và nghỉ |
| Đào khoáng sản | Tự vào mỏ, đào đá gần nhất, rèn cúp khi đủ quặng rồi về ngủ |
| Hang Sâu | Tự rèn kiếm/giáp, mua thuốc, vào hang và chiến đấu từng tầng |

Chọn chạy **1, 3, 7 ngày hoặc liên tục**, rồi chọn tốc độ
**chậm/vừa/nhanh/siêu nhanh**. Auto chỉ bán nông sản và đồ thường; quặng,
kim cương và thuốc được giữ lại để rèn hoặc đi hang. Khi hết năng lượng,
hết đá trong ngày hoặc máu quá thấp, auto tự về giường ngủ để hồi đầy.
Bạn thấy nhân vật tự đi theo từng ô; đường chấm và khung AUTO cho biết
công việc đang làm. Auto dùng thao tác, năng lượng và tài nguyên thật;
câu cá vẫn chạy qua mô phỏng thanh câu. Chế độ toàn bộ tự mua vật nuôi,
nâng cấp công trình và phân bổ điểm thuộc tính/tay nghề khi đủ điều kiện.
Các chế độ riêng phù hợp khi muốn giữ quyền lựa chọn những khoản này.

Trong giao diện trực tiếp, **Space/P** tạm dừng hoặc tiếp tục, **O/Esc**
dừng auto, **+/-** đổi tốc độ. **WASD/mũi tên/E** lấy lại điều khiển để tự
chơi. **Q** lưu và về menu chính. Chọn **Thoát** ở menu sẽ mở cửa sổ xác
nhận trước khi đóng game. Đồ gửi trong rương được giữ để bạn tự quản lý.
Nếu đang học tân thủ, chế độ **Toàn bộ** ưu tiên thực hiện lộ trình học
trước công việc thông thường. Các chế độ riêng làm đúng lĩnh vực đã chọn,
không tự dùng điểm nâng nhân vật. Mở lại ván luôn điều khiển thủ công.

Chế độ dòng cũng dùng `n` và `o`, cả ngoài menu lẫn trong bản đồ. Khi auto
đang chạy, gõ `p`, `o`, `+` hoặc `-` rồi Enter; game tiếp tục di chuyển
trong khi chờ lệnh. Hết đầu vào/Ctrl+C sẽ dừng và lưu. Auto lưu ngay sau
thao tác, lưu vị trí định kỳ khi đi bộ và lưu lúc dừng; lỗi lưu sẽ dừng auto.

Bộ tìm đường A* và cache địa hình được dùng chung cho auto/hướng dẫn.
Auto giữ đường đã tính và đi tiếp, chỉ tìm lại khi đích/trạng thái thay đổi.
Có thể đo lại bằng `python3 tools/benchmark_navigation.py`.

## Menu bắt đầu, nhân vật và intro

Chạy bình thường trong terminal sẽ mở màn tiêu đề với phong cảnh và menu:

| Mục | Hành động |
| --- | --- |
| `1` Tiếp tục | Mở ván hiện tại, hiển thị tên nhân vật/nông trại, ngày và cấp |
| `2` Hành trình mới | Tạo nhân vật rồi bắt đầu ván mới |
| `3` Credit nhà phát triển | Phần ghi công 143 dòng, có thể cuộn và tạm dừng |
| `4` Hướng dẫn | Xem những phím điều khiển cơ bản |
| `0` Thoát | Đóng menu |

Khi tạo nhân vật trong giao diện curses, một trang duy nhất hiện **hồ sơ**
bên trái và **thẻ xem trước trực tiếp** bên phải. Dùng ↑↓/W/S để di chuyển,
Enter để sửa tên hoặc chọn, ←→/A/D để đổi **biểu tượng** (`@`, `&`, `o`),
**màu áo** và **xuất thân**. Nhấn **B** hoặc Enter ở **Bắt đầu hành trình**
để xác nhận; Esc hủy. Tên tiếng Việt được hỗ trợ. Xuất thân có Người làm
vườn, Người câu cá và Người lữ hành, làm thay đổi lời giới thiệu; các lựa
chọn đều bắt đầu với cùng tài nguyên và điểm. Tên và ngoại hình được dùng
trên bản đồ, bảng C và lời chào của NPC.

Màn hình quá hẹp tự chuyển về luồng từng bước; chế độ `--text` vẫn hỏi lần
lượt tên, biểu tượng, màu áo và xuất thân. Ván cũ chỉ được sao lưu và thay
thế sau khi xác nhận Bắt đầu. Esc khi nhập tên hoặc `0` trong menu con hủy
quá trình, giữ nguyên ván cũ. Trong chế độ dòng, nhập `0` rồi Enter để hủy.
Enter ở bước nhập tên dùng tên mặc định.

**Intro phát sau khi xác nhận Bắt đầu hành trình và vào ván chơi**, với
hiệu ứng **typewriting**: chữ hiện dần theo thời gian, khoảng 38 ký tự/giây.
Menu chính không phát intro trước khi bắt đầu.

Intro gồm ba trang: **Lá thư trong nắng**, **Chuyến xe đến Mây Nhỏ** và
**Lan đón bạn**. Khi đang gõ, Enter/Space **hiện hết trang**; nhấn lần nữa
mới sang trang tiếp. P/Backspace quay lại; S/Q/Esc bỏ qua toàn bộ intro
ngay lập tức. Mũi tên/PgUp/PgDn cuộn khi cửa sổ thấp; chữ tự theo xuống
trang trong lúc gõ nếu bạn chưa cuộn bằng tay. Mỗi trang chờ bạn đọc xong.

Ván mới xem một lần; tiếp tục ván cũ vào thẳng game. Nếu đóng khi intro
chưa xong, ván mới đã được lưu và lần Tiếp tục sau sẽ phát lại từ đầu.
`--intro` yêu cầu xem lại khi đã vào ván; `--skip-intro` bỏ qua.

## Credit nhà phát triển

Chọn **3** ở menu chính để mở credit của **RedEye Studio**:

- **b14ckb34rvn** — lập trình
- **TeaM1lk**, **so'dly**, **MoiMoi**, **Fanta de Son** — đồ họa
- **Hoàng Lê** — âm thanh
- **BrosHill** — cốt truyện

Phần credit vẫn có các đoạn ghi chú về thế giới, hệ thống và lời cảm ơn.
Nội dung nằm ở `farmgame/credits.txt`, có thể chỉnh lại thông tin nhóm.

- Credit tự cuộn chậm; **Space** tạm dừng hoặc chạy tiếp.
- Mũi tên/PgUp/PgDn cuộn bằng tay và dừng tự chạy; **Home/End** tới đầu/cuối.
- **Q/Esc/Enter** trở lại menu; tới cuối credit sẽ dừng để bạn đọc.
- Chế độ dòng phân trang: Enter tiếp, B quay lại, Q về menu.

Xem credit không thay đổi file lưu. Hiệu ứng intro vẫn hoạt động trong
`--text` khi dùng terminal thật; khi chuyển hướng đầu vào/đầu ra, chữ hiện
ngay để đọc hoặc chạy lệnh theo kịch bản mà không phải chờ animation.

```bash
python3 main.py --quick                 # vào thẳng ván hiện tại
python3 main.py --menu --text           # menu bắt đầu dạng dòng
python3 main.py --new                   # mở tạo nhân vật mới trong terminal
python3 main.py --intro                 # xem mở đầu sau khi vào ván
python3 main.py --skip-intro            # tạo mới và bỏ đoạn mở đầu
```

Khi chuyển hướng stdin/stdout, game giữ luồng menu chơi dạng dòng cũ;
thêm `--menu` nếu muốn hiện màn bắt đầu trong luồng này. `--quick` bỏ màn
bắt đầu. `--menu`/`--quick` và `--intro`/`--skip-intro` là các cặp tùy chọn
loại trừ nhau.

## Điều khiển bản đồ

| Phím | Hành động |
| --- | --- |
| `W A S D` / mũi tên | Đi lên, trái, xuống, phải; không tốn sức hoặc đổi ngày |
| `E` | Tương tác với công trình, nội thất, hồ hoặc ô ruộng gần bạn |
| `F` | Bảng cánh đồng dạng ô: chọn ô để gieo, tưới, thu hoặc dọn |
| `B` | Sổ chuồng: 3 khu mở theo cấp, chọn con để vuốt ve |
| `K` | Bộ sưu tầm cá: loài, độ hiếm, số lần câu và điểm |
| `I` | Túi đồ hai cột, tab lọc, minh họa; Enter gửi/rút khi mở rương |
| `C` | Bảng nhân vật: cấp, XP, điểm thuộc tính và tay nghề |
| `T` | Lan hướng dẫn tân thủ: xem nhiệm vụ, tạm ẩn/tiếp tục/bỏ qua |
| `N` | Bảng nhiệm vụ hằng ngày và nhận thưởng |
| `O` | Chọn chế độ auto; khi đang chạy, nhấn lại để dừng |
| `G` | Đổi hình bản đồ Unicode / ASCII thường |
| `Z` | Đổi khung bản đồ rộng: ô hẹp, nhìn được nhiều đất hơn |
| `M` | Mở bản đồ tổng quan toàn làng (atlas), đánh dấu vị trí và NPC |
| `R` | Mở danh sách khu vực và đi nhanh tới điểm an toàn |
| `J` | Thẻ dân làng: chân dung, nghề, sở thích, lịch sinh hoạt, tọa độ và mức thân |
| `H` / `?` | Xem sổ tay hướng dẫn |
| `P` / `F5` | Lưu ngay |
| `Q` | Lưu và về menu chính; chọn Thoát ở menu sẽ hỏi xác nhận |
| `Space` khi câu cá | Nâng thanh câu; thả phím để hạ xuống |

Trong menu dùng mũi tên/W/S rồi Enter hoặc E để chọn. Có thể chọn trực tiếp
các mục 1–9 bằng phím số. Esc/Q quay lại. Khi nhập số lượng, `*` chọn tất cả
nếu màn hình có hỗ trợ tùy chọn này.

Bạn là `@`. `H` là cửa nhà ở phía tây bắc, `B` là chuồng ở giữa làng, `M`
là cửa hàng phía đông bắc, `O` là cửa Mỏ Khoáng trên Đồi Gió, `~` là hồ,
`s` là cát, `S` là biển phía đông nam, `T` là cây. Tường, cây,
nước và đồ nội thất chặn đường; đứng **kề một ô** rồi nhấn E để dùng.
Dòng hướng dẫn dưới bản đồ luôn cho biết hành động có thể thực hiện.

## Mỏ khoáng, lò rèn và Hang Sâu

Đi lên **Đồi Gió** tới cửa mỏ `O` ở `(76,6)` rồi nhấn E. Mỏ Khoáng là một
bản đồ trong nhà riêng với các tảng đá `◆` (ASCII `*`), lò rèn `⚒`, cổng
Hang Sâu `☠` và cửa ra `⇥`. Đứng sát một tảng đá rồi nhấn E để đào; mỗi lần
tốn năng lượng, nhận đá và quặng đồng/sắt/vàng, hiếm hơn là tinh thể hang
sâu. Ngủ một đêm sẽ làm đầy lại toàn bộ tảng đá.

- **Đá** và quặng nằm trong túi như mọi vật phẩm khác; có thể bán ở chợ hoặc
  cất vào rương. Quặng càng quý càng ở sâu phía đông mỏ.
- **Cuốc mỏ** giảm sức đào và tăng số quặng mỗi lần; **Kiếm rèn** tăng sát
  thương; **Giáp da** tăng máu tối đa và giảm đòn nhận vào.
- **Lò rèn** `F` cạnh cửa mỏ mở ba trang bị trên. Mỗi bậc cần đá, quặng và
  xu theo bảng giá riêng, tối đa bậc 5. Chọn món rồi Enter để rèn; dòng mô tả
  ghi rõ nguyên liệu còn thiếu.
- **Hang Sâu** `G` mở chế độ dungeon theo lượt, cần kiếm ít nhất bậc 1 và
  máu trên 1. Mỗi tầng có một nhóm quái; hạ hết để xuống tầng kế, tối đa 5
  tầng với Hang Chúa ở cuối. Phím `1`/Enter tấn công, `2` uống thuốc hồi sức,
  `3` rút lui. Máu, xu và quặng nhận được lưu ngay; kỷ lục tầng sâu nhất
  được ghi vào hồ sơ nhân vật. Bị đánh gục sẽ mất một phần xu và tỉnh dậy
  với 1 máu, nên hãy ngủ hoặc mua thuốc trước khi quay lại.
- **Thuốc hồi sức** bán ở quầy Vật tư của chợ (40 xu) và hồi 12 máu.
- Trong mỏ, **N/O** vẫn mở nhiệm vụ/auto nhưng auto chỉ chạy ở làng và trong
  nhà; hãy ra khỏi mỏ trước khi bật auto.

## Chợ làng có thẻ minh họa

Chợ `M` mở một bảng chia ô thay vì danh sách dài. Năm quầy **Hạt giống**,
**Vật nuôi**, **Vật tư**, **Bán hàng**, **Nâng cấp** nằm trên thanh thẻ;
mỗi món là một ô có hình ASCII/Unicode, tên, giá, cấp mở khóa và thông tin
ngắn. Ô đang chọn được tô sáng, dòng cuối mô tả chi tiết món đó.

- `←→`/`↑↓` hoặc `A D W S` di chuyển giữa các ô; `Tab`/`]` và `[` đổi quầy;
  phím `1`–`5` mở thẳng quầy tương ứng; `Enter` mua, bán hoặc nâng cấp.
- Hạt giống hỏi số lượng; vật nuôi, nâng cấp và “Bán tất cả” có bước xác nhận.
- Quầy **Bán hàng** cho bán từng phần (nhập số lượng) hoặc bán tất cả. Rương
  trong nhà luôn được giữ nguyên.
- Quầy **Vật tư** có thức ăn lẻ, bao 10 phần và túi hạt hỗn hợp (mỗi giống
  đang mở một hạt). Quầy **Nâng cấp** ghi rõ “Đã tối đa” khi hết bậc.
- Terminal hẹp hoặc thấp tự chuyển sang menu dòng gọn nhưng vẫn giữ biểu
  tượng và thông tin từng món.

## Làng rộng và NPC

Nông trại cùng các công trình cũ nằm ở góc tây bắc. Camera cuộn theo nhân
vật để khám phá **Đồng Hoa**, **Rừng Thông**, **Quảng trường**, **Hồ Sen** và
**Đồi Gió**, **Cửa Mỏ**, **Thung Lũng Đông**, **Đồi Trà**, **Bãi Bồi** và **Bãi Biển**. Đi dọc đường sang đông, qua cầu tại hàng 7 hoặc 21 để vượt
suối; lối nam nông trại dẫn tới rừng. Các vùng vẫn nối liền trong một map.

Nhấn **R** để mở bảng **KHU VỰC · ĐI NHANH**: mỗi vùng có biểu tượng, mô tả
và điểm đến an toàn. Đi nhanh không tốn năng lượng, ngày hay xu; chọn bằng
↑↓/W/S rồi Enter. Bãi Biển nằm ở phía đông nam, sau rặng lau của Bãi Bồi.

### Bản đồ theo trang

Ván mới dùng **bản đồ theo trang**: mỗi lần camera chỉ hiện một khu vực nhỏ
(Khu Sinh Sống, Đồng Hoa, Đồi Gió, Đồi Trà, Rừng Thông, Quảng Trường, Hồ Sen,
Thung Lũng Đông, Ruộng Cánh Đồng, Bãi Bồi, Bãi Biển). Đi tới rìa trang và
bước qua **con đường** ở mép bản đồ để sang trang kế tiếp; bãi cỏ, bờ nước
hoặc rừng chặn lại, nên các lối đi vẫn rõ ràng. Tên trang và tọa độ hiện ở
dòng đầu; **M** vẫn mở bản đồ tổng quan toàn làng khi cần nhìn xa.

Ván cũ giữ bản đồ đầy đủ cho tới khi bạn mở **R** và chọn **Bật bản đồ theo
khu vực**. Save hiện tại đã được chuyển sang chế độ này; nhấn **R** để đi nhanh
giữa các trang.

**Cánh đồng nay ở `(26,42)`, xa nhà về phía nam.** Từ cửa nhà `(4,4)`, đi
theo đường tới `(10,4)`, xuống `(10,21)`, sang `(26,21)`, rồi xuống `(26,42)`.
M mở tổng quan, ký hiệu `:` là cánh đồng. Sân gần nhà trở thành đất đi dạo;
cây đã trồng trong file lưu cũ được giữ nguyên và hiển thị ở cánh đồng mới.

NPC hiện bằng số `1`–`5`. Đến kề nhân vật rồi E để mở **thẻ chân dung**:
tên, nghề, khẩu hiệu, sở thích, lịch sinh hoạt và thanh thân `♥`. Chọn một
trong **năm chủ đề**: Chào hỏi, Hỏi về công việc, Chuyện quanh làng, Ước mơ,
Kỷ niệm. NPC đặt câu hỏi; bạn chọn hướng trả lời, NPC phản hồi và hỏi tiếp,
rồi bạn trả lời lần thứ hai để kết thúc. Mỗi chủ đề có hai nhánh và bốn lời
kết khác nhau, nên mỗi người có 20 mạch trò chuyện.

Hộp thoại hiển thị cả **lời NPC và lời của bạn**. Dùng W/S hoặc mũi tên để
đọc, Space sang trang; khi đọc hết, Space/Enter mở lựa chọn trả lời. Câu trả
lời được xem đầy đủ ở phần đọc trước khi chọn, kể cả trên cửa sổ hẹp. Q hủy
trước khi trả lời không thay đổi quan hệ hay XP. Sau lời kết, có thể chọn
chủ đề khác hoặc Q về bản đồ.

| Số | Nhân vật | Nghề nghiệp | Tọa độ (x, y) |
| --- | --- | --- | --- |
| `1` | Lan | Chủ tiệm | (28, 5), gần tiệm cũ |
| `2` | Bác Tư | Người câu cá | (30, 10), bờ đông hồ cũ |
| `3` | An | Người làm vườn | (39, 10), Đồng Hoa |
| `4` | Mai | Thủ thư | (55, 20), Quảng trường |
| `5` | Sơn | Người giữ rừng | (20, 25), Rừng Thông |

Mỗi người có lời thoại và mẹo riêng. Lời chào thay đổi theo ngày, trời mưa
và mức thân thiết; mốc 3, 6 và 9 thân mở lời thân mật hơn. Chân dung cũng
xuất hiện trong hộp chọn chủ đề và lời đáp. Lần trò chuyện đầu với mỗi người trong ngày tăng
**1 thân thiết**, tối đa **10**; nói thêm vẫn có hội thoại nhưng không tăng
điểm lặp. Lần trả lời đầu mỗi ngày với mỗi NPC cũng nhận **3 XP cơ bản**;
lặp lại hay khởi động lại game không nhận thêm. Trò chuyện không tốn sức,
tiền hay tự sang ngày. Quan hệ được
tự lưu và giữ nguyên khi chạy lại game.

M mở toàn cảnh thu nhỏ, J mở **sổ dân làng** dạng thẻ có chân dung, thanh
thân, sở thích, lịch sinh hoạt, tọa độ và khoảng cách từ bạn tới từng người;
cuộn bằng ↑↓. Nếu các điểm gần nhau trùng ô trên bản đồ thu nhỏ, ký hiệu
được xê dịch một ô để vẫn nhìn thấy; dùng J và tọa độ ở đầu màn hình để tìm
đúng người.

## Cấp độ, thuộc tính và tay nghề

Nhấn **C** để xem nhân vật. Cứ **40 XP** lên một cấp; mỗi cấp nhận **1 điểm
thuộc tính** và **2 điểm tay nghề**. Chọn chỉ số, đọc hiệu quả rồi xác nhận
nâng một bậc. Mỗi bậc tốn 1 điểm tương ứng, tối đa 5 bậc. Điểm chưa dùng
được giữ lại; file lưu cũ nhận đủ điểm theo cấp đã đạt.

Ván chơi rất dài có thể lên cấp vượt xa giới hạn 5 bậc của mọi chỉ số. Khi
mọi thuộc tính và tay nghề đã đạt bậc 5, game giữ tối đa **99 điểm dư** mỗi
loại để dành cho nội dung mới và tự quy đổi phần vượt mức thành xu khi tải
file lưu (20 xu/điểm thuộc tính, 10 xu/điểm tay nghề). Nhấn **X** trong hồ sơ
để đổi nốt 99 điểm dư; số điểm đã quy đổi được ghi trong file lưu nên mở lại
không bị cộng lặp.

| Thuộc tính | Hiệu quả |
| --- | --- |
| Thể lực | Mỗi bậc +4 sức tối đa và hồi ngay 4 sức |
| Khéo léo | Từ bậc 3, trồng và thu hoạch chỉ tốn 1 sức; bậc 1–2 tích lũy để mở hiệu quả |
| Tập trung | Mỗi bậc +1 XP cho mỗi hành động kiếm kinh nghiệm thành công |

| Tay nghề | Hiệu quả |
| --- | --- |
| Trồng trọt | Mỗi bậc +10% giá bán cây; từ bậc 3 thu 2 nông sản/ô |
| Câu cá | Mỗi bậc thanh câu rộng thêm 0,025; bậc 2 tốn 2 sức, bậc 4 tốn 1 sức |
| Chăn nuôi | Mỗi bậc +10% giá bán trứng/sữa/len/lông/nấm; từ bậc 3 thêm 1 sản phẩm mỗi lần vật nuôi cho hàng |
| Kiếm sống | Mỗi bậc +2 xu làm thuê; bậc 2/4 tăng gỗ và giảm sức tiêu hao |

XP đến từ thu hoạch, bắt cá, lấy sản phẩm chăn nuôi, làm thuê và trả lời
NPC lần đầu trong ngày. Mỗi hành động thành công chỉ cộng Tập trung một
lần; thao tác thất bại không thưởng XP. Giá bán và sức hiển thị trong game
đã tính chỉ số hiện tại. Nâng thể lực ở cửa hàng cộng dồn với thuộc tính.

## Nhà ở, tivi và kho item

Đứng cạnh cửa `H`, nhấn E để vào nhà. Bên trong có:

- **Tivi `V`:** xem thời tiết ngày mai. Xem lại cho cùng một dự báo; thời
  tiết này sẽ trở thành thời tiết thực tế khi bạn ngủ sang ngày mới.
- **Giường `Z`:** ngủ, hồi đầy năng lượng, cây lớn và vật nuôi chuyển ngày.
  Game cảnh báo nếu bạn định ngủ khi cây vẫn thiếu nước.
- **Rương `C`:** gửi/rút số lượng vật phẩm, hoặc cất toàn bộ túi. Giữ được
  hạt giống, nông sản, cá, thức ăn, sản phẩm chăn nuôi và món đã nấu.
- **Bếp `K`:** đứng kề rồi E để mở 8 công thức nấu ăn. Nguyên liệu lấy từ túi
  hoặc rương; món chín vào túi, hồi năng lượng, cộng XP và bán được ở chợ.
- **Cửa `D`:** đứng cạnh rồi E để ra làng.

Túi và rương được lưu riêng. Bán hàng chỉ bán nông sản/cá/sản phẩm có giá
trong **túi**. Hạt giống, thức ăn và mọi đồ trong **rương** được giữ lại.
Dụng cụ cơ bản (cuốc, bình tưới, cần câu) có sẵn từ đầu.

## Trồng cây

Đi đến cánh đồng phía nam `(26,42)`, nhìn vào ô muốn chăm hoặc đứng trên ô đó rồi E.
Game ưu tiên ô phía trước, sau đó ô dưới chân. Ô trống mở menu gieo hạt;
ô có cây được tưới; cây chín được thu hoạch; cây héo được dọn.

| Cây | Giá hạt | Giá bán | Đêm được tưới để chín | Cấp mở khóa |
| --- | ---: | ---: | ---: | ---: |
| Cà rốt | 8 | 24 | 2 | 1 |
| Lúa mì | 5 | 12 | 1 | 1 |
| Cà chua | 15 | 48 | 3 | 2 |
| Khoai tây | 18 | 55 | 2 | 2 |
| Dưa hấu | 22 | 72 | 3 | 2 |
| Bắp | 24 | 80 | 4 | 3 |
| Dâu tây | 35 | 105 | 3 | 3 |
| Bí ngô | 40 | 140 | 5 | 4 |
| Hoa hồng | 30 | 95 | 4 | 5 |

Trên bản đồ ASCII: `:` đất, `+` cây đang lớn, `*` chín, `x` héo. Cây đủ nước có
màu xanh nước. Chi phí cơ bản: trồng/thu hoạch 2 năng lượng, tưới/dọn cây héo 1.
Cây lớn sau khi ngủ nếu được tưới trong **ngày vừa kết thúc**. Mưa tự tưới
ruộng trong ngày đang mưa; dự báo mưa ngày mai không tưới bù ngày trước.
Thiếu nước 3 đêm liên tiếp làm cây héo. Cây chín không héo, không cần tưới.

Mỗi cây mặc định cho 1 nông sản, tay nghề trồng trọt bậc 3 cho 2. Thu hoạch tăng kinh nghiệm; mỗi 40 kinh nghiệm
lên một cấp. Ghé chợ để mua giống, bán hàng và nâng ruộng, thể lực, tưới tự động.

## Bảng cánh đồng

Nhấn **F** để mở bảng cánh đồng dạng lưới ô thay vì đi từng ô trên bản đồ.
Mỗi ô hiện tọa độ, biểu tượng cây, tên giống, số đêm đã lớn, trạng thái nước
và nút hành động gợi ý. `↑↓/←→` chọn, `Enter` gieo/tưới/thu/dọn, `PgUp/PgDn`
cuộn khi ruộng 6×6. Mưa và hệ thống tưới tự động được tính ngay trên thẻ.
Terminal hẹp dùng danh sách ô gọn nhưng vẫn đủ trạng thái.

## Nấu ăn tại bếp

Trong nhà, đứng kề bếp **K** rồi nhấn E. Bảng nấu ăn liệt kê công thức, nguyên
liệu đang có, năng lượng hồi và XP. Nguyên liệu được lấy từ **túi trước, rương
sau**; nếu thiếu bất kỳ món nào, cả công thức bị từ chối và không mất nguyên
liệu. Món nấu xong nằm trong túi như vật phẩm thường nên có thể cất rương,
bán ở chợ hoặc xem trong tab **Khác** của túi đồ.

| Món | Nguyên liệu | Hồi sức | XP | Giá bán |
| --- | --- | ---: | ---: | ---: |
| Bánh mì nướng | 2 lúa mì + 1 trứng | 8 | 8 | 65 |
| Salad vườn | 2 cà rốt + 1 cà chua | 10 | 10 | 90 |
| Nước dưa hấu | 1 dưa hấu | 12 | 12 | 95 |
| Chả cá | 2 cá rô + 1 trứng | 12 | 14 | 145 |
| Cháo trứng | 2 lúa mì + 1 trứng + 1 sữa | 16 | 15 | 120 |
| Súp bí ngô | 2 bí ngô + 1 sữa | 14 | 18 | 230 |
| Sinh tố dâu | 2 dâu tây + 1 sữa | 18 | 20 | 260 |
| Trà hoa hồng | 1 hoa hồng + 1 dâu tây | 15 | 16 | 180 |

## Câu cá

Đi tới bờ hồ `~`, nhấn E. Mỗi lần quăng cần mặc định tốn **3 năng lượng** (giảm theo tay nghề) và được
lưu ngay. Nhấn liên tiếp hoặc giữ Space để nâng thanh `====`, thả để hạ.
Giữ cá `><` trong thanh để tăng tiến độ đến 100%. Cá thoát khi tiến độ hết.

Hồ có 7 loài: cá rô, cá chép, cá trắm, cá hồi, cá măng, cá vàng và cá lăng.
Cá trắm mở ở cấp 2, cá măng cấp 3, cá lăng cấp 4; loài hiếm xuất hiện ít hơn.
Giá bán lần lượt 18/28/55/65/85/90/140 xu. Câu được cá nhận 5 kinh nghiệm cơ bản,
cộng Tập trung. Mỗi loài câu lần đầu được ghi vào **bộ sưu tầm** và cộng điểm
theo độ hiếm; nhấn **K** để xem 7 loài, số lần câu, giá bán, tổng giá trị và điểm sưu tầm.
Q thu cần, kết thúc lượt mà không nhận cá; Q lần nữa ở bản đồ lưu và về menu chính.
Cần câu không phải mua.

## Ba khu chăn nuôi mở theo cấp

Nhấn **B** (hoặc E khi đứng kề chuồng) để mở sổ chuồng dạng thẻ. Ba khu có
sức chứa riêng và mở dần theo cấp nông trại:

| Khu | Mở ở | Sức chứa | Vật nuôi |
| --- | ---: | ---: | --- |
| Sân Gà Vịt | Cấp 1 | 4 | Gà, vịt, thỏ |
| Đồng Cỏ | Cấp 2 | 4 | Bò, cừu, heo |
| Đồi Dê | Cấp 4 | 2 | Dê |

Tổng chuồng vẫn là 4 chỗ, nâng cấp 280 xu lên 8 chỗ. Khu khoá hiện cấp cần
mở; mua vượt khu hoặc vượt sức chứa sẽ bị từ chối và không trừ xu. Trong sổ,
`Tab`/`1–3` đổi khu, `↑↓` chọn con, `Enter` vuốt ve, `A` cho cả đàn ăn,
`C` thu sản phẩm, `M` mua, `F` mua thức ăn, `U` nâng chuồng. Mỗi thẻ hiện
chân dung, loài, tuổi, đói/no, trái tim thân thiết và sản phẩm đang có.

| Vật nuôi | Giá mua | Trưởng thành | Sản phẩm | Giá bán |
| --- | ---: | ---: | --- | ---: |
| Gà | 80 | 2 ngày | Trứng mỗi ngày đủ ăn | 18 |
| Vịt | 120 | 2 ngày | Trứng vịt mỗi ngày đủ ăn | 18 |
| Bò | 240 | 3 ngày | Sữa mỗi ngày đủ ăn | 45 |
| Cừu | 200 | 3 ngày | Len mỗi 2 ngày trưởng thành đủ ăn | 60 |
| Thỏ | 160 | 2 ngày | Lông thỏ mỗi 2 ngày trưởng thành đủ ăn | 70 |
| Dê | 300 | 3 ngày | Sữa dê mỗi 2 ngày trưởng thành đủ ăn | 45 |
| Heo | 420 | 3 ngày | Nấm củ mỗi 2 ngày trưởng thành đủ ăn | 110 |

Mỗi con ăn 1 phần thức ăn/ngày và chỉ được vuốt ve một lần/ngày. Thân thiết
4/5 trở lên cho gấp đôi sản lượng. Con non lớn qua ngày; vật nuôi bị đói
không chết, nhưng không tạo sản phẩm. Sản phẩm chưa lấy vẫn được giữ lại
trong chuồng. Auto toàn bộ tự mua trong khu đã mở và tôn trọng sức chứa riêng.

Mục tiêu dài hạn: thu hoạch **30 nông sản** và đạt **1.000 xu bán hàng**.
Tiền đã chi không làm giảm mục tiêu. Đạt mục tiêu vẫn chơi tiếp được.
Nếu hết vốn, đến gần cây và E để làm thuê: cơ bản tốn 4 sức, nhận 6 xu,
1 gỗ và 2 XP; tay nghề Kiếm sống tăng tiền/gỗ và giảm sức.

## Chế độ menu dòng

```bash
python3 main.py --text
```

Menu cũ: `1` trồng, `2` tưới, `3` thu hoạch/dọn, `4` mua giống, `5` bán,
`6` nâng cấp, `7` ngủ, `8` làm thuê, `f` cánh đồng, `b` chuồng, `k` sổ cá,
`c` nhân vật, `h` hướng dẫn, `s` lưu, `0` thoát.
Chọn ô bằng `A1`, `A1 A2`, `A1,A2`, hoặc `all`; Enter cũng chọn mọi ô phù hợp.

`m` mở bản đồ dòng, `i` xem kho item. Trong bản đồ nhập w/a/s/d rồi Enter;
có thể nhập liền nhiều bước như `wwaadd`. `e` tương tác, `i` túi, `b` về
menu, `q` lưu và về menu, `atlas` xem tổng quan, `j` xem sổ dân làng có chân dung.
Đứng cạnh NPC, nhập `e`, chọn chủ đề `1`–`3`, rồi chọn câu trả lời cho cả
hai lượt bằng `1` hoặc `2`. Cả hai phía được in rõ; `0` hủy. Trong bản đồ
dòng cũng dùng `c` để phân bổ điểm nhân vật.
Trong câu cá dòng, `r` nâng và Enter hạ theo từng
bước; thời gian chờ nhập không làm cá tự chạy.

## Lưu game và tùy chọn

Tự lưu sau hành động, di chuyển và khi thoát bằng Q/Ctrl+C. Chế độ menu
cũng lưu khi EOF. Lần chạy sau tiếp tục `saves/farm.json` cạnh `main.py`.
File lưu các phiên bản 1–6 được đọc và bổ sung dữ liệu mới tự động;
ruộng, tiền, kho đồ, vật nuôi, vị trí và kinh nghiệm được giữ nguyên.
Chỉ khu hiển thị ruộng được chuyển về cánh đồng mới. File lưu mới dùng
phiên bản 7, giữ cả nhiệm vụ ngày, tiến độ hướng dẫn, phần thưởng nhập môn,
tên/ngoại hình/xuất thân, trạng thái intro, thuộc tính/tay nghề và bộ sưu tầm cá.
Ván cũ thiếu khu cá mới hoặc mục sưu tầm sẽ được bổ sung mặc định 0, không mất đàn cũ. Ván cũ giữ nguyên hình
nhân vật đã có, mặc định tắt hướng dẫn để không ngắt việc đang chơi.

```bash
python3 main.py --new --name "Vườn nhà"
python3 main.py --save ./my-farm.json
python3 main.py --no-color
python3 main.py --ascii
python3 main.py --text --no-clear
python3 main.py --help
```

`--new` sao lưu ván cũ tại `<file-lưu>.bak-<thời-gian>`. Mở lại bằng
`--save đường-dẫn-bản-sao`. File hỏng được báo lỗi. Khi ghi file thất bại,
game hiển thị lý do và giữ ván đang chơi để thử lưu lại.

`NO_COLOR` tắt màu. `--no-clear` chọn menu dòng để giữ lịch sử màn hình.
Đầu vào/đầu ra chuyển hướng tự dùng menu dòng, không có mã màu ANSI.
Dùng terminal/font UTF-8 để hiển thị tiếng Việt.

## Kiểm tra và cấu trúc

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q main.py farmgame tests
```

`model.py` giữ trạng thái và luật trồng cây, `world.py` giữ bản đồ,
`animals.py`/`fishing.py` giữ hoạt động, `inventory.py` quản lý gửi-rút đồ,
`villagers.py` giữ nhân vật, hội thoại và quan hệ,
`dialogue.py` giữ các lượt đối đáp, `progression.py` giữ điểm/cấp và bonus,
`identity.py` giữ hồ sơ và nội dung mở đầu, `start_screen.py` giữ menu/tạo nhân vật,
`presentation.py` xử lý chữ gõ dần, `credits.py`/`credits.txt` giữ phần ghi công,
`tutorial.py` theo dõi thực hành, `tutorial_ui.py` hiển thị Lan hướng dẫn,
`daily.py` quản lý nhiệm vụ ngày, `automation.py` lập kế hoạch và thực thi auto,
`world.py`/`mining.py` giữ mỏ khoáng, `forge.py` giữ công thức rèn,
`dungeon.py` giữ luật chiến đấu theo lượt,
`activity_ui.py` điều khiển nhiệm vụ/auto, `navigation.py` tìm đường dùng chung,
`map_art.py` vẽ ô bản đồ, `map_view.py` bố trí camera/khung/thanh thể lực,
`storage.py` lưu JSON, `explore.py` là giao diện bản đồ curses,
`tui.py` vẽ khung nổi, bóng đổ và căn chữ theo ô Unicode;
`terminal.py`/`text_activities.py` là giao diện menu dòng. `main.py` khởi động.
# mossbrook_meadow
