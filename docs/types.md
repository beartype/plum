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
Efficient caching is possible for so-called _cacheable_ types. The dispatch result for
an argument `x` is cached under a key that captures `type(x)` and, only when some
method needs it, the identity of `x` when `x` is itself a class, the value of `x`
when `x` is something a `Literal` could match, and `x.__orig_class__` when `x` is
an instance of a parametrised user generic. An instance of a *subclass* of a
literal type is keyed on its identity rather than its value, since its `__eq__` is
user code; identity is finer than the value, so that is always correct and only
shares less. `cache_key(x)` returns that key, as a
tuple whose slots are an implementation detail. A function whose methods are all
faithful needs none of the extra slots and is keyed on `type(x)` directly.

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

Every faithful type is cacheable, and two important kinds are cacheable without being
faithful:

- `type[X]` (or `typing.Type[X]`): `issubclass(x, X)` depends on the identity of the
  class `x`, which `cache_key` captures.
- `Literal[...]`: the match depends on the *value* of `x`, likewise captured.

For example, `int` is faithful, since `type(1) == int`; but `Literal[1]` is not
faithful, since `issubclass(int, Literal[1])` is false. It is still cacheable, so
dispatching on it is fast.

```{admonition} Caching a `Literal` is bounded; caching `type[X]` is not
:class: warning
A key slot holds a strong reference to what it captures -- that is what makes
identity-based keying sound. A function dispatching on `Literal` therefore gets one
entry per distinct *value* ever passed, which for `Literal["ready"]` beside a `str`
fallback would grow with the caller's data, so that cache stops growing at 4096
entries; beyond it, arguments simply resolve as they did before `Literal` was cacheable
at all. A function dispatching on `type[X]` gets one entry per distinct argument class
and is *not* capped, since classes are bounded in practice -- but dynamically created
classes stay alive for the function's lifetime. Call `f.clear_cache()` or
`plum.clear_all_cache()` to release them.
```

Whether a function's types are cacheable decides which of two caches it uses.

* **Trust.** If every method uses only cacheable types, then the cache key
  determines which method matches, so the method is memoised under that key. A
  repeated call is one dictionary lookup and no type checking at all.
* **Verify.** If any method uses an uncacheable type, then no key determines the
  method, and nothing may be trusted without checking. The runtime types of the
  arguments do, however, determine which methods could *possibly* match, so those
  are memoised instead, and every call verifies that narrowed list against the
  actual arguments. This is much slower than a trusted hit, but the methods ruled
  out by the argument types are never checked again.

Both caches are cleared by `f.clear_cache()` and `clear_all_cache()`.

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
585 ns ± 6.2 ns per loop (mean ± std. dev. of 7 runs, 1,000,000 loops each)

>>> %timeit add_5_uncacheable([1])  # doctest:+SKIP
6.24 µs ± 68.9 ns per loop (mean ± std. dev. of 7 runs, 100,000 loops each)
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
unparametrised method:

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

Whether one parametrisation is a subtype of another — that is, how a `TypeVar`'s
variance is interpreted — is Beartype's decision, not Plum's.

A parametrised *user* generic is cacheable, though not faithful: whether an argument
matches depends on its `__orig_class__`, and the pair `(type(x), x.__orig_class__)` is
a bounded key, so dispatch on it is cached like any other. The unparametrised class
stays faithful.

Parametrised *builtins* are the ones that are not cacheable. Beartype decides
`list[int]` by inspecting the elements, which no key derived from the argument can
capture, so a function dispatching on one uses the **verify** cache described above.

```python
>>> from plum import is_cacheable

>>> is_cacheable(Box[int])
True

>>> is_cacheable(Box)
True

>>> is_cacheable(list[int])
False
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
