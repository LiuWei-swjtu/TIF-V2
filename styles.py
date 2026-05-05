STYLE = """
QMainWindow { background: #ffffff; }
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #f8f8f8, stop:1 #e8e8e8);
    border-bottom: 1px solid #ccc; padding: 5px; spacing: 6px;
}
QPushButton {
    background: #4a86c8; color: white; border: none;
    padding: 6px 14px; border-radius: 4px; font-weight: bold;
}
QPushButton:hover { background: #5a96d8; }
QPushButton:pressed { background: #3a76b8; }
QPushButton:disabled { background: #aaa; }
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {
    background: #fff; color: #333; border: 1px solid #ccc;
    padding: 4px 8px; border-radius: 3px;
}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover, QLineEdit:hover {
    border-color: #4a86c8;
}
QComboBox QAbstractItemView {
    background: #fff; color: #333;
    selection-background-color: #4a86c8; selection-color: #fff;
}
QLabel { color: #444; }
QStatusBar { background: #f5f5f5; color: #555; border-top: 1px solid #ddd; padding: 3px; }
QDockWidget {
    font-weight: bold; color: #333;
}
QDockWidget::title {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #f0f0f0, stop:1 #ddd);
    padding: 6px; border-bottom: 1px solid #bbb;
}
QGroupBox {
    font-weight: bold; color: #444;
    border: 1px solid #ccc; border-radius: 5px;
    margin-top: 8px; padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
}
QListWidget {
    background: #fafafa; border: 1px solid #ccc; border-radius: 3px;
    outline: none;
}
QListWidget::item {
    padding: 5px 4px; border-bottom: 1px solid #eee;
}
QListWidget::item:selected {
    background: #d0e4f7; color: #222;
}
QCheckBox { color: #444; spacing: 6px; }
QSlider::groove:horizontal {
    border: 1px solid #bbb; height: 6px; border-radius: 3px;
    background: #ddd;
}
QSlider::handle:horizontal {
    background: #4a86c8; width: 14px; margin: -4px 0;
    border-radius: 7px;
}
QScrollArea { border: none; }
QTabWidget::pane { border: 1px solid #ccc; }
QTableWidget {
    gridline-color: #ddd; background: #fff;
    selection-background-color: #d0e4f7;
}
QHeaderView::section {
    background: #f0f0f0; padding: 4px;
    border: 1px solid #ddd; font-weight: bold;
}
QRadioButton { color: #444; spacing: 6px; }
QFontComboBox { min-width: 120px; }
"""
