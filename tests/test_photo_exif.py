"""PHASE 22 STEP 2 — a coordinate out of a reported photograph, and the limits.

Two things are under test and they are not the same thing:

1. **Does it read the coordinate**, from the three formats a 119 caller actually
   sends — and does every way of NOT reading one produce its own sentence rather
   than a shrug.
2. **Does it leave everything else alone.** That half is the reason the code
   lives in its own package, and the tests for it are deliberately blunt: the
   tag list is pinned by value, the returned payload is checked for fields that
   must never appear, and the module source is checked for the calls that would
   write a file.

⚠ The fixtures are BUILT HERE, from Pillow, so no photograph of anyone's is in
this repository. The one exception is the HEIC container, which Pillow in this
environment cannot write (``features.check('heif')`` is False, measured) — see
:data:`HEIC_B64` for exactly where it came from.
"""

from __future__ import annotations

import base64
import io
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.photo import (  # noqa: E402
    GPS_ONLY_TAGS, MAX_BYTES, OUTCOMES, PRIVACY_KO, GpsReading, read_gps,
    sniff_container,
)
from wildfireguardian.photo import exif_gps as _mod  # noqa: E402
from wildfireguardian.service.params import check_in_region  # noqa: E402

#: A coordinate inside `yeongdeok_2025`'s registered walk bbox
#: (129.25~129.55 E, 36.30~36.60 N), so the gate accepts it.
IN_BBOX = (36, 27, 58.6, 129, 23, 58.6)
#: Well outside it. Not a wildfire report; the point is the REFUSAL.
OUT_OF_BBOX = (37, 30, 0.0, 127, 0, 0.0)

#: An 8x8 HEIC carrying the IN_BBOX coordinate, base64.
#:
#: ⚠ PROVENANCE, because a fixture nobody can reproduce is a fixture nobody can
#: trust. It was produced on macOS by Apple's own ImageIO:
#:
#:     python  -> gps.jpg          (Pillow, the same EXIF the JPEG test builds)
#:     sips -s format heic gps.jpg --out gps.heic
#:
#: So the HEIF path is verified against a container an Apple encoder wrote, not
#: only against one this repository synthesised — which is the whole risk with a
#: hand-written ISO-BMFF reader. It is an 8x8 solid colour: no photograph, no
#: person, no place.
HEIC_B64 = (
    "AAAAJGZ0eXBoZWljAAAAAG1pZjFNaVBybWlhZk1pSEJoZWljAAABw21ldGEAAAAAAAAAIWhk"
    "bHIAAAAAAAAAAHBpY3QAAAAAAAAAAAAAAAAAAAAAJGRpbmYAAAAcZHJlZgAAAAAAAAABAAAA"
    "DHVybCAAAAABAAAADnBpdG0AAAAAAAEAAAA4aWluZgAAAAAAAgAAABVpbmZlAgAAAAABAABo"
    "dmMxAAAAABVpbmZlAgAAAQACAABFeGlmAAAAABppcmVmAAAAAAAAAA5jZHNjAAIAAQABAAAA"
    "5mlwcnAAAADFaXBjbwAAABNjb2xybmNseAACAAIABoAAAAAMY2xsaQDLAEAAAAAUaXNwZQAA"
    "AAAAAAAIAAAACAAAAAlpcm90AAAAABBwaXhpAAAAAAMICAgAAABxaHZjQwEDcAAAALAAAAAA"
    "AB7wAPz9+PgAAAsDoAABABdAAQwB//8DcAAAAwCwAAADAAADAB5wJKEAAQAjQgEBA3AAAAMA"
    "sAAAAwAAAwAeoBQgQcCbDuIe5FlU3AgIGAKiAAEACUQBwGFyyERTZAAAABlpcG1hAAAAAAAA"
    "AAEAAQaBAgMFhoQAAAAsaWxvYwAAAABEAAACAAEAAAABAAACgQAAAD0AAgAAAAEAAAH3AAAA"
    "igAAAAFtZGF0AAAAAAAAANcAAAAGRXhpZgAATU0AKgAAAAgAAYglAAQAAAABAAAAGgAAAAAA"
    "BAABAAIAAAACTgAAAAACAAUAAAADAAAAUAADAAIAAAACRQAAAAAEAAUAAAADAAAAaAAAAAAA"
    "AAAkAAAAAQAAABsAAAABAAAW5AAAAGQAAACBAAAAAQAAABcAAAABAAAW5AAAAGQAAAA5KAGv"
    "ovZGgXz//mf1//kL7L3fN9V//HsfI7Lov8BU90yyZ/og+cI55vxEK1O/mHgi9hX4K3CEmyK4"
)


def _dms(d: int, m: int, s: float) -> tuple:
    return (Fraction(d, 1), Fraction(m, 1), Fraction(int(round(s * 100)), 100))


def _gps_block(coords) -> dict:
    lat_d, lat_m, lat_s, lon_d, lon_m, lon_s = coords
    return {1: "N", 2: _dms(lat_d, lat_m, lat_s),
            3: "E", 4: _dms(lon_d, lon_m, lon_s)}


def make_photo(fmt: str = "JPEG", gps: dict | None = None,
               device: bool = False) -> bytes:
    """A tiny image with exactly the EXIF the test wants.

    ``device`` writes Make and Model. Every test that uses it is asserting they
    do NOT come back out.
    """
    from PIL import Image
    im = Image.new("RGB", (8, 8), (120, 30, 30))
    exif = Image.Exif()
    if device:
        exif[0x010F] = "ACME Phone Co"
        exif[0x0110] = "Model X Pro"
    if gps:
        exif[0x8825] = gps
    buf = io.BytesIO()
    im.save(buf, fmt, exif=exif.tobytes())
    return buf.getvalue()


@pytest.fixture(scope="module")
def heic() -> bytes:
    return base64.b64decode(HEIC_B64)


# ---------------------------------------------------------------------------
# 1. It reads the coordinate, from the formats that actually arrive
# ---------------------------------------------------------------------------


def test_the_three_formats_a_reporter_sends_all_give_the_same_coordinate(heic):
    """JPEG, PNG and HEIC. HEIC is the iPhone default, so it is not optional."""
    jpeg = read_gps(make_photo("JPEG", _gps_block(IN_BBOX)))
    png = read_gps(make_photo("PNG", _gps_block(IN_BBOX)))
    hei = read_gps(heic)
    for r, name in ((jpeg, "JPEG"), (png, "PNG"), (hei, "HEIF")):
        assert r.ok, f"{name}: {r.outcome}"
        assert r.container == name
        assert r.lat == pytest.approx(36.46628, abs=1e-4), name
        assert r.lon == pytest.approx(129.39961, abs=1e-4), name


def test_the_container_is_sniffed_from_bytes_never_from_a_name(heic):
    assert sniff_container(make_photo("JPEG")) == "JPEG"
    assert sniff_container(make_photo("PNG")) == "PNG"
    assert sniff_container(heic) == "HEIF"
    assert sniff_container(b"GIF89a whatever") == "unknown"


def test_the_heif_reader_never_needs_a_decoder(heic):
    """The point of parsing the container by hand: no HEVC decoder is involved.

    If Pillow could decode HEIF this test would still pass; what it pins is that
    the reader does not DEPEND on it, which is why `pillow-heif` is not a
    dependency.
    """
    from PIL import features
    assert features.check("heif") is False, (
        "Pillow has gained HEIF support — the hand-written reader is now "
        "optional, which is a decision to take deliberately, not silently")
    assert read_gps(heic).ok


# ---------------------------------------------------------------------------
# 2. Every way of NOT getting a coordinate has its own sentence
# ---------------------------------------------------------------------------


def test_no_exif_at_all_says_so_and_names_the_common_cause():
    r = read_gps(make_photo("JPEG"))
    assert r.outcome == "no_exif"
    assert "위치 정보가 없습니다" in r.reason_ko
    # The brief's third case: this is the usual reason, and it is worth saying
    # because the fix (ask for the original) is different from every other case.
    assert "메신저" in r.reason_ko


def test_exif_without_gps_points_at_location_services_not_at_a_messenger():
    r = read_gps(make_photo("JPEG", device=True))
    assert r.outcome == "no_gps"
    assert "위치 서비스" in r.reason_ko


def test_a_camera_that_never_got_a_fix_writes_zero_and_is_refused_for_that():
    """0,0 is a real place in the Gulf of Guinea. It is never a Korean report.

    Refused HERE with its own sentence, rather than passed to the region gate to
    be refused there for the wrong reason.
    """
    r = read_gps(make_photo("JPEG", _gps_block((0, 0, 0.0, 0, 0, 0.0))))
    assert r.outcome == "gps_zero"
    assert "측위가 되지 않은" in r.reason_ko


def test_a_missing_hemisphere_reference_is_not_guessed():
    """Without N/S the sign is unknown, and Korea is not a good enough excuse."""
    block = _gps_block(IN_BBOX)
    del block[1], block[3]
    r = read_gps(make_photo("JPEG", block))
    assert r.outcome == "gps_incomplete"


@pytest.mark.parametrize("data,expected", [
    (b"", "empty"),
    (b"this is not an image", "unsupported_format"),
    (b"GIF89a\x00\x00\x00\x00\x00\x00", "unsupported_format"),
])
def test_input_that_is_not_a_photograph(data, expected):
    assert read_gps(data).outcome == expected


def test_a_truncated_file_says_broken_not_no_location(heic):
    """⚠ The distinction that matters operationally.

    「위치 정보가 없습니다」 sends the operator to the map. 「파일이 손상되었습니다」
    tells them to ask for the photograph again. A truncated upload answering the
    first would be a quiet failure wearing an honest sentence.
    """
    assert read_gps(make_photo("JPEG", _gps_block(IN_BBOX))[:200]).outcome == "malformed"
    assert read_gps(heic[:120]).outcome == "malformed"
    assert read_gps(heic[:487]).outcome == "malformed"


def test_an_oversized_upload_is_refused_before_it_is_parsed():
    assert read_gps(b"\xff\xd8\xff" + b"0" * MAX_BYTES).outcome == "too_large"


def test_every_outcome_has_a_sentence_and_none_is_silent():
    seen = set()
    for key, text in OUTCOMES.items():
        assert text.strip(), f"{key} has no sentence"
        seen.add(key)
    # Everything the code can actually return must be in the table.
    produced = {
        read_gps(b"").outcome,
        read_gps(b"nope").outcome,
        read_gps(make_photo("JPEG")).outcome,
        read_gps(make_photo("JPEG", device=True)).outcome,
        read_gps(make_photo("JPEG", _gps_block(IN_BBOX))).outcome,
        read_gps(make_photo("JPEG", _gps_block((0, 0, 0.0, 0, 0, 0.0)))).outcome,
    }
    assert produced <= seen, f"an outcome has no sentence: {produced - seen}"


# ---------------------------------------------------------------------------
# 3. Privacy. The blunt half.
# ---------------------------------------------------------------------------


def test_the_tag_list_is_exactly_four_and_pinned_by_value():
    """⚠ If this test needs changing, the change is the thing to review.

    1/3 are the N/S and E/W references, 2/4 the values. Nothing else is read:
    not the maker, the model, the timestamp, the owner, the serial number or
    the thumbnail.
    """
    assert GPS_ONLY_TAGS == frozenset({1, 2, 3, 4})


def test_the_device_that_took_the_photograph_never_comes_back_out():
    data = make_photo("JPEG", _gps_block(IN_BBOX), device=True)
    r = read_gps(data)
    assert r.ok
    blob = json.dumps(r.as_dict(), ensure_ascii=False)
    assert "ACME" not in blob, "the camera maker leaked into the payload"
    assert "Model X" not in blob, "the camera model leaked into the payload"


def test_the_reading_has_no_field_for_anything_but_a_coordinate():
    """A dataclass with nowhere to put the rest is the structural guarantee."""
    fields = set(GpsReading.__dataclass_fields__)
    assert fields == {"outcome", "lat", "lon", "container"}, fields


def test_the_payload_keys_are_enumerated_and_carry_no_surprise():
    keys = set(read_gps(make_photo("JPEG", _gps_block(IN_BBOX), device=True))
               .as_dict())
    assert keys == {"source", "outcome", "ok", "container", "lat", "lon",
                    "photo_reason_ko", "privacy_ko"}, keys


def test_the_module_contains_nothing_that_writes_a_file():
    """Static, and blunt on purpose: the package is one file for this reason.

    A reviewer should be able to see that the photograph cannot be persisted
    without reading the whole call graph.
    """
    src = (REPO / "src" / "wildfireguardian" / "photo" / "exif_gps.py").read_text(
        encoding="utf-8")
    code = re.sub(r'"""(?:.|\n)*?"""', "", src)       # drop docstrings
    code = re.sub(r"#.*$", "", code, flags=re.M)      # drop comments
    for forbidden in ("tempfile", "NamedTemporary", "mkstemp", "shutil",
                      ".write(", ".write_bytes(", ".write_text(", "os.rename",
                      "logging", "logger", "print("):
        assert forbidden not in code, (
            f"{forbidden!r} appears in the photo module: the photograph must "
            "not be written or logged anywhere")


def test_reading_a_photograph_creates_no_file(tmp_path, monkeypatch, heic):
    monkeypatch.chdir(tmp_path)
    for data in (make_photo("JPEG", _gps_block(IN_BBOX)),
                 make_photo("PNG", _gps_block(IN_BBOX)), heic,
                 b"broken", make_photo("JPEG")):
        read_gps(data)
    assert list(tmp_path.iterdir()) == [], "a file appeared while reading photos"


def test_the_processing_statement_says_the_three_things_it_must():
    assert "저장하지 않습니다" in PRIVACY_KO          # not stored
    assert "폐기" in PRIVACY_KO                      # discarded
    assert "파일명" in PRIVACY_KO                    # and the filename never travels


def test_no_operator_sentence_carries_a_dash_the_shipped_font_cannot_draw():
    """⚠ These strings are on screen but INVISIBLE to the screen gate.

    `check_screen_assets` reads the built HTML. Wording that arrives in an API
    response is never in that file, so the EM/EN dash rule has to be enforced
    where the wording lives. The vendored subset has no glyph for either.
    """
    for key, text in list(OUTCOMES.items()) + [("PRIVACY_KO", PRIVACY_KO)]:
        assert "—" not in text, f"{key} has an EM dash"
        assert "–" not in text, f"{key} has an EN dash"


# ---------------------------------------------------------------------------
# 4. The transport, and the ONE gate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from wildfireguardian.api.app import create_app
    from wildfireguardian.service import build_runner
    app = create_app(runner=build_runner(regions=["yeongdeok_2025"], capacity=1,
                                         max_workers=1))
    with TestClient(app) as c:
        yield c


def _post(client, data: bytes, region: str = "yeongdeok_2025"):
    return client.post(f"/api/regions/{region}/photo-gps", content=data,
                       headers={"Content-Type": "application/octet-stream"})


def test_a_photograph_inside_the_bbox_is_accepted_and_projected(client):
    r = _post(client, make_photo("JPEG", _gps_block(IN_BBOX)))
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["inside_registered_region"] is True
    # The console draws the crosshair from these; the page does no geodesy.
    assert isinstance(d["x_5179"], float) and isinstance(d["y_5179"], float)


def test_a_photograph_outside_the_bbox_gets_the_MAP_CLICK_refusal_verbatim(client):
    """⚠ ONE GATE, ONE SENTENCE, however the coordinate arrived.

    This is the requirement stated when the phase was set: EXIF coordinates go
    through `check_in_region`, not through a second rule of their own, and a
    refusal reads the same as a map click's.
    """
    lat, lon = 37.5, 127.0
    d = _post(client, make_photo("JPEG", _gps_block(OUT_OF_BBOX))).json()
    assert d["ok"] is True                     # the PHOTO was read fine
    assert d["inside_registered_region"] is False   # the COORDINATE is refused
    assert d["reason_ko"] == check_in_region("yeongdeok_2025", lat, lon)["reason_ko"]


def test_a_photograph_with_no_location_is_200_with_a_verdict_not_a_4xx(client):
    """The caller asked a question and got an answer. 4xx is for a bad request."""
    for data, outcome in ((make_photo("JPEG"), "no_exif"),
                          (make_photo("JPEG", device=True), "no_gps"),
                          (b"not an image", "unsupported_format")):
        r = _post(client, data)
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == outcome
        assert body["ok"] is False
        assert body["photo_reason_ko"].strip()
        assert "reason_ko" not in body, (
            "no coordinate exists, so there is no gate verdict to report")


def test_the_two_sentences_do_not_overwrite_each_other(client):
    """Found by writing it the other way round first: `payload.update(gate)`
    replaced the photo's own sentence with the gate's, and the screen lost the
    only explanation of why a photograph produced nothing."""
    d = _post(client, make_photo("JPEG", _gps_block(OUT_OF_BBOX))).json()
    assert d["photo_reason_ko"] != d["reason_ko"]
    assert "EXIF" in d["photo_reason_ko"]
    assert "bbox" in d["reason_ko"]


def test_an_unregistered_region_is_404(client):
    assert _post(client, make_photo("JPEG"), region="atlantis_2025").status_code == 404


def test_an_oversized_body_is_413_and_is_refused_on_the_header(client):
    r = _post(client, b"\xff\xd8\xff" + b"0" * MAX_BYTES)
    assert r.status_code == 413


def test_the_response_carries_the_processing_statement(client):
    assert _post(client, make_photo("JPEG")).json()["privacy_ko"] == PRIVACY_KO


# ---------------------------------------------------------------------------
# 5. The screen says the same thing the module does
# ---------------------------------------------------------------------------

CONSOLE = REPO / "web" / "console.html"


@pytest.mark.skipif(not CONSOLE.exists(), reason="run scripts/build_console.py")
def test_the_console_prints_the_processing_statement_byte_for_byte():
    """One copy. A promise about personal data that exists twice can drift."""
    assert PRIVACY_KO in CONSOLE.read_text(encoding="utf-8"), (
        "the console's photo privacy line has drifted from "
        "wildfireguardian.photo.PRIVACY_KO")


@pytest.mark.skipif(not CONSOLE.exists(), reason="run scripts/build_console.py")
def test_the_console_never_reads_the_photograph_itself():
    """⚠ The bytes go straight to fetch and are never held by the page.

    No FileReader, no data URI, no canvas — and no FormData, which is what keeps
    the FILENAME in the browser. If any of these appear, the privacy claim
    printed on the screen has stopped being true.
    """
    src = CONSOLE.read_text(encoding="utf-8")
    # Comments out first — the console EXPLAINS that it uses none of these, and
    # the first version of this test failed on its own explanation.
    code = re.sub(r"/\*(?:.|\n)*?\*/", "", src)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
    for banned in ("FileReader", "readAsDataURL", "readAsArrayBuffer",
                   "FormData", "toDataURL", "getImageData"):
        assert banned not in code, (
            f"{banned} in the console: the page is now handling the "
            "photograph's contents itself")
