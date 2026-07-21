"""Generate the generic-dispatch timing table for docs/generics.md.

Run directly::

    uv run python docs/_scripts/time_generics.py

or via nox (which also builds the docs)::

    uv run nox -s docs

Output is written to docs/_generated/generics_timing.md, which is
included verbatim by docs/generics.md via the MyST {include} directive.
"""

import dataclasses
import pathlib
import timeit
import typing

import plum

T = typing.TypeVar("T")


# ── Faithful baseline ──────────────────────────────────────────────────────
# A bare `B` overload with no parameterized overloads.  Plum uses the fast
# faithful-cache path (cache key = type(arg), no __orig_class__ handling).


@dataclasses.dataclass
class B(typing.Generic[T]):
    x: T


d_faithful = plum.Dispatcher()


@d_faithful
def f_faithful(b: B) -> str:
    return "B"


# ── Generic dispatch ───────────────────────────────────────────────────────
# Three overloads on A: A[Any] (bare-instance fallback), A[int], A[str].
# Plum uses the two-tier generic cache, keyed on __orig_class__ when present.


@dataclasses.dataclass
class A(typing.Generic[T]):
    x: T


d_generic = plum.Dispatcher()


@d_generic
def f_generic(a: A[typing.Any]) -> str:
    return "A[Any]"


@d_generic
def f_generic(a: A[int]) -> str:
    return "A[int]"


@d_generic
def f_generic(a: A[str]) -> str:
    return "A[str]"


# ── Measure ────────────────────────────────────────────────────────────────

# Warm up all cache paths before measuring.
f_faithful(B(1))
f_generic(A(1))
f_generic(A[int](1))
f_generic(A[str]("x"))

N = 50_000

t_faithful = timeit.timeit(lambda: f_faithful(B(1)), number=N) / N * 1e6
t_any = timeit.timeit(lambda: f_generic(A(1)), number=N) / N * 1e6
t_int = timeit.timeit(lambda: f_generic(A[int](1)), number=N) / N * 1e6

rows = [
    ("f(B(1))", "faithful — bare `B` overload", t_faithful, 1.0),
    ("f(A(1))", "generic — `A[Any]` fallback", t_any, t_any / t_faithful),
    ("f(A[int](1))", "generic — `A[int]` overload", t_int, t_int / t_faithful),
]

# ── Write markdown table ───────────────────────────────────────────────────

lines = [
    "| Call | Scenario | µs / call | vs faithful |",
    "| :--- | :--- | ---: | ---: |",
]
for call, scenario, us, rel in rows:
    lines.append(f"| `{call}` | {scenario} | {us:.2f} | {rel:.1f}× |")

out = pathlib.Path(__file__).parent.parent / "_generated" / "generics_timing.md"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(lines) + "\n")
print(f"Written {out.relative_to(pathlib.Path(__file__).parent.parent.parent)}")
