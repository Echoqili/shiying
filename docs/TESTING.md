# 测试说明

自动测试面向 Windows，使用合成媒体、本地 HTTP 服务、模拟 AI 接口与临时浏览器数据库，不需要真实账号或 AI 额度。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖下载队列、取消和失败恢复、字幕容错、播放列表确认、DPAPI 密钥保护、只读 Firefox 会话同步、音频分段检查点与 H.264/AAC 兼容转换。浏览器测试需要安装 Microsoft Edge；媒体测试需要 `tools/` 下的 FFmpeg 和 ffprobe。

构建后可执行 `scripts/verify_packaged.py` 验证打包应用的界面、工作进程通信、下载和模拟 AI 协议。自动测试不验证真实 Qoder 或其他收费 AI 服务的账号权限。

`scripts/test_live_sites.py` 是手动联网测试入口，需要先构建 `dist/Shiying/Shiying.exe`。它会下载公开视频样本，并在本地生成报告，不在 CI 中执行。曾对 YouTube、Bilibili、TikTok 和登录后的抖音样本进行测试；网站策略、账号和具体视频会影响结果，样本成功不代表全站保证。
