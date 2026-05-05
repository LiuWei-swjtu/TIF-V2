"""
主窗口：集成画布、图层面板、所有功能
"""
import os
import re
from pathlib import Path

import numpy as np
import geopandas as gpd
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QDockWidget, QWidget, QPushButton,
    QLabel, QFileDialog, QMessageBox, QApplication, QProgressBar, QStatusBar
)
from PySide6.QtCore import Qt, QTimer, QSettings, QSize
from PySide6.QtGui import QTransform, QAction

from config import (
    app_icon, APP_NAME, ORG_NAME,
    RASTER_EXTS, VECTOR_EXTS, ALL_EXTS
)
from layer import LayerInfo, layer_read_bands
from raster_reader import RasterReader
from vector_item import VectorGraphicsItem
from ui.layer_panel import LayerPanel
from ui.export_dialog import ExportDialog
from ui.composite_dialog import CompositeDialog
from ui.colormap_dialog import CMapManagerDialog

pg.setConfigOptions(imageAxisOrder='row-major')


class TIFViewer(QMainWindow):
    """主窗口：集成画布、图层面板、所有功能"""

    def __init__(self):
        super().__init__()
        self.setWindowIcon(app_icon())
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.setAcceptDrops(True)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._last_dir = self._settings.value('last_dir', '')
        self._project_crs = None  # 工程坐标系

        self._lock = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._refresh)

        self._build_ui()

    def _build_ui(self):
        # ---- 工具栏 ----
        tb = QToolBar('工具栏', movable=False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        btn_open = QPushButton(' 打开文件 ')
        btn_open.setToolTip('加载 TIF / SHP / GeoJSON 等文件')
        btn_open.clicked.connect(self._dlg_open)
        tb.addWidget(btn_open)
        tb.addSeparator()

        btn_reset = QPushButton(' 复位视图 ')
        btn_reset.clicked.connect(self._reset_view)
        tb.addWidget(btn_reset)
        tb.addSeparator()

        btn_export = QPushButton(' 导出图片 ')
        btn_export.setToolTip('打开高级导出对话框')
        btn_export.clicked.connect(self._show_export)
        tb.addWidget(btn_export)

        btn_composite = QPushButton(' 组图导出 ')
        btn_composite.setToolTip('创建多子图组合')
        btn_composite.clicked.connect(self._show_composite)
        tb.addWidget(btn_composite)
        tb.addSeparator()

        btn_cmap = QPushButton(' 色带管理 ')
        btn_cmap.clicked.connect(self._show_cmap_mgr)
        tb.addWidget(btn_cmap)

        tb.addWidget(QWidget())  # spacer

        # ---- 图层面板 ----
        self.layer_panel = LayerPanel(self)
        self.layer_panel.layer_changed.connect(self._on_layers_changed)
        self.layer_panel.request_zoom.connect(self._zoom_to_layer)
        self.layer_panel.request_add_layer.connect(self._dlg_open)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layer_panel)

        # ---- 画布 ----
        self.pw = pg.PlotWidget(background='#f5f5f5')
        self.pw.setAcceptDrops(False)
        self.pw.viewport().setAcceptDrops(False)
        self.pw.setAspectLocked(True)
        vb = self.pw.getViewBox()
        vb.setMenuEnabled(False)
        self.pw.hideAxis('left')
        self.pw.hideAxis('bottom')
        self.setCentralWidget(self.pw)

        vb.sigRangeChanged.connect(self._on_range)
        self.pw.scene().sigMouseClicked.connect(self._on_click)

        # ---- 状态栏 ----
        self._sl = QLabel('就绪 — 拖拽文件到窗口或点击"打开文件"')
        self._sl.setMinimumWidth(480)
        self.statusBar().addWidget(self._sl, 1)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(170)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.hide()
        self.statusBar().addPermanentWidget(self._progress, 0)

    # ---- 状态栏进度 ----
    def _busy_start(self, text, value=0, indeterminate=False):
        self._sl.setText(text)
        self._progress.show()
        if indeterminate:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 100)
            self._progress.setValue(value)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

    def _busy_step(self, text=None, value=None):
        if text is not None:
            self._sl.setText(text)
        if value is not None:
            if self._progress.maximum() == 0:
                self._progress.setRange(0, 100)
            self._progress.setValue(value)
        QApplication.processEvents()

    def _busy_end(self, text=None):
        self._progress.hide()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        try:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        except Exception:
            pass
        if text is not None:
            self._sl.setText(text)
        QApplication.processEvents()

    # ---- 文件加载 ----
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p:
                self._load_file(p)

    def _dlg_open(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '选择文件', self._last_dir,
            '支持的文件 (*.tif *.tiff *.shp *.geojson *.json *.kml *.gpkg);;所有文件 (*)')
        for p in paths:
            self._last_dir = os.path.dirname(p)
            self._settings.setValue('last_dir', self._last_dir)
            self._load_file(p)

    def _load_file(self, path):
        ext = path.lower()
        if ext.endswith(RASTER_EXTS):
            self._load_raster(path)
        elif ext.endswith(VECTOR_EXTS):
            self._load_vector(path)
        else:
            self._sl.setText(f'不支持的文件格式: {os.path.basename(path)}')

    def _load_raster(self, path):
        name = os.path.basename(path)
        rr = None
        self._busy_start(f'正在加载栅格: {name} ...', 5)
        try:
            self._busy_step('正在读取栅格元数据 ...', 15)
            rr = RasterReader(path)

            if rr.bands == 0:
                rr.close()
                self._busy_end('栅格文件不包含有效波段')
                return

            self._busy_step('正在检查坐标系 ...', 25)
            # 设置工程 CRS：栅格不能即时重投影，首次加入栅格时以栅格 CRS 为工程 CRS。
            existing_rasters = self.layer_panel.raster_layers()
            if rr.crs and (self._project_crs is None or not existing_rasters):
                if self._project_crs != rr.crs:
                    self._project_crs = rr.crs
                    self._reproject_vector_layers()

            # 创建图层
            layer = LayerInfo()
            layer.name = name
            layer.path = path
            layer.layer_type = 'raster'
            layer.reader = rr

            # 解析忽略值
            vals = []
            for p in re.split(r'[,，\s]+', layer.ignore_text.strip()):
                try:
                    vals.append(float(p))
                except ValueError:
                    pass
            rr.ignore_vals = vals

            # 默认波段设置
            if rr.bands >= 3:
                layer.band_mode = 'rgb'
                layer.rgb_bands = [1, 2, 3]
            else:
                layer.band_mode = 'single'
                layer.band = 1
                layer.colormap = 'viridis'

            self._busy_step('正在计算显示拉伸 ...', 45)
            self._update_layer_levels(layer)

            # 创建 ImageItem
            im = pg.ImageItem()
            im.setOpacity(layer.opacity)
            layer.image_item = im

            self._busy_step('正在添加到画布 ...', 60)
            self.pw.addItem(im)
            self.layer_panel.add_layer(layer)

            self._busy_step('正在生成预览概览 ...', 75)
            self._render_raster_overview(layer)

            self._busy_step('正在复位视图 ...', 92)
            self._reset_view()

            self._busy_end(f'已加载: {layer.name}  ({rr.w}×{rr.h}, {rr.bands}波段)')
        except Exception as e:
            if rr is not None:
                try:
                    rr.close()
                except Exception:
                    pass
            self._busy_end(f'加载栅格失败: {e}')

    def _read_vector_file(self, path):
        """优先用 pyogrio/Arrow 读取，失败后按常见中文编码回退。"""
        attempts = [
            {'engine': 'pyogrio', 'use_arrow': True},
            {'engine': 'pyogrio'},
            {'encoding': 'utf-8'},
            {'encoding': 'gbk'},
            {'encoding': 'gb18030'},
            {},
        ]
        errors = []
        for kw in attempts:
            try:
                return gpd.read_file(path, **kw)
            except Exception as e:
                errors.append(f"{kw or 'default'}: {e}")
        raise RuntimeError('；'.join(errors[-3:]))

    def _clean_vector_gdf(self, gdf):
        try:
            gdf = gdf[gdf.geometry.notna() & (~gdf.geometry.is_empty)].copy()
        except Exception:
            pass
        try:
            gdf['geometry'] = gdf.geometry.make_valid()
        except Exception:
            pass
        return gdf

    def _refresh_vector_item(self, layer):
        if layer.graphics_item:
            try:
                self.pw.removeItem(layer.graphics_item)
            except Exception:
                pass
        gi = VectorGraphicsItem(layer.gdf_proj, layer.pen_color, layer.pen_width)
        gi.setOpacity(layer.opacity)
        gi.setVisible(layer.visible)
        layer.graphics_item = gi
        self.pw.addItem(gi)

    def _reproject_vector_layers(self):
        if self._project_crs is None:
            return
        for layer in self.layer_panel.vector_layers():
            if layer.gdf is None:
                continue
            try:
                src = layer.gdf
                if src.crs is None:
                    src = src.set_crs(self._project_crs, allow_override=True)
                    layer.gdf = src
                layer.gdf_proj = src.to_crs(self._project_crs) if src.crs != self._project_crs else src
                self._refresh_vector_item(layer)
            except Exception as e:
                self._sl.setText(f'矢量重投影失败: {layer.name}: {e}')
        self._on_layers_changed()

    def _load_vector(self, path):
        name = os.path.basename(path)
        self._busy_start(f'正在加载矢量: {name} ...', 5)
        try:
            self._busy_step('正在读取矢量文件 ...', 15)
            gdf = self._clean_vector_gdf(self._read_vector_file(path))

            if len(gdf) == 0:
                self._busy_end('矢量文件不包含要素')
                return

            self._busy_step('正在检查坐标系 ...', 35)
            # 设置工程 CRS；无 .prj 的 SHP 在已有工程 CRS 下按工程 CRS 解释。
            if gdf.crs is None and self._project_crs is not None:
                try:
                    gdf = gdf.set_crs(self._project_crs, allow_override=True)
                except Exception:
                    pass
            if self._project_crs is None and gdf.crs:
                self._project_crs = gdf.crs

            layer = LayerInfo()
            layer.name = name
            layer.path = path
            layer.layer_type = 'vector'
            layer.gdf = gdf

            self._busy_step('正在投影矢量坐标 ...', 55)
            # 投影到工程 CRS
            if self._project_crs and gdf.crs and gdf.crs != self._project_crs:
                layer.gdf_proj = gdf.to_crs(self._project_crs)
            else:
                layer.gdf_proj = gdf

            self._busy_step('正在构建矢量图形 ...', 75)
            self._refresh_vector_item(layer)

            self._busy_step('正在添加图层 ...', 90)
            self.layer_panel.add_layer(layer)

            # 如果这是第一个图层，复位视图
            if len(self.layer_panel.layers) == 1:
                self._reset_view()

            self._busy_end(f'已加载矢量: {layer.name}  ({len(gdf)}个要素)')
        except Exception as e:
            self._busy_end(f'加载矢量失败: {e}')
            QMessageBox.warning(self, '加载矢量失败', f'{name} 加载失败：\n{e}')

    # ---- 图层渲染 ----
    def _update_layer_levels(self, layer):
        """为栅格图层计算显示级别"""
        if not layer.reader:
            return
        rr = layer.reader
        bands = layer_read_bands(layer)
        ov = rr.overview(bands)

        layer.vmins = []
        layer.vmaxs = []
        layer.cdfs = []
        layer.binss = []

        for i in range(len(bands)):
            v = ov[:, :, i]
            v = v[np.isfinite(v)]
            if v.size == 0:
                layer.vmins.append(0.0)
                layer.vmaxs.append(1.0)
                layer.cdfs.append(None)
                layer.binss.append(None)
                continue

            if layer.stretch == '百分比截断':
                vmin = float(np.percentile(v, 2))
                vmax = float(np.percentile(v, 98))
            elif layer.stretch == '全局最值':
                vmin = float(np.min(v))
                vmax = float(np.max(v))
            elif layer.stretch == '标准差拉伸':
                mean, std = np.mean(v), np.std(v)
                n = layer.std_n
                vmin = float(mean - n * std)
                vmax = float(mean + n * std)
            elif layer.stretch == '直方图均衡化':
                hist, bins = np.histogram(v.flatten(), bins=256)
                cdf = hist.cumsum()
                layer.cdfs.append(
                    (cdf - cdf.min()) * 255.0 / (cdf.max() - cdf.min() + 1e-8))
                layer.binss.append(bins[:-1])
                vmin, vmax = 0.0, 255.0
            else:
                vmin, vmax = 0.0, 1.0

            if layer.stretch != '直方图均衡化':
                layer.cdfs.append(None)
                layer.binss.append(None)

            if vmin >= vmax:
                vmax = vmin + 1.0
            layer.vmins.append(vmin)
            layer.vmaxs.append(vmax)

    def _render_raster_overview(self, layer):
        """全图概览渲染"""
        if not layer.reader or not layer.image_item:
            return
        rr = layer.reader
        bands = layer_read_bands(layer)
        ov = rr.overview(bands)
        self._show_raster_data(layer, ov, rr.extent)

    def _render_raster_window(self, layer, xmin, ymin, xmax, ymax, sw, sh):
        """窗口区域渲染"""
        if not layer.reader or not layer.image_item:
            return
        rr = layer.reader

        # 裁剪到栅格范围
        rx = rr.extent
        xmin = max(xmin, rx[0])
        ymin = max(ymin, rx[1])
        xmax = min(xmax, rx[2])
        ymax = min(ymax, rx[3])

        if xmax <= xmin or ymax <= ymin:
            return

        bands = layer_read_bands(layer)
        data = rr.read_extent(bands, xmin, ymin, xmax, ymax, sw, sh)
        if data is not None:
            self._show_raster_data(layer, data, (xmin, ymin, xmax, ymax))

    def _show_raster_data(self, layer, data, extent):
        """将数据推送到 ImageItem"""
        xmin, ymin, xmax, ymax = extent
        im = layer.image_item
        is_single = (layer.band_mode == 'single')

        if is_single:
            band_data = data[:, :, 0]
            if layer.stretch == '直方图均衡化' and layer.cdfs and layer.cdfs[0] is not None:
                mask = np.isfinite(band_data)
                if np.any(mask):
                    band_data = band_data.copy()
                    band_data[mask] = np.interp(
                        band_data[mask], layer.binss[0], layer.cdfs[0]
                    ).astype(np.float32)
                im.setImage(band_data, levels=[0, 255], autoLevels=False)
            else:
                vmin = layer.vmins[0] if layer.vmins else 0
                vmax = layer.vmaxs[0] if layer.vmaxs else 1
                im.setImage(band_data, levels=[vmin, vmax], autoLevels=False)
            from colormap import CMAP_STORE
            lut = CMAP_STORE.get(layer.colormap, layer.cmap_reverse)
            im.setLookupTable(lut)
        else:
            h, w, c = data.shape
            out = np.zeros((h, w, 4), dtype=np.uint8)
            mask = np.isfinite(data[:, :, 0])
            out[:, :, 3][mask] = 255
            for i in range(min(c, 3)):
                b_data = data[:, :, i]
                valid = b_data[mask]
                if valid.size > 0:
                    if layer.stretch == '直方图均衡化' and layer.cdfs and i < len(layer.cdfs) and layer.cdfs[i] is not None:
                        stretched = np.interp(valid, layer.binss[i], layer.cdfs[i])
                    else:
                        vmin = layer.vmins[i] if i < len(layer.vmins) else 0
                        vmax = layer.vmaxs[i] if i < len(layer.vmaxs) else 1
                        stretched = (valid - vmin) / (vmax - vmin + 1e-8) * 255.0
                        stretched = np.clip(stretched, 0, 255)
                    out[:, :, i][mask] = stretched.astype(np.uint8)
            im.setImage(out, autoLevels=False)
            im.setLookupTable(None)

        # 地理定位: 用 QTransform 将像素坐标映射到地理坐标
        dh, dw = data.shape[:2]
        tr = QTransform()
        tr.translate(xmin, ymax)  # 左上角地理坐标
        px_w = (xmax - xmin) / max(dw, 1)
        px_h = -(ymax - ymin) / max(dh, 1)  # 负值因为 y 向下
        tr.scale(px_w, px_h)
        im.setTransform(tr)

    # ---- 画布事件 ----
    def _on_range(self, *args):
        if not self._lock and self.layer_panel.raster_layers():
            self._timer.start()

    def _refresh(self):
        if self._lock:
            return
        vb = self.pw.getViewBox()
        xr, yr = vb.viewRange()
        xmin, xmax = xr
        ymin, ymax = yr

        sw = max(1, int(vb.width() * 1.2))
        sh = max(1, int(vb.height() * 1.2))

        self._lock = True
        for layer in self.layer_panel.layers:
            if layer.layer_type == 'raster' and layer.visible and layer.reader:
                self._render_raster_window(layer, xmin, ymin, xmax, ymax, sw, sh)
        self._lock = False

    def _reset_view(self):
        ext = self._full_extent()
        if not ext:
            return
        xmin, ymin, xmax, ymax = ext
        if xmax <= xmin or ymax <= ymin:
            return
        self._lock = True
        self.pw.setRange(xRange=[xmin, xmax], yRange=[ymin, ymax], padding=0.02)
        self._lock = False
        self._refresh()

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

    def _zoom_to_layer(self, lid):
        layer = self.layer_panel.get_layer(lid)
        if not layer:
            return
        if layer.layer_type == 'raster' and layer.reader:
            e = layer.reader.extent
        elif layer.layer_type == 'vector' and layer.gdf_proj is not None:
            b = layer.gdf_proj.total_bounds
            e = (b[0], b[1], b[2], b[3])
        else:
            return
        self._lock = True
        self.pw.setRange(xRange=[e[0], e[2]], yRange=[e[1], e[3]], padding=0.05)
        self._lock = False
        self._refresh()

    def _on_layers_changed(self):
        """图层属性或顺序变化时刷新"""
        # 重建画布 Z 顺序。不可见图层不重新读栅格，避免取消勾选触发慢读或越界。
        for layer in reversed(self.layer_panel.layers):
            if layer.image_item:
                layer.image_item.setVisible(layer.visible)
                if layer.visible:
                    try:
                        self._update_layer_levels(layer)
                    except Exception as e:
                        layer.visible = False
                        layer.image_item.setVisible(False)
                        self._sl.setText(f'图层刷新失败，已临时隐藏 {layer.name}: {e}')
            if layer.graphics_item:
                layer.graphics_item.setVisible(layer.visible)

        # 清理已移除图层的画布项
        active_items = set()
        for layer in self.layer_panel.layers:
            if layer.image_item:
                active_items.add(layer.image_item)
            if layer.graphics_item:
                active_items.add(layer.graphics_item)

        for item in list(self.pw.items()):
            if isinstance(item, (pg.ImageItem, VectorGraphicsItem)):
                if item not in active_items:
                    self.pw.removeItem(item)

        # Z 顺序: 后加的在上面 (列表头部的在上面)
        z = 0
        for layer in reversed(self.layer_panel.layers):
            if layer.image_item:
                layer.image_item.setZValue(z)
                z += 1
            if layer.graphics_item:
                layer.graphics_item.setZValue(z)
                z += 1

        self._refresh()

    def _on_click(self, ev):
        btn = ev.button()

        if btn == Qt.MouseButton.RightButton or btn == 2:
            self._show_export()
            return

        if btn != Qt.MouseButton.LeftButton and btn != 1:
            return

        try:
            pos = self.pw.getViewBox().mapSceneToView(ev.scenePos())
            gx, gy = pos.x(), pos.y()

            # 找到最上面的可见栅格图层来查值
            info_parts = [f'坐标: X={gx:.6f}  Y={gy:.6f}']
            for layer in self.layer_panel.layers:
                if layer.layer_type == 'raster' and layer.visible and layer.reader:
                    rr = layer.reader
                    inv = ~rr.transform
                    cf, rf = inv * (gx, gy)
                    c, r = int(cf), int(rf)
                    bands = layer_read_bands(layer)
                    vals = [rr.pixel(b, r, c) for b in bands]
                    if None not in vals:
                        if len(vals) == 1:
                            v = vals[0]
                            vs = '无效' if np.isnan(v) else f'{v:.6g}'
                        else:
                            vs = ', '.join('无效' if np.isnan(v) else f'{v:.6g}' for v in vals)
                        info_parts.append(f'[{layer.name}] = {vs}')
                    break  # 只查最上层

            self._sl.setText('    '.join(info_parts))
        except Exception as err:
            self._sl.setText(f'查询失败: {err}')

    # ---- 对话框 ----
    def _show_export(self):
        if not self.layer_panel.layers:
            self._sl.setText('请先加载图层')
            return
        dlg = ExportDialog(
            self.layer_panel,
            self.pw.getViewBox(),
            self._last_dir,
            self
        )
        dlg.exec()

    def _show_composite(self):
        if not self.layer_panel.layers:
            self._sl.setText('请先加载图层')
            return
        dlg = CompositeDialog(self.layer_panel, self)
        dlg.exec()

    def _show_cmap_mgr(self):
        dlg = CMapManagerDialog(self)
        dlg.exec()
        self.layer_panel.refresh_cmap_combo()

    def closeEvent(self, e):
        for layer in self.layer_panel.layers:
            if layer.reader:
                layer.reader.close()
        super().closeEvent(e)
