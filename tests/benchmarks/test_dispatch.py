"""Benchmarks for the dispatch paths that plum optimises.

Each benchmark isolates one path, so a change can be reported as a per-path delta
rather than as a single aggregate number. Run them with::

    nox -s benchmark

`--benchmark-disable` is set in ``addopts``, so an ordinary ``pytest`` run still
executes every benchmark once -- they cannot rot -- but times nothing.

Note that timing a *fresh registration* builds a `plum.Function` per round. They are
collected once out of scope, but the rounds still churn through registration state, so
the benchmarks get their own `pytest` invocation rather than being timed inside the
main suite.
"""

from collections.abc import Callable
from typing import Literal

import pytest

import plum

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
        pytest.param(parametric_wide, ((1,),), id="parametric-8-methods"),
    ],
)
def test_call(benchmark, f, args):
    """Time a warm call: the method cache is populated before timing starts."""
    f(*args)
    benchmark(f, *args)


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


class R1:
    pass


class R2:
    pass


@_dispatch
def unannotated_return(x: R1):
    return x


@_dispatch
def annotated_return(x: R1) -> R1:
    return x


@_dispatch
def annotated_union_return(x: R1) -> R1 | R2:
    return x


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
