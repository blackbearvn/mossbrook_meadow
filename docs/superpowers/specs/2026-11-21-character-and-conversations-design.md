# Nhân vật, cánh đồng xa nhà và đối thoại

## Yêu cầu

Game Python terminal hiện tại cần cấp độ/XP/điểm thuộc tính/tay nghề có tác
dụng thực tế, map lớn hơn với ruộng xa nhà, đối thoại hai chiều có lựa chọn.
Python3.10+ chỉ thư viện chuẩn, tiếng Việt, giữ tiến trình file lưu trước.

## Nhân vật và hợp đồng API

Giữ level=1+xp//40. Mỗi lần lên cấp nhận quyền phân bổ1 thuộc tính và2 tay
nghề. Điểm còn lại được suy ra từ level và tổng điểm đã phân bổ, không lưu
trùng số dư. Mỗi thuộc tính/tay nghề có5 bậc, mặc định0. Người có XP cũ nhận
đủ quyền phân bổ theo cấp hiện tại. Tăng XP qua harvest/fish/animal/work và
lựa chọn trả lời đầu tiên/ngày của mỗi NPC. Chỉ thao tác thành công mới có XP.

`progression.py` không import model runtime: ATTRIBUTES và SKILLS dict các
Definition(name,description); empty_attributes(), empty_skills();
attribute_points(farm), skill_points(farm), energy_limit(farm),
action_cost(farm,action), sale_price(farm,item_key), gain_xp(farm,amount)->str,
upgrade_attribute(farm,key)->str, upgrade_skill(farm,key)->str,
character_lines(farm)->list[str]. Import GameError cục bộ.

Farm thêm attributes dict keys endurance/dexterity/focus và skills dict
keys farming/fishing/ranching/foraging. Thêm properties energy_limit,
attribute_points,skill_points và award_xp(amount) delegate gain_xp.

- endurance Thể lực: +4 năng lượng tối đa/bậc, khi nâng hồi ngay4.
  max_energy tiếp tục giữ mức nền20/30; mọi ngủ/hiển thị/validate dùng energy_limit.
- dexterity Khéo léo: bậc3 trở lên giảm1 sức trồng/thu hoạch, tối thiểu1.
- focus Tập trung: mỗi lần kiếm XP được cộng thêm1 XP/bậc.
- farming Trồng trọt: giá bán cây +10%/bậc; bậc3 thêm1 nông sản/ô.
- fishing Câu cá: thanh câu rộng thêm0.025/bậc, tốn max(1,3-rank//2) sức.
- ranching Chăn nuôi: giá bán trứng/sữa/len +10%/bậc; bậc3 thêm1 sản phẩm
  mỗi lượt sinh sản (cộng với bonus thân thiết vật nuôi).
- foraging Kiếm sống: làm thuê nhận6+2*rank xu,1+rank//2 gỗ;
  tốn max(1,4-rank//2) sức, kiếm2 XP cơ bản.

sale_price nhận key chuẩn ITEMS (`crop:ca_rot`, `milk`, `ca_ro`), trả giá bán
đơn vị sau bonus, phần lẻ làm tròn xuống. Không cộng thưởng vào sales trước
khi bán. Existing APIs Farm.plant/water/harvest/sleep/work/sell_all giữ nguyên.
Crop harvest +base crop.xp qua award_xp; fish +5; collect +3*quantity; focus
được cộng một lần mỗi hành động. XP crossing nhiều cấp báo đủ điểm vừa nhận.

## Map và ruộng

world map128×64, FIELD_ORIGIN=(26,42), ruộng4..6 ô; LANDMARKS farm=('Cánh đồng',
(27,41)). Đặt đường đến ruộng, khu bao quanh đi được; HOME_DOOR4,3/nhà/nội
thất/các NPC cũ giữ vị trí. Khoảng cách nhà→ruộng >50 ô. Cánh đồng cũ gần
nhà chuyển thành sân/cỏ, không còn nhận thao tác trồng trọt. Nội dung plots
A1..F6 giữ nguyên, chỉ thay vị trí hiển thị. Giữ mọi static walkable cũ để
save đang ở vị trí đó vẫn hợp lệ, thêm cổng boundary cũ để nối map rộng.
Thêm Thung Lũng Đông, Đồi Trà, Bãi Bồi, đường/cầu kết nối mọi vùng. LANDMARKS
bổ sung valley/tea/floodplain; atlas cần map glyph cho mọi key mới.
location_name nhận diện 'Cánh đồng' ở khu ruộng, khu mới và cũ.

## Đối thoại

`dialogue.py`: DialogueChoice(id,text,next_node), DialogueNode(id,npc_line,
choices:tuple[DialogueChoice,...]), Conversation(npc_id,topic,node_id,
history:list[str],done=False, credited=False). Conversation chứa nodes dict
hoặc cấu trúc nội bộ để cố định nội dung trong lượt trò chuyện.
begin_dialogue(farm,npc_id,topic='greet')->Conversation: validate người/địa
điểm/topic, không mutate Farm; history bắt đầu một câu NPC thực sự hỏi.
dialogue_node(conversation)->DialogueNode; choose_response(farm,conversation,
choice_id)->str: validate gầnNPC/ID/state trước mutation; thêm lời 'Bạn: ...'
và phản hồi NPC vào history, chuyển node. Mỗi chủ đề có >=2 lượt lựa chọn
của người chơi, mỗi lượt >=2 câu trả lời; lựa chọn khác nhau dẫn đến lời
đáp hoặc câu hỏi tiếp nối khác nhau. Cả5NPC có nội dung riêng cho3topics.
Chào hỏi thay đổi ngày/mưa/thân thiết. Lượt trả lời đầu trong ngày gọi talk
để ghi quan hệ, nhận3XP bằng farm.award_xp chỉ nếu talked_on trước đó !=day.
Không nhận thêm XP/quan hệ từ việc lặp hoặc khởi động lại. API talk cũ giữ
để dùng compatibility nhưng giao diện sử dụng đối thoại mới.
Hoàn thành thì done; không được gửi choice lặp để nhận thưởng.

UI curses: C mở bảng nhân vật level/XP/điểm còn/thuộc tính/taynghề, lựa chọn
nâng có mô tả ảnh hưởng/giá1điểm/cap5. E NPC→chủ đề→NPC hỏi + người chơi
chọn câu trả lời→NPC đáp+hỏi tiếp→chọn tiếp→lời kết+transcript; Q/Esc quay
lại, hủy trước khi trả lời không mutate. Tự lưu sau upgrade/response.
History đầy đủ đọc được (wrap_cells/reader), cả lời người chơi và NPC hiện
trong giao diện. Text mode có C/c bảng nhân vật (cả menu chính và map),
E mở cuộc đối thoại theo chuỗi; người chơi chọn1/2,0/q hủy, lời2bên in rõ.
HUD và giá trong shop/inventory phản ánh energy_limit/sale_price thực tế.

## Save4 và kiểm tra

Save schema4 thêm attributes/skills, đọc schema1/2/3. Defaults0, giữ XP/đàn/
quan hệ/túi/ruộng/vị trí. Validate exact keys,0..5 int(notbool), phân bổ <=
ngân sách cấp, energy<=energy_limit. Không lưu dở hội thoại (XP/quan hệ đã
lưu khi chọn). Khôi phục oldsave không trồng lên NPC/công trình. JSON ghi
nguyên tử, file hỏng không tự ghi đè.

Test cấp/qua nhiều cấp/point budget/cap/invalid atomic, mọi bonus có tác dụng,
focus không thưởng thao tác sai, maxenergy/sleep/upgrade tương thích. MapBFS
mọi nơi, ruộng xa nhà và render relocated old crops, oldwalkable preserved.
Đối thoại5×3 đủ2choice-turns, hai nhánh khác nhau, cancellation/repeat/invalid/
distance atomic,1reward/day, UIhai bên. Migration1/2/3 và roundtrip4. Chạy
unittest/compileall, main.py PTY/profile-upgrade/moving/farming/dialogue/save.
