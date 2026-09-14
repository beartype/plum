"""Fixtures for testing, and the benchmark defaults."""

from unittest.mock import patch

import pytest

import plum
from plum._promotion import _convert, _promotion_rule

# Minimum time per benchmark round. At `pytest-benchmark`'s default a sub-microsecond
# benchmark gets too few iterations per round for the timer to resolve: its median
# snaps to a quantum, reproducibly, so a comparison against a run made with this floor
# reports a change that is not there. See `benchmarks/README.md`.
_BENCHMARK_MIN_TIME = 0.0005


def pytest_configure(config: pytest.Config) -> None:
    """Calibrate the benchmarks, and time them only when asked to.

    These were `addopts` entries, which made `pytest-benchmark` a hard requirement of
    *every* `pytest` invocation: without it installed, `pytest` aborts on the
    unrecognised arguments before collecting anything. Setting them here instead means
    the plugin is needed only to run `tests/benchmarks` itself: without it the rest of
    the suite still runs, and only those tests error on the missing fixture.

    This has to be the root `conftest.py` rather than `tests/benchmarks/conftest.py`.
    That one is loaded during collection, which is too late: the benchmarks then run
    *timed* as part of an ordinary suite run, and the registration ones leave a
    `plum.Function` per round behind for `tests/test_cache.py` to walk in its own
    per-call setup, which does not finish in any useful time.
    """
    if not hasattr(config.option, "benchmark_enable"):  # plugin not installed
        return

    config.option.benchmark_min_time = _BENCHMARK_MIN_TIME
    # An ordinary run still executes every benchmark body once, so they cannot rot.
    if not config.option.benchmark_enable:
        config.option.benchmark_disable = True


@pytest.fixture(autouse=True)
def _clean_union_aliases():
    """Give each test its own empty alias registry, restored automatically."""
    import plum._alias as _alias_mod
    from plum._alias import _ALIASED_UNIONS

    with (
        patch.dict(_ALIASED_UNIONS, clear=True),
        patch.object(_alias_mod, "_ALIASES_ARE_ACTIVE", True),
    ):
        yield


@pytest.fixture
def dispatch() -> plum.Dispatcher:
    """Provide a fresh Dispatcher for testing."""
    return plum.Dispatcher()


@pytest.fixture
def convert():
    # Save methods.
    _convert._resolve_pending_registrations()
    resolved = list(_convert._resolved)

    yield plum.convert

    # Clear methods after use.
    _convert._resolve_pending_registrations()
    _convert._pending = []
    _convert._resolved = resolved
    _convert.clear_cache(reregister=True)
    # Restoring the methods changes which conversions are the identity, so the
    # recorded identity conversions have to go with them.
    plum._function._identity_conversions.clear()


@pytest.fixture
def promote():
    # Save methods.
    _promotion_rule._resolve_pending_registrations()
    resolved = list(_promotion_rule._resolved)

    yield plum.promote

    # Clear methods after use.
    _promotion_rule._pending = []
    _promotion_rule._resolved = resolved
    _promotion_rule.clear_cache(reregister=True)
