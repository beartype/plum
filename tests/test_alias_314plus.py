import sys
from typing import Union

import pytest

from plum import set_union_alias

# These tests are for Python >= 3.14 only.
pytestmark = [
    pytest.mark.skipif(
        sys.version_info < (3, 14),
        reason="Union aliasing tests for Python >= 3.14",
    ),
]


@pytest.mark.parametrize("display", [str, repr])
def test_union_alias(display):
    # Check that printing is normal before registering any aliases.
    assert display(Union[int, str]) == "int | str"  # noqa: UP007

    # Register a simple alias and check that it prints correctly.
    IntStr = set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    assert display(IntStr) == "int | str"  # noqa: UP007
    assert display(Union[int, str]) == "int | str"  # noqa: UP007

    # Register a bigger alias.
    set_union_alias(Union[int, str, float], alias="IntStrFloat")  # noqa: UP007
    assert display(Union[int, str, float]) == "int | str | float"  # noqa: UP007


@pytest.mark.parametrize("display", [str, repr])
def test_uniontype_alias(display):
    # Check that printing is normal before registering any aliases.
    assert display(int | str) == "int | str"

    # Register a simple alias and check that it prints correctly.
    IntStr = set_union_alias(int | str, alias="IntStr")  # noqa: UP007
    assert display(IntStr) == "int | str"  # noqa: UP007
    assert display(int | str) == "int | str"  # noqa: UP007

    # Register a bigger alias.
    set_union_alias(int | str | float, alias="IntStrFloat")  # noqa: UP007
    assert display(int | str | float) == "int | str | float"  # noqa: UP007


def test_optional():
    assert repr(Union[int, None]) == "int | None"  # noqa: UP007
    assert repr(Union[None, int]) == "None | int"  # noqa: UP007
    assert repr(int | None) == "int | None"


def test_double_registration():
    # We can register with the same alias, but not with a different alias.

    set_union_alias(Union[int, str], alias="IntStr")  # noqa: UP007
    set_union_alias(Union[int, str], alias="OtherIntStr")  # noqa: UP007

    set_union_alias(int | str, alias="IntStr")  # This is OK.
    set_union_alias(int | str, alias="OtherIntStr")

    set_union_alias(int, alias="MyInt")
    set_union_alias(int, alias="MyInt")  # This is OK.
    set_union_alias(int, alias="MyOtherInt")
