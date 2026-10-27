"""Benchmarks for return annotations.

The unannotated case is the baseline. A satisfied annotation, plain or a union, should
add little to it, which `tests/test_benchmark.py` asserts.
"""

import pytest

from . import R1, annotated_return, annotated_union_return, unannotated_return


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
