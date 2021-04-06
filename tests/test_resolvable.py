import pytest

from plum.resolvable import Promise, ResolutionError


def test_promise():
    p = Promise()
    with pytest.raises(ResolutionError):
        p.resolve()
    p.deliver(1)
    assert p.resolve() == 1
