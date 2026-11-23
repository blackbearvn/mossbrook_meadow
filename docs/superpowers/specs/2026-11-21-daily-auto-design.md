# Nhiệm vụ hằng ngày và chế độ tự động

Mở rộng game terminal hiện tại, giữ Python 3.10+ và thư viện chuẩn. Bảng N
có bốn nhiệm vụ đổi sau khi ngủ: chăm ruộng, kiếm sống, câu cá, chăn nuôi,
giao tiếp hoặc bán hàng, chọn theo điều kiện nông trại. Theo dõi thao tác
thành công; nhận xu/XP bằng nút nhận thưởng, mỗi nhiệm vụ chỉ một lần.
Tiến độ và trạng thái đã nhận được lưu ở save 7; đọc được save 1–6.

O mở chế độ auto toàn bộ, trồng trọt, chăn nuôi hoặc câu cá. Chọn chạy
1/3/7 ngày hoặc liên tục, tốc độ chậm/vừa/nhanh. Auto đi từng ô, chăm cây
trước khi thiếu nước, chăm vật nuôi, nhận nhiệm vụ, nói chuyện, câu cá bằng
vật lý minigame thật, mua giống/thức ăn/vật nuôi, bán hàng, nâng cấp và
ngủ. Chỉ mode toàn bộ tự mua vật nuôi/nâng cấp/phân bổ điểm. Không sửa trực
tiếp xu, XP, sản phẩm hoặc dịch chuyển để giả kết quả. Không đụng đồ trong
rương. Mở lại ván luôn ở điều khiển thủ công.

Space/P tạm dừng, O/Esc dừng auto; +/- đổi tốc độ. Curses cập nhật mỗi nhịp,
không chặn bàn phím bằng vòng lặp dài. Chế độ dòng có điều khiển tương đương
và tiếp tục hiển thị tiến độ. Lưu theo hành động, định kỳ khi đi, lúc dừng
và thoát; lỗi lưu dừng auto và báo rõ. Auto có giới hạn thao tác để tránh
lặp vô hạn khi thiếu tài nguyên/đường bị chặn. Hướng dẫn tân thủ vẫn được
giữ; auto toàn bộ có thể làm theo lộ trình học bằng sự kiện thật. Các chế
độ riêng không làm việc ngoài lĩnh vực hoặc tự dùng điểm nâng nhân vật.

Tối ưu có số đo: cache địa hình tĩnh theo khu vực/kích thước ruộng; dùng
chung bộ tìm đường A* cho tutorial và auto. Cache đường/đồ thị có giới hạn,
giữ khả năng tới đúng ô ruộng theo hướng nhìn và tránh NPC. Auto giữ deque
đường đi, chỉ tìm lại khi đích/trạng thái thay đổi; không BFS mỗi khung hình.
Không ghi toàn bộ JSON theo từng ô đi trong auto. Đo trước/sau và kiểm tra
đường ngắn nhất bằng BFS độc lập; không đặt ngưỡng thời gian mong manh vào
unit test.

Kiểm chứng: nhiệm vụ làm sai/thất bại không tăng, không nhận thưởng lặp,
qua ngày đổi đúng, save cũ/invalid an toàn; auto nhiều ngày không làm héo
cây vì tiêu sai sức, chăm thú, đi cả trong/ngoài nhà, nhận dailies, câu thật,
pause/stop/lưu lỗi; giữ 248 bài kiểm thử hiện có. Chơi thử cả CLI và PTY.
