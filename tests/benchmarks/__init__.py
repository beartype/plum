"""Code shared by the benchmark modules and by `tests/test_benchmark.py`.

The return-annotation functions are timed by both the benchmarks and
`tests/test_benchmark.py`, and defining them twice would let the two copies drift
apart. This module depends on `plum` only, so `tests/test_benchmark.py` does not need
`pytest-benchmark`.
"""

import plum

_dispatch = plum.Dispatcher()


class Base:
    pass


class Derived(Base):
    pass


def _method_on(t):
    def many(x):
        return x

    many.__annotations__ = {"x": t}
    return many


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
