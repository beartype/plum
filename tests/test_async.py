import asyncio


def test_async_return_conversion(dispatch):
    @dispatch
    async def f(x: int) -> tuple:
        return x

    # An invoked method can wrap an `async def` too, so register one as well.
    dispatch.multi((float,))(f.invoke(int))

    async def run():
        assert await f(1) == (1,)
        assert await f(1) == (1,)  # Cache hit.
        assert await f.invoke(int)(1) == (1,)
        assert await f(1.0) == (1.0,)

    asyncio.run(run())
