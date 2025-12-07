from typing import Union

import pytest

import plum
from plum import ModuleType


@pytest.mark.xfail()
def test_beartype_on_strategy():
    # The `O(n)` strategy is not yet supported.
    for _ in range(10):
        assert not plum.isinstance([1, 1, 1, 1, None], list[int])


def test_isinstance():
    # Check that subscripted generics work and types are resolved.
    assert plum.isinstance(
        1,
        Union[float, ModuleType("builtins", "int")],  # noqa: F821
    )


def test_issubclass():
    # Check that subscripted generics work and types are resolved.
    assert plum.issubclass(
        Union[ModuleType("builtins", "int"), float],  # noqa: F821
        Union[ModuleType("numbers", "Number"), complex],  # noqa: F821
    )
