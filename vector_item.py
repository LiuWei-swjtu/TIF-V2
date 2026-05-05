"""
矢量图形项：在地理坐标系下使用 pyqtgraph 绘制矢量要素
"""
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QPainterPath
import pyqtgraph as pg
from shapely.geometry import (
    Polygon, MultiPolygon, LineString, MultiLineString,
    Point, MultiPoint, GeometryCollection
)


class VectorGraphicsItem(pg.GraphicsObject):
    """在地理坐标系下绘制矢量"""

    def __init__(self, gdf, pen_color='#000000', pen_width=2):
        super().__init__()
        self.gdf = self._prepare_gdf(gdf)
        self.pen = QPen(QColor(pen_color))
        self.pen.setWidth(pen_width)
        self.pen.setCosmetic(True)
        self._path = QPainterPath()
        self._point_radius = self._estimate_point_radius()
        self._build()

    def _prepare_gdf(self, gdf):
        """用于屏幕显示的轻量化几何，避免超大 SHP 构建 QPainterPath 时长时间假死。"""
        try:
            gdf = gdf[gdf.geometry.notna() & (~gdf.geometry.is_empty)].copy()
        except Exception:
            return gdf
        try:
            b = gdf.total_bounds
            span = max(abs(b[2] - b[0]), abs(b[3] - b[1]))
            if len(gdf) > 2000 and span > 0:
                tol = span / 20000.0
                gdf['geometry'] = gdf.geometry.simplify(tol, preserve_topology=True)
        except Exception:
            pass
        return gdf

    def _estimate_point_radius(self):
        try:
            b = self.gdf.total_bounds
            span = max(abs(b[2] - b[0]), abs(b[3] - b[1]))
            return max(span / 1200.0, 1e-9)
        except Exception:
            return 1.0

    def _walk_geoms(self, geom):
        if geom is None or geom.is_empty:
            return
        if isinstance(geom, GeometryCollection):
            for sub in geom.geoms:
                yield from self._walk_geoms(sub)
        else:
            yield geom

    def _build(self):
        for geom0 in self.gdf.geometry:
            for geom in self._walk_geoms(geom0):
                if isinstance(geom, (Polygon, MultiPolygon)):
                    polys = [geom] if isinstance(geom, Polygon) else geom.geoms
                    for poly in polys:
                        self._add_ring(poly.exterior)
                        for interior in poly.interiors:
                            self._add_ring(interior)
                elif isinstance(geom, (LineString, MultiLineString)):
                    lines = [geom] if isinstance(geom, LineString) else geom.geoms
                    for line in lines:
                        self._add_ring(line, close=False)
                elif isinstance(geom, (Point, MultiPoint)):
                    pts = [geom] if isinstance(geom, Point) else geom.geoms
                    r = self._point_radius
                    for pt in pts:
                        self._path.addEllipse(pt.x - r, pt.y - r, 2 * r, 2 * r)

    def _add_ring(self, ring, close=True):
        coords = list(ring.coords)
        if not coords:
            return
        # Shapely 的坐标可能是 (x, y) 或 (x, y, z)。
        # QPainterPath 只需要二维屏幕坐标，因此统一只取前两个值，兼容 PolygonZ / LineStringZ。
        first = coords[0]
        self._path.moveTo(first[0], first[1])
        for pt in coords[1:]:
            self._path.lineTo(pt[0], pt[1])
        if close:
            self._path.closeSubpath()

    def update_style(self, color, width):
        self.pen = QPen(QColor(color))
        self.pen.setWidth(width)
        self.pen.setCosmetic(True)
        self.update()

    def paint(self, p, *args):
        p.setPen(self.pen)
        p.drawPath(self._path)

    def boundingRect(self):
        return self._path.boundingRect()
