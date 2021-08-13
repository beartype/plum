import pytest

from plum.resolvable import Promise, ResolutionError


def test_promise():
    p = Promise()

    # Check delivery process.
    with pytest.raises(ResolutionError):
        p.resolve()
    p.deliver(1)
    assert p.resolve() == 1

    # Check that we can deliver twice.
    p.deliver(2)
    assert p.resolve() == 2


def test_promise_repr():
    # Test contruction with object.
    p = Promise(1)
    assert repr(p) == "Promise(obj=1)"

    # Test contruction without object.
    p = Promise()
    assert repr(p) == "Promise()"

    class MockClass:
        pass

    # Test `__repr__` after delivery process.
    for T in [int, MockClass]:
        p = Promise()
        p.deliver(T)
        assert repr(T) in repr(p)
