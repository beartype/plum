"""Benchmarks for plain calls and for cache misses.

`native` is the baseline every other number in the `call` group is read against: it is
the same call with no dispatch at all.
"""

from collections.abc import Callable
from typing import Literal

import pytest

import plum
from . import Base, Derived, _method_on

_dispatch = plum.Dispatcher()


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


# The calls above hit the method cache, so they never run the resolver. A miss does,
# and its cost grows with the number of registered methods: a real library's
# `convert` or `promote` has tens of them. These benchmarks empty the cache before
# every round.

_many_dispatch = plum.Dispatcher()

# Distinct classes, so each gets its own method and the resolver has a realistic
# number of candidates to order.
_many_types = [type(f"Many{i}", (object,), {}) for i in range(32)]


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
        pytest.param(many, _many_types[-1](), id="32-methods"),
    ],
)
def test_call_miss(benchmark, f, arg):
    """Time a call that has to resolve, with the cache emptied before each round."""
    f(arg)
    # `reregister=False`: by default, `clear_cache` also moves the resolved methods back
    # to pending, so every round would time re-registration on top of resolution.
    benchmark.pedantic(
        f, args=(arg,), setup=lambda: f.clear_cache(reregister=False), rounds=200
    )
