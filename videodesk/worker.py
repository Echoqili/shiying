"""One isolated job per process. JSON input and newline-delimited JSON events."""
import json
import sys

from .core import redact


def main():
    # --windowed executables have no sys.std* by default; main.py reopens Windows standard handles.
    settings = {}

    def emit(event, **data):
        print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)

    try:
        payload = json.loads(sys.stdin.read())
        settings = payload['settings']
        from .engine import run_task, test_connection
        if payload.get('action') == 'firefox_sync':
            from .firefox_sync import sync_youtube
            sync_youtube(emit)
        elif payload.get('action') == 'browser_login':
            import asyncio
            from pathlib import Path
            from .browser_login import login
            asyncio.run(login(Path(payload['marker']), emit, payload.get('site', 'douyin')))
        elif payload.get('action') == 'test':
            test_connection(settings, emit)
        else:
            run_task(payload['task'], settings, emit)
        return 0
    except Exception as exc:
        emit('error', detail=redact(str(exc), settings))
        return 1
