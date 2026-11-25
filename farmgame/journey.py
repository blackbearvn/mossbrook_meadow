"""Countryside discoveries, seasonal gathering and village restoration.

Rules shared by both terminal frontends. Reading a journal never changes a
save; only movement, gathering and confirmed community actions record progress.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .catalog import CROPS, ITEMS
from .pages import PAGES, page_for_coord

if TYPE_CHECKING:
    from .model import Farm

SEASONS = ('spring', 'summer', 'autumn', 'winter')
SEASON_NAMES = ('Xuân', 'Hạ', 'Thu', 'Đông')
FORAGE_ITEMS = ('herb', 'berry', 'mushroom', 'tea_leaf', 'shell', 'honey')


def season_index(farm: 'Farm') -> int:
    return ((farm.day - 1) // 28) % 4


def season_name(farm: 'Farm') -> str:
    return SEASON_NAMES[season_index(farm)]


def calendar_line(farm: 'Farm') -> str:
    return f'{season_name(farm)} · ngày {(farm.day-1) % 28+1}/28 · năm {(farm.day-1)//112+1}'


@dataclass(frozen=True, slots=True)
class Site:
    key: str
    name: str
    position: tuple[int, int]
    story: str
    gather: tuple[str, str, str, str]


# Every region has an authored encounter on or immediately beside its road.
# The old village terrain is unchanged: these are walkable map overlays.
_CONTENT = (
    ('residential', 'Bảng hẹn đầu làng', (10, 15),
     'Dưới mái bảng gỗ, Lan để một rổ hạt cho người đến muộn. Tờ giấy của Hà vẫn còn chỗ trống: “Ai rảnh thì cùng sửa lại làng nhé.”',
     ('herb', 'berry', 'mushroom', 'wood')),
    ('meadow', 'Vườn ong của An', (41, 10),
     'Một dải hoa được chừa nguyên giữa các lối mòn. An buộc sợi chỉ đỏ quanh bụi lớn nhất, nhắc mọi người để lại phần mật cho đàn ong.',
     ('honey', 'honey', 'berry', 'wood')),
    ('hill', 'Chuông gió cũ', (72, 8),
     'Chiếc chuông đồng khuyết một mảnh vẫn ngân khi gió lên. Từ đây nhìn thấy ánh đèn nhà Hà; có lẽ chiếc chuông cũng còn sửa được.',
     ('da', 'herb', 'mushroom', 'da')),
    ('tea', 'Luống trà Bác Hai', (111, 10),
     'Dấu dép nhỏ chạy dọc luống trà già. Bác Hai chỉ hái những búp vừa mở, rồi chừa lại một chén đầu mùa cho người từng trồng chúng.',
     ('tea_leaf', 'tea_leaf', 'tea_leaf', 'wood')),
    ('forest', 'Gốc thông đánh dấu', (20, 27),
     'Sơn khắc mũi tên thấp ngang đầu gối để trẻ con cũng tìm được đường. Dưới tán thông có cành khô và vết chân nai còn mới.',
     ('wood', 'herb', 'mushroom', 'wood')),
    ('square', 'Sân hội bên giếng', (57, 20),
     'Mai giữ chiếc chìa khóa kho đèn lồng ở đáy hộp sách. Mỗi mùa, mọi người lại mang một món từ nhà đến chiếc bàn dài quanh giếng.',
     ('herb', 'berry', 'mushroom', 'wood')),
    ('lake', 'Ghế chờ bên sen', (53, 30),
     'Có hai vết lõm trên ghế đá, một chỗ của Bác Tư, một chỗ cho bình trà. Chiếc cần câu dự phòng được dựng sẵn cho người ghé chơi.',
     ('herb', 'tea_leaf', 'mushroom', 'da')),
    ('valley', 'Nền cối xay', (98, 22),
     'Bánh xe gỗ nằm nghiêng dưới cỏ. Minh bảo nếu cối quay lại, nhà có ít ruộng cũng đủ thức ăn cho đàn gà qua những ngày mưa.',
     ('wood', 'herb', 'mushroom', 'da')),
    ('field', 'Nhà ươm bỏ quên', (26, 40),
     'Mái kính phủ bụi, nhưng trên bàn vẫn còn nhãn giống do An viết. Một cây con đã tự mọc qua khe ván, hướng về phía nắng.',
     ('herb', 'berry', 'mushroom', 'wood')),
    ('floodplain', 'Bến lau cạn', (55, 50),
     'Nước rút để lộ những cọc bến cũ. Sơn đặt bó lau ngang lối bùn để người gánh hàng không trượt; dưới rễ lau là một vạt rau thơm.',
     ('herb', 'shell', 'mushroom', 'da')),
    ('beach', 'Thuyền úp trên cát', (108, 50),
     'Màu sơn xanh còn sót lại dưới mạn thuyền. Bác Tư từng chở trà ra đảo trên chiếc này; nay trẻ con dùng nó làm chỗ kể chuyện sóng.',
     ('shell', 'shell', 'shell', 'wood')),
    ('east_meadow', 'Trại hạt theo gió', (274, 55),
     'Những túi vải treo thấp trên hàng rào để giữ hạt cỏ. An muốn thử một vườn cây ở đây, nơi ong không phải băng qua đường lớn.',
     ('herb', 'honey', 'berry', 'wood')),
    ('east_wood', 'Xưởng gỗ ven đường', (562, 55),
     'Hà giữ lại từng chiếc đinh thẳng trong hộp thiếc. Bàn thợ bị mưa dột một góc, còn thân cây đổ phía sau đủ gỗ cho nhiều mái nhà.',
     ('wood', 'honey', 'mushroom', 'wood')),
    ('east_lake', 'Cầu tàu soi mây', (850, 55),
     'Các cọc cầu tàu dừng giữa mặt nước. Bác Tư đã đo lại khoảng cách; chỉ cần một nhóm chịu mang ván đến, bọn trẻ sẽ có chỗ tập câu.',
     ('herb', 'shell', 'tea_leaf', 'da')),
    ('east_coast', 'Đèn dẫn thuyền', (1138, 55),
     'Chóa đèn còn nguyên dưới lớp muối. Vào đêm không trăng, Minh từng đứng đây chờ ánh đèn từ thuyền hàng; giờ chỉ còn tiếng sóng trả lời.',
     ('shell', 'shell', 'honey', 'da')),
    ('south_0_0', 'Bàn picnic dưới dâu', (162, 146),
     'Bác Hai để một mảnh khăn cũ trên ghế cho khách lỡ đường. Bụi dâu rủ xuống mép bàn, mùa quả chín ai đi qua cũng được chia một nắm.',
     ('berry', 'berry', 'berry', 'wood')),
    ('south_0_1', 'Vườn nấm dưới tán', (482, 146),
     'Những khoanh gỗ được xếp theo vòng tuổi cây. Hà và Sơn từng gây nấm ở đây để mang tặng các nhà chưa kịp thu vụ đầu tiên.',
     ('mushroom', 'wood', 'mushroom', 'wood')),
    ('south_0_2', 'Hộp thư trong sương', (802, 146),
     'Hộp thư không còn người nhận, nhưng bên trong vẫn khô. Mai muốn chép lại những bức thư tìm được trước khi sương làm mờ nét mực.',
     ('herb', 'tea_leaf', 'mushroom', 'da')),
    ('south_0_3', 'Chợ muối ven bến', (1122, 146),
     'Vệt trắng trên mặt bàn là muối chứ không phải bụi. Người bán đã đi nơi khác, để lại chiếc cân đồng và lời hẹn quay về khi đèn biển sáng.',
     ('shell', 'shell', 'herb', 'da')),
    ('south_1_0', 'Mỏ đá lộ thiên', (162, 310),
     'Trên phiến đá lớn còn nét phấn của Hà, chia từng khối để khiêng vừa sức. Rêu mới mọc quanh chỗ người thợ thường đặt bình nước.',
     ('da', 'da', 'quang_dong', 'da')),
    ('south_1_1', 'Trạm đo nước', (482, 310),
     'Bác Tư ghi mực nước bằng những vạch nhỏ trên cọc gỗ. Vạch cao nhất mang tên một năm lũ mà cả làng đã cùng nhau đắp bờ.',
     ('herb', 'tea_leaf', 'shell', 'da')),
    ('south_1_2', 'Cây mẹ rỗng ruột', (802, 310),
     'Bên trong thân cây có tổ sóc, còn vỏ ngoài đầy vết sét. Sơn khoanh một vòng đá để nhắc người lấy củi chừa cây già lại.',
     ('wood', 'honey', 'mushroom', 'wood')),
    ('south_1_3', 'Vườn vỏ ốc', (1122, 310),
     'Vỏ ốc được xếp thành hình ngôi nhà nhỏ. Một chiếc mang chữ của Minh từ ngày còn bé; sóng đã xóa nét cuối nhưng vẫn giữ được mái nhà.',
     ('shell', 'shell', 'berry', 'da')),
    ('south_2_0', 'Kho thóc cuối đồng', (162, 474),
     'Mùi rơm khô vẫn còn dưới mái. Trên tường là sổ mượn hạt: người nhận chỉ cần trả lại một phần khi vụ sau đã đủ ăn.',
     ('herb', 'honey', 'mushroom', 'wood')),
    ('south_2_1', 'Guồng nước bên thác', (482, 474),
     'Nước đập đều vào bánh guồng gãy. Minh đã tháo thử một thanh gỗ để học cách lắp; mảnh giấy vẽ lại nằm dưới hòn đá cạnh chân thác.',
     ('da', 'herb', 'tea_leaf', 'da')),
    ('south_2_2', 'Lều ngắm mây', (802, 474),
     'Mai đánh dấu tên những chòm sao trên nóc lều. Trang cuối để trống, chờ một buổi cả làng có thể ngồi đây mà không phải lo mùa đói.',
     ('tea_leaf', 'herb', 'mushroom', 'da')),
    ('south_2_3', 'Mốc đá thủy triều', (1122, 474),
     'Dây thừng cũ được buộc cao trên mỏm đá. Bác Tư dặn đừng hái sạch những vỏ ốc bám dưới thấp; chúng báo nước lên trước khi ta nghe sóng.',
     ('shell', 'da', 'shell', 'da')),
    ('south_3_0', 'Lối ván qua đầm', (162, 638),
     'Những tấm ván khác màu là dấu tay từng gia đình góp lại. Cuối lối có chỗ lau ngả xuống thành mái che, đủ cho hai người tránh mưa.',
     ('herb', 'honey', 'mushroom', 'wood')),
    ('south_3_1', 'Vườn trà lẩn trong rừng', (482, 638),
     'Trà mọc lẫn với cây dại, nhỏ lá mà thơm lâu. Bác Hai nhận ra giống cũ của mẹ và xin mọi người chỉ hái búp, đừng nhổ cả gốc.',
     ('tea_leaf', 'tea_leaf', 'mushroom', 'wood')),
    ('south_3_2', 'Nền vườn quả', (802, 638),
     'Hàng cây non đã lớn quá cọc chống nhưng chưa được tỉa. An buộc lại từng dây vải, tin rằng một vườn cây có thể nuôi được cả xóm.',
     ('herb', 'berry', 'berry', 'wood')),
    ('south_3_3', 'Ghế nhìn chân trời', (1122, 638),
     'Trên lưng ghế là tám nét khắc nhỏ, mỗi người trong làng một nét. Bên cạnh vẫn còn chỗ cho một dấu mới, nếu cậu muốn ở lại lâu hơn.',
     ('shell', 'honey', 'tea_leaf', 'da')),
)
SITES = {key: Site(key, name, position, story, gather)
         for key, name, position, story, gather in _CONTENT}
SITE_POSITIONS = {site.position: site for site in SITES.values()}


def nearby_site(farm: 'Farm') -> Site | None:
    if farm.area != 'village':
        return None
    dx, dy = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0),
              'right': (1, 0)}.get(farm.facing, (0, 0))
    for point in ((farm.player_x+dx, farm.player_y+dy),
                  (farm.player_x, farm.player_y)):
        if point in SITE_POSITIONS:
            return SITE_POSITIONS[point]
    return None


def discover(farm: 'Farm') -> str:
    if farm.area != 'village':
        return ''
    page = page_for_coord(farm.player_x, farm.player_y)
    if page is None or page.key in farm.discovered:
        return ''
    farm.discovered[page.key] = farm.day
    return f'Ghi vào hành trình: {page.name}. U mở sổ, tìm dấu ! để khám phá.'


def gather(farm: 'Farm', key: str) -> str:
    from .model import GameError
    if not isinstance(key, str) or key not in SITES:
        raise GameError('Không có điểm khám phá này.')
    site = nearby_site(farm)
    if site is None or site.key != key:
        raise GameError('Hãy đến dấu ! tại địa điểm này để thu thập.')
    if farm.gathered_on.get(key) == farm.day:
        raise GameError('Đã thu thập hôm nay. Chừa phần cho rừng, sáng mai quay lại nhé.')
    item = site.gather[season_index(farm)]
    amount = 1 + int(farm.weather == 'rainy' and item in ('herb', 'mushroom'))
    amount += int(farm.restoration.get('workshop', 0) == 3 and item in ('wood', 'da'))
    amount += int(farm.restoration.get('lighthouse', 0) == 3 and item == 'shell')
    cost = 1 if farm.restoration.get('sanctuary', 0) == 3 else 2
    farm._spend_energy(cost)
    farm.items[item] += amount
    farm.gathered_on[key] = farm.day
    discover(farm)
    xp = farm.award_xp(3)
    return f'{site.name}: {ITEMS[item].name} ×{amount}. (-{cost} sức) {xp}'


def travel_to_site(farm: 'Farm', key: str) -> str:
    from .model import GameError
    from .world import walkable
    if not isinstance(key, str) or key not in SITES:
        raise GameError('Không có điểm khám phá này.')
    site = SITES[key]
    if not walkable('village', *site.position, farm.size):
        raise GameError('Lối vào địa điểm đang bị chặn.')
    farm.area = 'village'
    farm.player_x, farm.player_y = site.position
    farm.facing = 'down'
    discover(farm)
    return f'Đã đến {site.name} · {PAGES[key].name}. E để khám phá.'


@dataclass(frozen=True, slots=True)
class Stage:
    name: str
    materials: dict[str, int]
    coins: int
    visits: tuple[str, ...]
    day: int
    story: str


@dataclass(frozen=True, slots=True)
class Project:
    key: str
    name: str
    site: str
    owner: str
    benefit: str
    stages: tuple[Stage, Stage, Stage]


PROJECTS = {
    'greenhouse': Project('greenhouse', 'Nhà ươm chung', 'field', 'an',
        'Mỗi sáng nhận 2 hạt giống phù hợp cấp độ, ngay trong túi.', (
            Stage('Dọn nền', {'wood': 4, 'herb': 2}, 20, ('meadow',), 1,
                  'An đặt lại nhãn giống trên bàn: “Lần này, ai cũng có phần.”'),
            Stage('Vá mái kính', {'wood': 8, 'da': 4, 'crop:ca_rot': 2}, 50, ('east_meadow',), 3,
                  'Hà giữ khung, An lắp kính. Hai người tranh nhau nhường chỗ khô cho cậu.'),
            Stage('Ươm vụ đầu', {'crop:lua_mi': 4, 'honey': 2}, 80, ('south_2_0',), 5,
                  'Sáng mai sẽ có túi hạt đầu tiên. An viết tên nông trại cậu lên chiếc kệ chung.'))),
    'mill': Project('mill', 'Cối xay thung lũng', 'valley', 'minh',
        'Mỗi sáng có 2 phần thức ăn vật nuôi.', (
            Stage('Gỡ bánh xe', {'wood': 6, 'da': 3}, 30, ('valley',), 2,
                  'Minh quay thử trục; tiếng gỗ cọt kẹt khiến em cười suốt cả buổi.'),
            Stage('Lắp guồng nước', {'wood': 10, 'quang_dong': 2}, 70, ('south_2_1',), 5,
                  'Nước lại chảy qua rãnh cũ. Em khoe với Lan rằng lần này không thừa chiếc ốc nào.'),
            Stage('Xay mẻ đầu', {'crop:lua_mi': 6, 'crop:bap': 2}, 100, ('south_1_0',), 8,
                  'Túi cám đầu tiên được chia đều. Minh dành phần nhỏ nhất cho đàn gà nhà em.'))),
    'pier': Project('pier', 'Cầu tàu Hồ Lớn', 'east_lake', 'tu',
        'Câu cá ít tốn sức hơn 1 điểm, tối thiểu 1.', (
            Stage('Đo lại bến', {'wood': 5, 'da': 3}, 25, ('lake',), 2,
                  'Bác Tư chỉ cọc nào phải thay, cọc nào còn chịu được một đời người nữa.'),
            Stage('Lát mặt cầu', {'wood': 12, 'quang_sat': 1}, 80, ('south_1_1',), 6,
                  'Bác Hai mang trà tới. Bác Tư nhận chén rồi lặng lẽ nhường ghế cho cháu.'),
            Stage('Bữa cá khai bến', {'ca_ro': 3, 'cha_ca': 1}, 100, ('east_lake',), 10,
                  'Bác dựng chiếc cần dự phòng cạnh ghế: “Chỗ này từ nay có tên cháu rồi.”'))),
    'workshop': Project('workshop', 'Xưởng sửa đồ của Hà', 'east_wood', 'ha',
        'Mỗi lần thu thập gỗ hoặc đá tại điểm khám phá được thêm 1.', (
            Stage('Chống mái dột', {'wood': 8, 'da': 2}, 40, ('forest',), 2,
                  'Hà nhấc chiếc xô hứng nước cuối cùng ra ngoài, thở ra nhẹ cả người.'),
            Stage('Dựng bàn thợ', {'wood': 12, 'quang_dong': 3}, 90, ('south_1_0',), 6,
                  'Sơn kê lại chân bàn. Hà bảo bàn hơi thấp, nhưng vừa cho hai người cùng làm.'),
            Stage('Bộ dụng cụ chung', {'quang_sat': 3, 'wool': 2}, 130, ('east_wood',), 10,
                  'Hà treo dụng cụ thấp hơn tầm vai: “Cứ lấy dùng, rồi nhớ mang về đây nhé.”'))),
    'orchard': Project('orchard', 'Vườn quả cuối làng', 'south_3_2', 'lan',
        'Mỗi sáng nhận 1 quả rừng; mùa Hạ/Thu nhận 2.', (
            Stage('Tỉa đường vào', {'wood': 8, 'herb': 3}, 40, ('east_meadow',), 4,
                  'Lan gấp hóa đơn lại, xắn tay áo giúp An dọn cỏ. Hôm nay tiệm đóng cửa sớm.'),
            Stage('Dẫn ong về vườn', {'honey': 3, 'tea_leaf': 3}, 90, ('south_0_0', 'south_3_2'), 8,
                  'Một đàn ong dừng ở hàng cây. An ra hiệu mọi người nói khẽ, như sợ làm khách lạ ngại.'),
            Stage('Giỏ quả đầu mùa', {'berry': 6, 'milk': 2}, 140, ('south_3_0',), 14,
                  'Lan chia quả vào tám giỏ, rồi tìm thêm một chiếc: “Suýt quên giỏ của cậu.”'))),
    'archive': Project('archive', 'Tủ chuyện làng', 'square', 'mai',
        'Mỗi sáng nhận 5 XP từ việc chép lại hành trình.', (
            Stage('Làm khô trang cũ', {'wood': 4, 'tea_leaf': 2}, 20, ('residential',), 1,
                  'Mai mở một trang chưa có chữ: “Tớ muốn ghi chuyện đang xảy ra, cả chuyện của cậu.”'),
            Stage('Theo dấu thư xưa', {'wood': 8, 'mushroom': 3}, 60, ('south_0_2', 'south_2_2'), 7,
                  'Dưới lớp giấy ố là tên ông bà của cả làng. Mai đọc chậm, giữ từng nét mực.'),
            Stage('Đêm đọc chuyện', {'banh_mi': 2, 'tea_leaf': 4}, 100, ('south_3_3',), 12,
                  'Không ai rời ghế khi đèn gần tắt. Mai để cậu tự viết dòng cuối của buổi đọc đầu tiên.'))),
    'sanctuary': Project('sanctuary', 'Lối rừng của Sơn', 'south_1_2', 'son',
        'Thu thập ở tất cả điểm khám phá chỉ tốn 1 sức.', (
            Stage('Đặt dấu lối mòn', {'wood': 6, 'da': 4}, 30, ('east_wood',), 3,
                  'Sơn khắc mũi tên thấp thêm một chút: “Cho cả những người chưa kịp lớn.”'),
            Stage('Chừa chỗ cho thú', {'wood': 10, 'herb': 4}, 80, ('south_0_1', 'south_1_2'), 8,
                  'Một con sóc trở lại gốc cây mẹ. Sơn đứng yên rất lâu rồi mới dám cười.'),
            Stage('Nối những đường về', {'mushroom': 5, 'honey': 2}, 140, ('south_3_1',), 15,
                  'Hà buộc sợi vải cuối cùng lên cành thấp. Từ đây ai đi xa cũng có đường về.'))),
    'lighthouse': Project('lighthouse', 'Ngọn đèn bờ đông', 'east_coast', 'hai',
        'Thu thập vỏ sò được thêm 1; bình minh nhận 10 xu tiền hàng ghé bến.', (
            Stage('Rửa lớp muối', {'shell': 5, 'wood': 6}, 50, ('beach', 'east_coast'), 4,
                  'Bác Hai lau chóa đèn bằng khăn cũ: “Mong người ngoài khơi cũng thấy đường về.”'),
            Stage('Đúc khung đèn', {'quang_dong': 4, 'quang_sat': 3}, 120, ('south_0_3', 'south_2_3'), 10,
                  'Hà đưa bác chiếc khung mới. Bác Tư nhìn ra biển, tay vẫn nắm chiếc mũ cũ.'),
            Stage('Thắp sáng chân trời', {'quang_vang': 2, 'honey': 3}, 200, ('south_1_3', 'south_3_3'), 21,
                  'Đốm sáng đầu tiên ngoài biển chớp lại. Bác Hai rót thêm một chén trà, để nguyên trên bàn.'))),
}


def project_requirements(farm: 'Farm', project: Project) -> list[str]:
    phase = farm.restoration.get(project.key, 0)
    if phase >= len(project.stages):
        return ['Đã hoàn thành. ' + project.benefit]
    from .inventory import count_item
    stage = project.stages[phase]
    return [f'Chặng {phase+1}/3: {stage.name} · từ ngày {stage.day}',
            ' · '.join(f'{ITEMS[item].name} {count_item(farm,item)+farm.chest[item]}/{n}'
                       for item, n in stage.materials.items()),
            f'Xu {farm.coins}/{stage.coins} · đã ghé: ' + ', '.join(
                PAGES[key].name + (' [x]' if key in farm.discovered else ' [ ]')
                for key in stage.visits),
            'Sau phục hồi: ' + project.benefit]


def restore(farm: 'Farm', key: str) -> str:
    from .model import GameError
    from .inventory import count_item
    from .cooking import _take
    if not isinstance(key, str) or key not in PROJECTS:
        raise GameError('Không có công trình này.')
    project = PROJECTS[key]
    site = nearby_site(farm)
    if site is None or site.key != project.site:
        raise GameError(f'Hãy đến {SITES[project.site].name} để cùng thi công.')
    phase = farm.restoration.get(key, 0)
    if phase >= 3:
        raise GameError('Công trình đã hoàn thành. Cả làng vẫn đang dùng mỗi ngày!')
    stage = project.stages[phase]
    if farm.day < stage.day:
        raise GameError(f'Mọi người đang chuẩn bị. Chặng này bắt đầu từ ngày {stage.day}.')
    if any(visit not in farm.discovered for visit in stage.visits):
        raise GameError('Hãy ghé các vùng ghi trong sổ trước để tìm hiểu công trình.')
    missing = [f'{ITEMS[item].name} ×{amount-count_item(farm,item)-farm.chest[item]}'
               for item, amount in stage.materials.items()
               if count_item(farm,item)+farm.chest[item] < amount]
    if missing or farm.coins < stage.coins:
        raise GameError('Còn thiếu: ' + ', '.join(missing + (
            [f'{stage.coins-farm.coins} xu'] if farm.coins < stage.coins else [])))
    for item, amount in stage.materials.items():
        _take(farm, item, amount)
    farm.coins -= stage.coins
    farm.restoration[key] = phase+1
    farm.friendships[project.owner] = min(10, farm.friendships[project.owner]+1)
    xp = farm.award_xp(10 + phase*5)
    return f'{project.name} · chặng {phase+1}/3. {stage.story} {xp}' + (
        ' Mở tiện ích: ' + project.benefit if phase == 2 else '')


def morning_benefits(farm: 'Farm') -> str:
    rewards = []
    if farm.restoration.get('greenhouse') == 3:
        unlocked = [key for key, crop in CROPS.items() if crop.level <= farm.level]
        crop = unlocked[(farm.day-1) % len(unlocked)]
        farm.seeds[crop] += 2
        rewards.append(f'Nhà ươm: 2 hạt {CROPS[crop].name}')
    if farm.restoration.get('mill') == 3:
        farm.items['feed'] += 2
        rewards.append('Cối xay: 2 thức ăn')
    if farm.restoration.get('orchard') == 3:
        amount = 2 if season_index(farm) in (1, 2) else 1
        farm.items['berry'] += amount
        rewards.append(f'Vườn quả: {amount} quả rừng')
    if farm.restoration.get('archive') == 3:
        xp = farm.award_xp(5)
        rewards.append('Tủ chuyện làng: ' + xp)
    if farm.restoration.get('lighthouse') == 3:
        farm.coins += 10
        rewards.append('Đèn biển: 10 xu')
    return ' · '.join(rewards)


@dataclass(frozen=True, slots=True)
class Festival:
    name: str
    day: int
    item: str
    amount: int
    story: str


FESTIVALS = {
    'spring': Festival('Hội gieo hạt', 7, 'crop:lua_mi', 2,
        'Lan trải hạt lên khăn, An dẫn bọn trẻ gieo luống đầu. Mai ghi tên cậu vào sổ hội. Bác Hai dúi thêm túi hạt: “Mang về, vụ đầu còn nhiều việc lắm.”'),
    'summer': Festival('Bữa cơm bên hồ', 14, 'ca_ro', 2,
        'Bác Tư nhóm bếp cá, Minh chạy đi lấy ghế còn thiếu. Hà và Sơn vừa chuyền đĩa vừa tranh nhau kể chuyện đường rừng. Lan giữ sẵn một chỗ cạnh cậu.'),
    'autumn': Festival('Đêm đèn mùa gặt', 21, 'mushroom', 3,
        'Đèn lồng sáng dọc đường. Mai đọc những dòng chuyện làng viết trong năm; đến đoạn cậu xuất hiện, An quay lại cười và cả bàn cùng nâng chén.'),
    'winter': Festival('Chén trà cuối năm', 28, 'tea_leaf', 3,
        'Mọi người ngồi sát quanh ấm trà của Bác Hai. Hà mang chiếc chuông đã sửa đến treo ngoài cửa. Tiếng chuông ngân, ai cũng có điều để hẹn sang năm.'),
}


def festival_line(farm: 'Farm') -> str:
    festival = FESTIVALS[SEASONS[season_index(farm)]]
    today = (farm.day-1) % 28+1
    when = 'HÔM NAY' if today == festival.day else (
        f'còn {festival.day-today} ngày' if today < festival.day else 'đã qua mùa này')
    return (f'{festival.name}: ngày {festival.day} {season_name(farm)} · {when}. '
            f'Mang {ITEMS[festival.item].name} ×{festival.amount} tới Sân hội (!), Quảng Trường.')


def attend_festival(farm: 'Farm') -> str:
    from .model import GameError
    from .inventory import count_item
    from .cooking import _take
    season = SEASONS[season_index(farm)]
    festival = FESTIVALS[season]
    site = nearby_site(farm)
    if site is None or site.key != 'square':
        raise GameError('Hãy đến Sân hội bên giếng ở Quảng Trường để dự hội.')
    if (farm.day-1) % 28+1 != festival.day:
        raise GameError(festival_line(farm))
    if farm.festivals_on.get(season, 0) > (farm.day-1)//112*112:
        raise GameError('Đã cùng mọi người dự hội này rồi. Hẹn mùa sau nhé!')
    if count_item(farm, festival.item) + farm.chest[festival.item] < festival.amount:
        raise GameError(f'Bàn ăn chung còn thiếu {ITEMS[festival.item].name} ×{festival.amount}.')
    _take(farm, festival.item, festival.amount)
    farm.festivals_on[season] = farm.day
    for npc in farm.friendships:
        farm.friendships[npc] = min(10, farm.friendships[npc]+1)
    farm.energy = farm.energy_limit
    farm.seeds['ca_rot'] += 4
    farm.seeds['lua_mi'] += 4
    xp = farm.award_xp(20)
    return f'{festival.name}\n{festival.story}\nHồi đầy sức, nhận 8 hạt giống và +1 thân thiết với cả làng. {xp}'


def journal_lines(farm: 'Farm') -> list[str]:
    lines = [calendar_line(farm), festival_line(farm),
             f'HÀNH TRÌNH · {len(farm.discovered)}/{len(SITES)} vùng đã ghé',
             'Tìm dấu ! (Unicode: ◆), đứng lên hoặc nhìn về dấu rồi E. R đi nhanh; U mở sổ.',
             'Mỗi điểm cho một sản vật mỗi ngày; mùa đổi sau 28 ngày, mưa giúp rau/nấm sinh sôi.']
    for key, site in SITES.items():
        status = f'đã ghé ngày {farm.discovered[key]}' if key in farm.discovered else 'chưa ghé'
        item = site.gather[season_index(farm)]
        gathered = ' · đã hái hôm nay' if farm.gathered_on.get(key) == farm.day else ''
        lines.append(f'{PAGES[key].name} · {site.name} ({site.position[0]},{site.position[1]}) · {status}{gathered}')
        lines.append(f'  Mùa này: {ITEMS[item].name}.')
        if key in farm.discovered:
            lines.append('  '+site.story)
    lines += ['', 'KHÔI PHỤC LÀNG · nguyên liệu dùng từ túi trước, rồi rương; xác nhận mới trừ đồ.']
    for project in PROJECTS.values():
        lines.append(f'{project.name} · {PAGES[project.site].name} · {farm.restoration.get(project.key,0)}/3')
        lines.extend(project_requirements(farm, project))
    return lines
