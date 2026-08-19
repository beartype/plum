"""Speed guards for the fast paths that `tests/benchmark.py` reports on.

These assert *ratios* between two dispatched calls timed in the same process, never
absolute durations: a ratio cancels out machine speed, interpreter version and CI
load, all of which move absolute timings by an order of magnitude.
"""

import timeit

import pytest

import plum

#: Cost of a dispatched call with a return annotation, relative to one without.
#:
#: A return annotation sends the call through `convert`, which is short-circuited
#: twice over: `_function._convert` skips the call entirely on a known-identity pair,
#: and `convert` itself returns early on one. Measured ratios, spread ~2.5% over nine
#: runs each:
#:
#: ===================================  =========  =====
#: State                                Annotated  Union
#: ===================================  =========  =====
#: Both short-circuits (healthy)             ~1.2   ~1.2
#: `_function._convert` fast path gone       ~2.3   ~2.3
#: Cache never consulted (pre-#292)          ~7.4  ~23.3
#: ===================================  =========  =====
#:
#: The bound sits between the first two rows, so either regression trips it, with
#: enough margin on a ~2.5% spread that load cannot decide the outcome.
MAX_ANNOTATED_RETURN_OVERHEAD = 1.75


class _R1:
    pass


class _R2:
    pass


@plum.dispatch
def _unannotated(x: _R1):
    return x


@plum.dispatch
def _annotated(x: _R1) -> _R1:
    return x


@plum.dispatch
def _annotated_union(x: _R1) -> _R1 | _R2:
    return x


def _time(f, arg, *, n=20_000, repeat=5):
    """Seconds per call to `f(arg)`, taking the fastest run.

    The minimum is the robust statistic here: noise can only ever add time.
    """
    f(arg)  # Warm up the method cache and the identity-conversion cache.
    return min(timeit.repeat(lambda: f(arg), number=n, repeat=repeat)) / n


@pytest.mark.benchmark
@pytest.mark.parametrize("f", [_annotated, _annotated_union], ids=["plain", "union"])
def test_annotated_return_is_not_much_slower_than_unannotated(f):
    """A satisfied return annotation must stay nearly free.

    Fails if the identity-conversion fast path stops being taken, and equally if it
    is still taken but has become expensive to consult.
    """
    r = _R1()
    overhead = _time(f, r) / _time(_unannotated, r)
    assert overhead < MAX_ANNOTATED_RETURN_OVERHEAD, (
        f"an annotated return cost {overhead:.1f}x an unannotated one, over the "
        f"{MAX_ANNOTATED_RETURN_OVERHEAD}x bound; the identity-conversion fast path "
        f"has likely regressed (see plum._function._identity_conversions)"
    )
