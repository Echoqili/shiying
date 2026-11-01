# Third-party software

Shiying uses the following independent components. Their respective licenses apply to those components; license texts available in the installed packages are copied to `licenses/` during the build.

- yt-dlp: https://github.com/yt-dlp/yt-dlp — Unlicense; additional bundled components have their own licenses.
- yt-dlp-ejs: https://github.com/yt-dlp/ejs — Unlicense and bundled MIT/ISC components.
- PySide6 / Qt for Python: https://www.qt.io/qt-for-python — LGPLv3/GPL/commercial. Qt libraries are distributed as replaceable dynamic libraries. Licensing information: https://www.qt.io/licensing/open-source-lgpl-obligations and source releases: https://download.qt.io/official_releases/QtForPython/ . No Qt libraries are modified by this application.
- Qoder Agent SDK / Qoder CLI: https://docs.qoder.com/zh/cli/sdk/overview . See the SDK package license and Qoder service terms at https://qoder.com/terms-of-service . Qoder is an external authenticated service; its credits and account permissions remain governed by Qoder.
- Requests and supporting Python packages: see `licenses/` and `DEPENDENCIES.txt`.
- Playwright: https://github.com/microsoft/playwright-python — Apache-2.0; uses the user's installed Edge/Chrome for user-driven login. Included driver notices remain in the Playwright package.
- Python: https://www.python.org/psf/license/ . PyInstaller: https://pyinstaller.org/en/stable/license.html .

## FFmpeg

The optional, unmodified shared GPL FFmpeg build used by the packaging script is obtained from https://github.com/yt-dlp/FFmpeg-Builds/releases/tag/latest . Build scripts and dependency source locations are available at https://github.com/yt-dlp/FFmpeg-Builds and the upstream source is https://ffmpeg.org/download.html .

The archive SHA256 and download URL used for this build are recorded in `tools/provenance.json`; the upstream GPL license is in `tools/LICENSE.txt`. The application invokes ffmpeg/ffprobe as separate executables. FFmpeg libraries remain replaceable in `tools/`. The executables' `-version` and `-buildconf` outputs identify their exact version and build configuration.

This source repository does not include third-party runtime binaries. The MIT license applies to this project’s own code, not to its dependencies. When redistributing packaged binaries, preserve these notices, review all included third-party licenses and supply any corresponding source required by the applicable license. Alternatively provide FFmpeg and Qoder externally through the application's configurable executable paths.

No Microsoft Windows fonts are distributed. The application uses fonts already installed on the user's system.
