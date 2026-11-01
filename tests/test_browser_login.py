import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from videodesk.browser_login import apply_session, load_session, save_session
from videodesk.engine import build_downloader


class BrowserSessionTests(unittest.TestCase):
    def test_youtube_session_is_separate_and_excludes_google_credentials(self):
        root = Path(__file__).parent / '.tmp'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder, patch.dict(os.environ, {'SHIYING_DATA_DIR': folder}):
            cookies = [dict(domain='.youtube.com', name='SAPISID', value='youtube-test-secret', expires=-1),
                       dict(domain='.google.com', name='SID', value='unrelated-google-secret', expires=-1)]
            self.assertTrue(save_session(cookies, 'Test Browser', 'youtube'))
            self.assertEqual(load_session(), {})
            session = load_session('youtube')
            self.assertEqual(len(session['cookies']), 1)
            raw = (Path(folder) / 'youtube-session.json').read_text()
            self.assertNotIn('youtube-test-secret', raw)
            with build_downloader({'quiet': True}, False) as ydl:
                apply_session(ydl, session, 'youtube')
                self.assertEqual([c.domain for c in ydl.cookiejar], ['.youtube.com'])

    def test_imported_cookie_file_is_not_overwritten_by_injected_session(self):
        root = Path(__file__).parent / '.tmp'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            path = Path(folder) / 'imported.txt'
            original = '# Netscape HTTP Cookie File\n'
            path.write_text(original, encoding='utf-8')
            with build_downloader({'quiet': True, 'cookiefile': str(path)}, False) as ydl:
                apply_session(ydl, {'cookies': [dict(domain='.douyin.com', name='sessionid', value='must-stay-encrypted', expires=-1)]})
            self.assertEqual(path.read_text(encoding='utf-8'), original)

    def test_encrypted_session_is_filtered_and_used_without_cookie_file(self):
        root = Path(__file__).parent / '.tmp'
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder, patch.dict(os.environ, {'SHIYING_DATA_DIR': folder}):
            cookies = [dict(domain='.douyin.com', name='sessionid', value='test-login-secret', path='/',
                            expires=-1, secure=True, httpOnly=True),
                       dict(domain='other.test', name='private', value='unrelated')]
            self.assertTrue(save_session(cookies, 'Test Browser'))
            encrypted = (Path(folder) / 'douyin-session.json').read_text()
            self.assertNotIn('test-login-secret', encrypted)
            session = load_session()
            self.assertEqual(len(session['cookies']), 1)
            with build_downloader({'quiet': True}, False) as ydl:
                apply_session(ydl, session)
                self.assertEqual(next(iter(ydl.cookiejar)).value, 'test-login-secret')

    def test_real_playwright_edge_cookie_capture(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                context = browser.new_context()
                context.add_cookies([{'name': 'test-session', 'value': 'local-test', 'url': 'https://www.douyin.com'}])
                # No navigation or account access: inspect only cookies injected into this new test context.
                self.assertEqual(context.cookies()[0]['value'], 'local-test')
            finally:
                browser.close()
