import inspect
import operator
from numbers import Number as Num, Real as Re
from typing import Any, Union
from unittest.mock import patch

import pytest

from beartype.door import TypeHint

import plum
import plum._signature
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


def test_le_non_signature_returns_not_implemented():
    """Signature.__le__ must return NotImplemented for non-Signature objects.

    This lets Python's comparison machinery try the reflected operation instead
    of raising TypeError, which is the correct protocol for __le__.
    """
    sig = Sig(int)
    assert sig.__le__("not_a_signature") is NotImplemented
    assert sig.__le__(42) is NotImplemented
    assert sig.__le__(None) is NotImplemented


def test_is_comparable_non_signature_returns_false():
    """Signature.is_comparable must return False for non-Signature objects."""
    sig = Sig(int)
    assert sig.is_comparable("not_a_signature") is False
    assert sig.is_comparable(42) is False
    assert sig.is_comparable(None) is False


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


@pytest.mark.parametrize(
    "sig, values, expected",
    [
        (Sig(int, int), (), 2),
        (Sig(int, int), (1,), 1),
        (Sig(int, int), (1.0,), 2),
        (Sig(int, int), (1, 1), 0),
        (Sig(int, int), (1, 1, 1), 1),
        (Sig(int, int), (1, 1, 1, 1), 2),
        (Sig(int, int), (1, 1.0, 1, 1), 3),
        (Sig(int, int), (1, 1.0, 1.0, 1), 3),
        (Sig(varargs=float), (1, 1), 2),
        (Sig(varargs=float), (1,), 1),
        (Sig(varargs=float), (), 0),
        (Sig(varargs=float), (1.0,), 0),
        (Sig(varargs=float), (1.0, 1.0), 0),
    ],
)
def test_compute_distance(sig, values, expected):
    assert sig.compute_distance(values) == expected


@pytest.mark.parametrize(
    "sig, values, expected_mismatches, expected_varargs_matched",
    [
        # Without varargs:
        (Sig(int, int), (), set(), True),
        (Sig(int, int), (1,), set(), True),
        (Sig(int, int), (1, 1), set(), True),
        (Sig(int, int), (1.0, 1), {0}, True),
        (Sig(int, int), (1, 1.0), {1}, True),
        (Sig(int, int), (1.0, 1.0), {0, 1}, True),
        # Extra values beyond sig.types are ignored when no varargs:
        (Sig(int, int), (1.0, 1.0, 1), {0, 1}, True),
        # With varargs:
        (Sig(int, int, varargs=int), (1.0, 1.0, 1.0), {0, 1}, False),
        (Sig(int, int, varargs=int), (1.0, 1.0, 1), {0, 1}, True),
        (Sig(int, int, varargs=int), (1.0, 1.0, 1, 1), {0, 1}, True),
    ],
)
def test_compute_mismatches(sig, values, expected_mismatches, expected_varargs_matched):
    assert sig.compute_mismatches(values) == (
        expected_mismatches,
        expected_varargs_matched,
    )


# ── Generic __orig_class__ semantics in distance/mismatches ──────────────────


@pytest.fixture()
def make_box():
    """Return a fresh Box generic class (avoids polluting module scope)."""
    from typing import Generic, TypeVar

    T = TypeVar("T")

    class Box(Generic[T]):
        def __init__(self, val: object) -> None:
            self.val = val

    return Box


def test_compute_distance_honours_orig_class(make_box):
    """compute_distance must use is_bearable_with_orig, not plain is_bearable.

    With plain is_bearable, beartype cannot distinguish Box[int] from Box[str]
    at runtime, so Sig(Box[str]).compute_distance((Box[int](1),)) would
    incorrectly return 0 (no mismatch) instead of 1.
    """
    Box = make_box
    box_int = Box[int](1)

    # A Box[int] instance does NOT match Sig(Box[str]).
    assert Sig(Box[str]).compute_distance((box_int,)) == 1

    # A Box[int] instance DOES match Sig(Box[int]) → distance 0.
    assert Sig(Box[int]).compute_distance((box_int,)) == 0

    # A Box[int] instance DOES match the bare Sig(Box) → distance 0.
    assert Sig(Box).compute_distance((box_int,)) == 0


def test_compute_mismatches_honours_orig_class(make_box):
    """compute_mismatches must use is_bearable_with_orig, not plain is_bearable.

    With plain is_bearable, beartype cannot distinguish Box[int] from Box[str],
    so Sig(Box[str]).compute_mismatches((Box[int](1),)) would incorrectly
    return (set(), True) instead of ({0}, True).
    """
    Box = make_box
    box_int = Box[int](1)

    # Box[int] does NOT match Box[str] → position 0 is a mismatch.
    assert Sig(Box[str]).compute_mismatches((box_int,)) == ({0}, True)

    # Box[int] DOES match Box[int] → no mismatch.
    assert Sig(Box[int]).compute_mismatches((box_int,)) == (set(), True)

    # Box[int] DOES match bare Box → no mismatch.
    assert Sig(Box).compute_mismatches((box_int,)) == (set(), True)


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


def test_le_constructs_typehint_wrapper_once_per_pair():
    """TypeHintWrapper must be constructed once per type pair in ``__le__``.

    A two-pass implementation constructs TypeHintWrapper for every type twice
    when the equality check (pass 1) fails and the subset check (pass 2)
    succeeds.  The optimised implementation must construct each wrapper exactly
    once per pair regardless of which branch is taken.
    """

    real_wrapper = plum._signature.TypeHintWrapper
    calls: list[object] = []

    def counting_wrapper(t: object) -> object:
        calls.append(t)
        return real_wrapper(t)

    # bool < int on both positions: equality fails, subset succeeds.
    # Two type pairs → expect exactly 4 TypeHintWrapper constructions
    # (one for each type in each pair, built once).
    with patch.object(plum._signature, "TypeHintWrapper", side_effect=counting_wrapper):
        result = Sig(bool, bool) <= Sig(int, int)

    assert result is True
    assert (
        len(calls) == 4
    ), f"Expected 4 TypeHintWrapper constructions, got {len(calls)}: {calls}"


@pytest.mark.parametrize(
    "left, right",
    [
        (Sig(int, int), Sig(int)),  # length mismatch
        (Sig(int, precedence=0), Sig(int, precedence=1)),  # precedence mismatch
        (Sig(int), Sig(int, varargs=int)),  # varargs-presence mismatch
    ],
    ids=["length", "precedence", "varargs"],
)
def test_eq_short_circuits_before_building_wrappers(left, right):
    """``__eq__`` returns False without building any TypeHintWrapper when cheap
    scalar checks (length / precedence / varargs) already prove inequality.
    """
    real_wrapper = plum._signature.TypeHintWrapper
    calls: list[object] = []

    def counting_wrapper(t: object) -> object:
        calls.append(t)
        return real_wrapper(t)

    with patch.object(plum._signature, "TypeHintWrapper", side_effect=counting_wrapper):
        result = left == right
    assert result is False
    assert len(calls) == 0, f"Expected 0 TypeHintWrapper calls, got {len(calls)}"


def test_is_comparable_avoids_redundant_typehint_wrappers():
    """``Signature.is_comparable`` must call ``__le__`` at most twice, not fall back
    to the base ``self < other or self == other or self > other`` which builds up to
    6 TypeHintWrapper objects per comparison.
    """
    real_wrapper = plum._signature.TypeHintWrapper
    calls: list[object] = []

    def counting_wrapper(t: object) -> object:
        calls.append(t)
        return real_wrapper(t)

    # Equal signatures: self.__le__(other) is True so the override returns
    # True after just 1 __le__ call (2 TypeHintWrapper constructions for
    # 1-type sig).  Without the override: 6 constructions.
    with patch.object(plum._signature, "TypeHintWrapper", side_effect=counting_wrapper):
        result = Sig(int).is_comparable(Sig(int))
    assert result is True
    assert len(calls) <= 2, (
        f"Expected at most 2 TypeHintWrapper calls for is_comparable "
        f"(equal 1-type signatures), got {len(calls)}"
    )
