from typing import Union

import plum
from plum import ModuleType


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
