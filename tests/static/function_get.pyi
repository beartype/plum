from types import MethodType
from typing_extensions import assert_type

import plum

# --- @plum.dispatch preserves the callable signature (T -> T) ---

class _Dispatched:
    @plum.dispatch
    def method(self, x: int) -> int: ...

# dispatch must not make the function untyped: the return type is preserved
assert_type(_Dispatched().method(1), int)

# --- Function.__get__ descriptor protocol ---

class _WithFunction:
    method: plum.Function

# Class-level access (instance=None): __get__ returns Function
assert_type(_WithFunction.method, plum.Function)

# Instance-level access: __get__ returns MethodType
assert_type(_WithFunction().method, MethodType)
