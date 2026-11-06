"""Await the result of an `async def` method before converting it.

This module must stay out of the `mypyc` compile set: a compiled `await` throws
exceptions into the inner coroutine with the three-argument `throw`, which Python 3.12
deprecates (`CPy_YieldFromErrorHandle` in `mypyc/lib-rt/misc_ops.c`).
"""

__all__ = ()

from collections.abc import Callable
from typing import Any

from ._util import TypeHint
from ._wraps import update_wrapper


def _async_return_conversion(
    method: Callable[..., Any],
    return_type: TypeHint,
    convert: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap an `async def` method to convert its awaited result.

    Args:
        method (function): Method to wrap.
        return_type (type): Type to convert the awaited result to.
        convert (function): Conversion function, passed in to avoid a circular import
            of `_function`.

    Returns:
        function: `method`, converting its awaited result to `return_type`.
    """

    async def wrapper(*args: Any, **kw: Any) -> Any:
        return convert(await method(*args, **kw), return_type)

    update_wrapper(wrapper, method)
    # Written into `__dict__`, since `mypy` rejects a new attribute on a function.
    wrapper.__dict__["__wrapped_by_plum__"] = method
    return wrapper
