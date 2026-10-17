"""Fetch single members of a large zip archive with HTTP range reads (USFS Research Data Archive).

The approved USFS archives C7 (RDS-2022-0071, tree-burn firebrand videos) and C8 (RDS-2021-0069,
FBAT in-fire videos) are multi-gigabyte zips on Box. Only a few videos are needed, so this reads
the zip's end-of-central-directory record and central directory with range requests, then fetches
just the local header and compressed bytes of each chosen member. Nothing else is downloaded.

    python scripts/fetch_rds_members.py list URL [--json OUT]
    python scripts/fetch_rds_members.py get URL MEMBER --out data/raw/C8_rim_plot1_c1.avi [--max-bytes N]

`get` checks the member's CRC-32 when it is fetched whole. `--max-bytes N` keeps only the first N
bytes of the member (a prefix of a long video, for example the minutes before the fire front
arrives); its CRC cannot be checked and the result records that. Stored and deflated members are
supported. The archive URL is the Box link from the archive's catalog page; it redirects to a
signed download URL on every request, so each range request starts from it again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_clips import UA, ssl_context  # noqa: E402

EOCD_SIG = b"PK\x05\x06"
EOCD64_LOC_SIG = b"PK\x06\x07"
EOCD64_SIG = b"PK\x06\x06"
CDIR_SIG = b"PK\x01\x02"
LOCAL_SIG = b"PK\x03\x04"
CHUNK = 8 * 1024 * 1024


def _range(url: str, start: int, end: int, tries: int = 4) -> bytes:
    """Bytes start..end inclusive. Raises when the server ignores the range."""
    for k in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": f"bytes={start}-{end}"})
        try:
            with urllib.request.urlopen(req, timeout=120, context=ssl_context()) as r:
                if r.status != 206:
                    raise RuntimeError(f"range request answered {r.status}, not 206 (no range support)")
                data = r.read()
            if len(data) != end - start + 1:
                raise RuntimeError(f"short range read: {len(data)} of {end - start + 1} bytes")
            return data
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if k == tries - 1:
                raise
            time.sleep(2 ** (k + 1))
            print(f"  retry {k + 1} after {exc}", file=sys.stderr)
    raise RuntimeError("unreachable")


def _size(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=120, context=ssl_context()) as r:
        cr = r.headers.get("Content-Range", "")
    if "/" not in cr:
        raise RuntimeError(f"no Content-Range in the answer ({cr!r}); the host does not serve ranges")
    return int(cr.rsplit("/", 1)[1])


def list_members(url: str) -> dict:
    """The archive size and every member: name, sizes, method, crc, local header offset."""
    size = _size(url)
    tail_len = min(size, 66000)
    tail = _range(url, size - tail_len, size - 1)
    i = tail.rfind(EOCD_SIG)
    if i < 0:
        raise RuntimeError("end of central directory not found")
    (_, _, _, _, n_total, cd_size, cd_off, _) = struct.unpack("<4sHHHHIIH", tail[i:i + 22])
    j = tail.rfind(EOCD64_LOC_SIG, 0, i)
    if j >= 0:                                  # zip64: the real values are in the zip64 record
        (_, _, eocd64_off, _) = struct.unpack("<4sIQI", tail[j:j + 20])
        rec = _range(url, eocd64_off, eocd64_off + 55)
        if rec[:4] != EOCD64_SIG:
            raise RuntimeError("zip64 end record not found")
        (n_total, cd_size, cd_off) = struct.unpack("<QQQ", rec[32:56])
    cd = _range(url, cd_off, cd_off + cd_size - 1)
    members, p = [], 0
    while p < len(cd) and cd[p:p + 4] == CDIR_SIG:
        (method, _t, _d, crc, csize, usize, n_len, x_len, c_len) = struct.unpack("<HHHIIIHHH", cd[p + 10:p + 34])
        (local_off,) = struct.unpack("<I", cd[p + 42:p + 46])
        name = cd[p + 46:p + 46 + n_len].decode("utf-8", "replace")
        extra = cd[p + 46 + n_len:p + 46 + n_len + x_len]
        q = 0
        while q + 4 <= len(extra):              # zip64 extra field: sizes and offset that overflow 32 bits
            (hid, hlen) = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals = extra[q + 4:q + 4 + hlen]
                k = 0
                if usize == 0xFFFFFFFF:
                    usize = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                if csize == 0xFFFFFFFF:
                    csize = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                if local_off == 0xFFFFFFFF:
                    local_off = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
            q += 4 + hlen
        members.append({"name": name, "method": method, "crc32": f"{crc:08x}", "compressed": csize,
                        "size": usize, "local_offset": local_off})
        p += 46 + n_len + x_len + c_len
    return {"url": url, "archive_bytes": size, "members_declared": n_total, "members": members}


def get_member(url: str, member: dict, out: Path, max_bytes: int | None = None) -> dict:
    """Write one member (or its first max_bytes) to out; return its provenance record."""
    off = member["local_offset"]
    hdr = _range(url, off, off + 29)
    if hdr[:4] != LOCAL_SIG:
        raise RuntimeError(f"no local header at {off}")
    (n_len, x_len) = struct.unpack("<HH", hdr[26:30])
    start = off + 30 + n_len + x_len
    method = member["method"]
    if method not in (0, 8):
        raise RuntimeError(f"compression method {method} is not supported")
    want = member["size"] if max_bytes is None else min(max_bytes, member["size"])
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    sha, crc, written = hashlib.sha256(), 0, 0
    dec = zlib.decompressobj(-15) if method == 8 else None
    pos, end = start, start + member["compressed"] - 1
    with open(tmp, "wb") as f:
        while pos <= end and written < want:
            chunk = _range(url, pos, min(end, pos + CHUNK - 1))
            pos += len(chunk)
            data = dec.decompress(chunk) if dec else chunk
            data = data[:want - written]
            f.write(data)
            sha.update(data)
            crc = zlib.crc32(data, crc)
            written += len(data)
            print(f"  {written / 1e6:8.1f} of {want / 1e6:.1f} MB", file=sys.stderr, end="\r")
    print(file=sys.stderr)
    whole = written == member["size"]
    if whole and f"{crc & 0xFFFFFFFF:08x}" != member["crc32"]:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"CRC mismatch for {member['name']}")
    tmp.replace(out)
    return {"archive_url": url, "member": member["name"], "member_bytes": member["size"],
            "member_crc32": member["crc32"], "bytes_written": written, "whole_member": whole,
            "crc_checked": whole, "file": str(out), "sha256": sha.hexdigest(),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list", help="list the archive's members")
    lp.add_argument("url")
    lp.add_argument("--json", help="write the listing here")
    gp = sub.add_parser("get", help="fetch one member")
    gp.add_argument("url")
    gp.add_argument("member", help="exact member name, as listed")
    gp.add_argument("--out", required=True)
    gp.add_argument("--max-bytes", type=int, help="keep only this many leading bytes of the member")
    gp.add_argument("--receipt", help="append the provenance record (JSON lines) here")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        info = list_members(a.url)
        if a.json:
            Path(a.json).parent.mkdir(parents=True, exist_ok=True)
            Path(a.json).write_text(json.dumps(info, indent=1))
        for m in info["members"]:
            print(f"{m['compressed']:>12} {m['size']:>12} m{m['method']} {m['name']}")
        print(f"{len(info['members'])} members, archive {info['archive_bytes']} bytes")
        return 0
    info = list_members(a.url)
    match = [m for m in info["members"] if m["name"] == a.member]
    if not match:
        print(f"no member named {a.member!r}", file=sys.stderr)
        return 1
    rec = get_member(a.url, match[0], Path(a.out), a.max_bytes)
    print(json.dumps(rec, indent=1))
    if a.receipt:
        with open(a.receipt, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
