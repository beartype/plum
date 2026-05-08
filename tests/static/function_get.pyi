from collections.abc import Callable
from types import MethodType
from typing_extensions import assert_type

import plum

# ---------------------------------------------------------------------------
# Dispatcher.__call__ — T -> T (preserves callable type)
# ---------------------------------------------------------------------------

# Annotate as Callable so that T is inferred uniformly by both checkers.
_plain: Callable[[int], str]

# Passing a function returns the same type (T -> T)
assert_type(plum.dispatch(_plain), Callable[[int], str])

# ---------------------------------------------------------------------------
# @plum.dispatch on a method preserves the callable signature (T -> T)
# ---------------------------------------------------------------------------

class _Dispatched:
    @plum.dispatch
    def method(self, x: int) -> int: ...

# dispatch must not make the function untyped: the return type is preserved
assert_type(_Dispatched().method(1), int)

# ---------------------------------------------------------------------------
# Function.__get__ descriptor protocol
# ---------------------------------------------------------------------------

class _WithFunction:
    method: plum.Function

# Class-level access (instance=None): __get__ returns Function
assert_type(_WithFunction.method, plum.Function)

# Instance-level access: __get__ returns MethodType
assert_type(_WithFunction().method, MethodType)

# ---------------------------------------------------------------------------
# Dispatcher instance vs module-level dispatch singleton
# ---------------------------------------------------------------------------

d = plum.Dispatcher()
assert_type(d, plum.Dispatcher)

# The module-level singleton has the same type as a freshly constructed one
assert_type(plum.dispatch, plum.Dispatcher)
