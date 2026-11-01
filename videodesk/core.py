from __future__ import annotations

import base64
import ctypes
import html
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


APP_NAME = '拾影'
ACTIVE = {'running', 'downloading', 'analyzing', 'transcribing', 'summarizing', 'processing'}
SECRET_FIELDS = ('api_key', 'asr_key', 'qoder_pat')
DEFAULTS = {
    'theme': 'cream',
    'output': str(Path.home() / 'Downloads' / '拾影'),
    'provider': 'qoder', 'qoder_cli': '', 'qoder_model': '', 'qoder_pat': '',
    'api_base': '', 'api_model': '', 'api_key': '',
    'asr_base': '', 'asr_model': 'whisper-1', 'asr_key': '',
    'ffmpeg_dir': '', 'proxy': '', 'cookie_file': '', 'language': 'zh',
}


def now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def app_root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def data_root() -> Path:
    return Path(os.environ.get('SHIYING_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Shiying')


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return fallback


class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(value: str, decrypt=False) -> str:
    if not value:
        return ''
    if os.name != 'nt':
        raise RuntimeError('此版本的密钥持久化需要 Windows 系统保护。')
    source = base64.b64decode(value) if decrypt else value.encode('utf-8')
    buffer = ctypes.create_string_buffer(source)
    input_blob = Blob(len(source), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    method = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not method(ctypes.byref(input_blob), None, None, None, None, 1, ctypes.byref(output)):
        raise ctypes.WinError()
    try:
        result = ctypes.string_at(output.data, output.size)
        return result.decode('utf-8') if decrypt else base64.b64encode(result).decode('ascii')
    finally:
        ctypes.windll.kernel32.LocalFree(output.data)


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or data_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.secret_error = ''

    def load_settings(self) -> dict:
        saved = read_json(self.root / 'settings.json', {})
        if not isinstance(saved, dict):
            saved = {}
        settings = DEFAULTS | {k: v for k, v in saved.items() if k in DEFAULTS and isinstance(v, str)}
        for key in SECRET_FIELDS:
            try:
                settings[key] = protect(saved.get('_' + key, ''), decrypt=True)
            except (OSError, ValueError, RuntimeError):
                settings[key] = ''
                self.secret_error = '已保存的密钥无法解密，请重新填写并保存。'
        return settings

    def save_settings(self, settings: dict):
        saved = {k: v for k, v in settings.items() if k in DEFAULTS and k not in SECRET_FIELDS}
        for key in SECRET_FIELDS:
            saved['_' + key] = protect(settings.get(key, ''))
        atomic_json(self.root / 'settings.json', saved)

    def load_tasks(self) -> list:
        tasks = read_json(self.root / 'tasks.json', [])
        if not isinstance(tasks, list):
            return []
        tasks = [t for t in tasks if isinstance(t, dict) and t.get('id')]
        for task in tasks:
            if task.get('status') in ACTIVE or task.get('status') == 'queued':
                task.update(status='interrupted', detail='上次退出时任务中断，可手动重试')
        return tasks

    def save_tasks(self, tasks: list):
        atomic_json(self.root / 'tasks.json', tasks)


def parse_urls(text: str) -> list[str]:
    # Mobile share text often contains a caption before/after the actual link.
    if not text.strip().startswith(('http://', 'https://')):
        found = re.findall(r'https?://[^\s<>"\']+', text)
        if found:
            text = '\n'.join(value.rstrip('，。；！、）】') for value in found)
    urls = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            parts = urlsplit(value)
            valid = parts.scheme in ('http', 'https') and bool(parts.hostname) and not re.search(r'\s', value)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError(f'请输入完整的 http/https 链接，每行一个：{value[:100]}')
        if value not in urls:
            urls.append(value)
    if not urls:
        raise ValueError('先粘贴一个视频链接。')
    return urls


def endpoint(base: str, route: str) -> str:
    base = base.strip().rstrip('/')
    parse_urls(base)
    return base if base.endswith('/' + route) else base + '/' + route


def chunk_text(text: str, limit=11000) -> list[str]:
    if limit < 1:
        raise ValueError('分段大小必须大于零')
    chunks = []
    while text:
        end = min(limit, len(text))
        if end < len(text):
            split = text.rfind('\n', end // 2, end)
            if split != -1:
                end = split + 1
        chunks.append(text[:end])
        text = text[end:]
    return chunks


def timecode(seconds: float, millis=False) -> str:
    total = max(0, round(seconds * 1000))
    hours, remainder = divmod(total, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    sec, ms = divmod(remainder, 1000)
    return f'{hours:02}:{minutes:02}:{sec:02}' + (f',{ms:03}' if millis else '')


def subtitle_text(value: str) -> str:
    lines = []
    stamp = ''
    previous = ''
    for raw in value.replace('\r', '').splitlines():
        line = raw.strip()
        if '-->' in line:
            match = re.match(r'(?:(\d{2,}):)?(\d{2}):(\d{2})[.,]\d+', line)
            if match:
                stamp = f'{int(match[1] or 0):02}:{match[2]}:{match[3]}'
            continue
        if not line or line.isdigit() or line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE', 'STYLE', 'REGION')):
            continue
        clean = html.unescape(re.sub(r'<[^>]+>', '', line)).strip()
        if clean and clean != previous:
            lines.append((f'[{stamp}] ' if stamp else '') + clean)
            previous = clean
    return '\n'.join(lines)


def find_tools(settings: dict) -> tuple[str, str]:
    candidates = []
    if settings.get('ffmpeg_dir'):
        candidates.append(Path(settings['ffmpeg_dir']))
    candidates += [app_root() / 'tools', Path(sys.executable).parent / 'tools']
    ffmpeg = ffprobe = ''
    for directory in candidates:
        if directory.is_file():
            directory = directory.parent
        for name in ('ffmpeg', 'ffprobe'):
            path = directory / (name + ('.exe' if os.name == 'nt' else ''))
            if path.is_file():
                if name == 'ffmpeg':
                    ffmpeg = ffmpeg or str(path)
                else:
                    ffprobe = ffprobe or str(path)
    return ffmpeg or shutil.which('ffmpeg') or '', ffprobe or shutil.which('ffprobe') or ''


def find_js_runtime() -> str:
    # Prefer the compatible Node already bundled with Playwright, rather than an
    # unrelated older Node on PATH (YouTube's current solver requires Node 22+).
    bundled = app_root() / 'playwright' / 'driver' / 'node.exe'
    if bundled.is_file():
        return str(bundled)
    import importlib.util
    spec = importlib.util.find_spec('playwright')
    if spec and spec.origin:
        candidate = Path(spec.origin).parent / 'driver' / ('node.exe' if os.name == 'nt' else 'node')
        if candidate.is_file():
            return str(candidate)
    return shutil.which('node') or ''


def download_options(task: dict, ffmpeg: bool) -> dict:
    height = task.get('quality', 'best')
    bound = f'[height<={int(height)}]' if height != 'best' else ''
    options = {
        'format': f'bestvideo{bound}+bestaudio/best{bound}' if ffmpeg else f'best{bound}',
        'outtmpl': str(Path(task['output']) / '%(title).160B [%(id)s].%(ext)s'),
        'windowsfilenames': True, 'noplaylist': not task.get('playlist', False),
        'continuedl': True, 'overwrites': False, 'socket_timeout': 25, 'retries': 3,
        'fragment_retries': 3, 'quiet': True, 'noprogress': True,
        'writesubtitles': bool(task.get('subtitles') or task.get('ai')),
        'writeautomaticsub': bool(task.get('subtitles') or task.get('ai')),
        'subtitleslangs': ['zh-Hans', 'zh-Hant', 'zh', 'en'],
        'subtitlesformat': 'vtt/srt/best', 'merge_output_format': 'mp4',
        'format_sort': ['res', 'vcodec:h264', 'acodec:aac'],
    }
    if task.get('mode') == 'audio':
        if not ffmpeg:
            raise ValueError('提取 MP3 需要 FFmpeg，请在设置中配置工具目录。')
        options['format'] = 'bestaudio/best'
        options['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    return options


def redact(text: str, settings: dict) -> str:
    for key in SECRET_FIELDS:
        if settings.get(key):
            text = text.replace(settings[key], '[密钥已隐藏]')
    text = re.sub(r'(?i)(authorization[\s:]+bearer\s+)\S+', r'\1[已隐藏]', text)
    return text[:2400]


def new_task(url: str, settings: dict, **options) -> dict:
    return dict(id=uuid.uuid4().hex, url=url, title=url, created=now(), status='queued',
                progress=0, detail='等待下载', output=settings['output'], mode='video',
                quality='best', ai=False, playlist=False, subtitles=False, files=[], notes=[]) | options
