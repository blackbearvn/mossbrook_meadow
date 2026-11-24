"""Hội thoại hai chiều của dân làng, đóng băng khi mở và thưởng một lần mỗi ngày."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .dialogue_content import (CLOSE_HELLO, FIRST_MEET, HELLO, LIGHT_CLOSE,
                               LIGHT_TALK, RAIN_HELLO, SCRIPTS)
from .villagers import NPCS, TOPICS, talk

if TYPE_CHECKING:
    from .model import Farm


@dataclass(frozen=True, slots=True)
class DialogueChoice:
    id: str
    text: str
    next_node: str


@dataclass(frozen=True, slots=True)
class DialogueNode:
    id: str
    npc_line: str
    choices: tuple[DialogueChoice, ...]


@dataclass(slots=True)
class Conversation:
    npc_id: str
    topic: str
    node_id: str
    history: list[str]
    done: bool = False
    credited: bool = False
    xp_reward: str = ''
    _nodes: dict[str, DialogueNode] = field(default_factory=dict, repr=False)


BRANCHING_NPC_IDS = frozenset(SCRIPTS)
LIGHT_NPC_IDS = frozenset(LIGHT_TALK)


def _validate_nearby(farm: 'Farm', npc_id: str, topic: str) -> None:
    from .model import GameError

    if not isinstance(npc_id, str) or npc_id not in NPCS:
        raise GameError('Không có người dân này.')
    if not isinstance(topic, str) or topic not in TOPICS:
        raise GameError('Chủ đề trò chuyện không hợp lệ.')
    npc = NPCS[npc_id]
    if (farm.area != 'village' or abs(farm.player_x - npc.position[0])
            + abs(farm.player_y - npc.position[1]) > 1):
        raise GameError(f'Hãy đứng cạnh {npc.name} để trò chuyện.')


def _hello(farm: 'Farm', npc_id: str) -> str:
    """Một lời chào ngắn, đổi theo ngày, mưa và mức thân thiết."""
    first_meeting = (farm.day == 1 and farm.talked_on.get(npc_id, 0) == 0
                     and farm.friendships.get(npc_id, 0) == 0)
    if first_meeting:
        parts = [FIRST_MEET[npc_id].format(name=farm.player_name, farm=farm.name)]
    else:
        parts = []
    if farm.weather == 'rainy':
        parts.append(RAIN_HELLO[npc_id])
    elif not first_meeting:
        pool = HELLO[npc_id]
        parts.append(pool[(farm.day - 1) % len(pool)])
    if farm.friendships.get(npc_id, 0) >= 6:
        parts.append(CLOSE_HELLO[npc_id])
    return ' '.join(parts)


def _light_line(farm: 'Farm', npc_id: str) -> str:
    """Câu kể đời thường của người thân, không phải câu hỏi phỏng vấn."""
    pool = LIGHT_TALK[npc_id]
    line = pool[(farm.day - 1) % len(pool)]
    if farm.friendships.get(npc_id, 0) >= 6:
        line += ' ' + LIGHT_CLOSE[npc_id][0]
    return line


def begin_dialogue(farm: 'Farm', npc_id: str, topic: str = 'greet') -> Conversation:
    """Mở cuộc trò chuyện mà không làm thay đổi trạng thái đã lưu."""
    from .model import GameError

    _validate_nearby(farm, npc_id, topic)
    if npc_id not in BRANCHING_NPC_IDS:
        raise GameError(f'{NPCS[npc_id].name} chỉ trò chuyện vài câu, không có chủ đề này.')
    question, warm, practical = SCRIPTS[npc_id][topic]
    if topic == 'greet':
        question = f'{_hello(farm, npc_id)} {question}'
    nodes = {}
    first_choices = []
    for branch_id, branch in (('warm', warm), ('practical', practical)):
        reply, followup, attempt, ask = branch
        first_choices.append(DialogueChoice(branch_id, reply, branch_id))
        choices = []
        for choice_id, (text, ending) in (('try', attempt), ('ask', ask)):
            end_id = f'{branch_id}_{choice_id}'
            nodes[end_id] = DialogueNode(end_id, ending, ())
            choices.append(DialogueChoice(choice_id, text, end_id))
        nodes[branch_id] = DialogueNode(branch_id, followup, tuple(choices))
    nodes['opening'] = DialogueNode('opening', question, tuple(first_choices))
    return Conversation(npc_id, topic, 'opening',
                        [f'{NPCS[npc_id].name}: {question}'], _nodes=nodes)


def begin_light_chat(farm: 'Farm', npc_id: str) -> Conversation:
    """Mở một câu chuyện ngắn với người thân; vẫn tính một lần mỗi ngày."""
    from .model import GameError

    _validate_nearby(farm, npc_id, 'greet')
    if npc_id not in LIGHT_NPC_IDS:
        raise GameError(f'{NPCS[npc_id].name} không thuộc nhóm trò chuyện ngắn.')
    xp_reward = ''
    if farm.talked_on[npc_id] != farm.day:
        talk(farm, npc_id, 'greet')
        xp_reward = farm.award_xp(3)
    line = _light_line(farm, npc_id)
    return Conversation(npc_id, 'greet', 'opening',
                        [f'{NPCS[npc_id].name}: {line}'], done=True,
                        xp_reward=xp_reward,
                        _nodes={'opening': DialogueNode('opening', line, ())})


def opening_line(farm: 'Farm', npc_id: str, topic: str = 'greet') -> str:
    """Một câu mở đầu dùng cho API talk() cũ, đồng bộ với khung chat."""
    if npc_id in BRANCHING_NPC_IDS:
        return dialogue_node(begin_dialogue(farm, npc_id, topic)).npc_line
    return _light_line(farm, npc_id)


def dialogue_node(conversation: Conversation) -> DialogueNode:
    from .model import GameError

    if conversation.node_id not in conversation._nodes:
        raise GameError('Lượt trò chuyện không hợp lệ.')
    return conversation._nodes[conversation.node_id]


def choose_response(farm: 'Farm', conversation: Conversation, choice_id: str) -> str:
    """Trả về lời mới, kèm thông báo thân thiết/XP nếu đây là lượt đầu trong ngày."""
    from .model import GameError

    _validate_nearby(farm, conversation.npc_id, conversation.topic)
    if conversation.done:
        raise GameError('Cuộc trò chuyện đã kết thúc.')
    current = dialogue_node(conversation)
    choice = next((item for item in current.choices
                   if isinstance(choice_id, str) and item.id == choice_id), None)
    if choice is None or choice.next_node not in conversation._nodes:
        raise GameError('Câu trả lời không hợp lệ.')
    following = conversation._nodes[choice.next_node]
    new_lines = [f'Bạn: {choice.text}',
                 f'{NPCS[conversation.npc_id].name}: {following.npc_line}']
    reward = []
    if farm.talked_on[conversation.npc_id] != farm.day:
        status = talk(farm, conversation.npc_id, conversation.topic).splitlines()[-1]
        xp_status = farm.award_xp(3)
        reward = [status, xp_status] if xp_status else [status]
        conversation.credited = True
        conversation.xp_reward = xp_status
    conversation.history.extend(new_lines)
    conversation.node_id = following.id
    conversation.done = not following.choices
    return '\n'.join(new_lines + reward)
