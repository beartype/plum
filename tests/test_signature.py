import inspect
import operator
from collections.abc import Callable, Iterable
from numbers import Number as Num, Real as Re
from typing import Annotated, Any, Literal, Optional, Union

import pytest

from beartype.door import TypeHint
from beartype.vale import Is

import plum
from plum import Signature as Sig
from plum._util import Missing


def test_instantiation_copy():
    s = Sig(
        int,
        int,
        varargs=float,
        precedence=1,
    )
    for _ in range(2):
        assert s.types == (int, int)
        assert s.has_varargs
        assert s.varargs is float
        assert s.precedence == 1
        assert s.is_faithful

        # Test copying.
        s = s.__copy__()

    # Test defaults.
    s = Sig(int, int)
    assert not s.has_varargs
    assert s.varargs == Missing

    # Test faithfulness check.
    assert Sig(int, int).is_faithful
    assert Sig(int, int, varargs=int).is_faithful
    assert not Sig(tuple[int], int, varargs=int).is_faithful
    assert not Sig(int, tuple[int], varargs=int).is_faithful
    assert not Sig(int, int, varargs=tuple[int]).is_faithful


def _impl(x, y, *z):
    return str(x)


@pytest.mark.parametrize(
    "sig, expected",
    [
        (
            Sig(),
            "Signature()",
        ),
        (
            Sig(int),
            "Signature(int)",
        ),
        (
            Sig(int, float),
            "Signature(int, float)",
        ),
        (
            Sig(int, float, varargs=complex),
            "Signature(int, float, varargs=complex)",
        ),
        (
            Sig(int, float, varargs=complex),
            "Signature(int, float, varargs=complex)",
        ),
        (
            Sig(int, float, varargs=complex, precedence=1),
            "Signature(int, float, varargs=complex, precedence=1)",
        ),
        (
            Sig(
                int,
                float,
                varargs=complex,
                precedence=1,
            ),
            "Signature(int, float, varargs=complex, precedence=1)",
        ),
    ],
)
def test_repr(sig, expected):
    assert repr(sig) == expected


def test_hash():
    assert hash(Sig(int)) == hash(Sig(int))
    sigs = {Sig(int), Sig(int, int), Sig(int, int, varargs=int)}
    assert len(sigs) == 3


def test_equality():
    sig = Sig(int, float, varargs=complex, precedence=1)
    assert sig == Sig(int, float, varargs=complex, precedence=1)
    assert sig != Sig(int, int, varargs=complex, precedence=1)
    assert sig != Sig(int, float, varargs=int, precedence=1)
    assert sig != Sig(int, float, varargs=complex, precedence=2)
    # :class:`Signature` should allow comparison against other objects.
    assert sig != 1

    # Test all branches of variable argument `TypeHint` casting.
    assert Sig() == Sig()
    assert Sig() != Sig(varargs=int)
    assert Sig(varargs=int) != Sig()
    assert Sig(varargs=int) == Sig(varargs=int)

    # Test equivalent but not identical types.
    t1 = Union[int, bool]  # noqa: UP007
    t2 = int
    assert t1 is not t2 and t1 != t2
    assert TypeHint(t1) == TypeHint(t2)
    assert Sig(t1) == Sig(t2)
    assert Sig(varargs=t1) == Sig(varargs=t2)

    # Test equivalent but not identical types.
    t1 = int | bool
    t2 = int
    assert t1 is not t2 and t1 != t2
    assert TypeHint(t1) == TypeHint(t2)
    assert Sig(t1) == Sig(t2)
    assert Sig(varargs=t1) == Sig(varargs=t2)


def test_expand_varargs():
    # Case of no variable arguments:
    assert Sig(int, int).expand_varargs(3) == (int, int)

    # Case of variable arguments:
    s = Sig(int, int, varargs=float)
    assert s.expand_varargs(2) == (int, int)
    assert s.expand_varargs(3) == (int, int, float)
    assert s.expand_varargs(4) == (int, int, float, float)


def test_varargs_tie_breaking(dispatch: plum.Dispatcher):
    # These are related to bug #117.

    assert Sig(int) < Sig(int, varargs=int)
    assert Sig(int, varargs=int) < Sig(int, Num)
    assert Sig(int, int, varargs=int) < Sig(int, Num)

    assert not Sig(int) >= Sig(int, varargs=int)
    assert not Sig(int, varargs=int) >= Sig(int, Num)
    assert not Sig(int, int, varargs=int) >= Sig(int, Num)

    @dispatch
    def f(*xs: int):
        return "ints"

    @dispatch
    def f(*xs: Num):
        return "nums"

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: int, y: int):
        return "two ints"

    @dispatch
    def f(x: Num):
        return "num"

    @dispatch
    def f(x: Num, y: Num):
        return "two nums"

    @dispatch
    def f(x: int, *ys: int):
        return "int and ints"

    @dispatch
    def f(x: int, *ys: Num):
        return "int and nums"

    @dispatch
    def f(x: Num, *ys: int):
        return "num and ints"

    @dispatch
    def f(x: Num, *ys: Num):
        return "num and nums"

    assert f(1) == "int"
    assert f(1, 1) == "two ints"
    assert f(1, 1, 1) == "int and ints"

    assert f(1.0) == "num"
    assert f(1.0, 1.0) == "two nums"
    assert f(1.0, 1.0, 1.0) == "num and nums"

    assert f(1, 1.0) == "int and nums"
    assert f(1.0, 1) == "num and ints"

    assert f(1, 1, 1.0) == "int and nums"
    assert f(1.0, 1.0, 1) == "num and nums"
    assert f(1, 1.0, 1.0) == "int and nums"
    assert f(1.0, 1, 1) == "num and ints"


def test_117_case1(dispatch: plum.Dispatcher):
    class A:
        pass

    class B:
        pass

    @dispatch
    def f(x: int, *a: A):
        return "int and As"

    @dispatch
    def f(x: int, *a: B):
        return "int and Bs"

    with pytest.raises(plum.AmbiguousLookupError):
        f(1)
    assert f(1, A()) == "int and As"
    assert f(1, B()) == "int and Bs"


@pytest.mark.xfail(reason="bug #117")
def test_117_case2(dispatch: plum.Dispatcher):
    class A:
        pass

    class B:
        pass

    @dispatch
    def f(x: int, *a: A):
        return "int and As"

    @dispatch
    def f(x: Num, *a: B):
        return "num and Bs"

    assert f(1) == "int and As"
    assert f(1, A()) == "int and As"
    assert f(1.0) == "num and Bs"
    assert f(1.0, B()) == "num and Bs"


def test_117_case3(dispatch: plum.Dispatcher):
    class A:
        pass

    class B:
        pass

    @dispatch
    def f(x: int, *a: A):
        return "int and As"

    @dispatch
    def f(x: int, *a: B):
        return "int and Bs"

    @dispatch
    def f(x: Num, *a: B):
        return "num and Bs"

    with pytest.raises(plum.AmbiguousLookupError):
        f(1)
    assert f(1, A()) == "int and As"
    assert f(1, B()) == "int and Bs"
    assert f(1.0) == "num and Bs"
    assert f(1.0, B()) == "num and Bs"


def test_varargs_subset():
    assert Sig(int, varargs=int) == Sig(int, varargs=int)
    assert Sig(int, varargs=int) < Sig(Num, varargs=int)
    assert Sig(int, varargs=int) < Sig(int, varargs=Num)
    assert Sig(int, varargs=int) < Sig(Num, varargs=Num)
    assert Sig(int, varargs=Num) == Sig(int, varargs=Num)
    assert Sig(int, varargs=Num) < Sig(Num, varargs=Num)
    assert Sig(Num, varargs=int) == Sig(Num, varargs=int)
    assert Sig(Num, varargs=int) < Sig(Num, varargs=Num)
    assert Sig(Num, varargs=Num) == Sig(Num, varargs=Num)

    assert not Sig(Num, varargs=int) <= Sig(int, varargs=int)
    assert not Sig(int, varargs=Num) <= Sig(int, varargs=int)
    assert not Sig(Num, varargs=Num) <= Sig(int, varargs=int)
    assert not Sig(int, varargs=Num) <= Sig(Num, varargs=int)
    assert not Sig(Num, varargs=Num) <= Sig(Num, varargs=int)
    assert not Sig(Num, varargs=int) <= Sig(int, varargs=Num)
    assert not Sig(Num, varargs=Num) <= Sig(int, varargs=Num)

    class A:
        pass

    class B:
        pass

    assert not Sig(int, varargs=A) <= Sig(int, varargs=B)
    assert not Sig(int, varargs=B) <= Sig(int, varargs=A)


def test_comparison():
    # Variable arguments shortcuts:
    assert not Sig(varargs=int) <= Sig()
    assert not Sig(varargs=Num) <= Sig(varargs=int)

    # Expandability shortcuts:
    assert not Sig(int) <= Sig(int, int)
    assert not Sig(int) <= Sig(int, int, varargs=int)
    assert not Sig(int, int, varargs=int) <= Sig(int)

    # Test expansion:
    assert Sig(varargs=int) <= Sig(Re, varargs=Re)
    assert Sig(int, varargs=int) <= Sig(Re, varargs=Re)
    assert Sig(int, int, varargs=int) <= Sig(Re, varargs=Re)

    assert not Sig(varargs=Num) <= Sig(Re, varargs=Re)
    assert not Sig(Num, varargs=int) <= Sig(Re, varargs=Re)
    assert not Sig(int, int, varargs=Num) <= Sig(Re, varargs=Re)

    assert Sig(float, varargs=int) <= Sig(float, Re, varargs=Re)
    assert Sig(float, int, varargs=int) <= Sig(float, Re, varargs=Re)
    assert Sig(float, int, int, varargs=int) <= Sig(float, Re, varargs=Re)


def test_match():
    assert Sig(int).match((1,))
    assert Sig(int, int).match((1, 2))
    assert Sig(int, varargs=int).match((1,))
    assert Sig(int, varargs=int).match((1, 2))
    assert Sig(int, varargs=int).match((1, 2, 3))

    # Wrong type:
    assert not Sig(int).match((1.0,))
    assert not Sig(int, int).match((1, 2.0))
    assert not Sig(int, varargs=int).match((1.0,))
    assert not Sig(int, varargs=int).match((1, 2.0))
    assert not Sig(int, varargs=int).match((1, 2, 3.0))

    # Wrong number:
    assert not Sig(int).match((1, 2))
    assert not Sig(int, int).match((1,))
    assert not Sig(int, varargs=int).match(())


def test_compute_distance():
    assert Sig(int, int).compute_distance(()) == 2
    assert Sig(int, int).compute_distance((1,)) == 1
    assert Sig(int, int).compute_distance((1.0,)) == 2
    assert Sig(int, int).compute_distance((1, 1)) == 0
    assert Sig(int, int).compute_distance((1, 1, 1)) == 1
    assert Sig(int, int).compute_distance((1, 1, 1, 1)) == 2
    assert Sig(int, int).compute_distance((1, 1.0, 1, 1)) == 3
    assert Sig(int, int).compute_distance((1, 1.0, 1.0, 1)) == 3

    assert Sig(varargs=float).compute_distance((1, 1)) == 2
    assert Sig(varargs=float).compute_distance((1,)) == 1
    assert Sig(varargs=float).compute_distance(()) == 0
    assert Sig(varargs=float).compute_distance((1.0,)) == 0
    assert Sig(varargs=float).compute_distance((1.0, 1.0)) == 0


def test_compute_mismatches():
    # Test without varargs present:
    assert Sig(int, int).compute_mismatches(()) == (set(), True)
    assert Sig(int, int).compute_mismatches((1,)) == (set(), True)
    assert Sig(int, int).compute_mismatches((1, 1)) == (set(), True)
    assert Sig(int, int).compute_mismatches((1.0, 1)) == ({0}, True)
    assert Sig(int, int).compute_mismatches((1, 1.0)) == ({1}, True)
    assert Sig(int, int).compute_mismatches((1.0, 1.0)) == ({0, 1}, True)
    # If more values are given, these are ignored if not varargs are present.
    assert Sig(int, int).compute_mismatches((1.0, 1.0, 1)) == ({0, 1}, True)

    # Test with varargs present:
    sig = Sig(int, int, varargs=int)
    assert sig.compute_mismatches((1.0, 1.0, 1.0)) == ({0, 1}, False)
    assert sig.compute_mismatches((1.0, 1.0, 1)) == ({0, 1}, True)
    assert sig.compute_mismatches((1.0, 1.0, 1, 1)) == ({0, 1}, True)


def test_inspect_signature():
    assert isinstance(plum.inspect_signature(lambda x: x), inspect.Signature)
    assert len(plum.inspect_signature(lambda x: x).parameters) == 1
    assert len(plum.inspect_signature(operator.itemgetter(1)).parameters) == 1
    assert len(plum.inspect_signature(operator.attrgetter("x")).parameters) == 1


def assert_signature(f, *types, varargs=Missing):
    sig = Sig.from_callable(f)
    assert sig.types == types
    assert sig.varargs == varargs


def test_signature_from_callable():
    def f():
        pass

    # Check precedence.
    assert Sig.from_callable(f).precedence == 0
    assert Sig.from_callable(f, precedence=1).precedence == 1

    # Check defaults.
    assert_signature(f)

    # Check a more complex example.

    def f(a: int, b, *c: float, **kw_args: Num) -> Re:
        pass

    assert_signature(f, int, Any, varargs=float)

    # Check that default values must be right.

    def f_good(a: int = 1):
        pass

    def f_bad(a: int = 1.0):
        pass

    assert_signature(f_good, int)
    with pytest.raises(
        TypeError,
        match=r"Default value `1.0` is not an instance of the annotated type `int`.",
    ):
        Sig.from_callable(f_bad)


def test_append_default_args():
    def f(a: int, b=1, c: float = 1.0, *d: complex, option=None, **other_options):
        pass

    sigs = plum.append_default_args(Sig.from_callable(f), f)
    assert len(sigs) == 3
    assert (sigs[0].types, sigs[0].varargs) == ((int, Any, float), complex)
    assert (sigs[1].types, sigs[1].varargs) == ((int, Any), Missing)
    assert (sigs[2].types, sigs[2].varargs) == ((int,), Missing)

    # Test the case of more argument names than types.
    sigs = plum.append_default_args(Sig(int, Any), f)
    assert len(sigs) == 2
    assert (sigs[0].types, sigs[0].varargs) == ((int, Any), Missing)
    assert (sigs[1].types, sigs[1].varargs) == ((int,), Missing)
    sigs = plum.append_default_args(Sig(int), f)
    assert len(sigs) == 1
    assert (sigs[0].types, sigs[0].varargs) == ((int,), Missing)

    # Test that `itemgetter` is supported.
    f = operator.itemgetter(0)
    assert len(plum.append_default_args(Sig.from_callable(f), f)) == 1


def test_signature_cache_spec_and_derived_flags():
    # Faithful signature: empty spec, is_faithful.
    s = Sig(int, int)
    assert s.cache_spec == frozenset()
    assert s.is_faithful

    # type[X] signature: non-empty spec, cacheable but not faithful.
    s = Sig(type[int], int)
    assert s.cache_spec and not s.is_faithful

    # varargs participate.
    assert Sig(int, varargs=type[int]).cache_spec
    assert not Sig(int, varargs=type[int]).is_faithful

    # Uncacheable: spec is None.
    s = Sig(list[int])
    assert s.cache_spec is None
    assert not s.is_faithful


# A grid of hints and values wide enough to exercise every branch of
# `_might_match_hint`: faithful and unfaithful, subscripted and bare, unions,
# `Literal`, `Annotated`, and hints without an origin.

_MIGHT_MATCH_HINTS = [
    Any,
    int,
    str,
    object,
    list,
    list[int],
    list[str],
    tuple[int, ...],
    dict[str, int],
    Callable[[int], int],
    Iterable[int],
    type[int],
    Literal[1],
    Literal["a"],
    int | list[int],
    Optional[list[str]],  # noqa: UP007, UP045
    Annotated[int, Is[lambda x: x > 0]],
    Annotated[list[int], Is[lambda x: len(x) > 0]],
]

# Grouped by runtime type, since that is all `might_match` may depend on.
_MIGHT_MATCH_VALUES = [
    [1, 2, -1],
    [1.0, 2.5],
    ["a", "b"],
    [True, False],
    [None],
    [[1], ["a"], [], [1, 2]],
    [(1, 2), ()],
    [{"a": 1}, {1: "a"}, {}],
    [int, str],
    [lambda x: x],
    [object()],
]


@pytest.mark.parametrize("hint", _MIGHT_MATCH_HINTS)
def test_might_match_is_implied_by_match(hint):
    # Under-inclusion is a wrong answer: whatever matches must be kept.
    s = Sig(hint)
    for group in _MIGHT_MATCH_VALUES:
        for v in group:
            assert not s.match((v,)) or s.might_match((v,))


@pytest.mark.parametrize("hint", _MIGHT_MATCH_HINTS)
def test_might_match_depends_only_on_the_runtime_type(hint):
    # The verify cache is keyed on `tuple(map(type, args))`, so `might_match` must
    # not distinguish two values of the same type.
    s = Sig(hint)
    for group in _MIGHT_MATCH_VALUES:
        assert len({s.might_match((v,)) for v in group}) == 1


def test_might_match_arity_and_varargs():
    s = Sig(int, varargs=list[int])
    assert s.might_match((1,))
    assert s.might_match((1, [1]))
    assert s.might_match((1, [1], [2]))
    assert not s.might_match(())
    assert not s.might_match(("a",))
    # The varargs must be checked too, not just the fixed types.
    assert not s.might_match((1, "a"))

    s = Sig(int, list[int])
    assert not s.might_match((1,))
    assert not s.might_match((1, [1], [2]))
    assert s.might_match((1, [1]))
    # A list of the wrong element type cannot be ruled out by the runtime type.
    assert s.might_match((1, ["a"]))
    assert not s.match((1, ["a"]))
