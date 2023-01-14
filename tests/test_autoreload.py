import pytest

from plum import Dispatcher
from plum import autoreload as ar
from plum.function import NotFoundLookupError


def test_autoreload_activate_deactivate():
    # We shouldn't be able to deactivate before activation.
    with pytest.raises(
        RuntimeError,
        match=r"(?i)plum autoreload module was never activated",
    ):
        ar.deactivate()

    ar.activate()

    from IPython.extensions import autoreload as iar

    # Check that it is activated.
    assert ar._update_instances_original is not None
    assert ar._update_instances_original.__module__ == "IPython.extensions.autoreload"
    assert iar.update_instances.__module__ == "plum.autoreload"

    ar.deactivate()

    # Check that it is deactivated.
    assert ar._update_instances_original.__module__ == "IPython.extensions.autoreload"
    assert iar.update_instances.__module__ == "IPython.extensions.autoreload"
    assert iar.update_instances == ar._update_instances_original


def test_autoreload_correctness():
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

    ar._update_instances(A1, A2)

    assert test(A2()) == 1

    with pytest.raises(NotFoundLookupError):
        test(A1())

    assert isinstance(a1, A2)
