"""Create a portable ZIP and SHA256 sums after building the Windows application."""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from videodesk import __version__  # noqa: E402

VERSION = __version__
application = ROOT / 'dist' / 'Shiying'
output = ROOT / 'dist' / 'release'
output.mkdir(parents=True, exist_ok=True)
if not (application / 'Shiying.exe').is_file():
    raise SystemExit('Run build.ps1 before packaging.')
archive = output / f'Shiying-{VERSION}-windows-x64.zip'
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
    for path in sorted(application.rglob('*')):
        if path.is_file():
            zipped.write(path, path.relative_to(application.parent).as_posix())
with zipfile.ZipFile(archive) as zipped:
    if zipped.testzip() is not None:
        raise RuntimeError('ZIP integrity verification failed')
records = []
for path in sorted(output.iterdir()):
    if path.suffix.lower() in ('.zip', '.exe'):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        records.append(f'{digest}  {path.name}')
(output / 'SHA256SUMS.txt').write_text('\n'.join(records) + '\n', encoding='utf-8')
print('Created', archive.name, f'({archive.stat().st_size / 1024**2:.1f} MiB)')
print('ZIP integrity passed; SHA256SUMS.txt generated')
