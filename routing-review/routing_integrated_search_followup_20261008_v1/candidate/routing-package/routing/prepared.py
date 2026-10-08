"""Explicit, immutable reuse of admitted JSON graph geometry.

Only graph admission is reused. Forecasts, requests, costs, search outcomes and
independent route checks are never cached here.
"""

from dataclasses import dataclass, field
import hashlib
import json

from .validation import ValidationError, validate_graph


def _json_contents(value):
    """Reject Python values which JSON would silently coerce or discard."""
    kind = type(value)
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("graph object keys must be strings")
            _json_contents(item)
    elif kind is list:
        for item in value:
            _json_contents(item)
    elif kind not in (str, int, float, bool, type(None)):
        raise ValueError("prepared graphs require JSON values")


def _encode(graph):
    # Python's JSON float round-trip preserves represented binary64 values,
    # signed zero, and the distinction between integer and float encodings.
    try:
        _json_contents(graph)
        return json.dumps(
            graph,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ValidationError("PREPARED_GRAPH_FORMAT", str(exc)) from exc


@dataclass(frozen=True, slots=True, init=False)
class PreparedGraph:
    """Owned validated bytes; construction always performs graph admission.

    ``snapshot()`` returns a fresh mutable copy, never the trusted storage.
    ``matches()`` compares all canonical bytes, not merely revision or digest.
    This is an API immutability contract, not isolation from arbitrary Python
    code using reflection or bypassing frozen-object protections.
    """

    _payload: bytes = field(repr=False)
    _fingerprint: str

    def __init__(self, graph):
        payload = _encode(graph)
        # Validate the owned snapshot, avoiding a later read of caller state.
        validate_graph(json.loads(payload))
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_fingerprint", hashlib.sha256(payload).hexdigest())

    def __init_subclass__(cls, **kwargs):
        raise TypeError("PreparedGraph cannot be subclassed")

    @property
    def fingerprint(self):
        """SHA-256 of full canonical represented input, for provenance only."""
        return self._fingerprint

    @property
    def encoded_size_bytes(self):
        """Retained serialized payload length; excludes Python object overhead."""
        return len(self._payload)

    def snapshot(self):
        """Decode a fresh graph. Mutating it cannot change future solves."""
        return json.loads(self._payload)

    def matches(self, graph):
        """Exact contents equality; same revision alone never establishes it."""
        try:
            return _encode(graph) == self._payload
        except ValidationError:
            return False


def prepare_graph(graph):
    """Validate and freeze one graph; call again explicitly after any change."""
    return PreparedGraph(graph)
