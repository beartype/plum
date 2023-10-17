import abc
import sys
import typing

try:
    from typing import Literal
except ImportError:

    class LiteralMeta(type):
        """A simple proxy for :class:`typing.Literal`."""

        def __getitem__(self, item):
            return self

    class Literal(metaclass=LiteralMeta):
        __faithful__ = False


import pytest

from plum.type import (
    ModuleType,
    PromisedType,
    ResolvableType,
    _is_hint,
    is_faithful,
    resolve_type_hint,
    type_mapping,
)
from plum.util import Callable


def test_resolvabletype():
    t = ResolvableType("int")
    assert t.__name__ == "int"
    assert t.resolve() is t
    assert t.deliver(int) is t
    assert t.resolve() is int


def test_promisedtype():
    t = PromisedType("int")
    assert t.__name__ == "PromisedType[int]"
    assert t.resolve() is t
    assert t.deliver(int) is t
    assert t.resolve() is int


def test_promsedtype_default_name():
    t = PromisedType()
    assert t.__name__ == "PromisedType[SomeType]"


@pytest.mark.parametrize(
    "module, name, type",
    [
        ("typing", "Union", typing.Union),
        ("__builtin__", "int", int),
        ("__builtins__", "int", int),
        ("builtins", "int", int),
    ],
)
def test_moduletype(module, name, type):
    t = ModuleType(module, name)
    assert t.__name__ == f"ModuleType[{module}.{name}]"
    assert t.resolve() is t
    assert t.retrieve()
    assert t.resolve() is type

    t = ModuleType("<nonexistent>", "f")
    assert not t.retrieve()


def test_is_hint():
    assert not _is_hint(int)
    assert _is_hint(typing.Union[int, float])
    assert _is_hint(Callable)


@pytest.mark.skipif(
    sys.version_info < (3, 9),
    reason="Requires Python 3.9 or higher.",
)
def test_is_hint_subscripted_builtins():
    assert _is_hint(tuple[int])


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Requires Python 3.10 or higher.",
)
def test_is_hint_new_union():
    assert int | float


def test_type_mapping():
    assert resolve_type_hint(int) is int
    try:
        type_mapping[int] = float
        assert resolve_type_hint(int) is float
    finally:
        del type_mapping[int]


@pytest.mark.parametrize(
    "pseudo_int",
    [
        PromisedType("int").deliver(int),
        # We deliver a promised type to a promised type, which means that the
        # resolution must resolve deliveries.
        PromisedType("int").deliver(PromisedType("int").deliver(int)),
        ModuleType("builtins", "int"),
    ],
)
def test_resolve_type_hint(pseudo_int):
    # Test leaves.
    assert resolve_type_hint(None) is None
    assert resolve_type_hint(Ellipsis) is Ellipsis
    assert resolve_type_hint(int) is int
    assert resolve_type_hint(typing.Any) is typing.Any
    assert resolve_type_hint(Callable) is Callable

    # Test composition.
    assert resolve_type_hint((pseudo_int, pseudo_int)) == (int, int)
    assert resolve_type_hint([pseudo_int, pseudo_int]) == [int, int]

    def _combo1(fake, real):
        return typing.Union[fake, float], typing.Union[real, float]

    def _combo2(fake, real):
        return Callable[[fake, float], fake], Callable[[real, float], real]

    def _combo3(fake, real):
        return _combo2(*_combo1(fake, real))

    def _combo4(fake, real):
        return _combo3(*_combo2(*_combo1(fake, real)))

    for combo in [_combo1, _combo2, _combo3, _combo4]:
        fake, real = combo(pseudo_int, int)
        assert resolve_type_hint(fake) == real

    class A:
        pass

    # Test warning.
    a = A()
    with pytest.warns(Warning, match=r"(?i)could not resolve the type hint"):
        assert resolve_type_hint(a) is a


def test_resolve_type_hint_moduletype_recursion():
    t = ModuleType("<nonexistent>", "f")
    assert resolve_type_hint(t) == t


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Requires Python 3.10 or higher.",
)
def test_resolve_type_hint_new_union():
    assert resolve_type_hint(float | int) == float | int


def test_is_faithful():
    # Example of a not faithful type.
    t_nf = Callable[[int], int]

    # Test leaves.
    assert is_faithful(typing.Any)
    assert is_faithful(Callable)
    assert is_faithful(None)
    assert is_faithful(Ellipsis)

    # Test composition.
    # Lists:
    assert is_faithful([int, float])
    assert not is_faithful([int, t_nf])
    # Tuples:
    assert is_faithful((int, float))
    assert not is_faithful((int, t_nf))
    # `Callable`:
    assert not is_faithful(Callable[[int], int])
    # `Union`:
    assert is_faithful(typing.Union[int, float])
    assert not is_faithful(typing.Union[int, t_nf])

    # Test warning.
    with pytest.warns(
        Warning, match=r"(?i)could not determine whether `(.*)` is faithful or not"
    ):
        assert not is_faithful(1)


def test_is_faithful_custom_metaclass():
    class A:
        pass

    class BMeta(type):
        def __instancecheck__(self, cls):
            pass

    class B(metaclass=BMeta):
        pass

    assert is_faithful(A)
    assert not is_faithful(B)


def test_is_faithful_abcmeta():
    class A(metaclass=abc.ABCMeta):  # noqa: B024
        pass

    assert is_faithful(A)


def test_is_faithful_dunder():
    """Check that `__faithful__` works."""

    class UnfaithfulClass:
        __faithful__ = False

    class FaithfulClass:
        __faithful__ = True

    assert not is_faithful(UnfaithfulClass)
    assert is_faithful(FaithfulClass)


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Requires Python 3.10 or higher.",
)
def test_is_faithful_new_union():
    assert not is_faithful(int | float)


def test_is_faithful_literal(recwarn):
    assert not is_faithful(Literal[1])
    # There should be no warnings.
    assert len(recwarn) == 0
