# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

纽约网约车司机「大单热区」可视化：处理 NYC TLC 高频网约车（HVFHV）月度行程数据，
按 接单区域 × 星期几 × 小时 聚合，在纯静态 Leaflet 网页地图上以等值区域图呈现。
用户是 Uber/Lyft 司机，用它判断当前时段去哪里更容易接到大单。

## 常用命令

```bash
# 运行网页（纯静态，无构建步骤）
cd web && python3 -m http.server 8765

# 数据处理（依赖装在 .venv）
.venv/bin/python scripts/process_trips.py data/fhvhv_YYYY-MM.parquet  # 重新聚合 → web/data/stats.json
.venv/bin/python scripts/make_zones_geojson.py                        # 重建区域边界 → web/data/taxi_zones.geojson

# 下载新月份数据（TLC 约有 2 个月发布延迟，每月 ~500MB）
curl -o data/fhvhv_YYYY-MM.parquet "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_YYYY-MM.parquet"
```

没有测试和 lint；验证方式是启动 http.server 后在浏览器里看地图渲染与控制台。

## 架构

数据管道（一次性/每月运行）与前端（静态）完全解耦，接口是 `web/data/` 下两个 JSON：

1. **`scripts/make_zones_geojson.py`** — TLC 官方 taxi_zones shapefile（EPSG:2263）
   → Douglas-Peucker 简化 → WGS84 GeoJSON（~0.3MB，含 id/zone/borough 属性）。
2. **`scripts/process_trips.py`** — 500MB parquet（~2200万行）→ `stats.json`（~0.8MB）。
   核心口径：**earn = driver_pay + tips**；大单分三档阈值（全市 P90 动态 / $70 / $100，
   写进 `meta.thresholds`）。输出结构：
   `stats[zoneId][dow][hour] = [订单数, 平均收入, 大单数P90, 大单数$70, 大单数$100]`，
   dow 0=周一；`meta.days_per_dow` 用于把月度计数换算成「每小时大单数」。
3. **`scripts/fetch_hotels.py`** — Overpass API（多镜像轮询，需 User-Agent）拉取
   OSM 酒店 POI → 射线法归属到 taxi zone → `web/data/hotels.json`。
4. **`web/index.html`** — 单文件前端（Leaflet 从 `web/lib/` 本地加载，地图瓦片用 CARTO CDN）。
   默认时段取 **America/New_York 当前时间**（不是本机时区）；着色是当前时段内
   7 档分位数分箱（相对比较，非固定刻度）；样本 <10 单（MIN_TRIPS）的格子置灰。
   酒店图层开启时 Top 榜切换为酒店排名（值 = 酒店所在区域的当前指标）。

## 约定

- 前端改动时保持深/浅两套顺序色阶（RAMP_LIGHT / RAMP_DARK）同步：深色模式下近零值向深色退隐、高值变亮，方向与浅色相反。
- UI 文案为简体中文。
- `data/` 下的原始 parquet 是可再生的大文件，不要提交到版本库（目前项目未启用 git）。
- stats.json 结构变更时，前端 `zoneValue()` / `tipHtml()` 需同步修改。
