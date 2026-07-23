import pandas as pd
from pathlib import Path

d = Path("data/raw/firms")
frames = []
for fn in ["viirs_snpp.csv", "viirs_noaa20.csv", "modis.csv"]:
    p = d / fn
    if not p.exists():
        continue
    df = pd.read_csv(p)
    if df.empty:
        continue
    out = pd.DataFrame({
        "latitude": df["latitude"],
        "longitude": df["longitude"],
        "acq_date": df["acq_date"].astype(str),
        "acq_time": df["acq_time"].astype(int),
        "frp": df["frp"],
        "confidence": df["confidence"].astype(str),
        "satellite": df["satellite"].astype(str),
        "instrument": df["instrument"].astype(str),
    })
    frames.append(out)

m = pd.concat(frames, ignore_index=True)

hhmm = m["acq_time"].astype(int).astype(str).str.zfill(4)
m["timestamp"] = pd.to_datetime(
    m["acq_date"] + " " + hhmm.str[:2] + ":" + hhmm.str[2:],
    format="%Y-%m-%d %H:%M", utc=True,
)
m = m.sort_values("timestamp").reset_index(drop=True)

out_path = d / "yeongdeok_2025_detections.csv"
m.to_csv(out_path, index=False)
print(f"merged {len(m)} detections -> {out_path}")
print("date range:", m['timestamp'].min(), "to", m['timestamp'].max())
print("by instrument:", m.groupby('instrument').size().to_dict())
