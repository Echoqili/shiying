import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QProcess
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from videodesk.controller import Controller
from videodesk.core import Store, new_task
from videodesk.ui import MainWindow
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


if __name__ == '__main__':
    unittest.main()
