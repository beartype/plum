import pytest

from plum import NotFoundLookupError
from plum.overload import dispatch, overload


@overload
def f(x: int) -> int:
    return x


@overload
def f(x: str) -> str:
    return x


@dispatch
def f(x):
    pass


def test_overload() -> None:
    assert f(1) == 1
    assert f("1") == "1"
    with pytest.raises(NotFoundLookupError):
        f(1.0)  # type: ignore
