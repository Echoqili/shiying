import hashlib
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from videodesk.browser_login import load_session
from videodesk.firefox_sync import default_profile, read_youtube_cookies, sync_youtube


class FirefoxSyncTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / '.tmp'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        self.profile = self.root / 'Profiles' / 'normal'
        self.profile.mkdir(parents=True)
        self.database = self.profile / 'cookies.sqlite'
        with sqlite3.connect(self.database) as connection:
            connection.execute('CREATE TABLE moz_cookies(host,name,value,path,expiry,isSecure,isHttpOnly,originAttributes)')
            connection.executemany('INSERT INTO moz_cookies VALUES(?,?,?,?,?,?,?,?)', [
                ('.youtube.com', 'SAPISID', 'only-youtube-secret', '/', time.time()+3600, 1, 1, ''),
                ('.google.com', 'SID', 'must-not-read', '/', time.time()+3600, 1, 1, ''),
                ('evil-youtube.com', 'SID', 'must-not-read', '/', time.time()+3600, 1, 1, ''),
                ('.youtube.com', 'old', 'expired', '/', time.time()-10, 1, 1, ''),
                ('.youtube.com', 'other-account', 'different-container', '/', time.time()+3600, 1, 1, '^userContextId=2'),
            ])
        connection.close()
        (self.root / 'profiles.ini').write_text('[InstallABC]\nDefault=Profiles/normal\n[Profile0]\nPath=Profiles/wrong\nDefault=1\nIsRelative=1\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_installed_firefox_default_profile_has_priority(self):
        self.assertEqual(default_profile(self.root), self.profile.resolve())

    def test_missing_default_never_falls_back_to_another_account(self):
        (self.root / 'profiles.ini').write_text(
            '[InstallABC]\nDefault=Profiles/new-default\n[Profile0]\nPath=Profiles/normal\nIsRelative=1\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '不会改读其他账号'):
            default_profile(self.root)

    def test_readonly_youtube_scope_default_container_and_expiration(self):
        before = hashlib.sha256(self.database.read_bytes()).digest()
        cookies = read_youtube_cookies(self.profile)
        self.assertEqual([c['name'] for c in cookies], ['SAPISID'])
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).digest())

    def test_sync_encrypts_only_scoped_session(self):
        with patch('videodesk.firefox_sync.default_profile', return_value=self.profile), \
             patch('videodesk.firefox_sync.firefox_executable', return_value=''), \
             patch.dict(os.environ, {'SHIYING_DATA_DIR': str(self.root / 'state')}):
            events = []
            sync_youtube(lambda event, **data: events.append(event))
            self.assertEqual(events, ['done'])
            self.assertEqual(len(load_session('youtube')['cookies']), 1)
            raw = (self.root / 'state' / 'youtube-session.json').read_text()
            self.assertNotIn('only-youtube-secret', raw)
            self.assertNotIn('must-not-read', raw)
