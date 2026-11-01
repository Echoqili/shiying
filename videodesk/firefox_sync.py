"""Read only the user's default Firefox YouTube cookies; never copy its database."""
import configparser
import os
import sqlite3
import time
from pathlib import Path

from .browser_login import save_session


def firefox_executable():
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe') as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if Path(value).is_file():
                        return value
            except OSError:
                pass
    for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        candidate = Path(os.environ.get(base, '')) / 'Mozilla Firefox' / 'firefox.exe'
        if candidate.is_file():
            return str(candidate)
    return ''


def default_profile(root=None):
    root = root or Path(os.environ.get('APPDATA', Path.home())) / 'Mozilla' / 'Firefox'
    config = configparser.ConfigParser()
    config.read(root / 'profiles.ini', encoding='utf-8-sig')
    installed = [root / config[s]['Default'] for s in config.sections()
                 if s.startswith('Install') and config[s].get('Default')]
    defaults, others = [], []
    for section in config.sections():
        if section.startswith('Profile') and config[section].get('Path'):
            path = Path(config[section]['Path'])
            if config[section].get('IsRelative', '1') == '1':
                path = root / path
            (defaults if config[section].get('Default') == '1' else others).append(path)
    for group in (installed, defaults, others):
        paths = list(dict.fromkeys(p.resolve() for p in group))
        if len(paths) == 1:
            if not (paths[0] / 'cookies.sqlite').is_file():
                raise ValueError('默认 Firefox 配置尚无会话数据库，请在默认普通窗口登录 YouTube 后重试；不会改读其他账号配置。')
            return paths[0]
        if len(paths) > 1:
            raise ValueError('发现多个 Firefox 默认配置，无法确定账号。请在 Firefox 设定常用默认配置后重试。')
    raise ValueError('未找到 Firefox 会话。请先安装并正常打开 Firefox，登录 YouTube 后再同步。')


def read_youtube_cookies(profile):
    path = Path(profile) / 'cookies.sqlite'
    cookies = []
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
        try:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(moz_cookies)')}
            origin_filter = " AND originAttributes = ''" if 'originAttributes' in columns else ''
            query = ("SELECT host,name,value,path,expiry,isSecure,isHttpOnly FROM moz_cookies "
                     "WHERE (host IN ('youtube.com','.youtube.com') OR host LIKE '%.youtube.com')" + origin_filter)
            for host, name, value, cookie_path, expiry, secure, http_only in connection.execute(query):
                if not value or expiry and expiry < time.time():
                    continue
                cookies.append({'domain': host, 'name': name, 'value': value, 'path': cookie_path or '/',
                                'expires': expiry or -1, 'secure': bool(secure), 'httpOnly': bool(http_only)})
        finally:
            connection.close()
    except sqlite3.Error:
        raise ValueError('无法读取 Firefox 的 YouTube 会话。请正常关闭 Firefox 后重新点击同步。') from None
    return cookies


def sync_youtube(emit):
    cookies = read_youtube_cookies(default_profile())
    markers = {'SAPISID', '__Secure-3PAPISID', 'LOGIN_INFO'}
    if not any(c['name'] in markers for c in cookies):
        raise ValueError('Firefox 中未找到已登录的 YouTube 会话。请用普通窗口登录并播放视频后，再点同步。')
    version = '140.0'
    executable = firefox_executable()
    if executable:
        config = configparser.ConfigParser()
        config.read(Path(executable).parent / 'application.ini', encoding='utf-8')
        version = config.get('App', 'Version', fallback=version)
    user_agent = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{version}) Gecko/20100101 Firefox/{version}'
    save_session(cookies, user_agent, 'youtube')
    emit('done', detail='Firefox 的 YouTube 登录状态已同步并加密保存，可以重试下载。')
