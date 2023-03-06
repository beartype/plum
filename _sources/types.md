# Types

Types of arguments of arguments and return types can be specified using type hints as
usual.
You can use anything from `typing`.
Under the hood, Plum uses [Beartype](https://github.com/beartype/beartype), which means
that all types and type hints supported by Beartype are also supported by Plum.
Here are a few examples:

```python
from typing import Union, Optional, List, Dict

from plum import dispatch


@dispatch
def f(x) -> str:
    return "fallback"


@dispatch
def f(x: int, *xs: int) -> str:
    return "one or more ints"


@dispatch
def f(x: Union[int, str]) -> str:
    return "int or str"


@dispatch
def f(x: list) -> str:
    return "list"


@dispatch
def f(x: List[int]) -> str:
    return "list of int"


@dispatch
def f(x: Optional[dict]) -> Optional[str]:
    return "dict or None"


@dispatch
def f(x: Dict[int, str]) -> str:
   return "dict of int to str"
```

**Note:**
Although parametric types such as `List[int]` and `Dict[int, str]` are fully
supported, they do incur a performance penalty.
For optimal performance, is recommended to use parametric types only where necessary.
`Union` and `Optional` do not incur a performance penalty.

The type system is *covariant*, as opposed to Julia's type
system, which is *invariant*.
For example, this means that `List[T1]` is a subtype of `List[T2]` whenever
`T1` is a subtype of `T2`.

## Performance and Faithful Types

Plum achieves performance by caching the dispatch process.
Unfortunately, efficient caching is not always possible.
Efficient caching is possible for so-called _faithful_ types.

````{admonition} Definition: faithful type
A type `t` is _faithful_ if, for all `x`, the following is true:
```python
isinstance(x, t) == issubclass(type(x), t)
```
````

For example, `int` is faithful, since `type(1) == int`;
but `Literal[1]` is not faithful, since `issubclass(int, Literal[1])` is false.

Methods which have signatures that depend only on faithful types will 
be performant.
On the other hand, methods which have one or more signatures with one or more
unfaithful types cannot use caching and will therefore be less performant.

Example:

```python
from typing import Literal

from plum import dispatch


@dispatch
def add_5_faithful(x: int):
    return x + 5


@dispatch
def add_5_unfaithful(x: Literal[1]):
    return x + 5
```

```python
>>> %timeit add_5_faithful(1)
585 ns ± 6.2 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)

>>> %timeit add_5_unfaithful(1)
6.24 µs ± 68.9 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)
```

Plum implements `is_faithful`, which is a function that attempts to establish whether
a type is faithful or not:

```python
>>> from plum import is_faithful

>>> is_faithful(int)
True

>>> is_faithful(Literal[1])
False
```

If you implement, e.g., a type with a custom `__instancecheck__`, then `is_faithful`
will detect this and conservatively say that your type is not faithful.
You can tell Plum whether your type is faithful or not by setting `__faithful__`:

```python
...

class MyClass(metaclass=MyMeta):
    __faithful__ = True   # Yes, `MyClass` is faithful!

    ...
```

(moduletype)=
## `ModuleType`

A niche use case is that you might want to depend on types from packages you have not
yet imported.
This can be useful if these packages either bring a lot of dependencies or are slow to
load.
This is possible with `ModuleType`.

```{important}
After the dependency is imported, you must clear all cache using `clear_all_cache`!
If you do not, due to existing caches, dispatch may behave erroneously.
```

Example:

```python
from plum import dispatch, clear_all_cache, ModuleType

EagerTensor = ModuleType("tensorflow.python.framework.ops", "EagerTensor")


@dispatch
def f(x: EagerTensor):
    return "An eager TF tensor!"
```

```python
>>> f(1)
NotFoundLookupError: For function `f`, `(1,)` could not be resolved.

>>> f.methods
[Signature(plum.type.ModuleType[tensorflow.python.framework.ops.EagerTensor], implementation=<function f at 0x7fc2a89a5310>)]

>>> import tensorflow as tf  # Very slow...

>>> clear_all_cache()  # Clear dispatch cache.

>>> f(tf.ones(5))
'An eager TF tensor!'
```

The object `EagerTensor` is a `type`.
You can resolve it to what it points to with `resolve_type_hint`:

```python
>>> EagerTensor
plum.type.ModuleType[tensorflow.python.framework.ops.EagerTensor]

>>> from plum import resolve_type_hint

>>> resolve_type_hint(EagerTensor)
tensorflow.python.framework.ops.EagerTensor
```

(promisedtype)=
## `PromisedType`

Another problem that can occur is that you want to depend on a type from your package,
but you just cannot yet access it because of circular imports.
In this case, you use `PromisedType` to create a proxy type and then deliver the
dependency when it is available.

```{important}
You *must* deliver the dependency before the proxy type is used!
That is, you cannot use the function that uses the proxy type as a type hint
before the dependency is delivered.
```

```python
from plum import dispatch, clear_all_cache, PromisedType

ProxyInt = PromisedType("SpecialInt")  # Proxy for `int`


@dispatch
def f(x: ProxyInt):
    return "An integer!"

# Deliver the type that `ProxyInt` should point to. Do this before `f` is first used!
ProxyInt.deliver(int)  
```

```python
>>> f(1)
'An integer!' 
```

Like for `PromisedType`,
the object `ProxyInt` is a `type`.
You can resolve it to what it points to with `resolve_type_hint`:

```python
>>> ProxyInt
plum.type.PromisedType[SpecialInt]

>>> from plum import resolve_type_hint

>>> resolve_type_hint(ProxyInt)
int
```
