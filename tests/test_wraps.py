import functools

from plum._wraps import update_wrapper


class _W:
    """A bare object for `update_wrapper` to write onto."""


def test_update_wrapper_matches_functools_wraps():
    """`update_wrapper` matches `functools.wraps`, except for `__type_params__`."""

    def target(x: int) -> str:
        """The docstring."""
        return "s"

    target.custom_attr = 42  # `functools.wraps` merges `__dict__`; so must we.

    reference, fast = _W(), _W()
    functools.wraps(target)(reference)
    update_wrapper(fast, target)

    # Annotations live on `__annotations__` before Python 3.14 and on `__annotate__`
    # from 3.14, so compare both, present or not.
    missing = object()
    for attr in (
        "__name__",
        "__qualname__",
        "__module__",
        "__doc__",
        "__annotations__",
        "__annotate__",
        "custom_attr",
    ):
        assert getattr(fast, attr, missing) == getattr(reference, attr, missing), attr
    assert fast.__wrapped__ is target is reference.__wrapped__


def test_update_wrapper_callable_object():
    """A callable object need not have `__qualname__` or `__dict__`."""

    class Slotted:
        __slots__ = ()
        __name__ = "slotted"
        __module__ = "somewhere"
        __doc__ = None

    wrapped, wrapper = Slotted(), _W()
    update_wrapper(wrapper, wrapped)
    assert wrapper.__qualname__ == "slotted"
    assert wrapper.__wrapped__ is wrapped
