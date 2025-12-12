import pytest

import plum


def test_overload(dispatch: plum.Dispatcher) -> None:
    @plum.overload
    def f(x: int) -> int:
        return x

    @plum.overload
    def f(x: str) -> str:
        return x

    @dispatch
    def f(x):
        pass

    assert f(1) == 1
    assert f("1") == "1"
    with pytest.raises(plum.NotFoundLookupError):
        f(1.0)
