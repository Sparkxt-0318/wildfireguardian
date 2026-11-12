"""Generator side of certificate binding (BINDING_RULE.md rev 2.1, R1): turn a format-1 `.wfgc` bundle into format 2.

`to_v2(text, G, A, W, Q)`:
- changes the header `WFGC 1` to `WFGC 2`;
- inserts the BIND section directly after `END_INSTANCE` + newline:
  `BIND` / `I w1..w8` / `G ..` / `A ..` / `W ..` / `Q ..` / `END_BIND`;
- I = SHA-256 of the bytes from the `I` of `INSTANCE` through the newline after `END_INSTANCE`.

The digests G A W Q come from bind_digests.digests() on the inputs the certificate was generated from. This module
imports nothing from either checker.
"""
import hashlib

import bind_digests

FIELDS = ("G", "A", "W", "Q")


def instance_span(text):
    a = text.index("INSTANCE")
    b = text.index("END_INSTANCE\n", a) + len("END_INSTANCE\n")
    return a, b


def to_v2(text, dg):
    if not text.startswith("WFGC 1\n"):
        raise ValueError("expected a format-1 bundle starting 'WFGC 1\\n'")
    a, b = instance_span(text)
    inst = text[a:b]
    I = hashlib.sha256(inst.encode("ascii")).hexdigest()
    rows = ["BIND", "I " + " ".join(map(str, bind_digests.words(I)))]
    for f in FIELDS:
        h = dg[f]
        if not (isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)):
            raise ValueError("%s is not 64 lowercase hex" % f)
        rows.append(f + " " + " ".join(map(str, bind_digests.words(h))))
    rows.append("END_BIND")
    out = "WFGC 2\n" + text[len("WFGC 1\n"):b] + "\n".join(rows) + "\n" + text[b:]
    return out, I
