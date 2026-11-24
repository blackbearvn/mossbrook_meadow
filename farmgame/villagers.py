"""Dân làng, lời thoại ngắn và luật thân thiết hằng ngày."""

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
    'hai': NPC('hai', 'Bác Hai', 'Vợ Bác Tư · pha trà', '6', (32, 10),
               'Bác Hai luôn mang theo bình trà nóng, ngồi cạnh Bác Tư bên hồ.',
               motto='Chén trà nóng là cách hỏi han dịu dàng nhất của người già.',
               likes='Trà hoa hồng, sữa và những chén cháo nóng',
               schedule='Sáng nấu trà đưa ra bờ hồ, chiều kể chuyện với Bác Tư'),
    'minh': NPC('minh', 'Minh', 'Em trai Lan', '7', (25, 4),
                'Minh phụ việc tiệm hạt của chị Lan, chuyên chở và xếp hàng.',
                motto='Hàng sạch sẽ thì khách nhìn cái là muốn mua.',
                likes='Bánh mì nướng, trứng và chuyện vui trên đường chở hàng',
                schedule='Sáng chở hàng về tiệm, chiều phụ chị Lan dọn kho'),
    'ha': NPC('ha', 'Hà', 'Vợ Sơn · thợ sửa đồ', '8', (21, 24),
              'Hà là thợ sửa đồ của làng, ghế gãy hay mái dột đều nhờ tay cô.',
              motto='Đồ cũ mà được chăm, còn dùng được cả chục năm.',
              likes='Gỗ, đá và một ly sữa khi tay cô đang bận',
              schedule='Sáng sửa đồ ở xưởng nhỏ ven rừng, chiều cùng Sơn đi vòng rừng'),
}

# Family ties, Stardew-style: gifting one member also warms their relative.
_FAMILIES = {
    'tu': 'hai', 'hai': 'tu',
    'lan': 'minh', 'minh': 'lan',
    'son': 'ha', 'ha': 'son',
    'an': 'mai', 'mai': 'an',
}
_FAMILY_LABELS = {
    ('tu', 'hai'): 'vợ chồng', ('an', 'mai'): 'chị em',
}


def relative_of(npc_id: str) -> str | None:
    """The npc's family member in the village, or None."""
    return _FAMILIES.get(npc_id)


def family_line(npc_id: str) -> str:
    """One short line naming the family tie, for the directory and cards."""
    relative = _FAMILIES.get(npc_id)
    if relative is None:
        return ''
    label = _FAMILY_LABELS.get((npc_id, relative),
                               _FAMILY_LABELS.get((relative, npc_id),
                                                  'người thân của'))
    return f'{label} {NPCS[relative].name}'


TOPICS = {
    'greet': 'Chào hỏi',
    'work': 'Hỏi về công việc',
    'village': 'Chuyện quanh làng',
    'dream': 'Ước mơ',
    'memory': 'Kỷ niệm',
    'festival': 'Lễ hội mùa',
    'secret': 'Điều chưa kể',
    'future': 'Chuyện ngày mai',
}
BOND_TITLES = ((0, 'Người mới quen'), (3, 'Bạn quen'),
               (6, 'Bạn thân'), (9, 'Tri kỷ'))


def bond_title(friendship: int) -> str:
    title = BOND_TITLES[0][1]
    for threshold, name in BOND_TITLES:
        if friendship >= threshold:
            title = name
    return title


def empty_friendships() -> dict[str, int]:
    return dict.fromkeys(NPCS, 0)


def empty_talked_on() -> dict[str, int]:
    return dict.fromkeys(NPCS, 0)


NPC_POSITIONS = {npc.position: npc for npc in NPCS.values()}


def npc_at(x: int, y: int, area: str = 'village') -> NPC | None:
    if area != 'village':
        return None
    return NPC_POSITIONS.get((x, y))


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
    """API cũ: trả về một câu mở đầu và trạng thái, dùng chung nội dung mới."""
    from .model import GameError
    from .dialogue import opening_line

    if not isinstance(npc_id, str) or npc_id not in NPCS:
        raise GameError('Không có người dân này.')
    if not isinstance(topic, str) or topic not in TOPICS:
        raise GameError('Chủ đề trò chuyện không hợp lệ.')
    npc = NPCS[npc_id]
    if (farm.area != 'village'
            or abs(npc.position[0] - farm.player_x)
            + abs(npc.position[1] - farm.player_y) > 1):
        raise GameError(f'Hãy đứng cạnh {npc.name} để trò chuyện.')
    line = opening_line(farm, npc_id, topic)
    before = farm.friendships[npc_id]
    first_today = farm.talked_on[npc_id] != farm.day
    if first_today:
        ensure_daily(farm)
        farm.friendships[npc_id] = min(10, before + 1)
        farm.talked_on[npc_id] = farm.day
        record_daily(farm, 'talk')
    gained = farm.friendships[npc_id] - before
    status = f'Thân thiết: {farm.friendships[npc_id]}/10'
    status += ' (+1 hôm nay).' if gained else ' · Đã hỏi thăm hôm nay.'
    return f'{npc.name}: {line}\n{status}'
