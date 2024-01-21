import sys
from typing import Literal

if sys.version_info < (3, 9):
    import typing_extensions

    get_type_hints = typing_extensions.get_type_hints
    get_origin = typing_extensions.get_origin
    get_args = typing_extensions.get_args

    def is_literal(x):
        return x == Literal and not isinstance(x, typing_extensions.Annotated)

else:
    import typing

    get_type_hints = typing.get_type_hints
    get_origin = typing.get_origin
    get_args = typing.get_args

    def is_literal(x):
        return x == Literal