import abc
import enum
import sys
import typing
from numbers import Number
from typing import Annotated, Any, Literal, Union

import pytest

from plum._bear import is_bearable
from plum._type import (
    _ARG_KEYS,
    KeyPart,
    ModuleType,
    PromisedType,
    ResolvableType,
    TypeHintWrapper,
    _cache_spec,
    _is_hint,
    _substitute_any,
    _type_hint_eq,
    _type_hint_le,
    _wrap_type_hint,
    cache_key,
    is_cacheable,
    is_faithful,
    resolve_type_hint,
    type_mapping,
)
from plum._util import Callable

skip_if_less_than_py310 = pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="Requires Python 3.10 or higher.",
)


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


def test_moduletype_allow_fail():
    t_not_allowed = ModuleType("__builtin__", "nonexisting")
    t_allowed = ModuleType("__builtin__", "nonexisting", allow_fail=True)

    with pytest.raises(AttributeError):
        t_not_allowed.retrieve()

    assert not t_allowed.retrieve()


def test_moduletype_condition():
    store = {"condition": False}
    t = ModuleType("builtins", "int", condition=lambda: store["condition"])
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

    t = ModuleType("mymodule", "A", faithful=False)
    assert t.retrieve()
    assert t.retrieve()  # Doing it twice is OK.
    assert t.resolve() is module.A
    assert not t.resolve().__faithful__

    t = ModuleType("mymodule", "A", faithful=True)
    with pytest.raises(TypeError, match="`A.__faithful__` is already set"):
        t.retrieve()

    # Test retrieving a type and setting `__faithful__` to `False`.
    t = ModuleType("mymodule", "B", faithful=False)
    assert t.retrieve()
    assert t.retrieve()  # Doing it twice is OK.
    assert t.resolve() is module.B
    assert not t.resolve().__faithful__

    # Test retrieving a type and setting `__faithful__` to `True`.
    t = ModuleType("mymodule", "C", faithful=True)
    assert t.retrieve()
    assert t.retrieve()  # Doing it twice is OK.
    assert t.resolve() is module.C
    assert t.resolve().__faithful__


def test_is_hint():
    assert not _is_hint(int)
    assert _is_hint(typing.Union[int, float])  # noqa: UP007
    assert _is_hint(int | float)
    assert _is_hint(Callable)


@skip_if_less_than_py310
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

    def _combo0(fake, real):
        return fake | float, real | float

    def _combo1(fake, real):
        return typing.Union[fake, float], typing.Union[real, float]  # noqa: UP007

    def _combo2(fake, real):
        return Callable[[fake, float], fake], Callable[[real, float], real]

    def _combo3(fake, real):
        return _combo2(*_combo1(fake, real))

    def _combo4(fake, real):
        return _combo3(*_combo2(*_combo1(fake, real)))

    for combo in [_combo0, _combo1, _combo2, _combo3, _combo4]:
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


@skip_if_less_than_py310
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
    assert is_faithful(typing.Union[int, float])  # noqa: UP007
    assert not is_faithful(typing.Union[int, t_nf])  # noqa: UP007
    assert is_faithful(int | float)  # noqa: UP007
    assert not is_faithful(int | t_nf)

    # Test warning.
    with pytest.warns(
        Warning,
        match=r"(?i)could not determine whether `(.*)` is faithful or cacheable",
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


@skip_if_less_than_py310
def test_is_faithful_new_union():
    assert is_faithful(int | float)


def test_is_faithful_literal(recwarn):
    assert not is_faithful(Literal[1])
    # There should be no warnings.
    assert len(recwarn) == 0


def test_type_hint_eq():
    """Regression test for https://github.com/beartype/plum/issues/295.

    `Any` must compare equal only to `Any`, never to an unrelated concrete type.
    """
    assert _type_hint_eq(Any, Any)
    assert not _type_hint_eq(Any, int)
    assert not _type_hint_eq(int, Any)
    assert not _type_hint_eq(Any, object)
    assert not _type_hint_eq(object, Any)

    assert _type_hint_eq(int, int)
    assert not _type_hint_eq(int, float)

    # Equivalent but not identical types should still compare equal.
    assert _type_hint_eq(Union[int, bool], int)  # noqa: UP007


def test_type_hint_le():
    """Regression test for https://github.com/beartype/plum/issues/295.

    `Any` must stay the unique least-specific type - a subhint of nothing but
    itself, even though everything else remains a subhint of it.
    """
    assert _type_hint_le(Any, Any)
    assert not _type_hint_le(Any, int)
    assert not _type_hint_le(Any, object)

    # Ordinary subhint relationships still work as before.
    assert _type_hint_le(int, Any)
    assert _type_hint_le(int, int)
    assert _type_hint_le(int, Number)
    assert not _type_hint_le(Number, int)


def test_type_hint_eq_nested_any():
    """`Any` nested inside a parameterised hint must not collide either.

    `beartype>=0.23` collapses `list[Any]` onto `list[int]` exactly as it collapses
    `Any` onto `int`, so the rewrite in `_substitute_nested_any` has to reach every
    level, not just the root.
    """
    assert not _type_hint_eq(list[Any], list[int])
    assert not _type_hint_eq(dict[str, Any], dict[str, int])
    assert not _type_hint_eq(list[list[Any]], list[list[int]])
    assert not _type_hint_eq(tuple[int, Any], tuple[int, str])

    # A nested `Any` stays the least specific argument, as at the root.
    assert _type_hint_le(list[int], list[Any])
    assert not _type_hint_le(list[Any], list[int])

    # Identical nestings still compare equal, and unrelated ones still do not.
    assert _type_hint_eq(list[Any], list[Any])
    assert _type_hint_eq(list[int], list[int])
    assert not _type_hint_eq(list[Any], dict[str, Any])


def test_substitute_any_rebuilds_hints():
    """Every hint form plum may hold must survive the rewrite unchanged in shape."""
    # `Literal`'s arguments are values, not hints, so they must be left alone.
    assert _substitute_any(Literal["a", "b"]) == Literal["a", "b"]
    # Hints without an `Any` come back untouched.
    assert _substitute_any(list[int]) == list[int]
    assert _substitute_any(int) is int

    assert _substitute_any(Any) is object
    assert _substitute_any(list[Any]) == list[object]
    assert _substitute_any(dict[str, Any]) == dict[str, object]
    assert _substitute_any(tuple[Any, ...]) == tuple[object, ...]
    assert _substitute_any(list[list[Any]]) == list[list[object]]
    assert _substitute_any(Union[int, Any]) == Union[int, object]  # noqa: UP007
    assert _substitute_any(int | Any) == int | object
    # `Callable` stores its parameters in a list.
    assert _substitute_any(Callable[[int, Any], Any]) == Callable[[int, object], object]
    assert _substitute_any(Callable[..., Any]) == Callable[..., object]


def test_wrap_type_hint_unhashable_hint():
    """An unhashable hint cannot be cached but must still be wrapped."""
    hint = Annotated[list[Any], {"a": 1}]
    assert _wrap_type_hint(hint) == TypeHintWrapper(Annotated[list[object], {"a": 1}])
    # A hashable one is cached, which is the point of the helper.
    assert _wrap_type_hint(list[Any]) is _wrap_type_hint(list[Any])


def test_is_cacheable_and_faithful_split():
    class SomeClass:
        pass

    # Faithful ⇒ cacheable, and type-keyed.
    assert is_faithful(int) and is_cacheable(int)
    assert is_faithful(typing.Any) and is_cacheable(typing.Any)
    assert is_faithful(type) and is_cacheable(type)  # bare, unsubscripted
    assert is_faithful(typing.Union[int, str])  # noqa: UP007

    # type[X]: cacheable but NOT faithful.
    assert not is_faithful(type[int])
    assert is_cacheable(type[int])
    assert not is_faithful(type[SomeClass])
    assert is_cacheable(type[SomeClass])
    assert not is_faithful(typing.Type[int])  # noqa: UP006
    assert is_cacheable(typing.Type[int])  # noqa: UP006
    assert is_cacheable(typing.Union[type[int], str])  # noqa: UP007

    # Literal: cacheable but NOT faithful.
    assert not is_faithful(typing.Literal[1])
    assert is_cacheable(typing.Literal[1])

    # Genuinely uncacheable.
    assert not is_cacheable(list[int])
    assert not is_cacheable(list[type[int]])


def test_empty_tuple_hint_is_not_faithful():
    """`tuple[()]` matches on the *length* of the value, not its type.

    `typing.get_args(tuple[()])` is `()`, which used to send it down the
    "unsubscripted hints are faithful" fast path. `()` matches it and `(1,)` does
    not, so the classification must be uncacheable.
    """
    assert is_bearable((), tuple[()])
    assert not is_bearable((1,), tuple[()])

    assert not is_faithful(tuple[()])
    assert not is_cacheable(tuple[()])
    assert not is_faithful(typing.Tuple[()])  # noqa: UP006
    assert not is_cacheable(typing.Tuple[()])  # noqa: UP006
    # Nested in a union, the whole hint goes with it.
    assert not is_cacheable(typing.Union[tuple[()], int])  # noqa: UP007

    # Other unsubscripted hints are unaffected. In particular bare `typing.Tuple`
    # shares the `tuple` origin but means "any tuple", which depends only on the
    # type, so it must stay faithful rather than be lumped in with `tuple[()]`.
    assert is_faithful(typing.Tuple)  # noqa: UP006
    assert is_cacheable(typing.Tuple)  # noqa: UP006
    assert is_faithful(tuple)
    assert is_faithful(typing.List)  # noqa: UP006
    assert is_faithful(typing.Any)


def test_cache_key_contract():
    """Equal keys imply the same match result, so anything that dispatches
    differently must get a distinct key. The width and order of the slots are an
    implementation detail and deliberately not asserted here.
    """

    class SomeClass:
        pass

    # Non-classes keyed on their type and value.
    assert cache_key(1) == (int, None, 1)
    assert cache_key("x") == (str, None, "x")
    # Classes keyed on identity; distinct from a same-type instance key.
    assert cache_key(int) == cache_key(int)
    assert cache_key(int) != cache_key(str)
    assert cache_key(int) != cache_key(1)
    assert cache_key(SomeClass) == cache_key(SomeClass)


def test_cache_key_survives_pathological_metaclasses():
    # Unhashable class (metaclass defines __eq__, nulls __hash__): key must not raise.
    class MetaUnhashable(type):
        def __eq__(cls, other):
            return cls is other

    class Unhashable(metaclass=MetaUnhashable):
        pass

    d = {cache_key(Unhashable): "ok"}
    assert d[cache_key(Unhashable)] == "ok"

    # Lying equality + colliding hash: distinct classes must not collide in the key.
    class MetaLie(type):
        def __eq__(cls, other):
            return True

        def __hash__(cls):
            return 7

    class A(int, metaclass=MetaLie):
        pass

    class B(metaclass=MetaLie):
        pass

    assert cache_key(A) != cache_key(B)
    assert {cache_key(A): 1}.get(cache_key(B)) is None


def test_public_api_exports():
    import plum

    assert plum.is_cacheable(int) is True
    assert plum.is_cacheable(list[int]) is False
    assert plum.cache_key(1)[0] is int
    assert "is_cacheable" in plum.__all__
    assert "cache_key" in plum.__all__


def test_is_cacheable_literal():
    """`Literal` is cacheable (via the value key part) but not faithful."""
    assert not is_faithful(Literal[1])
    assert is_cacheable(Literal[1])
    assert is_cacheable(Literal[1, 2])
    assert is_cacheable(Literal["a", None])
    # Unions and containers combine as usual.
    assert is_cacheable(typing.Union[Literal[1], str])  # noqa: UP007
    assert is_cacheable(typing.Union[Literal[1], type[int]])  # noqa: UP007
    assert not is_cacheable(list[Literal[1]])


def test_cache_key_value_part_is_opt_in():
    """Only a resolver that asks for `VALUE` pays for the value slot."""
    identity_only = frozenset({KeyPart.IDENTITY})
    value_only = frozenset({KeyPart.VALUE})

    # A `type[X]`-only resolver's key is unchanged: `(type(x), identity(x))`.
    assert cache_key(1, spec=identity_only) == (int, None)
    assert len(cache_key(int, spec=identity_only)) == 2

    # A `Literal`-only resolver captures the value and nothing else.
    assert cache_key(1, spec=value_only) == (int, 1)
    assert cache_key(2, spec=value_only) == (int, 2)
    assert cache_key(1, spec=value_only) != cache_key(2, spec=value_only)
    # `True` and `1` are equal but not interchangeable for `Literal`: the type slot
    # keeps them apart.
    assert cache_key(True, spec=value_only) != cache_key(1, spec=value_only)
    # A value that can never match any `Literal` gets an empty slot.
    assert cache_key(1.5, spec=value_only) == (float, None)
    assert cache_key([1], spec=value_only) == (list, None)


def test_cache_key_value_covers_literal_matching_subclasses():
    """Subclass instances match `Literal`s, so their value must be captured."""
    value_only = frozenset({KeyPart.VALUE})

    class MyInt(int):
        pass

    assert is_bearable(MyInt(1), Literal[1])
    assert not is_bearable(MyInt(2), Literal[1])
    assert cache_key(MyInt(1), spec=value_only) != cache_key(MyInt(2), spec=value_only)

    class MyEnum(enum.IntEnum):
        A = 1
        B = 2

    assert is_bearable(MyEnum.A, Literal[1])
    assert cache_key(MyEnum.A, spec=value_only) != cache_key(MyEnum.B, spec=value_only)


def test_cache_key_value_survives_unhashable_values():
    """An unhashable argument must not make the key raise."""
    value_only = frozenset({KeyPart.VALUE})

    class Unhashable(str):
        def __eq__(self, other):
            return str(self) == str(other)

        __hash__ = None  # type: ignore[assignment]

    a, b = Unhashable("a"), Unhashable("b")
    assert is_bearable(a, Literal["a"])
    assert not is_bearable(b, Literal["a"])

    d = {cache_key(a, spec=value_only): 1, cache_key(b, spec=value_only): 2}
    assert len(d) == 2
    assert d[cache_key(a, spec=value_only)] == 1

    # Plain unhashable values are fine too.
    hash(cache_key([1], spec=value_only))


def test_arg_keys_agree_with_cache_key():
    """`_ARG_KEYS` is a hot-path specialisation of `cache_key`: keep them in sync."""
    from itertools import chain, combinations

    subsets = [
        frozenset(s)
        for s in chain.from_iterable(
            combinations(KeyPart, r) for r in range(len(KeyPart) + 1)
        )
    ]
    assert set(_ARG_KEYS) == set(subsets)

    class SomeClass:
        pass

    values = [1, True, "x", b"x", None, 1.5, [1], SomeClass, int, SomeClass()]
    for spec in subsets:
        for x in values:
            expected = cache_key(x, spec=spec)
            actual = _ARG_KEYS[spec](x)
            if spec:
                assert actual == expected, (spec, x)
            else:
                # The faithful specialisation is plain `type`, not a 1-tuple.
                assert (actual,) == expected, (spec, x)


def test_cache_spec_of_an_array_like_hint():
    """Classification must not evaluate a hint's truthiness.

    `x == Ellipsis` on a `numpy` array returns an array, whose `bool()` raises, so
    an array reaching the classifier used to blow up rather than be reported
    uncacheable.
    """
    np = pytest.importorskip("numpy")

    with pytest.warns(UserWarning, match="faithful or cacheable"):
        assert _cache_spec(np.array([1, 2, 3])) is None

    # The two values the branch actually exists for still classify as faithful.
    assert _cache_spec(None) == frozenset()
    assert _cache_spec(Ellipsis) == frozenset()


def test_cache_specs_are_interned():
    # Only `2 ** len(KeyPart)` specs exist, so every signature and resolver must
    # share one instance rather than hold a private 216-byte copy.
    from plum._type import _canonical, _combine

    specs = [_combine((int, float)), _combine((str,)), _combine((type[int], int))]
    assert specs[0] is specs[1] is _combine((bool,))
    assert specs[2] is _combine((type[str],))
    assert _canonical(frozenset(specs[2])) is specs[2]
