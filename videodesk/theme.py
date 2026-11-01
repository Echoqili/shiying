from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


DARK_STYLE = '''
QWidget { background: #101416; color: #eef1ee; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; }
QMainWindow { background: #101416; }
QFrame#Sidebar { background: #14191b; border-right: 1px solid #283034; }
QFrame#Panel { background: #191f22; border: 1px solid #30383c; border-radius: 14px; }
QFrame#TaskCard { background: #191f22; border: 1px solid #2c3539; border-radius: 12px; }
QFrame#Panel QLabel, QFrame#TaskCard QLabel { background: transparent; }
QLabel#Muted { color: #89969b; background: transparent; }
QLabel#Title { font-size: 30px; font-weight: 700; letter-spacing: 1px; }
QLabel#Section { font-size: 17px; font-weight: 600; }
QLabel#Brand { font-size: 23px; font-weight: 700; letter-spacing: 3px; background: transparent; }
QLabel#Eyebrow { color: #b7ef85; font-size: 11px; letter-spacing: 2px; background: transparent; }
QPushButton { background: #222b2f; border: 1px solid #364247; border-radius: 8px; padding: 9px 15px; font-weight: 500; }
QPushButton:hover { background: #303c40; border-color: #66767b; }
QPushButton:pressed { background: #37464a; }
QPushButton:disabled { color: #667278; border-color: #2d363a; background: #20282b; }
QPushButton#Primary { background: #b7ef85; color: #152111; border: none; font-weight: 700; padding: 11px 22px; }
QPushButton#Primary:hover { background: #c8ffa0; }
QPushButton#Primary:disabled { background: #4d633c; color: #a1b192; }
QPushButton#Nav { text-align: left; padding: 13px 20px; border: none; background: transparent; color: #94a1a6; font-size: 14px; }
QPushButton#Nav:checked { background: #28352a; color: #c4f1a2; }
QPushButton#Nav:hover { background: #222b2e; color: #eef1ee; }
QPushButton#Small { padding: 6px 12px; font-size: 12px; }
QLineEdit, QPlainTextEdit, QTextEdit { background: #111719; color: #e5ece7; border: 1px solid #354044; border-radius: 8px; padding: 10px; selection-background-color: #4b693c; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #a0ce7e; }
QComboBox { background: #20292d; border: 1px solid #39474c; border-radius: 7px; padding: 8px 12px; min-width: 80px; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox QAbstractItemView { background: #222b2f; selection-background-color: #3a4e35; padding: 6px; border: 1px solid #46544d; }
QCheckBox { spacing: 8px; background: transparent; color: #b6c2c5; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px; border: 1px solid #526369; background: #172023; }
QCheckBox::indicator:checked { background: #a5d77b; border: 1px solid #b7ef85; image: none; }
QProgressBar { border: none; background: #2c373c; border-radius: 3px; height: 5px; text-align: center; }
QProgressBar::chunk { background: #b7ef85; border-radius: 3px; }
QListWidget { border: none; outline: none; background: transparent; }
QListWidget::item { border: none; padding: 0; margin: 0; background: transparent; }
QListWidget::item:selected { background: transparent; }
QListWidget#NoteList::item { padding: 15px 10px; border-bottom: 1px solid #283237; color: #adbabe; }
QListWidget#NoteList::item:selected { background: #29382c; color: #c5f0a4; border-radius: 7px; }
QTextBrowser { border: 1px solid #303c40; border-radius: 12px; background: #171e21; padding: 24px; color: #d9e2dd; selection-background-color: #4b693c; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 7px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: #3a464b; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { color: #edf4ed; background: #28352e; border: 1px solid #52644b; padding: 6px; }
QSplitter::handle { background: transparent; width: 14px; }
QDialog { background: #151c1f; }
'''


LIGHT_COLORS = {
    '#101416': '#f5f1e8', '#14191b': '#eee9df', '#191f22': '#fffcf6',
    '#111719': '#f8f5ee', '#171e21': '#fffcf6', '#151c1f': '#f5f1e8',
    '#eef1ee': '#29362f', '#e5ece7': '#29362f', '#d9e2dd': '#29362f',
    '#89969b': '#6f766d', '#94a1a6': '#68756a', '#b6c2c5': '#536353',
    '#adbabe': '#61705f', '#b7ef85': '#52704d', '#152111': '#ffffff',
    '#17251b': '#ffffff', '#c8ffa0': '#63845b', '#c4f1a2': '#355b33',
    '#c5f0a4': '#355b33',
    '#28352a': '#dfe7d7', '#29382c': '#dfe7d7', '#222b2e': '#e8e9dd',
    '#222b2f': '#f1eee4', '#20292d': '#f1eee4', '#303c40': '#e6e7da',
    '#37464a': '#dce3d2', '#20282b': '#ebe8df', '#2a372f': '#e4eadb',
    '#b4cdab': '#52704d', '#a5b9a0': '#627b59', '#b0bfc4': '#62715c',
    '#acbabf': '#62715c', '#728b6d': '#728b6d',
    '#283034': '#d9d6cb', '#30383c': '#dedbcf', '#2c3539': '#dedbcf',
    '#364247': '#d2d5c7', '#354044': '#d2d5c7', '#39474c': '#d2d5c7',
    '#283237': '#dfdfd2', '#2c373c': '#e2e5d8',
    '#3a464b': '#c9cdbf', '#526369': '#a9b49e', '#172023': '#faf8f1',
    '#a5d77b': '#52704d', '#9ecbff': '#3e6595', '#cfb8ff': '#795498',
    '#d8c1ff': '#795498', '#eea09b': '#a24d45', '#e7bf86': '#936727',
    '#aeb8bd': '#657164', '#92a1a8': '#657164', '#eaf2e6': '#29362f',
    '#8ea298': '#6f766d', '#4b693c': '#c9dbb8', '#3a4e35': '#dce7d1',
    '#46544d': '#c3ceba', '#edf4ed': '#29362f', '#28352e': '#edf0e3',
}
_theme = 'cream'


def themed(value):
    import re
    if _theme == 'dark':
        return value
    return re.sub(r'#[0-9a-fA-F]{6}', lambda match: LIGHT_COLORS.get(match[0].lower(), match[0]), value)


STYLE = themed(DARK_STYLE)


def apply_theme(app, theme='cream'):
    global _theme
    _theme = 'dark' if theme == 'dark' else 'cream'
    app.setStyleSheet(themed(DARK_STYLE))
    from PySide6.QtWidgets import QTextBrowser
    for widget in app.allWidgets():
        current = widget.styleSheet()
        original = widget.property('theme_original')
        if original is None or current != widget.property('theme_applied'):
            original = current
            widget.setProperty('theme_original', original)
        converted = themed(original)
        if current != converted:
            widget.setStyleSheet(converted)
        widget.setProperty('theme_applied', converted)
        if isinstance(widget, QTextBrowser):
            document = widget.document()
            base = widget.property('theme_document') or document.defaultStyleSheet()
            widget.setProperty('theme_document', base)
            document.setDefaultStyleSheet(themed(base))


def icon(name, color='#acbabf', size=24):
    color = themed(color)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24, size / 24)
    painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if name in ('download', 'arrow'):
        painter.drawLine(12, 3, 12, 15)
        painter.drawLine(7, 10, 12, 15)
        painter.drawLine(17, 10, 12, 15)
        painter.drawLine(4, 17, 4, 21)
        painter.drawLine(4, 21, 20, 21)
        painter.drawLine(20, 21, 20, 17)
    elif name == 'notes':
        painter.drawRoundedRect(QRectF(5, 3, 14, 18), 2, 2)
        for y, width in [(8, 8), (12, 8), (16, 5)]:
            painter.drawLine(8, y, 8 + width, y)
    elif name == 'settings':
        painter.drawEllipse(QRectF(4, 4, 16, 16))
        painter.drawEllipse(QRectF(9, 9, 6, 6))
        for x1, y1, x2, y2 in [(12, 1, 12, 4), (12, 20, 12, 23), (1, 12, 4, 12), (20, 12, 23, 12)]:
            painter.drawLine(x1, y1, x2, y2)
    elif name == 'folder':
        path = QPainterPath()
        path.moveTo(3, 6)
        for point in [(10, 6), (12, 9), (21, 9), (21, 20), (3, 20), (3, 6)]:
            path.lineTo(*point)
        painter.drawPath(path)
    elif name == 'spark':
        path = QPainterPath()
        path.moveTo(12, 2)
        for point in [(15, 9), (22, 12), (15, 15), (12, 22), (9, 15), (2, 12), (9, 9), (12, 2)]:
            path.lineTo(*point)
        painter.drawPath(path)
    elif name == 'play':
        painter.setBrush(QColor(color))
        path = QPainterPath()
        path.moveTo(8, 5)
        path.lineTo(20, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == 'plus':
        painter.drawLine(12, 5, 12, 19)
        painter.drawLine(5, 12, 19, 12)
    elif name == 'paste':
        painter.drawRoundedRect(QRectF(5, 5, 14, 16), 2, 2)
        painter.drawRoundedRect(QRectF(9, 2, 6, 5), 1, 1)
    painter.end()
    return QIcon(pixmap)


def app_icon():
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#b7ef85'))
    painter.drawRoundedRect(QRectF(4, 4, 120, 120), 30, 30)
    painter.setBrush(QColor('#17251b'))
    path = QPainterPath()
    path.moveTo(46, 33)
    path.lineTo(93, 64)
    path.lineTo(46, 95)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)
