"""Population-weighted scoring and calibration for either model family."""

from __future__ import annotations

from typing import Any

import numpy as np

from .cache import CachedSplit

LOG_LOSS_EPSILON = 1e-7


def brier(target: np.ndarray, prediction: np.ndarray, weight: np.ndarray) -> float:
    residual = prediction.astype(np.float64) - target.astype(np.float64)
    return float(np.dot(weight, residual * residual) / weight.sum(dtype=np.float64))



def weighted_rank_metrics(target: np.ndarray, prediction: np.ndarray,
                          weight: np.ndarray) -> tuple[float | None, float | None]:
    """Average precision and ROC AUC with tied scores treated as one threshold."""
    positive = float(np.dot(weight, target))
    negative = float(weight.sum(dtype=np.float64) - positive)
    if positive == 0:
        return None, None
    order = np.argsort(-prediction, kind="stable")
    sorted_scores = prediction[order]
    sorted_y = target[order]
    sorted_w = weight[order]
    thresholds = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(order) - 1]
    true_positive = np.cumsum(sorted_w * sorted_y, dtype=np.float64)[thresholds]
    false_positive = np.cumsum(sorted_w * (1 - sorted_y), dtype=np.float64)[thresholds]
    recall = true_positive / positive
    precision = true_positive / (true_positive + false_positive)
    ap = float(np.dot(np.diff(np.r_[0.0, recall]), precision))
    auc = None
    if negative > 0:
        fpr = np.r_[0.0, false_positive / negative]
        tpr = np.r_[0.0, recall]
        auc = float(np.sum(np.diff(fpr) * (tpr[:-1] + tpr[1:]) / 2))
    return ap, auc



def probability_metrics(target: np.ndarray, prediction: np.ndarray,
                        weight: np.ndarray, neighbor_count: np.ndarray) -> dict[str, Any]:
    n = len(target)
    if n == 0:
        return {"sample_count": 0, "represented_population_weight": 0.0,
                "brier": None, "average_precision": None, "roc_auc": None,
                "clipped_log_loss": None, "exact_negative_log_likelihood_mean": None}
    y = target.astype(np.float64)
    p = prediction.astype(np.float64)
    total = float(weight.sum(dtype=np.float64))
    positives = y == 1
    zero_contact = neighbor_count == 0
    unsupported = positives & (p == 0)
    wrong_certain = (~positives) & (p == 1)
    clipped = np.clip(p, LOG_LOSS_EPSILON, 1 - LOG_LOSS_EPSILON)
    clipped_terms = np.where(positives, -np.log(clipped), -np.log1p(-clipped))
    if unsupported.any() or wrong_certain.any():
        exact_nll: float | str = "infinity"
    else:
        exact_terms = np.empty(n, dtype=np.float64)
        exact_terms[positives] = -np.log(p[positives])
        exact_terms[~positives] = -np.log1p(-p[~positives])
        exact_nll = float(np.dot(weight, exact_terms) / total)
    ap, auc = weighted_rank_metrics(y, p, weight)
    positive_weight = float(weight[positives].sum(dtype=np.float64))
    return {
        "sample_count": n,
        "represented_population_weight": total,
        "positive_sample_count": int(positives.sum()),
        "sample_positive_fraction": float(positives.mean()),
        "positive_population_weight": positive_weight,
        "weighted_prevalence": positive_weight / total,
        "mean_probability": float(np.dot(weight, p) / total),
        "brier": brier(y, p, weight),
        "positive_class_brier": brier(y[positives], p[positives], weight[positives]) if positives.any() else None,
        "negative_class_brier": brier(y[~positives], p[~positives], weight[~positives]) if (~positives).any() else None,
        "average_precision": ap,
        "roc_auc": auc,
        "clipped_log_loss": float(np.dot(weight, clipped_terms) / total),
        "log_loss_probability_floor": LOG_LOSS_EPSILON,
        "exact_negative_log_likelihood_mean": exact_nll,
        "unsupported_positive_sample_count": int(unsupported.sum()),
        "unsupported_positive_population_weight": float(weight[unsupported].sum()),
        "zero_contact_positive_sample_count": int((zero_contact & positives).sum()),
        "zero_contact_positive_population_weight": float(weight[zero_contact & positives].sum()),
        "zero_contact_positive_fraction": (float(weight[zero_contact & positives].sum()) / positive_weight
                                            if positive_weight else None),
        "zero_contact_population_weight": float(weight[zero_contact].sum()),
        "wrong_probability_one_negative_sample_count": int(wrong_certain.sum()),
    }



def weighted_calibration(target, prediction, weight):
    """Descriptive pooled reliability bins with inverse sampling weights.

    Bins are fixed before evaluation. These weighted cell-hour summaries do
    not give uncertainty intervals or assume neighboring targets independent.
    """
    edges = np.array([0, .01, .02, .05, .1, .2, .5, 1.0], dtype=np.float64)
    membership = np.minimum(np.searchsorted(edges, prediction, side="right") - 1, len(edges) - 2)
    total = float(weight.sum(dtype=np.float64))
    bins, absolute_error = [], 0.0
    for index in range(len(edges) - 1):
        selected = membership == index
        population = float(weight[selected].sum(dtype=np.float64))
        mean_p = float(np.dot(weight[selected], prediction[selected]) / population) if population else None
        outcome = float(np.dot(weight[selected], target[selected]) / population) if population else None
        if population:
            absolute_error += population / total * abs(mean_p - outcome)
        bins.append(dict(lower=float(edges[index]), upper=float(edges[index + 1]),
                         upper_inclusive=index == len(edges) - 2,
                         sample_count=int(selected.sum()),
                         positive_sample_count=int(target[selected].sum()),
                         represented_population_weight=population,
                         population_fraction=population / total,
                         mean_probability=mean_p, weighted_outcome_rate=outcome))
    return dict(bins=bins, weighted_expected_calibration_error=absolute_error,
                interpretation="Fixed-bin descriptive weighted reliability; no confidence intervals")



def scoped_metrics(data: CachedSplit, predictions: dict[str, np.ndarray],
                   selection: np.ndarray | None = None) -> dict[str, Any]:
    selected = np.ones(len(data), dtype=bool) if selection is None else selection
    counts = data.neighbor_count
    result = {}
    for name, p in predictions.items():
        result[name] = {}
        for scope, mask in (("all_eligible", selected), ("burned_neighbor_contact", selected & (counts > 0))):
            result[name][scope] = probability_metrics(data.target[mask], p[mask], data.weight[mask], counts[mask])
    return result



def country_for_event(metadata: dict[str, Any], event_id: str) -> str:
    per_event = metadata.get("per_event", {})
    if isinstance(per_event, dict):
        entry = per_event.get(event_id, {})
    else:
        entry = next((record for record in per_event
                      if record.get("event_id", record.get("id")) == event_id), {})
    value = entry.get("country", entry.get("country_code", "unknown"))
    return str(value)



def split_metrics(data: CachedSplit, predictions: dict[str, np.ndarray],
                  metadata: dict[str, Any]) -> dict[str, Any]:
    indices = np.unique(data.event_index)
    event_metrics = {}
    for index in indices:
        event_id = metadata["event_ids"][int(index)]
        event_metrics[event_id] = scoped_metrics(data, predictions, data.event_index == index)
    return {"models": scoped_metrics(data, predictions),
            "per_event": event_metrics}

