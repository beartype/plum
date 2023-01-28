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
        ar.deactivate_autoreload()

    ar.activate_autoreload()

    from IPython.extensions import autoreload as iar

    # Check that it is activated.
    assert ar._update_instances_original is not None
    assert ar._update_instances_original.__module__ == "IPython.extensions.autoreload"
    assert iar.update_instances.__module__ == "plum.autoreload"

    ar.deactivate_autoreload()

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

    class A3:
        pass

    @dispatch
    def test(x: A1):
        return 1

    a = A1()

    assert isinstance(a, A1)
    assert test(a) == 1

    assert test(A1()) == 1
    with pytest.raises(NotFoundLookupError):
        test(A2())
    with pytest.raises(NotFoundLookupError):
        test(A3())

    ar._update_instances(A1, A2)

    assert isinstance(a, A2)
    assert test(a) == 1

    with pytest.raises(NotFoundLookupError):
        test(A1())
    assert test(A2()) == 1
    with pytest.raises(NotFoundLookupError):
        test(A3())

    ar._update_instances(A2, A3)

    assert isinstance(a, A3)
    assert test(a) == 1

    with pytest.raises(NotFoundLookupError):
        test(A1())
    with pytest.raises(NotFoundLookupError):
        test(A2())
    assert test(A3()) == 1
