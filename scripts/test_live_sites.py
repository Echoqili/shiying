"""Live public-video checks through the shipped desktop executable, without AI."""
import concurrent.futures
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from videodesk.core import DEFAULTS, atomic_json, find_tools, new_task, read_json  # noqa: E402
from videodesk.browser_login import session_path  # noqa: E402

SITES = {
    'YouTube': ['https://www.youtube.com/watch?v=jNQXAC9IVRw', 'https://www.youtube.com/watch?v=J---aiyznGQ'],
    'Bilibili': ['https://www.bilibili.com/video/BV1nx411u79K', 'https://www.bilibili.com/video/BV1bK411W797?p=1'],
    'TikTok': ['https://www.tiktok.com/@pokemonlife22/video/7059698374567611694',
               'https://www.tiktok.com/@patroxofficial/video/6742501081818877190'],
}
OUT = ROOT / 'downloads' / 'site-tests'
REPORT = ROOT / 'docs' / 'live-site-tests.json'
EXE = ROOT / 'dist' / 'Shiying' / 'Shiying.exe'
QUALITY = 'best'


def run_site(site):
    results = []
    for index, url in enumerate(SITES[site]):
        settings = DEFAULTS | {'output': str(OUT / site), 'provider': 'qoder', 'cookie_file': ''}
        task = new_task(url, settings, quality=QUALITY, ai=False)
        payload = {'settings': settings, 'task': task}
        began = time.monotonic()
        auth = 'saved_youtube_session' if site == 'YouTube' and session_path('youtube').is_file() else 'anonymous'
        record = {'site': site, 'sample': index + 1, 'url': url, 'authentication': auth, 'quality_limit': QUALITY}
        print(f'START {site} sample {index + 1}', flush=True)
        # CREATE_NEW_PROCESS_GROUP lets the timeout cleanup terminate only this test worker tree.
        process = subprocess.Popen([str(EXE), '--worker'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            stdout, stderr = process.communicate(json.dumps(payload).encode('utf-8'), timeout=150)
            events = []
            for line in stdout.decode('utf-8', 'replace').splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            record['warnings'] = [e.get('detail', '') for e in events if e.get('event') == 'log']
            errors = [e.get('detail', '') for e in events if e.get('event') == 'error']
            artifacts = [e['item'] for e in events if e.get('event') == 'artifact']
            record['artifacts'] = artifacts
            record['status'] = 'downloaded' if process.returncode == 0 and artifacts else 'failed'
            record['error'] = '\n'.join(errors) or (stderr.decode('utf-8', 'replace')[-1800:] if process.returncode else '')
            _, ffprobe = find_tools({})
            ffmpeg, _ = find_tools({})
            record['media'] = []
            for artifact in artifacts:
                path = Path(artifact['file'])
                probe = subprocess.run([ffprobe, '-v', 'error', '-show_entries',
                                        'format=duration,size:stream=codec_type,width,height,codec_name', '-of', 'json', str(path)],
                                       capture_output=True, timeout=30)
                decode = subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-i', str(path), '-f', 'null', 'NUL'],
                                        capture_output=True, timeout=60)
                metadata = json.loads(probe.stdout) if probe.returncode == 0 else {}
                record['media'].append({'file': str(path), 'probe': metadata, 'decode_exit': decode.returncode,
                                        'decode_error': decode.stderr.decode('utf-8', 'replace')[-500:]})
                if probe.returncode or decode.returncode:
                    record['status'] = 'validation_failed'
                if not any(s.get('codec_type') == 'audio' for s in metadata.get('streams', [])):
                    record['status'] = 'missing_audio'
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            process.communicate()
            record.update(status='timeout', error='150-second live test deadline exceeded')
        except Exception as exc:
            record.update(status='test_error', error=str(exc))
        record['elapsed_seconds'] = round(time.monotonic() - began, 2)
        atomic_json(OUT / site / f'sample-{index + 1}.json', record)
        results.append(record)
        print(f'RESULT {site} sample {index + 1}: {record["status"]} {record.get("error", "")[:550]}', flush=True)
        if record['status'] == 'downloaded':
            break
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', choices=list(SITES))
    parser.add_argument('--quality', default='best')
    arguments = parser.parse_args()
    QUALITY = arguments.quality
    selected = [arguments.site] if arguments.site else list(SITES)
    report = read_json(REPORT, {'date': '2026-11-01', 'executable': str(EXE), 'ai_enabled': False, 'results': []})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run_site, site) for site in selected]
        for future in concurrent.futures.as_completed(futures):
            report['results'].extend(future.result())
            atomic_json(REPORT, report)
    print('REPORT:', REPORT, flush=True)
