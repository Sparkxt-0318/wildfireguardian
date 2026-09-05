"""GK2A AMI Level-1B reader — DN to brightness temperature, and geolocation.

Session 19. GK-2A's Advanced Meteorological Imager scans the Korean Peninsula
(``LA``) every 2 minutes at 2 km in the infrared. The archive is the NOAA GK2A
PDS on AWS Open Data (``s3://noaa-gk2a-pds``), distributed by NOAA in
coordination with KMA, and it is readable **without credentials** — verified in
Phase 0 by an anonymous HTTPS GET.

EVERY CONSTANT USED HERE COMES OUT OF THE FILE. Nothing is looked up, recalled
or assumed: the radiance gain/offset, the Planck constants, the
effective-temperature correction and the full GEOS navigation are all global
attributes of each granule. That matters because a fabricated calibration
constant would silently move every brightness temperature this session reports.

    DN  --(gain, offset)-->  radiance
    radiance --(inverse Planck at the channel wavelength)--> T_eff
    T_eff --(c0 + c1·T + c2·T²)--> T_bb

⚠ ONE THING IS INFERRED, NOT READ: the radiance UNIT. The file gives gain and
offset but never states the unit of their product, and the choice changes every
temperature by tens of kelvin. It was settled EMPIRICALLY, and the working is
recorded here because the alternative is an unfalsifiable constant:

  * read as per-wavelength W·m⁻²·sr⁻¹·μm⁻¹ the 8.7 μm scene came out
    **311.8–466.2 K** — impossible for an Earth scene;
  * read as per-wavenumber **mW·m⁻²·sr⁻¹·(cm⁻¹)⁻¹**, inverted with the
    wavenumber form of Planck, the same scene is **225.8 / 278.9 / 298.1 K**
    (min / median / max) — cold cloud top, cool March land, warm surface.

The second is therefore the unit, and :func:`brightness_temperature` refuses any
result outside 150–400 K so a wrong conversion fails loudly rather than shifting
every number quietly. The first attempt tripped that check, which is why the
check exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: ⚠ THE VALID-BIT COUNT IS PER CHANNEL AND MUST BE READ FROM THE FILE.
#: An early version hard-coded 13 bits, which is right for ir087 and ir112 and
#: WRONG for sw038, which uses 14. Masking sw038 to 13 bits silently produced a
#: whole-scene brightness temperature of 376 K — every pixel hotter than any
#: real fire, and still inside the 150–400 K sanity window, so the range check
#: did not catch it. The scene-MEDIAN check below is what catches it.
DEFAULT_VALID_BITS = 13

#: Physically possible brightness temperature for any single Earth pixel. A fire
#: pixel at 3.8 μm can genuinely exceed 350 K, so this is deliberately loose.
BT_SANITY_K = (150.0, 400.0)

#: The scene MEDIAN is a much tighter constraint than any single pixel: half a
#: 500x500 Korean scene is never hotter than 330 K nor colder than 180 K. This
#: is the check that catches a wrong bit mask or a wrong radiance unit, because
#: both shift the whole distribution rather than a few pixels.
BT_MEDIAN_SANITY_K = (180.0, 330.0)

#: Channel used for the mid-infrared fire signal (3.83 μm) and the window
#: channel it is differenced against (11.2 μm). See ``scripts/gk2a_detection.py``
#: for why these two and not others.
MIR_CHANNEL = "sw038"
TIR_CHANNEL = "ir112"


@dataclass(frozen=True)
class Granule:
    """One channel, one timestep, already converted."""

    bt: np.ndarray                 # brightness temperature, K
    quality: np.ndarray            # 0 good, 1 conditional, 2 out-of-scan, 3 error
    channel: str
    wavelength_um: float
    acquisition_time: str          # scene_acquisition_time, UTC, from the file
    attrs: dict


def _f(attrs: dict, key: str) -> float:
    """Attributes arrive as str, numpy scalar or 1-element array. Normalise."""
    v = attrs[key]
    if isinstance(v, (str, bytes)):
        return float(v)
    arr = np.asarray(v)
    return float(arr.reshape(-1)[0]) if arr.size else float("nan")


def brightness_temperature(dn: np.ndarray, attrs: dict,
                           valid_bits: int = DEFAULT_VALID_BITS) -> np.ndarray:
    """Convert raw counts to brightness temperature in kelvin.

    ``valid_bits`` must come from the granule's own
    ``number_of_valid_bits_per_pixel``; :func:`read_granule` passes it.
    """
    mask = (1 << int(valid_bits)) - 1
    valid = (np.asarray(dn).astype("uint16") & mask).astype("float64")
    rad = _f(attrs, "DN_to_Radiance_Gain") * valid + _f(attrs, "DN_to_Radiance_Offset")

    lam_um = _f(attrs, "channel_center_wavelength")
    h = _f(attrs, "Plank_constant_h")                            # sic, as in file
    c = _f(attrs, "light_speed")
    k = _f(attrs, "Boltzmann_constant_k")

    nu = 1.0 / (lam_um * 1e-6)                   # wavenumber, m^-1
    with np.errstate(divide="ignore", invalid="ignore"):
        # mW·m⁻²·sr⁻¹·(cm⁻¹)⁻¹ -> W·m⁻²·sr⁻¹·(m⁻¹)⁻¹ : ×1e-3 for mW, ÷100
        # because one cm⁻¹ spans a hundred m⁻¹.
        spectral = rad * 1e-3 / 100.0
        teff = (h * c * nu / k) / np.log(2 * h * c**2 * nu**3 / spectral + 1.0)
        bt = (_f(attrs, "Teff_to_Tbb_c0")
              + _f(attrs, "Teff_to_Tbb_c1") * teff
              + _f(attrs, "Teff_to_Tbb_c2") * teff**2)

    finite = bt[np.isfinite(bt)]
    if finite.size:
        lo, hi = float(finite.min()), float(finite.max())
        med = float(np.median(finite))
        if lo < BT_SANITY_K[0] or hi > BT_SANITY_K[1]:
            raise ValueError(
                f"pixel brightness temperature outside {BT_SANITY_K} K "
                f"(got {lo:.1f}..{hi:.1f}) — the radiance unit or the "
                f"{valid_bits}-bit mask is wrong for this granule")
        if not (BT_MEDIAN_SANITY_K[0] <= med <= BT_MEDIAN_SANITY_K[1]):
            raise ValueError(
                f"SCENE MEDIAN brightness temperature {med:.1f} K is outside "
                f"{BT_MEDIAN_SANITY_K} — half a Korean scene cannot be that "
                f"temperature. Check number_of_valid_bits_per_pixel "
                f"(used {valid_bits}) before trusting any number from this file")
    return bt


def geos_latlon(attrs: dict, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Per-pixel latitude and longitude for a GEOS-projected sub-image.

    The sub-image's corner scan angles (``image_upperleft_x/y``) and the
    ground sample distance are file attributes, so no assumption is made about
    where in the full disk the LA window sits.
    """
    ny, nx = shape
    ulx = _f(attrs, "image_upperleft_x")
    uly = _f(attrs, "image_upperleft_y")
    lrx = _f(attrs, "image_lowerright_x")
    lry = _f(attrs, "image_lowerright_y")
    x = np.linspace(ulx, lrx, nx)
    y = np.linspace(uly, lry, ny)
    X, Y = np.meshgrid(x, y)

    H = _f(attrs, "nominal_satellite_height")
    Re = _f(attrs, "earth_equatorial_radius")
    Rp = _f(attrs, "earth_polar_radius")
    sub = _f(attrs, "sub_longitude")                 # radians

    cosx, sinx = np.cos(X), np.sin(X)
    cosy, siny = np.cos(Y), np.sin(Y)
    ratio2 = (Re / Rp) ** 2
    disc = (H * cosx * cosy) ** 2 - (cosy**2 + ratio2 * siny**2) * (H**2 - Re**2)
    with np.errstate(invalid="ignore"):
        sd = np.sqrt(np.where(disc >= 0, disc, np.nan))
        sn = (H * cosx * cosy - sd) / (cosy**2 + ratio2 * siny**2)
        s1 = H - sn * cosx * cosy
        s2 = sn * sinx * cosy
        # ⚠ SIGN. The CGMS LRIT/HRIT formulation writes s3 = -sn·sin(y) for a
        # y axis that increases SOUTHWARD. This product's y decreases downward
        # (image_upperleft_y 0.11696 > image_lowerright_y 0.08902), so y
        # increases NORTHWARD and the sign flips. Written the CGMS way first,
        # the Korean Peninsula came out at latitude -44..-31; the corner
        # attributes settle it, not a convention recalled from memory.
        s3 = sn * siny
        lon = np.degrees(np.arctan2(s2, s1) + sub)
        lat = np.degrees(np.arctan(ratio2 * s3 / np.hypot(s1, s2)))
    return lat, lon


def read_granule(path: str | Path) -> Granule:
    import xarray as xr

    with xr.open_dataset(path, engine="h5netcdf") as ds:
        attrs = dict(ds.attrs)
        var = ds["image_pixel_values"]
        dn = var.values.astype("uint16")
        chan = str(var.attrs.get("channel_name", "?")).lower()
        bits = int(var.attrs.get("number_of_valid_bits_per_pixel",
                                 DEFAULT_VALID_BITS))
        qbits = int(var.attrs.get("number_of_data_quality_flag_bits_per_pixel", 2))
    return Granule(
        bt=brightness_temperature(dn, attrs, valid_bits=bits),
        quality=((dn >> (16 - qbits)) & ((1 << qbits) - 1)).astype("uint8"),
        channel=chan,
        wavelength_um=_f(attrs, "channel_center_wavelength"),
        acquisition_time=str(attrs.get("scene_acquisition_time", "")),
        attrs=attrs,
    )


def s3_key(channel: str, when, area: str = "la020ge") -> str:
    """Object key for one channel at one UTC timestamp."""
    return (f"AMI/L1B/LA/{when:%Y%m}/{when:%d}/{when:%H}/"
            f"gk2a_ami_le1b_{channel}_{area}_{when:%Y%m%d%H%M}.nc")


__all__ = [
    "BT_SANITY_K", "Granule", "MIR_CHANNEL", "TIR_CHANNEL",
    "brightness_temperature", "geos_latlon", "read_granule", "s3_key",
]
