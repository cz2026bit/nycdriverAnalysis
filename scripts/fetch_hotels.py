"""从 OpenStreetMap Overpass API 拉取纽约市酒店 POI，归属到出租车区域。

输出 web/data/hotels.json: [{name, lat, lon, zone}]
"""
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ZONES = ROOT / "web/data/taxi_zones.geojson"
OUT = ROOT / "web/data/hotels.json"

OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
# NYC 五区 bbox
QUERY = """
[out:json][timeout:120];
(
  node["tourism"="hotel"]["name"](40.49,-74.27,40.92,-73.68);
  way["tourism"="hotel"]["name"](40.49,-74.27,40.92,-73.68);
);
out center tags;
"""


def point_in_ring(lon, lat, ring):
    """射线法点归多边形。"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def main():
    elements = None
    for url in OVERPASS_MIRRORS:
        print(f"请求 {url} ...")
        try:
            r = requests.post(
                url, data={"data": QUERY}, timeout=180,
                headers={"User-Agent": "nycdriverAnalysis/1.0 (personal project)"},
            )
            r.raise_for_status()
            elements = r.json()["elements"]
            break
        except Exception as e:
            print(f"  失败: {e}")
    if elements is None:
        raise SystemExit("所有 Overpass 镜像均失败")
    print(f"OSM 返回 {len(elements)} 个酒店")

    zones = json.loads(ZONES.read_text())["features"]

    def find_zone(lon, lat):
        for f in zones:
            for poly in f["geometry"]["coordinates"]:
                if point_in_ring(lon, lat, poly[0]):
                    return f["properties"]["id"]
        return None

    hotels, seen = [], set()
    for el in elements:
        name = el["tags"].get("name", "").strip()
        if el["type"] == "node":
            lat, lon = el["lat"], el["lon"]
        else:
            c = el.get("center")
            if not c:
                continue
            lat, lon = c["lat"], c["lon"]
        key = name.lower()
        if not name or key in seen:
            continue
        zid = find_zone(lon, lat)
        if zid is None:
            continue  # bbox 内但在 NYC 区域外（新泽西等）
        seen.add(key)
        hotels.append({"name": name, "lat": round(lat, 5), "lon": round(lon, 5), "zone": zid})

    OUT.write_text(json.dumps(hotels, ensure_ascii=False, separators=(",", ":")))
    print(f"写出 {len(hotels)} 家酒店 -> {OUT} ({OUT.stat().st_size/1e3:.0f} KB)")


if __name__ == "__main__":
    main()
