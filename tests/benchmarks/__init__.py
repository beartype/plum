"""Code shared by the benchmark modules and by `tests/test_benchmark.py`.

The return-annotation functions are timed by both the benchmarks and
`tests/test_benchmark.py`, and defining them twice would let the two copies drift
apart. This module depends on `plum` only, so `tests/test_benchmark.py` does not need
`pytest-benchmark`.
"""

import plum

__all__ = [
    "Base",
    "Derived",
    "R1",
    "R2",
    "annotated_return",
    "annotated_union_return",
    "method_on",
    "unannotated_return",
]

_dispatch = plum.Dispatcher()


class Base:
    pass


class Derived(Base):
    pass


def method_on(t):
    """Build a function of one argument with type hint `t`."""

    def f(x: t):
        return x

    return f


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
