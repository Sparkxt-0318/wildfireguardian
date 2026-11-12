"""Politely probe how far back the HPWREN archive is reachable from this network.
Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego. Sequential, throttled, cached."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hpwren_archive import archive_exists
from hpwren_common import ROOT

Q = 5  # 12-15 PT
PROBES = [
 ("2019-10-10","wilson-s-mobo-c","Saddleridge"), ("2019-10-10","69bravo-e-mobo-c","Saddleridge"),
 ("2019-10-24","wilson-s-mobo-c","Tick"), ("2019-10-24","69bravo-e-mobo-c","Tick"),
 ("2020-08-01","rdmrc-n-mobo-c","Apple"), ("2020-08-01","marion-w-mobo-c","Apple"),
 ("2020-08-13","wilson-s-mobo-c","Lake"),
 ("2020-09-06","lp-e-mobo-c","Valley"), ("2020-09-06","sm-e-mobo-c","Valley"), ("2020-09-06","wilson-s-mobo-c","Bobcat/El Dorado"),
 ("2020-09-06","rdmrc-n-mobo-c","El Dorado"),
 ("2020-12-03","stgo-e-mobo-c","Bond"), ("2020-12-03","chino-e-mobo-c","Bond"),
 ("2021-08-15","cp-e-mobo-c","2021 control"), ("2021-08-15","stgo-e-mobo-c","2021 control"),
 ("2022-07-01","cp-e-mobo-c","intermediate"), ("2022-07-01","stgo-e-mobo-c","intermediate"),
 ("2023-07-01","cp-e-mobo-c","intermediate"), ("2023-07-01","stgo-e-mobo-c","intermediate"),
 ("2024-07-03","cp-e-mobo-c","intermediate"), ("2025-07-01","cp-e-mobo-c","intermediate"),
 ("2026-07-01","cp-e-mobo-c","intermediate"),
 ("2026-08-10","cp-e-mobo-c","90-day edge (97 d ago)"), ("2026-08-16","cp-e-mobo-c","90-day edge (87 d ago)"),
]
rows = []
for date, cam, why in PROBES:
    r = archive_exists(cam, date, (Q,))[Q]
    r.update(date=date, cam=cam, note=why, q=Q)
    rows.append(r)
    print(date, cam, r["list_status"], r["n_listed"], r["image_status"], r["video_status"], r["video_storage_class"], flush=True)
(ROOT / "outputs" / "hpwren_archive_probe.json").write_text(json.dumps(rows, indent=1))
