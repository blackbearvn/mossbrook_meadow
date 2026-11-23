# Nông trại Mây Nhỏ

Tạo game nông trại theo lượt bằng Python, chơi trong terminal bằng menu số.
Đây là dự án mới; triển khai trực tiếp trong thư mục làm việc trống hiện tại.

## Phạm vi và cách chơi

- Python 3.10 trở lên, chỉ dùng thư viện chuẩn, giao diện tiếng Việt.
- Chạy bằng `python3 main.py`; không cần mạng, tài khoản hoặc cài thư viện.
- Ruộng ban đầu 4 × 4, tọa độ A1–D4; nâng cấp tối đa 6 × 6.
- Có cà rốt, lúa mì, cà chua, bắp và bí ngô. Thu hoạch tăng kinh nghiệm,
  mỗi 40 kinh nghiệm tăng một cấp và mở khóa giống cây mới.
- Trồng tốn 2 năng lượng, tưới tốn 1, thu hoạch tốn 2. Ngủ hồi năng lượng
  và chuyển ngày. Cây chỉ lớn khi được tưới hoặc trời mưa, héo sau 3 đêm
  khô liên tiếp. Nông sản đã chín không héo.
- Thời tiết ngày mới được chọn ngẫu nhiên; luật lớn cây sử dụng thời tiết
  của ngày vừa kết thúc. Mưa tưới toàn bộ ruộng trong ngày đó.
- Mua hạt, bán nông sản, mở rộng ruộng, tăng năng lượng, mua hệ thống tưới.
  Có việc làm thuê để kiếm lại tiền nếu hết giống và hết tiền.
- Mục tiêu: thu hoạch 30 nông sản và bán được tổng cộng 1.000 xu.
  Tiếp tục chơi tự do sau khi đạt mục tiêu.

## Cấu trúc

`farmgame/model.py` giữ dữ liệu và luật chơi, không đọc bàn phím hoặc ghi file.
`farmgame/storage.py` kiểm tra và lưu JSON bằng thay thế file nguyên tử.
`farmgame/terminal.py` vẽ bảng màu ANSI, menu và xử lý nhập liệu theo dòng.
`main.py` xử lý tham số, tiếp tục game và khởi động giao diện.

Menu cho phép chọn một ô, nhiều ô hoặc `all`. Tác vụ hàng loạt xử lý các ô
hợp lệ đến khi hết tài nguyên và báo rõ kết quả. Đầu vào lỗi không làm
thay đổi trạng thái. Không dùng emoji để tránh lệch cột trên terminal.
Màu và xóa màn hình tự tắt khi đầu ra không phải TTY; có tùy chọn tắt riêng.

## Lưu và khôi phục

Tự lưu sau hành động thay đổi trạng thái; `s` lưu thủ công, `0` lưu và thoát.
EOF và Ctrl+C cũng lưu tiến trình. Mặc định lưu tại `saves/farm.json` bên
cạnh `main.py`, hỗ trợ `--save PATH`. `--new` sao lưu file cũ trước khi tạo
ván mới. File lỗi hoặc phiên bản không hỗ trợ được báo rõ, không tự ghi đè.
Lỗi ghi file phải hiện cảnh báo và giữ ván chơi trong bộ nhớ.

## Kiểm chứng

Dùng `unittest` cho chu trình trồng–tưới–qua ngày–thu hoạch–bán; năng lượng,
mưa, cây héo, nâng cấp, giống khóa, đầu vào không hợp lệ và phục hồi kinh tế.
Kiểm tra lưu/đọc bằng file thật trong thư mục tạm, từ chối file lỗi.
Chạy CLI trong subprocess với chuỗi thao tác hoàn chỉnh, EOF, Ctrl+C và
terminal giả lập để kiểm tra giao diện, tự lưu và tiếp tục game.
