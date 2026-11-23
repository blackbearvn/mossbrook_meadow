# Lan hướng dẫn tân thủ từng bước

## Trải nghiệm

Sau intro của nhân vật mới, hỏi 'Để Lan dẫn từng bước nhé?' với Bắt đầu/Tự
khám phá. Tutorial theo hành động thật, không chỉ đọc sổ tay; không tự đi,
teleport, trồng hay tua ngày. T mở bảng hướng dẫn ở bất cứ đâu, có tiếp tục,
tạm ẩn và bỏ qua. Ván cũ mặc định off, có thể bật bằng T. Trạng thái được
lưu, không tự bật trở lại sau khi bỏ qua. Intro/credit không tính hoạt động.

15 bước cố định: map → movement(4bước thành công) → talk(Lan2lượt hoàn tất)
→ bag → buy(>=1hạtlúamì) → field → plant(lúamì) → water(cùngô) → home
→ tv → sleep → harvest(cùngô) → sell → character → upgrade.

Hiện mục tiêu, chỉ dẫn theo vị trí/tài nguyên, đường đi dạng dấu· với camera
hiện tại và phím tiếp theo. Chỉ dẫn dùng BFS qua terrain+NPC, dừng ở ô kề
công trình/NPC; dùng ruộngtarget_plot nhất quán. Trong nhà dẫn ra cửa khi
đích ngoài làng, ngoài làng dẫn vào nhà khi đích nội thất. Chỉ đường không
tốn sức, không đổi ngày. Khi tới nơi nhắc đúng E và lựa chọn menu.

Plant/water/harvest theo cùng một plot lưu trong tutorial. Nếu cây mất/héo,
quay về bước plant kèm cách dọn/mua giống/hồi sức, không kẹt ở bước sai.
Mưa/tưới tự động được tính đủ nước, chuyển water khi cây thực sự đủ nước.
Nếu hết sức ưu tiên đường về giường; hết giống dẫn cửa hàng, hết tiền dẫn
làm thuê. Nếu ruộng đầy chỉ cách thu/dọn; không tự xóa cây hoặc tặng tài
nguyên. Đọc tivi không qua ngày. Bán chỉ hoàn thành khi bán thật thành công.

Tới character, mở C mới nhận một lần40XP nhập môn để lên ít nhất một cấp,
giải thích điểm thuộc tính/tay nghề, rồi yêu cầu tự nâng một chỉ số thật.
Không nhận thưởng khi đọc/nhấnT/bỏqua/mở lại save; reward_given lưu riêng.
Khi hoàn tất hiển thị lời chúc, T vẫn đọc được tổng kết.

## Trạng thái/API (hợp đồng tích hợp)

`tutorial.py`: TutorialState(status='off',step=0,moves=0,plot=None,
planted_on=0,watered_on=0,reward_given=False); dataclass, no model runtime
import; status off/pending/active/paused/skipped/completed. active+paused
đều theo dõi thực hành, paused chỉ tắt overlay/path.
Step frozen dataclass(id,title,instructions); STEPS tuple15 thứ tự trên.
Hint frozen dataclass(title,body,key,target:tuple[int,int]|None,path:tuple[
tuple[int,int],...],area:str); hinttarget/path thuộc area hiện tại, giúp UIvẽ.

APIs start_tutorial(farm)->str, pause_tutorial(farm)->str,
resume_tutorial(farm)->str, skip_tutorial(farm)->str,
record_event(farm,event,**details)->str, sync_tutorial(farm)->str,
current_step(farm)->Step|None, tutorial_hint(farm)->Hint|None,
tutorial_lines(farm)->list[str]. Hint/lines read-only không đổi save.
Returnmessage '' nếu không thay đổi, messageLan khi hoàn thành1bước/recovery.
start off/pending/skipped resetstep0/moves/plot/days, GIỮ reward_given để
không farmXP; completed chỉ tổngkếtkhôngreset. start không tựtrừ/tặnggì.
Recordchỉeventkhớpcurrent; eventwrong/failednone không hoàn thành. Khi bước
upgrade nếu mọiattributes/skills đãmax thì tự hoàn thành khi character.

Events đúng keys: map,move(from_x,from_y),talk(npc_id,done),bag,
buy(crop,quantity),plant(coordinate,crop),water(coordinate),enter_home,tv,
sleep,harvest(coordinate),sell,character,upgrade. field tính từ tọa độ thật
qua sync sauđi, không cóevent giả. move chỉ ghi khiworld.move trảTrue;
talk chỉ ởconversation.done; phầnmodelrecord sau cácactionthànhcông;
map/bag/character/tv ởUI, upgradeđiểmattribute/skill ởprogression.

Farm thêm tutorial:TutorialState defaultoff; identity.create_character set
pending. Model plant/water/sleep/harvest/buy_seeds/sell_all local recordevent
sau mutation; progression upgrade localrecord sau mutation; message trống
không ảnh hưởng text cũ. world không sửa, UI moveeventđínhkèm sau moveTrue.

`tutorial_ui.py`: TutorialCoach(ui,farm,save_callback,*,text=False), ui là
ExplorerGame hoặc TerminalGame. public offer()->None hỏi pending, panel()
menuT, event(name,**details)->None gọirecord/log/save nếustatechanged,
sync()->None, draw_curses()->None (sau map/footer, tránh overwrite controls),
draw_text()->None; path_points()->set[tuple] đọc hint. Root chỉ tích hợp
coach vào runtime; moduleUIcó thể tự dùng helper paint/choose/reader/ask.
Offer pending sauintrotrướchànhđộng, cancel chọnTựkhámphá => skipped, không
ghi đè introstate. Panel mởkhôngtặngXP/chỉcontrols; viewexplain đầyđủnhỏwindow.

## Save6 và kiểm tra

Save6 tutorialasdict; đọc1..5 thêm TutorialStateoff, giữmọicũ. Validateexact
statefields/type/capstep0..lenSTEPS-1 (completedstep=lenSTEPSallowed), moves0..4,
plotNonehoặcvalidcurrentplot, dates0..day, rewardbool; statuscompleted phải
step=lenSTEPS, otherstep<lenSTEPS. Invalidfile =>SaveError. Migrationkhông
write. Factorypending tests gameplayunchanged phải bỏ tutorialtrongcomparison.

TDD engineactualpath/actions/wrongsequence/failure/paused/skipresume/nodupXP,
sameplot/rain/dead/recovery, BFSpathneighbor/accessNPCindooroutdoor. Save
roundtripstate/migrations5+validation+reloadreward. UIoffer/wronginput/route
overlay/profileXPevent. TextCLI/realPTY newcreate->skipintro->acceptguide->
15tasksandresume/paused/skip, provefailedactionnotadvance, old218testsrerun.
