"""
全局配置：常量、工具函数、matplotlib 初始化
"""
import sys
import os
from pathlib import Path

os.environ['GDAL_NUM_THREADS'] = 'ALL_CPUS'

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

APP_NAME = '遥感可视化工具 V2'
ORG_NAME = 'GeoVis'

DEFAULT_CMAPS = [
    'gray', 'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'jet', 'turbo', 'rainbow', 'nipy_spectral', 'gist_ncar',
    'terrain', 'ocean', 'gist_earth', 'cubehelix', 'brg',
    'Blues', 'Greens', 'Reds', 'Purples', 'Oranges', 'Greys',
    'bone', 'pink', 'copper',
    'hot', 'afmhot', 'cool', 'Wistia', 'autumn', 'spring',
    'summer', 'winter',
    'Spectral', 'RdYlBu', 'RdYlGn', 'BrBG', 'PiYG', 'PRGn',
    'PuOr', 'RdBu', 'RdGy', 'bwr', 'seismic',
    'tab10', 'tab20', 'tab20b', 'tab20c',
    'Set1', 'Set2', 'Set3', 'Pastel1', 'Pastel2', 'Dark2',
    'Paired', 'Accent'
]

RASTER_EXTS = ('.tif', '.tiff')
VECTOR_EXTS = ('.shp', '.geojson', '.json', '.kml', '.gpkg')
ALL_EXTS = RASTER_EXTS + VECTOR_EXTS

DEFAULT_CN_FONT = '宋体'
DEFAULT_EN_FONT = 'Times New Roman'
MAX_EXPORT_READ_PX = 8192
MAX_PREVIEW_READ_PX = 2048


def project_base_dir():
    """返回工程目录。源码运行时为 .py 所在目录；打包后为 exe 所在目录。"""
    try:
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent
    except Exception:
        return Path.cwd()


def app_icon_path():
    """查找工程目录 source 文件夹中的 .ico 图标。优先使用 图标.ico / icon.ico。"""
    source_dir = project_base_dir() / 'source'
    candidates = [
        source_dir / '图标.ico',
        source_dir / 'icon.ico',
        source_dir / 'app.ico',
        source_dir / 'logo.ico',
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    try:
        icons = sorted(source_dir.glob('*.ico'))
        if icons:
            return str(icons[0])
    except Exception:
        pass
    return ''


def app_icon():
    """返回应用图标；找不到图标时返回空 QIcon，不影响程序启动。"""
    from PySide6.QtGui import QIcon
    path = app_icon_path()
    if not path:
        return QIcon()
    icon = QIcon(path)
    return icon if not icon.isNull() else QIcon()


def apply_matplotlib_fonts(cn_font=DEFAULT_CN_FONT, en_font=DEFAULT_EN_FONT, size=10):
    """设置中英文字体回退链，保证中文宋体、英文新罗马优先。"""
    families = [en_font, cn_font, 'SimSun', '宋体', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams.update({
        'font.family': families,
        'font.size': size,
        'axes.unicode_minus': False,
    })
