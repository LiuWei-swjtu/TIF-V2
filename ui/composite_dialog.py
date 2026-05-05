"""
组图导出对话框：多子图组合，支持独立/共享色带
"""
from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QLineEdit,
    QGroupBox, QLabel, QRadioButton, QButtonGroup, QScrollArea,
    QSlider, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QFontComboBox, QWidget
)
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QPixmap, QImage, QFont

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from mpl_toolkits.axes_grid1 import make_axes_locatable

from config import (
    app_icon, apply_matplotlib_fonts,
    DEFAULT_CN_FONT, DEFAULT_EN_FONT,
    MAX_EXPORT_READ_PX, MAX_PREVIEW_READ_PX
)
from layer import layer_read_bands, layer_single_band_for_matplotlib, layer_rgb_for_matplotlib


class CompositeDialog(QDialog):
    """组图导出：多子图组合"""

    def __init__(self, layer_panel, parent=None):
        super().__init__(parent)
        self.layer_panel = layer_panel
        self.setWindowIcon(app_icon())
        self.setWindowTitle('组图导出')
        self.setMinimumSize(1050, 700)

        # 预览渲染比较重，滑块/数字连续变化时用防抖，避免每一小步都重画。
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(280)
        self._preview_timer.timeout.connect(self._update_preview)
        self._spacing_syncing = False

        self._build_ui()

    def _schedule_preview(self, *args):
        if hasattr(self, '_preview_timer'):
            self._preview_timer.start()
        else:
            self._update_preview()

    def _sync_spacing_pair(self, spin, slider, value, from_slider=False):
        """只同步同一行的数字框和滑块；横向与纵向控件互不联动。"""
        if getattr(self, '_spacing_syncing', False):
            return
        self._spacing_syncing = True
        try:
            if from_slider:
                fv = float(value) / 100.0
                if abs(spin.value() - fv) > 1e-9:
                    spin.setValue(fv)
            else:
                iv = int(round(float(value) * 100))
                if slider.value() != iv:
                    slider.setValue(iv)
        finally:
            self._spacing_syncing = False
        self._schedule_preview()

    def _on_wspace_spin_changed(self, value):
        self._sync_spacing_pair(self._wspace_spin, self._wspace_slider, value, from_slider=False)

    def _on_wspace_slider_changed(self, value):
        self._sync_spacing_pair(self._wspace_spin, self._wspace_slider, value, from_slider=True)

    def _on_hspace_spin_changed(self, value):
        self._sync_spacing_pair(self._hspace_spin, self._hspace_slider, value, from_slider=False)

    def _on_hspace_slider_changed(self, value):
        self._sync_spacing_pair(self._hspace_spin, self._hspace_slider, value, from_slider=True)

    def _make_spacing_control(self, default, tooltip):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        spin = QDoubleSpinBox()
        spin.setRange(0.00, 1.50)
        spin.setDecimals(2)
        spin.setSingleStep(0.02)
        spin.setValue(default)
        spin.setFixedWidth(90)
        spin.setToolTip(tooltip)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 150)
        slider.setValue(int(round(default * 100)))
        slider.setToolTip(tooltip)

        layout.addWidget(spin)
        layout.addWidget(slider, 1)
        return row, spin, slider

    def _build_ui(self):
        main = QHBoxLayout(self)

        # ---- 左侧设置 ----
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setMinimumWidth(500)
        left_w = QWidget()
        form = QVBoxLayout(left_w)

        # 网格大小
        grp_grid = QGroupBox('布局设置')
        g_l = QFormLayout(grp_grid)
        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 6)
        self._rows_spin.setValue(1)
        self._rows_spin.valueChanged.connect(self._rebuild_table)
        g_l.addRow('行数:', self._rows_spin)

        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 6)
        self._cols_spin.setValue(2)
        self._cols_spin.valueChanged.connect(self._rebuild_table)
        g_l.addRow('列数:', self._cols_spin)

        w_row, self._wspace_spin, self._wspace_slider = self._make_spacing_control(
            0.04, '左右子图之间的绝对间隔；不会压缩子图高度'
        )
        self._wspace_spin.valueChanged.connect(self._on_wspace_spin_changed)
        self._wspace_slider.valueChanged.connect(self._on_wspace_slider_changed)
        g_l.addRow('横向间距:', w_row)

        h_row, self._hspace_spin, self._hspace_slider = self._make_spacing_control(
            0.04, '上下子图之间的绝对间隔；不会压缩子图宽度'
        )
        self._hspace_spin.valueChanged.connect(self._on_hspace_spin_changed)
        self._hspace_slider.valueChanged.connect(self._on_hspace_slider_changed)
        g_l.addRow('纵向间距:', h_row)

        self._preserve_aspect_cb = QCheckBox('保持地图真实比例')
        self._preserve_aspect_cb.setChecked(True)
        self._preserve_aspect_cb.setToolTip('勾选时保持地图横纵比例；取消勾选后横向/纵向间距的视觉效果更独立，但地图可能被拉伸')
        self._preserve_aspect_cb.toggled.connect(self._schedule_preview)
        g_l.addRow(self._preserve_aspect_cb)

        self._show_vector_cb = QCheckBox('导出图片中显示矢量图层')
        self._show_vector_cb.setChecked(True)
        self._show_vector_cb.setToolTip('勾选时在组图预览和导出图中绘制所选 SHP/矢量边界；取消勾选后仍可用矢量图层控制范围，但不显示边界线')
        self._show_vector_cb.toggled.connect(self._schedule_preview)
        g_l.addRow(self._show_vector_cb)

        form.addWidget(grp_grid)

        # 子图表
        grp_sub = QGroupBox('子图配置')
        sub_l = QVBoxLayout(grp_sub)
        self._table = QTableWidget()
        self._table.setMinimumHeight(200)
        sub_l.addWidget(self._table)

        sync_row = QHBoxLayout()
        self._sync_first_btn = QPushButton('一键同步第一个图层/范围到全部')
        self._sync_first_btn.setToolTip('把第1个子图的栅格图层、矢量图层、要素范围和要素序号复制到其余子图；不会覆盖子图标题')
        self._sync_first_btn.clicked.connect(self._sync_first_subplot)
        sync_row.addWidget(self._sync_first_btn)
        sync_row.addStretch()
        sub_l.addLayout(sync_row)

        form.addWidget(grp_sub)

        # 色带模式
        grp_cb = QGroupBox('色带设置')
        cb_l = QVBoxLayout(grp_cb)
        self._cb_mode_group = QButtonGroup(self)
        self._cb_individual = QRadioButton('每个子图独立色带')
        self._cb_individual.setChecked(True)
        self._cb_shared = QRadioButton('所有子图共用色带')
        self._cb_mode_group.addButton(self._cb_individual, 0)
        self._cb_mode_group.addButton(self._cb_shared, 1)
        cb_l.addWidget(self._cb_individual)
        cb_l.addWidget(self._cb_shared)

        self._symmetric_cb = QCheckBox('对称色带范围')
        cb_l.addWidget(self._symmetric_cb)

        title_row = QFormLayout()
        self._cb_title_edit = QLineEdit('Value')
        title_row.addRow('色带标题:', self._cb_title_edit)
        cb_l.addLayout(title_row)

        form.addWidget(grp_cb)

        # 输出参数
        grp_out = QGroupBox('输出参数')
        o_l = QFormLayout(grp_out)

        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 2400)
        self._dpi_spin.setValue(600)
        o_l.addRow('DPI:', self._dpi_spin)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText('组图标题')
        o_l.addRow('标题:', self._title_edit)

        self._show_axes_cb = QCheckBox('显示坐标框')
        self._show_axes_cb.setChecked(True)
        o_l.addRow(self._show_axes_cb)

        self._font_cn_cb = QFontComboBox()
        self._font_cn_cb.setCurrentFont(QFont(DEFAULT_CN_FONT))
        o_l.addRow('中文字体:', self._font_cn_cb)

        self._font_en_cb = QFontComboBox()
        self._font_en_cb.setCurrentFont(QFont(DEFAULT_EN_FONT))
        o_l.addRow('英文字体:', self._font_en_cb)

        self._fontsize_spin = QSpinBox()
        self._fontsize_spin.setRange(6, 48)
        self._fontsize_spin.setValue(10)
        o_l.addRow('字号:', self._fontsize_spin)

        form.addWidget(grp_out)
        form.addStretch()
        left.setWidget(left_w)
        main.addWidget(left)

        # ---- 右侧预览 ----
        right = QVBoxLayout()
        right.addWidget(QLabel('预览:'))
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumSize(450, 350)
        self._preview_label.setStyleSheet('background: #eee; border: 1px solid #ccc;')
        right.addWidget(self._preview_label, 1)

        btn_row = QHBoxLayout()
        btn_preview = QPushButton('刷新预览')
        btn_preview.clicked.connect(self._update_preview)
        btn_row.addWidget(btn_preview)

        btn_save = QPushButton('保存组图')
        btn_save.setStyleSheet('font-weight: bold;')
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        btn_close = QPushButton('关闭')
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        right.addLayout(btn_row)
        main.addLayout(right, 1)

        self._rebuild_table()

    def _rebuild_table(self):
        rows = self._rows_spin.value()
        cols = self._cols_spin.value()
        n = rows * cols
        self._table.setRowCount(n)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            '位置', '栅格图层', '矢量图层', '要素范围', '要素序号', '子图标题'
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        raster_names = ['(无)'] + [l.name for l in self.layer_panel.raster_layers()]
        vector_names = ['(无)'] + [l.name for l in self.layer_panel.vector_layers()]

        for i in range(n):
            r, c = i // cols, i % cols
            # 位置
            self._table.setItem(i, 0, QTableWidgetItem(f'({r+1},{c+1})'))
            self._table.item(i, 0).setFlags(Qt.ItemIsEnabled)

            # 栅格
            cb_r = QComboBox()
            cb_r.addItems(raster_names)
            if i < len(raster_names) - 1:
                cb_r.setCurrentIndex(min(i + 1, len(raster_names) - 1))
            self._table.setCellWidget(i, 1, cb_r)

            # 矢量
            cb_v = QComboBox()
            cb_v.addItems(vector_names)
            self._table.setCellWidget(i, 2, cb_v)

            # 要素范围
            feat_cb = QComboBox()
            feat_cb.addItems(['全部整体', '单个要素', '单个循环'])
            self._table.setCellWidget(i, 3, feat_cb)

            feat_spin = QSpinBox()
            feat_spin.setRange(0, 999999)
            feat_spin.setValue(i)
            self._table.setCellWidget(i, 4, feat_spin)

            # 标题
            self._table.setItem(i, 5, QTableWidgetItem(''))

    def _row_extent_for_layout(self, row, raster_list, vector_list):
        """估算某个子图最终会使用的数据范围，用于自动计算组图画布长宽比。"""
        cb_r = self._table.cellWidget(row, 1)
        cb_v = self._table.cellWidget(row, 2)
        feat_cb = self._table.cellWidget(row, 3)
        feat_spin = self._table.cellWidget(row, 4)

        has_raster = cb_r and cb_r.currentIndex() > 0
        has_vector = cb_v and cb_v.currentIndex() > 0

        if has_vector:
            try:
                vl = vector_list[cb_v.currentIndex() - 1]
                gdf = vl.gdf_proj if vl.gdf_proj is not None else vl.gdf
                if gdf is not None and len(gdf) > 0:
                    mode = feat_cb.currentText() if feat_cb else '全部整体'
                    if mode == '单个要素':
                        idx = feat_spin.value() if feat_spin else 0
                        idx = min(max(idx, 0), len(gdf) - 1)
                        g = gdf.iloc[idx:idx + 1]
                    elif mode == '单个循环':
                        g = gdf.iloc[(row % len(gdf)):(row % len(gdf)) + 1]
                    else:
                        g = gdf
                    b = g.total_bounds
                    pad_x = (b[2] - b[0]) * 0.05
                    pad_y = (b[3] - b[1]) * 0.05
                    return (b[0] - pad_x, b[1] - pad_y, b[2] + pad_x, b[3] + pad_y)
            except Exception:
                pass

        if has_raster:
            try:
                rl = raster_list[cb_r.currentIndex() - 1]
                if rl.reader:
                    return rl.reader.extent
            except Exception:
                pass

        return None

    def _estimate_grid_box_aspect(self, rows, cols, raster_list, vector_list):
        """
        根据子图真实数据范围估算 Figure 高宽比。
        单纯调 wspace/hspace 只能控制网格之间的间距；如果 Figure 的长宽比
        和地图数据长宽比不匹配，aspect='equal' 会在每个格子内部留下空白，
        看起来就像"间距调到 0 还是很宽"。
        """
        aspects = []
        for row in range(rows * cols):
            e = self._row_extent_for_layout(row, raster_list, vector_list)
            if not e:
                continue
            dx = e[2] - e[0]
            dy = e[3] - e[1]
            if dx > 0 and dy > 0:
                aspects.append(dy / dx)

        if not aspects:
            return 1.0

        aspect = float(np.median(aspects))
        # 防止极端狭长范围把预览压得过扁或过高。
        return min(max(aspect, 0.35), 2.50)

    def _sync_first_subplot(self):
        """把第一个子图的图层与范围配置复制到所有子图。"""
        if self._table.rowCount() <= 1:
            return

        src_raster = self._table.cellWidget(0, 1)
        src_vector = self._table.cellWidget(0, 2)
        src_extent = self._table.cellWidget(0, 3)
        src_feat = self._table.cellWidget(0, 4)
        if not (src_raster and src_vector and src_extent and src_feat):
            return

        raster_idx = src_raster.currentIndex()
        vector_idx = src_vector.currentIndex()
        extent_idx = src_extent.currentIndex()
        feat_val = src_feat.value()

        for row in range(1, self._table.rowCount()):
            dst_raster = self._table.cellWidget(row, 1)
            dst_vector = self._table.cellWidget(row, 2)
            dst_extent = self._table.cellWidget(row, 3)
            dst_feat = self._table.cellWidget(row, 4)
            if dst_raster:
                dst_raster.setCurrentIndex(min(raster_idx, max(0, dst_raster.count() - 1)))
            if dst_vector:
                dst_vector.setCurrentIndex(min(vector_idx, max(0, dst_vector.count() - 1)))
            if dst_extent:
                dst_extent.setCurrentIndex(min(extent_idx, max(0, dst_extent.count() - 1)))
            if dst_feat:
                dst_feat.setValue(feat_val)

        self._schedule_preview()

    def _render(self, dpi=72, for_save=False):
        rows = self._rows_spin.value()
        cols = self._cols_spin.value()
        n = rows * cols
        actual_dpi = self._dpi_spin.value() if for_save else dpi

        font_cn = self._font_cn_cb.currentFont().family() or DEFAULT_CN_FONT
        font_en = self._font_en_cb.currentFont().family() or DEFAULT_EN_FONT
        font_size = self._fontsize_spin.value()
        apply_matplotlib_fonts(font_cn, font_en, font_size)

        raster_list = self.layer_panel.raster_layers()
        vector_list = self.layer_panel.vector_layers()
        shared_mode = self._cb_shared.isChecked()
        symmetric = self._symmetric_cb.isChecked()
        preserve_aspect = self._preserve_aspect_cb.isChecked() if hasattr(self, '_preserve_aspect_cb') else True
        show_vector = self._show_vector_cb.isChecked() if hasattr(self, '_show_vector_cb') else True
        draw_aspect = 'equal' if preserve_aspect else 'auto'

        # 横向/纵向间距使用"绝对物理间隔（英寸）"，而不是 Matplotlib 原生的
        # wspace/hspace 百分比。这样横向间距变大时，只增加整张 Figure 的宽度，
        # 不压缩每个地图 Axes 的宽度；纵向同理。否则在 aspect='equal' 下，
        # Axes 宽度被压缩后高度也会被同步压缩，看起来就像纵向也跟着变。
        map_aspect = self._estimate_grid_box_aspect(rows, cols, raster_list, vector_list) if preserve_aspect else 0.78
        cell_w = 3.8
        cell_h = max(1.8, cell_w * map_aspect) if preserve_aspect else 3.0

        gap_x = self._wspace_spin.value() if hasattr(self, '_wspace_spin') else 0.04
        gap_y = self._hspace_spin.value() if hasattr(self, '_hspace_spin') else 0.04

        title_in = 0.45 if self._title_edit.text().strip() else 0.18
        left_in = 0.52 if self._show_axes_cb.isChecked() else 0.16
        bottom_in = 0.46 if self._show_axes_cb.isChecked() else 0.16
        top_in = title_in
        # 共享色带需要在右侧单独留出空间；独立色带由 axes_grid1 贴在各子图右侧。
        right_in = 0.78 if shared_mode else 0.28

        grid_w = cols * cell_w + max(0, cols - 1) * gap_x
        grid_h = rows * cell_h + max(0, rows - 1) * gap_y
        fig_w = max(2.0, left_in + grid_w + right_in)
        fig_h = max(2.0, bottom_in + grid_h + top_in)

        # 换算回 Matplotlib 需要的相对边距。由于 Figure 尺寸已经随 gap_x/gap_y
        # 增大，下面的 wspace/hspace 不会再挤压 Axes 本身。
        adj_left = left_in / fig_w
        adj_right = 1.0 - right_in / fig_w
        adj_bottom = bottom_in / fig_h
        adj_top = 1.0 - top_in / fig_h
        adj_wspace = (gap_x / cell_w) if cols > 1 else 0.0
        adj_hspace = (gap_y / cell_h) if rows > 1 else 0.0

        fig, axes = plt.subplots(rows, cols, figsize=(fig_w, fig_h), dpi=actual_dpi,
                                  squeeze=False)

        # 共享色带时先计算全局范围。直方图均衡化图层先映射到 0-255，
        # 否则共用色带仍会按原始值百分比截断，和主界面显示不一致。
        global_vmin, global_vmax = None, None
        global_cmap = 'gray'
        if shared_mode:
            all_v = []
            all_hist_eq = True
            saw_single = False
            for i in range(n):
                cb_r = self._table.cellWidget(i, 1)
                if cb_r and cb_r.currentIndex() > 0:
                    rl = raster_list[cb_r.currentIndex() - 1]
                    if rl.reader and rl.band_mode == 'single':
                        saw_single = True
                        ov = rl.reader.overview(layer_read_bands(rl))
                        bd_for_cb, _, _, is_hist_eq = layer_single_band_for_matplotlib(ov[:, :, 0], rl)
                        all_hist_eq = all_hist_eq and is_hist_eq
                        v = bd_for_cb[np.isfinite(bd_for_cb)]
                        if v.size > 0:
                            all_v.append(v)
                        global_cmap = rl.colormap + ('_r' if rl.cmap_reverse else '')
            if all_v:
                if saw_single and all_hist_eq:
                    global_vmin, global_vmax = 0.0, 255.0
                else:
                    combined = np.concatenate(all_v)
                    global_vmin = float(np.percentile(combined, 2))
                    global_vmax = float(np.percentile(combined, 98))
                    if symmetric:
                        abs_max = max(abs(global_vmin), abs(global_vmax))
                        global_vmin, global_vmax = -abs_max, abs_max

        last_mappable = None
        for i in range(n):
            r_idx, c_idx = i // cols, i % cols
            ax = axes[r_idx][c_idx]

            cb_r = self._table.cellWidget(i, 1)
            cb_v = self._table.cellWidget(i, 2)
            feat_cb = self._table.cellWidget(i, 3)
            feat_spin = self._table.cellWidget(i, 4)
            title_item = self._table.item(i, 5)
            subtitle = title_item.text() if title_item else ''

            has_raster = cb_r and cb_r.currentIndex() > 0
            has_vector = cb_v and cb_v.currentIndex() > 0

            # 确定范围
            extent = None
            clip_gdf = None
            if has_vector:
                vl = vector_list[cb_v.currentIndex() - 1]
                gdf = vl.gdf_proj if vl.gdf_proj is not None else vl.gdf
                if gdf is not None:
                    mode = feat_cb.currentText() if feat_cb else '全部整体'
                    if mode == '单个要素':
                        idx = feat_spin.value() if feat_spin else 0
                        idx = min(max(idx, 0), len(gdf) - 1)
                        clip_gdf = gdf.iloc[idx:idx + 1]
                    elif mode == '单个循环':
                        idx = i % len(gdf)
                        clip_gdf = gdf.iloc[idx:idx + 1]
                    else:
                        clip_gdf = gdf
                    b = clip_gdf.total_bounds
                    pad_x = (b[2] - b[0]) * 0.05
                    pad_y = (b[3] - b[1]) * 0.05
                    extent = (b[0] - pad_x, b[1] - pad_y, b[2] + pad_x, b[3] + pad_y)

            if has_raster:
                rl = raster_list[cb_r.currentIndex() - 1]
                rr = rl.reader
                if not extent:
                    extent = rr.extent

                xmin, ymin, xmax, ymax = extent
                rw = min(int(fig_w / cols * actual_dpi), 2048) if for_save else 400
                rh = min(int(fig_h / rows * actual_dpi), 2048) if for_save else 400
                bands = layer_read_bands(rl)
                data = rr.read_extent(bands, xmin, ymin, xmax, ymax, rw, rh)

                if data is not None and rl.band_mode == 'single':
                    bd = data[:, :, 0]
                    v = bd[np.isfinite(bd)]
                    if v.size == 0:
                        continue

                    bd, local_vmin, local_vmax, is_hist_eq = layer_single_band_for_matplotlib(bd, rl)

                    if shared_mode and global_vmin is not None:
                        vmin_val, vmax_val = global_vmin, global_vmax
                        cmap_name = global_cmap
                    else:
                        vmin_val, vmax_val = local_vmin, local_vmax
                        # 直方图均衡化的显示域固定为 0-255；对称色带会破坏与主界面的一致性。
                        if symmetric and not is_hist_eq:
                            abs_max = max(abs(vmin_val), abs(vmax_val))
                            vmin_val, vmax_val = -abs_max, abs_max
                        cmap_name = rl.colormap + ('_r' if rl.cmap_reverse else '')

                    im = ax.imshow(bd, extent=[xmin, xmax, ymin, ymax],
                                   cmap=cmap_name, vmin=vmin_val, vmax=vmax_val,
                                   interpolation='nearest', origin='upper', aspect=draw_aspect)
                    last_mappable = im

                    if not shared_mode:
                        divider = make_axes_locatable(ax)
                        cax = divider.append_axes("right", size="4%", pad=0.035)
                        cb = fig.colorbar(im, cax=cax)
                        if self._cb_title_edit.text():
                            cb.set_label(self._cb_title_edit.text(), fontsize=font_size * 0.9)
                        cb.ax.tick_params(labelsize=font_size * 0.7)

                elif data is not None:
                    rgb = layer_rgb_for_matplotlib(data, rl)
                    ax.imshow(rgb, extent=[xmin, xmax, ymin, ymax],
                              interpolation='nearest', origin='upper', aspect=draw_aspect)

            # 矢量叠加：显示开关只控制最终图片中是否绘制矢量边界；
            # 矢量图层仍可用于确定导出范围/单个要素范围。
            if show_vector and has_vector and clip_gdf is not None:
                vl = vector_list[cb_v.currentIndex() - 1]
                try:
                    clip_gdf.boundary.plot(ax=ax, color=vl.pen_color,
                                            linewidth=vl.pen_width * 0.5)
                except Exception:
                    clip_gdf.plot(ax=ax, facecolor='none',
                                  edgecolor=vl.pen_color,
                                  linewidth=vl.pen_width * 0.5)

            if extent:
                ax.set_xlim(extent[0], extent[2])
                ax.set_ylim(extent[1], extent[3])

            if subtitle:
                ax.set_title(subtitle, fontsize=font_size)

            if not self._show_axes_cb.isChecked():
                ax.set_axis_off()
            else:
                ax.tick_params(labelsize=font_size * 0.7)

        title_text = self._title_edit.text().strip()

        # 共享色带：先让 Matplotlib 按 aspect='equal' 完成子图真实布局，
        # 再读取所有子图的实际 Axes 位置，用这些位置的上下边界创建色带轴。
        # 这样色带高度会与子图区域严格对齐，不再使用固定的 [0.14, 0.72]。
        if shared_mode and last_mappable is not None:
            fig.subplots_adjust(left=adj_left, right=adj_right, bottom=adj_bottom, top=adj_top,
                                wspace=adj_wspace, hspace=adj_hspace)
            if title_text:
                fig.suptitle(title_text, fontsize=font_size * 1.3, fontweight='bold')

            # aspect='equal' 会在 draw 阶段压缩/移动 Axes；必须 draw 后再取位置。
            FigureCanvasAgg(fig).draw()
            plot_axes = [ax for row in axes for ax in row if ax.get_visible()]
            positions = [ax.get_position() for ax in plot_axes]
            if positions:
                x1 = max(p.x1 for p in positions)
                y0 = min(p.y0 for p in positions)
                y1 = max(p.y1 for p in positions)
                cbar_pad = 0.012
                cbar_width = 0.018
                cax = fig.add_axes([x1 + cbar_pad, y0, cbar_width, y1 - y0])
            else:
                cax = fig.add_axes([0.90, 0.15, 0.018, 0.70])

            cb = fig.colorbar(last_mappable, cax=cax)
            if self._cb_title_edit.text():
                cb.set_label(self._cb_title_edit.text(), fontsize=font_size)
            cb.ax.tick_params(labelsize=font_size * 0.8)
        else:
            fig.subplots_adjust(left=adj_left, right=adj_right, bottom=adj_bottom, top=adj_top,
                                wspace=adj_wspace, hspace=adj_hspace)
            if title_text:
                fig.suptitle(title_text, fontsize=font_size * 1.3, fontweight='bold')

            # 对独立色带模式也执行一次 draw，使 make_axes_locatable 追加的色带轴
            # 根据新的 wspace/hspace 完成最终定位。
            FigureCanvasAgg(fig).draw()

        return fig

    def _update_preview(self):
        try:
            fig = self._render(dpi=72, for_save=False)
            canvas = FigureCanvasAgg(fig)
            canvas.draw()
            buf = canvas.buffer_rgba()
            w, h = canvas.get_width_height()
            qimg = QImage(buf, w, h, QImage.Format_RGBA8888).copy()
            pm = QPixmap.fromImage(qimg)
            pm = pm.scaled(self._preview_label.size(),
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._preview_label.setPixmap(pm)
            plt.close(fig)
        except Exception as e:
            self._preview_label.setText(f'预览失败: {e}')

    def _save(self):
        p, _ = QFileDialog.getSaveFileName(
            self, '保存组图', '',
            'PNG (*.png);;JPEG (*.jpg);;TIFF (*.tif);;PDF (*.pdf);;SVG (*.svg)')
        if not p:
            return
        try:
            fig = self._render(for_save=True)
            fig.savefig(p, dpi=self._dpi_spin.value(),
                        bbox_inches='tight', pad_inches=0.15,
                        facecolor='white')
            plt.close(fig)
            QMessageBox.information(self, '完成', f'已保存至:\n{p}')
        except Exception as e:
            QMessageBox.critical(self, '保存失败', str(e))
