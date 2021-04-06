import typing

import pytest

from plum.parametric import List, Tuple
from plum.resolvable import ResolutionError
from plum.type import (
    VarArgs,
    Union,
    Type,
    PromisedType,
    deliver_reference,
    get_reference,
    ptype,
    is_object,
    is_type,
    TypeType,
)
from plum.type import _processed_owners


def test_varargs():
    assert hash(VarArgs(int)) == hash(VarArgs(int))
    assert repr(VarArgs(int)) == f"VarArgs({Type(int)!r})"
    assert VarArgs(int).expand(2) == (Type(int), Type(int))
    assert not VarArgs(int).parametric
    assert VarArgs(List[int]).parametric


def test_comparabletype():
    assert isinstance(1, Union[int])
    assert not isinstance("1", Union[int])
    assert isinstance("1", Union[int, str])
    assert issubclass(Union[int], Union[int])
    assert issubclass(Union[int], Union[int, str])
    assert not issubclass(Union[int, str], Union[int])
    assert Union[int].mro() == int.mro()
    with pytest.raises(RuntimeError):
        Union[int, str].mro()


def test_union():
    assert hash(Union[int, str]) == hash(Union[str, int])
    assert repr(Union[int, str]) == repr(Union[int, str])
    assert set(Union[int, str].get_types()) == {str, int}
    assert not Union[int].parametric

    # Test equivalence between `Union` and `Type`.
    assert hash(Union[int]) == hash(Type(int))
    assert hash(Union[int, str]) != hash(Type(int))
    assert repr(Union[int]) == repr(Type(int))
    assert repr(Union[int, str]) != repr(Type(int))

    # Test lazy conversion to set.
    t = Union[int, int, str]
    assert isinstance(t._types, tuple)
    t.get_types()
    assert isinstance(t._types, set)

    # Test aliases.
    assert repr(Union(int, alias="MyUnion")) == "tests.test_type.MyUnion"
    assert repr(Union(int, str, alias="MyUnion")) == "tests.test_type.MyUnion"


def test_type():
    assert hash(Type(int)) == hash(Type(int))
    assert hash(Type(int)) != hash(Type(str))
    assert repr(Type(int)) == f"{int.__module__}.{int.__name__}"
    assert Type(int).get_types() == (int,)
    assert not Type(int).parametric
    assert not Type(List[int]).parametric


def test_promisedtype():
    t = PromisedType()
    with pytest.raises(ResolutionError):
        hash(t)
    with pytest.raises(ResolutionError):
        repr(t)
    with pytest.raises(ResolutionError):
        t.get_types()

    t.deliver(Type(int))
    assert hash(t) == hash(Type(int))
    assert repr(t) == repr(Type(int))
    assert t.get_types() == Type(int).get_types()
    assert not t.parametric

    t = PromisedType()
    t.deliver(List[int])
    assert t.parametric


def test_qualifiednametype():
    class A:
        pass

    name = "tests.test_type.test_qualifiednametype.<locals>.A"
    t = get_reference(name)

    with pytest.raises(ResolutionError):
        t.resolve()

    # Check delivery process.
    assert A not in _processed_owners
    deliver_reference(A)
    assert A in _processed_owners
    assert t == Type(A)

    # Check caching.
    assert get_reference(name) == Type(A)


def test_astype():
    class A:
        pass

    t = Type(int)
    assert ptype(t) is t
    assert ptype(int) == t

    # Check conversion of strings.
    name = "tests.test_type.test_astype.<locals>.A"
    t = ptype(name)
    deliver_reference(A)
    assert t == Type(A)
    assert ptype("A", context=lambda: None) == Type(A)
    with pytest.raises(TypeError):
        ptype("A")

    with pytest.raises(RuntimeError):
        ptype(1)


def test_astype_typing_mapping():
    class A:
        pass

    assert ptype(typing.Union[typing.Union[int], list]) == Union[Union[int], list]
    assert ptype(typing.Union) == Union[object]
    assert ptype(typing.Optional[int]) == Union[int, type(None)]
    assert ptype(typing.Optional) == Union[object]
    assert ptype(typing.List[typing.List[int]]) == List[List[int]]
    assert ptype(typing.List) == Type(list)
    assert ptype(typing.Tuple[typing.Tuple[int], list]) == Tuple[Tuple[int], list]
    assert ptype(typing.Tuple) == Type(tuple)
    t = ptype(typing._ForwardRef("builtins.int"))
    deliver_reference(int)
    assert t == Type(int)

    # Check propagation of conversion of strings.
    ptype("tests.test_type.test_astype_typing_mapping.<locals>.A")
    deliver_reference(A)
    assert ptype(typing.Union["A"], context=lambda: None) == ptype(Union[A])
    assert ptype(typing.List["A"], context=lambda: None) == ptype(List[A])
    assert ptype(typing.Tuple["A"], context=lambda: None) == ptype(Tuple[A])


def test_typetype():
    Promised = PromisedType()
    Promised.deliver(int)

    assert ptype(type(int)) <= TypeType
    assert ptype(type(Promised)) <= TypeType

    assert not (ptype(int) <= TypeType)
    assert not (ptype(Promised) <= TypeType)


def test_is_object():
    assert is_object(Type(object))
    assert not is_object(Type(int))


def test_is_type():
    assert is_type(int)
    assert is_type(Type(int))
    assert not is_type(1)
