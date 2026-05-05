"""
高级导出对话框：DPI、范围、坐标框、色带数值、标题、字体、预览
"""
import os
from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QLineEdit,
    QGroupBox, QLabel, QRadioButton, QButtonGroup, QScrollArea,
    QFileDialog, QMessageBox, QFontComboBox
)
from PySide6.QtCore import Qt, QSize
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


class ExportDialog(QDialog):
    """高级导出: DPI、范围、坐标框、色带数值、标题、字体、预览"""

    def __init__(self, layer_panel, view_box, last_dir='', parent=None):
        super().__init__(parent)
        self.layer_panel = layer_panel
        self.view_box = view_box
        self.last_dir = last_dir
        self.setWindowIcon(app_icon())
        self.setWindowTitle('导出设置')
        self.setMinimumSize(920, 640)
        self._build_ui()
        self._update_preview()

    def _build_ui(self):
        main = QHBoxLayout(self)

        # ---- 左侧设置 ----
        left = QScrollArea()
        left.setWidgetResizable(True)
        left.setMinimumWidth(420)
        left_w = QWidget()
        form = QVBoxLayout(left_w)

        # DPI
        grp_dpi = QGroupBox('输出参数')
        g1 = QFormLayout(grp_dpi)
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 2400)
        self._dpi_spin.setValue(600)
        self._dpi_spin.setSingleStep(50)
        self._dpi_spin.valueChanged.connect(self._update_preview)
        g1.addRow('DPI:', self._dpi_spin)
        form.addWidget(grp_dpi)

        # 范围
        grp_extent = QGroupBox('导出范围')
        e_layout = QVBoxLayout(grp_extent)
        self._ext_group = QButtonGroup(self)
        self._ext_view = QRadioButton('当前视窗范围')
        self._ext_view.setChecked(True)
        self._ext_full = QRadioButton('完整数据范围')
        self._ext_shp = QRadioButton('矢量图层边界')
        self._ext_feat = QRadioButton('矢量某一要素边界')
        self._ext_group.addButton(self._ext_view, 0)
        self._ext_group.addButton(self._ext_full, 1)
        self._ext_group.addButton(self._ext_shp, 2)
        self._ext_group.addButton(self._ext_feat, 3)
        for btn in [self._ext_view, self._ext_full, self._ext_shp, self._ext_feat]:
            e_layout.addWidget(btn)
            btn.toggled.connect(self._update_preview)

        # SHP选择
        shp_row = QHBoxLayout()
        shp_row.addWidget(QLabel('矢量图层:'))
        self._shp_cb = QComboBox()
        self._shp_cb.currentIndexChanged.connect(self._on_shp_select)
        shp_row.addWidget(self._shp_cb, 1)
        e_layout.addLayout(shp_row)

        feat_row = QHBoxLayout()
        feat_row.addWidget(QLabel('要素序号:'))
        self._feat_spin = QSpinBox()
        self._feat_spin.setMinimum(0)
        self._feat_spin.valueChanged.connect(self._update_preview)
        feat_row.addWidget(self._feat_spin)
        e_layout.addLayout(feat_row)

        form.addWidget(grp_extent)

        # 色带设置
        grp_cb = QGroupBox('色带设置')
        cb_l = QFormLayout(grp_cb)
        self._show_colorbar = QCheckBox('显示色带')
        self._show_colorbar.setChecked(True)
        self._show_colorbar.toggled.connect(self._update_preview)
        cb_l.addRow(self._show_colorbar)

        self._symmetric = QCheckBox('对称色带范围')
        self._symmetric.toggled.connect(self._update_preview)
        cb_l.addRow(self._symmetric)

        self._vmin_edit = QLineEdit()
        self._vmin_edit.setPlaceholderText('自动')
        self._vmin_edit.editingFinished.connect(self._update_preview)
        cb_l.addRow('最小值:', self._vmin_edit)

        self._vmax_edit = QLineEdit()
        self._vmax_edit.setPlaceholderText('自动')
        self._vmax_edit.editingFinished.connect(self._update_preview)
        cb_l.addRow('最大值:', self._vmax_edit)

        self._cb_title_edit = QLineEdit('Value')
        self._cb_title_edit.setPlaceholderText('色带标题')
        self._cb_title_edit.textChanged.connect(self._update_preview)
        cb_l.addRow('色带标题:', self._cb_title_edit)

        form.addWidget(grp_cb)

        # 坐标框 & 标题
        grp_label = QGroupBox('标注设置')
        lb_l = QFormLayout(grp_label)

        self._show_axes = QCheckBox('显示坐标框')
        self._show_axes.setChecked(True)
        self._show_axes.toggled.connect(self._update_preview)
        lb_l.addRow(self._show_axes)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText('图片标题')
        self._title_edit.textChanged.connect(self._update_preview)
        lb_l.addRow('标题:', self._title_edit)

        self._xlabel_edit = QLineEdit()
        self._xlabel_edit.textChanged.connect(self._update_preview)
        lb_l.addRow('X轴标题:', self._xlabel_edit)

        self._ylabel_edit = QLineEdit()
        self._ylabel_edit.textChanged.connect(self._update_preview)
        lb_l.addRow('Y轴标题:', self._ylabel_edit)

        form.addWidget(grp_label)

        # 字体
        grp_font = QGroupBox('字体设置')
        f_l = QFormLayout(grp_font)
        self._font_cn_cb = QFontComboBox()
        self._font_cn_cb.setCurrentFont(QFont(DEFAULT_CN_FONT))
        self._font_cn_cb.currentFontChanged.connect(self._update_preview)
        f_l.addRow('中文字体:', self._font_cn_cb)

        self._font_en_cb = QFontComboBox()
        self._font_en_cb.setCurrentFont(QFont(DEFAULT_EN_FONT))
        self._font_en_cb.currentFontChanged.connect(self._update_preview)
        f_l.addRow('英文字体:', self._font_en_cb)

        self._fontsize_spin = QSpinBox()
        self._fontsize_spin.setRange(6, 48)
        self._fontsize_spin.setValue(10)
        self._fontsize_spin.valueChanged.connect(self._update_preview)
        f_l.addRow('字号:', self._fontsize_spin)

        form.addWidget(grp_font)
        form.addStretch()

        left.setWidget(left_w)
        main.addWidget(left)

        # ---- 右侧预览 ----
        right = QVBoxLayout()
        right.addWidget(QLabel('预览 (低分辨率示意):'))
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumSize(400, 300)
        self._preview_label.setStyleSheet('background: #eee; border: 1px solid #ccc;')
        right.addWidget(self._preview_label, 1)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton('刷新预览')
        btn_refresh.clicked.connect(self._update_preview)
        btn_row.addWidget(btn_refresh)

        btn_save = QPushButton('保存图片')
        btn_save.setStyleSheet('font-weight: bold;')
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        btn_close = QPushButton('关闭')
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)
        right.addLayout(btn_row)
        main.addLayout(right, 1)

        # 填充 SHP 列表
        self._populate_shp()

    def _populate_shp(self):
        self._shp_cb.clear()
        self._shp_cb.addItem('(无)')
        for l in self.layer_panel.vector_layers():
            self._shp_cb.addItem(l.name, l.id)

    def _on_shp_select(self, idx):
        lid = self._shp_cb.itemData(idx)
        if lid:
            layer = self.layer_panel.get_layer(lid)
            if layer and layer.gdf_proj is not None:
                self._feat_spin.setMaximum(len(layer.gdf_proj) - 1)
        self._update_preview()

    def _full_extent(self):
        """所有可见图层的合并范围"""
        xmin, ymin, xmax, ymax = float('inf'), float('inf'), -float('inf'), -float('inf')
        found = False
        for layer in self.layer_panel.layers:
            if not layer.visible:
                continue
            if layer.layer_type == 'raster' and layer.reader:
                e = layer.reader.extent
                xmin = min(xmin, e[0])
                ymin = min(ymin, e[1])
                xmax = max(xmax, e[2])
                ymax = max(ymax, e[3])
                found = True
            elif layer.layer_type == 'vector' and layer.gdf_proj is not None:
                b = layer.gdf_proj.total_bounds
                xmin = min(xmin, b[0])
                ymin = min(ymin, b[1])
                xmax = max(xmax, b[2])
                ymax = max(ymax, b[3])
                found = True
        if found:
            return (xmin, ymin, xmax, ymax)
        return None

    def _get_extent(self):
        """计算导出范围 (xmin, ymin, xmax, ymax)"""
        mode = self._ext_group.checkedId()
        if mode == 0:
            # 当前视窗
            xr, yr = self.view_box.viewRange()
            return (xr[0], yr[0], xr[1], yr[1])
        elif mode == 1:
            # 完整数据范围
            return self._full_extent()
        elif mode == 2:
            # SHP边界
            lid = self._shp_cb.currentData()
            if lid:
                layer = self.layer_panel.get_layer(lid)
                if layer and layer.gdf_proj is not None:
                    b = layer.gdf_proj.total_bounds
                    return (b[0], b[1], b[2], b[3])
            return self._full_extent()
        elif mode == 3:
            # 要素边界
            lid = self._shp_cb.currentData()
            if lid:
                layer = self.layer_panel.get_layer(lid)
                if layer and layer.gdf_proj is not None:
                    feat_idx = self._feat_spin.value()
                    if 0 <= feat_idx < len(layer.gdf_proj):
                        b = layer.gdf_proj.iloc[feat_idx:feat_idx+1].total_bounds
                        pad_x = (b[2] - b[0]) * 0.05
                        pad_y = (b[3] - b[1]) * 0.05
                        return (b[0] - pad_x, b[1] - pad_y,
                                b[2] + pad_x, b[3] + pad_y)
            return self._full_extent()
        return self._full_extent()

    def _render_figure(self, dpi=72, for_save=False):
        """用 matplotlib 渲染图片"""
        extent = self._get_extent()
        if not extent:
            return None

        xmin, ymin, xmax, ymax = extent
        dx, dy = xmax - xmin, ymax - ymin
        if dx <= 0 or dy <= 0:
            return None

        actual_dpi = self._dpi_spin.value() if for_save else dpi
        # 计算图幅尺寸（英寸）
        max_dim = 10 if for_save else 5
        if dx > dy:
            fw = max_dim
            fh = max_dim * dy / dx
        else:
            fh = max_dim
            fw = max_dim * dx / dy
        fw = max(fw, 2)
        fh = max(fh, 2)

        font_cn = self._font_cn_cb.currentFont().family() or DEFAULT_CN_FONT
        font_en = self._font_en_cb.currentFont().family() or DEFAULT_EN_FONT
        font_size = self._fontsize_spin.value()
        apply_matplotlib_fonts(font_cn, font_en, font_size)

        fig = Figure(figsize=(fw, fh), dpi=actual_dpi)
        canvas = FigureCanvasAgg(fig)

        show_cb = self._show_colorbar.isChecked()
        ax = fig.add_subplot(111)

        # 渲染栅格图层 (从后往前)
        raster_layers = [l for l in reversed(self.layer_panel.layers)
                         if l.layer_type == 'raster' and l.visible and l.reader]

        last_mappable = None
        active_raster = None

        read_w = int(fw * actual_dpi) if for_save else int(fw * dpi)
        read_h = int(fh * actual_dpi) if for_save else int(fh * dpi)
        lim = MAX_EXPORT_READ_PX if for_save else MAX_PREVIEW_READ_PX
        read_w = min(read_w, lim)
        read_h = min(read_h, lim)

        for rl in raster_layers:
            rr = rl.reader
            bands = layer_read_bands(rl)
            data = rr.read_extent(bands, xmin, ymin, xmax, ymax, read_w, read_h)
            if data is None:
                continue

            if rl.band_mode == 'single':
                band_data = data[:, :, 0]
                v = band_data[np.isfinite(band_data)]
                if v.size == 0:
                    continue

                # 与主界面一致：直方图均衡化先把原始值映射到 0-255，再用色带显示。
                band_data, vmin_val, vmax_val, is_hist_eq = layer_single_band_for_matplotlib(band_data, rl)

                # 用户自定义范围和对称范围只作用于非直方图均衡化；
                # 直方图均衡化的显示域固定为 0-255，才能和主界面一致。
                if not is_hist_eq:
                    try:
                        umin = float(self._vmin_edit.text())
                        vmin_val = umin
                    except (ValueError, TypeError):
                        pass
                    try:
                        umax = float(self._vmax_edit.text())
                        vmax_val = umax
                    except (ValueError, TypeError):
                        pass

                    if self._symmetric.isChecked():
                        abs_max = max(abs(vmin_val), abs(vmax_val))
                        vmin_val, vmax_val = -abs_max, abs_max

                cmap_name = rl.colormap
                if rl.cmap_reverse:
                    cmap_name += '_r'

                im = ax.imshow(band_data, extent=[xmin, xmax, ymin, ymax],
                               cmap=cmap_name, vmin=vmin_val, vmax=vmax_val,
                               interpolation='nearest', origin='upper', aspect='equal',
                               alpha=rl.opacity)
                last_mappable = im
                active_raster = rl
            else:
                # RGB：同样复用图层拉伸方式，直方图均衡化时逐通道套用缓存 CDF。
                rgb = layer_rgb_for_matplotlib(data, rl)
                ax.imshow(rgb, extent=[xmin, xmax, ymin, ymax],
                          interpolation='nearest', origin='upper', aspect='equal',
                          alpha=rl.opacity)

        # 渲染矢量图层
        vec_layers = [l for l in reversed(self.layer_panel.layers)
                      if l.layer_type == 'vector' and l.visible and l.gdf_proj is not None]
        for vl in vec_layers:
            try:
                vl.gdf_proj.boundary.plot(ax=ax, color=vl.pen_color,
                                           linewidth=vl.pen_width * 0.5,
                                           alpha=vl.opacity)
            except Exception:
                try:
                    vl.gdf_proj.plot(ax=ax, facecolor='none',
                                     edgecolor=vl.pen_color,
                                     linewidth=vl.pen_width * 0.5,
                                     alpha=vl.opacity)
                except Exception:
                    pass

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

        # 坐标框
        if self._show_axes.isChecked():
            ax.tick_params(labelsize=font_size * 0.8)
            if self._xlabel_edit.text():
                ax.set_xlabel(self._xlabel_edit.text(), fontsize=font_size)
            if self._ylabel_edit.text():
                ax.set_ylabel(self._ylabel_edit.text(), fontsize=font_size)
        else:
            ax.set_axis_off()

        # 标题
        if self._title_edit.text():
            ax.set_title(self._title_edit.text(), fontsize=font_size * 1.2,
                         fontweight='bold')

        # 色带
        if show_cb and last_mappable is not None:
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="4%", pad=0.08)
            cb = fig.colorbar(last_mappable, cax=cax)
            if self._cb_title_edit.text():
                cb.set_label(self._cb_title_edit.text(), fontsize=font_size)
            cb.ax.tick_params(labelsize=font_size * 0.8)

        fig.tight_layout()
        return fig

    def _compute_levels(self, v, layer):
        """根据图层的拉伸设置计算 vmin/vmax"""
        if layer.stretch == '百分比截断':
            return float(np.percentile(v, 2)), float(np.percentile(v, 98))
        elif layer.stretch == '全局最值':
            return float(np.min(v)), float(np.max(v))
        elif layer.stretch == '标准差拉伸':
            mean, std = np.mean(v), np.std(v)
            n = layer.std_n
            return float(mean - n * std), float(mean + n * std)
        return float(np.min(v)), float(np.max(v))

    def _update_preview(self, *args):
        try:
            fig = self._render_figure(dpi=72, for_save=False)
            if fig is None:
                self._preview_label.setText('无可渲染内容')
                return
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
        default_name = 'export.png'
        rasters = self.layer_panel.raster_layers()
        if rasters:
            default_name = Path(rasters[0].path).stem + '_export.png'

        p, _ = QFileDialog.getSaveFileName(
            self, '保存图片', str(Path(self.last_dir) / default_name),
            'PNG (*.png);;JPEG (*.jpg);;TIFF (*.tif);;PDF (*.pdf);;SVG (*.svg)')
        if not p:
            return

        try:
            fig = self._render_figure(for_save=True)
            if fig is None:
                QMessageBox.warning(self, '错误', '无可渲染内容')
                return

            fig.savefig(p, dpi=self._dpi_spin.value(),
                        bbox_inches='tight', pad_inches=0.1,
                        facecolor='white')
            plt.close(fig)
            QMessageBox.information(self, '完成', f'已保存至:\n{p}')
        except Exception as e:
            QMessageBox.critical(self, '保存失败', str(e))
