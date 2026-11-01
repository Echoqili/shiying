"""Produce MP4/H.264/AAC files playable in Windows' older media player."""
import json
import os
import subprocess
import uuid
from pathlib import Path

from .core import find_tools


def media_info(path, settings):
    _, probe = find_tools(settings)
    if not probe:
        raise ValueError('视频兼容处理需要 ffprobe。')
    result = subprocess.run([probe, '-v', 'error', '-show_entries',
                             'stream=codec_type,codec_name,pix_fmt:format=duration', '-of', 'json', str(path)],
                            capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=30)
    if result.returncode:
        raise RuntimeError('无法检查视频编码：' + result.stderr.decode('utf-8', 'replace')[-400:])
    return json.loads(result.stdout)


def windows_compatible(path, settings, emit):
    path = Path(path)
    info = media_info(path, settings)
    videos = [s for s in info['streams'] if s['codec_type'] == 'video']
    audios = [s for s in info['streams'] if s['codec_type'] == 'audio']
    good_video = videos and videos[0]['codec_name'] == 'h264' and videos[0].get('pix_fmt') == 'yuv420p'
    good_audio = all(s['codec_name'] == 'aac' for s in audios)
    if path.suffix.lower() == '.mp4' and good_video and good_audio:
        return str(path)
    if not videos:
        raise ValueError('下载文件没有视频轨道。')
    ffmpeg, _ = find_tools(settings)
    if not ffmpeg:
        raise ValueError('转换兼容视频需要 FFmpeg。')
    target = path.with_name(path.stem + ' [兼容].mp4')
    # Never overwrite a pre-existing output, including a user's edited copy.
    if target.exists():
        target = path.with_name(path.stem + ' [兼容-' + uuid.uuid4().hex[:8] + '].mp4')
    temporary = target.with_name(target.stem + '.' + uuid.uuid4().hex[:8] + '.tmp.mp4')
    emit('progress', status='processing', detail='正在生成兼容 Windows 播放器的 MP4（H.264 / AAC）')
    command = [ffmpeg, '-v', 'error', '-nostdin', '-n', '-i', str(path), '-map', '0:v:0', '-map', '0:a:0?',
               '-c:v', 'copy' if good_video else 'libx264']
    if not good_video:
        command += ['-pix_fmt', 'yuv420p', '-preset', 'fast', '-crf', '20', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
    command += ['-c:a', 'copy' if good_audio else 'aac']
    if not good_audio:
        command += ['-b:a', '192k']
    command += ['-movflags', '+faststart', str(temporary)]
    try:
        result = subprocess.run(command, capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('MP4 兼容转换失败，原文件已保留：' + result.stderr.decode('utf-8', 'replace')[-500:])
        checked = media_info(temporary, settings)
        source_duration = float(info.get('format', {}).get('duration') or 0)
        output_duration = float(checked.get('format', {}).get('duration') or 0)
        if source_duration and abs(source_duration - output_duration) > max(1, source_duration * .01):
            raise RuntimeError('兼容文件时长校验失败，原文件已保留。')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return str(target)
