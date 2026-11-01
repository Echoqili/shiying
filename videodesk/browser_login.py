"""User-driven Douyin login in an isolated Playwright browser context."""
import asyncio
import json
import time
from http.cookiejar import Cookie

from .core import atomic_json, data_root, protect, read_json


def site_cookies(cookies, site='douyin'):
    domain = {'douyin': 'douyin.com', 'youtube': 'youtube.com'}[site]
    return [c for c in cookies if c.get('domain', '').lstrip('.') == domain
            or c.get('domain', '').lstrip('.').endswith('.' + domain)]


def douyin_cookies(cookies):
    return site_cookies(cookies)


def session_path(site='douyin'):
    if site not in ('douyin', 'youtube'):
        raise ValueError('不支持的登录站点')
    return data_root() / (site + '-session.json')


def save_session(cookies, user_agent, site='douyin'):
    cookies = site_cookies(cookies, site)
    if not cookies:
        raise ValueError('没有获取到该站点 Cookies，请先在浏览器打开网站并完成登录。')
    atomic_json(session_path(site), {'encrypted': protect(json.dumps({'cookies': cookies, 'user_agent': user_agent}))})
    markers = ('sessionid', 'sessionid_ss', 'sid_guard') if site == 'douyin' else ('SAPISID', '__Secure-3PAPISID', 'LOGIN_INFO')
    return any(c['name'] in markers for c in cookies)


def load_session(site='douyin'):
    value = read_json(session_path(site), {})
    if not value.get('encrypted'):
        return {}
    try:
        return json.loads(protect(value['encrypted'], decrypt=True))
    except (OSError, ValueError, TypeError):
        raise ValueError('登录会话无法读取，请重新登录该站点。') from None


def apply_session(ydl, session, site='douyin'):
    for item in site_cookies(session.get('cookies', []), site):
        expires = item.get('expires', -1)
        if expires > 0 and expires <= time.time():
            continue
        domain = item['domain']
        ydl.cookiejar.set_cookie(Cookie(
            version=0, name=item['name'], value=item['value'], port=None, port_specified=False,
            domain=domain, domain_specified=domain.startswith('.'), domain_initial_dot=domain.startswith('.'),
            path=item.get('path') or '/', path_specified=True, secure=item.get('secure', False),
            expires=int(expires) if expires > 0 else None, discard=expires <= 0,
            comment=None, comment_url=None, rest={'HttpOnly': item.get('httpOnly', False)}, rfc2109=False))


async def login(marker, emit, site='douyin'):
    from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout

    async with async_playwright() as pw:
        browser = None
        for channel in ('msedge', 'chrome'):
            try:
                browser = await pw.chromium.launch(channel=channel, headless=False)
                break
            except Exception:
                continue
        if browser is None:
            raise RuntimeError('无法启动登录浏览器，请先安装 Microsoft Edge 或 Google Chrome。')
        try:
            context = await browser.new_context(viewport={'width': 1200, 'height': 800})
            page = await context.new_page()
            try:
                await page.goto({'douyin': 'https://www.douyin.com/', 'youtube': 'https://www.youtube.com/watch?v=jNQXAC9IVRw'}[site], wait_until='domcontentloaded', timeout=45000)
            except BrowserTimeout:
                emit('log', detail='网页加载较慢，请在浏览器中完成登录。')
            emit('browser_ready', detail='请在新窗口完成登录或验证，然后点击“完成登录，保存”。')
            deadline = time.monotonic() + 600
            while not marker.is_file():
                if not browser.is_connected() or page.is_closed():
                    raise RuntimeError('登录窗口已关闭，尚未保存。请重新打开登录。')
                if time.monotonic() > deadline:
                    raise RuntimeError('登录等待超时，请重新打开登录。')
                await asyncio.sleep(.3)
            signed_in = save_session(await context.cookies(), await page.evaluate('navigator.userAgent'), site)
            emit('done', detail='登录会话已加密保存，可以重试下载。' if signed_in else '已保存浏览器会话，但未检测到登录标记；如下载失败，请重新登录。')
        finally:
            marker.unlink(missing_ok=True)
            await browser.close()


async def resolve_video(url, session, emit):
    """Observe a normally playing video; leave any website verification to the user."""
    from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
    import re

    async with async_playwright() as pw:
        browser = None
        for channel in ('msedge', 'chrome'):
            try:
                browser = await pw.chromium.launch(channel=channel, headless=False)
                break
            except Exception:
                continue
        if not browser:
            raise RuntimeError('无法打开 Edge/Chrome 获取视频播放地址。')
        try:
            context = await browser.new_context(user_agent=session.get('user_agent') or None)
            await context.add_cookies(session.get('cookies', []))
            page = await context.new_page()
            details = {}

            async def response_received(response):
                if response.status != 200 or '/aweme/' not in response.url:
                    return
                try:
                    payload = await response.json()
                    items = [payload.get('aweme_detail')] + (payload.get('aweme_list') or [])
                    for item in items:
                        if isinstance(item, dict) and item.get('aweme_id'):
                            details[str(item['aweme_id'])] = item
                except Exception:
                    pass

            page.on('response', response_received)
            emit('progress', status='analyzing', detail='正在浏览器中获取播放地址；如遇验证，请在窗口中完成')
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            except BrowserTimeout:
                pass
            try:
                await page.locator('video').first.evaluate('(video) => { video.muted = true; video.play().catch(() => {}); }', timeout=5000)
            except Exception:
                pass
            video_id = re.search(r'/video/(\d+)', page.url)
            if not video_id:
                raise RuntimeError('页面未打开目标抖音视频，请检查链接或完成页面验证。')
            deadline = time.monotonic() + 90
            while video_id[1] not in details:
                if page.is_closed() or time.monotonic() > deadline:
                    raise RuntimeError('浏览器未获取到目标视频详情；请确认此账号可播放该视频并完成页面验证。')
                await asyncio.sleep(.3)
            item = details[video_id[1]]
            video = item.get('video') or {}
            addresses = (video.get('play_addr') or {}).get('url_list') or []
            if not addresses:
                raise RuntimeError('目标视频详情没有可下载的播放地址。')
            return {'id': video_id[1], 'title': item.get('desc') or '抖音视频',
                    'url': addresses[0], 'ext': 'mp4', 'webpage_url': url,
                    'duration': (video.get('duration') or 0) / 1000,
                    'http_headers': {'Referer': 'https://www.douyin.com/', 'User-Agent': session.get('user_agent', '')}}
        finally:
            await browser.close()
