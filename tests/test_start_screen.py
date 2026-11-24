import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'farm.json'

    def run_menu(self, answers, **kwargs):
        from farmgame.start_screen import run_startup
        self.output = io.StringIO()
        with patch('builtins.input', side_effect=answers), redirect_stdout(self.output):
            return run_startup(self.path, graphical=False, **kwargs)

    def old_save(self):
        from farmgame.model import Farm
        from farmgame.storage import save_game
        save_game(Farm(name='Vườn cũ'), self.path)
        return self.path.read_bytes()

    def test_quit_and_eof_never_create_save(self):
        for answer in (['0'], [EOFError], [KeyboardInterrupt]):
            self.assertIsNone(self.run_menu(answer).farm)
            self.assertFalse(self.path.exists())

    def test_cancel_wizard_preserves_existing_bytes(self):
        original = self.old_save()
        result = self.run_menu(['2', 'An', '0', '0'])
        self.assertIsNone(result.farm)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.bak-*')), [])

    def test_final_confirmation_creates_profile_and_exact_backup(self):
        from farmgame.storage import load_game
        original = self.old_save()
        result = self.run_menu(['2', 'Bình', 'Vườn Nắng', '2', '2', '3', '1'], skip_intro=True)
        self.assertTrue(result.created)
        farm = load_game(self.path)
        self.assertEqual((farm.player_name, farm.name, farm.avatar, farm.outfit, farm.background),
                         ('Bình', 'Vườn Nắng', '&', 'cyan', 'traveler'))
        self.assertTrue(farm.intro_seen)
        self.assertEqual([p.read_bytes() for p in self.path.parent.glob('*.bak-*')], [original])

    def test_continue_and_preview_do_not_write(self):
        original = self.old_save()
        self.assertEqual(self.run_menu(['1']).farm.name, 'Vườn cũ')
        self.run_menu(['3', 'q', '0'])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('*.bak-*')), [])

    def test_corrupt_continue_keeps_title_and_file(self):
        self.path.write_bytes(b'bad save')
        self.assertIsNone(self.run_menu(['1', '0']).farm)
        self.assertIn('Không thể đọc', self.output.getvalue())
        self.assertEqual(self.path.read_bytes(), b'bad save')

    def test_invalid_name_reprompts_and_normalizes_unicode(self):
        result = self.run_menu(['2', 'a'*25, ' Bi\u0300nh ', '', '', '', '', '1'], skip_intro=True)
        self.assertEqual(result.farm.player_name, 'Bình')
        self.assertIn('24', self.output.getvalue())

    def test_save_failure_returns_to_title_without_launch(self):
        from farmgame.storage import SaveError
        original = self.old_save()
        with patch('farmgame.start_screen.save_game', side_effect=SaveError('disk full')):
            result = self.run_menu(['2', '', '', '', '', '', '1', '0'])
        self.assertIsNone(result.farm)
        self.assertIn('disk full', self.output.getvalue())
        self.assertEqual(self.path.read_bytes(), original)

    def test_interrupt_intro_keeps_committed_new_save(self):
        from farmgame.storage import load_game
        result = self.run_menu(['2', '', '', '', '', '', '1'])
        self.assertTrue(result.play_intro)
        self.assertFalse(load_game(self.path).intro_seen)

    def test_interrupted_new_intro_resumes_once_on_continue(self):
        from farmgame.storage import load_game
        self.run_menu(['2', '', '', '', '', '', '1'])
        self.assertFalse(load_game(self.path).intro_seen)
        result = self.run_menu(['1'])
        self.assertTrue(result.play_intro)
        self.assertFalse(result.farm.intro_seen)
        result.farm.intro_seen = True
        from farmgame.storage import save_game
        save_game(result.farm, self.path)
        original = self.path.read_bytes()
        self.run_menu(['1'])
        self.assertEqual(self.path.read_bytes(), original)

    def test_skip_pending_intro_marks_it_seen_without_showing_pages(self):
        from farmgame.storage import load_game
        self.run_menu(['2', '', '', '', '', '', '1'])
        result = self.run_menu(['1'], skip_intro=True)
        self.assertTrue(result.farm.intro_seen)
        self.assertTrue(load_game(self.path).intro_seen)

    def test_edit_preview_retains_previous_values(self):
        result = self.run_menu(['2', 'An', 'Vườn An', '2', '3', '2', '2',
                                '', '', '', '', '', '1'], skip_intro=True)
        self.assertEqual((result.farm.player_name, result.farm.avatar, result.farm.outfit),
                         ('An', '&', 'yellow'))

    def test_show_intro_is_read_only(self):
        from dataclasses import asdict
        from farmgame.identity import create_character
        from farmgame.start_screen import show_intro
        farm = create_character('An', 'Vườn')
        before = asdict(farm)
        with patch('builtins.input', side_effect=['', '', '']), redirect_stdout(io.StringIO()):
            self.assertTrue(show_intro(farm, graphical=False))
        self.assertEqual(asdict(farm), before)

    def test_backup_failure_does_not_attempt_to_replace_old_save(self):
        from farmgame.storage import SaveError
        original = self.old_save()
        with patch('farmgame.start_screen.backup_save', side_effect=SaveError('backup denied')):
            result = self.run_menu(['2', '', '', '', '', '', '1', '0'], skip_intro=True)
        self.assertIsNone(result.farm)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn('backup denied', self.output.getvalue())

    def test_cancel_final_confirmation_never_creates_save(self):
        self.assertIsNone(self.run_menu(['2', '', '', '', '', '', '0', '0']).farm)
        self.assertFalse(self.path.exists())

    def test_force_new_cancellation_returns_to_title(self):
        original = self.old_save()
        result = self.run_menu(['0', '1'], force_new=True)
        self.assertEqual(result.farm.name, 'Vườn cũ')
        self.assertEqual(self.path.read_bytes(), original)

    def test_curses_failure_restores_without_saving_placeholder(self):
        from farmgame.start_screen import run_startup
        original = self.old_save()
        with patch('farmgame.start_screen._with_ui', side_effect=RuntimeError('screen failed')):
            with unittest.mock.patch('sys.stderr', new_callable=io.StringIO) as errors:
                result = run_startup(self.path, graphical=True)
        self.assertIsNone(result.farm)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn('--text', errors.getvalue())
        self.assertEqual(result.exit_code, 1)


class CursesTitleMenuTests(unittest.TestCase):
    def test_main_menu_centers_logo_above_the_choices(self):
        from unittest.mock import Mock
        from tests.test_floating_ui import CellScreen, curses_namespace
        from farmgame.start_screen import CursesUI
        ui = CursesUI(color=False)
        ui._screen = CellScreen(24, 80)
        ui._curses = curses_namespace()
        ui._colors = {}
        ui.key = Mock(side_effect=['\n'])
        choice = ui.choose(
            'MOSSBROOK MEADOW · Một cuộc sống chậm giữa mây trời',
            [('1', 'Tiếp tục'), ('2', 'Hành trình mới'), ('0', 'Thoát')],
            body='Ngày 1 · Cấp 1')
        rendered = '\n'.join(ui._screen.lines())
        self.assertEqual(choice, '1')
        self.assertIn('M O S S B R O O K', rendered)
        self.assertIn('M E A D O W', rendered)
        self.assertIn('1. Tiếp tục', rendered)
        self.assertLess(rendered.index('M O S S B R O O K'),
                        rendered.index('1. Tiếp tục'))

    def test_animated_title_scene_stays_inside_the_terminal(self):
        from unittest.mock import Mock
        from tests.test_floating_ui import CellScreen, curses_namespace
        from farmgame.start_screen import CursesUI, _paint_title_scene
        for uni in (False, True):
            ui = CursesUI(color=False)
            ui._screen = CellScreen(24, 80)
            ui._curses = curses_namespace()
            ui._colors = {}
            ui.unicode_map = uni
            ui.key = Mock(side_effect=['\x1b'])
            choice = ui.choose(
                'MOSSBROOK MEADOW · Một cuộc sống chậm giữa mây trời',
                [('1', 'Tiếp tục'), ('0', 'Thoát')], body='Ngày 1 · Cấp 1')
            self.assertEqual(choice, '0')
            rendered = '\n'.join(ui._screen.lines())
            self.assertIn('M O S S B R O O K', rendered)
            self.assertIn('1. Tiếp tục', rendered)
            # A sweep of animation frames keeps every glyph in bounds.
            options = [('1', 'Tiếp tục'), ('0', 'Thoát')]
            for frame in range(0, 64, 7):
                ui._screen.erase()
                _paint_title_scene(ui, 24, 80, frame, options, 0, 'Ngày 1')


class CursesInputTests(unittest.TestCase):
    def ui(self):
        from types import SimpleNamespace
        from farmgame.start_screen import CursesUI
        ui = CursesUI()
        ui._curses = SimpleNamespace(KEY_ENTER=343, KEY_BACKSPACE=263,
                                    KEY_UP=259, KEY_DOWN=258, KEY_RESIZE=410,
                                    KEY_NPAGE=338, KEY_PPAGE=339)
        ui._screen = unittest.mock.Mock()
        ui._screen.getmaxyx.return_value = (12, 30)
        ui.paint = unittest.mock.Mock(return_value=(7, 0))
        return ui

    def test_unicode_editing_retains_combining_marks_and_survives_resize(self):
        ui = self.ui()
        ui.key = unittest.mock.Mock(side_effect=[*'Bi\u0300nhx', 410, '\x7f', '\n'])
        self.assertEqual(ui.name('Tên', 'Mây', 24), 'Bình')

    def test_invalid_name_is_reported_without_losing_typed_value(self):
        ui = self.ui()
        ui.key = unittest.mock.Mock(side_effect=[*('a'*25), '\n', '\x7f', '\n'])
        self.assertEqual(ui.name('Tên', 'Mây', 24), 'a'*24)
        self.assertTrue(any('24' in ' '.join(call.args[1]) for call in ui.paint.call_args_list))

    def test_escape_cancels_name(self):
        ui = self.ui()
        ui.key = unittest.mock.Mock(side_effect=[*'Bình', '\x1b'])
        self.assertIsNone(ui.name('Tên', 'Mây', 24))

    def test_narrow_preview_can_scroll_up_to_read_profile(self):
        ui = self.ui()
        ui._screen.getmaxyx.return_value = (8, 18)
        ui.paint = unittest.mock.Mock(return_value=(3, 0))
        ui.key = unittest.mock.Mock(side_effect=[339, '0'])
        ui.choose('Xem trước', [('1', 'Bắt đầu'), ('0', 'Hủy')], body='Dòng tên\n'*10)
        offsets = [call.args[4] for call in ui.paint.call_args_list]
        self.assertLess(offsets[1], offsets[0])
