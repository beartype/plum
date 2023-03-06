from typing import Union

import pytest

from plum import activate_union_aliases, deactivate_union_aliases, set_union_alias
from plum.alias import _aliased_unions


@pytest.fixture()
def union_aliases():
    """Activate union aliases during the test and remove all aliases after the test
    finishes."""
    activate_union_aliases()
    yield
    deactivate_union_aliases()
    _aliased_unions.clear()


@pytest.mark.parametrize("display", [str, repr])
def test_union_alias(display, union_aliases):
    # Check that printing is normal before registering any aliases.
    assert display(Union[int, str]) in {
        "typing.Union[int, str]",
        "typing.Union[str, int]",
    }

    # Register a simple alias and check that it prints correctly.
    IntStr = set_union_alias(Union[int, str], alias="IntStr")
    assert display(IntStr) == "typing.Union[IntStr]"
    assert display(Union[int, str]) == "typing.Union[IntStr]"
    assert display(Union[int, str, float]) in {
        "typing.Union[IntStr, float]",
        "typing.Union[float, IntStr]",
    }

    # Register a bigger alias.
    set_union_alias(Union[int, str, float], alias="IntStrFloat")
    assert display(Union[int, str]) == "typing.Union[IntStr]"
    assert display(Union[int, str, float]) == "typing.Union[IntStrFloat]"
    assert display(Union[int, str, complex]) in {
        "typing.Union[IntStr, complex]",
        "typing.Union[complex, IntStr]",
    }
    assert display(Union[int, str, float, complex]) in {
        "typing.Union[IntStrFloat, complex]",
        "typing.Union[complex, IntStrFloat]",
    }


def test_optional(union_aliases):
    assert repr(Union[int, None]) == "typing.Optional[int]"
    assert repr(Union[None, int]) == "typing.Optional[int]"


def test_double_registration(union_aliases):
    # We can register with the same alias, but not with a different alias.

    set_union_alias(Union[int, str], alias="IntStr")
    set_union_alias(Union[int, str], alias="IntStr")  # This is OK.
    with pytest.raises(RuntimeError, match=r"already has alias"):
        set_union_alias(Union[int, str], alias="OtherIntStr")

    set_union_alias(int, alias="MyInt")
    set_union_alias(int, alias="MyInt")  # This is OK.
    with pytest.raises(RuntimeError, match=r"already has alias"):
        set_union_alias(int, alias="MyOtherInt")
