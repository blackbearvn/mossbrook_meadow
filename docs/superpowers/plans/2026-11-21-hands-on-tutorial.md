# Kế hoạch triển khai hướng dẫn tân thủ

**Mục tiêu:** 15 bước thực hành có chỉ đường, nhắc phím, xác nhận hành động
thành công và lưu tiến độ. Thiết kế nằm trong
`docs/superpowers/specs/2026-11-21-hands-on-tutorial-design.md`.

**Kiến trúc:** `tutorial.py` quản lý trạng thái, điều kiện hoàn tất và tìm
đường; model phát sự kiện sau thao tác thành công; `TutorialCoach` phục vụ
cả curses và chế độ dòng. Save phiên bản 6. Chỉ dùng thư viện chuẩn Python.

## Công việc

- [x] Engine: `tutorial.py`, hook trong model/progression và kiểm thử hành
  động thật, sai ô, thời tiết, cây bị thay, ruộng đầy, XP một lần, đường đi.
- [x] Persistence: chuyển save 1–5 sang trạng thái mặc định tắt, nhân vật mới
  được mời học sau intro; kiểm tra dữ liệu và giữ phần thưởng qua lưu/tải.
- [x] UI: lời mời, menu T, chỉ dẫn đầy đủ, đường chấm và khung nhắc phím;
  tạm ẩn vẫn theo dõi thực hành, bỏ qua không ảnh hưởng nông trại.
- [x] Tích hợp hai giao diện: bản đồ, di chuyển, hội thoại Lan, túi, mua hạt,
  trồng/tưới/thu hoạch, vào nhà, tivi, ngủ, bán và nâng điểm nhân vật.
- [x] Kiểm thử hành trình 15 bước qua CLI và PTY, tiếp tục ván đã lưu.
- [x] Cập nhật README và trợ giúp phím T; kiểm tra cú pháp và review độc lập.

## Các lỗi đã xử lý qua kiểm thử và review

- Chỉ tính bước di chuyển thành công, cuộc đối thoại hoàn tất và đúng luống
  lúa mì được theo dõi. Không nhận lại XP khi bỏ qua, bắt đầu lại hoặc tải ván.
- Nếu luống được thay bằng cây khác, tìm ô trống thay vì yêu cầu xóa cây sống.
  Ruộng đầy có chỉ dẫn tưới, ngủ hoặc thu hoạch theo trạng thái cây.
- Chế độ dòng ghi nhận M ngay khi mở bản đồ, vẽ đường chấm và chấp nhận M
  để xem toàn cảnh cả khi vừa bật hướng dẫn bằng T ngay trong bản đồ.
- Hiển thị lời chúc hoàn tất khi người chơi dùng điểm nâng thuộc tính/tay nghề.

## Giới hạn triển khai

- Không đổi bản đồ hay tài nguyên khi đọc lời mời/chỉ dẫn. Người chơi tự
  điều khiển và thực hiện mọi thao tác. Phần thưởng nhập môn là 40 XP cơ bản.
- `Farm()` mặc định tắt hướng dẫn; ván cũ bật bằng T. Nhân vật mới tạo từ
  menu được mời sau intro. Không cần thêm cờ dòng lệnh riêng.
- Thư mục không có Git repository thực; không tạo worktree hay commit.

## Kết quả xác minh

- `python3 -m unittest discover -s tests -q`: 248 tests, OK.
- `python3 -m compileall -q main.py farmgame tests`: mã thoát 0.
- `python3 main.py --help`: có phím T, mã thoát 0.
- Chơi qua PTY thật: tạo nhân vật, chấp nhận hướng dẫn, hoàn thành cả 15
  bước, tạm ẩn/tiếp tục, hội thoại hai lượt, trồng và thu cùng luống, bán
  hàng, nâng chỉ số. Kết thúc ngày 2, cấp 2, 46 XP, save phiên bản 6.
  Mở lại vẫn hoàn tất 15/15, không nhận lại XP và không mời học lặp.
- Review độc lập đã kiểm tra lại các lỗi bản đồ dòng, đường chấm, thông
  điệp hoàn tất và alias M; 12 UI tests đều đạt, không còn lỗi trong phạm
  vi review sau sửa.
