# Scope of Functions


## Dispatchers

% skip: start "Example code"

Consider the following package design.

`package/__init__.py`:

```python
import a
import b
```

`package/a.py`:

```python
from plum import dispatch


@dispatch
def f(x: int):
   return "int"
```

`package/b.py`:

```python
from plum import dispatch


@dispatch
def f(x: float):
   return "float"
```

In a design like this, the methods for `f` recorded by `dispatch` are _global_:

```python
>>> from package.a import f

>>> f(1.0)
'float'
```

This could be what you want, but it could also be undesirable.
In addition, by using the global `@dispatch`, someone could accidentally overwrite
your methods.

`other_package/some_file.py`:
```python
from plum import dispatch


# If another package happens to also define `f` for an `int`, then that overwrites
# your method!

@dispatch
def f(x: int):
    ...
```

To prevent this from happening and to keep your functions private, you can create new
dispatchers.

`package/__init__.py`:

```python
import a
import b
```

`package/a.py`:

```python
from plum import Dispatcher

dispatch = Dispatcher()


@dispatch
def f(x: int):
   return "int"
```

`package/b.py`:

```python
from plum import Dispatcher

dispatch = Dispatcher()


@dispatch
def f(x: float):
   return "float"
```


```python
>>> from package.a import f

>>> f(1)
'int'

>>> f(1.0)
NotFoundLookupError: For function `f`, `(1.0,)` could not be resolved.

>>> from package.b import f

>>> f(1)
NotFoundLookupError: For function `f`, `(1,)` could not be resolved.

>>> f(1.0)
'float'
```

% skip: end

## Redefinition Warnings

Whenever you create a dispatcher, you can set `warn_redefinition=True` to throw a warning whenever a method of a function overwrites another.
It is recommended to use this setting.

% invisible-code-block: python
%
% import warnings

```python
>>> from plum import Dispatcher

>>> dispatch = Dispatcher(warn_redefinition=True)

>>> @dispatch
... def f(x: int):
...    return x

>>> @dispatch
... def f(x: int):
...    return x

>>> with warnings.catch_warnings(record=True) as w:  # doctest:+ELLIPSIS
...     f(1)
...     print(w[0].message)
1
`Method(function_name='f', signature=Signature(int), return_type=typing.Any, implementation=<function f at 0x...>)` (`<doctest .../scope.md[0]>:1`) overwrites the earlier definition `Method(function_name='f', signature=Signature(int), return_type=typing.Any, implementation=<function f at 0x...>)` (`<doctest .../scope.md[0]>:1`).
```

Note that the redefinition warning is thrown whenever the function is run for the first
time, because methods are only registered whenever they are needed.
