"""Compile-time `mypyc` helpers.

:func:`mypyc_attr` lives in :mod:`mypy_extensions`, which is present when building the
`mypyc`-compiled wheel but is **not** a runtime dependency of Plum. The import is
therefore guarded: during compilation the real decorator is used (and recognised by
`mypyc`); in a pure-Python install it falls back to a no-op.
"""

from typing import TYPE_CHECKING

__all__ = ["mypyc_attr"]

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
