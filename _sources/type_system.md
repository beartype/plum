# Type System

## Union Types

`typing.Union` can be used to instantiate union types:

```python
from typing import Union

from plum import dispatch

@dispatch
def f(x):
    return "fallback"


@dispatch
def f(x: Union[int, str]):
    return "int or str"
```

```python
>>> f(1)
'int or str'

>>> f("1")
'int or str'

>>> f(1.0)
'fallback'
```

(parametric-types)=
## Parametric Types

The parametric types `typing.Tuple`, `typing.List`, `typing.Dict`,
`typing.Iterable`, and `typing.Sequence` can be used to dispatch on respectively
tuples, lists,  dictionaries, iterables, and sequence with particular types of
elements.
Importantly, the type system is *covariant*, as opposed to Julia's type
system, which is *invariant*.

Example involving some parametric types:

```python
from typing import Union, Tuple, List, Dict

from plum import dispatch

@dispatch
def f(x: Union[tuple, list]):
    return "tuple or list"
    
    
@dispatch
def f(x: Tuple[int, int]):
    return "tuple of two ints"
    
    
@dispatch
def f(x: List[int]):
    return "list of int"


@dispatch
def f(x: Dict[int, str]):
   return "dict of int to str"
```

```python
>>> f([1, 2])
'list of int'

>>> f([1, "2"])
'tuple or list'

>>> f((1, 2))
'tuple of two ints'

>>> f((1, 2, 3))
'tuple or list'

>>> f((1, "2"))
'tuple or list'

>>> f({1: "2"})
'dict of int to str'
```

**Note:** Although parametric types are supported, parametric types do incur a
significant  performance hit, because the type of every element in a list or tuple
must be checked.
It is recommended to use parametric types only where absolutely necessary.

## Variable Arguments

A variable number of arguments can be used without any problem.

```python
from plum import dispatch

@dispatch
def f(x: int):
    return "single argument"
    

@dispatch
def f(x: int, *xs: int):
    return "multiple arguments"
```

```python
>>> f(1)
'single argument'

>>> f(1, 2)
'multiple arguments'

>>> f(1, 2, 3)
'multiple arguments'
```

## Return Types

Return types can be used without any problem.

```python
from typing import Union

from plum import dispatch, add_conversion_method

@dispatch
def f(x: Union[int, str]) -> int:
    return x
```

```python
>>> f(1)
1

>>> f("1")
TypeError: Cannot convert a "builtins.str" to a "builtins.int".

>>> add_conversion_method(type_from=str, type_to=int, f=int)

>>> f("1")
1
```
