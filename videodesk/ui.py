from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QSplitter, QStackedWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from .controller import Controller
from .core import ACTIVE, Store, find_tools, new_task, parse_urls
from .settings import SettingsPage
from .theme import app_icon, icon, apply_theme
from .widgets import Panel, TaskCard, button, label


class MainWindow(QMainWindow):
    def __init__(self, store=None):
        super().__init__()
        self.controller = Controller(store or Store(), self)
        self.setWindowTitle('拾影 · 视频下载与 AI 笔记')
        self.setWindowIcon(app_icon())
        self.resize(1280, 900)
        self.setMinimumSize(1100, 780)
        self.cards = {}
        self.task_filter = 'all'
        self.selected_note = None
        self.note_mode = 'markdown'
        self.test_closing = False
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(32, 22, 32, 20)
        right.setSpacing(22)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label('工作空间  /  本地工作台', 'Muted', 12))
        toolbar.addStretch()
        toolbar.addWidget(button('打开下载目录', self.open_output, small=True, symbol='folder'))
        right.addLayout(toolbar)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.download_page())
        self.pages.addWidget(self.notes_page())
        self.settings_page = SettingsPage(self.controller.settings)
        self.settings_page.saved.connect(self.save_settings)
        self.pages.addWidget(self.settings_page)
        right.addWidget(self.pages, 1)
        footer = QHBoxLayout()
        self.footer = label('准备就绪', 'Muted', 11)
        footer.addWidget(self.footer, 1)
        footer.addWidget(label('POWERED BY yt-dlp  /  Qoder', 'Muted', 10))
        right.addLayout(footer)
        layout.addLayout(right, 1)
        self.controller.changed.connect(self.task_changed)
        self.controller.queue_changed.connect(self.rebuild)
        self.rebuild()
        apply_theme(QApplication.instance(), self.controller.settings.get('theme', 'cream'))
        if self.controller.store.secret_error:
            self.footer.setText(self.controller.store.secret_error)

    def sidebar(self):
        frame = QFrame()
        frame.setObjectName('Sidebar')
        frame.setFixedWidth(208)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 30, 16, 22)
        layout.setSpacing(9)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(38, 38))
        brand.addWidget(logo)
        brand.addSpacing(4)
        brand.addWidget(label('拾影', 'Brand'))
        brand.addStretch()
        layout.addLayout(brand)
        layout.addWidget(label('   SAVE WHAT INSPIRES', 'Muted', 9))
        layout.addSpacing(38)
        layout.addWidget(label('   我的工作台', 'Muted', 10))
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        self.nav_buttons = []
        for index, (text, symbol) in enumerate([('下载任务', 'download'), ('AI 笔记', 'notes'), ('设置', 'settings')]):
            nav = button('   ' + text)
            nav.setObjectName('Nav')
            nav.setIcon(icon(symbol, '#a5b9a0', 20))
            nav.setCheckable(True)
            nav.clicked.connect(lambda checked=False, page=index: self.switch_page(page))
            self.nav.addButton(nav, index)
            self.nav_buttons.append(nav)
            layout.addWidget(nav)
        self.nav_buttons[0].setChecked(True)
        layout.addStretch()
        info = Panel()
        box = QVBoxLayout(info)
        box.setContentsMargins(15, 16, 15, 16)
        box.setSpacing(10)
        box.addWidget(label('视频 → 文字 → 灵感', '', 12))
        hint = label('好内容，值得慢慢消化。\n用 AI 整理每一次收获。', 'Muted', 10)
        hint.setWordWrap(True)
        box.addWidget(hint)
        box.addWidget(button('配置我的 AI  →', lambda: self.switch_page(2), small=True))
        layout.addWidget(info)
        layout.addSpacing(15)
        self.engine_state = label('●  本地下载引擎', 'Muted', 11)
        layout.addWidget(self.engine_state)
        from . import __version__
        layout.addWidget(label(f'拾影  {__version__}', 'Muted', 10))
        return frame

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        if index == 1:
            self.refresh_notes()

    def download_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(17)
        layout.addWidget(label('COLLECT  /  KEEP  /  UNDERSTAND', 'Eyebrow'))
        layout.addWidget(label('把好内容，留在身边。', 'Title'))
        layout.addWidget(label('粘贴链接，保存视频。再把值得记住的，交给 AI。', 'Muted'))
        panel = Panel()
        body = QVBoxLayout(panel)
        body.setContentsMargins(22, 19, 22, 20)
        body.setSpacing(13)
        heading = QHBoxLayout()
        heading.addWidget(label('添加视频链接', 'Section'))
        heading.addStretch()
        heading.addWidget(button('粘贴链接', self.paste, small=True, symbol='paste'))
        body.addLayout(heading)
        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText('https://…\n支持 YouTube、B 站等 yt-dlp 支持的网站；多个链接请每行粘贴一个')
        self.url_input.setFixedHeight(88)
        body.addWidget(self.url_input)
        options = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem('视频 + 音频', 'video')
        self.mode.addItem('提取 MP3', 'audio')
        self.mode.currentIndexChanged.connect(lambda: self.quality.setEnabled(self.mode.currentData() == 'video'))
        self.quality = QComboBox()
        for text, value in [('最佳画质', 'best'), ('最高 1080p', '1080'), ('最高 720p', '720'), ('最高 480p', '480')]:
            self.quality.addItem(text, value)
        self.subtitles = QCheckBox('保存字幕')
        self.playlist = QCheckBox('整个播放列表')
        options.addWidget(self.mode)
        options.addWidget(self.quality)
        options.addSpacing(8)
        options.addWidget(self.subtitles)
        options.addWidget(self.playlist)
        options.addStretch()
        body.addLayout(options)
        pathrow = QHBoxLayout()
        pathrow.addWidget(label('保存到', 'Muted', 12))
        self.output = QLineEdit(self.controller.settings['output'])
        self.output.setMinimumWidth(200)
        pathrow.addWidget(self.output, 1)
        pathrow.addWidget(button('更改目录', self.choose_output, small=True))
        body.addLayout(pathrow)
        bottom = QHBoxLayout()
        self.auto_ai = QCheckBox('完成后生成 AI 笔记')
        self.auto_ai.setToolTip('字幕或文字稿将发送到所选总结服务；缺少字幕时音频将发送到配置的转写服务。')
        self.auto_ai.toggled.connect(self.ai_hint_changed)
        bottom.addWidget(self.auto_ai)
        self.provider_badge = label('Qoder', 'Muted', 11)
        bottom.addWidget(self.provider_badge)
        bottom.addStretch()
        self.add_button = button('开始下载', self.add_downloads, primary=True, symbol='download')
        bottom.addWidget(self.add_button)
        body.addLayout(bottom)
        self.ai_hint = label('所选 AI 服务将处理字幕/文字稿；无字幕时，音频会发送到你配置的转写服务。', 'Muted', 10)
        self.ai_hint.setWordWrap(True)
        self.ai_hint.hide()
        body.addWidget(self.ai_hint)
        layout.addWidget(panel)

        task_heading = QHBoxLayout()
        task_heading.addWidget(label('下载任务', 'Section'))
        self.count_label = label('0', 'Muted', 12)
        task_heading.addWidget(self.count_label)
        task_heading.addStretch()
        self.filter_group = QButtonGroup(self)
        for text, value in [('全部', 'all'), ('进行中', 'active'), ('已完成', 'complete')]:
            control = button(text, small=True)
            control.setCheckable(True)
            control.setChecked(value == 'all')
            control.clicked.connect(lambda checked=False, val=value: self.set_filter(val))
            self.filter_group.addButton(control)
            task_heading.addWidget(control)
        layout.addLayout(task_heading)
        self.task_stack = QStackedWidget()
        empty = QWidget()
        ebox = QVBoxLayout(empty)
        ebox.addStretch()
        drawing = QLabel()
        drawing.setPixmap(icon('download', '#728b6d', 42).pixmap(42, 42))
        drawing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ebox.addWidget(drawing)
        ebox.addSpacing(8)
        message = label('从第一个链接开始', '', 15)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ebox.addWidget(message)
        self.empty_subtitle = label('你的下载任务会出现在这里', 'Muted', 12)
        self.empty_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ebox.addWidget(self.empty_subtitle)
        ebox.addStretch()
        self.task_stack.addWidget(empty)
        self.task_list = QListWidget()
        self.task_list.setSpacing(5)
        self.task_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.task_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.task_stack.addWidget(self.task_list)
        layout.addWidget(self.task_stack, 1)
        return page

    def notes_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('让每一段视频，都有收获。', 'Title'))
        titles.addWidget(label('导入本地视频、音频或文字稿，也能生成 AI 笔记。', 'Muted'))
        top.addLayout(titles, 1)
        top.addWidget(button('导入本地文件', self.import_file, primary=True, symbol='plus'))
        layout.addLayout(top)
        hint = label('生成笔记时，字幕/文字稿将发送到所选 AI；没有字幕的音视频还会使用你配置的转写服务。', 'Muted', 11)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        tools = QHBoxLayout()
        self.note_count = label('0 篇笔记', 'Muted')
        tools.addWidget(self.note_count)
        tools.addStretch()
        self.summary_button = button('总结', lambda: self.show_note('markdown'), small=True)
        self.transcript_button = button('文字稿', lambda: self.show_note('transcript'), small=True)
        self.srt_button = button('字幕', lambda: self.show_note('srt'), small=True)
        self.export_button = button('导出', self.export_note, small=True)
        self.copy_button = button('复制', self.copy_note, small=True)
        for control in (self.summary_button, self.transcript_button, self.srt_button, self.copy_button, self.export_button):
            tools.addWidget(control)
        layout.addLayout(tools)
        splitter = QSplitter()
        self.note_list = QListWidget()
        self.note_list.setObjectName('NoteList')
        self.note_list.setMinimumWidth(200)
        self.note_list.currentItemChanged.connect(self.select_note)
        self.note_view = QTextBrowser()
        self.note_view.setOpenLinks(False)
        self.note_view.anchorClicked.connect(self.open_link)
        self.note_view.document().setDefaultFont(QFont('Microsoft YaHei UI', 11))
        self.note_view.document().setDefaultStyleSheet('h1 {font-size: 24px; color: #eaf2e6;} h2 {font-size: 18px; color: #b7ef85;} p, li {line-height: 1.7;} blockquote {color: #8ea298;} a {color: #b7ef85;}')
        splitter.addWidget(self.note_list)
        splitter.addWidget(self.note_view)
        splitter.setSizes([240, 700])
        layout.addWidget(splitter, 1)
        self.show_note()
        return page

    def ai_hint_changed(self, checked):
        self.ai_hint.setVisible(checked)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, '选择下载目录', self.output.text())
        if path:
            self.output.setText(path)

    def paste(self):
        text = QApplication.clipboard().text().strip()
        if text:
            current = self.url_input.toPlainText().strip()
            self.url_input.setPlainText(current + '\n' + text if current else text)
            self.url_input.setFocus()

    def add_downloads(self):
        try:
            urls = parse_urls(self.url_input.toPlainText())
            output = self.output.text().strip()
            if not output:
                raise ValueError('请选择保存目录。')
            ffmpeg, ffprobe = find_tools(self.controller.settings)
            if self.mode.currentData() == 'audio' and not (ffmpeg and ffprobe):
                raise ValueError('提取 MP3 需要 FFmpeg 和 ffprobe，请先在设置中配置。')
            Path(output).mkdir(parents=True, exist_ok=True)
            tasks = [new_task(url, self.controller.settings, output=output, mode=self.mode.currentData(),
                              quality=self.quality.currentData(), subtitles=self.subtitles.isChecked(),
                              playlist=self.playlist.isChecked(), ai=self.auto_ai.isChecked()) for url in urls]
            self.controller.add(tasks)
            self.url_input.clear()
            self.footer.setText(f'已添加 {len(tasks)} 个下载任务')
        except (ValueError, OSError) as exc:
            QMessageBox.information(self, '添加任务', str(exc))

    def import_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '导入文件生成 AI 笔记', '', '视频、音频和文字稿 (*.mp4 *.mkv *.webm *.mov *.avi *.m4a *.mp3 *.wav *.flac *.ogg *.txt *.srt *.vtt);;所有文件 (*)')
        tasks = []
        for value in paths:
            path = Path(value)
            task = new_task('', self.controller.settings, action='notes', ai=True, title=path.stem,
                            files=[{'file': value, 'title': path.stem, 'source': '', 'subtitles': []}])
            tasks.append(task)
        if tasks:
            self.controller.add(tasks)
            self.switch_page(0)

    def set_filter(self, value):
        self.task_filter = value
        self.rebuild()

    def matches(self, task):
        return self.task_filter == 'all' or (self.task_filter == 'complete' and task['status'] == 'complete') or (self.task_filter == 'active' and task['status'] in ACTIVE | {'queued'})

    def rebuild(self):
        self.task_list.clear()
        self.cards.clear()
        for task in self.controller.tasks:
            if not self.matches(task):
                continue
            card = TaskCard(task)
            card.action.connect(self.task_action)
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 138))
            self.task_list.addItem(item)
            self.task_list.setItemWidget(item, card)
            self.cards[task['id']] = card
        self.task_stack.setCurrentIndex(1 if self.cards else 0)
        self.empty_subtitle.setText('没有符合筛选条件的任务' if self.controller.tasks else '你的下载任务会出现在这里')
        self.refresh_stats()
        self.refresh_notes()

    def task_changed(self, task_id):
        card = self.cards.get(task_id)
        task = next((t for t in self.controller.tasks if t['id'] == task_id), None)
        if card:
            card.refresh()
        if task and ((card is not None) != self.matches(task)):
            self.rebuild()
        self.refresh_stats()
        if task and task.get('notes'):
            self.refresh_notes()

    def refresh_stats(self):
        tasks = self.controller.tasks
        active = sum(t['status'] in ACTIVE | {'queued'} for t in tasks)
        completed = sum(t['status'] == 'complete' for t in tasks)
        self.count_label.setText(f'{len(tasks)}')
        self.footer.setText(f'{active} 个任务进行中  ·  {completed} 个已完成' if tasks else '准备就绪 · 添加链接即可开始')
        self.engine_state.setText('●  正在处理任务' if active else '●  本地下载引擎')
        self.provider_badge.setText('Qoder' if self.controller.settings['provider'] == 'qoder' else '自定义 AI')

    def task_action(self, task_id, action):
        task = next((t for t in self.controller.tasks if t['id'] == task_id), None)
        if not task:
            return
        if action == 'cancel':
            self.controller.cancel(task)
        elif action == 'retry':
            self.controller.retry(task)
        elif action == 'retry_notes':
            self.controller.retry(task, notes=True)
        elif action == 'open':
            self.open_output(task['output'])
        elif action == 'notes':
            self.switch_page(1)
            if task.get('notes'):
                self.focus_note(task['notes'][0]['markdown'])
        elif action == 'detail':
            self.details(task)

    def details(self, task):
        dialog = QDialog(self)
        dialog.setWindowTitle('任务详情')
        dialog.resize(740, 490)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 20)
        heading = label(task['title'], 'Section')
        heading.setWordWrap(True)
        layout.addWidget(heading)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        content = f'来源：{task.get("url") or "本地文件"}\n保存目录：{task["output"]}\n\n{task.get("detail", "")}\n'
        if task.get('files'):
            content += '\n文件：\n' + '\n'.join(f['file'] for f in task['files'])
        if task.get('transcript'):
            content += '\n\n文字稿：' + task['transcript']
        if task.get('logs'):
            content += '\n\n日志：\n' + '\n'.join(task['logs'])
        view.setPlainText(content)
        layout.addWidget(view, 1)
        row = QHBoxLayout()
        if task.get('files'):
            generate = button('生成 / 重试 AI 笔记', lambda: (dialog.accept(), self.controller.retry(task, notes=True)), primary=True)
            generate.setEnabled(task['status'] not in ACTIVE | {'queued'})
            row.addWidget(generate)
        row.addWidget(button('打开保存目录', lambda: self.open_output(task['output'])))
        row.addStretch()
        row.addWidget(button('关闭', dialog.accept))
        layout.addLayout(row)
        dialog.exec()

    def refresh_notes(self):
        if not hasattr(self, 'note_list'):
            return
        selected = self.selected_note.get('markdown') if self.selected_note else None
        notes = [note for task in self.controller.tasks for note in task.get('notes', [])]
        self.note_count.setText(f'{len(notes)} 篇笔记')
        current = [self.note_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.note_list.count())]
        if current == notes:
            return
        self.note_list.blockSignals(True)
        self.note_list.clear()
        for note in notes:
            item = QListWidgetItem(note['title'] + '\n' + note.get('created', ''))
            item.setData(Qt.ItemDataRole.UserRole, note)
            item.setToolTip(note['title'])
            self.note_list.addItem(item)
        self.note_list.blockSignals(False)
        if notes:
            self.focus_note(selected)
        else:
            self.selected_note = None
            self.show_note()

    def focus_note(self, path):
        for index in range(self.note_list.count()):
            if self.note_list.item(index).data(Qt.ItemDataRole.UserRole)['markdown'] == path:
                self.note_list.setCurrentRow(index)
                return
        if self.note_list.count():
            self.note_list.setCurrentRow(0)

    def select_note(self, item, previous=None):
        self.selected_note = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.show_note()

    def show_note(self, mode=None):
        if mode:
            self.note_mode = mode
        for control in (self.summary_button, self.transcript_button, self.export_button, self.copy_button):
            control.setEnabled(bool(self.selected_note))
        self.srt_button.setEnabled(bool(self.selected_note and self.selected_note.get('srt')))
        if not self.selected_note:
            self.note_view.setHtml('<h2>给灵感一个落脚点。</h2><p>下载时勾选“完成后生成 AI 笔记”，<br>或导入本地视频、音频、文字稿。</p><p>生成的摘要与文字稿会保存在这里。</p>')
            return
        if self.note_mode == 'srt' and not self.selected_note.get('srt'):
            self.note_mode = 'markdown'
        try:
            text = Path(self.selected_note[self.note_mode]).read_text(encoding='utf-8')
            if self.note_mode == 'markdown':
                self.note_view.setMarkdown(text)
            else:
                self.note_view.setPlainText(text)
        except OSError as exc:
            self.note_view.setPlainText('无法读取文件：' + str(exc))

    def copy_note(self):
        if self.selected_note:
            try:
                QApplication.clipboard().setText(Path(self.selected_note[self.note_mode]).read_text(encoding='utf-8'))
                self.footer.setText('已复制到剪贴板')
            except OSError as exc:
                QMessageBox.warning(self, '复制失败', str(exc))

    def export_note(self):
        if not self.selected_note:
            return
        source = Path(self.selected_note[self.note_mode])
        filters = {'markdown': 'Markdown (*.md)', 'transcript': '文字稿 (*.txt)', 'srt': '字幕 (*.srt)'}
        path, _ = QFileDialog.getSaveFileName(self, '导出笔记', str(Path.home() / source.name), filters[self.note_mode] + ';;所有文件 (*)')
        if path:
            try:
                if Path(path).resolve() != source.resolve():
                    shutil.copyfile(source, path)
                self.footer.setText('已导出：' + path)
            except OSError as exc:
                QMessageBox.warning(self, '导出失败', str(exc))

    def open_link(self, url):
        if url.scheme() in ('https', 'http'):
            QDesktopServices.openUrl(url)

    def open_output(self, path=None):
        if not isinstance(path, str):
            path = self.output.text() if hasattr(self, 'output') else self.controller.settings['output']
        try:
            directory = Path(path)
            directory.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve())))
        except OSError as exc:
            QMessageBox.warning(self, '打开目录', str(exc))

    def save_settings(self, settings):
        try:
            self.controller.store.save_settings(settings)
            self.controller.settings = settings
            apply_theme(QApplication.instance(), settings.get('theme', 'cream'))
            self.output.setText(settings['output'])
            self.settings_page.test_result.setText('设置已保存。密钥已使用 Windows 系统机制加密。')
            self.refresh_stats()
        except OSError as exc:
            QMessageBox.warning(self, '保存失败', str(exc))

    def closeEvent(self, event):
        self.controller.shutdown()
        if self.settings_page.test_job:
            self.settings_page.test_job.cancel()
        if self.settings_page.browser_job:
            self.settings_page.browser_job.cancel()
        event.accept()
