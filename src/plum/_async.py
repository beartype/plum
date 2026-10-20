"""Interpreted coroutine adapter, preserving Python's cancellation behavior."""

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
    """Await a resolved async method before converting its annotated result.

    Keep this adapter outside the mypyc compile set: compiled coroutine
    delegation uses the deprecated three-argument ``throw`` on Python 3.12.
    """

    async def converted(*args: Any, **kw: Any) -> Any:
        return convert(await method(*args, **kw), return_type)

    update_wrapper(converted, method)
    converted.__dict__["__wrapped_by_plum__"] = method
    return converted
