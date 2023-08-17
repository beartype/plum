import pytest

from plum import Dispatcher, NotFoundLookupError, overload

dispatch = Dispatcher()


@overload
def f(x: int) -> int:  # E: pyright(marked as overload)
    return x


@overload
def f(x: str) -> str:  # E: pyright(marked as overload)
    return x


@dispatch
def f(x):  # E: pyright(overloaded implementation is not consistent)
    pass


def test_overload() -> None:
    assert f(1) == 1
    assert f("1") == "1"
    with pytest.raises(NotFoundLookupError):
        # E: pyright(argument of type "float" cannot be assigned to parameter "x")
        # E: mypy(no overload variant of "f" matches argument type "float")
        f(1.0)
