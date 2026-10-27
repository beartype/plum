import asyncio
from collections.abc import Awaitable

import pytest

from plum._resolver import _unwrap_invoked_methods


def test_async_overloads_and_conversion(dispatch):
    @dispatch
    async def f(x: int) -> tuple:
        return x

    @dispatch
    async def f(x: str) -> str:
        return x.upper()

    async def run():
        # Both cold resolution and subsequent cache hits must await before conversion.
        for _ in range(2):
            assert await f(3) == (3,)
            assert await f("hello") == "HELLO"

    asyncio.run(run())


def test_async_invoke_and_registration(dispatch):
    async def f(x: int) -> tuple:
        """Async method documentation."""
        return x

    original = f
    f = dispatch(f)
    invoked = f.invoke(int)
    dispatch.multi((float,))(invoked)

    async def run():
        assert await invoked(2) == (2,)
        assert await f(2.5) == (2.5,)

    asyncio.run(run())
    assert invoked.__name__ == "f"
    assert invoked.__doc__ == original.__doc__
    assert _unwrap_invoked_methods(invoked) is original
    assert f.methods[0].implementation is original
    assert f.resolve_method((1,))[0] is original


def test_async_bound_method(dispatch):
    class A:
        @dispatch
        async def f(self, x: int, *, offset: int = 1) -> tuple:
            return x + offset

    async def run():
        a = A()
        assert await a.f(2, offset=3) == (5,)
        assert await a.f.invoke(int)(2, offset=4) == (6,)

    asyncio.run(run())


def test_async_exception_and_cancellation(dispatch):
    cancelled = []

    @dispatch
    async def f(x: int) -> int:
        raise ValueError("method failed")

    @dispatch
    async def f(x: str) -> str:
        try:
            await asyncio.Future()
        finally:
            cancelled.append(True)

    async def run():
        with pytest.raises(ValueError, match="method failed"):
            await f(1)
        task = asyncio.create_task(f("wait"))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert cancelled == [True]


def test_unannotated_async_and_sync_awaitable_controls(dispatch):
    @dispatch
    async def unannotated(x: int):
        return x

    async def inner(x):
        return x

    @dispatch
    def sync_awaitable(x: int) -> Awaitable[int]:
        return inner(x)

    @dispatch
    async def nested_awaitable(x: int) -> Awaitable[int]:
        return inner(x)

    async def run():
        assert await unannotated(1) == 1
        assert await sync_awaitable(2) == 2
        assert await (await nested_awaitable(3)) == 3

    asyncio.run(run())


def test_mixed_sync_async_overloads_and_none(dispatch):
    @dispatch
    async def f(x: int) -> None:
        return None

    @dispatch
    def f(x: str) -> str:
        return x

    async def run():
        assert await f(1) is None
        assert f("sync") == "sync"

    asyncio.run(run())


def test_async_conversion_error_is_raised_when_awaited(dispatch):
    @dispatch
    async def f(x: int) -> int:
        return "not convertible"

    async def run():
        pending = f(1)
        with pytest.raises(TypeError, match="Cannot convert"):
            await pending

    asyncio.run(run())


def test_async_cancel_before_start_does_not_create_inner_coroutine(dispatch):
    started = []

    @dispatch
    async def f(x: int) -> int:
        started.append(x)
        return x

    async def run():
        task = asyncio.create_task(f(1))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert started == []
