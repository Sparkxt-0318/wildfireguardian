"""The OpenAPI 3.1 contract (contracts/wfg_api_v1.yaml) is the single source of truth: it is served as /openapi.json,
rendered by /docs, and its component schemas validate request bodies (and, in tests, every response)."""
from __future__ import annotations

import functools

import yaml

from .config import CONTRACT_PATH

URN = "urn:wfg:api:v1"


@functools.lru_cache(maxsize=1)
def spec() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def validator(component: str):
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
    registry = Registry().with_resource(URN, Resource.from_contents(spec(), default_specification=DRAFT202012))
    return Draft202012Validator({"$ref": "%s#/components/schemas/%s" % (URN, component)}, registry=registry)


def errors(component: str, instance) -> list:
    out = []
    for e in sorted(validator(component).iter_errors(instance), key=lambda e: list(e.absolute_path)):
        out.append({"path": "/".join(str(p) for p in e.absolute_path), "message": e.message[:300]})
    return out
