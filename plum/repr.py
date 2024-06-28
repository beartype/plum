import inspect
import os
import sys
import types
import typing
from functools import partial
from typing import Any, Callable, Dict, Iterable, Optional, Type, TypeVar

import rich
from rich.color import Color
from rich.style import Style
from rich.text import Text

__all__ = [
    "repr_short",
    "repr_type",
    "repr_source_path",
    "repr_pyfunction",
    "rich_repr",
]

T = TypeVar("T")

path_style = Style(color=Color.from_ansi(7))
file_style = Style(bold=True, underline=True)

module_style = Style(color="grey66")
class_style = Style(bold=True)


def repr_type(x) -> Text:
    """Returns a :class:`rich.Text` representation of a type or module.

    Does some light syntax highlighting mimicking Julia, boldening class names and
    coloring module names with a lighter color.

    Args:
        x (object): Type or module.

    Returns:
        :class:`rich.Text`: Representation.
    """

    if isinstance(x, type):
        if x.__module__ in ["builtins", "typing", "typing_extensions"]:
            return Text(x.__qualname__, style=class_style)
        else:
            res = Text(f"{x.__module__}.", style=module_style)
            res += Text(x.__qualname__, style=class_style)
            return res

    if isinstance(x, types.ModuleType):
        return Text(x.__name__, style=module_style)

    return Text(repr(x), style=class_style)


def repr_short(x) -> str:
    """Representation as a string, but in shorter form. This just calls
    :func:`typing._type_repr`.

    Args:
        x (object): Object.

    Returns:
        str: Shorter representation of `x`.
    """
    # :func:`typing._type_repr` is an internal function, but it should be available in
    # Python versions 3.8 through 3.11.
    return typing._type_repr(x)


def _safe_getfile(obj) -> str:
    """Safer version of :func:`inspect.getfile`.

    Classes defined in PyBind, even if they pretend hard to be functions, like
    `jax.jit(fun)`, will raise an error if passed to `inspect.getfile`.

    This function will catch those errors and try harder to get the underlying file, and
    raise an error only if it cannot.

    This function can only raise an `OSError`.

    Args:
        obj (object): An object.

    Returns:
        str: Path to the file that defines `obj`.

    Raises:
        OSError: File that defines `obj` cannot be found.
    """
    try:
        return inspect.getfile(obj)
    except TypeError:
        # Raised when the function passed is a C-defined class. It might still contain
        # `__module__`, which can be used to backtrace the file that defines `obj`.
        if hasattr(obj, "__module__"):
            module = sys.modules.get(obj.__module__, None)
            if hasattr(module, "__file__"):
                return module.__file__

        raise OSError("Source code not available.") from None


def repr_source_path(function: Callable) -> Text:
    """Create a :class:`rich.Text` object with an hyperlink to the function definition.

    Args:
        function (Callable): A function.

    Returns:
        :class:`rich.Text` or None:
            Representation with a hyperlink to the source. If the introspection failed,
            it returns :obj:`None`.
    """

    try:
        f_path = _safe_getfile(function)
        f_line = inspect.getsourcelines(function)[1]
        uri = f"file://{f_path}#{f_line}"

        # Compress the path.
        home_path = os.path.expanduser("~")
        f_path = f_path.replace(home_path, "~")

        # Underline file name.
        f_name = os.path.basename(f_path)
        f_path = (
            Text(os.path.dirname(f_path), style=path_style)
            + Text("/")
            + Text(f_name, style=file_style)
        )
        f_path.append_text(Text(f":{f_line}"))
        f_path.stylize(f"link {uri}")
        return f_path
    except OSError:  # pragma: no cover
        return None


def repr_pyfunction(f: Callable) -> Text:
    """Create a :class:`rich.Text` object representation a function, including a link
    to the source definition created with :func:`repr_source_path`.

    Args:
        f (Callable): A function.

    Returns:
        :class:`rich.Text`: Representation of `f`.
    """
    res = Text(repr(f))
    source = repr_source_path(f)
    if source is not None:
        res.append(" @ ")
        res.append_text(source)
    return res


########################
# Rich class decorator #
########################


def __repr_from_rich__(self) -> str:
    """Default implementation of `__repr__` that calls :mod:`rich`.

    Returns:
        str: Representation of `self.`
    """
    console = rich.get_console()
    with console.capture() as capture:
        console.print(self, end="")
    res = capture.get()
    return res


def _repr_mimebundle_from_rich_(
    self,
    include: Iterable[str],
    exclude: Iterable[str],
    **kw_args: Any,
) -> Dict[str, str]:
    """Implementation of `_repr_mimebundle_` for better rendering in Jupyter.

    Args:
        include (Iterable[str]): Only these MIME types should be included.
        exclude (Iterable[str]): These MIME types should be excluded.
        **kw_args (object): Additional keyword arguments. These are ignored.

    Returns:
        dict[str, str]: Representation by MIME type.
    """
    from rich.jupyter import _render_segments

    console = rich.get_console()
    segments = list(console.render(self, console.options))  # type: ignore
    html = _render_segments(segments)
    text = console._render_buffer(segments)
    data = {"text/plain": text, "text/html": html}
    if include:
        data = {k: v for (k, v) in data.items() if k in include}
    if exclude:
        data = {k: v for (k, v) in data.items() if k not in exclude}
    return data


def rich_repr(cls: Optional[Type[T]] = None, str: bool = False) -> Type[T]:
    """Class decorator defining a `__repr__` method that calls :mod:`rich.`

    This also sets `_repr_mimebundle_` for better rendering in Jupyter.

    Args:
        cls (type, optional): Class to decorate. If `None`, this function returns a
            decorator.
        str (bool, optional): Also define `__str__`. Defaults to not defining
            `__str__`

    Returns:
        The decorated class. If cls is None, returns a decorator.
    """
    if cls is None:
        return partial(rich_repr, str=str)
    cls.__repr__ = __repr_from_rich__
    cls._repr_mimebundle_ = _repr_mimebundle_from_rich_
    if str:
        cls.__str__ = __repr_from_rich__
    return cls
