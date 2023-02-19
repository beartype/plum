from numbers import Number
from typing import Union

import pytest

from plum import Kind, ModuleType, Val, kind, parametric, type_parameter
from plum.parametric import CovariantMeta, is_concrete, is_type


def test_covariantmeta():
    class A(metaclass=CovariantMeta):
        pass

    with pytest.raises(RuntimeError):
        A.concrete


class MyType(CovariantMeta):
    pass


@pytest.mark.parametrize(
    "parametric",
    [
        parametric,
        # Also test that we can use our own metaclass.
        parametric(metaclass=MyType),
    ],
)
def test_parametric(parametric):
    class Base1:
        pass

    class Base2:
        pass

    @parametric
    class A(Base1):
        pass

    assert issubclass(A, Base1)
    assert not issubclass(A, Base2)

    assert A[1] == A[1]
    assert A[2] == A[2]
    assert A[1] != A[2]

    a1 = A[1]()
    a2 = A[2]()

    assert type(a1) == A[1]
    assert type(a2) == A[2]
    assert isinstance(a1, A[1])
    assert not isinstance(a1, A[2])
    assert issubclass(type(a1), A)
    assert issubclass(type(a1), Base1)
    assert not issubclass(type(a1), Base2)

    # Test multiple type parameters.
    assert A[1, 2] == A[1, 2]

    def tuples_are_identical(tup1, tup2):
        if len(tup1) != len(tup2):
            return False
        for x, y in zip(tup1, tup2):
            if x is not y:
                return False
        return True

    # Test type parameter extraction.
    assert type_parameter(A[1]()) == 1
    assert type_parameter(A["1"]()) == "1"
    assert type_parameter(A[1.0]()) == 1.0
    assert type_parameter(A[1, 2]()) == (1, 2)
    assert type_parameter(A[a1]()) is a1
    assert tuples_are_identical(type_parameter(A[a1, a2]()), (a1, a2))
    assert tuples_are_identical(type_parameter(A[1, a2]()), (1, a2))

    # Test that an error is raised if type parameters are specified twice.
    T = A[1]
    with pytest.raises(TypeError):
        T[1]


def test_parametric_inheritance():
    class A(metaclass=CovariantMeta):
        def __init__(self, x):
            self.x = x

    @parametric
    class B(A):
        def __init__(self, x, y):
            pass

    class C(B):
        def __init__(self, x, y, z):
            pass

    @parametric
    class D(C):
        def __init__(self, w, x, y, z):
            pass

    @parametric
    class E(D):
        def __init__(self, v, w, x, y, z):
            pass

    assert issubclass(B, A)
    assert issubclass(B[1], A)
    assert issubclass(C, A)
    assert issubclass(D, A)
    assert issubclass(D[1], A)
    assert issubclass(E, A)
    assert issubclass(E[1], A)

    assert issubclass(C, B)
    assert issubclass(D, B)
    assert issubclass(D[1], B)
    assert issubclass(E, B)
    assert issubclass(E[1], B)

    assert not issubclass(C, B[1])
    assert not issubclass(D, B[1])
    assert issubclass(D[1], B[1])  # Covariance
    assert not issubclass(D[1], B[1, 2])
    assert not issubclass(D[1], B[2])
    assert issubclass(E, B)
    assert issubclass(E[1], B)

    assert issubclass(D, C)
    assert issubclass(D[1], C)
    assert issubclass(E, C)
    assert issubclass(E[1], C)

    assert issubclass(E, D)
    assert issubclass(E[1], D)

    assert not issubclass(E, D[1])
    assert issubclass(E[1], D[1])  # Covariance
    assert not issubclass(E[1], D[1, 2])
    assert not issubclass(E[1], D[2])

    assert type(A(1)) == A
    assert type(B(1, 2)) == B[int, int]
    assert type(C(1, 2, 3)) == C
    assert type(D(1, 2, 3, 4)) == D[int, int, int, int]
    assert type(E(1, 2, 3, 4, 5)) == E[int, int, int, int, int]


def test_parametric_covariance():
    @parametric
    class A:
        pass

    # Test covariance.
    assert issubclass(A[int], A[Number])
    assert not issubclass(A[int], A[float])

    # Check that the number of arguments must be right.
    assert not issubclass(A[int], A[Number, Number])
    assert issubclass(A[int, int], A[Number, Number])
    assert not issubclass(A[int, int, int], A[Number, Number])

    # Test that type parameters are resolved.
    assert issubclass(
        A[ModuleType("builtins", "int")],
        A[ModuleType("numbers", "Number")],
    )

    # Check a mix between equatable objects and types.
    assert issubclass(A[1, int], A[1, Number])
    assert not issubclass(A[2, int], A[1, Number])


def test_parametric_constructor():
    @parametric
    class A:
        def __init__(self, x, *, y=3):
            self.x = x
            self.y = y

    assert A.parametric
    assert not A.concrete
    with pytest.raises(RuntimeError):
        A.type_parameter

    assert A[float].parametric
    assert A[float].concrete
    assert A[float].type_parameter == float

    a1 = A[float](5.0)
    a2 = A(5.0)

    assert a1.x == 5.0
    assert a2.x == 5.0
    assert a1.y == 3
    assert a2.y == 3

    assert type_parameter(a1) == float
    assert type_parameter(a2) == float
    assert type(a1) == type(a2)
    assert type(a1).__name__ == type(a2).__name__ == f"A[{float}]"


def test_parametric_override_type_parameters():
    @parametric
    class NTuple:
        @classmethod
        def __infer_type_parameter__(self, *args):
            # Mimicks the type parameters of an `NTuple`.
            T = type(args[0])
            N = len(args)
            return (N, T)

        def __init__(self, *args):
            T = type(self)._type_parameter[1]
            assert all(isinstance(arg, T) for arg in args)
            self.args = args

    assert isinstance(NTuple(1, 2, 3), NTuple[3, int])


def test_is_concrete():
    class A:
        pass

    @parametric
    class B:
        pass

    assert not is_concrete(A)
    assert not is_concrete(B)
    assert is_concrete(B[1])


def test_is_type():
    assert is_type(int)
    assert is_type(Union[int, float])
    assert not is_type(1)


def test_type_parameter():
    @parametric
    class A:
        pass

    class B:
        pass

    assert type_parameter(A()) == ()
    assert type_parameter(A[1]) == 1
    assert type_parameter(A[1]()) == 1
    assert type_parameter(A["1"]) == "1"
    assert type_parameter(A["1"]()) == "1"

    with pytest.raises(
        RuntimeError,
        match=r"(?i)cannot get the type parameter of non-instantiated parametric",
    ):
        type_parameter(A)
    with pytest.raises(ValueError, match=r"not a concrete parametric type"):
        type_parameter(B)
    with pytest.raises(ValueError, match=r"not a concrete parametric type"):
        type_parameter(B())


def test_kind():
    assert Kind[1] == Kind[1]
    assert Kind[1] != Kind[2]
    assert Kind[1](1).get() == 1
    assert Kind[2](1, 2).get() == (1, 2)

    Kind2 = kind()
    assert Kind2[1] != Kind[1]
    assert Kind[1] == Kind[1]
    assert Kind2[1] == Kind2[1]

    # Test providing a superclass, where the default should be `object`.
    class SuperClass:
        pass

    Kind3 = kind(SuperClass)
    assert issubclass(Kind3[1], SuperClass)
    assert not issubclass(Kind2[1], SuperClass)
    assert issubclass(Kind2[1], object)


def test_val():
    # Check some cases.
    for T, v in [
        (Val[3], Val(3)),
        (Val[3, 4], Val((3, 4))),
        (Val[(3, 4)], Val((3, 4))),
    ]:
        assert T == type(v)
        assert T() == v

    # Test all checks for numbers of arguments and the like.
    with pytest.raises(ValueError):
        Val()
    with pytest.raises(ValueError):
        Val(1, 2, 3)
    with pytest.raises(ValueError):
        Val[1](2)

    # Check that `__init__` can only be called for a concrete instance.
    class MockVal:
        concrete = False

    with pytest.raises(ValueError):
        Val[1].__init__(MockVal())

    assert repr(Val[1]()) == "plum.parametric.Val[1]()"
