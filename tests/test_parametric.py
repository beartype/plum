import numpy as np
import pytest

from plum import (
    Dispatcher,
    parametric,
    type_parameter,
    kind,
    Kind,
    ptype,
    type_of,
    Type,
    PromisedType,
    List,
    Tuple,
    Union,
    NotFoundLookupError,
)
from plum.parametric import _types_of_iterable


def test_covariance():
    assert issubclass(List[int], List[object])
    assert issubclass(List[List[int]], List[List[object]])
    assert not issubclass(List[int], List[str])
    assert not issubclass(List[list], List[int])


def test_parametric():
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

    # Test multiple type parameters
    assert A[1, 2] == A[1, 2]

    def tuple_elements_are_identical(tup1, tup2):
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
    assert tuple_elements_are_identical(type_parameter(A[a1, a2]()), (a1, a2))
    assert tuple_elements_are_identical(type_parameter(A[1, a2]()), (1, a2))

    # Test that an error is raised if type parameters are specified twice.
    T = A[1]
    with pytest.raises(TypeError):
        T[1]


def test_constructor():
    @parametric
    class A:
        def __init__(self, x, *, y=3):
            self.x = x
            self.y = y

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

    @parametric
    class B:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    b1 = B[float, int](5.0, 3)
    b2 = B(5.0, 3)

    assert b1.x == 5.0
    assert b2.x == 5.0
    assert b1.y == 3
    assert b2.y == 3

    assert type_parameter(b1) == (float, int)
    assert type_parameter(b2) == (float, int)
    assert type(b1) == type(b2)
    assert type(b1).__name__ == type(b2).__name__ == f"B[{float},{int}]"


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


def test_listtype():
    # Standard type tests.
    assert hash(List[int]) == hash(List[int])
    assert hash(List[int]) != hash(List[str])
    assert hash(List[List[int]]) == hash(List[List[int]])
    assert hash(List[List[int]]) != hash(List[List[str]])
    assert repr(List[int]) == f"List[{Type(int)!r}]"
    assert issubclass(List[int].get_types()[0], list)
    assert not issubclass(List[int].get_types()[0], int)
    assert not issubclass(List[int].get_types()[0], tuple)

    # Test instance check.
    assert isinstance([], List[Union[object]])
    assert isinstance([1, 2], List[Union[int]])

    # Check tracking of parametric.
    assert List[int].parametric
    assert ptype(List[List[int]]).parametric
    assert ptype(Union[List[int]]).parametric
    promise = PromisedType()
    promise.deliver(List[int])
    assert promise.resolve().parametric

    # Test correctness.
    dispatch = Dispatcher()

    @dispatch
    def f(x):
        return "fallback"

    @dispatch
    def f(x: list):
        return "list"

    @dispatch
    def f(x: List[int]):
        return "list of int"

    @dispatch
    def f(x: List[List[int]]):
        return "list of list of int"

    assert f([1]) == "list of int"
    assert f(1) == "fallback"
    assert f([1, 2]) == "list of int"
    assert f([1, 2, "3"]) == "list"
    assert f([[1]]) == "list of list of int"
    assert f([[1], [1]]) == "list of list of int"
    assert f([[1], [1, 2]]) == "list of list of int"
    assert f([[1], [1, 2, "3"]]) == "list"


def test_tupletype():
    # Standard type tests.
    assert hash(Tuple[int]) == hash(Tuple[int])
    assert hash(Tuple[int]) != hash(Tuple[str])
    assert hash(Tuple[Tuple[int]]) == hash(Tuple[Tuple[int]])
    assert hash(Tuple[Tuple[int]]) != hash(Tuple[Tuple[str]])
    assert repr(Tuple[int]) == f"Tuple[{Type(int)!r}]"
    assert issubclass(Tuple[int].get_types()[0], tuple)
    assert not issubclass(Tuple[int].get_types()[0], int)
    assert not issubclass(Tuple[int].get_types()[0], list)

    # Test instance check.
    assert isinstance((), Tuple())
    assert isinstance((1, 2), Tuple[int, int])

    # Check tracking of parametric.
    assert Tuple[int].parametric
    assert ptype(List[Tuple[int]]).parametric
    assert ptype(Union[Tuple[int]]).parametric
    promise = PromisedType()
    promise.deliver(Tuple[int])
    assert promise.resolve().parametric

    # Test correctness.
    dispatch = Dispatcher()

    @dispatch
    def f(x):
        return "fallback"

    @dispatch
    def f(x: tuple):
        return "tup"

    @dispatch
    def f(x: Tuple[int]):
        return "tup of int"

    @dispatch
    def f(x: Tuple[int, int]):
        return "tup of double int"

    @dispatch
    def f(x: Tuple[Tuple[int]]):
        return "tup of tup of int"

    @dispatch
    def f(x: Tuple[Tuple[int], Tuple[int]]):
        return "tup of double tup of int"

    @dispatch
    def f(x: Tuple[int, Tuple[int, int]]):
        return "tup of int and tup of double int"

    assert f((1,)) == "tup of int"
    assert f(1) == "fallback"
    assert f((1, 2)) == "tup of double int"
    assert f((1, 2, "3")) == "tup"
    assert f(((1,),)) == "tup of tup of int"
    assert f(((1,), (1,))) == "tup of double tup of int"
    assert f((1, (1, 2))) == "tup of int and tup of double int"
    assert f(((1,), (1, 2))) == "tup"


def test_types_of_iterables():
    assert _types_of_iterable([1]) == Type(int)
    assert _types_of_iterable(["1"]) == Type(str)
    assert _types_of_iterable([1, "1"]) == Union[int, str]
    assert _types_of_iterable((1,)) == Type(int)
    assert _types_of_iterable(("1",)) == Type(str)
    assert _types_of_iterable((1, "1")) == Union[int, str]


def test_type_of():
    assert type_of(1) == Type(int)
    assert type_of("1") == Type(str)
    assert type_of([1]) == List[int]
    assert type_of([1, "1"]) == List[Union[int, str]]
    assert type_of([1, "1", (1,)]) == List[Union[int, str, Tuple[int]]]
    assert type_of((1,)) == Tuple[int]
    assert type_of(("1",)) == Tuple[str]
    assert type_of((1, "1")) == Tuple[int, str]
    assert type_of((1, "1", [1])) == Tuple[int, str, List[int]]


def test_type_of_extension():
    dispatch = Dispatcher()

    @parametric
    class NPArray(np.ndarray):
        pass

    @type_of.dispatch
    def type_of_extension(x: np.ndarray):
        return NPArray[x.ndim]

    @dispatch
    def f(x: NPArray[1]):
        return "vector"

    @dispatch
    def f(x: NPArray[2]):
        return "matrix"

    assert f(np.random.randn(10)) == "vector"
    assert f(np.random.randn(10, 10)) == "matrix"
    with pytest.raises(NotFoundLookupError):
        f(np.random.randn(10, 10, 10))
