# Benchmarks

These guard the dispatch paths that plum optimises. Every performance claim in a pull
request should be a delta measured here, so that claims from different PRs are
comparable.

## Running them

```console
$ nox -s benchmark
```

An ordinary `pytest` run collects them too, but does not time them: `addopts` carries
`--benchmark-disable`, so each benchmark body still executes once per run and cannot
silently rot.

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

Two cautions, both learned the hard way on this project:

- **Interleave, do not trust sequential runs.** A machine can drift by several percent
  across a session, which is larger than some of the effects being measured. For a
  small effect, alternate base and branch rather than running each once.
- **Compare medians, not minimums.** The minimum is the least noisy statistic but it
  also hides a change that only shows up under realistic load.
- **Keep the calibration floor.** `nox -s benchmark` passes
  `--benchmark-min-time=0.0005`. At pytest-benchmark's default, a sub-microsecond
  benchmark runs too few iterations per round for the timer to resolve, its median
  snaps to a quantum, and a comparison can report a double-digit change that is not
  there. This bit us: `test_invoke_and_call` showed a reproducible 294 -> 375 ns
  "regression" from a patch that does not touch that code, and `timeit` on the same
  two trees gave 282 vs 278 ns. With the floor raised, both read ~302 ns.
- **Confirm a surprising result outside the harness** before believing it. A direct
  `timeit` loop takes a minute and settles the question.
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
