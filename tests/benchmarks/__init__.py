"""Shapes shared by the benchmarks and by the regression gate in `test_benchmark.py`.

They live here rather than in either module because both time the same three calls --
a return annotation that is satisfied, one that is a union, and none at all -- and two
definitions of the same shape can drift into measuring different things.

Importing this pulls in `plum` only, so `test_benchmark.py` stays free of
`pytest-benchmark`.
"""

__all__ = [
    "R1",
    "R2",
    "annotated_return",
    "annotated_union_return",
    "unannotated_return",
]

import plum

_dispatch = plum.Dispatcher()


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
