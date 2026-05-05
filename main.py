"""
TIF查看器 V2 入口
"""
import sys
from PySide6.QtWidgets import QApplication

from config import app_icon
from styles import STYLE
from ui.main_window import TIFViewer


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)

    win = TIFViewer()
    screen = app.primaryScreen().availableGeometry()
    x = (screen.width() - win.width()) // 2
    y = (screen.height() - win.height()) // 2
    win.move(x, y)
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
