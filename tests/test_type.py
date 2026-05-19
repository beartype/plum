import abc
import sys
import types
import typing
from typing import Literal, get_args, get_origin

import pytest

import plum
from plum._type import ResolvableType, _is_hint, type_mapping

skip_if_less_than_py310 = pytest.mark.skipif(
    sys.version_info < (3, 10), reason="Requires Python 3.10 or higher."
)


def test_resolvabletype():
    t = ResolvableType("int")
    assert t.__name__ == "int"
    assert t.resolve() is t
    assert t.deliver(int) is t
    assert t.resolve() is int


def test_promisedtype():
    t = plum.PromisedType("int")
    assert t.__name__ == "PromisedType[int]"
    assert t.resolve() is t
    assert t.deliver(int) is t
    assert t.resolve() is int


def test_promsedtype_default_name():
    t = plum.PromisedType()
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
    t = plum.ModuleType(module, name)
    assert t.__name__ == f"ModuleType[{module}.{name}]"
    assert t.resolve() is t
    assert t.retrieve()
    assert t.resolve() is type

    t = plum.ModuleType("<nonexistent>", "f")
    assert not t.retrieve()


def test_moduletype_allow_fail():
    t_not_allowed = plum.ModuleType("__builtin__", "nonexisting")
    t_allowed = plum.ModuleType("__builtin__", "nonexisting", allow_fail=True)

    with pytest.raises(AttributeError):
        t_not_allowed.retrieve()

    assert not t_allowed.retrieve()


def test_moduletype_condition():
    store = {"condition": False}
    t = plum.ModuleType("builtins", "int", condition=lambda: store["condition"])
    assert not t.retrieve()
    store["condition"] = True
    assert t.retrieve()


def test_moduletype_faithful(monkeypatch):
    class Module:
        class A:
            __faithful__ = False

        class B:
            pass

        class C:
            pass

    module = Module()
    monkeypatch.setitem(sys.modules, "mymodule", module)

    # Test retrieving a type with `__faithful__` already set.

    t = plum.ModuleType("mymodule", "A", faithful=False)
    assert t.retrieve()
    assert t.retrieve()  # Doing it twice is OK.
    assert t.resolve() is module.A
    assert not t.resolve().__faithful__

    t = plum.ModuleType("mymodule", "A", faithful=True)
    with pytest.raises(TypeError, match="`A.__faithful__` is already set"):
        t.retrieve()

    # Test retrieving a type and setting `__faithful__` to `False`.
    t = plum.ModuleType("mymodule", "B", faithful=False)
    assert t.retrieve()
    assert t.retrieve()  # Doing it twice is OK.
    assert t.resolve() is module.B
    assert not t.resolve().__faithful__

    # Test retrieving a type and setting `__faithful__` to `True`.
    t = plum.ModuleType("mymodule", "C", faithful=True)
    assert t.retrieve()
    assert t.retrieve()  # Doing it twice is OK.
    assert t.resolve() is module.C
    assert t.resolve().__faithful__


def test_is_hint():
    assert not _is_hint(int)
    assert _is_hint(typing.Union[int, float])  # noqa: UP007
    assert _is_hint(int | float)
    assert _is_hint(plum.Callable)


@skip_if_less_than_py310
def test_is_hint_new_union():
    assert int | float


def test_type_mapping():
    assert plum.resolve_type_hint(int) is int
    try:
        type_mapping[int] = float
        assert plum.resolve_type_hint(int) is float
    finally:
        del type_mapping[int]


@pytest.mark.parametrize(
    "pseudo_int",
    [
        plum.PromisedType("int").deliver(int),
        # We deliver a promised type to a promised type, which means that the
        # resolution must resolve deliveries.
        plum.PromisedType("int").deliver(plum.PromisedType("int").deliver(int)),
        plum.ModuleType("builtins", "int"),
    ],
)
def test_resolve_type_hint(pseudo_int):
    # Test leaves.
    assert plum.resolve_type_hint(None) is None
    assert plum.resolve_type_hint(Ellipsis) is Ellipsis
    assert plum.resolve_type_hint(int) is int
    assert plum.resolve_type_hint(typing.Any) is typing.Any
    assert plum.resolve_type_hint(plum.Callable) is plum.Callable

    # Test composition.
    assert plum.resolve_type_hint((pseudo_int, pseudo_int)) == (int, int)
    assert plum.resolve_type_hint([pseudo_int, pseudo_int]) == [int, int]

    def _combo0(fake, real):
        return fake | float, real | float

    def _combo1(fake, real):
        return typing.Union[fake, float], typing.Union[real, float]  # noqa: UP007

    def _combo2(fake, real):
        return plum.Callable[[fake, float], fake], plum.Callable[[real, float], real]

    def _combo3(fake, real):
        return _combo2(*_combo1(fake, real))

    def _combo4(fake, real):
        return _combo3(*_combo2(*_combo1(fake, real)))

    for combo in [_combo0, _combo1, _combo2, _combo3, _combo4]:
        fake, real = combo(pseudo_int, int)
        assert plum.resolve_type_hint(fake) == real

    class A:
        pass

    # Test warning.
    a = A()
    with pytest.warns(Warning, match=r"(?i)could not resolve the type hint"):
        assert plum.resolve_type_hint(a) is a


def test_resolve_type_hint_moduletype_recursion():
    t = plum.ModuleType("<nonexistent>", "f")
    assert plum.resolve_type_hint(t) == t


@skip_if_less_than_py310
def test_resolve_type_hint_new_union():
    assert plum.resolve_type_hint(float | int) == float | int


def test_resolve_type_hint_user_defined_generic_with_args():
    T = typing.TypeVar("T")

    class Box(typing.Generic[T]):
        pass

    # Box[int].__module__ is this test module, not a stdlib module, so
    # _is_hint(Box[int]) returns False.  The elif-branch for user-defined
    # parameterised generics handles it by recursing into the args and
    # reconstructing the subscripted type.
    result = plum.resolve_type_hint(Box[int])
    assert result == Box[int]


def test_resolve_type_hint_generic_no_args_returns_unchanged():
    """resolve_type_hint returns x unchanged when get_origin is set but args are empty.

    ``types.GenericAlias(Widget, ())`` creates an alias whose ``get_origin`` is
    the user-defined ``Widget`` class (non-None, so ``_is_hint`` is False) but
    whose ``get_args`` is an empty tuple.  The no-args fallback path in the
    ``elif get_origin(x) is not None:`` branch must return ``x`` unchanged.
    """

    class Widget:
        pass

    alias = types.GenericAlias(Widget, ())
    assert get_origin(alias) is Widget  # confirm setup
    assert get_args(alias) == ()

    result = plum.resolve_type_hint(alias)
    assert result is alias  # returned unchanged — no-args fallback

    # Example of a not faithful type.
    t_nf = plum.Callable[[int], int]

    # Test leaves.
    assert plum.is_faithful(typing.Any)
    assert plum.is_faithful(plum.Callable)
    assert plum.is_faithful(None)
    assert plum.is_faithful(Ellipsis)

    # Test composition.
    # Lists:
    assert plum.is_faithful([int, float])
    assert not plum.is_faithful([int, t_nf])
    # Tuples:
    assert plum.is_faithful((int, float))
    assert not plum.is_faithful((int, t_nf))
    # `Callable`:
    assert not plum.is_faithful(plum.Callable[[int], int])
    # `Union`:
    assert plum.is_faithful(typing.Union[int, float])  # noqa: UP007
    assert not plum.is_faithful(typing.Union[int, t_nf])  # noqa: UP007
    assert plum.is_faithful(int | float)  # noqa: UP007
    assert not plum.is_faithful(int | t_nf)

    # Test warning.
    with pytest.warns(
        Warning, match=r"(?i)could not determine whether `(.*)` is faithful or not"
    ):
        assert not plum.is_faithful(1)


def test_is_faithful_custom_metaclass():
    class A:
        pass

    class BMeta(type):
        def __instancecheck__(self, cls):
            pass

    class B(metaclass=BMeta):
        pass

    assert plum.is_faithful(A)
    assert not plum.is_faithful(B)


def test_is_faithful_abcmeta():
    class A(metaclass=abc.ABCMeta):  # noqa: B024
        pass

    assert plum.is_faithful(A)


def test_is_faithful_dunder():
    """Check that `__faithful__` works."""

    class UnfaithfulClass:
        __faithful__ = False

    class FaithfulClass:
        __faithful__ = True

    assert not plum.is_faithful(UnfaithfulClass)
    assert plum.is_faithful(FaithfulClass)


@skip_if_less_than_py310
def test_is_faithful_new_union():
    assert plum.is_faithful(int | float)


def test_is_faithful_literal(recwarn):
    assert not plum.is_faithful(Literal[1])
    # There should be no warnings.
    assert len(recwarn) == 0
