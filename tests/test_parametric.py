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
    Dict,
    Iterable,
    Sequence,
    Union,
    NotFoundLookupError,
    Val,
)
from plum.parametric import _types_of_iterable, CovariantMeta


def test_covariantmeta():
    class A(metaclass=CovariantMeta):
        pass

    with pytest.raises(RuntimeError):
        A.concrete


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


def test_constructor():
    @parametric
    class A:
        def __init__(self, x, *, y=3):
            self.x = x
            self.y = y

    assert A.parametric
    assert not A.concrete
    assert not A.runtime_type_of
    with pytest.raises(RuntimeError):
        A.type_parameter

    assert A[float].parametric
    assert A[float].concrete
    assert not A[float].runtime_type_of
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

    @parametric(runtime_type_of=True)
    class B:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    assert B.parametric
    assert not B.concrete
    assert B.runtime_type_of
    with pytest.raises(RuntimeError):
        B.type_parameter

    assert B[float].parametric
    assert B[float].concrete
    assert B[float].runtime_type_of
    assert B[float].type_parameter == float

    b1 = B[float, int](5.0, 3)
    b2 = B(5.0, 3)

    assert b1.x == 5.0
    assert b2.x == 5.0
    assert b1.y == 3
    assert b2.y == 3

    assert type_parameter(b1) == (float, int)
    assert type_parameter(b2) == (float, int)
    assert type(b1) == type(b2)
    assert type(b1).__name__ == type(b2).__name__ == f"B[{float}, {int}]"


def test_override_type_parameters():
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

    assert NTuple[3, int] == type(NTuple(1, 2, 3))


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


def test_list():
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

    # Check tracking of runtime `type_of`.
    assert List[int].runtime_type_of
    assert ptype(List[List[int]]).runtime_type_of
    assert ptype(Union[List[int]]).runtime_type_of
    promise = PromisedType()
    promise.deliver(List[int])
    assert promise.resolve().runtime_type_of

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


def test_tuple():
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

    # Check tracking of runtime `type_of`.
    assert Tuple[int].runtime_type_of
    assert ptype(List[Tuple[int]]).runtime_type_of
    assert ptype(Union[Tuple[int]]).runtime_type_of
    promise = PromisedType()
    promise.deliver(Tuple[int])
    assert promise.resolve().runtime_type_of

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


def test_dict():
    # Standard type tests.
    assert hash(Dict[int, float]) == hash(Dict[int, float])
    assert hash(Dict[int, float]) != hash(Tuple[int, str])
    assert hash(Dict[int, float]) != hash(Tuple[str, float])
    assert hash(Dict[Tuple[int], float]) == hash(Dict[Tuple[int], float])
    assert hash(Dict[Tuple[int], float]) != hash(Dict[Tuple[str], float])
    assert repr(Dict[int, float]) == f"Dict[{Type(int)!r}, {Type(float)!r}]"
    assert issubclass(Dict[int, float].get_types()[0], dict)
    assert not issubclass(Dict[int, float].get_types()[0], int)

    # Test instance check.
    assert isinstance({}, Dict[Union[object], Union[object]])
    assert isinstance({1: 2.0}, Dict[int, float])

    # Check tracking of parametric.
    assert Dict[int, float].parametric
    assert ptype(Dict[Tuple[int], float]).parametric
    assert ptype(Union[Dict[int, float]]).parametric
    promise = PromisedType()
    promise.deliver(Dict[int, float])
    assert promise.resolve().parametric

    # Check tracking of runtime `type_of`.
    assert Dict[int, float].runtime_type_of
    assert ptype(Dict[Tuple[int], float]).runtime_type_of
    assert ptype(Union[Dict[int, float]]).runtime_type_of
    promise = PromisedType()
    promise.deliver(Dict[int, float])
    assert promise.resolve().runtime_type_of

    # Test correctness.
    dispatch = Dispatcher()

    @dispatch
    def f(x):
        return "fallback"

    @dispatch
    def f(x: dict):
        return "dict"

    @dispatch
    def f(x: Dict[int, int]):
        return "int to int"

    @dispatch
    def f(x: Dict[str, int]):
        return "str to int"

    @dispatch
    def f(x: Dict[Union[int, str], int]):
        return "int or str to int"

    assert f(1) == "fallback"
    assert f({1: 1}) == "int to int"
    assert f({"1": 1}) == "str to int"
    assert f({"1": 1, 1: 1}) == "int or str to int"
    assert f({"1": "1", 1: 1}) == "dict"


def test_iterable():
    # Standard type tests.
    assert hash(Iterable[int]) == hash(Iterable[int])
    assert hash(Iterable[int]) != hash(Iterable[str])
    assert hash(Iterable[int]) != hash(Iterable())
    assert hash(Iterable[Iterable[int]]) == hash(Iterable[Iterable[int]])
    assert hash(Iterable[Iterable[int]]) != hash(Iterable[Iterable[str]])
    assert repr(Iterable()) == "Iterable"
    assert repr(Iterable[int]) == f"Iterable[{Type(int)!r}]"

    # Test instance check.
    assert isinstance([], Iterable())
    assert isinstance([], Iterable[object])
    assert isinstance((1, 2.0), Iterable())
    assert isinstance((1, 2.0), Iterable[Union[int, float]])
    assert isinstance([1, 2], Iterable())
    assert isinstance([1, 2], Iterable[int])
    assert isinstance((x for x in [1, 2]), Iterable())

    # Test subclass check.
    assert issubclass(ptype(list), Iterable())
    assert issubclass(List[int], Iterable())
    assert issubclass(List[int], Iterable[int])
    assert not issubclass(ptype(list), Iterable[int])
    assert issubclass(Iterable[int], Iterable[object])

    # Check tracking of parametric.
    assert Iterable[int].parametric
    assert ptype(Iterable[Iterable[int]]).parametric
    assert ptype(Union[Iterable[int]]).parametric
    promise = PromisedType()
    promise.deliver(Iterable[int])
    assert promise.resolve().parametric

    # Check tracking of runtime `type_of`.
    assert Iterable[int].runtime_type_of
    assert ptype(Iterable[Iterable[int]]).runtime_type_of
    assert ptype(Union[Iterable[int]]).runtime_type_of
    promise = PromisedType()
    promise.deliver(Iterable[int])
    assert promise.resolve().runtime_type_of

    assert not Iterable().runtime_type_of
    assert ptype(Iterable[Iterable()]).runtime_type_of
    assert not ptype(Union[Iterable()]).runtime_type_of
    promise = PromisedType()
    promise.deliver(Iterable())
    assert not promise.resolve().runtime_type_of

    # Test correctness.
    dispatch = Dispatcher()

    @parametric
    class A:
        def __init__(self, el_type):
            pass

        def __iter__(self):
            pass

    @parametric
    class B(A):
        @classmethod
        def __iter_el_type__(cls):
            return cls.type_parameter

    @dispatch
    def f(x):
        return "fallback"

    @dispatch
    def f(x: Iterable()):
        return "it"

    @dispatch
    def f(x: Iterable[int]):
        return "it of int"

    @dispatch
    def f(x: Iterable[Iterable[object]]):
        return "it of it"

    assert f(1) == "fallback"
    # Test various iterators:
    assert f((x for x in [1, 2])) == "it"
    assert f(A(1)) == "it"
    assert f(A(1.0)) == "it"
    assert f(B(1)) == "it of int"
    assert f(B(1.0)) == "it"
    assert f([1]) == "it of int"
    assert f([1.0]) == "it"
    assert f({1: 1}) == "it of int"
    assert f({1.0: 1}) == "it"
    assert f((1, 1)) == "it of int"
    assert f((1.0, 1)) == "it"
    # Test nested iterators:
    assert f([[1]]) == "it of it"
    assert f(([1], [1, 2, "3"])) == "it of it"


def test_sequence():
    # Standard type tests.
    assert hash(Sequence[int]) == hash(Sequence[int])
    assert hash(Sequence[int]) != hash(Sequence[str])
    assert hash(Sequence[int]) != hash(Sequence())
    assert hash(Sequence[Sequence[int]]) == hash(Sequence[Sequence[int]])
    assert hash(Sequence[Sequence[int]]) != hash(Sequence[Sequence[str]])
    assert repr(Sequence()) == "Sequence"
    assert repr(Sequence[int]) == f"Sequence[{Type(int)!r}]"

    # Test instance check.
    assert isinstance([], Sequence())
    assert isinstance([], Sequence[object])
    assert isinstance((1, 2.0), Sequence())
    assert isinstance((1, 2.0), Sequence[Union[int, float]])
    assert isinstance([1, 2], Sequence())
    assert isinstance([1, 2], Sequence[int])
    assert not isinstance((x for x in [1, 2]), Sequence())

    # Test subclass check.
    assert issubclass(ptype(list), Sequence())
    assert issubclass(List[int], Sequence())
    assert issubclass(List[int], Sequence[int])
    assert not issubclass(ptype(list), Sequence[int])
    assert issubclass(Sequence[int], Sequence[object])

    # Check tracking of parametric.
    assert Sequence[int].parametric
    assert ptype(Sequence[Sequence[int]]).parametric
    assert ptype(Union[Sequence[int]]).parametric
    promise = PromisedType()
    promise.deliver(Sequence[int])
    assert promise.resolve().parametric

    # Check tracking of runtime `type_of`.
    assert Sequence[int].runtime_type_of
    assert ptype(Sequence[Sequence[int]]).runtime_type_of
    assert ptype(Union[Sequence[int]]).runtime_type_of
    promise = PromisedType()
    promise.deliver(Sequence[int])
    assert promise.resolve().runtime_type_of

    assert not Sequence().runtime_type_of
    assert ptype(Sequence[Sequence()]).runtime_type_of
    assert not ptype(Union[Sequence()]).runtime_type_of
    promise = PromisedType()
    promise.deliver(Sequence())
    assert not promise.resolve().runtime_type_of

    # Test correctness.
    dispatch = Dispatcher()

    @parametric
    class A:
        def __init__(self, el_type):
            pass

        def __len__(self):
            pass

        def __getitem__(self, item):
            pass

    @parametric
    class B(A):
        @classmethod
        def __getitem_el_type__(cls):
            return cls.type_parameter

    @dispatch
    def f(x):
        return "fallback"

    @dispatch
    def f(x: Sequence()):
        return "seq"

    @dispatch
    def f(x: Sequence[int]):
        return "seq of int"

    @dispatch
    def f(x: Sequence[Sequence[object]]):
        return "seq of seq"

    assert f(1) == "fallback"
    assert f((x for x in [1, 2])) == "fallback"
    # Test various sequences:
    assert f(A(1)) == "seq"
    assert f(A(1.0)) == "seq"
    assert f(B(1)) == "seq of int"
    assert f(B(1.0)) == "seq"
    assert f([1]) == "seq of int"
    assert f([1.0]) == "seq"
    assert f({1: 1}) == "seq of int"
    assert f({1: 1.0}) == "seq"
    assert f((1, 1)) == "seq of int"
    assert f((1.0, 1)) == "seq"
    # Test nested sequences:
    assert f([[1]]) == "seq of seq"
    assert f(([1], [1, 2, "3"])) == "seq of seq"


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

    @parametric(runtime_type_of=True)
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
