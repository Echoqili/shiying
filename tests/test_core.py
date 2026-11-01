import tempfile
import unittest
import subprocess
from unittest.mock import patch
from pathlib import Path

from videodesk.core import Store, chunk_text, parse_urls, subtitle_text, download_options
from videodesk.core import find_js_runtime

TEST_TEMP = Path(__file__).parent / '.tmp'
TEST_TEMP.mkdir(exist_ok=True)


class CoreTests(unittest.TestCase):
    def test_bundled_youtube_runtime_overrides_old_system_node(self):
        with patch('videodesk.core.shutil.which', return_value='C:/old-node-20/node.exe'):
            runtime = find_js_runtime()
        version = subprocess.check_output([runtime, '--version'], text=True).strip()
        self.assertGreaterEqual(int(version.lstrip('v').split('.')[0]), 22)

    def test_douyin_share_caption_extracts_link(self):
        self.assertEqual(parse_urls('示例视频 https://v.douyin.com/test123/ 复制此链接，打开抖音'),
                         ['https://v.douyin.com/test123/'])

    def test_links_are_deduplicated_and_preserved(self):
        self.assertEqual(parse_urls('https://example.com/v?a=1&b=2\nhttps://example.com/v?a=1&b=2'), ['https://example.com/v?a=1&b=2'])

    def test_non_web_links_rejected(self):
        for value in ['file:///C:/test', '--exec=whoami', 'https://', 'hello']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_urls(value)

    def test_vtt_timestamp_and_repeated_cues(self):
        text = 'WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n你好 <b>世界</b>\n\n00:00:03.000 --> 00:00:04.000\n你好 世界\n'
        self.assertEqual(subtitle_text(text), '[00:00:01] 你好 世界')

    def test_chunks_bound_length_and_preserve_content(self):
        value = '一段文字。\n' * 100
        parts = chunk_text(value, 80)
        self.assertTrue(all(len(p) <= 80 for p in parts))
        self.assertEqual(''.join(parts).replace('\n', ''), value.replace('\n', ''))

    def test_store_recovers_interrupted_job(self):
        with tempfile.TemporaryDirectory(dir=TEST_TEMP) as root:
            store = Store(Path(root))
            store.save_tasks([{'id': 'a', 'status': 'running', 'title': 'video', 'progress': 34}])
            recovered = Store(Path(root)).load_tasks()
            self.assertEqual(recovered[0]['status'], 'interrupted')
            self.assertEqual(recovered[0]['progress'], 34)

    def test_formats_preserve_resolution_limit_on_fallback(self):
        options = download_options({'quality': '720', 'mode': 'video', 'output': '.'}, ffmpeg=True)
        self.assertIn('best[height<=720]', options['format'])
        self.assertFalse(options['noplaylist'] is False)

    def test_missing_ffmpeg_uses_combined_format(self):
        options = download_options({'quality': '1080', 'mode': 'video', 'output': '.'}, ffmpeg=False)
        self.assertNotIn('+', options['format'])


if __name__ == '__main__':
    unittest.main()
