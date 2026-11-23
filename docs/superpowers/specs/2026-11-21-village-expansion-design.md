# Mossbrook Meadow: làng, câu cá, chăn nuôi và nhà ở

## Trải nghiệm

Mở rộng game Python terminal hiện tại thành bản đồ làng di chuyển trực tiếp
bằng WASD/mũi tên. E tương tác theo vị trí; I xem túi đồ; Q lưu và thoát.
Python 3.10+, thư viện chuẩn; curses cho terminal tương tác, menu dòng cho
stdin/terminal không hỗ trợ, `--text` chọn menu cũ. Tất cả lời hướng dẫn tiếng Việt.

Làng có ruộng tối đa 6 × 6, nhà, cửa hàng, chuồng và hồ. Cây/nước/tường chặn
đường. Đi bộ không tốn năng lượng hay làm đổi ngày. Trồng/tưới/thu hoạch
giữ luật cũ. Bản đồ nhỏ đủ dùng ở 80 × 24, có viewport cho terminal hẹp.

Nhà có nội thất thật đi lại được: giường Z, tivi V, rương C, cửa D. E trước
cửa vào/ra; E cạnh giường ngủ. Tivi cho biết thời tiết ngày mai, đọc nhiều
lần không đổi dự báo. Ngủ dùng dự báo đã lưu làm thời tiết ngày mới, rồi
tạo dự báo tiếp theo. Không tự tua ngày vì chờ nhập hoặc di chuyển.

Câu cá có thanh điều khiển và cá di động. Space nâng thanh, thả để hạ;
giữ cá trong thanh đến khi tiến độ đầy. Tốn 3 năng lượng khi quăng cần,
thoát hoặc tuột cá không nhận thưởng; nhận cá/kinh nghiệm đúng một lần.
Nuôi gà, bò, cừu: mua con non, mua thức ăn, cho ăn, vuốt ve, lấy trứng/sữa/len.
Mỗi con chỉ ăn/vuốt ve một lần mỗi ngày, lớn qua ngày, có sản phẩm nếu đủ
tuổi và được ăn. Con bị đói không chết, không cho sản phẩm. Chuồng ban đầu
4 chỗ, nâng lên 8. Mức thân thiết cao giúp tăng sản lượng.

Kho item hiển thị giống, nông sản, cá, thức ăn và sản phẩm vật nuôi. Rương
trong nhà cho gửi/rút số lượng cụ thể hoặc tất cả. Bán hàng chỉ bán đồ có
giá trong túi; không bán hạt, thức ăn hoặc đồ đã cất trong rương.

## Giao diện các mô-đun (ràng buộc tích hợp)

`catalog.py` xuất Crop, CROPS, WEATHER, Item(name, sell_price, buy_price),
EXTRA_ITEMS, ITEMS. Khóa giống `seed:ca_rot`, nông sản `crop:ca_rot`, tương
tự cho các cây khác. Khóa đồ khác: `ca_ro`, `ca_chep`, `ca_hoi`, `ca_vang`,
`egg`, `milk`, `wool`, `feed`, `wood`. ITEMS là toàn bộ các khóa này.

Farm giữ nguyên API cũ, thêm area='village', player_x=10, player_y=7,
facing='down', forecast='cloudy', items=dict EXTRA_ITEMS (feed=8, còn lại=0),
chest=dict ITEMS (tất cả=0), animals=list[Animal], barn_capacity=4,
fish_caught=0. Farm.sleep(next_weather=None) dùng forecast khi không truyền
tham số; gọi advance_animals trước khi kết thúc ngày. Farm.forecast_report()
chỉ trả nội dung, không thay đổi trạng thái. Farm.sell_all() bán cả cá/sản
phẩm vật nuôi/gỗ trong items. Farm.buy_item(key, quantity) mua mặt hàng
buy_price > 0. Nâng chuồng bằng upgrade('barn'), giá 280, 4 lên 8 chỗ.

`inventory.py`: count_item(farm, key), inventory_rows(farm) trả list tuple
(key, name, bag_count, chest_count); transfer_item(farm, key, quantity,
direction) với direction deposit/withdraw; deposit_all(farm) gửi mọi đồ
trong túi vào rương. Thao tác kiểm tra đầy đủ trước khi đổi số lượng.

`world.py`: VILLAGE_WIDTH=32, VILLAGE_HEIGHT=14, HOME_WIDTH=16, HOME_HEIGHT=9;
HOME_DOOR=(4,3), BARN_DOOR=(15,6), SHOP_DOOR=(26,3), TV=(3,2), BED=(12,2),
CHEST=(3,5), EXIT=(8,8), FIELD_ORIGIN=(3,4).
tile_at(area,x,y,size=4)->str; walkable(area,x,y,size=4)->bool;
move(farm,direction)->bool (up/down/left/right; đổi hướng ngay cả khi bị chặn);
plot_at(x,y,size)->str|None; target_plot(farm)->str|None (ô trước mặt rồi dưới chân);
is_near(farm,kind)->bool (home,barn,shop,water,tv,bed,chest,exit,forest);
context(farm)->tuple[str,str] (mã hành động, nhãn hướng dẫn), enter_home(farm),
leave_home(farm), location_name(farm)->str. Trường không hợp lệ ném GameError.
Cửa ngoài và các đồ nội thất không đi xuyên được; tương tác khi kề 1 ô.
context ưu tiên nội thất/cửa, rồi ruộng, rồi hồ/rừng. Mã hành động: home,
exit,tv,bed,chest,barn,shop,plot,fish,forest,none. Không phụ thuộc curses.

`animals.py`: Animal(kind,name,age=0,fed=False,petted=False,friendship=0,
produce=0,days_since_product=0). ANIMAL_TYPES ánh xạ chicken/cow/sheep đến
AnimalType(name,price,product,mature_days,interval). Giá 80/240/200,
product egg/milk/wool, tuổi trưởng thành 2/3/3 ngày, chu kỳ 1/1/2 ngày.
buy_animal(farm,kind,name=None), buy_feed(farm,quantity), feed_animals(farm),
pet_animal(farm,index), collect_products(farm), advance_animals(farm) trả str.
Hàm hoạt động trên Farm, không áp đặt vị trí (giao diện kiểm tra vị trí).
Import Farm/GameError cục bộ hoặc TYPE_CHECKING để tránh vòng import model.

`fishing.py`: FishingRound(rng=None) có fish_key:str, bar:float, target:float,
progress:float, done:bool, caught:bool, claimed:bool; step(dt,holding) cập nhật
thanh và cá theo dt, không dùng thời gian tường. start_fishing(farm,rng=None)
kiểm tra kề hồ và năng lượng rồi trả lượt câu; finish_fishing(farm,round)
trao thưởng một lần nếu done và caught, cập nhật items/fish_caught/xp.

`explore.py`: ExplorerGame(farm,save_path,color=True,clear_screen=True)
có messages:list[str] và run()->int. Chỉ import curses khi thực sự dùng.
Vẽ map + crop overlay + nhân vật, có help, menu gieo hạt/cửa hàng/nâng cấp/
chuồng/túi/rương, tivi dự báo, giường xác nhận nếu cây đói nước. Quăng cần
lưu ngay khoản năng lượng đã dùng. Mọi hành động thay đổi trạng thái và
di chuyển đều tự lưu. Q/Ctrl+C trả mã 0 khi lưu được, 1 nếu lỗi lưu.
Xử lý cửa sổ resize và ký tự Unicode; lỗi hiển thị không làm mất ván chơi.

## File lưu và kiểm tra

Phiên bản JSON 2 chứa toàn bộ vị trí, nội thất, dự báo, túi, rương và đàn vật
nuôi. Đọc được phiên bản 1 bằng cách bổ sung trường mới, giữ nguyên ruộng/
tiền/hạt/nông sản/kinh nghiệm. Vẫn ghi nguyên tử, không ghi đè file hỏng.
Test luật đi/chặn, các điểm đều tới được, vào/ra nhà, dự báo không đổi,
vòng vật nuôi, câu cá/thưởng một lần, chuyển đồ không nhân bản, bán không
lấy đồ trong rương, migration v1 và roundtrip v2. Chạy lại 35 test hiện tại,
thêm kiểm tra CLI và PTY cho WASD/E, nhà/tivi/rương, resize và Ctrl+C.
