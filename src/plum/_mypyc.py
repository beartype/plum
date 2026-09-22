"""Compile-time `mypyc` helpers. This module must stay out of the compile set.

:func:`mypyc_attr` lives in :mod:`mypy_extensions`, which is present when building the
`mypyc`-compiled wheel but is **not** a runtime dependency of Plum. The import is
therefore guarded: during compilation the real decorator is used (and recognised by
`mypyc`); in a pure-Python install it falls back to a no-op.

:class:`NativeBase` works only while this module is interpreted, which is why it lives
here rather than in a module of its own.
"""

from typing import TYPE_CHECKING

__all__ = ["NativeBase", "mypyc_attr"]

if TYPE_CHECKING:
    # Let the type checker see only the real, fully-typed decorator.
    from mypy_extensions import mypyc_attr
else:
    try:
        from mypy_extensions import mypyc_attr
    except ImportError:  # pragma: no cover

        def mypyc_attr(*args, **kwargs):
            """No-op fallback for a pure-Python install."""
            return lambda cls: cls


class NativeBase:
    """Base for `mypyc` native classes. Must stay interpreted.

    A native class has neither `__dict__` nor `__weakref__`, but one inheriting from a
    class outside the compile set gains both and stays native. Its instances can then be
    weakly referenced, which `jax.jit` needs (#318), and accept undeclared attributes,
    such as `__doc__` (#317) and those :func:`functools.wraps` copies.

    Weak references work, but their callbacks never run: a native class frees its
    instances without calling `PyObject_ClearWeakRefs()`. A `weakref.WeakSet` or
    `weakref.WeakValueDictionary` therefore keeps a stale entry, which can crash the
    interpreter at shutdown. See mypyc/mypyc#1102; python/mypy#19056 is the fix.

    `jax.jit` is unaffected: it does not rely on the callback.
    """
