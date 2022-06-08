import numpy as np
import pytest

from pathlib import Path

from plum import Dispatcher, autoreload as p_autoreload
from plum.function import NotFoundLookupError


def test_autoreload_activate_deactivate():
    p_autoreload.activate()

    assert p_autoreload._update_instances_original is not None
    assert (
        p_autoreload._update_instances_original.__module__
        == "IPython.extensions.autoreload"
    )

    from IPython.extensions import autoreload

    assert autoreload.update_instances.__module__ == "plum.autoreload"

    p_autoreload.deactivate()

    assert (
        p_autoreload._update_instances_original.__module__
        == "IPython.extensions.autoreload"
    )
    assert autoreload.update_instances.__module__ == "IPython.extensions.autoreload"
    assert autoreload.update_instances == p_autoreload._update_instances_original


def test_autoreload_works():
    dispatch = Dispatcher()

    class A1:
        pass

    class A2:
        pass

    @dispatch
    def test(x: A1):
        return 1

    assert test(A1()) == 1

    with pytest.raises(NotFoundLookupError):
        test(A2())

    a1 = A1()

    p_autoreload._update_instances(A1, A2)

    assert test(A2()) == 1

    with pytest.raises(NotFoundLookupError):
        test(A1())

    assert isinstance(a1, A2)
