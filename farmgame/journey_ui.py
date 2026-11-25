"""Small journal and encounter menus for the two terminal clients."""
from . import journey
from .catalog import ITEMS
from .model import GameError
from .pages import PAGES


def _project_at(site):
    return next((p for p in journey.PROJECTS.values() if p.site == site.key), None)


def _site_details(farm, site):
    item = site.gather[journey.season_index(farm)]
    state = ('Đã thu thập hôm nay; sáng mai có lại.'
             if farm.gathered_on.get(site.key) == farm.day else 'Chưa thu thập hôm nay.')
    return [site.story, journey.calendar_line(farm),
            f'Mùa này: {ITEMS[item].name}. {state}']


def explorer_site(game):
    farm = game.farm
    site = journey.nearby_site(farm)
    if site is None:
        return
    project = _project_at(site)
    labels = ['Thu thập sản vật hôm nay']
    details = _site_details(farm, site)
    if project:
        labels.append('Cùng phục hồi: ' + project.name)
        details += journey.project_requirements(farm, project)
    festival_choice = len(labels)
    if site.key == 'square':
        labels.append('Dự lễ hội mùa')
        details.append(journey.festival_line(farm))
    read_choice = len(labels)
    labels.append('Đọc trọn câu chuyện và yêu cầu')
    choice = game._choose(site.name, labels, details=details)
    if choice == 0:
        game._action(journey.gather, farm, site.key)
    elif project and choice == 1:
        if farm.restoration.get(project.key, 0) >= 3:
            game._reader(project.name, project.benefit)
            return
        confirm = game._choose('ĐÓNG GÓP · ' + project.name,
                               ['Giữ nguyên liệu', 'Góp đủ nguyên liệu và xu cho chặng này'],
                               details=journey.project_requirements(farm, project))
        if confirm == 1:
            if game._action(journey.restore, farm, project.key):
                game._reader(project.name, game.messages[-1])
    elif site.key == 'square' and choice == festival_choice:
        if game._action(journey.attend_festival, farm):
            game._reader('LỄ HỘI MÙA', game.messages[-1])
    elif choice == read_choice:
        game._reader(site.name, '\n'.join(details))


def explorer_journal(game):
    farm = game.farm
    choice = game._choose('HÀNH TRÌNH MOSSBROOK', [
        f'Đọc nhật ký · {len(farm.discovered)}/31 vùng',
        'Đi tới điểm khám phá',
        'Công trình cộng đồng',
        'Lịch mùa và lễ hội',
    ], details=[journey.calendar_line(farm), journey.festival_line(farm)],
        close_keys=('u', 'U'))
    if choice == 0:
        game._reader('SỔ HÀNH TRÌNH', '\n'.join(journey.journal_lines(farm)))
    elif choice == 1:
        sites = list(journey.SITES.values())
        index = game._choose('ĐIỂM KHÁM PHÁ · 31 VÙNG', [
            f'{PAGES[s.key].name} · {s.name}' + (' · đã ghé' if s.key in farm.discovered else '')
            for s in sites])
        if index is not None:
            game._action(journey.travel_to_site, farm, sites[index].key)
    elif choice == 2:
        projects = list(journey.PROJECTS.values())
        index = game._choose('KHÔI PHỤC LÀNG · 8 CÔNG TRÌNH', [
            f'{p.name} · {farm.restoration.get(p.key, 0)}/3 · {PAGES[p.site].name}'
            for p in projects])
        if index is None:
            return
        project = projects[index]
        details = journey.project_requirements(farm, project)
        index = game._choose(project.name, ['Đến công trình', 'Xem tiến độ'], details=details)
        if index == 0:
            game._action(journey.travel_to_site, farm, project.site)
        elif index == 1:
            game._reader(project.name, '\n'.join(details))
    elif choice == 3:
        lines = [journey.calendar_line(farm), journey.festival_line(farm), '',
                 'Mỗi mùa dài 28 ngày. Cây trong ruộng tiếp tục lớn như thường.',
                 'Sản vật tại dấu ! đổi theo mùa; rau thơm và nấm nhiều hơn khi mưa.',
                 'Ngày hội: mang món góp đến Sân hội bên giếng (!) rồi E để dự hội.',
                 'Mỗi hội được dự một lần trong năm; có bữa ăn, hạt và tình làng.']
        lines += [f'{journey.SEASON_NAMES[i]} · ngày {journey.FESTIVALS[key].day}: '
                  + journey.FESTIVALS[key].name for i, key in enumerate(journey.SEASONS)]
        game._reader('LỊCH MÙA', '\n'.join(lines))


def _text_pick(ui, title, labels, details=()):
    ui.say(title, 'title')
    for line in details:
        ui.wrapped(line)
    for index, label in enumerate(labels, 1):
        ui.wrapped(f'[{index}] {label}')
    ui.wrapped('[0] Quay lại', 'dim')
    answer = ui.ask('Chọn: ').lower()
    if answer in ('', '0', 'q', 'esc', 'u'):
        return None
    if not answer.isdecimal() or not 1 <= int(answer) <= len(labels):
        raise GameError('Chọn số trong danh sách hoặc 0 để quay lại.')
    return int(answer)-1


def text_site(ui):
    farm = ui.farm
    site = journey.nearby_site(farm)
    if site is None:
        return False
    project = _project_at(site)
    labels = ['Thu thập sản vật hôm nay']
    details = _site_details(farm, site)
    if project:
        labels.append('Cùng phục hồi: ' + project.name)
        details += journey.project_requirements(farm, project)
    festival_choice = len(labels)
    if site.key == 'square':
        labels.append('Dự lễ hội mùa')
        details.append(journey.festival_line(farm))
    choice = _text_pick(ui, site.name, labels, details)
    if choice == 0:
        ui.messages = [journey.gather(farm, site.key)]
    elif project and choice == 1:
        if farm.restoration.get(project.key, 0) >= 3:
            ui.wrapped(project.benefit)
            return False
        confirm = _text_pick(ui, 'ĐÓNG GÓP · ' + project.name,
                             ['Giữ nguyên liệu', 'Góp đủ nguyên liệu và xu cho chặng này'],
                             journey.project_requirements(farm, project))
        if confirm != 1:
            return False
        ui.messages = [journey.restore(farm, project.key)]
    elif site.key == 'square' and choice == festival_choice:
        ui.messages = [journey.attend_festival(farm)]
    else:
        return False
    return True


def text_journal(ui):
    farm = ui.farm
    choice = _text_pick(ui, 'HÀNH TRÌNH MOSSBROOK', [
        f'Đọc nhật ký · {len(farm.discovered)}/31 vùng', 'Đi tới điểm khám phá',
        'Công trình cộng đồng', 'Lịch mùa và lễ hội'],
        [journey.calendar_line(farm), journey.festival_line(farm)])
    if choice == 0:
        for line in journey.journal_lines(farm):
            ui.wrapped(line)
        ui.ask('Enter để quay lại... ')
    elif choice == 1:
        sites = list(journey.SITES.values())
        index = _text_pick(ui, 'ĐIỂM KHÁM PHÁ', [
            f'{PAGES[s.key].name} · {s.name}' for s in sites])
        if index is not None:
            ui.messages = [journey.travel_to_site(farm, sites[index].key)]
            return True
    elif choice == 2:
        projects = list(journey.PROJECTS.values())
        index = _text_pick(ui, 'KHÔI PHỤC LÀNG', [
            f'{p.name} · {farm.restoration.get(p.key, 0)}/3' for p in projects])
        if index is None:
            return False
        project = projects[index]
        index = _text_pick(ui, project.name, ['Đến công trình'],
                           journey.project_requirements(farm, project))
        if index == 0:
            ui.messages = [journey.travel_to_site(farm, project.site)]
            return True
    elif choice == 3:
        ui.wrapped('Mỗi mùa 28 ngày; cây ruộng tiếp tục lớn. Sản vật tại dấu ! đổi theo mùa.')
        for i, key in enumerate(journey.SEASONS):
            festival = journey.FESTIVALS[key]
            ui.wrapped(f'{journey.SEASON_NAMES[i]} · ngày {festival.day}: {festival.name}. '
                       f'Góp {ITEMS[festival.item].name} ×{festival.amount} ở Sân hội (!), Quảng Trường.')
        ui.ask('Enter để quay lại... ')
    return False
