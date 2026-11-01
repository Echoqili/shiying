from urllib.parse import urlsplit

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from .core import ACTIVE
from .theme import icon, themed


def label(text='', name='', size=0):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    if size:
        widget.setStyleSheet(f'font-size: {size}px; background: transparent;')
    return widget


def button(text, callback=None, primary=False, small=False, symbol=''):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        widget.setObjectName('Primary')
    elif small:
        widget.setObjectName('Small')
    if symbol:
        widget.setIcon(icon(symbol, '#17251b' if primary else '#b0bfc4', 18))
    if callback:
        widget.clicked.connect(callback)
    return widget


class Panel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('Panel')


STATUS = {
    'queued': ('等待中', '#aeb8bd'), 'running': ('启动中', '#b7ef85'),
    'analyzing': ('解析中', '#9ecbff'), 'downloading': ('下载中', '#b7ef85'),
    'processing': ('处理中', '#d8c1ff'), 'transcribing': ('转写中', '#cfb8ff'),
    'summarizing': ('总结中', '#cfb8ff'), 'complete': ('已完成', '#b7ef85'),
    'partial': ('AI 待重试', '#e7bf86'), 'failed': ('失败', '#eea09b'),
    'cancelled': ('已取消', '#92a1a8'), 'interrupted': ('已中断', '#e7bf86'),
}


class TaskCard(QFrame):
    action = Signal(str, str)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName('TaskCard')
        self.setMinimumHeight(134)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(16)
        badge = QLabel()
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(icon('notes' if task.get('action') == 'notes' else 'play', '#b4cdab', 25).pixmap(25, 25))
        badge.setStyleSheet(themed('background: #2a372f; border-radius: 12px;'))
        badge.setProperty('theme_original', 'background: #2a372f; border-radius: 12px;')
        badge.setProperty('theme_applied', badge.styleSheet())
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        center = QVBoxLayout()
        center.setSpacing(7)
        top = QHBoxLayout()
        self.title = label('', '', 14)
        self.title.setMinimumWidth(0)
        top.addWidget(self.title, 1)
        self.tag = label()
        top.addWidget(self.tag)
        center.addLayout(top)
        self.source = label('', 'Muted', 11)
        center.addWidget(self.source)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        center.addWidget(self.progress)
        self.detail = label('', 'Muted', 11)
        self.detail.setMinimumWidth(0)
        center.addWidget(self.detail)
        layout.addLayout(center, 1)
        actions = QVBoxLayout()
        actions.setSpacing(7)
        self.main_button = button('', lambda: self.action.emit(task['id'], self.main_action), small=True)
        self.extra_button = button('详情', lambda: self.action.emit(task['id'], 'detail'), small=True)
        actions.addWidget(self.main_button)
        actions.addWidget(self.extra_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        task = self.task
        state = task['status']
        text, color = STATUS.get(state, (state, '#aeb8bd'))
        self.tag.setText(text)
        self.tag.setStyleSheet(themed(f'color: {color}; background: transparent; font-size: 11px;'))
        self.tag.setProperty('theme_original', f'color: {color}; background: transparent; font-size: 11px;')
        self.tag.setProperty('theme_applied', self.tag.styleSheet())
        self.title.setText(self.fontMetrics().elidedText(task['title'], Qt.TextElideMode.ElideRight, max(250, self.width() - 295)))
        self.title.setToolTip(task['title'])
        domain = urlsplit(task.get('url', '')).hostname or '本地文件'
        mode = 'AI 笔记' if task.get('action') == 'notes' else ('MP3 音频' if task.get('mode') == 'audio' else '视频')
        self.source.setText(f'{domain}  ·  {mode}  ·  {task.get("created", "")}')
        self.progress.setValue(task.get('progress', 0))
        detail = task.get('detail', '').replace('\n', ' ')
        self.detail.setText(self.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideRight, max(250, self.width() - 270)))
        self.detail.setToolTip(task.get('detail', ''))
        if state in ACTIVE or state == 'queued':
            self.main_action = 'cancel'
            self.main_button.setText('取消任务')
        elif state == 'complete':
            self.main_action = 'notes' if task.get('notes') else 'open'
            self.main_button.setText('查看笔记' if task.get('notes') else '打开目录')
        elif state == 'partial':
            self.main_action = 'retry_notes'
            self.main_button.setText('重试 AI')
        else:
            self.main_action = 'retry'
            self.main_button.setText('重新开始')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()
