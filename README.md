# Mossbrook Meadow

**Mossbrook Meadow** là game nông trại tiếng Việt chạy trực tiếp trong terminal.
Bạn bắt đầu với một mảnh vườn nhỏ, trồng trọt, chăm vật nuôi, câu cá, nấu ăn,
trò chuyện với dân làng và dần mở rộng cuộc sống ở Mossbrook Meadow.
Màn hình chính đặt logo ở giữa, phía trên danh sách lựa chọn. Hội thoại có
cử chỉ, phản ứng và lời tạm biệt riêng theo thời tiết, mức thân thiết và
tính cách từng người, thay vì chỉ đọc câu hỏi–đáp cố định.

Trò chơi có bản đồ làng rộng, hệ thống ngày – thời tiết – năng lượng, nhiệm vụ
hằng ngày, túi đồ, chợ, nhà ở, chuồng trại và hồ câu. Ngoài phần nông trại còn
có **Mỏ Khoáng** để đào quặng, **Lò Rèn** để nâng cấp trang bị và
**Hang Sâu** 5 tầng với cửa sổ chiến đấu riêng theo lượt: người chơi bên
trái, quái bên phải, mỗi bên có thanh HP và MP ở trên, nhật ký trận đấu ở dưới.
Quái báo trước ý định; người chơi có thể tấn công, dùng kỹ năng tiêu MP, đỡ đòn,
uống thuốc hoặc rút lui. Hệ thống **thành tựu**
ghi lại các cột mốc như vụ thu hoạch đầu tiên, chinh phục Hang Sâu và rèn
trang bị Huyền thoại. Lò Rèn nâng 5 slot trang bị
(mũ, kiếm, giáp, quần, giày) qua 5 cấp bậc: Bình thường, Hiếm, Sử thi,
Truyền thuyết và Huyền thoại. Hội thoại với dân làng dùng
hộp thoại ở cuối màn hình theo phong cách RPG: chân dung, tên người nói,
chữ hiện dần và các lựa chọn trả lời. Mỗi dân làng có 8 tuyến chủ đề, gồm
chào hỏi, công việc, chuyện làng, ước mơ, kỷ niệm, lễ hội, điều chưa kể và
chuyện ngày mai. Mỗi cuộc trò chuyện có thêm cử chỉ, phản ứng theo lựa chọn
và lời kết riêng, nên người dân không còn nói như một cỗ máy.

Bảng nhiệm vụ ngày có hơn 20 loại nhiệm vụ, gồm trồng trọt, chăn nuôi, câu cá,
khai mỏ, nấu ăn, rèn trang bị và Hang Sâu. Hệ thống **thành tựu** có 12 nhóm,
mỗi nhóm 5 bậc từ Bình thường đến Huyền thoại, theo dõi tiến độ dài hạn và
tặng điểm thành tựu. Người chơi có thể tự do khám phá hoặc dùng chế độ **Auto**
để nhân vật tự làm việc.

Game chỉ dùng thư viện chuẩn của Python, không cần cài thêm gói và không cần
kết nối mạng.

## Yêu cầu

- **Python 3.10 trở lên**
- Một terminal hỗ trợ Unicode để có giao diện đẹp nhất
- Kích thước khuyến nghị: **80 × 24** trở lên

## Cách chạy

Mở terminal tại thư mục dự án và chạy:

```bash
python3 main.py
```

Game sẽ mở menu chính. Từ đây bạn có thể:

1. **Tiếp tục** ván đã lưu
2. **Tạo nhân vật mới**
3. Xem **Credit**
4. Đọc **Hướng dẫn**
0. **Thoát game** (có cửa sổ xác nhận)

### Chạy bằng giao diện dòng lệnh

Dùng khi terminal không hỗ trợ curses hoặc bạn thích nhập lệnh từng dòng:

```bash
python3 main.py --text
```

Trên Windows có thể dùng:

```powershell
py main.py --text
```

### Một số tùy chọn khi chạy

| Lệnh | Tác dụng |
| --- | --- |
| `python3 main.py` | Mở menu và vào game |
| `python3 main.py --quick` | Bỏ qua menu, vào thẳng ván đang lưu (hoặc tạo ván mới nếu chưa có) |
| `python3 main.py --new` | Tạo ván mới, sao lưu ván cũ trước |
| `python3 main.py --name "Vườn Nắng"` | Đặt tên nông trại cho ván mới |
| `python3 main.py --save duong/dan/farm.json` | Chọn file lưu khác |
| `python3 main.py --ascii` | Dùng ký tự ASCII đơn giản |
| `python3 main.py --no-color` | Tắt màu |
| `python3 main.py --intro` | Xem lại đoạn mở đầu |
| `python3 main.py --skip-intro` | Bỏ qua đoạn mở đầu |

Mặc định tiến trình được lưu tại `saves/farm.json`.

## Điều khiển cơ bản

| Phím | Hành động |
| --- | --- |
| `WASD` / phím mũi tên | Di chuyển |
| `E` | Tương tác với người, cửa, ruộng, mỏ… |
| `C` | Mở hồ sơ nhân vật: Hồ sơ / Trang bị / Túi đồ / Thành tựu |
| `Tab` / `Shift+Tab` | Chuyển tab trong hồ sơ, túi đồ, chợ, chuồng |
| `1–5` trong tab Trang bị | Chọn ô trang bị |
| `Enter` / click | Mở tooltip trang bị |
| `I` | Mở túi đồ |
| `N` | Nhiệm vụ hằng ngày |
| `O` | Bật/tắt và chọn chế độ Auto |
| `M` | Bản đồ tổng quan |
| `R` | Danh sách khu vực và đi nhanh |
| `F` | Bảng cánh đồng |
| `B` | Sổ chuồng vật nuôi |
| `K` | Bộ sưu tầm cá |
| `G` | Đổi giao diện Unicode / ASCII |
| `Z` | Đổi khung bản đồ rộng |
| `H` / `?` | Trợ giúp |
| `P` / `F5` | Lưu game |
| `Q` | Lưu và về menu chính |

Các menu có tab chỉ dùng `Tab` / `Shift+Tab` để chuyển tab.
Tab **Trang bị** hiển thị 5 ô vuông cho mũ, kiếm, giáp, quần và giày.
Chọn một ô rồi nhấn `Enter` hoặc click để xem tooltip cấp bậc, hiệu ứng và
vật liệu rèn kế tiếp. Tab **Thành tựu** theo dõi tiến độ và điểm thành tựu;
nhấn `Space` để xem danh sách đầy đủ.

Trong trận đấu ở Hang Sâu, quái sẽ hiện **ý định** trước mỗi lượt. Nhấn
`1` để tấn công, `2` để uống thuốc, `3` để rút lui, `4` để đỡ đòn
(giảm một nửa sát thương của đòn kế tiếp) và `5` để dùng kỹ năng nặng
(tiêu 3 MP). MP đầy lại khi bắt đầu trận mới hoặc xuống tầng tiếp theo.

Khi đang chơi, nhấn `Q` sẽ lưu tiến trình rồi trở về menu chính. Chọn **Thoát**
ở menu để đóng game; game sẽ hỏi xác nhận trước khi thoát.
