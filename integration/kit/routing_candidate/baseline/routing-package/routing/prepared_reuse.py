"""Opt-in owner-local reuse of ORIGINAL PreparedGraph admission.

The cache is a trusted local builder store, not an import format for third-party
"validated" objects. Full canonical graph contents and executable source identity
are authenticated. JSON only: cache contents never execute pickle/code.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile
import threading
import time

from routing.prepared import PreparedGraph, _encode
from routing import prepared as prepared_module

SCHEMA = "wfg.owner-local.prepared-graph/1"
MAGIC = b"WFG-PREPARED-1\n"
MAX_HEADER_BYTES = 16384


class CacheAuthorityError(ValueError):
    """An artifact or its trusted local authority cannot be established."""


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def source_identity():
    """Bind all routing-package Python sources and this cache implementation."""
    root = Path(prepared_module.__file__).resolve().parent
    members = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(root.rglob("*.py"))}
    members["@prepared_reuse.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return hashlib.sha256(_json({"schema": SCHEMA, "sources": members})).hexdigest()


def _trusted_object(payload, fingerprint):
    # Only reachable after the ORIGINAL builder validated these exact bytes,
    # either in this process or via an authenticated owner-local cache receipt.
    graph = object.__new__(PreparedGraph)
    object.__setattr__(graph, "_payload", payload)
    object.__setattr__(graph, "_fingerprint", fingerprint)
    return graph


def _private_dir(path):
    path = Path(path).absolute()
    # Refuse symlinks at every existing component, including store ancestors.
    # Rejecting a symlink (rather than resolving it) keeps the trust location clear.
    for p in [*reversed(path.parents), path]:
        try:
            st = p.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(st.st_mode):
            raise CacheAuthorityError("CACHE_DIRECTORY_SYMLINK")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise CacheAuthorityError("CACHE_DIRECTORY_NOT_PRIVATE")
    return path


def _open_private(path, flags):
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), 0o600)
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
            or st.st_mode & 0o077 or st.st_nlink != 1):
        os.close(fd)
        raise CacheAuthorityError("CACHE_FILE_NOT_PRIVATE")
    return fd


def _read_private(path):
    fd = _open_private(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as f:
        return f.read()


@dataclass(frozen=True)
class PreparationReceipt:
    schema: str
    source_sha256: str
    graph_sha256: str
    graph_revision: str
    mode: str
    cache_hit: bool
    lookup_s: float
    payload_bytes: int
    admission_reused: bool


class LocalPreparedStore:
    """One process, full-content ownership; never caches request/hazard state."""
    def __init__(self, *, expected_source_sha256=None):
        self.authority = source_identity()
        if expected_source_sha256 is not None and self.authority != expected_source_sha256:
            raise CacheAuthorityError("SOURCE_AUTHORITY_MISMATCH")
        self._objects = {}
        self._lock = threading.Lock()

    def _authority_check(self):
        if source_identity() != self.authority:
            raise CacheAuthorityError("SOURCE_CHANGED_AFTER_STORE_CREATION")

    def get(self, graph):
        t = time.perf_counter()
        self._authority_check()
        payload = _encode(graph)
        fingerprint = hashlib.sha256(payload).hexdigest()
        with self._lock:
            pg = self._objects.get(fingerprint)
            hit = pg is not None
            if hit and pg._payload != payload:
                raise CacheAuthorityError("GRAPH_DIGEST_COLLISION")
            if not hit:
                # The original constructor is the admission authority.
                # It owns/validates the captured bytes, not later caller state.
                pg = PreparedGraph(json.loads(payload))
                self._objects[fingerprint] = pg
        return pg, PreparationReceipt(SCHEMA, self.authority, fingerprint,
            json.loads(payload)["revision"], "process_local", hit,
            time.perf_counter() - t, len(payload), hit)


class ArtifactPreparedStore:
    """Private authenticated JSON store shared by fresh request processes.

    A same-UID adversary who can read the private key is outside this owner-local
    boundary. Do not accept an externally supplied cache root/key/archive.
    Artifact corruption is rejected, never quietly rebuilt. Missing artifacts
    are constructed by the original cold validator under a per-graph lock.
    """
    def __init__(self, root, *, expected_source_sha256=None):
        self.authority = source_identity()
        if expected_source_sha256 is not None and self.authority != expected_source_sha256:
            raise CacheAuthorityError("SOURCE_AUTHORITY_MISMATCH")
        self.root = _private_dir(root)
        keyfile = self.root / "authority.key"
        lockfd = _open_private(self.root / "authority.lock", os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(lockfd, fcntl.LOCK_EX)
            try:
                self.key = _read_private(keyfile)
            except FileNotFoundError:
                key = secrets.token_bytes(32)
                self._atomic_write(keyfile, key)
                self.key = key
            if len(self.key) != 32:
                raise CacheAuthorityError("CACHE_KEY_FORMAT")
        finally:
            fcntl.flock(lockfd, fcntl.LOCK_UN)
            os.close(lockfd)

    def _atomic_write(self, target, contents):
        fd, tmp = tempfile.mkstemp(prefix=".prepare-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(contents)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
            dirfd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def _signature(self, header):
        return hmac.new(self.key, _json(header), hashlib.sha256).hexdigest()

    def artifact_path(self, graph):
        fingerprint = hashlib.sha256(_encode(graph)).hexdigest()
        return self.root / (self.authority + "-" + fingerprint + ".wfggraph")

    def get(self, graph):
        t = time.perf_counter()
        if source_identity() != self.authority:
            raise CacheAuthorityError("SOURCE_CHANGED_AFTER_STORE_CREATION")
        payload = _encode(graph)
        fingerprint = hashlib.sha256(payload).hexdigest()
        path = self.root / (self.authority + "-" + fingerprint + ".wfggraph")
        lockfd = _open_private(path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(lockfd, fcntl.LOCK_EX)
            try:
                encoded = _read_private(path)
            except FileNotFoundError:
                pg = PreparedGraph(json.loads(payload))
                header = {"schema": SCHEMA, "source_sha256": self.authority,
                          "graph_sha256": fingerprint, "payload_bytes": len(payload),
                          "graph_revision": json.loads(payload)["revision"],
                          "validation_authority": "original.routing.prepared.PreparedGraph"}
                header["hmac_sha256"] = self._signature(header)
                self._atomic_write(path, MAGIC + _json(header) + b"\n" + payload)
                hit = False
            else:
                hit = True
                if not encoded.startswith(MAGIC):
                    raise CacheAuthorityError("ARTIFACT_MAGIC")
                try:
                    header_line, found = encoded[len(MAGIC):].split(b"\n", 1)
                    if len(header_line) > MAX_HEADER_BYTES:
                        raise CacheAuthorityError("ARTIFACT_HEADER_SIZE")
                    header = json.loads(header_line)
                    signature = header.pop("hmac_sha256")
                except (ValueError, TypeError, KeyError) as exc:
                    raise CacheAuthorityError("ARTIFACT_HEADER_FORMAT") from exc
                expected = {"schema": SCHEMA, "source_sha256": self.authority,
                            "graph_sha256": fingerprint, "payload_bytes": len(payload),
                            "graph_revision": json.loads(payload)["revision"],
                            "validation_authority": "original.routing.prepared.PreparedGraph"}
                if header != expected:
                    raise CacheAuthorityError("ARTIFACT_IDENTITY_MISMATCH")
                if not isinstance(signature, str) or not hmac.compare_digest(signature, self._signature(header)):
                    raise CacheAuthorityError("ARTIFACT_AUTHENTICATION_FAILED")
                # Exact comparison binds an authoritative supplied graph,
                # rather than accepting a caller's revision or digest alone.
                if found != payload:
                    raise CacheAuthorityError("ARTIFACT_GRAPH_CONTENT_MISMATCH")
                pg = _trusted_object(found, fingerprint)
        finally:
            fcntl.flock(lockfd, fcntl.LOCK_UN)
            os.close(lockfd)
        return pg, PreparationReceipt(SCHEMA, self.authority, fingerprint,
            json.loads(payload)["revision"], "authenticated_artifact", hit,
            time.perf_counter() - t, len(payload), hit)
