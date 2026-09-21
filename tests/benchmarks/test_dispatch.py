"""Benchmarks for the dispatch paths that plum optimises.

Each benchmark isolates one path, so a change can be reported as a per-path delta
rather than as a single aggregate number. Run them with::

    nox -s benchmark

`tests/conftest.py` disables timing unless ``--benchmark-enable`` is passed, so an
ordinary ``pytest`` run still executes every benchmark once -- they cannot rot -- but
times nothing.

Note that timing a *fresh registration* creates a `plum.Function` per round, and
`Function._instances` keeps them all. That is harmless here but is why the benchmarks
get their own `pytest` invocation instead of being timed inside the main suite.
"""

from collections.abc import Callable
from typing import Literal

import pytest

import plum
from . import (
    R1,
    annotated_return,
    annotated_union_return,
    unannotated_return,
)

# --------------------------------------------------------------------------------
# Plain calls.
#
# `native` is the baseline every other number in this group is read against: it is
# the same call with no dispatch at all.

_dispatch = plum.Dispatcher()


class Base:
    pass


class Derived(Base):
    pass


def native(x):
    return x


def native2(x, y):
    return x


@_dispatch
def faithful(x: int):
    return x


@_dispatch
def faithful(x: str):
    return x


@_dispatch
def faithful2(x: int, y: int):
    return x


@_dispatch
def faithful2(x: str, y: str):
    return x


@_dispatch
def on_class(x: type[Base]):
    return x


@_dispatch
def on_class(x: type[int]):
    return x


@_dispatch
def on_literal(x: Literal["a"]):
    return x


@_dispatch
def on_literal(x: str):
    return x


@_dispatch
def parametric(x: tuple[int]):
    return x


@_dispatch
def parametric(x: tuple[str]):
    return x


@_dispatch
def union_arg(x: int | str):
    return x


@_dispatch
def union_arg(x: float):
    return x


# The same uncacheable dispatch, but on a function that also carries methods a
# `tuple` argument can never match. Full resolution costs one match test per
# method, so this is the case where narrowing the candidates can pay; two methods
# alone leave nothing to narrow and hide the effect entirely.


@_dispatch
def parametric_wide(x: tuple[int]):
    return x


@_dispatch
def parametric_wide(x: tuple[str]):
    return x


@_dispatch
def parametric_wide(x: list[int]):
    return x


@_dispatch
def parametric_wide(x: list[str]):
    return x


@_dispatch
def parametric_wide(x: dict[str, int]):
    return x


@_dispatch
def parametric_wide(x: set[int]):
    return x


@_dispatch
def parametric_wide(x: frozenset[str]):
    return x


@_dispatch
def parametric_wide(x: Callable[[int], int]):
    return x


@pytest.mark.benchmark(group="call")
@pytest.mark.parametrize(
    ("f", "args"),
    [
        pytest.param(native, (1,), id="native"),
        pytest.param(native2, (1, 2), id="native-2-args"),
        pytest.param(faithful, (1,), id="faithful"),
        pytest.param(faithful2, (1, 2), id="faithful-2-args"),
        pytest.param(on_class, (Derived,), id="type[X]"),
        pytest.param(on_literal, ("a",), id="Literal"),
        pytest.param(parametric, ((1,),), id="parametric"),
        pytest.param(union_arg, (1,), id="union-arg"),
        pytest.param(parametric_wide, ((1,),), id="parametric-8-methods"),
    ],
)
def test_call(benchmark, f, args):
    """Time a warm call: the method cache is populated before timing starts."""
    f(*args)
    benchmark(f, *args)


# --------------------------------------------------------------------------------
# Cache misses.
#
# Every `test_call` above is warm, so it times a dict lookup and never the resolver.
# A miss runs the resolver, whose cost grows with the number of registered methods --
# and a real library's `convert` or `promote` carries tens of them, not two. These
# clear the cache before each round, so they are the only benchmarks here that time
# resolution itself.

_many_dispatch = plum.Dispatcher()

# Distinct classes, so each gets its own method and the resolver has a realistic
# number of candidates to order.
_many_types = [type(f"Many{i}", (object,), {}) for i in range(32)]


def _method_on(t):
    def many(x):
        return x

    many.__annotations__ = {"x": t}
    return many


many = None
for _t in _many_types:
    many = _many_dispatch(_method_on(_t))


@_dispatch
def few(x: int):
    return x


@_dispatch
def few(x: str):
    return x


@pytest.mark.benchmark(group="miss")
@pytest.mark.parametrize(
    ("f", "arg"),
    [
        pytest.param(few, 1, id="2-methods"),
        pytest.param(many, None, id="32-methods"),
    ],
)
def test_call_miss(benchmark, f, arg):
    """Time a call that has to resolve, with the cache emptied before each round."""
    if arg is None:
        arg = _many_types[-1]()
    f(arg)
    # `reregister=False`: the default also moves resolved methods back to pending,
    # so each round would time re-registration on top of the resolution this is for.
    benchmark.pedantic(
        f, args=(arg,), setup=lambda: f.clear_cache(reregister=False), rounds=200
    )


# --------------------------------------------------------------------------------
# Calls through a class.


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
        # Both method cases go through a lambda, so both pay the attribute access
        # per call. Binding one side once would leave `Function.__get__` out of
        # only that side and inflate the ratio between them.
        pytest.param(lambda x: _native_instance.go(x), id="native-method"),
        pytest.param(lambda x: _dispatched_instance.go(x), id="dispatched-method"),
    ],
)
def test_method(benchmark, f):
    """Time `__call__` and attribute access, which go through `Function.__get__`."""
    f(1)
    benchmark(f, 1)


# --------------------------------------------------------------------------------
# Return annotations.
#
# An annotated return runs `convert` on every call; an unannotated one is
# short-circuited. The union is the case that costs the most to check.


@pytest.mark.benchmark(group="return")
@pytest.mark.parametrize(
    "f",
    [
        pytest.param(unannotated_return, id="unannotated"),
        pytest.param(annotated_return, id="annotated"),
        pytest.param(annotated_union_return, id="annotated-union"),
    ],
)
def test_return(benchmark, f):
    """Time the return side of a call, holding the argument side fixed."""
    r = R1()
    f(r)
    benchmark(f, r)


# --------------------------------------------------------------------------------
# `invoke` and `convert`.


@pytest.mark.benchmark(group="invoke")
def test_invoke(benchmark):
    """Time resolving a method by type, without calling it."""
    unannotated_return.invoke(R1)
    benchmark(unannotated_return.invoke, R1)


@pytest.mark.benchmark(group="invoke")
def test_invoke_and_call(benchmark):
    """Time `invoke` end to end, which is how a user calls a specific method."""
    r = R1()
    unannotated_return.invoke(R1)(r)  # Warm the wrapper and the method cache.
    benchmark(lambda: unannotated_return.invoke(R1)(r))


@pytest.mark.benchmark(group="convert")
def test_convert(benchmark):
    """Time `plum.convert` on a pair that needs no conversion."""
    plum.convert(1, int)  # Warm the method cache and the identity-conversion memo.
    benchmark(plum.convert, 1, int)


# --------------------------------------------------------------------------------
# Registration.
#
# Registration is where the type hints are classified. It happens once per method,
# but the cost lands on import of any library that dispatches.


def _register_and_resolve(hints):
    """Register one method per hint on a fresh function, then resolve them."""
    dispatch = plum.Dispatcher()
    f = None
    for hint in hints:

        def method(x):
            return x

        method.__annotations__ = {"x": hint}
        f = dispatch(method)
    f._resolve_pending_registrations()
    return f


@pytest.mark.benchmark(group="register")
@pytest.mark.parametrize(
    "hints",
    [
        pytest.param((int, str), id="faithful"),
        pytest.param((int | float, str | bytes), id="union"),
        pytest.param((type[Base], type[int]), id="type[X]"),
        pytest.param((Literal["a"], Literal["b"]), id="Literal"),
        pytest.param((tuple[int], tuple[str]), id="parametric"),
    ],
)
def test_register(benchmark, hints):
    """Time registering a set of methods and resolving them for the first time."""
    benchmark(_register_and_resolve, hints)
