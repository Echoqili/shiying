from __future__ import annotations

import os
import sys


def worker_stdio():
    if os.name == 'nt' and (sys.stdin is None or sys.stdout is None):
        import ctypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.restype = ctypes.c_void_p
        for name, number, flags, mode in [('stdin', -10, os.O_RDONLY, 'r'), ('stdout', -11, os.O_WRONLY, 'w'), ('stderr', -12, os.O_WRONLY, 'w')]:
            if getattr(sys, name) is None:
                handle = kernel.GetStdHandle(number)
                if handle and handle != ctypes.c_void_p(-1).value:
                    descriptor = msvcrt.open_osfhandle(handle, flags | os.O_BINARY)
                    stream = os.fdopen(descriptor, mode, encoding='utf-8', errors='replace', buffering=1)
                    setattr(sys, name, stream)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if stream and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')


def main():
    if '--worker' in sys.argv:
        worker_stdio()
        from videodesk.worker import main as run_worker
        return run_worker()
    if '--smoke' in sys.argv:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    from videodesk.theme import STYLE, app_icon
    from videodesk.ui import MainWindow

    app = QApplication(sys.argv)
    # Windows' offscreen Qt plugin does not discover system fonts automatically.
    # Register existing system fonts; no Microsoft fonts are redistributed.
    if not QFontDatabase.families():
        for filename in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
            font_path = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', filename)
            if os.path.isfile(font_path):
                QFontDatabase.addApplicationFont(font_path)
    app.setApplicationName('Shiying')
    app.setOrganizationName('Shiying')
    app.setWindowIcon(app_icon())
    app.setFont(QFont('Microsoft YaHei UI', 10))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    if '--smoke' in sys.argv:
        def capture():
            if '--screenshot' in sys.argv:
                filename = sys.argv[sys.argv.index('--screenshot') + 1]
                window.grab().save(filename)
            window.close()
            app.quit()
        QTimer.singleShot(900, capture)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
