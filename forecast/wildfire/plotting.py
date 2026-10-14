"""Matrix and observed-event plots with explicit support for unknown cells.

Matplotlib and PyTorch are not imported when this module is imported. Plotting
accepts real NumPy arrays, masked arrays, and PyTorch tensors (copied to CPU
for display without altering the original). The final two
dimensions are always spatial rows and columns; ``index`` addresses preceding
dimensions in their original order. Unselected preceding dimensions must have
length one. Neither helper thresholds a probability or treats unknowns as zero.
"""
from __future__ import annotations

from numbers import Integral, Real

import numpy as np

__all__ = ["plot_matrix", "plot_comparison"]


def _array(value, name):
    """Convert a real array while preserving an existing NumPy mask."""
    if hasattr(value, "detach") and hasattr(value, "numpy"):
        value = value.detach()
        if hasattr(value, "cpu"):
            value = value.cpu()
        try:
            value = value.numpy()
        except TypeError as exc:
            # NumPy has no bfloat16 dtype. A CPU tensor can convert it safely.
            if str(getattr(value, "dtype", "")) == "torch.bfloat16":
                value = value.float().numpy()
            else:
                raise TypeError(f"{name} must be a dense real numeric array") from exc
    try:
        array = np.ma.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real numeric array") from exc
    if array.dtype.kind not in "biuf":
        raise TypeError(f"{name} must contain real numeric values")
    return array


def _prepare(value, valid=None, *, name="matrix"):
    array = _array(value, name)
    if array.ndim < 2:
        raise ValueError(f"{name} must have at least two dimensions (rows, columns)")
    if array.shape[-2] == 0 or array.shape[-1] == 0:
        raise ValueError(f"{name} must have nonempty spatial dimensions")
    mask = np.ma.getmaskarray(array) | ~np.isfinite(np.ma.getdata(array))
    if valid is not None:
        validity = _array(valid, "valid")
        if validity.dtype.kind != "b":
            raise TypeError("valid must contain booleans")
        if validity.shape != array.shape:
            raise ValueError(
                f"valid shape {validity.shape} must equal the full {name} shape {array.shape}"
            )
        mask = mask | np.ma.getmaskarray(validity) | ~np.ma.getdata(validity)
    return np.ma.array(np.ma.getdata(array), mask=mask, copy=False)


def _select(array, index=None):
    leading = array.shape[:-2]
    if index is None:
        indices = ()
    elif isinstance(index, Integral) and not isinstance(index, (bool, np.bool_)):
        indices = (index,)
    elif isinstance(index, tuple):
        indices = index
    else:
        raise TypeError("index must be an integer or a tuple of integers for leading dimensions")
    if len(indices) > len(leading):
        raise ValueError(
            f"index has {len(indices)} entries but matrix has {len(leading)} leading dimensions"
        )
    selected = []
    for dimension, size in enumerate(leading):
        if dimension < len(indices):
            item = indices[dimension]
            if not isinstance(item, Integral) or isinstance(item, (bool, np.bool_)):
                raise TypeError("index entries must be integers")
            if not -size <= item < size:
                raise IndexError(f"index {item} is out of bounds for leading dimension {dimension} of size {size}")
            selected.append(int(item))
        elif size == 1:
            selected.append(0)
        else:
            raise ValueError(
                f"matrix shape {array.shape} is ambiguous: provide index for leading dimension {dimension} "
                f"of size {size}"
            )
    return array[tuple(selected) + (slice(None), slice(None))]


def _matrix(value, valid=None, index=None):
    """Return one 2D masked matrix without discarding validity information.

    ``valid`` must be boolean and have exactly the full shape of ``value``.
    ``index=t`` selects the first leading dimension; ``index=(b, t)`` selects
    the first two. Any remaining leading dimensions must be singleton.
    Existing masks, nonfinite values, and false or masked validity entries are
    unknown. Input arrays are never modified.
    """
    return _select(_prepare(value, valid), index)


def _colormap(cmap, unknown_color):
    import matplotlib

    result = matplotlib.colormaps.get_cmap(cmap).copy()
    result.set_bad(unknown_color)
    return result


def plot_matrix(
    matrix, *, valid=None, index=None, ax=None, title=None, cmap="viridis",
    vmin=None, vmax=None, colorbar=True, colorbar_label=None,
    unknown_color="#d9d9d9", origin="upper", figsize=(6, 5), **imshow_options,
):
    """Plot one matrix and return ``(figure, axes)``.

    Unknown cells appear in ``unknown_color``. A full-shape boolean ``valid``
    mask can supplement a masked array or its nonfinite cells. Leading
    dimensions require ``index`` unless all have length one. For example,
    ``(T, 1, H, W)`` accepts ``index=t``; ``(B, T, 1, H, W)`` accepts
    ``index=(b, t)``. Negative indices follow NumPy indexing.

    Pass an existing Matplotlib ``ax`` to compose figures. ``figsize`` applies
    only to newly created figures. Additional options such as ``extent``,
    ``interpolation``, and ``aspect`` are passed directly to ``imshow``.
    """
    selected = _matrix(matrix, valid, index)
    import matplotlib.pyplot as plt

    if ax is None:
        figure, ax = plt.subplots(figsize=figsize, constrained_layout=True)
    else:
        figure = ax.figure
    options = {"interpolation": "nearest", **imshow_options}
    image = ax.imshow(selected, cmap=_colormap(cmap, unknown_color), vmin=vmin,
                      vmax=vmax, origin=origin, **options)
    if title is not None:
        ax.set_title(title)
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    if colorbar:
        bar = figure.colorbar(image, ax=ax)
        if colorbar_label is not None:
            bar.set_label(colorbar_label)
    return figure, ax


def _comparison_axes(axes, count, figsize):
    import matplotlib.pyplot as plt
    from matplotlib.axes import Axes

    if axes is None:
        figure, axes = plt.subplots(1, count, figsize=figsize or (5 * count, 5),
                                    squeeze=False, constrained_layout=True)
        return figure, axes.reshape(-1)
    array = np.asarray(axes, dtype=object).reshape(-1)
    if array.size != count or any(not isinstance(ax, Axes) for ax in array):
        raise ValueError(f"axes must contain exactly {count} Matplotlib axes")
    if len({id(ax) for ax in array}) != count:
        raise ValueError("axes must be distinct")
    figure = array[0].figure
    if any(ax.figure is not figure for ax in array):
        raise ValueError("all axes must belong to the same figure")
    return figure, array


def _event_positions(selected, *, extent=None, origin="upper"):
    rows, cols = np.nonzero(np.ma.filled(selected, False))
    if extent is None:
        return cols, rows
    left, right, bottom, top = extent
    height, width = selected.shape
    x = left + (cols + 0.5) * (right - left) / width
    if origin == "upper":
        y = top - (rows + 0.5) * (top - bottom) / height
    else:
        y = bottom + (rows + 0.5) * (top - bottom) / height
    return x, y


def _region_outline(ax, region, *, extent=None, origin="upper", color):
    """Outline every boundary of a physical pixel footprint at cell edges."""
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch

    padded = np.pad(region, 1)
    sides = (
        (region & ~padded[1:-1, :-2], (-0.5, -0.5), (-0.5, 0.5)),
        (region & ~padded[1:-1, 2:], (0.5, -0.5), (0.5, 0.5)),
        (region & ~padded[:-2, 1:-1], (-0.5, -0.5), (0.5, -0.5)),
        (region & ~padded[2:, 1:-1], (-0.5, 0.5), (0.5, 0.5)),
    )
    segments = []
    for boundary, start, end in sides:
        rows, cols = np.nonzero(boundary)
        centers = np.column_stack((cols, rows))
        segments.append(np.stack((centers + start, centers + end), axis=1))
    vertices = np.concatenate(segments, axis=0).reshape(-1, 2)
    if extent is not None:
        left, right, bottom, top = extent
        height, width = region.shape
        vertices[:, 0] = left + (vertices[:, 0] + 0.5) * (right - left) / width
        row_fraction = (vertices[:, 1] + 0.5) / height
        vertices[:, 1] = (top - row_fraction * (top - bottom) if origin == "upper"
                          else bottom + row_fraction * (top - bottom))
    codes = np.tile([Path.MOVETO, Path.LINETO], len(vertices) // 2)
    outline = PathPatch(Path(vertices, codes), fill=False, edgecolor=color,
                        linewidth=1.2, zorder=3, label="Loaded region")
    ax.add_patch(outline)


def plot_comparison(
    probability, observed, *, valid=None, observed_valid=None, index=None,
    burned_area=None, burned_area_valid=None,
    mode="overlay", axes=None, titles=None, figsize=None, cmap="viridis",
    unknown_color="#d9d9d9", event_color="#00e5ff", event_label="Newly burned in forecast interval", marker="o",
    marker_size=18, marker_facecolor="none", burned_color="#8b5a2b", burned_alpha=0.65,
    region_valid=None, region_color="#586a7a",
    colorbar=True, **imshow_options,
):
    """Compare observed newly burned cells with predicted event probabilities.

    ``probability`` and ``observed`` must have identical full shapes. Known
    probabilities must lie in ``[0, 1]``; known observations must be binary
    zero/one. Each array retains its own mask, supplemented by the corresponding
    full-shape boolean ``valid`` or ``observed_valid``. Supply observations for
    the same prediction interval; this function does not infer time alignment.

    The default ``mode='overlay'`` shows one probability panel with markers at
    observed next-hour events. Optional binary ``burned_area`` describes the
    cumulative area already burned at the prediction cutoff, with its own
    ``burned_area_valid`` mask. It must have the same full shape as probability
    and is drawn as a translucent layer beneath the event markers. This helper
    does not infer timestamps for either reference field.

    Each layer retains its own validity: known observed events and previously
    burned cells remain visible even where probabilities are unavailable.
    An absent marker does not imply a known negative outcome when the reference
    is unavailable. ``mode='side_by_side'`` shows observations and probabilities
    in two panels; ``mode='both'`` additionally shows the combined overlay.
    Probability colors always span zero to one; no threshold is applied.

    ``index`` has the same meaning as in :func:`plot_matrix`. ``axes`` can be a
    single axes for overlay mode or a collection with one distinct axes per
    panel, all in one figure. ``titles`` accepts one title per displayed panel
    (or a string for overlay mode). A three-title sequence can also be supplied
    in any mode: it denotes observations, probability, and overlay, and the
    titles for the displayed panels are selected automatically. ``figsize``
    applies only when creating a figure; its default is ``(5 * panel_count, 5)``.
    ``cmap`` controls probability colors, ``event_color`` controls positive
    observations and overlay markers, and ``unknown_color`` controls unknown
    cells. ``event_label`` names the reference interval in the overlay legend.
    ``marker`` is a Matplotlib marker style and ``marker_size`` is its
    area in square points. Markers have cyan outlines and are hollow by default
    (``marker_facecolor='none'``), so the probability color remains visible
    inside. Supply a Matplotlib color to fill them. ``burned_color`` and
    ``burned_alpha`` (between zero
    and one) control the previous-burn layer in overlay panels. ``colorbar``
    controls the shared probability scale, which applies to the background only.
    Extra options are passed to ``imshow``; explicit
    ``vmin``, ``vmax``, and ``norm`` are rejected to preserve the probability
    scale. ``extent`` and ``origin`` also control event-marker positions.
    Optional boolean ``region_valid`` outlines the loaded physical footprint
    in ``region_color``. It may have the full probability shape or the selected
    spatial shape ``(H, W)``. This is separate from probability availability:
    the full raster extent remains visible, including unburned/unknown areas.
    Returns ``(figure, axes)`` with a one-dimensional NumPy array of panel axes.
    """
    modes = {"side_by_side": ("observed", "probability"),
             "overlay": ("overlay",), "both": ("observed", "probability", "overlay")}
    if mode not in modes:
        raise ValueError("mode must be 'side_by_side', 'overlay', or 'both'")
    if (isinstance(burned_alpha, (bool, np.bool_)) or not isinstance(burned_alpha, Real)
            or not np.isfinite(burned_alpha) or not 0 <= burned_alpha <= 1):
        raise ValueError("burned_alpha must be a finite number in [0, 1]")
    if burned_area is None and burned_area_valid is not None:
        raise ValueError("burned_area_valid requires burned_area")
    for reserved in ("vmin", "vmax", "norm"):
        if reserved in imshow_options:
            raise ValueError(f"{reserved} cannot override the fixed probability range [0, 1]")
    predicted = _prepare(probability, valid, name="probability")
    full_shape = predicted.shape
    target = _prepare(observed, observed_valid, name="observed")
    if predicted.shape != target.shape:
        raise ValueError(f"probability shape {predicted.shape} must equal observed shape {target.shape}")
    known_probabilities = predicted.compressed()
    if np.any((known_probabilities < 0) | (known_probabilities > 1)):
        raise ValueError("known probability values must lie in [0, 1]")
    known_targets = target.compressed()
    if np.any((known_targets != 0) & (known_targets != 1)):
        raise ValueError("known observed values must be binary (0 or 1)")
    previous = None
    if burned_area is not None:
        previous = _prepare(burned_area, burned_area_valid, name="burned_area")
        if previous.shape != predicted.shape:
            raise ValueError(f"burned_area shape {previous.shape} must equal probability shape {predicted.shape}")
        known_previous = previous.compressed()
        if np.any((known_previous != 0) & (known_previous != 1)):
            raise ValueError("known burned_area values must be binary (0 or 1)")
        previous = _select(previous, index)
    predicted, target = _select(predicted, index), _select(target, index)
    region = None
    if region_valid is not None:
        region = _array(region_valid, "region_valid")
        if region.dtype.kind != "b":
            raise TypeError("region_valid must contain booleans")
        if region.shape == full_shape:
            region = _select(region, index)
        elif region.shape != predicted.shape:
            raise ValueError("region_valid must match the full probability shape or selected spatial shape (H, W)")
        region = np.asarray(np.ma.filled(region, False))
    panels = modes[mode]
    defaults = {"observed": "Observed newly burned cells",
                "probability": "Predicted new-burn probability q",
                "overlay": "New burns over predicted probability q"}
    if previous is not None:
        defaults["overlay"] = "Previous burned area and new burns\nOver predicted probability q"
    if titles is None:
        titles = [defaults[panel] for panel in panels]
    elif isinstance(titles, str):
        if len(panels) != 1:
            raise ValueError(f"titles must contain exactly {len(panels)} titles")
        titles = [titles]
    else:
        try:
            titles = list(titles)
        except TypeError as exc:
            raise TypeError("titles must be a sequence of panel titles") from exc
        if len(titles) == 3 and len(panels) != 3:
            all_titles = dict(zip(("observed", "probability", "overlay"), titles))
            titles = [all_titles[panel] for panel in panels]
        elif len(titles) != len(panels):
            raise ValueError(f"titles must contain exactly {len(panels)} titles")

    from matplotlib.colors import ListedColormap
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    figure, panel_axes = _comparison_axes(axes, len(panels), figsize)
    probability_cmap = _colormap(cmap, unknown_color)
    observed_cmap = ListedColormap(["#ffffff", event_color])
    observed_cmap.set_bad(unknown_color)
    previous_layer = None
    if previous is not None:
        previous_layer = np.ma.array(
            np.ma.getdata(previous),
            mask=np.ma.getmaskarray(previous) | (np.ma.getdata(previous) != 1),
        )
        previous_cmap = ListedColormap([burned_color])
        previous_cmap.set_bad((0, 0, 0, 0))
    options = {"interpolation": "nearest", "origin": "upper", **imshow_options}
    if options["origin"] is None:
        import matplotlib

        options["origin"] = matplotlib.rcParams["image.origin"]
    probability_images = []
    probability_axes = []
    for panel, ax, title in zip(panels, panel_axes, titles):
        if panel == "observed":
            ax.imshow(target, cmap=observed_cmap, vmin=0, vmax=1, **options)
            legend = [Patch(facecolor="#ffffff", edgecolor="#666666", label="No observed event (0)"),
                      Patch(facecolor=event_color, label="Observed event (1)")]
        else:
            probability_images.append(ax.imshow(predicted, cmap=probability_cmap, vmin=0, vmax=1, **options))
            probability_axes.append(ax)
            legend = []
            if panel == "overlay":
                if previous_layer is not None:
                    ax.imshow(previous_layer, cmap=previous_cmap, vmin=0, vmax=1,
                              **{**options, "alpha": burned_alpha})
                    legend.append(Patch(facecolor=burned_color, alpha=burned_alpha,
                                        label="Already burned at cutoff"))
                x, y = _event_positions(target, extent=options.get("extent"), origin=options["origin"])
                # imshow sets the limits before scatter. Freeze them so empty or
                # sparse event selections cannot change the displayed raster.
                xlim, ylim = ax.get_xlim(), ax.get_ylim()
                ax.scatter(x, y, s=marker_size, marker=marker, facecolors=marker_facecolor,
                           edgecolors=event_color, linewidths=1.2)
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
                legend.append(Line2D([], [], color=event_color, marker=marker, linestyle="None",
                                     markerfacecolor=marker_facecolor, markeredgecolor=event_color,
                                     markeredgewidth=1.2, label=event_label))
        if region is not None:
            xlim, ylim = ax.get_xlim(), ax.get_ylim()
            _region_outline(ax, region, extent=options.get("extent"), origin=options["origin"], color=region_color)
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            legend.append(Line2D([], [], color=region_color, label="Loaded region"))
        displayed = target if panel == "observed" else predicted
        if np.ma.getmaskarray(displayed).any():
            legend.append(Patch(facecolor=unknown_color,
                                label="Reference unavailable" if panel == "observed" else "Probability unavailable"))
        ax.legend(handles=legend, loc="best", fontsize="small")
        ax.set_title(title)
        ax.set_xlabel("Column" if options.get("extent") is None else "x")
        ax.set_ylabel("Row" if options.get("extent") is None else "y")
    if colorbar:
        bar = figure.colorbar(probability_images[0], ax=probability_axes)
        bar.set_label("New-burn probability q")
    return figure, panel_axes
