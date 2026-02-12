__all__ = ["is_bearable"]

from functools import partial

from beartype import (
    BeartypeConf as _BeartypeConf,
    BeartypeStrategy as _BeartypeStrategy,
)
from beartype.door import is_bearable as _is_bearable

# Ensure that type checking is always entirely correct! The default O(1) strategy
# is super fast, but might yield unpredictable dispatch behaviour. The O(n) strategy
# actually is not yet available, but we can already opt in to use it.
is_bearable = partial(_is_bearable, conf=_BeartypeConf(strategy=_BeartypeStrategy.On))
