from __future__ import annotations

import importlib.util
import shutil
import subprocess
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox,
    QScrollArea, QVBoxLayout, QWidget,
)

from .controller import Job
from .core import DEFAULTS, data_root, find_tools, parse_urls
from .widgets import Panel, button, label


def locate_qoder(configured=''):
    if configured and Path(configured).is_file():
        return configured
    for name in ('qodercli.exe', 'qoder.exe', 'qodercli', 'qoder'):
        value = shutil.which(name)
        if value and Path(value).suffix.lower() not in ('.ps1', '.cmd', '.bat'):
            return value
    spec = importlib.util.find_spec('qoder_agent_sdk')
    if spec and spec.origin:
        for candidate in Path(spec.origin).parent.rglob('*.exe'):
            if 'qoder' in candidate.name.lower():
                return str(candidate)
    return ''


class SettingsPage(QWidget):
    saved = Signal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.fields = {}
        self.test_job = None
        self.browser_job = None
        self.settings = settings.copy()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        heading = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(label('让 AI 按你的方式工作', 'Title'))
        title.addWidget(label('选择 Qoder 额度，或接入你自己的模型服务。', 'Muted'))
        heading.addLayout(title, 1)
        heading.addWidget(button('保存设置', self.save, primary=True))
        outer.addLayout(heading)
        outer.addSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 9, 0)
        self.body.setSpacing(16)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        _, appearance = self.section('界面外观', '米白色更柔和，也可以切换回深色。保存后立即生效。')
        self.theme_choice = QComboBox()
        self.theme_choice.addItem('米白色', 'cream')
        self.theme_choice.addItem('深色', 'dark')
        self.theme_choice.setCurrentIndex(1 if settings.get('theme') == 'dark' else 0)
        appearance.addRow('背景主题', self.theme_choice)
        card, form = self.section('01  总结服务', 'AI 只处理文字稿。每次调用会按所选服务的规则消耗额度。')
        self.provider = QComboBox()
        self.provider.addItem('Qoder · 使用我的账号额度', 'qoder')
        self.provider.addItem('自定义 · 兼容 OpenAI 接口', 'custom')
        self.provider.setCurrentIndex(1 if settings['provider'] == 'custom' else 0)
        self.provider.currentIndexChanged.connect(self.toggle_provider)
        form.addRow('总结方式', self.provider)

        self.qoder_card, qform = self.section('Qoder', '使用官方 Agent SDK。支持本机 CLI 登录，也可填写个人访问令牌 PAT。')
        self.add_field(qform, 'qoder_model', '模型（可选）', '留空使用 Qoder 默认模型')
        self.add_field(qform, 'qoder_cli', 'CLI 路径（可选）', '默认使用内置运行时', picker='file')
        self.add_field(qform, 'qoder_pat', 'PAT（可选）', '使用本机登录时可留空', secret=True)
        qrow = QHBoxLayout()
        qrow.addWidget(button('登录 Qoder', self.login, symbol='plus'))
        qrow.addWidget(button('获取 PAT', lambda: QDesktopServices.openUrl(QUrl('https://qoder.com/account/integrations'))))
        qrow.addStretch()
        qform.addRow('', qrow)
        qform.addRow('', self.hint('登录会打开 Qoder 官方终端；已有登录态可直接测试。你的密码由 Qoder 管理。'))

        self.custom_card, cform = self.section('自定义 AI', '填写服务商提供的 API 信息。支持 Chat Completions 兼容接口，包括火山方舟。')
        presets = QHBoxLayout()
        presets.addWidget(button('填入豆包接口地址', self.doubao, small=True))
        presets.addStretch()
        cform.addRow('', presets)
        self.add_field(cform, 'api_base', 'API 地址', '例如 https://你的服务商/v1 或 /api/v3')
        self.add_field(cform, 'api_key', 'API Key', '填写你的 API Key；本地无鉴权服务可留空', secret=True)
        self.add_field(cform, 'api_model', '模型名称', '填写模型 ID；豆包可填写已开通的模型或接入点 ID')

        _, aform = self.section('02  语音转写', '优先使用视频已有字幕。缺少字幕时，音频将发送到此处配置的语音识别服务。')
        self.add_field(aform, 'asr_base', '转写 API 地址', '兼容 /audio/transcriptions 的服务基础地址')
        self.add_field(aform, 'asr_key', '转写 API Key', '可使用与总结不同的服务和密钥', secret=True)
        self.add_field(aform, 'asr_model', '转写模型', '例如 whisper-1，填写服务商实际支持的模型')
        aform.addRow('', self.hint('Qoder 总结额度不等于语音转写额度。有字幕或导入文字稿时，无需配置语音转写。'))

        _, dform = self.section('03  下载与网络', '设置保存位置、音视频工具和网络连接。')
        self.add_field(dform, 'output', '默认保存目录', '', picker='directory')
        self.add_field(dform, 'ffmpeg_dir', 'FFmpeg 目录', '默认使用内置工具，也可指定含 ffmpeg 和 ffprobe 的目录', picker='directory')
        self.add_field(dform, 'proxy', '代理地址（可选）', '例如 http://127.0.0.1:7890')
        self.add_field(dform, 'cookie_file', 'Cookies 文件（可选）', 'Netscape 格式，用于需要登录的网站', picker='file')
        ffmpeg, ffprobe = find_tools(settings)
        self.tools_label = self.hint('FFmpeg / ffprobe：' + ('已就绪' if ffmpeg and ffprobe else '待配置；普通合并格式仍可下载'))
        dform.addRow('', self.tools_label)
        self.browser_status = self.hint('使用独立浏览器登录；本站会话加密保存在本机，下载对应网站时自动使用。')
        dform.addRow('网站登录', self.browser_status)
        login_row = QHBoxLayout()
        self.browser_button = button('登录抖音（Playwright）', lambda: self.start_browser_login('douyin'))
        self.youtube_button = button('打开 Firefox 登录', self.open_firefox)
        self.browser_save = button('完成登录，保存', self.finish_browser_login)
        self.browser_save.setEnabled(False)
        login_row.addWidget(self.browser_button)
        login_row.addWidget(self.youtube_button)
        login_row.addWidget(self.browser_save)
        dform.addRow('', login_row)
        self.firefox_sync_button = button('同步 Firefox 的 YouTube 登录状态', self.sync_firefox)
        dform.addRow('YouTube', self.firefox_sync_button)

        _, tform = self.section('连接测试', '测试会发送一条简短请求，并消耗少量所选服务的额度。')
        self.test_button = button('测试总结连接', self.test)
        tform.addRow('', self.test_button)
        self.test_result = self.hint('尚未测试。API Key 只保存在本机，使用 Windows 系统机制加密。')
        tform.addRow('', self.test_result)
        self.body.addStretch()
        self.toggle_provider()

    def section(self, title, description):
        card = Panel()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(12)
        layout.addWidget(label(title, 'Section'))
        layout.addWidget(self.hint(description))
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)
        self.body.addWidget(card)
        return card, form

    def start_browser_login(self, site='douyin'):
        if self.browser_job:
            return
        self.browser_marker = data_root() / ('login-' + uuid.uuid4().hex + '.ready')
        self.browser_job = Job({'action': 'browser_login', 'site': site, 'settings': self.collect(), 'marker': str(self.browser_marker)}, self)
        self.browser_button.setEnabled(False)
        self.youtube_button.setEnabled(False)
        self.firefox_sync_button.setEnabled(False)
        self.browser_status.setText('正在打开独立登录浏览器…')
        self.browser_job.event.connect(self.browser_event)
        self.browser_job.ended.connect(self.browser_ended)
        self.browser_job.start()

    def browser_event(self, event):
        if event['event'] == 'browser_ready':
            self.browser_save.setEnabled(True)
        if event['event'] in ('browser_ready', 'done', 'error'):
            self.browser_status.setText(event.get('detail', ''))

    def finish_browser_login(self):
        if self.browser_job:
            self.browser_marker.touch()
            self.browser_save.setEnabled(False)
            self.browser_status.setText('正在加密保存会话…')

    def browser_ended(self, code):
        self.browser_save.setEnabled(False)
        self.browser_button.setEnabled(True)
        self.youtube_button.setEnabled(True)
        self.firefox_sync_button.setEnabled(True)
        if code and self.browser_status.text() in ('正在打开独立登录浏览器…', '正在加密保存会话…'):
            self.browser_status.setText('登录进程未完成，请重新打开登录。')
        self.browser_marker.unlink(missing_ok=True)
        if self.browser_job:
            self.browser_job.deleteLater()
        self.browser_job = None

    def open_firefox(self):
        from .firefox_sync import firefox_executable
        path = firefox_executable()
        if not path:
            self.browser_status.setText('未找到 Firefox，请先安装 Firefox，再点击此按钮。')
            return
        subprocess.Popen([path, 'https://www.youtube.com/watch?v=jNQXAC9IVRw'])
        self.browser_status.setText('请在正常 Firefox 窗口登录并播放 YouTube 视频，再点击下方同步按钮。')

    def sync_firefox(self):
        if self.browser_job:
            return
        self.browser_marker = data_root() / ('login-' + uuid.uuid4().hex + '.ready')
        self.browser_job = Job({'action': 'firefox_sync', 'settings': self.collect()}, self)
        self.browser_button.setEnabled(False)
        self.youtube_button.setEnabled(False)
        self.firefox_sync_button.setEnabled(False)
        self.browser_status.setText('正在同步 Firefox 的 YouTube 会话…')
        self.browser_job.event.connect(self.browser_event)
        self.browser_job.ended.connect(self.browser_ended)
        self.browser_job.start()

    def hint(self, text):
        widget = label(text, 'Muted', 12)
        widget.setWordWrap(True)
        return widget

    def add_field(self, form, key, name, placeholder, secret=False, picker=None):
        edit = QLineEdit(self.settings.get(key, ''))
        edit.setPlaceholderText(placeholder)
        edit.setMinimumWidth(250)
        self.fields[key] = edit
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        if secret:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            show = button('显示', small=True)
            show.setCheckable(True)
            show.toggled.connect(lambda checked, e=edit, b=show: (e.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password), b.setText('隐藏' if checked else '显示')))
            row.addWidget(show)
        if picker:
            row.addWidget(button('选择', lambda: self.pick(edit, picker), small=True))
        form.addRow(name, row)

    def pick(self, edit, kind):
        value = QFileDialog.getExistingDirectory(self, '选择目录', edit.text()) if kind == 'directory' else QFileDialog.getOpenFileName(self, '选择文件', edit.text())[0]
        if value:
            edit.setText(value)

    def collect(self):
        return DEFAULTS | {key: edit.text().strip() for key, edit in self.fields.items()} | {'provider': self.provider.currentData(), 'theme': self.theme_choice.currentData()}

    def toggle_provider(self):
        if not hasattr(self, 'custom_card'):
            return
        qoder = self.provider.currentData() == 'qoder'
        self.qoder_card.setVisible(qoder)
        self.custom_card.setVisible(not qoder)

    def doubao(self):
        self.fields['api_base'].setText('https://ark.cn-beijing.volces.com/api/v3')

    def save(self):
        values = self.collect()
        if not values['output']:
            QMessageBox.information(self, '保存目录', '请先选择默认保存目录。')
            return
        for key in ('api_base', 'asr_base'):
            if values[key]:
                try:
                    parse_urls(values[key])
                except ValueError as exc:
                    QMessageBox.warning(self, '接口地址', str(exc))
                    return
        self.saved.emit(values)

    def login(self):
        path = locate_qoder(self.fields['qoder_cli'].text().strip())
        if not path:
            QMessageBox.information(self, 'Qoder 登录', '未找到 Qoder CLI。请安装 Qoder CLI 并指定路径，或填写 Qoder 个人访问令牌 PAT。')
            return
        try:
            subprocess.Popen([path, 'login'], creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            self.test_result.setText('已打开 Qoder 登录终端。完成登录后，点击“测试总结连接”。')
        except OSError as exc:
            QMessageBox.warning(self, '无法打开登录', str(exc))

    def test(self):
        if self.test_job:
            return
        self.test_result.setText('正在连接，请稍候…')
        self.test_button.setEnabled(False)
        self.test_job = Job({'action': 'test', 'settings': self.collect()}, self)
        self.test_job.event.connect(self.test_event)
        self.test_job.ended.connect(self.test_ended)
        self.test_job.start()

    def test_event(self, event):
        if event['event'] in ('done', 'error'):
            self.test_result.setText(('✓ ' if event['event'] == 'done' else '连接失败：') + event['detail'])

    def test_ended(self, code):
        if self.test_result.text() == '正在连接，请稍候…':
            self.test_result.setText('连接测试未完成。请检查登录、配置或网络。')
        self.test_button.setEnabled(True)
        if self.test_job:
            self.test_job.deleteLater()
        self.test_job = None
