import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from videodesk.core import find_tools
from videodesk.media import media_info, windows_compatible


class MediaCompatibilityTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent / '.tmp'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.temp.name)
        self.ffmpeg, _ = find_tools({})

    def tearDown(self):
        self.temp.cleanup()

    def generate(self, name, video, audio):
        output = self.root / name
        command = [self.ffmpeg, '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=teal:s=64x64:r=5',
                   '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '0.6', '-c:v', video, '-pix_fmt', 'yuv420p']
        if video == 'libaom-av1':
            command += ['-cpu-used', '8']
        command += ['-c:a', audio, str(output)]
        subprocess.run(command, check=True, capture_output=True)
        return output

    def test_av1_opus_becomes_h264_aac_mp4_and_preserves_original(self):
        original = self.generate('source.mkv', 'libaom-av1', 'libopus')
        digest = hashlib.sha256(original.read_bytes()).digest()
        converted = Path(windows_compatible(original, {}, lambda *a, **k: None))
        self.assertEqual(converted.suffix, '.mp4')
        info = media_info(converted, {})
        self.assertEqual([s['codec_name'] for s in info['streams']], ['h264', 'aac'])
        self.assertEqual(info['streams'][0]['pix_fmt'], 'yuv420p')
        self.assertEqual(digest, hashlib.sha256(original.read_bytes()).digest())
        result = subprocess.run([self.ffmpeg, '-v', 'error', '-i', str(converted), '-f', 'null', 'NUL'], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_compatible_file_is_reused_without_transcode(self):
        original = self.generate('source.mp4', 'libx264', 'aac')
        digest = hashlib.sha256(original.read_bytes()).digest()
        self.assertEqual(windows_compatible(original, {}, lambda *a, **k: None), str(original))
        self.assertEqual(digest, hashlib.sha256(original.read_bytes()).digest())

    def test_existing_output_is_not_overwritten(self):
        original = self.generate('source.mkv', 'libx264', 'aac')
        existing = self.root / 'source [兼容].mp4'
        existing.write_bytes(b'user-owned-file')
        result = windows_compatible(original, {}, lambda *a, **k: None)
        self.assertNotEqual(result, str(existing))
        self.assertEqual(existing.read_bytes(), b'user-owned-file')
