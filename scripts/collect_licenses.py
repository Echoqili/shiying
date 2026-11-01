"""Copy installed dependency license texts into the desktop distribution."""
from importlib import metadata
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
output = root / 'licenses'
output.mkdir(exist_ok=True)
packages = ['yt-dlp', 'yt-dlp-ejs', 'qoder-agent-sdk', 'requests', 'urllib3', 'certifi', 'charset-normalizer',
            'idna', 'PySide6', 'shiboken6', 'anyio', 'mcp', 'httpx', 'httpcore', 'pydantic', 'pycryptodomex',
            'mutagen', 'brotli', 'websockets', 'playwright', 'pyee', 'greenlet']
index = []
for name in packages:
    try:
        distribution = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    index.append(f'{name} {distribution.version}')
    for file in distribution.files or []:
        if any(token in file.name.lower() for token in ('license', 'copying', 'notice')):
            original = Path(distribution.locate_file(file))
            if original.is_file() and original.stat().st_size < 2000000:
                target = output / name / str(file).replace('..', '_')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
(output / 'DEPENDENCIES.txt').write_text('\n'.join(index) + '\n', encoding='utf-8')
print('Collected dependency notices:', len(index))
