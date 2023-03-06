# Scope of Functions

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
