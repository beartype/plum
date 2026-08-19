import typing
import warnings
from numbers import Number
from typing import Union

import pytest

import plum
from plum import add_conversion_method, add_promotion_rule, conversion_method
from plum._promotion import _promotion_rule


class Num:
    pass


class Re(Num):
    pass


class Rat(Re):
    pass


def test_convert(convert):
    # Test basic conversion.
    assert convert(1.0, float) == 1.0
    assert convert(1.0, object) == 1.0
    with pytest.raises(TypeError):
        convert(1.0, int)

    # Test conversion with inheritance.
    r = Re()
    assert convert(r, Re) == r
    assert convert(r, Num) == r
    with pytest.raises(TypeError):
        convert(r, Rat)

    # Test `add_conversion_method`.
    add_conversion_method(float, int, lambda _: 2.0)
    assert convert(1.0, float) == 1.0
    assert convert(1.0, object) == 1.0
    assert convert(1.0, int) == 2.0

    # Test `conversion_method`.

    @conversion_method(Num, Rat)
    def num_to_fp(x):
        return 3.0

    assert convert(r, Re) == r
    assert convert(r, Num) == r
    assert convert(r, Rat) == 3.0

    # Test that `conversion_method` returns the function.
    assert num_to_fp(1) == 3.0


def test_convert_resolve_type_hints(convert):
    add_conversion_method(int, float, lambda x: 2.0)
    # The below calls will only work if the type hint is resolved.
    assert convert(1, plum.ModuleType("builtins", "float")) == 2.0
    # This tests the one in the fallback of `_convert`.
    assert convert(1, plum.ModuleType("builtins", "int")) == 1


def test_default_conversion_methods():
    # Conversion to `tuple`.
    assert plum.convert(1, tuple) == (1,)
    assert plum.convert((1,), tuple) == (1,)
    assert plum.convert(((1,),), tuple) == ((1,),)
    assert plum.convert([1], tuple) == (1,)
    assert plum.convert([(1,)], tuple) == ((1,),)

    # Conversion to `list`.
    assert plum.convert(1, list) == [1]
    assert plum.convert((1,), list) == [1]
    assert plum.convert(((1,),), list) == [(1,)]
    assert plum.convert([1], list) == [1]
    assert plum.convert([(1,)], list) == [(1,)]

    # Convert to `str`.
    assert plum.convert(b"test", str) == "test"


def test_promote(convert, promote):
    assert promote() == ()
    assert promote(1) == (1,)
    assert promote(1.0) == (1.0,)
    assert promote(1, 1) == (1, 1)
    assert promote(1.0, 1.0) == (1.0, 1.0)
    assert promote(1, 1, 1) == (1, 1, 1)
    assert promote(1.0, 1.0, 1.0) == (1.0, 1.0, 1.0)
    with pytest.raises(TypeError):
        promote(1, 1.0)
    with pytest.raises(TypeError):
        promote(1.0, 1)

    add_promotion_rule(int, float, float)

    with pytest.raises(TypeError):
        promote(1, 1.0)
    with pytest.raises(TypeError):
        promote(1.0, 1)

    add_conversion_method(int, float, lambda x: x + 1.0)

    assert promote(1, 1.0) == (2.0, 1.0)
    assert promote(1, 1, 1.0) == (2.0, 2.0, 1.0)
    assert promote(1.0, 1.0, 1) == (1.0, 1.0, 2.0)

    with pytest.raises(TypeError):
        promote(1, "1")
    with pytest.raises(TypeError):
        promote("1", 1)
    with pytest.raises(TypeError):
        promote(1.0, "1")
    with pytest.raises(TypeError):
        promote("1", 1.0)

    add_promotion_rule(str, int, float)
    add_promotion_rule(str, float, float)
    add_conversion_method(str, float, lambda x: "lel")

    assert promote(1, "1", 1.0) == (2.0, "lel", 1.0)
    assert promote("1", 1, 1.0) == ("lel", 2.0, 1.0)
    assert promote(1.0, "1", 1) == (1.0, "lel", 2.0)
    assert promote("1", 1.0, "1") == ("lel", 1.0, "lel")


@pytest.mark.parametrize("use_uniontype_union", [True, False])
def test_promote_union(convert, promote, use_uniontype_union):
    # Baseline promotion rules.
    add_promotion_rule(int, float, float)
    add_conversion_method(int, float, float)

    # Union promotion rules.
    if use_uniontype_union:
        add_promotion_rule(str, int | float, float)
        add_conversion_method(str, int | float, float)
    else:
        add_promotion_rule(str, Union[int, float], float)  # noqa: UP007
        add_conversion_method(str, Union[int, float], float)  # noqa: UP007

    assert promote(1, "1", "1") == (1.0, 1.0, 1.0)
    assert promote("1", 1, 1) == (1.0, 1.0, 1.0)
    assert promote(1.0, "1", 1) == (1.0, 1.0, 1.0)
    assert promote("1", 1.0, 1) == (1.0, 1.0, 1.0)


def test_promote_resolve_type_hints(convert, promote):
    t = _promotion_rule(
        plum.ModuleType("builtins", "int"),
        plum.ModuleType("numbers", "Number"),
    )
    assert t == Number
    t = _promotion_rule(
        plum.ModuleType("numbers", "Number"),
        plum.ModuleType("builtins", "int"),
    )
    assert t == Number


def test_inheritance(convert, promote):
    add_promotion_rule(Num, Rat, Num)
    add_promotion_rule(Num, Re, Num)
    add_promotion_rule(Rat, Re, Num)
    add_conversion_method(Rat, Num, lambda x: "Num from Rat")
    add_conversion_method(Re, Num, lambda x: "Num from Re")

    n = Num()
    assert promote(n, Rat()) == (n, "Num from Rat")
    assert promote(Re(), n) == ("Num from Re", n)
    assert promote(Re(), Rat()) == ("Num from Re", "Num from Rat")


def test_self_promotion(convert, promote):
    # This should trigger the "escape hatch" in `add_promotion_rule`. It also should not
    # trigger a redefinition warning. Explicitly test for that.
    with warnings.catch_warnings():
        warnings.simplefilter("error")

        # Simple case where types are identical:
        add_promotion_rule(Num, Num, Num)
        n = Num()
        assert promote(n, n) == (n, n)

        # Also test a more complicated scenario where the types are equal, but
        # not identical.
        t1 = typing.Union[int, float]  # noqa: UP007
        t2 = typing.Union[float, int]  # noqa: UP007
        assert t1 is not t2
        add_promotion_rule(t1, t2, str)
        add_conversion_method(int, str, str)
        add_conversion_method(float, str, str)
        assert promote(1, 1.0) == ("1", "1.0")

        # Also test a more complicated scenario where the types are equal, but not
        # identical.
        t1 = int | float
        t2 = float | int
        assert t1 is not t2
        add_promotion_rule(t1, t2, str)
        add_conversion_method(int, str, str)
        add_conversion_method(float, str, str)
        assert promote(1, 1.0) == ("1", "1.0")


# These pin the conditions that make the identity-conversion cache sound. They go
# through a dispatched function, because that - not `plum.convert` - reads the cache.


@pytest.fixture
def identity_conversions(convert):
    """`plum._function._identity_conversions`, cleared before and after the test."""
    plum._function._identity_conversions.clear()
    yield plum._function._identity_conversions
    plum._function._identity_conversions.clear()


def test_identity_conversion_is_recorded_and_read(
    identity_conversions, dispatch, monkeypatch
):
    """Once a pair is recorded, a repeat call must not reach `convert` at all."""

    class Base:
        pass

    @dispatch
    def f(x: Base) -> Base:
        return x

    obj = Base()
    assert f(obj) is obj
    assert identity_conversions[Base, Base] is True

    def explode(*args, **kw):
        raise AssertionError("convert was called despite a recorded identity")

    monkeypatch.setattr(plum._function, "_promised_convert", explode)
    assert f(obj) is obj


def test_conversion_methods_beat_recorded_identities(identity_conversions, dispatch):
    """A conversion method must win regardless of registration order.

    Registered *after* the pair is recorded as an identity, it must invalidate the
    entry; once it claims the pair, the pair must be recorded as not an identity.
    """

    class Base:
        pass

    class Sub(Base):
        pass

    @dispatch
    def f(x: Sub) -> Base:
        return x

    obj = Sub()
    assert f(obj) is obj
    assert identity_conversions[Sub, Base] is True

    add_conversion_method(Sub, Base, lambda _: "converted")
    assert f(obj) == "converted"
    # The re-analysed pair is no longer an identity, and the call keeps converting.
    assert identity_conversions[Sub, Base] is False
    assert f(obj) == "converted"


def test_unfaithful_targets_are_not_recorded(identity_conversions, dispatch):
    """`Gate` and `Literal` match on the value, so their pairs must never be recorded.

    Both `Thing` objects share the key `(Thing, Gate)`: recording the first call
    would make the second wrongly succeed.
    """

    class Meta(type):
        def __instancecheck__(cls, instance):
            return getattr(instance, "ok", False)

    class Gate(metaclass=Meta):
        pass

    class Thing:
        pass

    @dispatch
    def f(x: Thing) -> Gate:
        return x

    good, bad = Thing(), Thing()
    good.ok, bad.ok = True, False

    assert f(good) is good
    assert identity_conversions[(Thing, Gate)] is False
    with pytest.raises(TypeError):
        f(bad)

    @dispatch
    def g(x: int) -> typing.Literal[1]:
        return x

    assert g(1) == 1
    assert identity_conversions[(int, typing.Literal[1])] is False
    with pytest.raises(TypeError):
        g(2)


def test_failed_conversions_are_not_recorded(identity_conversions, dispatch):
    class Base:
        pass

    @dispatch
    def f(x: float) -> Base:
        return x

    with pytest.raises(TypeError):
        f(1.0)
    # A raising conversion never reaches the recording step, so nothing is stored.
    assert (float, Base) not in identity_conversions
    with pytest.raises(TypeError):
        f(1.0)


def test_recorded_identities_cleared_by_clear_all_cache(identity_conversions, dispatch):
    class Base:
        pass

    @dispatch
    def f(x: Base) -> Base:
        return x

    assert f(Base()) is not None
    assert identity_conversions
    plum.clear_all_cache()
    assert not identity_conversions


def test_union_targets_are_recorded(identity_conversions, dispatch):
    """A union of faithful types is faithful, so it is recordable as a whole."""

    class A:
        pass

    class B:
        pass

    @dispatch
    def f(x: A | float) -> A | B:
        return x

    a = A()
    assert f(a) is a
    assert identity_conversions[A, A | B] is True
    with pytest.raises(TypeError):
        f(1.0)


def test_recorded_identities_are_bounded(identity_conversions, dispatch, monkeypatch):
    """Recording stops at the limit instead of retaining types forever."""
    monkeypatch.setattr(plum._promotion, "_IDENTITY_CONVERSION_LIMIT", 3)

    @dispatch
    def f(x: object) -> object:
        return x

    types = [type(f"C{i}", (), {}) for i in range(10)]
    for t in types:
        assert f(t()) is not None
    assert len(identity_conversions) == 3


def test_unhashable_target_still_raises(identity_conversions, dispatch):
    """An unhashable target raises, as it always has.

    The cache hashes `(type(obj), type_to)`, but so does the method lookup it
    replaces, so such a target has never been usable.
    """

    class Meta(type):
        __hash__ = None  # The class object itself is unhashable.

    class Unhashable(metaclass=Meta):
        pass

    class Thing:
        pass

    with pytest.raises(TypeError, match="unhashable type"):
        plum.convert(Thing(), Unhashable)

    with pytest.raises(TypeError, match="unhashable type"):
        plum.convert(Thing(), [int])
