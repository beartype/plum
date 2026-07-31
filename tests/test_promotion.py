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


# The identity-conversion memo (`plum._function.identity_conversions`) lets a dispatched
# call skip `convert` when its return annotation is already satisfied. These tests pin
# the conditions that make the skip sound, not its speed. They go through a dispatched
# function, because that -- not `plum.convert` -- is what reads the memo.


def _memo():
    return plum._function.identity_conversions


@pytest.fixture
def memo(convert):
    """A cleared memo, restored afterwards along with the conversion methods."""
    plum._function.identity_conversions.clear()
    yield _memo()
    plum._function.identity_conversions.clear()


def test_identity_conversion_is_memoised(memo, dispatch):
    class Base:
        pass

    @dispatch
    def f(x: Base) -> Base:
        return x

    obj = Base()
    assert f(obj) is obj
    assert memo[Base, Base] is True
    # The memoised answer is the same answer.
    assert f(obj) is obj


def test_memo_is_actually_read(memo, dispatch, monkeypatch):
    """Once a pair is memoised, the call must not reach `convert` at all."""

    class Base:
        pass

    @dispatch
    def f(x: Base) -> Base:
        return x

    obj = Base()
    assert f(obj) is obj  # Populates the memo.

    def explode(*args, **kw):
        raise AssertionError("convert was called despite a memoised identity")

    monkeypatch.setattr(plum._function, "_promised_convert", explode)
    assert f(obj) is obj


def test_memo_yields_to_a_later_conversion_method(memo, dispatch):
    """A conversion method registered *after* a pair is memoised must still win.

    `Sub` is a `Base`, so the first call finds no conversion method and returns the
    object unchanged. Registering `Sub -> Base` afterwards makes the memoised answer
    wrong, so `add_conversion_method` has to drop it.
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
    assert memo[Sub, Base] is True

    add_conversion_method(Sub, Base, lambda _: "converted")
    assert f(obj) == "converted"


def test_memo_not_used_for_unfaithful_targets(memo, dispatch):
    """A target whose match depends on the value cannot be answered from the type.

    Both objects are `Thing`s, so they share the key `(Thing, Gate)`, but `Gate`
    decides membership from the value. Memoising the first call would make the second
    wrongly succeed -- exactly what the faithfulness gate prevents.
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
    assert memo[(Thing, Gate)] is False
    with pytest.raises(TypeError):
        f(bad)


def test_memo_not_used_for_literals(memo, dispatch):
    @dispatch
    def f(x: int) -> typing.Literal[1]:
        return x

    assert f(1) == 1
    assert memo[(int, typing.Literal[1])] is False
    with pytest.raises(TypeError):
        f(2)


def test_memo_does_not_mask_failures(memo, dispatch):
    class Base:
        pass

    @dispatch
    def f(x: float) -> Base:
        return x

    with pytest.raises(TypeError):
        f(1.0)
    # A raising conversion never reaches the recording step, so nothing is stored.
    assert (float, Base) not in memo
    with pytest.raises(TypeError):
        f(1.0)


def test_memo_cleared_by_clear_all_cache(memo, dispatch):
    class Base:
        pass

    @dispatch
    def f(x: Base) -> Base:
        return x

    assert f(Base()) is not None
    assert memo
    plum.clear_all_cache()
    assert not memo


def test_memo_handles_union_targets(memo, dispatch):
    """A union of faithful types is faithful, so it is memoisable as a whole."""

    class A:
        pass

    class B:
        pass

    @dispatch
    def f(x: A | float) -> A | B:
        return x

    a = A()
    assert f(a) is a
    assert memo[A, A | B] is True
    with pytest.raises(TypeError):
        f(1.0)


def test_memo_is_bounded(memo, dispatch, monkeypatch):
    """The memo stops growing at its limit instead of retaining types forever."""
    monkeypatch.setattr(plum._promotion, "_IDENTITY_CONVERSION_LIMIT", 3)

    @dispatch
    def f(x: object) -> object:
        return x

    types = [type(f"C{i}", (), {}) for i in range(10)]
    for t in types:
        assert f(t()) is not None
    assert len(memo) == 3


def test_memo_not_used_when_a_conversion_method_applies(memo, dispatch):
    """A pair a conversion method handles must never be memoised as an identity.

    `Sub` is a `Base`, so the fallback *would* have returned it unchanged; what makes
    the pair unmemoisable is that a conversion method claims it first.
    """

    class Base:
        pass

    class Sub(Base):
        pass

    add_conversion_method(Sub, Base, lambda _: "converted")

    @dispatch
    def f(x: Sub) -> Base:
        return x

    obj = Sub()
    assert f(obj) == "converted"
    assert memo[(Sub, Base)] is False
    # The second call must convert too, rather than take a memoised shortcut.
    assert f(obj) == "converted"


def test_unhashable_target_still_raises(memo, dispatch):
    """An unhashable target raises `TypeError`, as it did before the memo existed.

    The memo hashes `(type(obj), type_to)`, but so does the method lookup it replaces,
    so such a target has never been usable. This pins that the memo did not turn a
    `TypeError` into something else.
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
