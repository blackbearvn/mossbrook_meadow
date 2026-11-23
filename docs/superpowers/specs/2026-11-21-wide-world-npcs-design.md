# Làng rộng và dân làng

Mở rộng game Python terminal hiện tại: map 80×36 thay cho 32×14, camera theo
người chơi, bản đồ tổng quan và 5 NPC có hội thoại. Giữ nguyên nhà, ruộng,
chuồng, tiệm, hồ cũ và các vị trí cũ. Python 3.10+, chỉ thư viện chuẩn.

## Bản đồ và dân làng

Giữ phần cũ x<32,y<14, mở lối phía đông (31,7), phía nam (10,13), (26,13).
Thêm Đồng Hoa ở x32–44,y3–16; Rừng Thông phía tây nam x2–34,y17–33;
Quảng trường phía đông x49–68,y12–23; Hồ Sen đông nam x54–72,y26–31;
Đồi Gió đông bắc x69–76,y3–11. Suối x45–47 bắc–nam, có cầu tại y7 và y21.
Đường liên thông tất cả khu và vị trí NPC. Địa hình không được chặn tọa độ
các NPC hoặc cô lập lối vào. Mọi vị trí ruộng 4–6 ô vẫn dùng được.

NPC cố định, hiển thị bằng số 1–5, chặn bước đi vào nhưng không thay đổi
terrain walkable dùng để kiểm tra save. Nếu save cũ trùng vị trí NPC thì
vẫn tải được, có thể bước ra và nói chuyện ngay tại ô đó. NPC không có
trong nhà. E kề một ô để trò chuyện, hoặc E khi trùng vị trí do save cũ.

| ID | Tên | Nghề | Glyph | Vị trí |
| --- | --- | --- | --- | --- |
| lan | Lan | Chủ tiệm | 1 | 28,5 |
| tu | Bác Tư | Người câu cá | 2 | 30,10 |
| an | An | Người làm vườn | 3 | 39,10 |
| mai | Mai | Thủ thư | 4 | 55,20 |
| son | Sơn | Người giữ rừng | 5 | 20,25 |

## Hợp đồng API

`villagers.py`: NPC frozen dataclass(id,name,role,glyph,position,description);
NPCS dict các ID trên; TOPICS dict greet/work/village nhãn tiếng Việt;
empty_friendships()->dict[str,int], empty_talked_on()->dict[str,int] đều zero;
npc_at(x,y,area='village')->NPC|None; nearby_npc(farm)->NPC|None;
talk(farm,npc_id,topic='greet')->str. Không import model ở top level (local
GameError/TYPE_CHECKING). nearby ưu tiên ô trước mặt rồi khoảng cách, ID.
talk yêu cầu đứng kề/đúng ô NPC, kiểm tra ID/topic trước khi đổi trạng thái.
Mỗi lần nói chuyện có nội dung theo nhân vật/chủ đề/ngày/thời tiết/mức thân.
Lần trò chuyện đầu trong ngày +1 thân (max10), các lần khác không tăng.
Không trừ sức, tiền, tăng XP hay tự sang ngày. Nội dung tiếng Việt tự viết.

Farm thêm friendships và talked_on dict đủ 5 ID, bắt đầu zero. Save JSON
version3, đọc được v1 và v2 bằng bổ sung trường mặc định; giữ nguyên tất cả
trạng thái cũ. Kiểm tra friendship 0..10, talked_on 0..farm.day.

`world.py`: VILLAGE_WIDTH=80, VILLAGE_HEIGHT=36, giữ API cũ. Di chuyển phải
kiểm tra NPC đang chiếm ô đích bằng npc_at. context ưu tiên cửa/nội thất,
sau đó NPC, rồi ruộng/hồ/rừng; trả ('npc', 'E: trò chuyện với ...') khi phù hợp.
location_name trả 'Làng Mossbrook Meadow / <khu vực>' hoặc 'Trong nhà'. Export
LANDMARKS dict key -> (nhãn, (x,y)): farm(10,7), home(4,3), shop(26,3),
barn(15,6), meadow(39,10), square(55,20), forest(20,25), lake(53,28), hill(72,6).
Giữ glyph cũ, thêm hoa ',' (walkable); cầu là '=' ưu tiên hơn nước.

Giao diện curses: camera luôn theo người, 2 ký tự/ô khi rộng>=64, 1 khi hẹp;
vẽ NPC trên nền và dưới @; header hiển thị khu vực và tọa độ. E mở menu
3 chủ đề, sau mỗi câu có màn hội thoại xuống dòng/đọc được hết, tự lưu trạng
thái và cho tiếp tục chọn chủ đề. Q/Esc hủy không tăng thân thiết.
M mở tổng quan toàn map (thu nhỏ vừa cửa sổ, NPC/player được giữ), J mở danh
sách dân làng kèm nghề, vị trí và mức thân. Tất cả dùng được khi resize.
Menu dòng có viewport, cùng hội thoại E, 'atlas' xem bản đồ tổng quan,
'j' xem dân làng. Không ghi đè các phím m/b/i cũ.

## Kiểm tra

BFS tới mọi khu/NPC, cầu qua suối, border dùng kích thước map mới. Kiểm tra
các tọa độ cũ giữ terrain, NPC collision và ưu tiên tương tác, camera ngoài
khu cũ. Đối thoại gần/xa/trong nhà, đầu vào lỗi không mutate, +1/ngày/max10,
thay đổi nội dung và không tự đổi ngày/tốn năng lượng. Migration v1/v2 và
roundtripv3 lưu thân thiết, ngày đã chào; không tăng lại khi khởi động lại.
Chạy toàn bộ tests cũ, compileall và main.py PTY: đi sang vùng mới, chat,
atlas, resize, lưu/đọc lại. Rà soát độc lập trước hoàn thành.
