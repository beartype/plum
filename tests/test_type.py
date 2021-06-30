import typing

import pytest

from plum.parametric import List, Tuple
from plum.resolvable import ResolutionError
from plum.type import (
    VarArgs,
    Union,
    Type,
    PromisedType,
    deliver_forward_reference,
    get_forward_reference,
    ptype,
    is_object,
    is_type,
    TypeType,
)


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


def test_forwardreferencedtype():
    class A:
        pass

    class B:
        pass

    t_a = get_forward_reference("A")
    t_b = get_forward_reference("B")

    with pytest.raises(ResolutionError):
        t_a.resolve()
    with pytest.raises(ResolutionError):
        t_b.resolve()

    deliver_forward_reference(A)

    assert t_a == Type(A)
    with pytest.raises(ResolutionError):
        t_b.resolve()

    deliver_forward_reference(B)

    assert t_a == Type(A)
    assert t_b == Type(B)


def test_ptype():
    class A:
        pass

    t = Type(int)
    assert ptype(t) is t
    assert ptype(int) == t

    # Check `None` as valid type annotation.
    assert ptype(None) == Type(type(None))

    # Check conversion of strings.
    t = ptype("A")
    deliver_forward_reference(A)
    assert t == Type(A)

    with pytest.raises(RuntimeError):
        ptype(1)


def test_ptype_typing_mapping():
    class A:
        pass

    # `Union`:
    assert ptype(typing.Union[typing.Union[int], list]) == Union[Union[int], list]
    assert ptype(typing.Union) == Union[object]

    # `Optional`:
    assert ptype(typing.Optional[int]) == Union[int, type(None)]
    assert ptype(typing.Optional) == Union[object]

    # `List`:
    assert ptype(typing.List[typing.List[int]]) == List[List[int]]
    assert ptype(typing.List) == Type(list)

    # `Tuple`:
    assert ptype(typing.Tuple[typing.Tuple[int], list]) == Tuple[Tuple[int], list]
    assert ptype(typing.Tuple) == Type(tuple)

    # `ForwardRef`:
    if hasattr(typing, "ForwardRef"):
        t = ptype(typing.ForwardRef("A"))
    else:
        # The `typing` package is different for Python 3.6.
        t = ptype(typing._ForwardRef("A"))
    deliver_forward_reference(A)
    assert t == Type(A)

    # `Any`:
    assert ptype(typing.Any) == ptype(object)

    # `Callable`:
    assert ptype(typing.Callable) == Type(typing.Callable)

    # Check propagation of conversion of strings.
    t = ptype(typing.Union["A"])
    deliver_forward_reference(A)
    assert t == ptype(Union[A])

    t = ptype(typing.List["A"])
    deliver_forward_reference(A)
    assert t == ptype(List[A])

    t = ptype(typing.Tuple["A"])
    deliver_forward_reference(A)
    assert t == ptype(Tuple[A])


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
