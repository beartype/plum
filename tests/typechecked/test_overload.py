import pytest

from plum import Dispatcher, NotFoundLookupError, overload

dispatch = Dispatcher()


@overload
def f(x: int) -> int:
    return x


@overload
def f(x: str) -> str:
    return x


@dispatch
def f(x):  # E: pyright(overloaded implementation is not consistent)
    pass


def test_overload() -> None:
    assert f(1) == 1
    assert f("1") == "1"
    with pytest.raises(NotFoundLookupError):
        # E: pyright(argument of type "float" cannot be assigned to parameter "x")
        # E: pyright(no overloads for "f" match the provided arguments)
        # E: mypy(no overload variant of "f" matches argument type "float")
        f(1.0)
