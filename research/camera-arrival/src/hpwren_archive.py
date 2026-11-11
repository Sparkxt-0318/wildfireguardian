"""HPWREN archive addressing + existence checks (throttled, disk-cached).
Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego.

URL templates (from the cameras page JS, https://www.hpwren.ucsd.edu/cameras/):
  list : https://cdn.hpwren.ucsd.edu/hpwren-cameras/<cam>/<YYYY>/<YYYYMMDD>/<YYYYMMDD>_<cam>_Q<q>.txt
  image: https://cdn.hpwren.ucsd.edu/MTA/<cam>/large/<YYYYMMDD>/Q<q>/<epoch>.jpg
  video: https://cdn.hpwren.ucsd.edu/hpwren-cameras/<cam>/<YYYY>/<YYYYMMDD>/Q<q>.mp4
q = 1..8 = 3-hour blocks 00-03 ... 21-24 in *Pacific local time*; date in the path is the Pacific date.
<epoch> = Unix epoch seconds UTC (list entries are '<epoch>.jpg', ~1/min).
Only HEAD requests (or the list GET, ~2.7 kB) are used: no image or video bytes are downloaded here.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hpwren_common import fetch

CDN = "https://cdn.hpwren.ucsd.edu/hpwren-cameras/"
MTA = "https://cdn.hpwren.ucsd.edu/MTA/"


def _d(date):
    s = str(date).replace("-", "")
    assert len(s) == 8 and s.isdigit(), date
    return s


def list_url(cam, date, q):
    d = _d(date)
    return f"{CDN}{cam}/{d[:4]}/{d}/{d}_{cam}_Q{q}.txt"


def image_url(cam, date, q, epoch):
    return f"{MTA}{cam}/large/{_d(date)}/Q{q}/{epoch}.jpg"


def video_url(cam, date, q):
    d = _d(date)
    return f"{CDN}{cam}/{d[:4]}/{d}/Q{q}.mp4"


def get_list(cam, date, q):
    """Return (status, [epochs]) for the image list of one 3h block."""
    r = fetch(list_url(cam, date, q))
    if r["status"] != 200:
        return r["status"], []
    eps = [int(l[:10]) for l in r["body"].decode().split() if l[:10].isdigit()]
    return 200, eps


def archive_exists(camera, date, quarters=(4,)):
    """Which of list / images / video exist for camera on date (Pacific date).
    For each requested quarter: list = GET 200; images = HEAD 200 on the first
    listed image (None if there is no list); video = HEAD 200 (also reports the
    S3 storage class: DEEP_ARCHIVE means the object exists but is not readable
    without a restore request to HPWREN). Returns a dict per quarter."""
    out = {}
    for q in quarters:
        ls, eps = get_list(camera, date, q)
        res = {"list_status": ls, "list": ls == 200, "n_listed": len(eps)}
        if eps:
            h = fetch(image_url(camera, date, q, eps[0]), method="HEAD")
            res.update(image_status=h["status"], images=h["status"] == 200, image_url=image_url(camera, date, q, eps[0]))
        else:
            res.update(image_status=None, images=None)
        v = fetch(video_url(camera, date, q), method="HEAD")
        res.update(video_status=v["status"], video=v["status"] == 200,
                   video_storage_class=v["headers"].get("x-amz-storage-class", "STANDARD" if v["status"] == 200 else None),
                   video_bytes=v["headers"].get("Content-Length"))
        out[q] = res
    return out


if __name__ == "__main__":
    cam, date = sys.argv[1], sys.argv[2]
    print(archive_exists(cam, date, tuple(int(x) for x in sys.argv[3:]) or (4,)))
