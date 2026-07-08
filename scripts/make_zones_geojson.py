"""将 TLC 官方出租车区域 shapefile (EPSG:2263) 转换为简化后的 WGS84 GeoJSON。"""
import json
import math
from pathlib import Path

import shapefile  # pyshp
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
SHP = ROOT / "data/taxi_zones_shp/taxi_zones/taxi_zones.shp"
OUT = ROOT / "web/data/taxi_zones.geojson"

# 简化容差（英尺，EPSG:2263 单位）。~50ft 在城市尺度上视觉无损。
TOLERANCE = 50.0


def point_seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def douglas_peucker(points, tol):
    """迭代式 Douglas-Peucker 简化。"""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        dmax, idx = -1.0, -1
        for i in range(lo + 1, hi):
            d = point_seg_dist(points[i], points[lo], points[hi])
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol:
            keep[idx] = True
            stack.append((lo, idx))
            stack.append((idx, hi))
    return [p for p, k in zip(points, keep) if k]


def main():
    sf = shapefile.Reader(str(SHP))
    fields = [f[0] for f in sf.fields[1:]]
    tr = Transformer.from_crs("EPSG:2263", "EPSG:4326", always_xy=True)

    features = []
    for sr in sf.shapeRecords():
        rec = dict(zip(fields, sr.record))
        shape = sr.shape
        parts = list(shape.parts) + [len(shape.points)]
        rings = []
        for i in range(len(shape.parts)):
            ring = shape.points[parts[i]:parts[i + 1]]
            ring = douglas_peucker(ring, TOLERANCE)
            if len(ring) < 4:
                continue
            lonlat = [tr.transform(x, y) for x, y in ring]
            rings.append([[round(lon, 5), round(lat, 5)] for lon, lat in lonlat])
        if not rings:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "id": int(rec["LocationID"]),
                "zone": rec["zone"],
                "borough": rec["borough"],
            },
            # 简化处理：外环+洞的归属不做严格判断，作为多个多边形渲染即可
            "geometry": {"type": "MultiPolygon", "coordinates": [[r] for r in rings]},
        })

    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                              separators=(",", ":")))
    print(f"写出 {len(features)} 个区域 -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
