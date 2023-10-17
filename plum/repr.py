import inspect
import re
import sys
import types
import typing
from functools import partial
from typing import Any, Callable, Dict, Iterable

import rich
from rich.color import Color
from rich.style import Style
from rich.text import Text

__all__ = [
    "repr_short",
    "repr_type",
    "repr_source_path",
    "formatannotation",
]

py_version = sys.version_info.minor


path_style = Style(color=Color.from_ansi(7))
file_style = Style(bold=True, underline=True)

module_style = Style(color=Color.from_ansi(7))
class_style = Style(bold=True)


def repr_type(typ):
    if py_version > 8 and isinstance(typ, types.GenericAlias):
        return Text(repr(typ), style=class_style)

    if isinstance(typ, type):
        if typ.__module__ in ["builtins", "typing"]:
            return Text(typ.__qualname__, style=class_style)
        else:
            return Text(f"{typ.__module__}.", style=module_style) + Text(
                typ.__qualname__, style=class_style
            )
    if isinstance(typ, types.FunctionType):
        return Text(typ.__name__, style=module_style)

    return Text(repr(typ), style=class_style)


def repr_short(x):
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


def formatannotation(annotation, base_module=None):
    if getattr(annotation, "__module__", None) == "typing":

        def repl(match):
            text = match.group()
            return text.removeprefix("typing.")

        return re.sub(r"[\w\.]+", repl, repr(annotation))
    if isinstance(annotation, types.GenericAlias):
        return str(annotation)
    if isinstance(annotation, type):
        if annotation.__module__ in ("builtins", base_module):
            return annotation.__qualname__
        return annotation.__module__ + "." + annotation.__qualname__
    return repr(annotation)


def repr_source_path(function: Callable) -> Text:
    """Returns the string with the link to the
    file and line where the method implementation
    is defined.
    """
    try:
        fpath = inspect.getfile(function)
        fline = str(inspect.getsourcelines(function)[1])
        "file://" + fpath + "#" + fline

        import os

        # compress the path
        home_path = os.path.expanduser("~")
        fpath = fpath.replace(home_path, "~")

        # underline file name
        fname = os.path.basename(fpath)
        if fname.endswith(".py"):
            fpath = (
                Text(os.path.dirname(fpath), style=path_style)
                + Text("/")
                + Text(fname, style=file_style)
            )
        fpath = fpath + ":" + fline
        fpath.stylize("link {uri}")
    except OSError:
        fpath = Text()
    return fpath


def repr_pyfunction(function: Callable) -> Text:
    """Returns the string with the link to the
    file and line where the method implementation
    is defined.
    """
    res = Text(repr(function))
    res.append(" @ ")
    res.append_text(repr_source_path(function))
    return res


#####
# new
#####


def __repr_from_rich__(self) -> str:
    """
    default __repr__ that calls __rich__
    """
    # print("calling __repr_from_rich__")
    console = rich.get_console()
    with console.capture() as capture:
        console.print(self, end="")
    res = capture.get()
    # print("got ", res)
    return res


def _repr_mimebundle_from_rich_(
    self, include: Iterable[str], exclude: Iterable[str], **kwargs: Any
) -> Dict[str, str]:
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


def rich_repr(clz=None, str=False):
    """
    Class decorator setting the repr method to use
    `rich`.
    """
    if clz is None:
        return partial(rich_repr, str=str)
    clz.__repr__ = __repr_from_rich__
    clz._repr_mimebundle_ = _repr_mimebundle_from_rich_
    if str:
        clz.__str__ = __repr_from_rich__
    return clz
