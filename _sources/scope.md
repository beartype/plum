# Scope of Functions

Consider the following package design.

**package/\_\_init\_\_.py**

```python
import a
import b
```

**package/a.py**

```python
from plum import dispatch

@dispatch
def f(x: int):
   return "int"
```

**package/b.py**

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

This could be what you want, but it can also be undesirable, because it means that
someone could accidentally overwrite your methods.
To keep your functions private, you can create new dispatchers:

**package/\_\_init\_\_.py**

```python
import a
import b
```

**package/a.py**

```python
from plum import Dispatcher

dispatch = Dispatcher()


@dispatch
def f(x: int):
   return "int"
```

**package/b.py**

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
NotFoundLookupError: For function "f", signature Signature(builtins.float) could not be resolved.

>>> from package.b import f

>>> f(1)
NotFoundLookupError: For function "f", signature Signature(builtins.int) could not be resolved.

>>> f(1.0)
'float'
```
