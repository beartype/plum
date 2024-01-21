import sys

__all__ = ["get_type_hints", "get_origin", "get_args", "Annotated"]

# Before Python 3.9, e.g. `get_type_hints` does not include the keyword argument
# `include_extras`, so we take `get_type_hints` from `typing_extensions` instead,
# which backports support for `include_extras`.

if sys.version_info < (3, 9):  # pragma: specific no cover 3.9 3.10 3.11
    import typing_extensions

    get_type_hints = typing_extensions.get_type_hints
    get_origin = typing_extensions.get_origin
    get_args = typing_extensions.get_args
    Annotated = typing_extensions.Annotated


else:  # pragma: specific no cover 3.8
    import typing

    get_type_hints = typing.get_type_hints
    get_origin = typing.get_origin
    get_args = typing.get_args
    Annotated = typing.Annotated
