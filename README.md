# 纽约大单热区地图 🚕

基于 NYC TLC 官方高频网约车（Uber/Lyft）行程数据，在浏览器地图上展示
**哪个区域、哪个时段更容易接到大单**（司机单笔到手收入前 10% 的订单）。

## 快速开始

```bash
cd web && python3 -m http.server 8765
# 浏览器打开 http://localhost:8765
```

线上版本：https://cz2026bit.github.io/nycdriverAnalysis/ （推送 main 分支自动部署）

页面默认显示**纽约当前时间**对应的星期和小时，可以：
- 切换星期几和小时滑块，查看任意时段
- 切换指标：每小时大单数（默认）/ 大单概率 / 平均收入
- 切换大单标准：前10%（动态阈值）/ $70+ / $100+
- 🏨 酒店图层：显示 550 家酒店位置，榜单变为酒店排名（按所在区域指标）
- 悬停区域查看详情，点击 Top 榜跳转到对应区域/酒店
- 右上角切换深色/浅色模式

## 更新数据（每月）

TLC 数据约有 2 个月发布延迟。更新到新月份：

```bash
# 1. 下载新月份数据（把 2026-05 换成目标月份）
curl -o data/fhvhv_2026-05.parquet \
  "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2026-05.parquet"

# 2. 重新聚合
.venv/bin/python scripts/process_trips.py data/fhvhv_2026-05.parquet
```

区域边界（`web/data/taxi_zones.geojson`）一般不需要更新；如需重建：
`.venv/bin/python scripts/make_zones_geojson.py`

酒店数据来自 OpenStreetMap，如需更新：`.venv/bin/python scripts/fetch_hotels.py`

## 指标口径

- **大单**：司机单笔到手收入（driver_pay + tips）达到所选档位——
  前10%（全市 P90 动态阈值，当前为 $47.34）/ $70+ / $100+
- **每小时大单数**：该区域该时段（星期几 × 小时）平均每小时产生的大单数，反映供给热度
- **大单概率**：该区域该时段订单中大单的占比
- 样本 < 10 单的格子显示为灰色（数据不足）
- 地图着色为当前时段内 7 档分位数分箱（相对比较）

## 数据来源

- 行程数据：[NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)（High Volume FHV）
- 区域边界：TLC 官方 taxi_zones shapefile（EPSG:2263 → WGS84，Douglas-Peucker 简化）
