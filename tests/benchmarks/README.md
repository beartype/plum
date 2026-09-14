# Benchmarks

These guard the dispatch paths that plum optimises. Every performance claim in a pull
request should be a delta measured here, so that claims from different PRs are
comparable.

## Running them

```console
$ nox -s benchmark
```

An ordinary `pytest` run collects them too, but does not time them: `tests/conftest.py`
disables timing unless `--benchmark-enable` is passed, so each benchmark body still
executes once per run and cannot silently rot. It is set there rather than in `addopts`
so that `pytest-benchmark` is required only to run this directory. Without the plugin
installed, `pytest` still collects and runs everything else -- measured, 222 passed --
and reports these as errors on the missing `benchmark` fixture rather than aborting
the session, which is what an `addopts` entry for an unrecognised argument does.

## Demonstrating that a change is faster

`pytest-benchmark` stores runs and diffs them, which is how a PR shows its numbers:

```console
$ git checkout <base>
$ nox -s benchmark -- --benchmark-save=base
$ git checkout <branch>
$ nox -s benchmark -- --benchmark-compare=0001 --benchmark-compare-fail=median:5%
```

The comparison table goes in the PR description. `--benchmark-compare-fail` makes the
run exit non-zero on a regression, so it can also be used as a local gate.

This works for any base that already has this directory. For an *earlier* base it does
not, and it fails quietly: `nox -s benchmark` there runs the old `tests/benchmark.py`,
which ignores the `--benchmark-save` argument, saves nothing, and still exits 0 -- so
the later `--benchmark-compare` has nothing to diff against. To measure across that
boundary, copy `tests/benchmarks/` onto the base and run the same harness on both
sides.

Cautions, all learned the hard way on this project:

- **Interleave, do not trust sequential runs.** A machine can drift by several percent
  across a session, which is larger than some of the effects being measured. For a
  small effect, alternate base and branch rather than running each once.
- **Compare medians, not minimums.** The minimum is the least noisy statistic but it
  also hides a change that only shows up under realistic load.
- **Keep the calibration floor.** `tests/conftest.py` sets `--benchmark-min-time` to
  0.0005, so it applies to `nox -s benchmark` and to a plain `pytest` alike. At the
  default, a sub-microsecond benchmark runs too few iterations per round, its median
  snaps to a quantum, and a comparison can report a double-digit change that is not
  there. This bit us: `test_invoke_and_call` showed a reproducible 294 -> 375 ns
  "regression" from a patch that does not touch that code, and `timeit` on the same
  two trees gave 282 vs 278 ns. With the floor raised, both read ~302 ns.
- **Confirm a surprising result outside the harness** before believing it. A direct
  `timeit` loop takes a minute and settles the question.
- **Scope `--benchmark-enable` to this directory.** The registration benchmarks build
  a `plum.Function` per iteration, and `Function._instances` is a list that never
  releases them, so a run leaves tens of thousands behind. That is harmless here, but
  `tests/test_cache.py` walks `Function._instances` before every timed call in its own
  setup, so running the whole tree with `--benchmark-enable` turns that walk
  quadratic and the run does not finish in any useful time. `nox -s benchmark` passes
  `tests/benchmarks`, which is why it is unaffected. (The registry becomes weak later
  in this series, which removes the interaction.)
- **Check what you are actually measuring after building a wheel.** A `mypyc` build
  leaves `.so` files in `src/plum/`, and they shadow the editable install, so a later
  benchmark run silently measures the compiled build. `python -c "import plum;
  print(plum.COMPILED)"` says which one you have; `rm -f src/plum/*.so` restores the
  interpreted one.

## Migrating to CodSpeed

The suite is written against the `benchmark` fixture, which is the reason to use
`pytest-benchmark` here rather than a hand-rolled timing loop: `pytest-codspeed`
implements the same fixture and, when both plugins are installed, replaces
`pytest-benchmark`'s with its own. So the migration changes no benchmark code at all.

1. Add `pytest-codspeed` to the `test_runtime` dependency group.
2. Add a workflow that runs the suite under CodSpeed's action:

   ```yaml
   name: Benchmarks
   on:
     pull_request:
     push:
       branches: [master]
   jobs:
     benchmarks:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v6
           with:
             python-version: "3.13"
         - run: uv sync --group dev --locked
         - uses: CodSpeedHQ/action@v4
           with:
             run: uv run --frozen pytest tests/benchmarks --codspeed
             token: ${{ secrets.CODSPEED_TOKEN }}
   ```

3. Add `CODSPEED_TOKEN` to the repository secrets.

Why do this at all, given the local flow above works: CodSpeed measures simulated CPU
instructions rather than wall time, so it is stable on shared CI runners where wall
time is not. That turns "each PR must demonstrate that it does not regress" from a
manual step into an automatic check on every pull request, with the base branch as the
comparison point.

Until that lands, the local save/compare flow above is the mechanism, and the numbers
live in PR descriptions.
