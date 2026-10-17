"""Validate live HTTP responses against contracts/wfg_api_v1.yaml (independent of the server's own validator).

The response schema is located by JSON pointer inside the contract document
(#/paths/<path>/<method>/responses/<status>/content/<media type>/schema), so every $ref resolves within the contract.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "wfg_api_v1.yaml"
SPEC = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
URN = "urn:wfg:test-contract"
REGISTRY = Registry().with_resource(URN, Resource.from_contents(SPEC, default_specification=DRAFT202012))
JSON_MEDIA = ("application/json", "application/geo+json")
SEEN: set = set()


def _esc(s: str) -> str:
    return s.replace("~", "~0").replace("/", "~1")


def _resolve_response(resp: dict) -> dict:
    if "$ref" in resp:
        node = SPEC
        for part in resp["$ref"].lstrip("#/").split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return node
    return resp


def assert_conforms(response, path: str, method: str = "get") -> None:
    """``path`` is the contract path template (without the /v1 server prefix), e.g. '/route-checks/{job_id}'."""
    op = SPEC["paths"][path][method]
    status = str(response.status_code)
    assert status in op["responses"], "%s %s returned %s, which the contract does not declare (%s)" % (
        method.upper(), path, status, sorted(op["responses"]))
    resp = op["responses"][status]
    if "$ref" in resp:
        pointer = resp["$ref"]
        resp = _resolve_response(resp)
        base = pointer
    else:
        base = "#/paths/%s/%s/responses/%s" % (_esc(path), method, status)
    media = response.headers.get("content-type", "").split(";")[0].strip()
    assert media in resp["content"], "%s %s %s: media type %r not declared (%s)" % (
        method.upper(), path, status, media, sorted(resp["content"]))
    pointer = "%s/content/%s/schema" % (base, _esc(media))
    instance = response.json() if media in JSON_MEDIA else response.text
    v = Draft202012Validator({"$ref": URN + pointer}, registry=REGISTRY)
    errors = sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))
    assert not errors, "%s %s %s does not match the contract:\n%s" % (
        method.upper(), path, status, "\n".join("  /%s: %s" % ("/".join(map(str, e.absolute_path)), e.message[:300]) for e in errors[:15]))
    SEEN.add((path, method, status))


def assert_component(name: str, instance) -> None:
    v = Draft202012Validator({"$ref": URN + "#/components/schemas/" + name}, registry=REGISTRY)
    errors = list(v.iter_errors(instance))
    assert not errors, "%s: %s" % (name, "; ".join(e.message[:200] for e in errors[:10]))
