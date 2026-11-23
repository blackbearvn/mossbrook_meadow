"""Two-way village conversations, frozen when opened and rewarded once daily."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .villagers import NPCS, TOPICS, bond_title, talk

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
    _nodes: dict[str, DialogueNode] = field(default_factory=dict, repr=False)


# Each topic contains a question and two genuinely different directions.
# Each direction contains a reply/question and two player replies with endings.
_SCRIPTS = {
    'lan': {
        'greet': (
            'Mình đang chọn chỗ đặt giỏ hạt trước tiệm. Bạn thích nhìn thấy gì khi ghé vào?',
            ('Một giỏ đầy màu sắc, nhìn là muốn trồng ngay.',
             'Vậy mình sẽ xen túi cà rốt với bí ngô cho vui mắt. Bạn muốn giỏ ấy gợi mùa nào?',
             ('Mùa xuân, có cả một khởi đầu mới.', 'Mình sẽ thêm một nhành hoa nhỏ. Mong mỗi lần ghé tiệm bạn cũng thấy muốn bắt đầu điều gì đó.'),
             ('Mùa gặt, nghĩ tới thành quả sẽ có động lực hơn.', 'Thế mình đặt cạnh giỏ một bó lúa chín. Nhìn thấy đích đến cũng là cách nuôi hy vọng nhỉ.')),
            ('Mình thích bảng ghi rõ giống và thời gian lớn.',
             'Bạn nói đúng, khách mới sẽ dễ chọn hơn. Bạn cần biết thời gian lớn hay giá trước?',
             ('Thời gian lớn, để mình sắp xếp việc vườn.', 'Mình sẽ để số ngày ngay dưới tên giống. Bạn ghé đọc rồi hãy chọn, cứ thong thả nhé.'),
             ('Giá trước, túi tiền của mình còn mỏng.', 'Mình sẽ viết giá thật rõ. Chọn vài túi vừa sức trước, tiệm vẫn luôn chờ bạn.'))),
        'work': (
            'Mình vừa kiểm lại giống trong tiệm. Bạn đang khó chọn giống hay khó giữ lại sản phẩm cần dùng?',
            ('Mình muốn nghe bạn kể về giống cây.',
             'Lúa mì chín nhanh, còn bí ngô cần kiên nhẫn. Bạn thích vụ ngắn hay một luống để mong đợi lâu hơn?',
             ('Mình chọn vụ ngắn cho quen nhịp chăm cây.', 'Lúa mì hợp để tập thói quen ghé ruộng mỗi ngày. Nhớ xem giống nào đã mở theo cấp của bạn nhé.'),
             ('Mình muốn thử kiên nhẫn với bí ngô.', 'Đến khi đủ cấp, bạn thử một luống nhỏ thôi. Cảm giác chờ quả lớn lên đáng yêu lắm.')),
            ('Mình hay bán nhầm thứ muốn để dành.',
             'Mình chỉ thu sản phẩm trong túi, rương ở nhà sẽ giữ hộ bạn. Bạn muốn để dành làm giống chuyện gì?',
             ('Mình muốn cất một phần vụ mùa đầu tiên.', 'Vậy nhớ ghé rương trước khi bán nhé. Có thứ để ngắm lại còn quý hơn vài đồng xu.'),
             ('Mình muốn giữ cá đẹp để sưu tầm.', 'Cá trong rương cũng sẽ được giữ lại. Hôm nào bắt được con lạ, kể mình nghe nó có màu gì nhé.'))),
        'village': (
            'Mình định nghỉ tiệm sớm để đi dạo. Theo bạn nên ghé đồng hoa hay quảng trường?',
            ('Đồng hoa, An chắc đang chăm cây.',
             'An luôn chừa một lối giữa hoa cho khách đi qua. Bạn thích ngắm hoa hay hỏi chuyện người trồng?',
             ('Mình thích ngắm những màu An chọn.', 'Bạn cứ đi theo lối trống nhé. Mình sẽ rủ An kể xem vì sao lại đặt hai màu cạnh nhau.'),
             ('Mình muốn hỏi An cách chăm cây.', 'An thích trao đổi kinh nghiệm lắm. Kể cả luống từng héo cũng là một câu chuyện có ích.')),
            ('Quảng trường, đi nghe Mai kể chuyện.',
             'Mai đang gom chuyện làng vào những trang sách. Nếu được góp một chuyện, bạn sẽ kể gì?',
             ('Chuyện vụ mùa đầu tiên của mình.', 'Chuyện ấy đáng ghi lại đấy. Những bàn tay mới cũng đang làm nên lịch sử của làng mà.'),
             ('Chuyện một người hàng xóm đã giúp mình.', 'Mai sẽ thích lắm. Mình cũng muốn đọc những điều tử tế thường bị mọi người quên kể.'))),
        'dream': (
            'Mình hay nghĩ về một cửa tiệm có góc trà nhỏ. Bạn muốn tiệm mở thêm điều gì cho làng?',
            ('Một góc trà để mọi người ngồi lại sau khi mua hạt.',
             'Mình đã phác sẵn một chiếc bàn cạnh cửa sổ. Bạn thích tiệm đông vui hay yên tĩnh hơn?',
             ('Đông vui một chút, nghe được nhiều chuyện.', 'Vậy mình sẽ kê thêm ghế dài. Có người kể chuyện, cửa tiệm mới thành nơi chốn chứ không chỉ là quầy hàng.'),
             ('Yên tĩnh, để ai mệt cũng có chỗ ngồi.', 'Mình sẽ giữ một góc thật nhẹ. Đôi khi cửa tiệm chỉ cần mở cửa và im lặng cùng khách.')),
            ('Một bảng ghi giống cây ai cũng đọc được.',
             'Mình muốn ghi cả thời gian chín lẫn giá bán. Bạn nghĩ nên đặt bảng ở đâu để dễ thấy?',
             ('Ngay cạnh giỏ hạt, nhìn là hiểu.', 'Hợp lý đấy. Mình sẽ viết chữ to hơn cho người mới, còn người quen thì cứ ghé hỏi mình.'),
             ('Để ở ngoài hiên, khách thấy trước khi vào.', 'Mình sẽ treo một tấm nhỏ ngoài hiên. Biết trước mình cần gì thì vào tiệm sẽ thong thả hơn.'))),
        'memory': (
            'Mình vừa tìm thấy hộp đựng đồng xu đầu tiên của tiệm. Bạn muốn nghe chuyện mở tiệm không?',
            ('Có chứ, chuyện ngày đầu tiên thế nào?',
             'Hôm ấy mình xếp nhầm hạt cho một nhà, phải chạy theo xin lỗi. Bạn muốn nghe phần xấu hổ hay phần vui?',
             ('Phần xấu hổ, để mình biết mình không phải người duy nhất.', 'Hóa ra người ấy cũng không phân biệt được hạt. Hai bên cười rồi cùng gieo thử, cuối mùa có một luống đẹp lạ.'),
             ('Phần vui, mình muốn nghe chuyện ấm áp.', 'Hôm sau họ quay lại cảm ơn vì đã chỉ đúng. Mình nhận ra một lời xin lỗi chân thành cũng có thể mở đầu cho tình bạn.')),
            ('Hộp ấy có gì đặc biệt?',
             'Chỉ là chiếc hộp gỗ cũ với vài đồng xu, nhưng nó nhắc mình vì sao lại mở tiệm. Bạn có giữ kỷ vật nào không?',
             ('Mình giữ hạt giống của vụ đầu tiên.', 'Vậy hãy cất một hạt thật riêng. Sau này nhìn lại, bạn sẽ thấy mình đã đi xa đến mức nào.'),
             ('Mình chưa có, chắc phải bắt đầu giữ.', 'Bắt đầu từ một đồng xu, một cánh hoa hay một trang giấy đều được. Kỷ vật chỉ có giá trị vì mình trao cho nó một câu chuyện.'))),
    },
    'tu': {
        'greet': (
            'Bác chừa một chỗ bên hồ này. Cháu muốn ngồi nghe nước hay kể bác chuyện nông trại?',
            ('Cháu ngồi nghe nước cùng bác một lát.',
             'Ừ, cứ để vai thả lỏng. Cháu nghe tiếng cá quẫy hay tiếng gió qua lau rõ hơn?',
             ('Tiếng cá quẫy, cháu cứ muốn nhìn theo.', 'Hồi trẻ bác cũng thế, động một cái là ngó. Có khi niềm vui chỉ là biết dưới kia vẫn rộn ràng.'),
             ('Tiếng gió qua lau làm cháu dễ chịu.', 'Vậy hôm nào mệt lại ngồi đây. Bác chẳng cần cháu nói gì, có bạn ngồi cạnh là vui rồi.')),
            ('Cháu muốn kể bác nghe chuyện nông trại.',
             'Bác nghe đây. Hôm nay cháu tự hào về việc làm xong hay đang lo một việc chưa thành?',
             ('Cháu mừng vì đã chăm xong cây.', 'Thế thì cho đôi tay nghỉ một lát. Chăm được những việc nhỏ đều đặn là giỏi rồi cháu.'),
             ('Cháu còn lo mình chưa biết làm cho tốt.', 'Bác từng làm tuột bao nhiêu con cá mới học được. Cứ thử chậm rãi, ngày mai mình còn làm lại.'))),
        'work': (
            'Cháu muốn bác chỉ cách giữ thanh câu hay cách giữ sức khi đi câu?',
            ('Thanh câu cứ trượt khỏi con cá, bác ạ.',
             'Giữ Space thì thanh nâng lên, thả thì hạ xuống. Cháu thường giữ mãi hay nhấp từng nhịp?',
             ('Cháu hay giữ mãi, chắc phải thử nhấp nhẹ.', 'Đúng rồi, thử những nhịp ngắn rồi nhìn cá đổi hướng. Đừng kéo cần như đang kéo cả mặt hồ lên.'),
             ('Cháu nhấp rồi nhưng vẫn cuống khi cá đổi hướng.', 'Cứ nhìn chỗ cá đang đi tới và sửa từng chút. Mất một con cũng chẳng sao, mặt hồ còn rộng.')),
            ('Cháu đi câu một lúc là hết sức.',
             'Tập tay nghề câu cá sẽ giúp cháu đỡ tốn sức. Cháu muốn luyện dần hay chia buổi câu ngắn lại?',
             ('Cháu sẽ dành điểm cho tay nghề câu cá.', 'Luyện thêm thì tay cũng vững, thanh câu rộng hơn. Bác thích người chịu học từng chút như cháu.'),
             ('Cháu sẽ dừng sớm để còn chăm đàn vật nuôi.', 'Biết lúc thu cần cũng là một cái khéo. Để ngày mai còn vui mà ra hồ, cháu nhé.'))),
        'village': (
            'Nếu rời hồ hôm nay, cháu muốn tìm một bờ nước mới hay một nơi nhìn làng từ xa?',
            ('Cháu muốn tìm Hồ Sen.',
             'Hồ Sen ở phía đông nam, qua suối rồi men đường xuống. Cháu đến đó để câu hay để ngồi ngắm?',
             ('Cháu muốn thử câu ở bờ khác.', 'Nhớ chọn chỗ đứng kề nước. Gặp con gì đẹp thì kể bác nghe, bác vẫn tò mò như ngày mới cầm cần.'),
             ('Cháu muốn ngắm sen và nghỉ chân.', 'Đi chậm thôi, đôi khi bóng mây trên nước cũng đáng để ngắm hết một buổi.')),
            ('Cháu muốn lên Đồi Gió.',
             'Đồi ở phía đông bắc. Cháu thích nhìn những mái nhà hay nhìn đường mình đã đi?',
             ('Nhìn mái nhà, để nhớ làng mình ấm áp thế nào.', 'Bác cũng thích thấy khói bếp từ xa. Đi đâu rồi cũng vui khi biết có chỗ để trở về.'),
             ('Nhìn những con đường, cháu muốn khám phá tiếp.', 'Cứ nhớ vài mốc như cầu và hồ trước nhé. Có đường để tìm về thì chuyến đi mới thong thả.'))),
        'dream': (
            'Bác có một cuốn sổ vẽ những chỗ cá hay nổi. Cháu nghĩ bác nên làm gì với nó?',
            ('Chép lại thành bản đồ cho người mới.',
             'Bác sợ vẽ sai thì người ta mất công. Cháu nghĩ nên ghi chỗ chắc chắn hay ghi cả phỏng đoán?',
             ('Ghi cả phỏng đoán, kèm lời bác dặn.', 'Vậy bác sẽ viết như đang kể cho cháu nghe. Người đọc cần một người dẫn đường hơn là một tấm bản đồ hoàn hảo.'),
             ('Chỉ ghi chỗ chắc chắn, để đỡ nhầm.', 'Bác cũng thích vậy. Điều mình biết chắc mà chia sẻ thật lòng thì đã quý hơn nhiều lời đồn rồi.')),
            ('Một ngày bác muốn câu được cá vàng.',
             'Cá vàng hiếm lắm, bác chỉ mong gặp một lần. Nếu bắt được, cháu nghĩ bác nên giữ hay thả?',
             ('Giữ lại để ngắm một hôm.', 'Bác sẽ ngắm thật lâu rồi thả về. Có những niềm vui chỉ cần gặp một lần là đủ nhớ cả đời.'),
             ('Thả về ngay, để nó còn sống tự do.', 'Cháu nói trúng ý bác. Câu được đã là duyên, thả về là giữ duyên ấy lâu hơn.'))),
        'memory': (
            'Bác nhớ có mùa nước lớn, cả làng cùng ra hồ. Cháu có muốn nghe không?',
            ('Cháu muốn nghe chuyện cả làng kéo lưới.',
             'Hôm ấy ai cũng ướt, chẳng ai về nhà trước. Cháu thích nhất là tiếng cười hay cảnh mọi người cùng làm?',
             ('Tiếng cười, nghe là thấy ấm.', 'Mẻ cá ấy bác nhớ mang máng, nhưng tiếng cười thì vẫn còn rõ. Làng mình sống bằng những ngày như thế.'),
             ('Cảnh cùng làm, để thấy làng mạnh đến đâu.', 'Một người kéo không nổi lưới, nhưng cả làng thì được. Cháu nhớ điều ấy khi làm việc một mình nhé.')),
            ('Bác có lần ngã xuống hồ thật à?',
             'Thật chứ, vì kéo cần quá mạnh. Cháu đoán lúc ấy bác nghĩ gì khi ở dưới nước?',
             ('Chắc bác chỉ nghĩ đến con cá.', 'Đúng là bác nghĩ đến con cá trước, rồi mới thấy lạnh. Sau đó bác học được rằng đôi khi phải buông ra mới giữ được.'),
             ('Chắc bác sợ mất cần câu.', 'Bác sợ mất cần thật. Nhưng cần ấy được vớt lên, còn bác thì có thêm một chuyện để kể mỗi mùa mưa.'))),
    },
    'an': {
        'greet': (
            'Mình đang nghỉ tay bên luống hoa. Bạn muốn ngắm hoa cùng mình hay kể chuyện luống cây của bạn?',
            ('Mình muốn ngắm hoa cùng bạn.',
             'Mình vừa ghép hoa vàng cạnh hoa tím. Bạn thấy chúng rực rỡ hay hơi chói mắt?',
             ('Rực rỡ, nhìn rất vui!', 'Vậy mình giữ mảng màu ấy nhé. Có người cùng thích một góc vườn làm mình vui cả buổi.'),
             ('Mình thích xen thêm một chút màu trắng.', 'Ý hay đấy, màu trắng sẽ cho mắt chỗ nghỉ. Lần tới mình thử để lại vài khoảng nhẹ hơn.')),
            ('Mình có chuyện luống cây muốn kể.',
             'Mình thích nghe lắm. Luống ấy vừa có mầm mới hay đang làm bạn lo?',
             ('Có mầm mới rồi, mình cứ ra ngắm mãi.', 'Mầm bé mà niềm vui to nhỉ! Nhớ giữ thói quen tưới, rồi bạn sẽ thấy mỗi ngày đều khác.'),
             ('Cây lớn chậm, mình sợ đã làm sai.', 'Bạn thử kiểm tra nước trước nhé. Cây cũng có nhịp riêng, đừng vì sốt ruột mà trách mình quá.'))),
        'work': (
            'Bạn đang cần sắp xếp lịch tưới hay đang băn khoăn lúc nào nên thu hoạch?',
            ('Mình hay quên tưới lúc đi xa.',
             'Cây cần một đêm được tưới để lớn, thiếu nước ba ngày liền sẽ héo. Bạn muốn dựa vào thời tiết hay tạo một thói quen?',
             ('Mình sẽ xem dự báo trước khi lên đường.', 'Tivi ở nhà giúp bạn biết ngày mai có mưa. Ngày mưa cây được tưới, bạn tha hồ sắp xếp chuyến đi.'),
             ('Mình sẽ ghé ruộng trước những việc khác.', 'Một vòng chăm cây đầu ngày dễ nhớ lắm. Xong rồi đi đâu cũng nhẹ đầu hơn.')),
            ('Cây chín rồi mà mình chưa muốn hái.',
             'Cây chín không héo nữa đâu. Bạn định giữ để ngắm hay gom một vụ lớn mang bán?',
             ('Mình muốn ngắm khu ruộng chín thêm chút nữa.', 'Vậy cứ để đó nhé. Công sức của bạn cũng xứng đáng được thưởng thức bằng mắt, không chỉ bằng tiền.'),
             ('Mình muốn gom đủ rồi mang bán một chuyến.', 'Tiện đấy, nhưng nhớ cất phần muốn giữ vào rương trước. Một chuyến gọn gàng sẽ đỡ bận hơn.'))),
        'village': (
            'Mình muốn trồng hoa ở một góc mọi người hay đi qua. Bạn nghĩ lối rừng hay đường ra hồ hợp hơn?',
            ('Lối rừng, dưới tán thông sẽ đẹp lắm.',
             'Mình sẽ hỏi Sơn trước để không chắn đường. Bạn thích một cụm nhỏ hay những chấm hoa dọc lối?',
             ('Một cụm nhỏ ở chỗ có nắng.', 'Mình cũng muốn để hoa có đủ ánh sáng. Cứ chọn đúng chỗ trước rồi mới tính trồng nhiều.'),
             ('Những chấm hoa để người đi biết đang gần làng.', 'Nghe như một lời chào dọc đường nhỉ. Mình sẽ bàn với Sơn để lối đi vẫn thoáng.')),
            ('Đường ra hồ, người ngồi nghỉ sẽ thích.',
             'Bác Tư hay ngồi lâu bên nước. Bạn muốn hoa có hương nhẹ hay màu dễ nhìn từ xa?',
             ('Hương nhẹ, đừng át cả mùi cỏ và nước.', 'Mình thích cách bạn nghĩ đến cả khoảng không quanh hoa. Một góc dịu dàng chắc sẽ hợp với bờ hồ.'),
             ('Màu sáng để ai đi ngang cũng thấy.', 'Mình sẽ thử chọn màu vàng như nắng. Biết đâu Bác Tư nhìn thấy lại có thêm chuyện để kể.'))),
        'dream': (
            'Mình mơ có một vườn ươm nhỏ để tặng cây con. Bạn nghĩ nên bắt đầu từ loại cây nào?',
            ('Cây dễ sống, để người mới không nản.',
             'Đúng là nên chọn cây chịu được sơ suất. Bạn muốn tặng kèm một tờ hướng dẫn hay chỉ dặn miệng?',
             ('Kèm tờ hướng dẫn nhỏ, cầm về là làm được.', 'Mình sẽ vẽ cả hình từng bước. Người mới đọc xong mà tự tin thì cây mới có cơ hội lớn.'),
             ('Dặn miệng thôi, để còn trò chuyện.', 'Vậy mỗi lần tặng cây là một lần quen thêm một người. Mình thích cách ấy hơn cả một vườn ươm đông cây.')),
            ('Một dải hoa nối đồng hoa với quảng trường.',
             'Nghe như một con đường có màu. Bạn muốn hoa nở quanh năm hay đổi màu theo mùa?',
             ('Đổi màu theo mùa, mỗi lần đi lại thấy mới.', 'Mình sẽ ghi lại từng mùa như một chương sách. Đi trên con đường ấy, ngày tháng sẽ có mùi hương riêng.'),
             ('Quanh năm một màu, để ai cũng nhận ra lối về.', 'Một màu ổn định cũng đẹp, như một dấu chỉ thân quen. Mình sẽ chọn loại hoa bền và ít cần chăm.'))),
        'memory': (
            'Luống hoa đầu tiên của mình từng bị ốc ăn hết. Bạn có muốn nghe mình đã làm gì tiếp không?',
            ('Bạn trồng lại ngay chứ?',
             'Mình ngồi khóc một lúc rồi trồng lại. Bạn nghĩ điều gì quan trọng hơn: rút kinh nghiệm hay giữ được niềm vui làm vườn?',
             ('Giữ niềm vui làm vườn, không vội trách mình.', 'Mình cũng nghĩ vậy. Kinh nghiệm sẽ đến, còn niềm vui mà mất thì vườn cũng thành việc nặng.'),
             ('Rút kinh nghiệm trước, rồi mới trồng lại.', 'Mình đã học cách kiểm tra lá và đất trước khi gieo. Một lần hỏng dạy mình nhiều hơn nhiều lần thành công im lặng.')),
            ('Mình có một chậu hoa nhỏ bên lối đi.',
             'Chậu hoa ấy có người đặc biệt tặng à? Mình tò mò vì sao bạn lại đặt nó ngay chỗ dễ thấy.',
             ('Để mỗi lần đi qua mình nhớ có người quan tâm.', 'Một chậu hoa nhỏ mà giữ được một niềm tin thì đáng trồng lắm. Bạn nhớ tưới cả những ngày bận nhé.'),
             ('Để người khác đi qua cũng thấy vui.', 'Vậy là bạn trồng cho cả lối đi, không chỉ cho mình. Mình sẽ học cách làm vườn như thế.'))),
    },
    'mai': {
        'greet': (
            'Mình vừa mở cuốn sổ chuyện làng. Bạn muốn đọc một chuyện cũ hay góp một điều mới?',
            ('Mình muốn đọc chuyện cũ.',
             'Có trang kể những nông trại đầu tiên bên hồ. Bạn tò mò về người dựng nhà hay người gieo vụ đầu?',
             ('Mình tò mò người đã dựng căn nhà đầu tiên.', 'Họ chọn chỗ nhìn thấy nước để dễ tìm đường về. Mình thích nghĩ một mái nhà cũng bắt đầu từ nỗi mong được trở về.'),
             ('Mình muốn biết vụ mùa đầu tiên ra sao.', 'Trong sổ chỉ có dòng: cả làng cùng chờ một luống xanh. Đôi khi một câu ngắn lại giữ được rất nhiều hy vọng.')),
            ('Mình muốn góp một chuyện mới.',
             'Mình sẵn sàng nghe rồi. Bạn muốn ghi một thành công hay một điều đã học từ lần làm hỏng?',
             ('Một thành công nhỏ thôi, nhưng mình vui lắm.', 'Những niềm vui nhỏ đáng có một trang riêng. Mình sẽ nhớ cảm giác bạn kể, chứ không chỉ nhớ kết quả.'),
             ('Mình muốn kể cả lần mình làm hỏng.', 'Cảm ơn bạn đã tin mình. Chuyện học lại từ đầu sẽ giúp người đến sau thấy họ không cô độc.'))),
        'work': (
            'Mình đang sắp lại sổ ghi chép. Bạn muốn biết cách mình chọn chuyện hay cách tìm đường để tự đi hỏi?',
            ('Bạn chọn những chuyện nào để ghi?',
             'Mình tìm cả tiếng nói thường bị bỏ quên. Theo bạn nên bắt đầu từ chuyện công việc hay một kỷ niệm?',
             ('Chuyện công việc hằng ngày của mọi người.', 'Vậy mình sẽ hỏi những việc nhỏ họ làm đều đặn. Một làng sống được là nhờ biết bao điều tưởng như bình thường ấy.'),
             ('Một kỷ niệm khiến họ muốn kể lại.', 'Mình sẽ để họ chọn chỗ bắt đầu. Khi người kể thấy thoải mái, câu chuyện thường có nhịp riêng rất đẹp.')),
            ('Mình muốn đi gặp mọi người nhưng hay lạc.',
             'Bản đồ tổng quan có số đánh dấu từng người. Bạn dễ nhớ theo cây cầu hay theo những nơi có nước?',
             ('Mình dễ nhớ những cây cầu.', 'Có lối cầu ở phía bắc và giữa làng. Chọn một cây cầu quen rồi lần đường từ đó sẽ dễ hình dung hơn.'),
             ('Mình nhớ hồ và suối tốt hơn.', 'Bạn lấy dòng suối làm trục nhé. Sau mỗi chuyến đi, nhớ thêm một đoạn đường nhỏ là đủ.'))),
        'village': (
            'Mình muốn đặt tên một chương mới về làng. Bạn chọn Những lối đi hay Những người chờ nhau?',
            ('Những lối đi, mỗi con đường đều có chuyện.',
             'Vậy chương ấy nên mở bằng lối rừng của Sơn hay bờ hồ của Bác Tư?',
             ('Lối rừng, nơi Sơn âm thầm dọn cành khô.', 'Mình sẽ bắt đầu bằng dấu chân đi được dễ dàng nhờ một người khác đã chăm sóc con đường.'),
             ('Bờ hồ, nơi Bác Tư ngồi qua nhiều mùa.', 'Một người ngồi yên cũng thấy làng thay đổi. Góc nhìn ấy sẽ khiến trang mở đầu thật khác.')),
            ('Những người chờ nhau nghe ấm áp hơn.',
             'Mình cũng nghĩ vậy. Bạn hình dung Lan chờ khách hay An chờ cây nở?',
             ('Lan chờ hàng xóm ghé tiệm kể chuyện.', 'Mình sẽ viết về chiếc cửa luôn mở và những câu hỏi thăm. Một cuộc gặp ngắn cũng nối được hai ngày xa cách.'),
             ('An chờ hoa nở để ai cũng được ngắm.', 'Vậy chương ấy sẽ có một khoảng lặng trước mùa hoa. Chờ đợi cũng có thể là một cách chăm sóc cả làng.'))),
        'dream': (
            'Mình muốn mở một phòng đọc nhỏ cho trẻ trong làng. Bạn nghĩ nên đặt nó ở đâu?',
            ('Cạnh quảng trường, để ai cũng ghé được.',
             'Đông người qua lại thì vui, nhưng có thể ồn. Bạn chọn thêm một góc yên hay để phòng thật rộng?',
             ('Thêm một góc yên phía sau.', 'Mình sẽ kê ghế thấp và để cửa sổ nhìn ra cây. Một đứa trẻ cần chỗ trốn ồn mới đọc được trọn một trang.'),
             ('Phòng thật rộng để nhiều người cùng đọc.', 'Rộng thì mình sẽ chia thành nhiều góc nhỏ. Không gian chung vẫn có thể dịu dàng nếu mỗi người có một chỗ của mình.')),
            ('Gần trường học, để giờ ra chơi ghé qua.',
             'Như vậy sẽ tiện lắm. Bạn nghĩ phòng đọc nên mở cả buổi tối hay chỉ ban ngày?',
             ('Mở cả buổi tối cho người lớn rảnh.', 'Mình sẽ thắp đèn ấm và để một ấm trà nhỏ. Đọc sách buổi tối cần ánh sáng và cảm giác an toàn hơn là nhiều sách.'),
             ('Chỉ ban ngày, để giữ nhịp sinh hoạt.', 'Ban ngày cũng đủ cho trẻ và người già. Mình sẽ dành buổi tối để sắp lại sách và ghi chép những gì nghe được.'))),
        'memory': (
            'Trang đầu tiên trong sổ làng của mình viết về tiếng chuông gió ở quảng trường. Bạn thấy sao?',
            ('Nghe rất bình dị mà đáng nhớ.',
             'Mình chọn nó vì ai cũng nghe nhưng ít ai nhắc. Bạn nghĩ chuyện nhỏ nào của làng cũng đáng ghi lại?',
             ('Chuyện người ta chào nhau mỗi sáng.', 'Mình sẽ đứng ở quảng trường sớm hơn để nghe. Những câu chào tưởng như vô nghĩa lại là thứ giữ làng mình gần nhau.'),
             ('Chuyện cây cối đổi màu theo mùa.', 'Mình có thể ghi từng mùa bằng một trang. Cây không nói, nhưng nhìn lâu sẽ thấy chúng cũng có chuyện để kể.')),
            ('Mình từng mượn sách rồi quên trả.',
             'Rồi bạn làm gì? Mình tò mò vì một cuốn sách quên trả có thể thành một câu chuyện khác.',
             ('Mình gửi lại kèm một lá thư xin lỗi.', 'Người ấy hẳn sẽ nhớ lá thư hơn cuốn sách. Mình muốn ghi lại những chuyện như thế: lỗi nhỏ được sửa bằng sự tử tế.'),
             ('Mình giữ luôn vì người ấy không nhớ.', 'Vậy bạn đã làm gì tiếp? Mình nghĩ món đồ mượn luôn nhắc mình về một món nợ, kể cả khi người kia quên.'))),
    },
    'son': {
        'greet': (
            'Tôi vừa đi một vòng dưới tán thông. Bạn muốn nghe chuyện dấu chim hay chuyện lối mòn?',
            ('Tôi muốn nghe về chim trong rừng.',
             'Sáng nay chúng gọi nhau ở tán cao. Bạn thích đứng nghe hay muốn tìm chỗ quan sát?',
             ('Đứng nghe thôi, để chúng khỏi giật mình.', 'Cứ đứng yên một lát rồi bạn sẽ phân biệt được tiếng gần, tiếng xa. Rừng thường kể nhiều hơn khi mình nói ít đi.'),
             ('Tôi muốn tìm một chỗ quan sát từ xa.', 'Bạn chọn khoảng trống và giữ khoảng cách nhé. Nhìn thấy chúng tự nhiên còn vui hơn cố tiến thật gần.')),
            ('Tôi muốn biết hôm nay lối mòn thế nào.',
             'Tôi vừa dọn cành gãy ở một khúc ngoặt. Bạn định đi dạo ngắn hay đi xa hơn?',
             ('Một vòng ngắn thôi, tôi muốn nghỉ đầu óc.', 'Vậy cứ theo đường sáng màu rồi quay về trước khi mệt. Không cần đi thật xa mới có một buổi dễ chịu.'),
             ('Tôi muốn đi xa và nhớ thêm đường mới.', 'Bạn ghi nhớ cầu và khoảng trống dưới tán cây. Mỗi lần thêm một mốc, khu rừng sẽ bớt lạ.'))),
        'work': (
            'Bạn muốn giúp nhặt củi hay muốn biết tôi chăm những lối rừng ra sao?',
            ('Tôi muốn thử nhặt củi giúp hàng xóm.',
             'Đứng cạnh cây là có thể làm thuê. Bạn muốn dành sức làm ít hay luyện tay nghề kiếm sống lâu dài?',
             ('Làm ít thôi, tôi còn phải về ruộng.', 'Biết chia sức là tốt. Xong việc nhỏ rồi quay về chăm cây, đừng để một buổi bận làm ngày mai mệt thêm.'),
             ('Tôi muốn luyện tay nghề kiếm sống.', 'Tay nghề ấy giúp tiền công và số gỗ khá hơn, còn đỡ tốn sức. Cứ nâng dần theo những việc bạn thật sự thích làm.')),
            ('Tôi tò mò cách anh giữ lối đi thông thoáng.',
             'Tôi xem cành rơi, chỗ rẽ và khoảng đường mọi người hay dùng. Bạn thấy chỗ dễ lạc hay chỗ khó đi cần chú ý trước?',
             ('Chỗ dễ lạc, ai mới đến cũng cần tìm đường.', 'Tôi sẽ kiểm tra những đoạn rẽ kỹ hơn. Một lối mòn rõ ràng là lời chào dành cho người chưa quen rừng.'),
             ('Chỗ khó đi, nhất là sau một cơn mưa.', 'Đúng, một cành chắn ngang có thể làm cả chuyến đi vất vả. Tôi sẽ nhớ nhìn kỹ nền đường sau mưa.'))),
        'village': (
            'Nếu có một buổi rảnh, bạn chọn lên Đồi Gió hay đi xuống Hồ Sen?',
            ('Tôi muốn lên Đồi Gió.',
             'Phía đông bắc ấy nhìn làng đẹp lắm. Bạn muốn đi lúc lòng đang rối hay lúc có tin vui?',
             ('Lúc lòng đang rối, để nhìn mọi thứ rộng hơn.', 'Tôi cũng từng lên đó vì thế. Nhìn những mái nhà nhỏ lại đôi khi giúp mình biết việc gì đáng giữ trong lòng.'),
             ('Lúc có tin vui, tôi muốn mang niềm vui đi xa.', 'Nghe hay đấy. Cứ để gió nghe cùng bạn, rồi khi về nhớ kể với một người đang chờ ở làng.')),
            ('Tôi muốn xuống Hồ Sen.',
             'Hồ ở đông nam, nhớ tính cả đường về nhé. Bạn muốn ngồi một mình hay rủ người đi cùng?',
             ('Tôi muốn ngồi yên một mình một lát.', 'Vậy tìm một góc thoáng bên bờ. Trước khi đi nhớ lo xong cho đàn vật nuôi để lúc nghỉ không phải bận lòng.'),
             ('Tôi muốn rủ một người hàng xóm.', 'Bạn thử hỏi Bác Tư, bác ấy quý những cuộc đi chậm. Có người cùng nhìn một mặt nước thì câu chuyện cũng khác.'))),
        'dream': (
            'Tôi muốn trồng một dải thông nối rừng với cánh đồng. Bạn nghĩ nên bắt đầu từ đâu?',
            ('Từ lối mòn mọi người hay đi.',
             'Hợp lý, nhưng trồng dọc lối có thể che mất nắng. Bạn ưu tiên bóng mát hay tầm nhìn thoáng?',
             ('Bóng mát, để người đi mệt có chỗ nghỉ.', 'Tôi sẽ trồng thưa và chừa khoảng trống ở khúc rẽ. Bóng mát phải đi cùng lối đi rõ ràng mới thành nơi dễ chịu.'),
             ('Tầm nhìn thoáng, để không ai lạc.', 'Vậy tôi sẽ chọn cây thấp ở đoạn đầu và cây cao ở phía xa. Một con đường vừa mát vừa dễ nhìn mới bền.')),
            ('Tôi muốn dạy người mới cách đọc rừng.',
             'Tôi chỉ biết chỉ bằng tay, không quen dạy. Bạn nghĩ nên bắt đầu bằng dấu chân hay tiếng chim?',
             ('Dấu chân và lối mòn, dễ thấy nhất.', 'Vậy tôi sẽ dẫn một vòng thật chậm. Đi đúng một lần rồi tự quay lại được, đó mới là học được rừng.'),
             ('Tiếng chim, để họ nghe trước khi nhìn.', 'Tiếng chim dạy mình sự kiên nhẫn. Nhưng phải chỉ cả đường về nữa, vì biết lắng nghe mà lạc thì vẫn chưa đủ.'))),
        'memory': (
            'Tôi từng lạc trong rừng một đêm. Bạn có muốn nghe tôi tìm về bằng cách nào không?',
            ('Bác tìm về bằng tiếng suối à?',
             'Đúng, tôi ngồi im đến khi nghe được nước. Bạn nghĩ lúc ấy điều gì cứu mình: tiếng suối hay việc mình chịu ngồi yên?',
             ('Chịu ngồi yên, vì hoảng thì không nghe được gì.', 'Chính thế. Rừng không làm mình lạc, nỗi hoảng mới làm mình đi sai. Sau đêm ấy tôi học cách đứng lại trước khi bước.'),
             ('Tiếng suối, vì nó chỉ đúng hướng.', 'Tiếng suối chỉ hướng, nhưng phải bình tĩnh mới nghe ra. Hai thứ ấy phải có cùng lúc thì mới tìm được đường về.')),
            ('Cây thông già ở lối vào do ông bác trồng à?',
             'Đúng, ông tôi trồng nó khi lối mòn còn chưa có tên. Bạn thấy một cái cây có thể giữ ký ức của một gia đình không?',
             ('Có, vì mỗi lần đi qua là một lần nhớ.', 'Tôi vẫn dọn cành cho nó mỗi mùa. Cây còn đó thì người đi sau còn biết chỗ này từng có ai chăm sóc.'),
             ('Không hẳn, ký ức nằm ở người nhiều hơn.', 'Có lẽ vậy. Nhưng cây giúp người ta nhớ cùng nhau, và đôi khi mình cần một chỗ để cùng nhớ.'))),
    },
}

_WEATHER = {
    'lan': 'Mưa xuống rồi, mình vừa che giỏ hạt cho khô.',
    'tu': 'Mưa gõ lộp bộp trên mặt hồ nghe vui tai quá.',
    'an': 'Mưa để lại những hạt nước trong veo trên cánh hoa.',
    'mai': 'Mưa rồi, mình ôm sách sát vào cho khỏi ướt.',
    'son': 'Mưa làm đất rừng mềm hơn, bạn bước thong thả nhé.',
}
_CLOSE = {
    'lan': 'Khách quen của mình đến rồi, có bạn tiệm vui hơn hẳn.',
    'tu': 'Bác vừa nghĩ hôm nay cháu có ghé không đấy.',
    'an': 'Có bạn ở đây mình lại muốn chia sẻ thêm một góc vườn.',
    'mai': 'Mình đã để dành trang trống cho câu chuyện của bạn.',
    'son': 'Nghe bước chân quen là tôi biết có bạn tới thăm.',
}

# Additional story routes.  They use the same two-turn shape as the original
# topics so the dialogue engine, rewards and save behaviour stay unchanged.
_EXTRA_SCRIPTS = {
    'lan': {
        'festival': (
            'Lễ hội mùa này tiệm mình định dựng một quầy nhỏ. Bạn muốn quầy bán hạt giống hay góc đổi hạt cũ?',
            ('Một quầy đầy hạt giống, để ai cũng bắt đầu được.',
             'Mình sẽ để túi hạt thấp vừa tầm trẻ con. Bạn nghĩ nên kèm một tờ hướng dẫn hay để mọi người tự hỏi?',
             ('Kèm tờ hướng dẫn ngắn, dễ đọc.', 'Vậy mình sẽ viết thật to ba bước gieo hạt. Người mới cầm túi hạt mà không phải ngại hỏi là mình vui rồi.'),
             ('Để mọi người tự hỏi, mình thích trò chuyện hơn.', 'Mình cũng thích vậy. Quầy hạt sẽ thành chỗ đứng chuyện, chứ không chỉ là nơi trao đổi tiền.')),
            ('Một góc đổi hạt cũ, để không ai phải bỏ thứ còn dùng được.',
             'Mình sẽ kê một cái bàn ở hiên. Bạn nghĩ nên nhận hạt thừa hay đổi lấy một chút xu?',
             ('Nhận hạt thừa rồi chia lại cho người cần.', 'Mình sẽ để một giỏ riêng ghi “hạt của làng”. Ai góp cũng vui, ai nhận cũng thấy được chào đón.'),
             ('Đổi lấy một chút xu để giữ công bằng.', 'Mình sẽ đặt giá thật nhỏ thôi. Có một chút xu, người ta thấy món đồ được trân trọng hơn.'))),
        'secret': (
            'Có lần mình giữ lại một túi hạt đẹp mà không bán. Bạn nghĩ mình nên kể cho ai?',
            ('Mình giữ vì nó nhắc tới người trồng ra nó.',
             'Người ấy đã rời làng từ lâu. Bạn nghĩ mình nên gieo thử hay cất mãi trong ngăn kéo?',
             ('Gieo thử một luống, để hạt được sống tiếp.', 'Mình sẽ gieo ở góc vườn sau tiệm. Nếu nở hoa, mình sẽ để một nhánh ở cửa sổ như lời chào.'),
             ('Cất đi, để giữ nguyên ký ức.', 'Có những thứ mình chỉ cần biết nó còn đó. Mình sẽ gói lại cẩn thận và thôi thấy áy náy.')),
            ('Mình nên kể cho An, người hiểu hạt giống.',
             'Nhưng mình sợ An sẽ nghĩ mình giữ hạt quá lâu. Bạn nghĩ mình nên nói thẳng hay đợi dịp hợp?',
             ('Nói thẳng, An sẽ hiểu.', 'Mình sẽ mang túi hạt sang vườn. Nói ra rồi, có khi mình còn học được cách giữ một thứ mà không cần giấu.'),
             ('Đợi lúc cùng chăm hoa rồi kể.', 'Mình sẽ chọn một buổi chiều yên. Câu chuyện đến đúng lúc thì nhẹ hơn nhiều.'))),
        'future': (
            'Mình đang nghĩ tới một ngày tiệm có thêm chỗ ngồi uống trà. Bạn muốn nó nhìn ra đường hay nhìn vào vườn?',
            ('Nhìn ra vườn, để khách thấy cây đang lớn.',
             'Mình sẽ đặt bàn cạnh cửa sổ. Bạn nghĩ nên trồng hoa gì để khách chờ cũng thấy vui?',
             ('Hoa cúc, vừa thơm vừa dễ chăm.', 'Mình sẽ trồng một dải cúc vàng dưới cửa sổ. Mùi hoa sẽ là lời mời trước cả tiếng chuông cửa.'),
             ('Một loại hoa đổi theo mùa, để lúc nào cũng mới.', 'Mình sẽ thử đổi chậu theo mùa. Tiệm nhỏ mà có bốn mùa đi qua cửa sổ thì cũng đủ vui.')),
            ('Nhìn ra đường, để khách qua lại dễ ghé.',
             'Như vậy sẽ đông hơn, nhưng chỗ ngồi có thể chật. Bạn nghĩ nên kê bàn nhỏ hay một dãy ghế dài?',
             ('Bàn nhỏ, để ai cũng có góc riêng.', 'Mình sẽ kê vài bàn hai ghế. Người quen có thể ngồi lâu mà không thấy mình chiếm chỗ của ai.'),
             ('Ghế dài, để người lạ dễ bắt chuyện.', 'Mình thích ý ấy. Một dãy ghế dài có thể biến người chờ nhau thành người quen.'))),
    },
    'tu': {
        'festival': (
            'Lễ hội năm nay bác định mở một góc kể chuyện bên hồ. Cháu nghĩ nên kể chuyện cá hay chuyện làng?',
            ('Chuyện cá, vì ai cũng tò mò dưới nước có gì.',
             'Bác sẽ kể con cá vàng bác từng thấy. Cháu nghĩ nên kể thật hay thêm chút huyền?',
             ('Kể thật, để người nghe tin mình.', 'Vậy bác sẽ kể đúng những gì còn nhớ. Một câu chuyện thật mà chậm rãi còn quý hơn mười chuyện ly kỳ.'),
             ('Thêm một chút huyền, cho lễ hội vui.', 'Bác sẽ thêm tiếng nước dâng và ánh trăng, nhưng vẫn giữ cái lõi thật. Kể chuyện cũng như câu cá, phải biết thả dây.')),
            ('Chuyện làng, vì người lớn tuổi còn nhớ nhiều.',
             'Bác sẽ mời thêm vài người cùng kể. Cháu nghĩ nên để mỗi người kể một đoạn hay bác kể trước?',
             ('Mỗi người một đoạn, câu chuyện sẽ có nhiều giọng.', 'Vậy bác sẽ ngồi nghe trước. Một buổi kể chuyện hay khi người kể sau không phải lặp lại người trước.'),
             ('Bác kể trước, rồi mời người khác tiếp.', 'Bác sẽ mở bằng chuyện ngắn thôi. Có người mở đường, người sau sẽ dễ kể hơn.'))),
        'secret': (
            'Có một chỗ trên hồ bác chưa từng dẫn ai tới. Cháu muốn biết vì sao không?',
            ('Đó là chỗ bác từng ngồi với người bạn cũ.',
             'Bạn ấy đi xa, để lại một cần câu gỗ. Cháu nghĩ bác nên mang cần ấy ra hồ lại hay cất trong nhà?',
             ('Mang ra hồ, để nó còn được dùng.', 'Bác sẽ lau lại và câu một buổi. Có lẽ bạn ấy sẽ cười nếu thấy bác vẫn còn vụng về như xưa.'),
             ('Cất trong nhà, để giữ nguyên như kỷ vật.', 'Vậy bác sẽ treo cạnh cửa sổ. Mỗi sáng thấy nó, bác nhớ có một người đã từng ngồi bên mình.')),
            ('Bác chưa dẫn ai vì lối đi hẹp, sợ người lạ vấp.',
             'Bác đã dọn bớt cành. Cháu nghĩ nên dẫn một người tới thử hay để chỗ ấy yên?',
             ('Dẫn một người tới thử, để chỗ ấy không bị quên.', 'Bác sẽ dẫn Mai tới, bạn ấy biết giữ chuyện. Một chỗ đẹp mà không ai biết thì cũng buồn.'),
             ('Để yên, không phải chỗ nào cũng cần người tới.', 'Cháu nói phải. Bác sẽ giữ nó như một khoảng lặng của hồ, chỉ kể khi thật cần.'))),
        'future': (
            'Bác tính dạy câu cho đứa trẻ trong làng. Cháu nghĩ nên bắt đầu bằng cách giữ cần hay cách đọc nước?',
            ('Giữ cần trước, tay quen rồi mới hiểu nước.',
             'Nhưng bọn trẻ thích thấy cá ngay. Cháu nghĩ nên cho chúng câu ở chỗ dễ hay cứ dẫn ra hồ lớn?',
             ('Chỗ dễ trước, để chúng có niềm vui.', 'Bác sẽ dẫn ra mép hồ cạn. Câu được con cá nhỏ đầu tiên, đứa trẻ sẽ nhớ cả đời.'),
             ('Ra hồ lớn, để học cả sự kiên nhẫn.', 'Vậy bác sẽ chuẩn bị trà và một buổi dài. Không câu được cũng là bài học, miễn đừng bỏ về giữa chừng.')),
            ('Đọc nước trước, vì hiểu nước thì mới biết cá ở đâu.',
             'Bác sẽ dạy chúng nhìn gợn sóng và bóng mây. Cháu nghĩ nên cho chúng tự đoán hay chỉ từng chỗ?',
             ('Để chúng tự đoán, sai thì mình sửa.', 'Bác sẽ đứng sau lặng nghe. Đoán sai một hai lần rồi tự thấy, các cháu sẽ nhớ lâu hơn.'),
             ('Chỉ từng chỗ trước, cho chắc.', 'Bác sẽ chỉ những chỗ chắc chắn. Khi đã quen, các cháu tự khám phá phần còn lại của hồ.'))),
    },
    'an': {
        'festival': (
            'Mình muốn làm một con đường hoa dẫn vào lễ hội. Bạn thích hoa trắng hay một dải nhiều màu?',
            ('Hoa trắng, để lối đi thật dịu.',
             'Mình sẽ trồng cúc trắng hai bên. Bạn nghĩ nên để một khoảng trống ở giữa hay trồng kín?',
             ('Để khoảng trống, người đi sẽ thấy nhẹ.', 'Mình sẽ chừa một lối đất mộc. Đôi khi khoảng trống làm mình nhìn hoa kỹ hơn.'),
             ('Trồng kín, để lễ hội thật rực rỡ.', 'Mình sẽ trồng dày nhưng chừa lối nhỏ. Rực rỡ mà vẫn bước qua được mới là khéo.')),
            ('Nhiều màu, để ai cũng tìm thấy màu mình thích.',
             'Mình sẽ nhờ trẻ trong làng chọn màu. Bạn nghĩ nên chia luống theo màu hay trộn lẫn?',
             ('Chia theo màu, nhìn sẽ gọn và dễ chăm.', 'Mình sẽ làm từng dải màu nối tiếp. Người đi hết con đường sẽ thấy như đi qua một mùa hoa.'),
             ('Trộn lẫn, để có chỗ bất ngờ.', 'Mình sẽ gieo xen hạt. Một bông mọc lạc chỗ đôi khi lại là bông đẹp nhất.'))),
        'secret': (
            'Mình có một luống hoa không bao giờ cắt. Bạn có muốn biết vì sao không?',
            ('Đó là luống hoa mẹ mình trồng trước khi đi.',
             'Mình sợ cắt rồi nó sẽ tàn. Bạn nghĩ mình nên hái một bông để cắm trong nhà hay cứ để nguyên?',
             ('Hái một bông, để hoa được ở gần mình.', 'Mình sẽ hái bông nở đẹp nhất. Hoa trong nhà có thể tàn, nhưng mình sẽ nhớ mùi hương ấy lâu hơn.'),
             ('Để nguyên, cho luống hoa tự sống.', 'Mình sẽ tiếp tục chăm và không cắt. Có những thứ mình giữ bằng cách để chúng tiếp tục lớn.')),
            ('Mình giữ nó vì đó là giống hoa khó trồng.',
             'Mình đã thử nhân giống nhưng chưa thành. Bạn nghĩ mình nên thử lại hay tìm giống khác?',
             ('Thử lại, mình sẽ giúp bạn chăm.', 'Có người cùng chăm, mình thấy dễ hơn. Lần này mình sẽ ghi lại từng ngày thay đổi.'),
             ('Tìm giống khác, để vườn có thêm màu.', 'Mình sẽ giữ luống cũ và trồng thêm một luống mới. Không cần thay thế ký ức, chỉ cần mở thêm chỗ cho tương lai.'))),
        'future': (
            'Mình muốn biến bãi đất sau vườn thành nơi ươm cây. Bạn nghĩ nên làm nhà lưới hay để trời nuôi?',
            ('Để trời nuôi, cây sẽ cứng cáp hơn.',
             'Nhưng mùa mưa lớn có thể làm cây non ngã. Bạn nghĩ nên che tạm hay chấp nhận mất một ít?',
             ('Che tạm, để giữ những cây yếu.', 'Mình sẽ dựng mái nhỏ khi mưa tới. Chăm cây cũng như chăm người, cần biết lúc nào che và lúc nào để lớn.'),
             ('Chấp nhận mất một ít, cây còn lại sẽ khỏe.', 'Mình sẽ chọn những cây mạnh nhất. Vườn không cần đông, chỉ cần mỗi cây đứng vững.')),
            ('Làm nhà lưới, để kiểm soát sâu bệnh.',
             'Nhưng nhà lưới tốn công dựng. Bạn nghĩ nên làm nhỏ trước hay làm một lần cho rộng?',
             ('Làm nhỏ trước, học rồi mở rộng.', 'Mình sẽ dựng một khung nhỏ sau vườn. Thấy nó đứng được qua một mùa, mình mới dám làm tiếp.'),
             ('Làm một lần cho rộng, đỡ phải sửa.', 'Mình sẽ nhờ Sơn giúp lấy cây. Một lần làm kỹ, sau này chỉ cần chăm thôi.'))),
    },
    'mai': {
        'festival': (
            'Lễ hội là dịp tốt để mở một góc đọc sách. Bạn muốn chọn sách cho trẻ hay sách về làng?',
            ('Sách cho trẻ, để chúng có chỗ bắt đầu.',
             'Mình sẽ chọn truyện ngắn và sách tranh. Bạn nghĩ nên đọc to hay để các em tự chọn?',
             ('Đọc to một câu chuyện, rồi để các em tự chọn.', 'Mình sẽ mở đầu bằng một chuyện ngắn. Nghe xong, đứa trẻ nào muốn ở lại sẽ tự tìm trang tiếp theo.'),
             ('Để các em tự chọn, mỗi em một niềm vui.', 'Mình sẽ xếp sách thấp vừa tầm tay. Chọn được một cuốn mình thích là bước đầu của người đọc.')),
            ('Sách về làng, để người lớn cùng nhớ.',
             'Mình sẽ đặt sổ làng bên cạnh. Bạn nghĩ nên mời người lớn kể thêm hay chỉ trưng bày?',
             ('Mời họ kể thêm, để sổ được viết tiếp.', 'Mình sẽ để bút và giấy trắng. Ai góp một câu, sổ làng lại dày thêm một chút.'),
             ('Chỉ trưng bày, để mọi người đọc trong yên.', 'Mình sẽ đặt một chiếc ghế nhỏ cạnh bàn. Có khi chỉ cần ngồi xuống là đã bắt đầu nhớ.'))),
        'secret': (
            'Mình có một cuốn sổ không đưa vào thư viện. Bạn có muốn biết nó ghi gì không?',
            ('Đó là những câu chuyện mình chưa dám viết hết.',
             'Mình sợ viết ra sẽ làm người trong chuyện buồn. Bạn nghĩ mình nên giữ riêng hay đưa họ đọc trước?',
             ('Đưa họ đọc trước, để họ chọn.', 'Mình sẽ hỏi từng người. Một câu chuyện về ai cũng nên được người ấy đồng ý trước khi kể.'),
             ('Giữ riêng, cho tới khi mình hiểu hơn.', 'Mình sẽ viết tiếp mà chưa công bố. Có những trang cần thời gian mới đủ chín.')),
            ('Đó là cuốn sổ ghi những chuyện mình nghe lén.',
             'Mình biết như vậy chưa hay. Bạn nghĩ mình nên xin lỗi những người trong sổ hay chỉ thôi ghi?',
             ('Xin lỗi và xin phép ghi lại.', 'Mình sẽ gặp từng người. Nếu họ đồng ý, câu chuyện sẽ có gốc rễ; nếu không, mình sẽ xé trang ấy.'),
             ('Thôi ghi, giữ phần đã nghe trong lòng.', 'Mình sẽ cất sổ đi. Biết dừng lại cũng là một cách tôn trọng người khác.'))),
        'future': (
            'Mình muốn viết một cuốn sách về Mossbrook Meadow. Bạn nghĩ nên bắt đầu từ hồ hay từ nông trại?',
            ('Từ nông trại, vì đó là nơi câu chuyện bắt đầu.',
             'Mình sẽ bắt đầu bằng ngôi nhà của bạn. Bạn muốn mình kể về người đầu tiên hay vụ mùa đầu tiên?',
             ('Người đầu tiên, để có một cái tên.', 'Mình sẽ tìm tên trong sổ cũ. Một câu chuyện có tên người sẽ không còn là chuyện chung chung.'),
             ('Vụ mùa đầu tiên, để có một khởi đầu.', 'Mình sẽ tả luống đất đầu tiên bên hồ. Cây mọc lên từ đất mới là hình ảnh mình muốn mở sách.')),
            ('Từ hồ, vì hồ đã ở đó trước cả làng.',
             'Mình sẽ phỏng vấn Bác Tư. Bạn nghĩ nên ghi lời bác nguyên văn hay viết lại cho gọn?',
             ('Nguyên văn, để giữ giọng nói của bác.', 'Mình sẽ ghi cả những khoảng lặng. Đôi khi người đọc cần nghe cách một người ngừng nói.'),
             ('Viết lại cho gọn, để dễ đọc.', 'Mình sẽ giữ ý và nhịp kể, nhưng bỏ phần lặp. Sách cần mời người đọc bước vào, không làm họ mệt.'))),
    },
    'son': {
        'festival': (
            'Lễ hội mình định mở một lối đi qua rừng cho khách. Bạn nghĩ nên dẫn tới đồi gió hay bờ suối?',
            ('Tới đồi gió, để thấy cả làng từ trên cao.',
             'Mình sẽ dọn một lối ngắn nhưng dốc. Bạn nghĩ nên đặt ghế nghỉ giữa đường hay chỉ để đá tự nhiên?',
             ('Đặt một ghế nghỉ, để người mệt có chỗ ngồi.', 'Mình sẽ làm một băng ghế gỗ đơn giản. Người đi xa mà biết phía trước có chỗ nghỉ sẽ yên tâm hơn.'),
             ('Để đá tự nhiên, cho lối đi giữ vẻ hoang.', 'Mình sẽ chọn một tảng đá phẳng và dọn quanh nó. Không cần bóng mát nhân tạo, rừng đã đủ dịu.')),
            ('Tới bờ suối, để khách nghe nước.',
             'Lối ấy thấp và dễ đi hơn. Bạn nghĩ nên đặt một cây cầu nhỏ hay để người ta bước qua đá?',
             ('Một cây cầu nhỏ, để ai cũng qua được.', 'Mình sẽ bắc cầu ở chỗ nước cạn. Một lối đi tốt là lối mà người yếu nhất cũng dùng được.'),
             ('Bước qua đá, để giữ cảm giác đi rừng.', 'Mình sẽ chọn những viên đá chắc và đặt thêm một tay vịn. Vẫn gần thiên nhiên, nhưng không ai phải liều.'))),
        'secret': (
            'Mình có một cây thông già bị sét đánh, vẫn đứng đó. Bạn có muốn biết mình giữ nó vì sao không?',
            ('Vì chim vẫn làm tổ trong thân cây ấy.',
             'Cây trông xấu nhưng vẫn có ích. Bạn nghĩ mình nên để nguyên hay tỉa bớt cành khô?',
             ('Để nguyên, đừng làm chim sợ.', 'Mình sẽ chỉ dọn cành rơi dưới gốc. Cây già còn che được một tổ nhỏ thì vẫn đáng được đứng.'),
             ('Tỉa bớt, để cây không gãy vào lối đi.', 'Mình sẽ tỉa phần ngọn khô và giữ thân chính. Chăm rừng là biết chỗ nào cần can thiệp, chỗ nào nên để yên.')),
            ('Vì nó là mốc để mình không lạc.',
             'Mình từng đi lạc một đêm quanh nó. Bạn nghĩ mình nên kể chuyện ấy cho người mới hay giữ riêng?',
             ('Kể, để người mới biết rừng không dễ.', 'Mình sẽ kể vào lúc dẫn họ qua lối. Một câu chuyện thật giúp người ta chuẩn bị tốt hơn lời dặn suông.'),
             ('Giữ riêng, không muốn ai sợ.', 'Mình sẽ chỉ nói những gì cần thiết. Rừng đã đủ bí ẩn, không cần thêm lời làm người ta lo.'))),
        'future': (
            'Mình muốn trồng thêm một dải cây bản địa ven lối mòn. Bạn nghĩ nên chọn cây cho hoa hay cây cho bóng?',
            ('Cây cho hoa, để lối đi có mùa.',
             'Mình sẽ chọn loài hoa rừng nhỏ. Bạn nghĩ nên trồng thành từng cụm hay rải dọc đường?',
             ('Từng cụm, để mỗi chỗ là một điểm dừng.', 'Mình sẽ trồng ba cụm ở ba khúc ngoặt. Người đi sẽ có lý do chậm lại ở từng đoạn.'),
             ('Rải dọc đường, để đi đâu cũng thấy.', 'Mình sẽ gieo thưa thôi. Hoa rải khắp lối sẽ làm người ta nhìn xuống nhiều hơn.')),
            ('Cây cho bóng, để lối đi mát hơn.',
             'Nhưng cây lớn có thể che mất tầm nhìn. Bạn nghĩ nên trồng một bên hay cả hai bên?',
             ('Một bên, để lối còn sáng.', 'Mình sẽ trồng phía đông, nơi nắng gắt nhất. Bóng mát đúng chỗ còn quý hơn bóng mát tràn lan.'),
             ('Cả hai bên, để thành một vòm cây.', 'Mình sẽ chừa khoảng trống trên cao. Vòm cây đẹp nhưng vẫn phải cho ánh sáng đi qua.'))),
    },
}
for _extra_npc, _extra_topics in _EXTRA_SCRIPTS.items():
    _SCRIPTS[_extra_npc].update(_extra_topics)

_SALUTATIONS = {
    'lan': ('Mừng bạn ghé tiệm.', 'Mình vừa xếp hàng xong, ghé chơi nhé.',
            'Hôm nay gặp bạn sớm, vui quá.'),
    'tu': ('Lại đây ngồi với bác, cháu.', 'Bác vừa thu cần, cháu ghé đúng lúc.',
           'Bác đang ngóng có người ngồi chơi đây.'),
    'an': ('Mừng bạn ghé vườn.', 'Mình vừa đặt bình tưới xuống, vào chơi nhé.',
           'Thấy bạn qua lối hoa là mình vui rồi.'),
    'mai': ('Chào bạn, mình vừa đọc xong một trang.', 'Ghé chơi nhé, mình đang đánh dấu sách.',
            'Hôm nay lại có bạn để cùng kể chuyện rồi.'),
    'son': ('Chào bạn, đi đường có mệt không?', 'Tôi vừa về từ lối rừng, mừng bạn ghé.',
            'Lại gặp bạn ở đây, rừng hôm nay có khách quý rồi.'),
}
_TRUST = {
    'lan': 'Mình để dành cho bạn chỗ ngồi cạnh cửa sổ, chỗ ấm nhất tiệm.',
    'tu': 'Cháu cứ ngồi chỗ đá này, bác đã lau khô từ sớm.',
    'an': 'Mình hái sẵn một nhánh hoa nhỏ, để dành cho người ghé vườn hôm nay.',
    'mai': 'Mình đã đánh dấu một trang cho riêng bạn, đọc xong mình cùng bàn nhé.',
    'son': 'Tôi để sẵn một bình trà rừng, ai đi đường xa ghé đây đều được uống.',
}


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


def begin_dialogue(farm: 'Farm', npc_id: str, topic: str = 'greet') -> Conversation:
    """Open a conversation without changing any saved game state."""
    _validate_nearby(farm, npc_id, topic)
    question, warm, practical = _SCRIPTS[npc_id][topic]
    if topic == 'greet':
        greeting = _SALUTATIONS[npc_id][(farm.day - 1) % 3]
        if farm.friendships[npc_id] == 0:
            greeting += f' Chào {farm.player_name}, chủ nông trại {farm.name}!'
        elif farm.friendships[npc_id] >= 9:
            greeting += ' ' + _TRUST[npc_id]
        elif farm.friendships[npc_id] >= 5:
            greeting += ' ' + _CLOSE[npc_id]
        elif farm.friendships[npc_id] == 3:
            greeting += f' {bond_title(3)} rồi, mình nói chuyện với bạn dễ hơn nhiều.'
        if farm.weather == 'rainy':
            greeting += ' ' + _WEATHER[npc_id]
        question = greeting + ' ' + question
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


def dialogue_node(conversation: Conversation) -> DialogueNode:
    from .model import GameError

    if conversation.node_id not in conversation._nodes:
        raise GameError('Lượt trò chuyện không hợp lệ.')
    return conversation._nodes[conversation.node_id]


def choose_response(farm: 'Farm', conversation: Conversation, choice_id: str) -> str:
    """Return new transcript lines, followed by any daily friendship/XP reward."""
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
    new_lines = [f'Bạn: {choice.text}', f'{NPCS[conversation.npc_id].name}: {following.npc_line}']
    reward = []
    if farm.talked_on[conversation.npc_id] != farm.day:
        status = talk(farm, conversation.npc_id, conversation.topic).splitlines()[-1]
        xp_status = farm.award_xp(3)
        reward = [status, xp_status] if xp_status else [status]
        conversation.credited = True
    conversation.history.extend(new_lines)
    conversation.node_id = following.id
    conversation.done = not following.choices
    return '\n'.join(new_lines + reward)
