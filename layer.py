"""
图层信息数据类与波段处理函数
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional, Any

import numpy as np


@dataclass
class LayerInfo:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ''
    path: str = ''
    layer_type: str = ''  # 'raster' / 'vector'
    visible: bool = True
    opacity: float = 1.0

    # 栅格属性
    reader: Optional[Any] = None
    image_item: Optional[Any] = None
    band_mode: str = 'single'
    band: int = 1
    rgb_bands: list[int] = field(default_factory=lambda: [1, 2, 3])
    colormap: str = 'gray'
    cmap_reverse: bool = False
    stretch: str = '百分比截断'
    std_n: float = 2.0
    ignore_text: str = '-9999,'
    vmins: list[float] = field(default_factory=list)
    vmaxs: list[float] = field(default_factory=list)
    cdfs: list[Any] = field(default_factory=list)
    binss: list[Any] = field(default_factory=list)

    # 矢量属性
    gdf: Optional[Any] = None
    gdf_proj: Optional[Any] = None  # 投影到工程 CRS 后的
    graphics_item: Optional[Any] = None
    pen_color: str = '#000000'
    pen_width: int = 2


def layer_read_bands(layer):
    """返回当前图层应该读取的安全波段号，并同步修正图层状态。"""
    rr = layer.reader
    if rr is None:
        return [1]
    count = max(1, int(rr.bands))

    def clamp(v):
        try:
            iv = int(v)
        except Exception:
            iv = 1
        return min(max(iv, 1), count)

    if layer.band_mode == 'rgb' and count >= 3:
        bands = list(layer.rgb_bands or [1, 2, 3])
        bands = (bands + [1, 2, 3])[:3]
        layer.rgb_bands = [clamp(b) for b in bands]
        return layer.rgb_bands

    layer.band_mode = 'single'
    layer.band = clamp(layer.band)
    return [layer.band]


def layer_stretch_limits(values, layer):
    """按图层当前拉伸方式计算显示上下限；直方图均衡化由专门函数处理。"""
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0, 1.0

    if layer.stretch == '百分比截断':
        vmin = float(np.percentile(values, 2))
        vmax = float(np.percentile(values, 98))
    elif layer.stretch == '全局最值':
        vmin = float(np.min(values))
        vmax = float(np.max(values))
    elif layer.stretch == '标准差拉伸':
        mean, std = np.mean(values), np.std(values)
        n = layer.std_n
        vmin = float(mean - n * std)
        vmax = float(mean + n * std)
    else:
        vmin = float(np.min(values))
        vmax = float(np.max(values))

    if vmin >= vmax:
        vmax = vmin + 1.0
    return vmin, vmax


def layer_histogram_equalized_band(band_data, layer, band_index=0):
    """把原始波段值映射到 0-255 的直方图均衡化显示值。"""
    if not (layer.cdfs and layer.binss):
        return None
    if band_index >= len(layer.cdfs) or band_index >= len(layer.binss):
        return None
    cdf = layer.cdfs[band_index]
    bins = layer.binss[band_index]
    if cdf is None or bins is None:
        return None

    out = band_data.astype(np.float32, copy=True)
    mask = np.isfinite(out)
    if np.any(mask):
        out[mask] = np.interp(out[mask], bins, cdf).astype(np.float32)
    return out


def layer_single_band_for_matplotlib(band_data, layer):
    """返回 Matplotlib imshow 可直接使用的单波段显示数组与 vmin/vmax。"""
    if layer.stretch == '直方图均衡化':
        eq = layer_histogram_equalized_band(band_data, layer, 0)
        if eq is not None:
            return eq, 0.0, 255.0, True

    values = band_data[np.isfinite(band_data)]
    vmin, vmax = layer_stretch_limits(values, layer)
    return band_data, vmin, vmax, False


def layer_rgb_for_matplotlib(data, layer):
    """让导出 RGB 与主界面保持一致：直方图均衡化时逐通道套用缓存 CDF。"""
    h, w, c = data.shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(min(c, 3)):
        ch = data[:, :, i]
        if layer.stretch == '直方图均衡化':
            eq = layer_histogram_equalized_band(ch, layer, i)
            if eq is not None:
                rgb[:, :, i] = np.clip(eq / 255.0, 0, 1)
                continue

        vv = ch[np.isfinite(ch)]
        if vv.size > 0:
            lo, hi = np.percentile(vv, [2, 98])
            if hi > lo:
                ch = (ch - lo) / (hi - lo)
            ch = np.clip(ch, 0, 1)
        rgb[:, :, i] = ch
    return np.nan_to_num(rgb, nan=1.0)
