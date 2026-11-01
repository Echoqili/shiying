from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .core import ACTIVE, Store, app_root, redact


class Job(QObject):
    event = Signal(dict)
    ended = Signal(int)

    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.process = QProcess(self)
        self.buffer = b''
        self.errors = b''
        self.finished = False
        self.cancelled = False
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.finished.connect(self.finish)
        self.process.errorOccurred.connect(self.process_error)

    def start(self):
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        env.insert('PYTHONUTF8', '1')
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(app_root()))
        if getattr(sys, 'frozen', False):
            program, args = sys.executable, ['--worker']
        else:
            program, args = sys.executable, [str(app_root() / 'main.py'), '--worker']
        self.process.started.connect(self.send)
        self.process.start(program, args)

    def send(self):
        self.process.write(json.dumps(self.payload, ensure_ascii=False).encode('utf-8'))
        self.process.closeWriteChannel()

    def read_error(self):
        self.errors = (self.errors + bytes(self.process.readAllStandardError()))[-12000:]

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                value = json.loads(line.decode('utf-8'))
                if isinstance(value, dict) and 'event' in value:
                    self.event.emit(value)
            except (ValueError, UnicodeError):
                pass

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.event.emit({'event': 'error', 'detail': '无法启动工作进程：' + self.process.errorString()})
            self.finish(-1)

    def finish(self, code, *_):
        if self.finished:
            return
        self.read()
        self.read_error()
        self.finished = True
        self.ended.emit(code)

    def cancel(self):
        self.cancelled = True
        pid = self.process.processId()
        if pid and os.name == 'nt':
            try:
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
        elif pid:
            self.process.kill()
        self.process.waitForFinished(3000)


class Controller(QObject):
    changed = Signal(str)
    queue_changed = Signal()

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.settings = store.load_settings()
        self.tasks = store.load_tasks()
        self.job = None
        self.current = None
        self.shutting_down = False
        self.last_save = 0

    def persist(self):
        self.store.save_tasks(self.tasks)
        self.last_save = time.monotonic()

    def add(self, tasks):
        self.tasks[0:0] = list(reversed(tasks))
        self.persist()
        self.queue_changed.emit()
        QTimer.singleShot(0, self.next)

    def next(self):
        if self.shutting_down or self.job:
            return
        task = next((t for t in reversed(self.tasks) if t['status'] == 'queued'), None)
        if not task:
            return
        self.current = task
        task.update(status='running', detail='启动任务中…', error='')
        self.persist()
        self.job = Job({'task': task.copy(), 'settings': self.settings.copy()}, self)
        self.job.event.connect(self.handle)
        self.job.ended.connect(self.ended)
        self.changed.emit(task['id'])
        self.job.start()

    def handle(self, event):
        task = self.current
        if not task or (self.job and self.job.cancelled):
            return
        kind = event['event']
        if kind == 'progress':
            for key in ('title', 'detail', 'status', 'progress'):
                if key in event:
                    task[key] = event[key]
        elif kind == 'artifact':
            item = event['item']
            task['files'] = [f for f in task.get('files', []) if f['file'] != item['file']] + [item]
            task['title'] = item['title']
        elif kind == 'transcript':
            task['transcript'] = event['path']
        elif kind == 'note':
            note = event['note']
            task['notes'] = [n for n in task.get('notes', []) if n['markdown'] != note['markdown']] + [note]
        elif kind == 'done':
            task.update(status='complete', progress=100, detail=event['detail'])
        elif kind == 'error':
            partial = task.get('files') and task.get('ai') and task['status'] in {'transcribing', 'summarizing'}
            task.update(status='partial' if partial else 'failed', detail=event['detail'], error=event['detail'])
        elif kind == 'log':
            task.setdefault('logs', []).append(event.get('detail', ''))
            task['logs'] = task['logs'][-40:]
        if kind != 'progress' or time.monotonic() - self.last_save > 1:
            self.persist()
        self.changed.emit(task['id'])

    def ended(self, code):
        job, task = self.job, self.current
        if task and task['status'] in ACTIVE:
            detail = redact(job.errors.decode('utf-8', 'replace'), self.settings).strip()
            task.update(status='partial' if task.get('files') else 'failed',
                        detail='工作进程意外退出。' + (detail[-800:] if detail else f' 退出码 {code}'))
        self.job = self.current = None
        self.persist()
        self.queue_changed.emit()
        if job:
            job.deleteLater()
        QTimer.singleShot(100, self.next)

    def cancel(self, task):
        task.update(status='cancelled', detail='已取消，可重试；已下载文件保留')
        self.persist()
        if self.current is task and self.job:
            self.job.cancel()
        self.changed.emit(task['id'])

    def retry(self, task, notes=False):
        if task['status'] in ACTIVE or task['status'] == 'queued':
            return
        task.update(status='queued', progress=0, detail='等待处理', error='')
        if notes:
            task['action'] = 'notes'
            task['ai'] = True
        elif task.get('action') != 'notes':
            task['action'] = 'download'
        self.persist()
        self.changed.emit(task['id'])
        QTimer.singleShot(0, self.next)

    def shutdown(self):
        self.shutting_down = True
        if self.job:
            if self.current:
                self.current.update(status='interrupted', detail='退出时中断，可重试')
            self.job.cancel()
        self.persist()
