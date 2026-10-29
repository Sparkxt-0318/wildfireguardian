"""Grid symmetries and wind-frame canonicalization for environmental kernels.

Coordinates. Arrays are ``[..., H, W]`` with row index increasing southward
and column index increasing eastward (north-up rasters). Wind channels hold
the vector the air moves toward, ``(u, v) = (eastward, northward)`` in m/s,
as produced by ``environment.weather``. Kernel offsets ``delta = (dy, dx)``
follow ``models.new_burn_probability``: offset (dy, dx) weights the source at
(row + dy, col + dx).

D4. ``k`` quarter turns counterclockwise as displayed (``torch.rot90`` on the
last two axes), optionally preceded by an east-west mirror. A physically
exact augmentation transforms the spatial arrays *and* the wind vector
channels; scalar channels (slope, tree cover, biome indicators) only move.
Kernel offset channels are permuted by the same group element, so a kernel
generator ``G`` is equivariant when ``G(g env) = g . G(env)``; group averaging
(:func:`d4_symmetrize_kernels`) makes any generator exactly equivariant.

Wind canonicalization. The environmental raster is rotated so that the
domain-mean wind points along +x (east), the kernel is generated in that
frame and then rotated back (positions and offsets, bilinear). The domain
mean is used because the weather inputs are 9 km model nodes; per-target
rotation would mostly resample the same vector. Resampling makes this an
approximate, not exact, symmetry; at zero rotation it is exact.
"""
from __future__ import annotations

import math
from math import isqrt
from typing import Callable, Sequence

import torch
from torch import Tensor
from torch.nn import functional as F

__all__ = [
    "D4_ELEMENTS", "d4_spatial", "d4_inverse_spatial", "d4_wind", "d4_kernel", "d4_sample",
    "d4_symmetrize_kernels", "rotate_vectors", "offset_rotation_matrix", "rotate_raster",
    "canonical_kernels", "mean_wind_angle",
]

D4_ELEMENTS = tuple((k, flip) for flip in (False, True) for k in range(4))


def d4_spatial(x: Tensor, k: int, flip: bool) -> Tensor:
    """Apply the D4 element to the last two (spatial) axes."""
    if flip:
        x = torch.flip(x, dims=(-1,))
    return torch.rot90(x, k % 4, dims=(-2, -1))


def d4_inverse_spatial(x: Tensor, k: int, flip: bool) -> Tensor:
    x = torch.rot90(x, -(k % 4), dims=(-2, -1))
    return torch.flip(x, dims=(-1,)) if flip else x


def d4_wind(u: Tensor, v: Tensor, k: int, flip: bool) -> tuple[Tensor, Tensor]:
    """Transform the wind vector values consistently with :func:`d4_spatial`.

    A mirror maps east to west (u -> -u). A counterclockwise quarter turn of a
    north-up map maps (east, north) to (north, west): (u, v) -> (-v, u).
    """
    if flip:
        u = -u
    for _ in range(k % 4):
        u, v = -v, u
    return u, v


def d4_kernel(kernels: Tensor, k: int, flip: bool) -> Tensor:
    """Transform positions and offsets of ``[..., K*K, H, W]`` kernels."""
    size = isqrt(kernels.shape[-3])
    if size * size != kernels.shape[-3]:
        raise ValueError("kernels must have K*K offset channels")
    leading = kernels.shape[:-3]
    h, w = kernels.shape[-2:]
    offsets = kernels.reshape(*leading, size, size, h, w)
    # Offsets are themselves a K x K grid with the same orientation as the map.
    offsets = offsets.movedim((-4, -3), (-2, -1))  # [..., H, W, K, K]
    offsets = d4_spatial(offsets, k, flip)
    offsets = offsets.movedim((-2, -1), (-4, -3))  # [..., K, K, H, W]
    moved = d4_spatial(offsets, k, flip)
    return moved.reshape(*leading, size * size, *moved.shape[-2:])


def d4_sample(environment: Tensor, wind_channels: tuple[int, int], k: int, flip: bool,
              *others: Tensor) -> tuple[Tensor, ...]:
    """Exact D4 augmentation of one sample: environment (with wind values) and grids.

    ``environment`` is ``[..., C, H, W]`` in raw (unnormalized) units so that
    the wind vector transform is a pure sign/swap. Any further grids
    (burned states, labels, masks, ages) are moved spatially.
    """
    iu, iv = wind_channels
    moved = d4_spatial(environment, k, flip).clone()
    u, v = d4_wind(moved[..., iu, :, :].clone(), moved[..., iv, :, :].clone(), k, flip)
    moved[..., iu, :, :] = u
    moved[..., iv, :, :] = v
    return (moved, *(d4_spatial(item, k, flip) for item in others))


def d4_symmetrize_kernels(generator: Callable[[Tensor], Tensor], environment: Tensor,
                          wind_channels: tuple[int, int] | None = None) -> Tensor:
    """Group-average a kernel generator: ``(1/8) sum_g g^-1 . G(g . env)``.

    The result is exactly D4-equivariant for any ``generator`` mapping
    ``[..., C, H, W]`` to ``[..., K*K, H, W]`` (raw environment input when
    ``wind_channels`` is given, so the wind values transform too).
    """
    total = None
    for k, flip in D4_ELEMENTS:
        if wind_channels is None:
            moved = d4_spatial(environment, k, flip)
        else:
            moved, = d4_sample(environment, wind_channels, k, flip)
        kernels = generator(moved)
        back = _d4_kernel_inverse(kernels, k, flip)
        total = back if total is None else total + back
    return total / len(D4_ELEMENTS)


def _d4_kernel_inverse(kernels: Tensor, k: int, flip: bool) -> Tensor:
    size = isqrt(kernels.shape[-3])
    leading = kernels.shape[:-3]
    h, w = kernels.shape[-2:]
    offsets = kernels.reshape(*leading, size, size, h, w)
    offsets = d4_inverse_spatial(offsets, k, flip)  # positions
    offsets = offsets.movedim((-4, -3), (-2, -1))
    offsets = d4_inverse_spatial(offsets, k, flip)  # offsets
    offsets = offsets.movedim((-2, -1), (-4, -3))
    return offsets.reshape(*leading, size * size, *offsets.shape[-2:])


def rotate_vectors(u: Tensor, v: Tensor, angle: Tensor | float) -> tuple[Tensor, Tensor]:
    """Rotate (east, north) vectors counterclockwise by ``angle`` radians."""
    c, s = (math.cos(angle), math.sin(angle)) if isinstance(angle, float) else (torch.cos(angle), torch.sin(angle))
    return u * c - v * s, u * s + v * c


def mean_wind_angle(u: Tensor, v: Tensor, valid: Tensor | None = None) -> float:
    """Direction (radians, counterclockwise from east) of the mean wind vector."""
    if valid is not None:
        u, v = u[valid], v[valid]
    if u.numel() == 0:
        return 0.0
    mu, mv = float(u.double().mean()), float(v.double().mean())
    return 0.0 if math.hypot(mu, mv) < 1e-9 else math.atan2(mv, mu)


def offset_rotation_matrix(size: int, angle: float, *, dtype=torch.float64, device=None) -> Tensor:
    """Bilinear map ``W`` with ``K_original = W @ K_canonical`` over offsets.

    The original-frame offset delta reads the canonical kernel at
    ``R(-angle) delta`` (map coordinates), with zero outside the K x K grid.
    """
    radius = size // 2
    ys, xs = torch.meshgrid(torch.arange(-radius, radius + 1, dtype=torch.float64),
                            torch.arange(-radius, radius + 1, dtype=torch.float64), indexing="ij")
    # Map coordinates: east = dx, north = -dy.
    east, north = xs.flatten(), -ys.flatten()
    c, s = math.cos(-angle), math.sin(-angle)
    ce, cn = east * c - north * s, east * s + north * c
    col, row = ce + radius, -cn + radius
    matrix = torch.zeros(size * size, size * size, dtype=torch.float64)
    c0, r0 = torch.floor(col), torch.floor(row)
    for dc in (0, 1):
        for dr in (0, 1):
            cc, rr = c0 + dc, r0 + dr
            weight = (1 - (col - cc).abs()) * (1 - (row - rr).abs())
            inside = (cc >= 0) & (cc < size) & (rr >= 0) & (rr < size) & (weight > 1e-12)
            target = torch.nonzero(inside).flatten()
            source = (rr[inside] * size + cc[inside]).long()
            matrix[target, source] += weight[inside]
    return matrix.to(dtype=dtype, device=device)


def rotate_raster(x: Tensor, angle: float, out_size: tuple[int, int], *, mode: str = "bilinear") -> Tensor:
    """Resample ``x[N, C, H, W]`` so the output shows the map rotated by ``-angle``.

    Output pixel at canonical position q (relative to the centre, square
    pixels) reads the input at ``R(angle) q``. Output and input share their
    centre; outside the input is zero.
    """
    n, c, h, w = x.shape
    oh, ow = out_size
    cos, sin = math.cos(angle), math.sin(angle)
    # Pixel coordinates relative to centre: col = east, row = south.
    rows = torch.arange(oh, dtype=x.dtype, device=x.device) - (oh - 1) / 2
    cols = torch.arange(ow, dtype=x.dtype, device=x.device) - (ow - 1) / 2
    rr, cc = torch.meshgrid(rows, cols, indexing="ij")
    east, north = cc, -rr
    se, sn = east * cos - north * sin, east * sin + north * cos
    src_col, src_row = se + (w - 1) / 2, -sn + (h - 1) / 2
    grid = torch.stack((2 * (src_col + 0.5) / w - 1, 2 * (src_row + 0.5) / h - 1), dim=-1)
    grid = grid.unsqueeze(0).expand(n, -1, -1, -1)
    return F.grid_sample(x, grid, mode=mode, padding_mode="zeros", align_corners=False)


def canonical_kernels(generator: Callable[[Tensor], Tensor], clean: Tensor, angle: float,
                      kernel_size: int) -> Tensor:
    """Generate kernels in the wind frame and rotate them back.

    ``clean`` is the normalized environment ``[N, C, H, W]`` whose wind
    channels have already been rotated by ``-angle`` (so the mean wind lies
    along +x). The raster is rotated onto a canvas large enough to hold the
    whole domain, kernels are generated there, resampled back to the
    original positions, and their offsets rotated by ``W(angle)``.
    """
    if abs(angle) < 1e-12:
        return generator(clean)
    n, c, h, w = clean.shape
    # Same parity as the input keeps pixel centres aligned with the domain.
    pad = int(math.ceil((math.hypot(h, w) - min(h, w)) / 2)) + kernel_size
    canvas = rotate_raster(clean, angle, (h + 2 * pad, w + 2 * pad))
    rotated = generator(canvas)  # [N, K*K, h + 2 pad, w + 2 pad] in the canonical frame
    back = rotate_raster(rotated, -angle, (h, w))
    matrix = offset_rotation_matrix(kernel_size, angle, dtype=back.dtype, device=back.device)
    return torch.einsum("ij,njhw->nihw", matrix, back)
