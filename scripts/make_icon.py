import os
import struct
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from videodesk.theme import app_icon

app = QApplication([])
directory = Path(__file__).resolve().parent.parent / 'assets'
directory.mkdir(exist_ok=True)
app_icon().pixmap(128, 128).save(str(directory / 'app.png'))
data = (directory / 'app.png').read_bytes()
(directory / 'app.ico').write_bytes(struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', 128, 128, 0, 0, 1, 32, len(data), 22) + data)
