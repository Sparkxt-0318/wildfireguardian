"""The offline gate, applied to what the API sends rather than to a file.

Round-3 PHASE 22 STEP 0.

WHY A RESPONSE NEEDS THE SAME GATE A PAGE DOES
----------------------------------------------
`scripts/check_screen_assets.py` proves a *file* fetches nothing. That check is
static, and it stops at the file. A JSON response is not a file: it is generated
per request, it carries paths and provenance strings straight out of the run
record, and a browser will happily follow any URL it finds in one.

The realistic ways an external URL reaches a payload here are not exotic:

* a run record carries ``hazard_npz`` and other provenance paths, and one edit
  away from those is a URL;
* an error string built from an exception can contain whatever the exception
  contained;
* a future field holding a documentation link, added by someone who did not
  know the rule.

None of those is caught by a static scan of `demo/*.html`, and each of them puts
a fetchable URL in front of a screen that is supposed to work with the network
unplugged. So the payload is scanned on the way out.

⚠ THIS IS A LAST LINE, NOT THE ONLY ONE. It runs over the serialised response,
so it costs time proportional to the payload. The routing result is a few
hundred kilobytes and the check measures in single-digit milliseconds, which is
affordable against a ~11 s scan. If a payload ever grows to where it is not,
sample rather than delete.
"""

from __future__ import annotations

import re
from typing import Any

#: XML namespace identifiers. Strings that NAME a dialect and are never
#: dereferenced — the same exemption `check_screen_assets` makes, for the same
#: reason, kept deliberately identical so the two gates cannot disagree.
NAMESPACE_IDENTIFIERS: frozenset[str] = frozenset({
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/1999/xlink",
})

#: A URL with a scheme and an authority. Deliberately narrow: this hunts for
#: things a browser would FETCH, not for every string containing a dot.
_URL_RE = re.compile(r"\b(?:https?|ftp|ws|wss|file)://[^\s\"'<>)\\]+",
                     re.IGNORECASE)

#: Protocol-relative URLs (`//cdn.example/x.js`) resolve against the page's own
#: scheme and are as fetchable as an absolute one, while matching no scheme.
_PROTOCOL_RELATIVE_RE = re.compile(r'(?<![:\w/])//[a-z0-9][a-z0-9.-]*\.[a-z]{2,}/')


class ExternalReferenceError(RuntimeError):
    """A response carried a URL a browser could fetch.

    Raised rather than scrubbed. Silently removing the URL would leave the
    payload subtly wrong and the bug in place; failing the request makes it
    somebody's problem now, while the cause is still on screen.
    """

    def __init__(self, urls: list[str], where: str = "response") -> None:
        self.urls = urls
        super().__init__(
            f"{where} carries {len(urls)} external reference(s): "
            f"{', '.join(urls[:5])}"
            f"{' …' if len(urls) > 5 else ''}. This API is consumed by a screen "
            "that must work with the network unplugged, so a fetchable URL in a "
            "payload is a defect even when the URL is valid.")


def find_external_refs(payload: Any) -> list[str]:
    """Every fetchable URL in ``payload``, excluding namespace identifiers.

    Walks the structure rather than the serialised text, so a URL is reported
    with the value it sat in rather than as an offset into a JSON blob.
    """
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            for m in _URL_RE.finditer(node):
                url = m.group(0).rstrip(".,;")
                if url in NAMESPACE_IDENTIFIERS:
                    continue
                found.append(url)
            for m in _PROTOCOL_RELATIVE_RE.finditer(node):
                found.append(m.group(0))
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(k)
                walk(v)
        elif isinstance(node, (list, tuple, set)):
            for v in node:
                walk(v)

    walk(payload)
    return found


def assert_offline(payload: Any, *, where: str = "response") -> Any:
    """Return ``payload`` unchanged, or raise :class:`ExternalReferenceError`."""
    urls = find_external_refs(payload)
    if urls:
        raise ExternalReferenceError(urls, where=where)
    return payload


__all__ = ["ExternalReferenceError", "NAMESPACE_IDENTIFIERS", "assert_offline",
           "find_external_refs"]
