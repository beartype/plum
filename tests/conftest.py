"""Fixtures for testing."""

from unittest.mock import patch

import pytest

import plum
from plum._promotion import _convert, _promotion_rule


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
