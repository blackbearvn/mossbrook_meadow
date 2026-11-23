"""Character identity and introductory story, independent of terminal UI."""

from typing import TYPE_CHECKING
import unicodedata

if TYPE_CHECKING:
    from .model import Farm


AVATARS = {'@': 'Nhà nông', '&': 'Người khám phá', 'o': 'Người lữ hành'}
OUTFITS = {'green': 'Xanh lá', 'cyan': 'Xanh ngọc',
           'yellow': 'Vàng', 'magenta': 'Tím hồng'}
BACKGROUNDS = {'gardener': 'Người làm vườn', 'angler': 'Người câu cá',
               'traveler': 'Người lữ hành'}
BACKGROUND_HINTS = {
    'gardener': 'Quen mùi đất sau mưa và những buổi tưới cây lúc bình minh.',
    'angler': 'Yêu mặt hồ tĩnh lặng và những buổi ngồi câu cá thong thả.',
    'traveler': 'Đã đi qua nhiều cung đường và đang tìm một nơi để gọi là nhà.',
}


def normalize_name(value: str, limit: int, label: str) -> str:
    """Return a trimmed NFC name, or a readable validation error."""
    if not isinstance(value, str):
        raise ValueError(f'{label} phải là chữ.')
    value = unicodedata.normalize('NFC', value).strip()
    if not value or len(value) > limit or not value.isprintable():
        raise ValueError(f'{label} cần từ 1 đến {limit} ký tự hiển thị được.')
    return value


def create_character(player_name: str, farm_name: str, avatar: str = '@',
                     outfit: str = 'green', background: str = 'gardener') -> 'Farm':
    """Create a fresh farm; appearance and origin never affect game balance."""
    player_name = normalize_name(player_name, 24, 'Tên người chơi')
    farm_name = normalize_name(farm_name, 28, 'Tên nông trại')
    for value, choices, label in ((avatar, AVATARS, 'Biểu tượng'),
                                   (outfit, OUTFITS, 'Màu áo'),
                                   (background, BACKGROUNDS, 'Xuất thân')):
        if not isinstance(value, str) or value not in choices:
            raise ValueError(f'{label} không hợp lệ.')
    from .model import Farm
    from .tutorial import TutorialState
    return Farm(name=farm_name, player_name=player_name, avatar=avatar,
                outfit=outfit, background=background, intro_seen=False,
                tutorial=TutorialState(status='pending'))


def intro_pages(farm: 'Farm') -> list[tuple[str, str]]:
    """Build three story pages without changing the farm or its intro flag."""
    memories = {
        'gardener': 'Đôi tay quen gieo hạt của bạn lại nhớ mùi đất sau cơn mưa.',
        'angler': 'Bạn mang theo ký ức về mặt hồ yên ả và những buổi ngồi câu cá.',
        'traveler': 'Sau bao cung đường, bạn mong tìm một nơi để gọi là nhà.',
    }
    return [
        ('Lá thư trong nắng',
         f'Gửi {farm.player_name},\n\n'
         f'Nông trại {farm.name} đang chờ bạn ở Mây Nhỏ. Hàng rào có thể đã cũ, '
         'nhưng đất vẫn mềm và khu vườn vẫn đón nắng mỗi sớm. '
         'Hãy đến khi bạn sẵn lòng bắt đầu một mùa mới.\n\n'
         'Trong phong thư còn một chiếc chìa khóa nhỏ, ấm lên trong lòng bàn tay.'),
        ('Chuyến xe đến Mây Nhỏ',
         f'{farm.player_name} nhìn những triền đồi trôi qua ô cửa xe. '
         f'{memories[farm.background]}\n\n'
         f'Xuất thân: {BACKGROUNDS[farm.background]}. Chiếc xe dừng bên khu nhà đầu làng, '
         f'và trên tấm bản đồ là cái tên thân thương: {farm.name}. '
         'Xa xa, tiếng nước và tiếng người gọi nhau hòa trong gió.'),
        ('Lan đón bạn',
         f'“Chào {farm.player_name}! Mình là Lan. Chào mừng bạn về {farm.name}!”\n\n'
         'Dùng WASD hoặc các phím mũi tên để đi; E tương tác, C xem nhân vật. '
         'Từ khu nhà, theo đường làng về phía nam tới cánh đồng: ô đầu ở tọa độ (26, 42). '
         'Ở ruộng, E mở việc gieo trồng, tưới và thu hoạch. Về nhà ngủ để sang ngày.\n\n'
         '“Cứ thong thả nhé. Một hạt giống và một lời chào là đủ cho ngày đầu tiên.”'),
    ]
