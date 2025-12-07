from typing import Annotated

import pytest

from beartype.vale import Is

import plum


def test_simple_annotated(dispatch: plum.Dispatcher):
    positive_int = Annotated[int, Is[lambda value: value > 0]]

    @dispatch
    def f(x: positive_int):
        return x

    assert f(1) == 1

    with pytest.raises(plum.NotFoundLookupError):
        f("my string")

    with pytest.raises(plum.NotFoundLookupError):
        f(-1)
