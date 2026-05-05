# TIF查看器V2 重构实施计划

**目标：** 将 2913 行单文件 `tif_viewer_v2.py` 拆分为 13 个模块文件

**原则：** 业务逻辑逐字照搬，只做模块拆分 + 接口解耦，不新增/删除功能

## 文件创建顺序（自底向上，无循环依赖）

### Task 1: config.py
- 从原文件提取：常量(APP_NAME, ORG_NAME, DEFAULT_CMAPS, RASTER_EXTS, VECTOR_EXTS, ALL_EXTS, DEFAULT_CN_FONT, DEFAULT_EN_FONT, MAX/MAX_PREVIEW 等)
- 工具函数：project_base_dir(), app_icon_path(), app_icon(), apply_matplotlib_fonts()
- 设置 matplotlib.use('Agg') 和 os.environ['GDAL_NUM_THREADS'] 在最顶部

### Task 2: styles.py
- 提取 STYLE 字符串

### Task 3: colormap.py
- 提取：make_lut(), lut_to_icon(), CMapStore, CMAP_STORE

### Task 4: raster_reader.py
- 提取 RasterReader

### Task 5: layer.py
- 提取 LayerInfo dataclass + 5个波段处理函数

### Task 6: vector_item.py
- 提取 VectorGraphicsItem

### Task 7: ui/colormap_dialog.py
- 提取 CMapManagerDialog
- 解耦：接收 cmap_store 参数而非引用全局

### Task 8: ui/layer_panel.py
- 提取 LayerPanel + 新增 request_add_layer 信号

### Task 9: ui/export_dialog.py
- 提取 ExportDialog，构造函数改为接收 layer_panel

### Task 10: ui/composite_dialog.py
- 提取 CompositeDialog，构造函数改为接收 layer_panel

### Task 11: ui/main_window.py
- 提取 TIFViewer，连接所有信号

### Task 12: main.py
- 提取 main() 入口函数

### Task 13: 项目文件
- requirements.txt, README.md, .gitignore
