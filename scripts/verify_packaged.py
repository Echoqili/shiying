"""Exercise the Windows distribution against localhost; never calls a cloud AI service."""
import json
import os
import subprocess
import sys
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_integration import IntegrationTests  # noqa: E402
from videodesk.core import new_task  # noqa: E402

exe = ROOT / 'dist' / 'Shiying' / 'Shiying.exe'
if not exe.is_file():
    raise SystemExit('Build Shiying.exe first.')

IntegrationTests.setUpClass()
try:
    fixture = IntegrationTests
    env = os.environ.copy()
    env['SHIYING_DATA_DIR'] = str(fixture.root / 'packaged-state')
    env['QT_QPA_PLATFORM'] = 'offscreen'
    screenshot = ROOT / 'docs' / 'packaged-preview.png'
    screenshot.unlink(missing_ok=True)
    result = subprocess.run([str(exe), '--smoke', '--screenshot', str(screenshot)], env=env,
                            capture_output=True, timeout=40)
    if result.returncode or not screenshot.is_file():
        raise RuntimeError(f'Packaged GUI failed: {result.returncode}, {result.stderr!r}')
    print('PASS packaged GUI startup and screenshot', flush=True)

    def worker(payload):
        result = subprocess.run([str(exe), '--worker'], input=json.dumps(payload).encode('utf-8'),
                                env=env, capture_output=True, timeout=60)
        lines = [json.loads(line) for line in result.stdout.decode('utf-8').splitlines() if line.strip()]
        if result.returncode or not lines or lines[-1]['event'] != 'done':
            raise RuntimeError(f'Packaged worker failed: {result.returncode}, {lines}, {result.stderr!r}')
        return lines

    worker({'action': 'test', 'settings': fixture.settings})
    print('PASS packaged custom AI connection and inherited pipe handles', flush=True)
    task = new_task(fixture.base + '/sample.mp4', fixture.settings)
    events = worker({'settings': fixture.settings, 'task': task})
    artifact = next(e['item'] for e in events if e['event'] == 'artifact')
    assert Path(artifact['file']).is_file()
    print('PASS packaged yt-dlp download and bundled FFmpeg', flush=True)
    transcript = fixture.root / 'packaged-transcript.txt'
    transcript.write_text('[00:00:01] 测试视频文字稿，包含需要总结的观点。', encoding='utf-8')
    task = new_task('', fixture.settings, action='notes', ai=True,
                    files=[{'file': str(transcript), 'title': '打包测试', 'source': '', 'subtitles': []}])
    events = worker({'settings': fixture.settings, 'task': task})
    note = next(e['note'] for e in events if e['event'] == 'note')
    assert Path(note['markdown']).is_file()
    print('PASS packaged transcript-to-summary workflow', flush=True)
    # Exercise Firefox sync against a synthetic profile, never a user's real browser.
    fake_appdata = fixture.root / 'fake-appdata'
    fake_firefox = fake_appdata / 'Mozilla' / 'Firefox'
    fake_profile = fake_firefox / 'Profiles' / 'test'
    fake_profile.mkdir(parents=True)
    (fake_firefox / 'profiles.ini').write_text('[InstallTEST]\nDefault=Profiles/test\n', encoding='utf-8')
    connection = sqlite3.connect(fake_profile / 'cookies.sqlite')
    try:
        connection.execute('CREATE TABLE moz_cookies(host,name,value,path,expiry,isSecure,isHttpOnly,originAttributes)')
        connection.execute('INSERT INTO moz_cookies VALUES(?,?,?,?,?,?,?,?)',
                           ('.youtube.com', 'SAPISID', 'synthetic-cookie-only', '/', time.time()+3600, 1, 1, ''))
        connection.commit()
    finally:
        connection.close()
    original_appdata = env.get('APPDATA')
    env['APPDATA'] = str(fake_appdata)
    try:
        worker({'action': 'firefox_sync', 'settings': fixture.settings})
    finally:
        if original_appdata is None:
            env.pop('APPDATA', None)
        else:
            env['APPDATA'] = original_appdata
    encrypted = (Path(env['SHIYING_DATA_DIR']) / 'youtube-session.json').read_text(encoding='utf-8')
    assert 'synthetic-cookie-only' not in encrypted
    print('PASS packaged Firefox sync and encrypted session with synthetic profile', flush=True)
    native_env = env | {'QT_QPA_PLATFORM': 'windows'}
    native_screenshot = ROOT / 'docs' / 'native-preview.png'
    native_screenshot.unlink(missing_ok=True)
    native = subprocess.run([str(exe), '--smoke', '--screenshot', str(native_screenshot)], env=native_env,
                            capture_output=True, timeout=40)
    if native.returncode or not native_screenshot.is_file():
        raise RuntimeError(f'Native Windows platform startup failed: {native.returncode}, {native.stderr!r}')
    print('PASS native Windows platform startup and rendering', flush=True)
finally:
    IntegrationTests.tearDownClass()
