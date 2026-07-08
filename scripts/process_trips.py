"""处理 TLC 高频网约车 (HVFHV) 行程数据。

按 接单区域 × 星期几 × 小时 聚合，输出前端所需的紧凑 JSON：
  - n:   订单数
  - avg: 平均司机收入 (driver_pay + tips)
  - big: 「大单」数（司机收入 >= 全市前10%阈值）

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

    # 大单阈值 = 全市司机单笔收入的前 10%（P90）
    threshold = round(float(df["earn"].quantile(0.90)), 2)
    print(f"大单阈值 (P90): ${threshold}")

    dt = df["pickup_datetime"]
    df["dow"] = dt.dt.dayofweek.astype("int8")   # 0=周一
    df["hour"] = dt.dt.hour.astype("int8")
    df["big"] = (df["earn"] >= threshold)

    # 当月每个星期几出现的天数（用于换算「每小时大单数」）
    days_per_dow = (
        dt.dt.normalize().drop_duplicates().dt.dayofweek.value_counts()
        .reindex(range(7), fill_value=0).tolist()
    )

    g = df.groupby(["PULocationID", "dow", "hour"]).agg(
        n=("earn", "size"), avg=("earn", "mean"), big=("big", "sum")
    ).reset_index()

    stats = {}
    for zone, zg in g.groupby("PULocationID"):
        grid = [[[0, 0, 0]] * 24 for _ in range(7)]
        grid = [[list(c) for c in row] for row in grid]
        for _, r in zg.iterrows():
            grid[int(r["dow"])][int(r["hour"])] = [
                int(r["n"]), round(float(r["avg"]), 2), int(r["big"])
            ]
        stats[str(int(zone))] = grid

    month = str(dt.iloc[0])[:7]
    out = {
        "meta": {
            "month": month,
            "threshold": threshold,
            "days_per_dow": days_per_dow,
            "total_trips": int(len(df)),
        },
        "stats": stats,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"写出 {len(stats)} 个区域 -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data/fhvhv_2026-05.parquet"))
