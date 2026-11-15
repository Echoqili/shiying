import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QProcess
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QMessageBox

from videodesk.controller import Controller
from videodesk.core import Store, new_task
from videodesk.ui import MainWindow
import videodesk.ui as ui
import test_integration as fixture


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if not QFontDatabase.families():
            QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
        fixture.IntegrationTests.setUpClass()
        cls.fixture = fixture.IntegrationTests

    @classmethod
    def tearDownClass(cls):
        fixture.IntegrationTests.tearDownClass()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=self.fixture.root)
        self.store = Store(Path(self.temp.name))
        self.store.save_settings(self.fixture.settings)
        self.controller = Controller(self.store)

    def tearDown(self):
        self.controller.shutdown()
        self.app.processEvents()
        self.temp.cleanup()

    def until(self, predicate, seconds=25):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertTrue(predicate(), 'GUI operation timed out')

    def test_qprocess_download_and_queue_continues_after_failure(self):
        bad = new_task(self.fixture.base + '/not-found.mp4', self.fixture.settings)
        good = new_task(self.fixture.base + '/sample.mp4', self.fixture.settings)
        self.controller.add([bad, good])
        self.until(lambda: good['status'] == 'complete' and self.controller.job is None)
        self.assertEqual(bad['status'], 'failed')
        self.assertTrue(Path(good['files'][0]['file']).is_file())

    def test_cancel_kills_worker_then_runs_next_job(self):
        first = new_task(self.fixture.base + '/sample.mp4', self.fixture.settings)
        second = new_task(self.fixture.base + '/sample.mp4', self.fixture.settings)
        self.controller.add([first, second])
        self.until(lambda: self.controller.job is not None and self.controller.job.process.state() == QProcess.ProcessState.Running)
        self.controller.cancel(first)
        self.until(lambda: second['status'] == 'complete' and self.controller.job is None)
        self.assertEqual(first['status'], 'cancelled')
        self.assertEqual(second['status'], 'complete')

    def test_settings_page_switch_and_persistence(self):
        window = MainWindow(self.store)
        try:
            window.switch_page(2)
            page = window.settings_page
            page.provider.setCurrentIndex(1)
            page.fields['api_model'].setText('new-custom-model')
            page.fields['api_key'].setText('gui-test-secret')
            page.save()
            self.assertEqual(window.controller.settings['provider'], 'custom')
            self.assertEqual(self.store.load_settings()['api_model'], 'new-custom-model')
            self.assertEqual(self.store.load_settings()['api_key'], 'gui-test-secret')
        finally:
            window.close()

    def test_remove_records_preserves_files_and_keeps_recoverable_ai_work(self):
        downloaded = Path(self.temp.name) / 'keep.mp4'
        downloaded.write_bytes(b'video')
        complete = new_task('https://example.test/done', self.fixture.settings, status='complete',
                            files=[{'file': str(downloaded), 'title': 'done'}])
        failed = new_task('https://example.test/fail', self.fixture.settings, status='failed')
        partial = new_task('https://example.test/partial', self.fixture.settings, status='partial', ai=True)
        self.controller.tasks = [complete, failed, partial]
        self.controller.persist()
        self.assertTrue(self.controller.remove(complete))
        self.assertTrue(downloaded.is_file())
        self.assertFalse(self.controller.remove(new_task('', self.fixture.settings, status='queued')))
        self.assertEqual(self.controller.clear_finished(), 1)
        self.assertEqual([task['id'] for task in self.controller.tasks], [partial['id']])
        self.assertEqual([task['id'] for task in self.store.load_tasks()], [partial['id']])
        self.assertTrue(self.controller.remove(partial))
        self.assertEqual(self.store.load_tasks(), [])

    def test_confirm_removal_builds_a_real_qt_dialog(self):
        window = MainWindow(self.store)
        try:
            def choose(role):
                def fake_exec(box):
                    box._chosen = next(b for b in box.buttons() if box.buttonRole(b) == role)
                    return 0
                return fake_exec

            def clicked(box):
                return getattr(box, '_chosen', None)

            with patch.object(QMessageBox, 'exec', choose(QMessageBox.ButtonRole.DestructiveRole)), \
                 patch.object(QMessageBox, 'clickedButton', clicked):
                self.assertTrue(ui.confirm_removal(window, '删除下载记录', '确定删除吗？'))
            with patch.object(QMessageBox, 'exec', choose(QMessageBox.ButtonRole.RejectRole)), \
                 patch.object(QMessageBox, 'clickedButton', clicked):
                self.assertFalse(ui.confirm_removal(window, '删除下载记录', '确定删除吗？'))
        finally:
            window.close()

    def test_delete_task_ui_respects_cancel_and_keeps_files(self):
        window = MainWindow(self.store)
        try:
            downloaded = Path(self.temp.name) / 'keep.mp4'
            downloaded.write_bytes(b'video')
            task = new_task('https://example.test/done', self.fixture.settings, status='complete',
                            files=[{'file': str(downloaded), 'title': 'done'}])
            window.controller.tasks = [task]
            window.controller.persist()
            window.rebuild()
            with patch('videodesk.ui.confirm_removal', return_value=False) as confirm:
                window.task_action(task['id'], 'delete')
                self.assertEqual(confirm.call_count, 1)
            self.assertEqual(len(window.controller.tasks), 1)
            self.assertEqual(len(window.cards), 1)
            with patch('videodesk.ui.confirm_removal', return_value=True):
                window.task_action(task['id'], 'delete')
            self.assertEqual(window.controller.tasks, [])
            self.assertEqual(window.controller.store.load_tasks(), [])
            self.assertEqual(window.cards, {})
            self.assertTrue(downloaded.is_file())
            self.assertIn('已删除', window.footer.text())
        finally:
            window.close()

    def test_clear_finished_ui_keeps_ai_partial_but_allows_single_delete(self):
        window = MainWindow(self.store)
        try:
            complete = new_task('https://example.test/done', self.fixture.settings, status='complete')
            failed = new_task('https://example.test/fail', self.fixture.settings, status='failed')
            partial = new_task('https://example.test/partial', self.fixture.settings, status='partial', ai=True)
            window.controller.tasks = [complete, failed, partial]
            window.controller.persist()
            window.rebuild()
            self.assertFalse(window.cards[partial['id']].delete_button.isHidden())
            with patch('videodesk.ui.confirm_removal', return_value=True) as confirm:
                window.clear_finished()
                self.assertEqual(confirm.call_args.kwargs.get('confirm'), '清除记录')
            self.assertEqual([task['id'] for task in window.controller.tasks], [partial['id']])
            self.assertEqual(list(window.cards), [partial['id']])
            with patch('videodesk.ui.confirm_removal', return_value=True):
                window.task_action(partial['id'], 'delete')
            self.assertEqual(window.controller.tasks, [])
            self.assertEqual(window.controller.store.load_tasks(), [])
        finally:
            window.close()


if __name__ == '__main__':
    unittest.main()
