from numbers import Number
from typing import Union

import pytest

import plum
from plum import add_conversion_method, add_promotion_rule, conversion_method
from plum.promotion import _promotion_rule


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
    assert plum.convert("test".encode(), str) == "test"


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

    add_promotion_rule(str, Union[int, float], float)
    add_conversion_method(str, Union[int, float], float)

    assert promote(1, "1", "1") == (2.0, 1.0, 1.0)
    assert promote("1", 1, 1) == (1.0, 2.0, 2.0)
    assert promote(1.0, "1", 1) == (1.0, 1.0, 2.0)
    assert promote("1", 1.0, 1) == (1.0, 1.0, 2.0)

    add_promotion_rule(str, int, float)
    add_promotion_rule(str, float, float)
    add_conversion_method(str, float, lambda x: "lel")

    assert promote(1, "1", 1.0) == (2.0, "lel", 1.0)
    assert promote("1", 1, 1.0) == ("lel", 2.0, 1.0)
    assert promote(1.0, "1", 1) == (1.0, "lel", 2.0)
    assert promote("1", 1.0, "1") == ("lel", 1.0, "lel")


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
