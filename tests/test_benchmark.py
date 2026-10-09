"""Tests that guard against performance regressions.

These compare the timing of two dispatched calls in the same process. Such a ratio is
robust to machine speed, interpreter version, and CI load; an absolute duration is not.
"""

import timeit

import pytest

from .benchmarks import R1, annotated_return, annotated_union_return, unannotated_return

# Cost of a dispatched call with a return annotation relative to one without. A
# satisfied return annotation is skipped in two places: `_function._convert` does not
# call `convert` at all for a recorded identity conversion, and `convert` returns
# early for one. With both in place the ratio is about 1.2; without the first it is
# about 2.3. The bound lies between the two, so losing either trips the test.
MAX_ANNOTATED_RETURN_OVERHEAD = 1.75


def _time(f, arg, *, n=20_000, repeat=5):
    """Time `f(arg)` in seconds per call.

    The fastest of `repeat` runs is taken, since noise can only ever add time.
    """
    f(arg)  # Warm up the method cache and the identity-conversion cache.
    return min(timeit.repeat(lambda: f(arg), number=n, repeat=repeat)) / n


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "f", [annotated_return, annotated_union_return], ids=["plain", "union"]
)
def test_annotated_return_is_not_much_slower_than_unannotated(f):
    """A return annotation that is already satisfied must add little to a call."""
    r = R1()
    overhead = _time(f, r) / _time(unannotated_return, r)
    assert overhead < MAX_ANNOTATED_RETURN_OVERHEAD, (
        f"An annotated return costs `{overhead:.1f}x` an unannotated one, over the "
        f"`{MAX_ANNOTATED_RETURN_OVERHEAD}x` bound. The identity-conversion fast path "
        f"in `plum._function._convert` has likely regressed."
    )
