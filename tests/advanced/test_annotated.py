import sys

if sys.version_info < (3, 9):
    from typing_extensions import Annotated
else:
    from typing import Annotated

import pytest
from beartype.vale import Is

from plum import Dispatcher, NotFoundLookupError


def test_simple_annotated():
    dispatch = Dispatcher()

    positive_int = Annotated[int, Is[lambda value: value > 0]]

    @dispatch
    def f(x: positive_int):
        return x

    assert f(1) == 1

    with pytest.raises(NotFoundLookupError):
        f("my string")

    with pytest.raises(NotFoundLookupError):
        f(-1)
