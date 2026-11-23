"""The villagers, their dialogue and daily friendship rules."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .daily import ensure_daily, record_daily

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class NPC:
    id: str
    name: str
    role: str
    glyph: str
    position: tuple[int, int]
    description: str
    motto: str = ''
    likes: str = ''
    schedule: str = ''


NPCS = {
    'lan': NPC('lan', 'Lan', 'Chủ tiệm', '1', (28, 5),
               'Lan chăm chút cửa tiệm nhỏ, nhớ cả giống cây mà hàng xóm thích trồng.',
               motto='Một cửa tiệm mở cửa là một lời chào.',
               likes='Hạt giống mới, hoa cúc và chuyện vụ mùa',
               schedule='Cả ngày ở tiệm, chiều muộn đi dạo đồng hoa'),
    'tu': NPC('tu', 'Bác Tư', 'Người câu cá', '2', (30, 10),
              'Bác Tư thuộc từng khúc nước và luôn có một câu chuyện bên bờ hồ.',
              motto='Mặt hồ không vội, người câu cũng chẳng cần vội.',
              likes='Cá vàng, trà nóng và người ngồi nghe chuyện',
              schedule='Sáng sớm và chiều mát ngồi ở bờ hồ cũ'),
    'an': NPC('an', 'An', 'Người làm vườn', '3', (39, 10),
              'An trồng hoa ven đường, thích trao đổi kinh nghiệm chăm cây.',
              motto='Chừa một lối nhỏ để hoa và người cùng đi.',
              likes='Hoa trắng, đất ẩm và nhật ký chăm cây',
              schedule='Chăm đồng hoa từ sáng, nghỉ trưa dưới gốc cây'),
    'mai': NPC('mai', 'Mai', 'Thủ thư', '4', (55, 20),
               'Mai mang sách ra quảng trường và sưu tầm những chuyện xưa của làng.',
               motto='Chuyện nhỏ của hôm nay là lịch sử của ngày mai.',
               likes='Sách cũ, chuyện làng và những buổi chiều yên',
               schedule='Buổi sáng ở quảng trường, chiều về sắp lại sổ'),
    'son': NPC('son', 'Sơn', 'Người giữ rừng', '5', (20, 25),
               'Sơn giữ những lối mòn dưới tán thông luôn sạch sẽ và dễ đi.',
               motto='Lối đi rõ ràng là món quà cho người đến sau.',
               likes='Cành khô đã dọn, tiếng chim và trà rừng',
               schedule='Đi một vòng rừng mỗi sáng, về trước khi trời tối'),
}
TOPICS = {
    'greet': 'Chào hỏi',
    'work': 'Hỏi về công việc',
    'village': 'Chuyện quanh làng',
    'dream': 'Ước mơ',
    'memory': 'Kỷ niệm',
}
BOND_TITLES = ((0, 'Người mới quen'), (3, 'Bạn quen'),
               (6, 'Bạn thân'), (9, 'Tri kỷ'))


def bond_title(friendship: int) -> str:
    title = BOND_TITLES[0][1]
    for threshold, name in BOND_TITLES:
        if friendship >= threshold:
            title = name
    return title

_DREAMS = {
    'lan': (
        'Mình mơ một ngày tiệm có đủ chỗ cho mọi người ngồi uống trà sau khi mua hạt.',
        'Mình muốn học cách làm bánh từ chính nông sản của làng mình.',
        'Có lẽ mình sẽ mở một góc nhỏ bán hạt giống đổi bằng câu chuyện vụ mùa.',
    ),
    'tu': (
        'Bác chỉ mong mỗi sáng còn đủ sức mang cần ra hồ, nghe nước kể chuyện.',
        'Bác muốn vẽ lại bản đồ những chỗ cá hay nổi, để sau này còn ai dùng.',
        'Ước mơ lớn nhất là một lần câu được cá vàng rồi thả nó về, chỉ để nhìn.',
    ),
    'an': (
        'Mình muốn trồng một dải hoa nối đồng hoa với quảng trường, ai đi cũng thấy vui.',
        'Mình mơ có một vườn ươm nhỏ để tặng cây con cho người mới làm vườn.',
        'Mình muốn học đủ nghề để chăm một khu vườn lành cả khi mình đã già.',
    ),
    'mai': (
        'Mình muốn hoàn thành cuốn sổ chuyện làng trước khi mùa mưa tới.',
        'Mình mơ mở một phòng đọc nhỏ nơi trẻ trong làng có thể ngồi cả buổi chiều.',
        'Mình muốn ghi lại cả những cách gọi tên cũ của từng con đường.',
    ),
    'son': (
        'Tôi muốn trồng thêm một dải thông nối rừng với cánh đồng phía nam.',
        'Tôi mơ một ngày lối mòn có đủ bảng chỉ dẫn cho người lạ cũng không lạc.',
        'Tôi muốn dạy cho người mới cách đọc rừng mà không cần phải phá gì.',
    ),
}
_MEMORIES = {
    'lan': (
        'Hồi mới mở tiệm, mình đã xếp nhầm hạt cà rốt vào túi bí ngô cho cả một nhà.',
        'Ngày đầu tiên có khách quay lại cảm ơn, mình đã đứng sau quầy cười một mình rất lâu.',
        'Mình vẫn giữ chiếc hộp gỗ đựng những đồng xu đầu tiên của tiệm.',
    ),
    'tu': (
        'Lần đầu câu cá, bác ngã xuống hồ vì kéo cần quá mạnh. Cả làng còn nhớ.',
        'Bác từng thả một con cá vàng về hồ và ngồi nhìn đến khi mặt trời lặn.',
        'Có một mùa nước lớn, cả làng cùng kéo lưới; bác nhớ tiếng cười hơn cả mẻ cá.',
    ),
    'an': (
        'Luống hoa đầu tiên của mình bị ốc ăn hết. Mình đã ngồi khóc rồi trồng lại.',
        'Mình học được cách chờ hoa nở từ bà ngoại; bà bảo vội vàng thì hoa cũng biết.',
        'Có người từng cảm ơn mình chỉ vì để một chậu hoa nhỏ bên lối đi.',
    ),
    'mai': (
        'Trang sổ đầu tiên mình viết là về tiếng chuông gió ở quảng trường.',
        'Mình từng mượn sách của một người lạ rồi quên trả; sau đó gửi lại kèm một lá thư.',
        'Mình nhớ ngày làng mất điện, mọi người ra quảng trường kể chuyện đến khuya.',
    ),
    'son': (
        'Tôi từng lạc trong rừng một đêm và học được cách nghe tiếng suối để tìm về.',
        'Cây thông già ở lối vào do ông tôi trồng; tôi vẫn dọn cành cho nó mỗi mùa.',
        'Có một con chim sẻ từng về đậu trên vai tôi mỗi sáng suốt cả mùa đông.',
    ),
}

_GREETINGS = {
    'lan': (
        'Chào bạn! Sáng nay mình vừa xếp lại những túi hạt giống. Mong vườn của bạn luôn xanh.',
        'Hôm nay bạn định trồng gì? Mình thích nhất lúc nghe mọi người kể về vụ mùa đầu tiên.',
        'Đi dạo một chút cũng tốt đấy. Cửa tiệm vẫn ở đây khi bạn cần thêm hạt.',
    ),
    'tu': (
        'Lại đây ngồi chơi. Câu cá còn có cái vui là được nhìn mặt hồ thật lâu.',
        'Hôm nay nước lặng. Có mang cần không? Cứ bình tĩnh, cá không thích người nóng vội đâu.',
        'Bác vừa thấy một vệt vàng dưới nước. Cá vàng hay nắng phản chiếu, phải câu mới biết!',
    ),
    'an': (
        'Bạn thấy đồng hoa này thế nào? Mình thích để chừa một lối nhỏ cho mọi người đi ngang.',
        'Sáng nay mùi đất dễ chịu thật. Chăm cây mỗi ngày làm mình có nhiều điều để mong đợi.',
        'Đừng quên nghỉ tay nhé. Mình thường ra đây ngắm hoa giữa những lúc làm vườn.',
    ),
    'mai': (
        'Chào bạn. Mình đang đọc những ghi chép về ngày ngôi làng được lập nên.',
        'Bạn có câu chuyện nào về nông trại không? Mình muốn giữ lại cả những chuyện nhỏ.',
        'Hôm nay quảng trường yên ả. Thật hợp để ngồi đọc thêm vài trang sách.',
    ),
    'son': (
        'Chào người hàng xóm mới! Cứ theo lối mòn mà đi, bạn sẽ ra khỏi rừng dễ thôi.',
        'Bạn có nghe tiếng chim không? Sáng nay cả khu rừng náo nhiệt hẳn lên.',
        'Tôi vừa nhặt bớt cành khô trên đường. Đi dạo thong thả nhé, rừng có nhiều thứ để ngắm.',
    ),
}
_RAIN = {
    'lan': 'Trời mưa rồi! Hôm nay cây tự được tưới, bạn có thể dành thời gian gặp hàng xóm.',
    'tu': 'Mưa làm mặt hồ nhảy múa cả lên. Thử thả cần xem hôm nay có gặp cá vàng không nhé.',
    'an': 'Mưa xuống thật đúng lúc. Mình đang ngắm những giọt nước đọng trên cánh hoa.',
    'mai': 'Ngày mưa khiến mình nhớ những trang sách cũ. Bạn đã xem dự báo trên tivi chưa?',
    'son': 'Mưa làm lối rừng ướt hơn. Cứ theo đường đất, tôi đã dọn cành khô cho dễ đi rồi.',
}
_WORK = {
    'lan': (
        'Cửa tiệm ở ngay phía bắc chỗ mình. Bạn có thể mua giống, thức ăn và bán sản phẩm ở đó.',
        'Hạt giống mới mở khi bạn lên cấp. Lúa mì chín nhanh, còn bí ngô cần kiên nhẫn hơn.',
        'Trước khi bán hàng, cất món muốn giữ vào rương trong nhà. Tiệm chỉ lấy sản phẩm trong túi.',
    ),
    'tu': (
        'Đứng kề hồ rồi quăng cần. Nhấn Space nâng thanh, thả để hạ; giữ con cá trong thanh nhé.',
        'Đừng giữ cần cứng mãi. Nhấp từng nhịp rồi thả, thanh sẽ theo được con cá dễ hơn.',
        'Mỗi lần quăng cần tốn ba sức. Nếu mệt, về ngủ rồi ngày mai mình lại ra hồ.',
    ),
    'an': (
        'Mỗi đêm được tưới, cây lớn thêm một bước. Ba đêm thiếu nước liên tiếp thì cây héo đấy.',
        'Cây đã chín không héo nữa. Bạn có thể thong thả đi chơi rồi quay lại thu hoạch.',
        'Xem tivi trước khi lên kế hoạch nhé. Biết ngày mai mưa thì việc vườn sẽ nhẹ nhàng hơn.',
    ),
    'mai': (
        'Mình ghi lại chuyện của người trong làng. Mỗi ngày ghé hỏi thăm một chút là đã có chuyện mới.',
        'Có những cuốn sách nói về thân thiết: gặp đều đặn có ý nghĩa hơn là hỏi cả trăm lần một ngày.',
        'Nếu lạc đường, mở bản đồ tổng quan. Những con số trên bản đồ là người trong làng đấy.',
    ),
    'son': (
        'Tôi giữ lối đi qua rừng thông. Những đoạn đường sáng màu dẫn tới đồng hoa và các cây cầu.',
        'Đứng cạnh cây là có thể giúp hàng xóm nhặt củi. Công việc nhỏ ấy kiếm được chút tiền mua giống.',
        'Đừng quên đàn vật nuôi khi đi xa. Cho ăn mỗi ngày và vuốt ve để chúng thân với bạn hơn.',
    ),
}
_VILLAGE = {
    'lan': (
        'Qua cầu phía đông là quảng trường. Mai thường mang sách ra đó, bạn thử ghé chào xem.',
        'An chăm đồng hoa phía bên kia lối đông. Hoa ở đó làm đường về làng vui hơn hẳn.',
        'Bác Tư ở cạnh hồ cũ. Bác ấy biết nhiều mẹo câu cá hơn bất kỳ ai ở đây.',
    ),
    'tu': (
        'Phía đông nam còn có Hồ Sen rộng hơn. Qua suối rồi men đường xuống dưới sẽ tới.',
        'Có hôm bác đi qua đồng hoa chỉ để nghe An kể chuyện trồng cây. Mỗi người một niềm vui.',
        'Muốn ngắm làng từ xa thì lên Đồi Gió phía đông bắc. Nhớ mang theo chút thời gian rảnh.',
    ),
    'an': (
        'Qua cầu đi tiếp về đông là quảng trường. Mai kể chuyện rất cuốn hút, bạn nên làm quen.',
        'Rừng thông nằm phía tây nam. Sơn thường ở khoảng trống giữa những lối mòn.',
        'Mình thích đường quanh Hồ Sen. Có lúc bạn đi xa chỉ để tìm thấy một chỗ ngồi yên.',
    ),
    'mai': (
        'Ngôi làng bắt đầu từ những nông trại nhỏ bên hồ. Giờ đến lượt bạn viết thêm một chương.',
        'Dòng suối chia làng thành hai phía. Có cầu ở lối bắc và lối giữa, nhớ chúng là khó lạc lắm.',
        'Sơn biết những con đường trong rừng, còn Bác Tư biết những câu chuyện của mặt hồ.',
    ),
    'son': (
        'Đi về phía đông sẽ ra quảng trường. Tới cây cầu là bạn đã đi đúng đường rồi.',
        'Hồ Sen ở đông nam yên tĩnh lắm. Nếu đi, nhớ quay về thăm đàn vật nuôi trước khi ngủ nhé.',
        'Tôi thích Đồi Gió phía đông bắc. Từ đó nhìn xuống, ngôi làng cứ như một khu vườn lớn.',
    ),
}
_CLOSE = {
    'lan': 'Có bạn ghé, cửa tiệm thấy ấm áp hơn hẳn.',
    'tu': 'Gặp bạn hoài thành quen, hôm nào vắng bác lại ngóng đấy.',
    'an': 'Lần sau có chuyện vui ở vườn, nhớ kể mình nghe nhé.',
    'mai': 'Mình đã dành một trang riêng cho những câu chuyện bạn kể.',
    'son': 'Bạn đã thành người quen của cả khu rừng này rồi.',
}


def empty_friendships() -> dict[str, int]:
    return dict.fromkeys(NPCS, 0)


def empty_talked_on() -> dict[str, int]:
    return dict.fromkeys(NPCS, 0)


def npc_at(x: int, y: int, area: str = 'village') -> NPC | None:
    if area != 'village':
        return None
    return next((npc for npc in NPCS.values() if npc.position == (x, y)), None)


def nearby_npc(farm: 'Farm') -> NPC | None:
    if farm.area != 'village':
        return None
    directions = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
    dx, dy = directions.get(farm.facing, (0, 0))
    ahead = (farm.player_x + dx, farm.player_y + dy)
    nearby = [npc for npc in NPCS.values()
              if abs(npc.position[0] - farm.player_x)
              + abs(npc.position[1] - farm.player_y) <= 1]
    return min(nearby, key=lambda npc: (
        npc.position != ahead,
        abs(npc.position[0] - farm.player_x) + abs(npc.position[1] - farm.player_y),
        npc.id,
    ), default=None)


def talk(farm: 'Farm', npc_id: str, topic: str = 'greet') -> str:
    from .model import GameError

    if not isinstance(npc_id, str) or npc_id not in NPCS:
        raise GameError('Không có người dân này.')
    if not isinstance(topic, str) or topic not in TOPICS:
        raise GameError('Chủ đề trò chuyện không hợp lệ.')
    npc = NPCS[npc_id]
    if (farm.area != 'village'
            or abs(npc.position[0] - farm.player_x)
            + abs(npc.position[1] - farm.player_y) > 1):
        raise GameError(f'Hãy đứng cạnh {npc.name} để trò chuyện.')
    before = farm.friendships[npc_id]
    first_today = farm.talked_on[npc_id] != farm.day
    if topic == 'greet':
        line = (_RAIN[npc_id] if farm.weather == 'rainy' else
                _GREETINGS[npc_id][(farm.day - 1) % len(_GREETINGS[npc_id])])
    else:
        choices = {'work': _WORK, 'village': _VILLAGE,
                   'dream': _DREAMS, 'memory': _MEMORIES}[topic][npc_id]
        line = choices[(farm.day - 1) % len(choices)]
    if before == 0:
        line = f'Chào chủ nông trại {farm.name}! {npc.description} {line}'
    elif before >= 5:
        line += ' ' + _CLOSE[npc_id]
    line = f'{bond_title(before)}: {line}' if before >= 3 else line
    if first_today:
        ensure_daily(farm)
        farm.friendships[npc_id] = min(10, before + 1)
        farm.talked_on[npc_id] = farm.day
        record_daily(farm, 'talk')
    gained = farm.friendships[npc_id] - before
    status = f'Thân thiết: {farm.friendships[npc_id]}/10'
    status += ' (+1 hôm nay).' if gained else ' · Đã hỏi thăm hôm nay.'
    return f'{npc.name}: {line}\n{status}'
