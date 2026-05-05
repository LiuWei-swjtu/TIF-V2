"""
色带管理对话框：添加、删除 colormap
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QGroupBox, QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import QSize

from config import app_icon
from colormap import CMAP_STORE


class CMapManagerDialog(QDialog):
    """色带增删管理"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(app_icon())
        self.setWindowTitle('色带管理')
        self.setMinimumSize(400, 500)
        layout = QVBoxLayout(self)

        # 添加区
        add_grp = QGroupBox('添加色带')
        add_l = QHBoxLayout(add_grp)
        self._add_edit = QLineEdit()
        self._add_edit.setPlaceholderText('输入 matplotlib 色带名称')
        add_l.addWidget(self._add_edit)
        btn_add = QPushButton('添加')
        btn_add.clicked.connect(self._add)
        add_l.addWidget(btn_add)
        layout.addWidget(add_grp)

        # 列表
        self._list = QListWidget()
        self._list.setIconSize(QSize(120, 18))
        self._refresh_list()
        layout.addWidget(self._list)

        # 删除按钮
        btn_del = QPushButton('删除选中色带')
        btn_del.clicked.connect(self._delete)
        layout.addWidget(btn_del)

        # 关闭
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.close)
        layout.addWidget(bb)

    def _refresh_list(self):
        self._list.clear()
        for n in CMAP_STORE.names:
            item = QListWidgetItem(CMAP_STORE.icon(n), n)
            self._list.addItem(item)

    def _add(self):
        name = self._add_edit.text().strip()
        if not name:
            return
        if CMAP_STORE.add(name):
            self._refresh_list()
            self._add_edit.clear()
        else:
            QMessageBox.warning(self, '错误', f'无法添加色带 "{name}"，请确认名称正确')

    def _delete(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.text()
        if CMAP_STORE.remove(name):
            self._refresh_list()
        else:
            QMessageBox.information(self, '提示', f'"{name}" 为内置基础色带，不可删除')
