"""处理 TLC 高频网约车 (HVFHV) 行程数据。

按 接单区域 × 星期几 × 小时 聚合，输出前端所需的紧凑 JSON。
每个格子为 [n, avg, big_p90, big_70, big_100]：
  - n:    订单数
  - avg:  平均司机收入 (driver_pay + tips)
  - big_*: 收入达到各档阈值的订单数（P90 动态阈值 / $70 / $100）

用法: python scripts/process_trips.py data/fhvhv_2026-05.parquet
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web/data/stats.json"

COLS = ["pickup_datetime", "PULocationID", "driver_pay", "tips"]


def main(parquet_path: str):
    print(f"读取 {parquet_path} ...")
    df = pq.read_table(parquet_path, columns=COLS).to_pandas()
    print(f"共 {len(df):,} 条行程")

    # 清洗：司机收入必须为正，区域 ID 有效
    df["earn"] = df["driver_pay"].fillna(0) + df["tips"].fillna(0)
    df = df[(df["earn"] > 0) & df["PULocationID"].between(1, 263)]

    # 大单阈值分三档：全市 P90（动态）、$70、$100
    p90 = round(float(df["earn"].quantile(0.90)), 2)
    thresholds = [p90, 70.0, 100.0]
    print(f"大单阈值: P90=${p90} / $70 / $100")

    dt = df["pickup_datetime"]
    df["dow"] = dt.dt.dayofweek.astype("int8")   # 0=周一
    df["hour"] = dt.dt.hour.astype("int8")
    for i, t in enumerate(thresholds):
        df[f"big{i}"] = (df["earn"] >= t)

    # 当月每个星期几出现的天数（用于换算「每小时大单数」）
    days_per_dow = (
        dt.dt.normalize().drop_duplicates().dt.dayofweek.value_counts()
        .reindex(range(7), fill_value=0).tolist()
    )

    g = df.groupby(["PULocationID", "dow", "hour"]).agg(
        n=("earn", "size"), avg=("earn", "mean"),
        big0=("big0", "sum"), big1=("big1", "sum"), big2=("big2", "sum"),
    ).reset_index()

    stats = {}
    for zone, zg in g.groupby("PULocationID"):
        grid = [[[0, 0, 0, 0, 0] for _ in range(24)] for _ in range(7)]
        for _, r in zg.iterrows():
            grid[int(r["dow"])][int(r["hour"])] = [
                int(r["n"]), round(float(r["avg"]), 2),
                int(r["big0"]), int(r["big1"]), int(r["big2"]),
            ]
        stats[str(int(zone))] = grid

    month = str(dt.iloc[0])[:7]
    out = {
        "meta": {
            "month": month,
            "thresholds": thresholds,
            "days_per_dow": days_per_dow,
            "total_trips": int(len(df)),
        },
        "stats": stats,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"写出 {len(stats)} 个区域 -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data/fhvhv_2026-05.parquet"))
