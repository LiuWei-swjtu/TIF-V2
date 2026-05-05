"""
色带存储系统：生成、管理、增删、反转 colormap
"""
import numpy as np
from matplotlib import colormaps as mpl_colormaps
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtCore import Qt

from config import DEFAULT_CMAPS


def make_lut(name, reverse=False):
    """生成 256×4 uint8 查找表"""
    try:
        cmap = mpl_colormaps[name]
    except Exception:
        from matplotlib.cm import get_cmap
        cmap = get_cmap(name)
    arr = (cmap(np.linspace(0, 1, 256)) * 255).astype(np.uint8)
    if reverse:
        arr = arr[::-1].copy()
    return arr


def lut_to_icon(lut, w=100, h=16):
    """LUT -> QIcon 用于下拉框"""
    qimg = QImage(256, 1, QImage.Format_RGBA8888)
    for i in range(256):
        c = lut[i]
        qimg.setPixelColor(i, 0, QColor(int(c[0]), int(c[1]), int(c[2]),
                                         int(c[3]) if len(c) >= 4 else 255))
    px = QPixmap.fromImage(qimg).scaled(w, h, Qt.IgnoreAspectRatio,
                                         Qt.SmoothTransformation)
    return QIcon(px)


class CMapStore:
    """全局色带存储，支持动态增删与反转"""

    def __init__(self):
        self.names: list[str] = list(DEFAULT_CMAPS)
        self.luts: dict[str, np.ndarray] = {}
        self._reversed: dict[str, np.ndarray] = {}
        for n in self.names:
            self.luts[n] = make_lut(n)
            self._reversed[n] = make_lut(n, reverse=True)

    def get(self, name, reverse=False):
        key = name
        store = self._reversed if reverse else self.luts
        if key not in store:
            store[key] = make_lut(name, reverse=reverse)
        return store[key]

    def add(self, name):
        if name not in self.names:
            try:
                self.luts[name] = make_lut(name)
                self._reversed[name] = make_lut(name, reverse=True)
                self.names.append(name)
                return True
            except Exception:
                return False
        return False

    def remove(self, name):
        if name in self.names and name not in DEFAULT_CMAPS[:10]:
            self.names.remove(name)
            self.luts.pop(name, None)
            self._reversed.pop(name, None)
            return True
        return False

    def icon(self, name, reverse=False):
        return lut_to_icon(self.get(name, reverse))


CMAP_STORE = CMapStore()
