"""
高效影像读取：窗口、概览、像素查询
"""
import numpy as np
import rasterio
from rasterio.enums import Resampling


class RasterReader:
    """高效影像读取，支持窗口、概览、像素查询"""

    def __init__(self, path):
        self.ds = rasterio.open(path)
        self.path = path
        self.w = self.ds.width
        self.h = self.ds.height
        self.bands = self.ds.count
        self.nodata = self.ds.nodata
        self.crs = self.ds.crs
        self.transform = self.ds.transform
        self.bounds = self.ds.bounds  # BoundingBox(left, bottom, right, top)
        self.ignore_vals: list[float] = []

    @property
    def extent(self):
        """返回 (xmin, ymin, xmax, ymax)"""
        b = self.bounds
        return (b.left, b.bottom, b.right, b.top)

    def _safe_bands(self, bands):
        """把 UI 传入的波段号钳制到 rasterio 可读取的 1-based 范围。"""
        if bands is None:
            bands = [1]
        if isinstance(bands, (int, np.integer)):
            bands = [int(bands)]
        safe = []
        for b in bands:
            try:
                ib = int(b)
            except Exception:
                ib = 1
            safe.append(min(max(ib, 1), max(self.bands, 1)))
        return safe or [1]

    def overview(self, bands, max_px=1536):
        bands = self._safe_bands(bands)
        ratio = max(self.w, self.h) / max_px
        if ratio <= 1:
            oh, ow = self.h, self.w
        else:
            oh, ow = max(1, int(self.h / ratio)), max(1, int(self.w / ratio))
        return self._read(bands, out=(oh, ow))

    def read_extent(self, bands, xmin, ymin, xmax, ymax, out_w, out_h):
        """读取指定地理范围；不裁剪输出 extent，避免导出时 TIF/SHP 错位。"""
        bands = self._safe_bands(bands)
        if xmax <= xmin or ymax <= ymin:
            return None
        rxmin, rymin, rxmax, rymax = self.extent
        if xmax <= rxmin or xmin >= rxmax or ymax <= rymin or ymin >= rymax:
            return None
        try:
            win = rasterio.windows.from_bounds(
                xmin, ymin, xmax, ymax, transform=self.transform
            )
        except Exception:
            inv = ~self.transform
            c0f, r0f = inv * (xmin, ymax)
            c1f, r1f = inv * (xmax, ymin)
            win = rasterio.windows.Window(c0f, r0f, c1f - c0f, r1f - r0f)
        if win.width == 0 or win.height == 0:
            return None
        return self._read(bands, win=win, out=(max(1, out_h), max(1, out_w)))

    def window(self, bands, c0, r0, cw, rh, ow, oh):
        bands = self._safe_bands(bands)
        win = rasterio.windows.Window(c0, r0, cw, rh)
        return self._read(bands, win=win, out=(max(1, oh), max(1, ow)))

    def pixel(self, band, r, c):
        band = self._safe_bands([band])[0]
        if not (0 <= c < self.w and 0 <= r < self.h):
            return None
        win = rasterio.windows.Window(int(c), int(r), 1, 1)
        val = float(self.ds.read(band, window=win)[0, 0])
        if (self.nodata is not None and val == self.nodata) or val in self.ignore_vals:
            return np.nan
        return val

    def geo(self, r, c):
        return self.ds.xy(r, c)

    def _read(self, bands, win=None, out=None):
        bands = self._safe_bands(bands)
        kw = {'resampling': Resampling.nearest, 'boundless': True, 'masked': True}
        if win is not None:
            kw['window'] = win
        if out:
            kw['out_shape'] = (len(bands), out[0], out[1])
        data = self.ds.read(bands, **kw).astype(np.float32)
        if np.ma.isMaskedArray(data):
            data = data.filled(np.nan)
        data = np.transpose(data, (1, 2, 0))
        if self.nodata is not None:
            data[data == self.nodata] = np.nan
        for iv in self.ignore_vals:
            data[data == iv] = np.nan
        return data

    def close(self):
        self.ds.close()
