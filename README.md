# Mossbrook Meadow

**Mossbrook Meadow** là game nông trại tiếng Việt chạy trực tiếp trong terminal.
Bạn bắt đầu với một mảnh vườn nhỏ, trồng trọt, chăm vật nuôi, câu cá, nấu ăn,
trò chuyện với dân làng và dần mở rộng cuộc sống ở Mossbrook Meadow.

Trò chơi có bản đồ làng rộng, hệ thống ngày – thời tiết – năng lượng, nhiệm vụ
hằng ngày, túi đồ, chợ, nhà ở, chuồng trại và hồ câu. Ngoài phần nông trại còn
có **Mỏ Khoáng** để đào quặng, **Lò Rèn** để nâng cấp cuốc/kiếm/giáp và
**Hang Sâu** 5 tầng với chiến đấu theo lượt. Người chơi có thể tự do khám phá
hoặc dùng chế độ **Auto** để nhân vật tự làm việc.

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
| `C` | Mở hồ sơ nhân vật: Hồ sơ / Trang bị / Túi đồ |
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

Khi đang chơi, nhấn `Q` sẽ lưu tiến trình rồi trở về menu chính. Chọn **Thoát**
ở menu để đóng game; game sẽ hỏi xác nhận trước khi thoát.
