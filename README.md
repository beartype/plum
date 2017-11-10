# Plum: Multiple Dispatch in Python

Everybody likes multiple dispatch, just like everybody likes plums.


## Examples
### Variable Arguments
```python
from plum import dispatch

@dispatch(int, [int])
def f(x, *xs):
    print(x, xs)
```

```
>>> f(1)
(1, ())
>>> f(1, 2)
(1, (2,))
>>> f(1, 2, 3)
(1, (2, 3))
```

#### Union Arguments
```python
from plum import dispatch

@dispatch(object)
def f(x):
    print('fallback')

@dispatch({int, str})
def f(x):
    print('int or str')
```


```
>>> f(1)
int or str
>>> f('1')
int or str
>>> f(1.0)
fallback
```


### Inheritance
```python
from plum import Dispatcher, Referentiable, Self

class Kernel(Referentiable):
    dispatch = Dispatcher(in_class=Self)
    
    @dispatch(Self)
    def __add__(self, other):
        return 'kernel'

class StationaryKernel(Kernel, Referentiable):
    dispatch = Dispatcher(in_class=Self)

    @dispatch(Self)
    def __add__(self, other):
        return 'stationary kernel'

kernel = Kernel()
stationary_kernel = StationaryKernel()
```


```
>>> kernel + 0
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "plum/function.py", line 144, in __call__
    raise e
plum.function.NotFoundLookupError: For function "__add__", signature (int) could not be resolved.
>>> kernel + kernel
'kernel'
>>> kernel + stationary_kernel
'kernel'
>>> stationary_kernel + kernel
'kernel'
>>> stationary_kernel + stationary_kernel
'stationary kernel'
```



