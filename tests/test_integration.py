import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from videodesk.ai import qoder_options, transcribe
from videodesk.core import DEFAULTS, Store, find_tools, new_task
from videodesk.engine import build_downloader, make_notes, run_task

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / 'tests' / '.tmp'
TEMP.mkdir(exist_ok=True)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, request, address, server):
        super().__init__(request, address, server, directory=str(server.root))

    def log_message(self, *args):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.server.requests.append((self.path, raw))
        if self.path.endswith('/chat/completions'):
            self.server.last_chat = json.loads(raw)
            response = {'choices': [{'message': {'content': '## 摘要\n\n测试视频讲解了三个观点。\n\n## 时间线\n\n- [00:00:01] 第一个观点。'}}]}
        elif self.path.endswith('/audio/transcriptions'):
            self.server.asr_calls = getattr(self.server, 'asr_calls', 0) + 1
            if self.server.asr_calls == getattr(self.server, 'fail_asr_call', -1):
                self.send_error(503, 'Temporary ASR failure')
                return
            response = {'text': '这是一段测试音频。', 'segments': [{'start': 0.1, 'end': 1.2, 'text': '这是一段测试音频。'}]}
        else:
            self.send_error(404)
            return
        data = json.dumps(response, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=TEMP)
        cls.root = Path(cls.temp.name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.root = cls.root
        cls.server.requests = []
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.settings = DEFAULTS | {'provider': 'custom', 'api_base': cls.base + '/v1', 'api_model': 'test-model',
                                   'asr_base': cls.base + '/v1', 'asr_model': 'test-asr', 'output': str(cls.root / 'output')}
        ffmpeg, _ = find_tools(cls.settings)
        subprocess.run([ffmpeg, '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=teal:s=160x90:r=10', '-f', 'lavfi', '-i', 'sine=frequency=440',
                        '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(cls.root / 'sample.mp4')],
                       check=True, capture_output=True)
        cls.env = patch.dict(os.environ, {'NO_PROXY': '127.0.0.1,localhost', 'SHIYING_DATA_DIR': str(cls.root / 'data')})
        cls.env.start()

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def test_real_ytdlp_downloads_local_video(self):
        events = []
        task = new_task(self.base + '/sample.mp4', self.settings)
        run_task(task, self.settings, lambda event, **data: events.append({'event': event, **data}))
        artifact = next(e['item'] for e in events if e['event'] == 'artifact')
        self.assertTrue(Path(artifact['file']).is_file())
        self.assertEqual(hashlib.sha256(Path(artifact['file']).read_bytes()).digest(),
                         hashlib.sha256((self.root / 'sample.mp4').read_bytes()).digest())
        self.assertEqual(events[-1]['event'], 'done')

    def test_custom_api_and_subtitle_notes(self):
        transcript = self.root / 'input.vtt'
        transcript.write_text('WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n测试视频的第一个观点\n', encoding='utf-8')
        item = {'file': str(transcript), 'title': '字幕测试', 'source': '', 'subtitles': []}
        task = new_task('', self.settings)
        result = make_notes(item, task, self.settings, lambda *a, **k: None)
        self.assertIn('三个观点', Path(result['markdown']).read_text(encoding='utf-8'))
        self.assertIn('[00:00:01]', Path(result['transcript']).read_text(encoding='utf-8'))
        self.assertEqual(self.server.last_chat['model'], 'test-model')

    def test_real_ffmpeg_audio_to_transcription_api(self):
        with tempfile.TemporaryDirectory(dir=self.root) as work:
            transcript, srt = transcribe(self.root / 'sample.mp4', self.settings, lambda *a, **k: None, Path(work))
        self.assertIn('测试音频', transcript)
        self.assertIn('00:00:00,100 --> 00:00:01,200', srt)
        self.assertTrue(any(path.endswith('/audio/transcriptions') and b'audio/mpeg' in raw for path, raw in self.server.requests))

    def test_ai_failure_preserves_downloaded_file(self):
        task = new_task(self.base + '/sample.mp4', self.settings, ai=True)
        settings = self.settings | {'asr_base': ''}
        events = []
        with self.assertRaisesRegex(RuntimeError, '文件已保留'):
            run_task(task, settings, lambda event, **data: events.append({'event': event, **data}))
        artifact = next(e['item'] for e in events if e['event'] == 'artifact')
        self.assertTrue(Path(artifact['file']).is_file())

    def test_qoder_official_sdk_is_configured_without_tools(self):
        options = qoder_options(DEFAULTS, str(self.root))
        self.assertEqual(options.tools, [])
        self.assertEqual(options.skills, [])
        self.assertEqual(options.setting_sources, [])
        self.assertIn('Bash', options.disallowed_tools)
        self.assertIsNotNone(options.auth)

    def test_keys_are_encrypted_and_roundtrip(self):
        store = Store(self.root / 'secure')
        settings = DEFAULTS | {'api_key': 'test-only-secret-key', 'qoder_pat': 'test-only-pat'}
        store.save_settings(settings)
        raw = (store.root / 'settings.json').read_text(encoding='utf-8')
        self.assertNotIn('test-only-secret-key', raw)
        self.assertNotIn('test-only-pat', raw)
        self.assertEqual(store.load_settings()['api_key'], settings['api_key'])

    def test_worker_protocol_returns_parseable_events(self):
        payload = {'action': 'test', 'settings': self.settings}
        result = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--worker'], input=json.dumps(payload).encode(),
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        events = [json.loads(line) for line in result.stdout.decode('utf-8').splitlines()]
        self.assertEqual(events[-1]['event'], 'done')

    def test_playlist_is_rejected_before_entry_download_when_not_enabled(self):
        with build_downloader({'quiet': True}, allow_playlist=False) as ydl:
            with self.assertRaisesRegex(ValueError, '播放列表'):
                ydl.process_ie_result({'_type': 'playlist', 'id': 'p', 'title': 'p', 'entries': [
                    {'_type': 'url', 'url': self.base + '/sample.mp4'}]}, download=True)

    def test_optional_subtitle_error_still_downloads_media(self):
        from videodesk.core import download_options
        options = download_options(new_task('', self.settings, subtitles=True), ffmpeg=True)
        options['ffmpeg_location'] = str(Path(find_tools(self.settings)[0]).parent)
        with build_downloader(options, allow_playlist=False) as ydl:
            info = ydl.process_ie_result({
                'id': 'optional-subs', 'title': 'optional subtitles', 'url': self.base + '/sample.mp4', 'ext': 'mp4',
                'subtitles': {'en': [{'ext': 'vtt', 'url': self.base + '/missing-subtitles.vtt'}]},
            }, download=True)
        self.assertTrue(Path(ydl.prepare_filename(info)).is_file())

    def test_note_identity_preserves_distinct_long_title_videos(self):
        prefix = 'same-title-' * 12
        task = new_task('', self.settings)
        first = self.root / (prefix + '[first].txt')
        second = self.root / (prefix + '[second].txt')
        first.write_text('first unique transcript', encoding='utf-8')
        second.write_text('second unique transcript', encoding='utf-8')
        notes = []
        for path in (first, second):
            notes.append(make_notes({'file': str(path), 'title': path.stem}, task, self.settings, lambda *a, **k: None))
        self.assertNotEqual(notes[0]['markdown'], notes[1]['markdown'])
        self.assertEqual(Path(notes[1]['transcript']).read_text(encoding='utf-8'), 'second unique transcript')

    def test_transcription_retries_only_unfinished_chunks(self):
        def fake_segment(command, **kwargs):
            pattern = Path(command[-1])
            pattern.with_name('part-00000.mp3').write_bytes(b'first audio')
            pattern.with_name('part-00001.mp3').write_bytes(b'second audio')
            return subprocess.CompletedProcess(command, 0, b'', b'')
        cache = self.root / 'asr-checkpoint.json'
        self.server.asr_calls = 0
        self.server.fail_asr_call = 2
        with tempfile.TemporaryDirectory(dir=self.root) as work, patch('videodesk.ai.subprocess.run', side_effect=fake_segment):
            with self.assertRaisesRegex(RuntimeError, '503'):
                transcribe(self.root / 'sample.mp4', self.settings, lambda *a, **k: None, Path(work), cache)
            self.server.fail_asr_call = -1
            text, _ = transcribe(self.root / 'sample.mp4', self.settings, lambda *a, **k: None, Path(work), cache)
        self.assertEqual(self.server.asr_calls, 3)
        self.assertIn('[00:10:00]', text)

    def test_real_audio_download_captures_final_mp3(self):
        events = []
        task = new_task(self.base + '/sample.mp4', self.settings, mode='audio')
        run_task(task, self.settings, lambda event, **data: events.append({'event': event, **data}))
        artifact = next(e['item'] for e in events if e['event'] == 'artifact')
        self.assertEqual(Path(artifact['file']).suffix, '.mp3')
        self.assertTrue(Path(artifact['file']).is_file())


if __name__ == '__main__':
    unittest.main()
