import typing

import plum


def test_isinstance():
    # Check that subscripted generics work and types are resolved.
    assert plum.isinstance(
        1,
        typing.Union[float, plum.ModuleType("builtins", "int")],  # noqa: F821
    )


def test_issubclass():
    # Check that subscripted generics work and types are resolved.
    assert plum.issubclass(
        typing.Union[plum.ModuleType("builtins", "int"), float],  # noqa: F821
        typing.Union[plum.ModuleType("numbers", "Number"), complex],  # noqa: F821
    )
