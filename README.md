# TIF查看器 V2

遥感影像与矢量数据可视化工具，基于 PySide6 + pyqtgraph + Matplotlib + Rasterio + GeoPandas 构建。

## 功能特性

- **多图层管理** — 支持同时加载多个 TIF 栅格文件和 SHP/GeoJSON/KML/GPKG 矢量文件，TIF 与矢量平等加载、互不依赖
- **图层控制** — 可见性切换、拖拽排序、透明度调节、移除图层
- **栅格显示** — 单波段/多波段彩色模式、4种拉伸方式（百分比截断/全局最值/标准差拉伸/直方图均衡化）、60+ 内置色带、色带反转
- **像素查询** — 点击画布任意位置查看对应栅格像元值
- **高质量导出** — 自定义 DPI（最高 2400）、色带数值标注、坐标框、标题/轴标题、预览示意图
- **导出范围** — 当前视窗 / 完整数据范围 / 矢量图层边界 / 矢量某一要素边界
- **色带对称模式** — 支持正负值对称显示（差值图可视化）
- **组图导出** — 最多 6×6 子图网格，支持独立色带/共用色带、矢量叠加控制、保持地图比例
- **色带管理** — 动态添加/删除 matplotlib 色带，支持反转
- **字体自定义** — 中英文字体、字号可调

## 项目结构

```
V2重构版/
├── main.py                    # 入口
├── config.py                  # 全局配置、工具函数、matplotlib 初始化
├── styles.py                  # Qt 样式表
├── colormap.py                # 色带存储系统 (CMapStore)
├── raster_reader.py           # 栅格读取器 (RasterReader)
├── layer.py                   # 图层数据类 + 波段处理函数
├── vector_item.py             # 矢量图形项 (VectorGraphicsItem)
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # 主窗口 (TIFViewer)
│   ├── layer_panel.py         # 图层面板
│   ├── export_dialog.py       # 单图导出对话框
│   ├── composite_dialog.py    # 组图导出对话框
│   └── colormap_dialog.py     # 色带管理对话框
├── source/
│   └── 图标.ico               # 应用图标
├── requirements.txt
└── README.md
```

## 安装与运行

### 环境要求

- Python 3.9+
- GDAL 库（rasterio 依赖，建议通过 conda 安装）

### 安装依赖

```bash
pip install -r requirements.txt
```

> **注意：** 如果 pip 安装 rasterio 遇到 GDAL 相关问题，推荐使用 conda：
> ```bash
> conda install -c conda-forge rasterio geopandas pyogrio
> pip install PySide6 pyqtgraph matplotlib
> ```

### 运行

```bash
python main.py
```

### 打包为 exe

```bash
python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --contents-directory "." \
  --name "TIF查看器V2" \
  -i "source\图标.ico" \
  --add-data "source;source" \
  --collect-submodules rasterio \
  --collect-binaries rasterio \
  --collect-data rasterio \
  --collect-binaries pyproj \
  --collect-data pyproj \
  --collect-binaries pyogrio \
  --collect-data pyogrio \
  --collect-binaries shapely \
  --collect-data matplotlib \
  --collect-submodules pyqtgraph \
  --hidden-import=matplotlib.backends.backend_agg \
  --hidden-import=mpl_toolkits.axes_grid1 \
  --hidden-import=geopandas \
  --hidden-import=pyogrio \
  --exclude-module tkinter \
  --exclude-module pytest \
  --exclude-module IPython \
  --exclude-module jupyter \
  --exclude-module notebook \
  --exclude-module scipy \
  --exclude-module sklearn \
  --exclude-module cv2 \
  --exclude-module PyQt5 \
  --exclude-module PyQt6 \
  --exclude-module PySide2 \
  --exclude-module geopandas.explore \
  --exclude-module folium \
  --exclude-module mapclassify \
  --exclude-module xyzservices \
  --exclude-module selenium \
  --exclude-module matplotlib.backends.backend_tkagg \
  --exclude-module matplotlib.backends.backend_qt5agg \
  main.py
```

## 使用说明

1. 点击 **打开文件** 或拖拽文件到窗口加载 TIF/SHP 等数据
2. 左侧 **图层面板** 管理图层顺序、可见性、显示参数
3. 右键画布或点击 **导出图片** 打开单图导出对话框
4. 点击 **组图导出** 创建多子图组合图
5. **色带管理** 支持动态增删色带

## 许可

MIT
