# Windows 安装

下载地址：https://github.com/Echoqili/shiying/releases/latest

适用于 Windows 10/11 64 位，无需安装 Python、Git 或 Node.js。

## 安装版（推荐）

下载文件名以 `windows-x64-setup.exe` 结尾的安装包，双击并按提示安装。安装完成后使用桌面上的「拾影 Shiying」快捷方式启动；可在 Windows 设置中卸载。默认安装到当前用户目录，无需管理员权限。

## 免安装版

下载文件名以 `windows-x64.zip` 结尾的压缩包，右键选择「全部解压」，进入 `Shiying` 文件夹，双击 `Shiying.exe`。请保留整个文件夹，包括 `_internal`，不要直接在压缩包内运行或仅移动 EXE。

下载页的 `Source code` 是开发者源码，不是安装包。`SHA256SUMS.txt` 提供发行文件校验值。

## 第一次使用

粘贴视频链接、选择画质和保存目录，然后开始下载。FFmpeg 和音视频合并工具已包含在发行版中。

AI 功能需在设置中登录自己的 Qoder 账号，或配置自己的总结和语音转写服务；发行版不附带账号、密钥或 AI 额度。抖音登录需安装 Edge 或 Chrome；YouTube 登录同步需安装 Firefox。

安装包暂未进行代码签名。仅从本项目 Releases 下载；如系统提示未知发布者，可先用 `Get-FileHash <下载文件路径> -Algorithm SHA256` 对照校验值确认文件。

设置和任务保存在 `%LOCALAPPDATA%/Shiying`，下载视频在用户选择的目录。升级前退出应用；卸载会保留这些个人数据。
