"""Benchmarks for `invoke` and `convert`."""

import pytest

import plum
from . import R1, unannotated_return


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
