from typing import Literal

import pytest

import plum
from .util import benchmark


def assert_cache_performance(f, f_native):
    # Time the performance of a native call.
    dur_native = benchmark(f_native, (1,), n=250, burn=10)

    def resolve_registrations():
        for f in plum.Function._instances:
            f._resolve_pending_registrations()

    def setup_no_cache():
        plum.clear_all_cache()
        resolve_registrations()

    # Time the performance of a cache miss.
    dur_first = benchmark(f, (1,), n=250, burn=10, setup=setup_no_cache)

    # Time the performance of a cache hit.
    plum.clear_all_cache()
    resolve_registrations()
    dur = benchmark(f, (1,), n=250, burn=10)

    # A cached call should not be more than 50 times slower than a native call.
    assert dur <= 50 * dur_native

    # A first call should not be more than 2000 times slower than a cached call.
    assert dur_first <= 2000 * dur

    # The cached call should be at least 4 times faster than a first call.
    assert dur <= dur_first / 4


def test_cache_function(dispatch: plum.Dispatcher):
    def f_native(x):
        pass

    @dispatch
    def f(x):
        pass

    @dispatch
    def f(x: int | float):
        pass

    @dispatch
    def f(x: int | float | str):
        pass

    # Test performance.
    assert_cache_performance(f, f_native)

    # Test cache correctness.
    assert f(1) is None

    @dispatch
    def f(x: int):
        return 1

    assert f(1) == 1


# This class needs to be in the global scope, otherwise it cannot its methods cannot
# obtains a reference to it.


class A:
    _dispatch = plum.Dispatcher()

    @_dispatch
    def __call__(self, x: int):
        pass

    @_dispatch
    def __call__(self, x: str):
        pass

    @_dispatch
    def go(self, x: int):
        pass

    @_dispatch
    def go(self, x: str):
        pass

    @_dispatch
    def go_again(self, x: int):
        pass

    @_dispatch
    def go_again(self, x: str):
        pass


def test_cache_class():
    class ANative:
        def __call__(self, x):
            pass

        def go(self, x):
            pass

        def go_again(self, x):
            pass

    a_native = ANative()
    a = A()

    # Test performance of calls.
    assert_cache_performance(a, a_native)

    # Test performance of method calls.
    assert_cache_performance(lambda x: a.go(x), lambda x: a_native.go(x))

    # Test performance of static calls.
    assert_cache_performance(
        lambda x: A.go_again(a, x),
        lambda x: ANative.go_again(a_native, x),
    )


def test_cache_clearing(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return 1

    @dispatch
    def f(x: float):
        return 2

    assert len(f._cache) == 0
    assert len(f._resolver) == 0

    assert f(1) == 1
    # Check that cache is used.
    assert len(f._cache) == 1
    assert len(f._resolver) == 2

    # Clear via the dispatcher.
    dispatch.clear_cache()
    assert len(f._cache) == 0
    assert len(f._resolver) == 0

    # Run the function again.
    assert f(1) == 1
    assert len(f._cache) == 1
    assert len(f._resolver) == 2

    # Clear via `clear_all_cache`.
    plum.clear_all_cache()
    assert len(f._cache) == 0
    assert len(f._resolver) == 0

    # Run the function one last time.
    assert f(1) == 1
    assert len(f._cache) == 1
    assert len(f._resolver) == 2


def test_cache_unfaithful(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return 1

    @dispatch
    def f(x: list[int]):
        return 2

    # Since `f` is not faithful, no method should be cached.
    assert f(1) == 1
    assert f([1]) == 2
    assert len(f._cache) == 0
    # The methods to consider are cached instead, one bucket per argument type.
    assert set(f._verify_cache) == {(int,), (list,)}


def test_type_dispatch_is_cached(dispatch):
    @dispatch
    def g(x: type[int]):
        return "type[int]"

    @dispatch
    def g(x: type[str]):
        return "type[str]"

    g._resolve_pending_registrations()
    assert g._resolver.is_cacheable and not g._resolver.is_faithful
    assert len(g._cache) == 0
    assert g(int) == "type[int]"
    assert g(str) == "type[str]"
    assert len(g._cache) == 2  # keyed by identity, one entry per class


def test_faithful_class_args_share_one_entry(dispatch):
    @dispatch
    def h(x: object):
        return "object"

    h._resolve_pending_registrations()
    assert h._resolver.is_faithful
    for cls in (int, str, float, list, dict):
        assert h(cls) == "object"
    assert len(h._cache) == 1  # faithful ⇒ keyed on type(x)=type, one bucket


def test_late_type_registration_invalidates_plain_type_keys(dispatch):
    # The one path that could mix key shapes in a single dict: entries accumulated
    # while the function was faithful are keyed on `type(x)`, but registering a
    # `type[X]` method rebinds the key callable to the identity-aware one.
    @dispatch
    def f(x: object):
        return "object"

    f._resolve_pending_registrations()
    assert f(int) == "object"
    assert f(str) == "object"
    # Faithful: both class arguments land in the same `(type,)` bucket.
    assert set(f._cache) == {(type,)}

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    # Registration is lazy, so resolving it is what invalidates the cache.
    f._resolve_pending_registrations()
    assert f._cache == {}

    assert f(int) == "type[int]"
    assert f(str) == "object"
    # No stale `(type,)` key survives: every key is now `((type(x), identity),)`.
    assert len(f._cache) == 2
    assert all(len(k) == 1 and len(k[0]) == 2 for k in f._cache)


def test_spec_survives_clear_cache_with_reregister(dispatch):
    """`clear_cache(reregister=True)` installs a fresh, faithful resolver whose
    methods are only pending. The key callable used for the next call must be the
    one that resolver ends up with, not a stale faithful `type`."""

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    @dispatch
    def f(x: object):
        return "object"

    assert f(int) == "type[int]"
    f.clear_cache(reregister=True)
    assert f(str) == "object"
    assert f(int) == "type[int]"


def test_literal_dispatch_is_cached(dispatch):
    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: Literal[2]):
        return "two"

    @dispatch
    def f(x: int):
        return "int"

    f._resolve_pending_registrations()
    assert f._resolver.is_cacheable and not f._resolver.is_faithful
    assert len(f._cache) == 0

    assert f(1) == "one"
    assert f(2) == "two"
    assert f(3) == "int"
    # Distinct literal values must not collide: one entry each.
    assert len(f._cache) == 3
    # And the cached answers must still be the right ones.
    assert (f(1), f(2), f(3)) == ("one", "two", "int")
    assert len(f._cache) == 3


def test_literal_dispatch_keeps_bool_and_int_apart(dispatch):
    # Beartype matches `x` against `Literal[v]` iff `isinstance(x, type(v))` and
    # `x == v`, so `True` matches `Literal[1]` but `1` does not match `Literal[True]`.
    assert plum._bear.is_bearable(True, Literal[1])
    assert not plum._bear.is_bearable(1, Literal[True])

    @dispatch
    def f(x: Literal[True]):
        return "true"

    @dispatch
    def f(x: int):
        return "int"

    assert f(True) == "true"
    assert f(1) == "int"
    assert f(0) == "int"
    # `True == 1`, so only the type slot of the key keeps these entries apart.
    assert len(f._cache) == 3


def test_literal_dispatch_covers_subclasses(dispatch):
    class MyInt(int):
        pass

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: int):
        return "int"

    # A subclass instance does match a `Literal`, so its value must be keyed.
    assert f(MyInt(1)) == "one"
    assert f(MyInt(2)) == "int"
    assert f(MyInt(1)) == "one"


def test_literal_dispatch_unhashable_argument(dispatch):
    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: object):
        return "object"

    # An unhashable argument must not make the cache key raise.
    assert f([1, 2]) == "object"
    assert f({"a": 1}) == "object"
    assert f(1) == "one"


def test_literal_and_type_dispatch_mixed(dispatch):
    from plum._type import KeyPart

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    @dispatch
    def f(x: object):
        return "object"

    f._resolve_pending_registrations()
    assert f._resolver.cache_spec == {KeyPart.IDENTITY, KeyPart.VALUE}

    assert f(1) == "one"
    assert f(int) == "type[int]"
    assert f(2) == "object"
    assert f(str) == "object"
    assert len(f._cache) == 4


def test_type_dispatch_does_not_capture_a_value_slot(dispatch):
    from plum._type import KeyPart

    @dispatch
    def g(x: type[int]):
        return "type[int]"

    g._resolve_pending_registrations()
    assert g._resolver.cache_spec == {KeyPart.IDENTITY}
    assert g(int) == "type[int]"
    # `(type(x), _identity(x))`: no value slot for a `type[X]`-only resolver.
    assert all(len(k) == 1 and len(k[0]) == 2 for k in g._cache)


def test_literal_dispatch_subclass_with_untrustworthy_equality(dispatch):
    """A subclass may define a non-transitive `__eq__`, so its value cannot be keyed.

    `W(1) == W(2)` is `True` with equal hashes, so value-keying puts them in the
    same cache bucket — yet `W(1) == 1` and `W(2) != 1`, so they must dispatch
    differently. Only identity is fine enough to key such an argument.
    """

    class W(int):
        def __hash__(self):
            return 0

        def __eq__(self, other):
            if type(other) is W:
                return True
            return int.__eq__(self, other)

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: int):
        return "int"

    assert f(W(1)) == "one"
    assert f(W(2)) == "int"
    # And in the other warm-up order.
    f.clear_cache()
    assert f(W(2)) == "int"
    assert f(W(1)) == "one"


def test_literal_dispatch_uses_identity_for_subclasses(dispatch):
    """End-to-end exercise of the `_Identity` fallback through actual dispatch."""
    from plum._type import _Identity

    class MyInt(int):
        pass

    @dispatch
    def f(x: Literal[1]):
        return "one"

    @dispatch
    def f(x: int):
        return "int"

    a, b = MyInt(1), MyInt(1)
    assert f(a) == "one"
    assert f(b) == "one"
    # Two equal-but-distinct subclass instances get separate, identity-keyed entries.
    assert len(f._cache) == 2
    assert all(isinstance(k[0][-1], _Identity) for k in f._cache)


def test_literal_dispatch_cache_is_bounded(dispatch):
    """A `Literal` method plus caller-controlled values must not grow the cache
    without bound. Dispatch stays correct past the limit; only the memoisation
    stops."""
    from plum._function import _VALUE_CACHE_LIMIT

    @dispatch
    def f(x: Literal["ready"]):
        return "ready"

    @dispatch
    def f(x: str):
        return "other"

    for i in range(_VALUE_CACHE_LIMIT + 100):
        assert f(f"v{i}") == "other"

    assert len(f._cache) == _VALUE_CACHE_LIMIT
    # Beyond the limit, resolution still gives the right answer.
    assert f("ready") == "ready"
    assert f("v0") == "other"
    assert len(f._cache) == _VALUE_CACHE_LIMIT


def test_identity_only_dispatch_cache_is_not_bounded(dispatch):
    """The bound applies to `VALUE` resolvers only: classes are bounded already."""
    from plum._function import _VALUE_CACHE_LIMIT

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    @dispatch
    def f(x: object):
        return "object"

    n = _VALUE_CACHE_LIMIT + 10
    for i in range(n):
        assert f(type(f"C{i}", (), {})) == "object"

    assert len(f._cache) > _VALUE_CACHE_LIMIT


# The verify cache: an uncacheable function cannot memoise a method, but it can
# memoise which methods are worth considering for given bare argument types.


def test_verify_cache_narrows_the_methods_considered(dispatch):
    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    @dispatch
    def f(x: int):
        return "int"

    assert f([1]) == "list[int]"
    assert f(["a"]) == "list[str]"
    assert f(1) == "int"

    # Uncacheable, so no method is memoised.
    assert len(f._cache) == 0
    # But the methods that could possibly match are, bucketed by bare types.
    assert set(f._verify_cache) == {(list,), (int,)}
    # A `list` argument can never match `int`, and vice versa.
    assert len(f._verify_cache[(list,)]) == 2
    assert len(f._verify_cache[(int,)]) == 1


def test_verify_cache_is_invalidated_by_registration(dispatch):
    @dispatch
    def f(x: list[int]):
        return "list[int]"

    # Warm the bucket for `list` arguments.
    assert f([1]) == "list[int]"
    assert set(f._verify_cache) == {(list,)}

    @dispatch
    def f(x: list[str]):
        return "list[str]"

    # The new method must make it into the bucket for `list`.
    assert f(["a"]) == "list[str]"
    assert f([1]) == "list[int]"


def test_verify_cache_clearing(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: list[int]):
        return "list[int]"

    assert f([1]) == "list[int]"
    assert len(f._verify_cache) == 1

    dispatch.clear_cache()
    assert f._verify_cache is None

    assert f([1]) == "list[int]"
    assert len(f._verify_cache) == 1

    plum.clear_all_cache()
    assert f._verify_cache is None


def test_verify_cache_preserves_ambiguity(dispatch):
    @dispatch
    def f(x: list[int], y: object):
        return 1

    @dispatch
    def f(x: object, y: list[int]):
        return 2

    # Cold: nothing is cached yet.
    with pytest.raises(plum.AmbiguousLookupError):
        f([1], [1])
    # The bucket is now warm, and the same call must still be ambiguous.
    assert set(f._verify_cache) == {(list, list)}
    with pytest.raises(plum.AmbiguousLookupError):
        f([1], [1])

    # Warming the very same bucket with an unambiguous call changes nothing.
    assert f([1], ["a"]) == 1
    with pytest.raises(plum.AmbiguousLookupError):
        f([1], [1])


def test_verify_cache_preserves_not_found(dispatch):
    @dispatch
    def f(x: list[int]):
        return 1

    @dispatch
    def f(x: tuple[int, ...]):
        return 2

    for _ in range(2):  # Cold, then warm.
        with pytest.raises(plum.NotFoundLookupError) as e:
            f(["a"])
        # The error reports all methods, not just the narrowed ones.
        assert len(e.value.methods) == 2


def test_verify_cache_preserves_precedence(dispatch):
    @dispatch(precedence=1)
    def f(x: list[int], y: object):
        return 1

    @dispatch
    def f(x: object, y: list[int]):
        return 2

    # Ambiguous but for the precedence, cold and warm.
    assert f([1], [1]) == 1
    assert f([1], [1]) == 1


def test_verify_cache_handles_varargs_and_arities(dispatch):
    @dispatch
    def f(x: int, *xs: list[int]):
        return "varargs"

    @dispatch
    def f(x: int):
        return "one"

    @dispatch
    def f(x: int, y: int):
        return "two"

    assert f(1) == "one"
    assert f(1, 2) == "two"
    assert f(1, [1]) == "varargs"
    assert f(1, [1], [2]) == "varargs"
    # A fixed-arity method is only ever in the bucket of its own arity. The varargs
    # method can match any arity, but only for arguments its varargs type admits:
    # it is in the `(int,)` bucket, where the varargs go unused, but not in the
    # `(int, int)` one, where `2` can never be a `list[int]`.
    assert len(f._verify_cache[(int,)]) == 2
    assert len(f._verify_cache[(int, int)]) == 1
    assert len(f._verify_cache[(int, list)]) == 1
    assert len(f._verify_cache[(int, list, list)]) == 1


def test_verify_bucket_is_not_poisoned_by_a_class_liar(dispatch):
    """Narrowing must not depend on anything but the runtime types.

    A bucket is keyed on `tuple(map(type, args))` and reused for every call with
    those types, so `might_match` has to answer the same for all of them. It used to
    ask `isinstance(v, origin)`, which consults `v.__class__` -- and two values of
    one type can answer differently. The bucket built from the first one then ruled
    out a method the second genuinely matches.
    """

    class Chameleon:
        """Same `type()` for both instances; only `__class__` differs."""

        def __init__(self, pretend, data):
            self.pretend, self.data = pretend, data

        @property
        def __class__(self):  # noqa: PLW3201
            return list if self.pretend else Chameleon

        def __iter__(self):
            return iter(self.data)

        def __len__(self):
            return len(self.data)

        def __getitem__(self, i):
            return self.data[i]

    @dispatch
    def f(x: list[int]):
        return "list[int]"

    @dispatch
    def f(x: object):
        return "object"

    hot, cold = Chameleon(True, [1, 2, 3]), Chameleon(False, [1, 2, 3])
    assert type(hot) is type(cold)
    # `hot` really does match `list[int]`, and `cold` really does not.
    assert plum._bear.is_bearable(hot, list[int])
    assert not plum._bear.is_bearable(cold, list[int])

    # Whichever arrives first, both must get the method full resolution would pick.
    assert f(cold) == "object"
    assert f(hot) == "list[int]"


def test_verify_bucket_is_not_poisoned_for_a_faithful_hint(dispatch):
    """The same failure, on the branch that handles *faithful* hints.

    `list` is faithful, so `_might_match_hint` takes its exact fast path -- which
    asks `is_bearable`, and so consults `__class__` just as the subscripted case
    does. Faithfulness is the assumption that `isinstance(x, t)` agrees with
    `issubclass(type(x), t)`, and a `__class__` override is exactly what breaks it.
    """

    class Chameleon:
        def __init__(self, pretend, data):
            self.pretend, self.data = pretend, data

        @property
        def __class__(self):  # noqa: PLW3201
            return list if self.pretend else Chameleon

        def __iter__(self):
            return iter(self.data)

        def __len__(self):
            return len(self.data)

        def __getitem__(self, i):
            return self.data[i]

    @dispatch
    def f(x: list):
        return "list"

    @dispatch
    def f(x: dict[str, int]):  # keeps the resolver uncacheable, so tier two runs
        return "dict"

    @dispatch
    def f(x: object):
        return "object"

    hot, cold = Chameleon(True, [1, 2, 3]), Chameleon(False, [1, 2, 3])
    assert plum._bear.is_bearable(hot, list)
    assert not plum._bear.is_bearable(cold, list)

    assert f(cold) == "object"
    assert f(hot) == "list"


def test_verify_cache_is_bounded(dispatch):
    """Tier-two buckets must not grow without bound.

    A bucket is keyed on the runtime types of the arguments, so an `n`-argument
    function's key space is combinatorial in what its callers pass. Past the limit a
    call resolves over every method, exactly as it did before tier two existed, so
    the answers are unchanged.
    """
    from plum._function import _VERIFY_CACHE_LIMIT

    @dispatch
    def f(x: list[int], y: object):
        return "list[int]"

    @dispatch
    def f(x: object, y: object):
        return "object"

    # More distinct type pairs than the cap allows.
    values = [type(f"B{i}", (), {})() for i in range(_VERIFY_CACHE_LIMIT + 50)]
    for v in values:
        assert f(v, 1) == "object"

    assert len(f._verify_cache) == _VERIFY_CACHE_LIMIT

    # And dispatch past the cap still agrees with what full resolution would say.
    assert f([1], 1) == "list[int]"
    assert f(values[-1], 1) == "object"


def test_verify_cache_is_not_allocated_for_cacheable_functions(dispatch):
    # Most functions are cacheable and never take the tier-two path, so they must
    # not each carry an empty dict for a cache they will never read.
    @dispatch
    def f(x: int):
        return "int"

    f(1)
    f(1)
    assert f._verify_cache is None
    assert f._cache  # ... while tier one is warm.

    @dispatch
    def g(x: list[int]):
        return "li"

    assert g._verify_cache is None  # Not until the first miss.
    g([1])
    assert g._verify_cache is not None
