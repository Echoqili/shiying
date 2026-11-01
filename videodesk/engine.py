from __future__ import annotations

import hashlib
import tempfile
import time
from pathlib import Path

from .ai import complete, summarize, transcribe
from .core import atomic_json, download_options, find_tools, find_js_runtime, now, redact, subtitle_text


class Logger:
    def __init__(self, emit, settings):
        self.emit, self.settings = emit, settings

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        self.emit('log', detail=redact(str(message), self.settings))

    def error(self, message):
        self.emit('log', detail=redact(str(message), self.settings))


def build_downloader(options, allow_playlist):
    import yt_dlp

    class DesktopDownloader(yt_dlp.YoutubeDL):
        def save_cookies(self):
            # Imported cookies are read-only. Never export the injected encrypted
            # browser session to a configured plaintext Netscape file on close.
            pass

        def process_ie_result(self, ie_result, download=True, extra_info=None):
            # noplaylist alone only handles URLs referring to both a video and playlist.
            if ie_result.get('_type') in ('playlist', 'multi_video') and not allow_playlist:
                raise ValueError('此链接返回播放列表。需要批量下载时，请勾选“整个播放列表”后重试。')
            return super().process_ie_result(ie_result, download=download, extra_info=extra_info or {})

        def _write_subtitles(self, info_dict, filename):
            # Subtitle failures must never hide media errors or prevent the ASR fallback.
            original = self.params.get('ignoreerrors', False)
            self.params['ignoreerrors'] = True
            try:
                result = super()._write_subtitles(info_dict, filename)
                if result is None:
                    self.report_warning('字幕保存失败，将继续下载视频；AI 可使用语音转写。')
                return result or []
            finally:
                self.params['ignoreerrors'] = original

    return DesktopDownloader(options)


def download(task: dict, settings: dict, emit) -> list[dict]:
    from yt_dlp.postprocessor.common import PostProcessor

    Path(task['output']).mkdir(parents=True, exist_ok=True)
    ffmpeg, ffprobe = find_tools(settings)
    options = download_options(task, bool(ffmpeg and ffprobe))
    from urllib.parse import urlsplit
    from .browser_login import load_session, apply_session
    hostname = urlsplit(task['url']).hostname or ''
    douyin = hostname == 'douyin.com' or hostname.endswith('.douyin.com')
    youtube = hostname in ('youtube.com', 'youtu.be') or hostname.endswith('.youtube.com')
    session_site = 'douyin' if douyin else 'youtube'
    session = load_session(session_site) if douyin or youtube else {}
    if session.get('user_agent'):
        options['http_headers'] = {'User-Agent': session['user_agent']}
    options['logger'] = Logger(emit, settings)
    if ffmpeg:
        options['ffmpeg_location'] = str(Path(ffmpeg).parent)
    if settings.get('proxy'):
        options['proxy'] = settings['proxy']
    if settings.get('cookie_file'):
        options['cookiefile'] = settings['cookie_file']
    # Explicitly enable Node when available; yt-dlp only enables Deno by default.
    node = find_js_runtime()
    if node:
        options['js_runtimes'] = {'node': {'path': node}, 'deno': {}}
    last = [0.0]

    def progress(data):
        if data.get('status') == 'downloading':
            clock = time.monotonic()
            if clock - last[0] < .18:
                return
            last[0] = clock
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            downloaded = data.get('downloaded_bytes', 0)
            fraction = downloaded / total if total else 0
            speed = data.get('speed') or 0
            eta = data.get('eta')
            detail = f'{downloaded / 1048576:.1f}' + (f' / {total / 1048576:.1f}' if total else '') + ' MB'
            if speed:
                detail += f' · {speed / 1048576:.1f} MB/s'
            if eta is not None:
                detail += f' · 剩余 {int(eta)} 秒'
            emit('progress', status='downloading', progress=int(min(fraction, 1) * (53 if task.get('ai') else 94)),
                 title=data.get('info_dict', {}).get('title') or task['title'], detail=detail)
        elif data.get('status') == 'finished':
            emit('progress', status='processing', progress=54 if task.get('ai') else 96, detail='下载完成，正在合并或整理文件')

    def postprocess(data):
        if data.get('status') == 'started':
            emit('progress', status='processing', detail='正在处理音视频文件')

    options['progress_hooks'] = [progress]
    options['postprocessor_hooks'] = [postprocess]
    records = []

    class Capture(PostProcessor):
        def run(self, info):
            filename = info.get('filepath') or self._downloader.prepare_filename(info)
            if task.get('mode') != 'audio' and ffmpeg and ffprobe:
                from .media import windows_compatible
                filename = windows_compatible(filename, settings, emit)
            subtitles = [value.get('filepath') for value in (info.get('requested_subtitles') or {}).values() if value.get('filepath')]
            item = {'file': filename, 'title': info.get('title', Path(filename).stem),
                    'source': info.get('webpage_url') or task['url'], 'subtitles': subtitles}
            records.append(item)
            emit('artifact', item=item)
            return [], info

    emit('progress', status='analyzing', progress=2, detail='正在解析视频链接')
    with build_downloader(options, allow_playlist=task.get('playlist', False)) as ydl:
        if session:
            apply_session(ydl, session, session_site)
        ydl.add_post_processor(Capture(), when='after_move')
        try:
            result = ydl.extract_info(task['url'], download=True)
        except Exception:
            if not douyin or not session:
                raise
            import asyncio
            from .browser_login import resolve_video
            emit('log', detail='抖音常规解析失败，改用已登录浏览器获取播放地址。')
            info = asyncio.run(resolve_video(task['url'], session, emit))
            result = ydl.process_ie_result(info, download=True)
    if not result or not records:
        raise RuntimeError('没有得到可下载的视频，请检查链接、站点支持情况或登录要求。')
    return records


def make_notes(item: dict, task: dict, settings: dict, emit) -> dict:
    emit('progress', status='transcribing', progress=56, detail='正在读取字幕或准备语音转写')
    path = Path(item['file'])
    directory = Path(task['output']) / 'AI 笔记' / task['id'][:8]
    directory.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(str(path.resolve()).encode('utf-8')).hexdigest()[:12]
    stem = path.stem[:64] + '-' + identity
    transcript_file = directory / (stem + '.transcript.txt')
    subtitle_file = directory / (stem + '.srt')
    text = ''
    # Preserve completed transcription across failed summaries and restarts.
    if transcript_file.is_file():
        text = transcript_file.read_text(encoding='utf-8')
    elif path.suffix.lower() in ('.txt', '.srt', '.vtt'):
        raw = path.read_text(encoding='utf-8-sig')
        text = subtitle_text(raw) if path.suffix.lower() in ('.srt', '.vtt') else raw
    else:
        for candidate in item.get('subtitles', []):
            subpath = Path(candidate)
            if subpath.is_file():
                text = subtitle_text(subpath.read_text(encoding='utf-8-sig'))
                if text:
                    break
    if text:
        emit('progress', status='transcribing', progress=69, detail='已读取文字稿，准备生成笔记')
    else:
        with tempfile.TemporaryDirectory(dir=directory, prefix='audio-') as work:
            text, srt = transcribe(path, settings, emit, Path(work), directory / (stem + '.asr.json'))
            if srt:
                subtitle_file.write_text(srt, encoding='utf-8')
    if not text.strip():
        raise RuntimeError('文字稿为空，无法生成笔记。')
    transcript_file.write_text(text, encoding='utf-8')
    emit('transcript', path=str(transcript_file))
    summary = summarize(text, item['title'], settings, emit)
    notes_file = directory / (stem + '.md')
    title = item['title'].replace('\n', ' ')
    header = f'# {title}\n\n> 生成于 {now()} · {"Qoder" if settings["provider"] == "qoder" else settings["api_model"]}\n\n'
    if item.get('source'):
        header += f'来源：{item["source"]}\n\n'
    notes_file.write_text(header + summary + '\n', encoding='utf-8')
    result = {'title': title, 'markdown': str(notes_file), 'transcript': str(transcript_file),
              'srt': str(subtitle_file) if subtitle_file.is_file() else '', 'source': item.get('source', ''), 'created': now()}
    atomic_json(directory / (stem + '.note.json'), result)
    emit('note', note=result)
    return result


def run_task(task, settings, emit):
    if task.get('action') == 'notes':
        records = task.get('files', [])
        if not records:
            raise ValueError('此任务没有可处理的本地文件。')
    else:
        records = download(task, settings, emit)
    if task.get('ai') or task.get('action') == 'notes':
        failures = []
        for index, item in enumerate(records):
            emit('log', detail=f'生成笔记 {index + 1}/{len(records)}：{item["title"]}')
            try:
                make_notes(item, task, settings, emit)
            except Exception as exc:
                failures.append(redact(f'{item["title"]}：{exc}', settings))
        if failures:
            raise RuntimeError('文件已保留，AI 处理未全部完成。' + '\n'.join(failures))
    emit('done', detail='下载与笔记已完成' if task.get('ai') else '下载完成', progress=100)


def test_connection(settings, emit):
    answer = complete('这是连接测试。请只回复：连接成功。', settings)
    emit('done', detail=answer[:300], progress=100)
