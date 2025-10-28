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

## Performance and Faithful Types

Plum achieves performance by caching the dispatch process.
Unfortunately, efficient caching is not always possible.
Efficient caching is possible for so-called _faithful_ types.

% skip: next "Definition"

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
>>> %timeit add_5_faithful(1)  # doctest:+SKIP
585 ns ± 6.2 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)

>>> %timeit add_5_unfaithful(1)  # doctest:+SKIP
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

% skip: next

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
>>> def jax_version():
...     import sys
...     version_string = sys.modules["jax.version"].__version__
...     return tuple(int(x) for x in version_string.split("."))

>>> ArrayImpl = Union[
...     ModuleType(
...         "jaxlib.xla_extension",
...         "ArrayImpl",
...         condition=lambda: jax_version() < (0, 6, 0),
...     ),
...     ModuleType(
...         "jaxlib._jax",
...         "ArrayImpl",
...         condition=lambda: jax_version() >= (0, 6, 0),
...     ),
... ]
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
<class 'plum.type.PromisedType[SpecialInt]'>

>>> from plum import resolve_type_hint

>>> resolve_type_hint(ProxyInt)
<class 'int'>
```
