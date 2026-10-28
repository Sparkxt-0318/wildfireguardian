"""Per-preparation backend selection; native execution never patches modules.

Only exact dyadic integer results are accepted from the extension. Unsupported
inputs retain the pre-existing exact Python fallback. A requested native
backend fails closed when its binary/source/loader identity is unavailable or
changes after loading. This assumes CPython's GIL and does not defend against
arbitrary in-process reflection or an adversary replacing files during loading.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import platform
import sys
import sysconfig
import threading
import types


class NativeBackendError(RuntimeError):
    """Requested preparation backend cannot be verified or used."""


_DEFAULT_MODE = os.environ.get('WFG_GRAPH_BACKEND', 'python')
_LOAD_LOCK = threading.Lock()
_LOADED = None


def resolve_mode(mode=None):
    value = _DEFAULT_MODE if mode is None else mode
    if type(value) is not str or value not in ('python', 'native'):
        raise NativeBackendError('UNSUPPORTED_GRAPH_BACKEND')
    return value


def _hash_regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise NativeBackendError('NATIVE_FILE_UNAVAILABLE:' + str(path))
    try:
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise NativeBackendError('NATIVE_FILE_UNREADABLE:' + str(path)) from exc
    key = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns)
    if key(before) != key(after):
        raise NativeBackendError('NATIVE_FILE_CHANGED_DURING_READ:' + str(path))
    return hashlib.sha256(data).hexdigest()


def _load_native():
    global _LOADED
    with _LOAD_LOCK:
        root = Path(__file__).resolve().parent
        suffix = sysconfig.get_config_var('EXT_SUFFIX')
        if not suffix or sys.implementation.name != 'cpython':
            raise NativeBackendError('UNSUPPORTED_PYTHON_ABI')
        binary = root / ('wfg_native_cell' + suffix)
        source = root / 'native_cell.c'
        binary_hash = _hash_regular(binary)
        source_hash = _hash_regular(source)
        fullname = __package__ + '.wfg_native_cell'
        if _LOADED is None:
            existing = sys.modules.get(fullname)
            # A pre-populated sys.modules entry can forge both __spec__ and
            # builtin-looking callables. Only our own first import establishes
            # the relationship between the on-disk binary and live functions.
            if existing is not None:
                raise NativeBackendError('NATIVE_PREEXISTING_MODULE_UNTRUSTED')
            try:
                spec = importlib.util.find_spec(fullname)
            except (ImportError, ValueError, AttributeError) as exc:
                raise NativeBackendError('NATIVE_SPEC_UNAVAILABLE') from exc
            if (spec is None or not isinstance(spec.loader, importlib.machinery.ExtensionFileLoader)
                    or not spec.origin or Path(spec.origin).resolve() != binary.resolve()):
                raise NativeBackendError('NATIVE_LOADER_ORIGIN_MISMATCH')
            try:
                module = importlib.import_module(fullname)
            except (ImportError, OSError) as exc:
                raise NativeBackendError('NATIVE_EXTENSION_UNAVAILABLE') from exc
            module_spec = getattr(module, '__spec__', None)
            if (module_spec is None
                    or not isinstance(module_spec.loader, importlib.machinery.ExtensionFileLoader)
                    or not module_spec.origin
                    or Path(module_spec.origin).resolve() != binary.resolve()
                    or Path(getattr(module, '__file__', '')).resolve() != binary.resolve()
                    or not isinstance(getattr(module, 'cell_at', None), types.BuiltinFunctionType)
                    or not isinstance(getattr(module, 'same_cell', None), types.BuiltinFunctionType)
                    or sys.modules.get(fullname) is not module):
                raise NativeBackendError('NATIVE_LOADED_MODULE_MISMATCH')
            if _hash_regular(binary) != binary_hash or _hash_regular(source) != source_hash:
                raise NativeBackendError('NATIVE_FILE_CHANGED_DURING_IMPORT')
            _LOADED = (module, binary_hash, source_hash, str(binary.resolve()), str(source.resolve()),
                       module.cell_at, module.same_cell)
        module, loaded_binary, loaded_source, binary_path, source_path, loaded_cell, loaded_chord = _LOADED
        if (binary_hash != loaded_binary or source_hash != loaded_source
                or str(binary.resolve()) != binary_path or str(source.resolve()) != source_path
                or sys.modules.get(fullname) is not module
                or getattr(module, 'cell_at', None) is not loaded_cell
                or getattr(module, 'same_cell', None) is not loaded_chord):
            raise NativeBackendError('NATIVE_IDENTITY_CHANGED_AFTER_LOAD')
        return module, binary_hash, source_hash, binary_path, source_path


def backend_identity(mode=None):
    selected = resolve_mode(mode)
    result = {'schema': 'wfg.native-backend/1', 'requested_mode': selected,
              'effective_mode': selected, 'python_implementation': sys.implementation.name,
              'python_version': platform.python_version(), 'cache_tag': sys.implementation.cache_tag,
              'soabi': sysconfig.get_config_var('SOABI'), 'machine': platform.machine(),
              'system': platform.system(), 'native_source_sha256': None,
              'native_binary_sha256': None, 'native_binary_path': None}
    if selected == 'native':
        _, binary_hash, source_hash, binary_path, _ = _load_native()
        result.update(native_source_sha256=source_hash, native_binary_sha256=binary_hash,
                      native_binary_path=binary_path)
    return result


class NativeOperations:
    """One graph validation owns its own counters, factory and fallback."""
    def __init__(self, fallback_cell):
        self.identity = backend_identity('native')
        self._module = _load_native()[0]
        self._cell_at = self._module.cell_at
        self._same_cell = self._module.same_cell
        self._fallback_cell = fallback_cell
        self.node_hits = self.node_fallbacks = 0
        self.chord_hits = self.chord_fallbacks = 0

    def cell_at(self, grid, x, y):
        cell = self._cell_at(grid, x, y)
        if cell is None:
            self.node_fallbacks += 1
            return self._fallback_cell(grid, x, y)
        self.node_hits += 1
        return cell

    def wrap_chord(self, baseline):
        def chord(grid, u, v):
            cell = self._same_cell(grid, u, v)
            if cell is None:
                self.chord_fallbacks += 1
                return baseline(grid, u, v)
            self.chord_hits += 1
            return [{'cell': cell, 'start': 0.0, 'end': 1.0}]
        return chord

    def receipt(self):
        if backend_identity('native') != self.identity:
            raise NativeBackendError('NATIVE_IDENTITY_CHANGED_DURING_PREPARATION')
        return {'identity': self.identity, 'node_hits': self.node_hits,
                'node_fallbacks': self.node_fallbacks, 'chord_hits': self.chord_hits,
                'chord_fallbacks': self.chord_fallbacks, 'admission_reused': False}
