"""Download (when requested), verify and unpack official yt-dlp FFmpeg binaries."""
import argparse
import hashlib
import json
import shutil
import zipfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--download', action='store_true', help='Download the official archive and checksums first')
args = parser.parse_args()
filename = 'ffmpeg-master-latest-win64-gpl-shared.zip'
base_url = 'https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/'
archive = ROOT / '.cache' / 'ffmpeg.zip'
if args.download:
    archive.parent.mkdir(exist_ok=True)
    for remote, local in [(filename, archive), ('checksums.sha256', archive.parent / 'checksums.sha256')]:
        print('Downloading', remote, flush=True)
        with urllib.request.urlopen(base_url + remote, timeout=120) as source, local.open('wb') as output:
            shutil.copyfileobj(source, output)
checksums = (ROOT / '.cache' / 'checksums.sha256').read_text(encoding='utf-8')
expected = next(line.split()[0] for line in checksums.splitlines() if line.strip().endswith(filename))
with archive.open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
if digest != expected:
    raise RuntimeError(f'FFmpeg checksum mismatch: {digest}')
destination = ROOT / 'tools'
destination.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as zipped:
    for info in zipped.infolist():
        path = Path(info.filename)
        if info.is_dir():
            continue
        # Flatten runtime binaries, keeping FFmpeg license and build configuration alongside.
        if 'bin' in path.parts and path.suffix.lower() in ('.exe', '.dll'):
            if path.name.lower() == 'ffplay.exe':
                continue
            target = destination / path.name
        elif path.name.upper().startswith(('LICENSE', 'COPYING')) or path.name in ('README.txt', 'README.md', 'ffmpeg_config.txt'):
            target = destination / path.name
        else:
            continue
        with zipped.open(info) as source, target.open('wb') as output:
            shutil.copyfileobj(source, output)
(destination / 'provenance.json').write_text(json.dumps({
    'url': 'https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/' + filename,
    'archive_sha256': digest,
    'source_and_build_scripts': 'https://github.com/yt-dlp/FFmpeg-Builds',
}, indent=2), encoding='utf-8')
print('Verified FFmpeg SHA256:', digest)
print('Installed', len(list(destination.glob('*'))), 'runtime/license files')
