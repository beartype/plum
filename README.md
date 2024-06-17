# [Plum: Multiple Dispatch in Python](https://github.com/beartype/plum)

[![DOI](https://zenodo.org/badge/110279931.svg)](https://zenodo.org/badge/latestdoi/110279931)
[![CI](https://github.com/beartype/plum/workflows/CI/badge.svg?branch=master)](https://github.com/beartype/plum/actions?query=workflow%3ACI)
[![Coverage Status](https://coveralls.io/repos/github/beartype/plum/badge.svg?branch=master&service=github)](https://coveralls.io/github/beartype/plum?branch=master)
[![Latest Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://beartype.github.io/plum)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Everybody likes multiple dispatch, just like everybody likes plums.

The design philosophy of Plum is to provide an implementation of multiple dispatch that is Pythonic, yet close to how [Julia](http://julialang.org/) does it.
[See here for a comparison between Plum, `multipledispatch`, and `multimethod`.](https://beartype.github.io/plum/comparison.html)

*Note:*
Plum 2 is now powered by [Beartype](https://github.com/beartype/beartype)!
If you notice any issues with the new release, please open an issue.

# Installation

Plum requires Python 3.8 or higher.

```bash
pip install plum-dispatch
```

# [Documentation](https://beartype.github.io/plum)

See [here](https://beartype.github.io/plum).

# What's This?

Plum brings your type annotations to life:

```python
from numbers import Number

from plum import dispatch


@dispatch
def f(x: str):
    return "This is a string!"


@dispatch
def f(x: int):
    return "This is an integer!"


@dispatch
def f(x: Number):
    return "This is a general number, but I don't know which type."
```

```python
>>> f("1")
'This is a string!'

>>> f(1)
'This is an integer!'

>>> f(1.0)
'This is a number, but I don't know which type.'

>>> f(object())
NotFoundLookupError: `f(<object object at 0x7fd3b01cd330>)` could not be resolved.

Closest candidates are the following:
    f(x: str)
        <function f at 0x7fd400644ee0> @ /<ipython-input-2-c9f6cdbea9f3>:6
    f(x: int)
        <function f at 0x7fd3a0235ca0> @ /<ipython-input-2-c9f6cdbea9f3>:11
    f(x: numbers.Number)
        <function f at 0x7fd3a0235d30> @ /<ipython-input-2-c9f6cdbea9f3>:16
```


> [!IMPORTANT]
> Dispatch, as implemented by Plum, is based on the _positional_ arguments to a function.
> Keyword arguments are not used in the decision making for which method to call.
> In particular, this means that _positional arguments without a default value must
> always be given as positional arguments_!
>
> Example:
> ```python
> from plum import dispatch
>
> @dispatch
> def f(x: int):
>    return x
>
> >>> f(1)        # OK
> 1
>
> >> try: f(x=1)  # Not OK
> ... except Exception as e: print(f"{type(e).__name__}: {e}")
> NotFoundLookupError: `f()` could not be resolved...
> ```


This also works for multiple arguments, enabling some neat design patterns:

```python
from numbers import Number, Real, Rational

from plum import dispatch


@dispatch
def multiply(x: Number, y: Number):
    return "Performing fallback implementation of multiplication..."


@dispatch
def multiply(x: Real, y: Real):
    return "Performing specialised implementation for reals..."


@dispatch
def multiply(x: Rational, y: Rational):
    return "Performing specialised implementation for rationals..."
```

```python
>>> multiply(1, 1)
'Performing specialised implementation for rationals...'

>>> multiply(1.0, 1.0)
'Performing specialised implementation for reals...'

>>> multiply(1j, 1j)
'Performing fallback implementation of multiplication...'

>>> multiply(1, 1.0)  # For mixed types, it automatically chooses the right optimisation!
'Performing specialised implementation for reals...'
```
# Projects Using Plum

The following projects are using Plum to do multiple dispatch!
Would you like to add your project here?
Please feel free to open a PR to add it to the list!

- [Coordinax](https://github.com/GalacticDynamics/coordinax) implements coordinates in JAX.
- [GPAR](https://github.com/wesselb/gpar) is an implementation of the [Gaussian Process Autoregressive Model](https://arxiv.org/abs/1802.07182).
- [GPCM](https://github.com/wesselb/gpcm) is an implementation of various [Gaussian Process Convolution Models](https://arxiv.org/abs/2203.06997).
- [Galax](https://github.com/GalacticDynamics/galax) does galactic and gravitational dynamics.
- [Geometric Kernels](https://github.com/GPflow/GeometricKernels) implements kernels on non-Euclidean spaces, such as Riemannian manifolds, graphs, and meshes.
- [LAB](https://github.com/wesselb/lab) uses Plum to provide backend-agnostic linear algebra (something that works with PyTorch/TF/JAX/etc).
- [MLKernels](https://github.com/wesselb/mlkernels) implements standard kernels.
- [MMEval](https://github.com/open-mmlab/mmeval) is a unified evaluation library for multiple machine learning libraries.
- [Matrix](https://github.com/wesselb/matrix) extends LAB and implements structured matrix types, such as low-rank matrices and Kronecker products.
- [NetKet](https://github.com/netket/netket), a library for machine learning with JAX/Flax targeted at quantum physics, uses Plum extensively to pick the right, efficient implementation for a large combination of objects that interact.
- [NeuralProcesses](https://github.com/wesselb/neuralprocesses) is a framework for composing Neural Processes.
- [OILMM](https://github.com/wesselb/oilmm) is an implementation of the [Orthogonal Linear Mixing Model](https://arxiv.org/abs/1911.06287).
- [PySAGES](https://github.com/SSAGESLabs/PySAGES) is a suite for advanced general ensemble simulations.
- [Quax](https://github.com/patrick-kidger/quax) implements multiple dispatch over abstract array types in JAX.
- [Unxt](https://github.com/GalacticDynamics/unxt) implements unitful quantities in JAX.
- [Varz](https://github.com/wesselb/varz) uses Plum to provide backend-agnostic tools for non-linear optimisation.

[See the docs for a comparison of Plum to other implementations of multiple dispatch.](https://beartype.github.io/plum/comparison.html)
