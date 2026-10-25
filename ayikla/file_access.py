"""Coordinate this process's readers with atomic moves on Windows."""

import os
import threading
import weakref
from contextlib import contextmanager

_registry = weakref.WeakValueDictionary()
_registry_lock = threading.Lock()


@contextmanager
def file_guard(path):
    key = os.path.normcase(os.path.abspath(path))
    with _registry_lock:
        lock = _registry.get(key)
        if lock is None:
            lock = threading.RLock()
            _registry[key] = lock
    with lock:
        yield
