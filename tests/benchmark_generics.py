"""Benchmark generic dispatch performance vs. the pre-generics baseline.

Scenarios
---------
1. faithful_only        – f(x: int) only                   [no generic signatures]
2. faithful_two         – f(x: int) / f(x: str)            [no generic signatures]
3. generic_only         – f(x: list[int]) / f(x: list[str])[all generic signatures]
4. mixed                – f(x: int) / f(x: list[int])      [has_generic_signatures=True]
5. infer_vs_type        – raw micro-benchmark: infer_hint(x) vs type(x)

For scenarios 1–4 each path is measured:
  warm  – N calls after cache is hot (measures cache-hit overhead)
  cold  – cache cleared between every call (measures full resolve overhead)
"""

from time import perf_counter

from beartype.bite import infer_hint

import plum

# ── helpers ──────────────────────────────────────────────────────────────────


def benchmark(f, args, *, n: int = 5_000, burn: int = 50, setup=None) -> float:
    """Return average call time in microseconds."""
    for _ in range(burn):
        if setup:
            setup()
        f(*args)
    times = []
    for _ in range(n):
        if setup:
            setup()
        t0 = perf_counter()
        f(*args)
        times.append(perf_counter() - t0)
    times.sort()
    # Trim 5% tails to reduce noise.
    trim = max(1, n // 20)
    return sum(times[trim:-trim]) * 1e6 / (n - 2 * trim)


def row(label: str, warm_us: float, cold_us: float, baseline_warm: float | None = None):
    suffix = ""
    if baseline_warm is not None:
        ratio = warm_us / baseline_warm
        suffix = f"  ({ratio:+.0%} vs baseline warm)"
    print(f"  {label:<35}  warm={warm_us:6.2f} µs  cold={cold_us:6.2f} µs{suffix}")


# ── native baseline ───────────────────────────────────────────────────────────


def _native(x):
    pass


native = benchmark(_native, (42,))
print(f"\nNative call: {native:.3f} µs")
print()

# ── scenario 1: faithful only ─────────────────────────────────────────────────

print("## Scenario 1 – faithful only  (f(x: int))")

_d1 = plum.Dispatcher()


@_d1
def _f1(x: int):
    return x


warm1 = benchmark(_f1, (42,))
cold1 = benchmark(_f1, (42,), setup=_f1.clear_cache)
row("faithful_only", warm1, cold1)
_base_faithful_warm = warm1  # reference

# ── scenario 2: two faithful methods ─────────────────────────────────────────

print("\n## Scenario 2 – two faithful  (f(x: int) / f(x: str))")

_d2 = plum.Dispatcher()


@_d2
def _f2(x: int):
    return x


@_d2
def _f2(x: str):
    return x


warm2_int = benchmark(_f2, (42,))
warm2_str = benchmark(_f2, ("hi",))
cold2 = benchmark(_f2, (42,), setup=_f2.clear_cache)
row("faithful_two  int arg", warm2_int, cold2, _base_faithful_warm)
row("faithful_two  str arg", warm2_str, cold2, _base_faithful_warm)

# ── scenario 3: generic only ──────────────────────────────────────────────────

print("\n## Scenario 3 – generic only  (f(x: list[int]) / f(x: list[str]))")

_d3 = plum.Dispatcher()


@_d3
def _f3(x: list[int]):
    return x


@_d3
def _f3(x: list[str]):
    return x


_li = [1, 2, 3]
_ls = ["a", "b"]

warm3_int = benchmark(_f3, (_li,))
warm3_str = benchmark(_f3, (_ls,))
cold3 = benchmark(_f3, (_li,), setup=_f3.clear_cache)
row("generic_only  list[int] arg", warm3_int, cold3, _base_faithful_warm)
row("generic_only  list[str] arg", warm3_str, cold3, _base_faithful_warm)

# ── scenario 4: mixed faithful + generic ─────────────────────────────────────

print("\n## Scenario 4 – mixed  (f(x: int) / f(x: list[int]))")
print("   NOTE: before this change, the int arm was NEVER cached (is_faithful=False).")
print("   The warm-int number should be compared against cold4, not against baseline.")

_d4 = plum.Dispatcher()


@_d4
def _f4(x: int):
    return x


@_d4
def _f4(x: list[int]):
    return x


_int_arg = 42
_list_arg = [1, 2, 3]

warm4_int = benchmark(_f4, (_int_arg,))
warm4_list = benchmark(_f4, (_list_arg,))
cold4_int = benchmark(_f4, (_int_arg,), setup=_f4.clear_cache)
cold4_list = benchmark(_f4, (_list_arg,), setup=_f4.clear_cache)
row("mixed  int  arg  (warm)", warm4_int, cold4_int, _base_faithful_warm)
row("mixed  list arg  (warm)", warm4_list, cold4_list, _base_faithful_warm)
print(
    f"  {'mixed  int  arg  (cold)':<35}  cold={cold4_int:6.2f} µs  "
    f"(pre-change this was the ONLY path for int in a mixed fn)"
)
print(f"  {'mixed  list arg  (cold)':<35}  cold={cold4_list:6.2f} µs")

# ── scenario 5: infer_hint vs type() micro-benchmark ─────────────────────────

print("\n## Scenario 5 – infer_hint vs type()  (raw overhead per argument)")

_dur_type_int = benchmark(type, (42,), n=50_000)
_dur_infer_int = benchmark(infer_hint, (42,), n=50_000)
_dur_type_list = benchmark(type, ([1, 2, 3],), n=50_000)
_dur_infer_list = benchmark(infer_hint, ([1, 2, 3],), n=50_000)

print(f"  {'type(int)':<35}  {_dur_type_int:.4f} µs")
print(
    f"  {'infer_hint(int)':<35}  {_dur_infer_int:.4f} µs  "
    f"({_dur_infer_int / _dur_type_int:.1f}x type)"
)
print(f"  {'type(list)':<35}  {_dur_type_list:.4f} µs")
print(
    f"  {'infer_hint(list[int])':<35}  {_dur_infer_list:.4f} µs  "
    f"({_dur_infer_list / _dur_type_list:.1f}x type)"
)

# ── summary ───────────────────────────────────────────────────────────────────

print("\n## Summary")
print(f"  Faithful dispatch overhead vs native:  {warm1 / native:.1f}x")
print(f"  Generic  dispatch overhead vs native:  {warm3_int / native:.1f}x")
print(f"  Mixed    dispatch overhead vs native:  {warm4_int / native:.1f}x  (int arm)")
print(
    f"  Mixed    dispatch overhead vs native:  {warm4_list / native:.1f}x  (list arm)"
)


# ── scenario 6: __orig_class__ dispatch ──────────────────────────────────────

print("\n## Scenario 6 – __orig_class__  (Box[int](1) vs Box[str]('x'))")
print("   Requires the user to write Box[int](...) so Python sets __orig_class__.")
print("   beartype.door.is_bearable alone CANNOT distinguish Box[int] from Box[str].")

from typing import Generic, TypeVar as _TV  # noqa: E402

_T = _TV("_T")


class _BenchBox(Generic[_T]):
    def __init__(self, v: object) -> None:
        self.v = v


_d6 = plum.Dispatcher()


@_d6
def _f6(x: _BenchBox[int]) -> str:  # type: ignore[type-arg]
    return "int"


@_d6
def _f6(x: _BenchBox[str]) -> str:  # type: ignore[type-arg]
    return "str"


_box_int = _BenchBox[int](1)
_box_str = _BenchBox[str]("hello")

warm6_int = benchmark(_f6, (_box_int,))
warm6_str = benchmark(_f6, (_box_str,))
cold6 = benchmark(_f6, (_box_int,), setup=_f6.clear_cache)
row("orig_class  Box[int] arg", warm6_int, cold6, _base_faithful_warm)
row("orig_class  Box[str] arg", warm6_str, cold6, _base_faithful_warm)
