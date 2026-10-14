# Benchmarks

These guard the dispatch paths that Plum optimises.
Every performance claim in a pull request should be a delta measured here, so that
claims from different PRs are comparable.

## Running them

```console
$ nox -s benchmark
```

An ordinary `pytest` run executes every benchmark once but does not time them:
`tests/conftest.py` disables timing unless `--benchmark-enable` is passed.
The options are set there rather than in `addopts`, so that `pytest-benchmark` is needed
only to run this directory.
Without the plugin, the rest of the suite still runs and only these tests error.

## Demonstrating that a change is faster

`pytest-benchmark` stores runs and compares them, which is how a PR shows its numbers:

```console
$ git checkout <base>
$ nox -s benchmark -- --benchmark-save=base
$ git checkout <branch>
$ nox -s benchmark -- --benchmark-compare=0001 --benchmark-compare-fail=median:5%
```

The comparison table goes in the PR description.
`--benchmark-compare-fail` makes the run exit non-zero on a regression, so it can also
be used as a local gate.

A base that predates this directory saves nothing: `nox -s benchmark` there runs the
old `tests/benchmark.py`, which ignores the flag and exits 0.
To compare against such a base, copy `tests/benchmarks/` onto it first.

Some cautions:

- **Interleave base and branch.**
  A machine can drift by several percent over a session, which is larger than some of
  the effects being measured, so alternate base and branch rather than running each
  once.
- **Compare medians, not minimums.**
  The minimum is the least noisy statistic, but it hides a change that only shows under
  realistic load.
- **Keep the minimum time per round.**
  `tests/conftest.py` raises `--benchmark-min-time` to 0.0005 s.
  At the default, a sub-microsecond benchmark runs too few iterations per round for
  the timer to resolve, and a comparison can report a double-digit change that is not
  there.
- **Confirm a surprising result with `timeit`** before believing it.
- **Check what you are measuring after building a wheel.**
  A `mypyc` build leaves `.so` files in `src/plum/`, and they shadow the editable
  install, so a later run silently measures the compiled build.
  `python -c "import plum; print(plum.COMPILED)"` says which one you have, and
  `rm -f src/plum/*.so` restores the interpreted one.

## CodSpeed

`pytest-codspeed` implements the same `benchmark` fixture and replaces
`pytest-benchmark`'s when both plugins are installed, so this suite runs unchanged under
`pytest tests/benchmarks --codspeed`.
CodSpeed measures CPU instructions rather than wall time, which is stable on shared CI
runners, so running it on every pull request would make the comparison automatic.
