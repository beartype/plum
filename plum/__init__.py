from ._version import version as __version__  # noqa: F401

from .dispatcher import *
from .function import *

# Because `function.py` is compiled with `cython`, we cannot use `inspect` to get the
# caller's frame, which in turn is necessary to detect whether we're using future
# annotations or not. We therefore patch `Function.dispatch` with an interpreted version
# in which we can safely use `inspect`.

import inspect as _inspect

_function_dispatch_original = Function.dispatch


def _function_dispatch(*args, **kw_args):
    frame = _inspect.currentframe().f_back
    return _function_dispatch_original(*args, **kw_args, _f_parent=frame)


Function.dispatch = _function_dispatch

from .parametric import *
from .promotion import *
from .resolvable import *
from .signature import *
from .type import *

from . import autoreload
