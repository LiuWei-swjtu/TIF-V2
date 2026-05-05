"""
图层面板：左侧图层管理 DockWidget
"""
import re
from typing import Optional

from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox,
    QLineEdit, QListWidget, QListWidgetItem, QGroupBox, QLabel,
    QColorDialog, QMenu, QSizePolicy, QSlider
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QColor

from colormap import CMAP_STORE
from layer import LayerInfo


class LayerPanel(QDockWidget):
    """左侧图层管理面板"""

    layer_changed = Signal()
    layer_selected = Signal(str)  # layer id
    request_zoom = Signal(str)  # layer id
    request_add_layer = Signal()  # 请求添加图层，由主窗口连接

    def __init__(self, parent=None):
        super().__init__('图层管理', parent)
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 工具条
        tool_row = QHBoxLayout()
        self._btn_add = QPushButton('添加图层')
        self._btn_add.clicked.connect(self._on_add_clicked)
        tool_row.addWidget(self._btn_add)
        tool_row.addStretch()
        main_layout.addLayout(tool_row)

        # 图层列表
        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.setDefaultDropAction(Qt.MoveAction)
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._ctx_menu)
        self._list.currentRowChanged.connect(self._on_select)
        self._list.model().rowsMoved.connect(self._on_reorder)
        main_layout.addWidget(self._list, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        self._btn_up = QPushButton('▲')
        self._btn_up.setFixedWidth(36)
        self._btn_up.setToolTip('上移图层')
        self._btn_up.clicked.connect(self._move_up)
        btn_row.addWidget(self._btn_up)

        self._btn_down = QPushButton('▼')
        self._btn_down.setFixedWidth(36)
        self._btn_down.setToolTip('下移图层')
        self._btn_down.clicked.connect(self._move_down)
        btn_row.addWidget(self._btn_down)

        btn_row.addStretch()

        self._btn_remove = QPushButton('移除')
        self._btn_remove.clicked.connect(self._remove_current)
        btn_row.addWidget(self._btn_remove)
        main_layout.addLayout(btn_row)

        # 属性区 (选中图层的属性)
        self._props = QGroupBox('图层属性')
        self._props_layout = QFormLayout(self._props)
        self._props_layout.setContentsMargins(6, 10, 6, 6)
        self._props.setMaximumHeight(300)

        # 通用属性
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(0, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.valueChanged.connect(self._on_opacity)
        self._props_layout.addRow('透明度:', self._opacity_slider)

        # 栅格属性
        self._raster_widget = QWidget()
        r_layout = QFormLayout(self._raster_widget)
        r_layout.setContentsMargins(0, 0, 0, 0)

        self._band_mode_cb = QComboBox()
        self._band_mode_cb.addItems(['单波段', '多波段彩色'])
        self._band_mode_cb.currentIndexChanged.connect(self._on_band_mode)
        r_layout.addRow('模式:', self._band_mode_cb)

        self._band_cb = QComboBox()
        self._band_cb.currentIndexChanged.connect(self._on_band_changed)
        r_layout.addRow('波段:', self._band_cb)

        # RGB行
        self._rgb_widget = QWidget()
        rgb_l = QHBoxLayout(self._rgb_widget)
        rgb_l.setContentsMargins(0, 0, 0, 0)
        self._r_cb = QComboBox()
        self._g_cb = QComboBox()
        self._b_cb = QComboBox()
        rgb_l.addWidget(QLabel('R:'))
        rgb_l.addWidget(self._r_cb)
        rgb_l.addWidget(QLabel('G:'))
        rgb_l.addWidget(self._g_cb)
        rgb_l.addWidget(QLabel('B:'))
        rgb_l.addWidget(self._b_cb)
        self._r_cb.currentIndexChanged.connect(self._on_band_changed)
        self._g_cb.currentIndexChanged.connect(self._on_band_changed)
        self._b_cb.currentIndexChanged.connect(self._on_band_changed)
        r_layout.addRow('RGB:', self._rgb_widget)
        self._rgb_widget.hide()

        self._cmap_cb = QComboBox()
        self._cmap_cb.setIconSize(QSize(80, 14))
        self._cmap_cb.setMaxVisibleItems(15)
        self._cmap_cb.setStyleSheet("QComboBox { combobox-popup: 0; }")
        self._refresh_cmap_list()
        self._cmap_cb.currentTextChanged.connect(self._on_cmap)
        r_layout.addRow('色带:', self._cmap_cb)

        self._reverse_cb = QCheckBox('反转色带')
        self._reverse_cb.toggled.connect(self._on_reverse)
        r_layout.addRow('', self._reverse_cb)

        self._stretch_cb = QComboBox()
        self._stretch_cb.addItems(['百分比截断', '全局最值', '标准差拉伸', '直方图均衡化'])
        self._stretch_cb.currentTextChanged.connect(self._on_stretch)
        r_layout.addRow('拉伸:', self._stretch_cb)

        self._std_spin = QDoubleSpinBox()
        self._std_spin.setRange(0.1, 10.0)
        self._std_spin.setValue(2.0)
        self._std_spin.setSingleStep(0.5)
        self._std_spin.valueChanged.connect(self._on_band_changed)
        r_layout.addRow('标准差倍数:', self._std_spin)

        self._ignore_edit = QLineEdit('-9999,')
        self._ignore_edit.editingFinished.connect(self._on_ignore)
        r_layout.addRow('忽略值:', self._ignore_edit)

        self._props_layout.addRow(self._raster_widget)

        # 矢量属性
        self._vector_widget = QWidget()
        v_layout = QFormLayout(self._vector_widget)
        v_layout.setContentsMargins(0, 0, 0, 0)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(60, 24)
        self._color_btn.clicked.connect(self._pick_color)
        v_layout.addRow('线条颜色:', self._color_btn)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 10)
        self._width_spin.setValue(2)
        self._width_spin.valueChanged.connect(self._on_vec_style)
        v_layout.addRow('线条宽度:', self._width_spin)

        self._props_layout.addRow(self._vector_widget)
        self._vector_widget.hide()
        self._raster_widget.hide()

        main_layout.addWidget(self._props)
        self.setWidget(container)

        self._layers: list[LayerInfo] = []
        self._block = False

    # -- 公共接口 --
    @property
    def layers(self):
        return self._layers

    def add_layer(self, layer: LayerInfo):
        self._layers.insert(0, layer)
        self._sync_list()
        self._list.setCurrentRow(0)
        self.layer_changed.emit()

    def get_layer(self, lid):
        for l in self._layers:
            if l.id == lid:
                return l
        return None

    def selected_layer(self) -> Optional[LayerInfo]:
        row = self._list.currentRow()
        if 0 <= row < len(self._layers):
            return self._layers[row]
        return None

    def raster_layers(self):
        return [l for l in self._layers if l.layer_type == 'raster']

    def vector_layers(self):
        return [l for l in self._layers if l.layer_type == 'vector']

    def refresh_cmap_combo(self):
        self._refresh_cmap_list()

    # -- 内部 --
    def _refresh_cmap_list(self):
        self._cmap_cb.blockSignals(True)
        cur = self._cmap_cb.currentText()
        self._cmap_cb.clear()
        for n in CMAP_STORE.names:
            self._cmap_cb.addItem(CMAP_STORE.icon(n), n)
        idx = self._cmap_cb.findText(cur)
        if idx >= 0:
            self._cmap_cb.setCurrentIndex(idx)
        self._cmap_cb.blockSignals(False)

    def _sync_list(self):
        self._block = True
        try:
            self._list.itemChanged.disconnect(self._on_check)
        except (TypeError, RuntimeError):
            pass
        self._list.blockSignals(True)
        self._list.clear()
        for layer in self._layers:
            prefix = '🗺' if layer.layer_type == 'raster' else '📐'
            vis = '✓' if layer.visible else '✗'
            text = f'{vis} {prefix} {layer.name}'
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, layer.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if layer.visible else Qt.Unchecked)
            self._list.addItem(item)
        self._list.blockSignals(False)
        self._list.itemChanged.connect(self._on_check)
        self._block = False

    def _on_check(self, item):
        if self._block:
            return
        lid = item.data(Qt.UserRole)
        layer = self.get_layer(lid)
        if layer:
            layer.visible = (item.checkState() == Qt.Checked)
            prefix = '🗺' if layer.layer_type == 'raster' else '📐'
            vis = '✓' if layer.visible else '✗'
            self._block = True
            item.setText(f'{vis} {prefix} {layer.name}')
            self._block = False
            self.layer_changed.emit()

    def _on_select(self, row):
        if self._block or row < 0 or row >= len(self._layers):
            self._raster_widget.hide()
            self._vector_widget.hide()
            return
        layer = self._layers[row]
        self._block = True
        self._opacity_slider.setValue(int(layer.opacity * 100))

        if layer.layer_type == 'raster':
            self._raster_widget.show()
            self._vector_widget.hide()
            rr = layer.reader
            if rr:
                if rr.bands < 3:
                    layer.band_mode = 'single'
                self._band_mode_cb.setEnabled(rr.bands >= 3)
                self._band_mode_cb.setCurrentIndex(0 if layer.band_mode == 'single' else 1)
                self._band_cb.clear()
                for i in range(rr.bands):
                    self._band_cb.addItem(f'Band {i+1}')
                self._band_cb.setCurrentIndex(min(max(layer.band - 1, 0), rr.bands - 1))

                for cb in [self._r_cb, self._g_cb, self._b_cb]:
                    cb.clear()
                    for i in range(rr.bands):
                        cb.addItem(f'Band {i+1}')
                if rr.bands >= 3:
                    layer.rgb_bands = [min(max(int(b), 1), rr.bands) for b in layer.rgb_bands]
                    self._r_cb.setCurrentIndex(layer.rgb_bands[0] - 1)
                    self._g_cb.setCurrentIndex(layer.rgb_bands[1] - 1)
                    self._b_cb.setCurrentIndex(layer.rgb_bands[2] - 1)

                self._on_band_mode(self._band_mode_cb.currentIndex())

                idx = self._cmap_cb.findText(layer.colormap)
                if idx >= 0:
                    self._cmap_cb.setCurrentIndex(idx)
                self._reverse_cb.setChecked(layer.cmap_reverse)
                self._stretch_cb.setCurrentText(layer.stretch)
                self._std_spin.setValue(layer.std_n)
                self._ignore_edit.setText(layer.ignore_text)

        elif layer.layer_type == 'vector':
            self._vector_widget.show()
            self._raster_widget.hide()
            self._color_btn.setStyleSheet(
                f'background-color: {layer.pen_color}; border: 1px solid #999;')
            self._width_spin.setValue(layer.pen_width)
        else:
            self._raster_widget.hide()
            self._vector_widget.hide()

        self._block = False
        self.layer_selected.emit(layer.id)

    def _on_opacity(self, val):
        layer = self.selected_layer()
        if layer and not self._block:
            layer.opacity = val / 100.0
            if layer.image_item:
                layer.image_item.setOpacity(layer.opacity)
            if layer.graphics_item:
                layer.graphics_item.setOpacity(layer.opacity)

    def _on_band_mode(self, idx):
        layer = self.selected_layer()
        if layer and layer.reader and layer.reader.bands < 3:
            idx = 0
        is_single = (idx == 0)
        self._band_cb.setVisible(is_single)
        self._rgb_widget.setVisible(not is_single)
        if layer and not self._block:
            layer.band_mode = 'single' if is_single else 'rgb'
            self.layer_changed.emit()

    def _on_band_changed(self, *args):
        layer = self.selected_layer()
        if layer and not self._block and layer.layer_type == 'raster':
            count = layer.reader.bands if layer.reader else 1
            def idx_to_band(cb):
                return min(max(cb.currentIndex() + 1, 1), count)
            layer.band = idx_to_band(self._band_cb)
            layer.rgb_bands = [idx_to_band(self._r_cb), idx_to_band(self._g_cb), idx_to_band(self._b_cb)]
            if count < 3:
                layer.band_mode = 'single'
            layer.std_n = self._std_spin.value()
            self.layer_changed.emit()

    def _on_cmap(self, name):
        layer = self.selected_layer()
        if layer and not self._block and layer.layer_type == 'raster':
            layer.colormap = name
            self.layer_changed.emit()

    def _on_reverse(self, checked):
        layer = self.selected_layer()
        if layer and not self._block and layer.layer_type == 'raster':
            layer.cmap_reverse = checked
            self.layer_changed.emit()

    def _on_stretch(self, name):
        layer = self.selected_layer()
        if layer and not self._block:
            layer.stretch = name
            self._std_spin.setVisible(name == '标准差拉伸')
            self.layer_changed.emit()

    def _on_ignore(self):
        layer = self.selected_layer()
        if layer and not self._block and layer.layer_type == 'raster':
            layer.ignore_text = self._ignore_edit.text()
            vals = []
            for p in re.split(r'[,，\s]+', layer.ignore_text.strip()):
                try:
                    vals.append(float(p))
                except ValueError:
                    pass
            if layer.reader:
                layer.reader.ignore_vals = vals
            self.layer_changed.emit()

    def _pick_color(self):
        layer = self.selected_layer()
        if not layer:
            return
        c = QColorDialog.getColor(QColor(layer.pen_color), self, '选择颜色')
        if c.isValid():
            layer.pen_color = c.name()
            self._color_btn.setStyleSheet(
                f'background-color: {layer.pen_color}; border: 1px solid #999;')
            if layer.graphics_item:
                layer.graphics_item.update_style(layer.pen_color, layer.pen_width)

    def _on_vec_style(self):
        layer = self.selected_layer()
        if layer and not self._block and layer.layer_type == 'vector':
            layer.pen_width = self._width_spin.value()
            if layer.graphics_item:
                layer.graphics_item.update_style(layer.pen_color, layer.pen_width)

    def _on_add_clicked(self):
        self.request_add_layer.emit()

    def _move_up(self):
        row = self._list.currentRow()
        if row > 0:
            self._layers[row], self._layers[row - 1] = self._layers[row - 1], self._layers[row]
            self._sync_list()
            self._list.setCurrentRow(row - 1)
            self.layer_changed.emit()

    def _move_down(self):
        row = self._list.currentRow()
        if row < len(self._layers) - 1:
            self._layers[row], self._layers[row + 1] = self._layers[row + 1], self._layers[row]
            self._sync_list()
            self._list.setCurrentRow(row + 1)
            self.layer_changed.emit()

    def _remove_current(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._layers):
            layer = self._layers.pop(row)
            if layer.reader:
                layer.reader.close()
            self._sync_list()
            if self._layers:
                self._list.setCurrentRow(min(row, len(self._layers) - 1))
            self.layer_changed.emit()

    def _ctx_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        lid = item.data(Qt.UserRole)
        layer = self.get_layer(lid)
        if not layer:
            return

        menu = QMenu(self)
        act_zoom = menu.addAction('缩放到图层')
        act_remove = menu.addAction('移除图层')
        action = menu.exec(self._list.mapToGlobal(pos))
        if action == act_zoom:
            self.request_zoom.emit(lid)
        elif action == act_remove:
            self._layers = [l for l in self._layers if l.id != lid]
            if layer.reader:
                layer.reader.close()
            self._sync_list()
            self.layer_changed.emit()

    def _on_reorder(self, *args):
        """拖拽排序后同步"""
        new_order = []
        for i in range(self._list.count()):
            lid = self._list.item(i).data(Qt.UserRole)
            l = self.get_layer(lid)
            if l:
                new_order.append(l)
        self._layers = new_order
        self.layer_changed.emit()
