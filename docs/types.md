# Types

Types of arguments of arguments and return types can be specified using type hints as
usual.
You can use anything from `typing`.
Under the hood, Plum uses [Beartype](https://github.com/beartype/beartype), which means
that all types and type hints supported by Beartype are also supported by Plum.
Here are a few examples:

```python
from typing import Union, Optional

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
def f(x: list[int]) -> str:
    return "list of int"


@dispatch
def f(x: Optional[dict]) -> Optional[str]:
    return "dict or None"


@dispatch
def f(x: dict[int, str]) -> str:
   return "dict of int to str"
```

Although parametric types such as `list[int]` and `dict[int, str]` are fully
supported, they do incur a performance penalty.
For optimal performance, is recommended to use parametric types only where necessary.
`Union` and `Optional` do not incur a performance penalty.

````{important}
Plum's type system is powered by [Beartype](https://github.com/beartype/beartype).
To ensure constant-time performance,
Beartype checks the types of containers by checking the type of a random single element.
This means that it is not safe to use containers with mixed element types!

```python
from typing import List

from plum import dispatch


@dispatch
def f(x: List[int]) -> str:
    return "list of int"
```

```
>>> f([1, "1"])  # It might happen to check the first element.
"list of int"

>>> f([1, "1"])  # Or it might check the second. :(
NotFoundLookupError: `f([1, '1'])` could not be resolved.
```

In the future, Beartype
[will support exhaustive type checking](https://beartype.readthedocs.io/en/latest/api_decor/#beartype.BeartypeStrategy.On).
Plum already opts into this behaviour and will use it once it becomes available.
````

The type system is *covariant*, as opposed to Julia's type
system, which is *invariant*.
For example, this means that `list[T1]` is a subtype of `list[T2]` whenever
`T1` is a subtype of `T2`.

## Performance, Cacheable and Faithful Types

Plum achieves performance by caching the dispatch process.
Unfortunately, efficient caching is not always possible.
Efficient caching is possible for so-called _cacheable_ types.
The dispatch result for an argument `x` is cached under a key `cache_key(x)`, which captures `type(x)` and, if some method needs it, the identity of `x` if `x` is a class, the value of `x` if a `Literal` could match it, and `x.__orig_class__` if `x` is an instance of a parametrised user generic.
Equal keys imply the same match result, but do not depend on the layout of the key, which may change.

````{admonition} Definition: cacheable type
A type `t` is _cacheable_ if, for all `x`, whether `x` matches `t` is a function of
`cache_key(x)` alone.
````

The most important cacheable types are the _faithful_ ones, whose match depends only on
`type(x)`:

% skip: next "Definition"

````{admonition} Definition: faithful type
A type `t` is _faithful_ if, for all `x`, the following is true:
```python
isinstance(x, t) == issubclass(type(x), t)
```
````

Every faithful type is cacheable.
Two kinds of types are cacheable but _not_ faithful:

- `type[X]` (or `typing.Type[X]`): `issubclass(x, X)` depends on the identity of the class `x`, which `cache_key` captures.
- `Literal[...]`: the match depends on the *value* of `x`, likewise captured.

For example, `int` is faithful, since `type(1) == int`.
`Literal[1]` is not faithful, since `issubclass(int, Literal[1])` is false, but it is cacheable.

```{admonition} Cache growth
:class: warning
The cache holds strong references to the classes and values that a function is called with.
A function that dispatches on `type[X]` therefore keeps every class it is called with alive until `f.clear_cache()` or `plum.clear_all_cache()` is called.
A function that dispatches on `Literal` stops caching after 4096 entries, since `Literal["ready"]` next to a `str` fallback would otherwise add an entry for every new string.
```

If every method of a function uses only cacheable types, then Plum caches which method the arguments match, and a repeated call is a single dictionary lookup.
If any method uses an uncacheable type, then Plum cannot cache the method.
It instead caches which methods arguments of the given types could match, and checks only those on every call.
This is slower, but faster than checking every method.
Both caches are cleared by `f.clear_cache()` and `plum.clear_all_cache()`.

Example:

```python
from typing import Literal

from plum import dispatch


@dispatch
def add_5_faithful(x: int):
    return x + 5


@dispatch
def add_5_uncacheable(x: list[int]):
    return x + [5]
```

```python
>>> %timeit add_5_faithful(1)  # doctest:+SKIP
382 ns ± 10.2 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)

>>> %timeit add_5_uncacheable([1])  # doctest:+SKIP
2.49 µs ± 31.1 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)
```

Plum implements `is_faithful`, which is a function that attempts to establish whether
a type is faithful or not:

```python
>>> from plum import is_faithful, is_cacheable

>>> is_faithful(int)
True

>>> is_faithful(Literal[1])
False

>>> is_faithful(type[int])
False

>>> is_cacheable(type[int])
True

>>> is_cacheable(Literal[1])
True

>>> is_cacheable(list[int])
False
```

If you implement, e.g., a type with a custom `__instancecheck__`, then `is_faithful`
will detect this and conservatively say that your type is not faithful.
You can tell Plum whether your type is faithful or not by setting `__faithful__`:

% skip: next

```python
...

class MyClass(metaclass=MyMeta):
    __faithful__ = True   # Yes, `MyClass` is faithful!

    ...
```

(generics)=
## Dispatching on User-Defined Generics

You can dispatch on a parametrised subclass of `typing.Generic`.
At runtime, `Box[int](1)` and `Box[str]("a")` are both plain `Box` instances, so an
instance check cannot tell them apart.
Python does record the intent, though: instantiating a subscripted generic sets
`__orig_class__` on the instance, and Plum dispatches on that.

```python
from typing import Generic, TypeVar

from plum import dispatch

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v):
        self.v = v


@dispatch
def unbox(b: Box[int]):
    return "an integer"


@dispatch
def unbox(b: Box[str]):
    return "a string"


@dispatch
def unbox(b: Box):
    return "unparametrised"
```

```python
>>> unbox(Box[int](1))
'an integer'

>>> unbox(Box[str]("a"))
'a string'
```

An instance created without a parameter records nothing, so it matches only the
unparametrised method.
The same holds for an instance of a class with `__slots__`, on which Python cannot set
`__orig_class__`:

```python
>>> unbox(Box(1.0))
'unparametrised'
```

A subclass of a parametrised generic records its parameter statically, in
`__orig_bases__`, so it dispatches even though its instances carry no `__orig_class__`:

```python
>>> class IntBox(Box[int]):
...     def __init__(self):
...         super().__init__(1)

>>> unbox(IntBox())
'an integer'
```

Whether `Box[bool]` matches `Box[int]`, i.e. how the variance of a `TypeVar` is
interpreted, is up to Beartype.

A parametrised user generic is cacheable but not faithful: dispatch on it is cached on
`type(x)` and `x.__orig_class__`.
The unparametrised class stays faithful.
A parametrised builtin such as `list[int]` is not cacheable, because Beartype checks
its elements, so a function that dispatches on one uses the verify cache described
above.

```python
>>> from plum import is_cacheable

>>> is_cacheable(Box[int])
True

>>> is_cacheable(Box)
True

>>> is_cacheable(list[int])
False
```

### Inferring the Parameter for Bare Instantiations

To let a bare instantiation dispatch like a subscripted one, decorate the class with
`plum.generic` and give it an `__infer_type_parameter__` classmethod, which returns the
parameter for a constructed instance:

```python
from typing import Generic, TypeVar

from plum import dispatch, generic

S = TypeVar("S")


@generic
class Crate(Generic[S]):
    def __init__(self, v):
        self.v = v

    @classmethod
    def __infer_type_parameter__(cls, instance):
        return type(instance.v)


@dispatch
def uncrate(c: Crate[int]):
    return "an integer"


@dispatch
def uncrate(c: Crate[str]):
    return "a string"
```

A bare instantiation now dispatches like a subscripted one:

```python
>>> uncrate(Crate(1))
'an integer'

>>> uncrate(Crate("a"))
'a string'
```

An explicit subscript still wins, because Python assigns `__orig_class__` *after*
`__init__` returns:

```python
>>> uncrate(Crate[str](1))
'a string'
```

Return a tuple from `__infer_type_parameter__` for a generic with several parameters.
The attribute is written with `object.__setattr__`, so frozen dataclasses work too, and
the parametrisation is built from `type(instance)`, so a generic subclass infers itself:

```python
>>> class SubCrate(Crate[S]):
...     pass

>>> SubCrate(1).__orig_class__ == SubCrate[int]
True
```

Every instantiation of a decorated class runs `__infer_type_parameter__` and builds
`Crate[...]`, so construction is slower. Dispatch on the result is not affected.

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

% skip: start "Requires `tensorflow`."

Example:

```python
from plum import dispatch, clear_all_cache, ModuleType

EagerTensor = ModuleType("tensorflow.python.framework.ops", "EagerTensor")


@dispatch
def f(x: EagerTensor):
    return "An eager TF tensor!"
```

```python
>>> try: f(1)
... except Exception as e: print(f"{type(e).__name__}: {e}")
NotFoundLookupError: `f(1)` could not be resolved...

>>> g.methods
List of 1 method(s):
    [0] f(x:
        plum.type.ModuleType[tensorflow.python.framework.ops.EagerTensor])
            <function f at ...> @ ...

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

You might run into a scenario where an import is only possible when a certain condition
is satisfied, e.g. a constraint on the package version.
You can specify a condition with the keyword argument `condition`.

Example:

```python
def jax_version():
    import sys
    version_string = sys.modules["jax.version"].__version__
    return tuple(int(x) for x in version_string.split("."))


ArrayImpl = Union[
    ModuleType(
        "jaxlib.xla_extension",
        "ArrayImpl",
        condition=lambda: jax_version() < (0, 6, 0),
    ),
    ModuleType(
        "jaxlib._jax",
        "ArrayImpl",
        condition=lambda: jax_version() >= (0, 6, 0),
    ),
]
```

You might also run into a scenario where you want to express that an import is faithful.
You can specify this with the keyword argument `faithful`.
This sets the dunder `__faithful__` on the imported type.

Example:

```python
JaxTensor = ModuleType(
    "jaxlib._jax",
    "ArrayImpl",
    condition=lambda: _jax_version() >= (0, 6, 0),
    faithful=True,
)
```

% skip: end

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
<class 'plum.PromisedType[SpecialInt]'>

>>> from plum import resolve_type_hint

>>> resolve_type_hint(ProxyInt)
<class 'int'>
```
