"""Benchmarks for calls through a class."""

import pytest

import plum


class NativeClass:
    def __call__(self, x):
        return x

    def go(self, x):
        return x


class DispatchedClass:
    _dispatch = plum.Dispatcher()

    @_dispatch
    def __call__(self, x: int):
        return x

    @_dispatch
    def __call__(self, x: str):
        return x

    @_dispatch
    def go(self, x: int):
        return x

    @_dispatch
    def go(self, x: str):
        return x


_native_instance = NativeClass()
_dispatched_instance = DispatchedClass()


@pytest.mark.benchmark(group="method")
@pytest.mark.parametrize(
    "f",
    [
        pytest.param(_native_instance, id="native-call"),
        pytest.param(_dispatched_instance, id="dispatched-call"),
        # Both method cases go through a lambda, so that both pay for the attribute
        # access on every call. Binding only one of them once would inflate the ratio
        # between the two.
        pytest.param(lambda x: _native_instance.go(x), id="native-method"),
        pytest.param(lambda x: _dispatched_instance.go(x), id="dispatched-method"),
    ],
)
def test_method(benchmark, f):
    """Time `__call__` and attribute access, which go through `Function.__get__`."""
    f(1)
    benchmark(f, 1)
