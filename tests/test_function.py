import abc
import os
import sys
import textwrap
import threading
import typing

import pytest

import plum
from plum._function import (
    _INVOKE_CACHE_LIMIT,
    Function,
    _BoundFunction,
    _convert,
    _owner_transfer,
)
from plum._method import Method
from plum._resolver import (
    AmbiguousLookupError,
    NotFoundLookupError,
    _change_function_name,
    _unwrap_invoked_methods,
)
from plum._signature import Signature


def test_convert_reference():
    class A:
        pass

    a = A()
    assert _convert(a, typing.Any) is a  # Nothing should happen.
    assert _convert(a, tuple) == (a,)


def test_change_function_name():
    def f(x):
        """Doc"""

    g = _change_function_name(f, "g")

    assert g.__name__ == "g"
    assert g.__doc__ == "Doc"


def test_function():
    def f(x):
        """Doc"""

    g = Function(f)

    assert g.__name__ == "f"
    assert g.__doc__ == "Doc"

    # Check global tracking of functions.
    assert g in Function._instances


def test_repr(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: str):
        return "str"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        f" (with 0 registered and 2 pending method(s))>"
    )

    # Register all methods.
    assert f(1) == "int"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        f" (with 2 registered and 0 pending method(s))>"
    )

    @dispatch
    def f(x: float):
        return "float"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        f" (with 2 registered and 1 pending method(s))>"
    )

    # Again register all methods.
    assert f(1) == "int"

    assert repr(f) == (
        f"<multiple-dispatch function {f.__qualname__}"
        " (with 3 registered and 0 pending method(s))>"
    )


# `A` needs to be in the global scope for owner resolution to work.


class A:
    pass


def test_owner():
    def f(x):
        pass

    assert Function(f).owner is None
    assert Function(f, owner="A").owner is A


def test_resolve_method_with_cache_no_arguments():
    def f(x):
        pass

    with pytest.raises(ValueError, match="`args` and `types` cannot both be `None`"):
        Function(f)._resolve_method_with_cache()


@pytest.fixture()
def owner_transfer():
    # Save and clear.
    before = dict(_owner_transfer)
    _owner_transfer.clear()

    yield _owner_transfer

    # Restore.
    _owner_transfer.clear()
    _owner_transfer.update(before)


def test_owner_transfer(owner_transfer):
    def f(x):
        pass

    class B:
        pass

    # Transfer once.
    owner_transfer[A] = B
    assert Function(f, owner="A").owner is B

    class C:
        pass

    # Transfer twice.
    owner_transfer[B] = C
    assert Function(f, owner="A").owner is C


def test_functionmeta():
    assert Function.__doc__ == Function._class_doc


@pytest.mark.parametrize("cls", [Function, _BoundFunction])
def test_class_doc_and_module(cls):
    # Class access must give each class its own docstring and a real module string:
    # the descriptors serve the instance values, but `help` and Sphinx read these.
    assert cls.__doc__ == cls._class_doc
    assert cls.__module__ == "plum._function"


def test_doc(monkeypatch):
    def f(x: int):
        """
        Process an int.
        """

    def f2(x: float):
        """Process a float.

        Args:
            x (float): Argument.
        """

    # Test the following:
    #   (1) the self-exclusion mechanism,
    #   (2) single-line original docstring,
    #   (3) the trimming of whitespace of the original docstring, and
    #   (4) the replacement of `<separator>` by lines of the right length.
    g = Function(f).dispatch(f)
    assert g.__doc__ == "Process an int."
    g.dispatch(f2)
    expected_doc = """
    Process an int.

    ------------------------

    f(x: float)

    Process a float.

    Args:
        x (float): Argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()

    def f(x: int):
        """
        Process an int.

        Args:
            x (int): A very long argument.
        """

    # Test multi-line original docstring.
    g = Function(f).dispatch(f)
    expected_doc = """
    Process an int.

    Args:
        x (int): A very long argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()
    g.dispatch(f2)
    expected_doc = """
    Process an int.

    Args:
        x (int): A very long argument.

    ----------------------------------

    f(x: float)

    Process a float.

    Args:
        x (float): Argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()

    def f(x: int):
        pass

    # Test empty original docstring.
    g = Function(f).dispatch(f)
    assert g.__doc__ is None
    g.dispatch(f2)
    expected_doc = """
    ------------------------

    f(x: float)

    Process a float.

    Args:
        x (float): Argument.
    """
    assert g.__doc__ == textwrap.dedent(expected_doc).strip()


def test_simple_doc(monkeypatch):
    @dispatch
    def f(x: int):
        """First."""

    @dispatch
    def f(x: str):
        """Second."""

    monkeypatch.setitem(os.environ, "PLUM_SIMPLE_DOC", "1")
    assert f.__doc__ == "First."

    monkeypatch.setitem(os.environ, "PLUM_SIMPLE_DOC", "0")
    expected_doc = """
    First.

    -----------

    f(x: str)

    Second.
    """
    assert f.__doc__ == textwrap.dedent(expected_doc).strip()


def test_methods(dispatch: plum.Dispatcher):
    def f(x: int):
        pass

    method1 = Method(f, Signature(int), function_name="f")
    f_dispatch = dispatch(f)

    def f(x: float):
        pass

    method2 = Method(f, Signature(float), function_name="f")
    dispatch(f)

    methods = [method1, method2]

    assert list(f_dispatch.methods) == methods


def test_function_dispatch(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return "int"

    @f.dispatch
    def implementation(x: float):
        return "float"

    @f.dispatch(precedence=1)
    def other_implementation(x: str):
        return "str"

    assert f(1) == "int"
    assert f(1.0) == "float"
    assert f("1") == "str"
    assert f._resolver.resolve(("1",)).signature.precedence == 1


def test_function_multi_dispatch(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return "int"

    @f.dispatch_multi((float,), Signature(str, precedence=1))
    def implementation(x):
        return "float or str"

    assert f(1) == "int"
    assert f(1.0) == "float or str"
    assert f("1") == "float or str"
    assert f._resolver.resolve(("1",)).signature.precedence == 1

    # Check that arguments to `f.dispatch_multi` must be tuples or signatures. This is a
    # `TypeError` in both the pure-Python and compiled builds (the compiled build raises
    # it at the typed-vararg C boundary).
    with pytest.raises(TypeError):
        f.dispatch_multi(1)


def test_register():
    def f(x: int):
        pass

    g = Function(f)
    g.register(f)

    assert g._pending == [(f, None, 0)]
    assert g._resolved == []
    assert len(g._resolver) == 0


def test_resolve_pending_registrations(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return "int"

    # Populate cache.
    assert f(1) == "int"

    # At this point, there should be nothing to register, so a call should not clear
    # the cache.
    assert f._pending == []
    f._resolve_pending_registrations()
    assert len(f._cache) == 1

    @f.dispatch
    def f(x: str):
        pass

    # Now there is something to register. A call should clear the cache.
    assert len(f._pending) == 1
    f._resolve_pending_registrations()
    assert len(f._pending) == 0
    assert len(f._cache) == 0

    # Register in two ways using multi and the wrong name.
    @f.dispatch_multi((float,), Signature(complex))
    def not_f(x):
        return "float or complex"

    # Even though we used `not_f`, dispatch should work correctly.
    assert not_f(1.0) == "float or complex"
    assert not_f(1j) == "float or complex"

    # Check the expansion of default values.

    @dispatch
    def g(x: int, y: float = 1.0, z: complex = 1j):
        return "ok"

    assert g(1) == "ok"
    assert g(1, 1.0) == "ok"
    assert g(1, 1.0, 1j) == "ok"

    assert g(1, y=1.0, z=1j) == "ok"
    assert g(1, 1.0, z=1j) == "ok"


def test_call_dispatch_error(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int, y):
        pass

    @dispatch
    def f(x, y: int):
        pass

    with pytest.raises(
        NotFoundLookupError,
        match="(?i)^`f\\('1', '1'\\)` could not be resolved\\.\n\nClosest",
    ):
        f("1", "1")

    with pytest.raises(
        AmbiguousLookupError,
        match="(?i)^`f\\(1, 1\\)` is ambiguous\\.\n\nCandidates:",
    ):
        f(1, 1)


# We already defined an `A` above. The classes below again need to be in the global
# scope.

dispatch = plum.Dispatcher()


class B(metaclass=abc.ABCMeta):
    @dispatch  # noqa: B027
    def __init__(self):
        pass

    def do(self, x):
        return "B"

    @abc.abstractmethod
    def do_something_else(self, x):
        pass


# Put a class in the middle of the two to make sure that MRO resolution works well.


class Inbetween(B):
    pass


class C(Inbetween):
    @dispatch
    def __init__(self):
        pass

    @dispatch
    def __call__(self):
        return "C"

    @dispatch
    def do(self, x: int):
        return "C"

    @dispatch
    def do_something_else(self, x: int):
        return "C"

    @dispatch
    def __le__(self, other: int):
        return 1


def test_call_mro():
    c = C()

    # If method cannot be found, the next in the MRO should be invoked.
    assert c.do(1) == "C"
    assert c.do(1.0) == "B"

    # Test a dunder method.
    assert (c <= 2) == 1
    with pytest.raises(
        NotFoundLookupError,
        match=r"(?i)^`C\.__le__\(.+\)` could not\s*be\s*resolved.*",
    ):
        c <= "2"  # noqa


def test_call_abstract():
    # Check that ABC still works.
    with pytest.raises(TypeError):
        B()
    c = C()

    # Abstract methods should be ignored.
    assert c.do_something_else(1) == "C"
    with pytest.raises(NotFoundLookupError):
        c.do_something_else(1.0)


def test_call_object():
    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`B\.__init__\(.+\)` could not\s*be\s*resolved.*",
    ):
        # Construction requires no arguments. Giving an argument should propagate to
        # `B` and then error.
        C(1)

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`C\.__call__\(.+\)` could not\s*be\s*resolved.*",
    ):
        # Calling requires no arguments.
        C()(1)


dispatch = plum.Dispatcher()


class D(type):
    @dispatch
    def __call__(self, x: str):
        pass


class E(D):
    @dispatch
    def __init__(self, name: str, bases: tuple[type], methods: dict):
        pass

    @dispatch
    def __call__(self):
        pass


def test_call_type():
    """Exactly like :func:`test_call_object`."""

    class A:
        pass

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`E\.__init__\(.+\)` could\s+not be resolved",
    ):
        E("Test", (A, object), {})  # Must have exactly one base.

    with pytest.raises(
        NotFoundLookupError,
        match=r"(?is)^`D\.__call__\(.+\)` could\s+not be resolved",
    ):
        # The call method will be tried at :class:`D` and only then error.
        E("Test", (object,), {})(1)


def test_call_convert(dispatch: plum.Dispatcher):
    @dispatch
    def f(x) -> tuple:
        return x

    assert f(1) == (1,)


def test_invoke(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: float):
        return "float"

    @dispatch
    def f(x: str):
        return "str"

    assert f.invoke(int)(None) == "int"
    assert f.invoke(float)(None) == "float"
    assert f.invoke(str)(None) == "str"


def test_invoke_convert(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int) -> tuple:
        return x

    assert f.invoke(int)(1) == (1,)


def test_invoke_wrapping(dispatch: plum.Dispatcher):
    @dispatch
    def f(x: int):
        """Docs"""

    assert f.invoke(int).__name__ == "f"
    assert f.invoke(int).__doc__ == "Docs"


def test_invoke_is_cached(dispatch: plum.Dispatcher):
    """The same types give back the identical wrapper, rather than a fresh one."""

    @dispatch
    def f(x: int):
        return "int"

    @dispatch
    def f(x: str):
        return "str"

    assert f.invoke(int) is f.invoke(int)
    # Different types are cached separately.
    assert f.invoke(int)(None) == "int"
    assert f.invoke(str)(None) == "str"


def test_invoke_cache_sees_later_methods(dispatch: plum.Dispatcher):
    """A method registered after `invoke` must not be masked by the cached wrapper."""

    @dispatch
    def f(x: object):
        return "object"

    assert f.invoke(int)(None) == "object"

    @dispatch
    def f(x: int):
        return "int"

    # The pending registration is resolved before the cache is consulted.
    assert f.invoke(int)(None) == "int"


def test_invoke_cache_cleared_by_clear_cache(dispatch: plum.Dispatcher):
    """`clear_cache` drops the wrappers along with the resolved methods."""

    @dispatch
    def f(x: int):
        return "int"

    first = f.invoke(int)
    f.clear_cache()
    assert f.invoke(int) is not first
    assert f.invoke(int)(None) == "int"


def test_invoke_implementation_unwrapping(dispatch: plum.Dispatcher):
    def f(x: int):
        return type(x)

    f_orig = f
    f = dispatch(f)

    # Redirect `float`s to `int`s.
    dispatch.multi((float,))(f.invoke(int))

    assert f(1) is int
    assert f(1.0) is float

    assert f.methods[0].implementation is f_orig
    assert f.methods[1].implementation is not f_orig
    assert _unwrap_invoked_methods(f.methods[0].implementation) is f_orig
    assert _unwrap_invoked_methods(f.methods[1].implementation) is f_orig


def test_bound(dispatch: plum.Dispatcher):
    class A:
        @dispatch
        def do(self, x: int):
            """Docs"""
            return "int"

    assert A().do.__doc__ == "Docs"
    assert A.do.__doc__ == "Docs"

    assert A().do.invoke(int)(1) == "int"
    assert A.do.invoke(A, int)(A(), 1) == "int"

    # Also test that `invoke` is wrapped, like above.
    assert A().do.invoke(int).__doc__ == "Docs"
    assert A.do.invoke(A, int).__doc__ == "Docs"


def test_name_after_clearing_cache(dispatch: plum.Dispatcher):
    @dispatch
    def some_function_name(x: int):
        pass

    assert some_function_name._resolver.function_name == "some_function_name"

    some_function_name.clear_cache()

    assert some_function_name._resolver.function_name == "some_function_name"


def _make_function_with_string_annotations():
    """Create a new dispatcher and function with string annotations."""

    dispatch = plum.Dispatcher()

    @dispatch
    def f(x: "int") -> "str":
        return "int"

    @dispatch
    def f(x: "str") -> "str":
        return "str"

    @dispatch
    def f(x: "float") -> "str":
        return "float"

    return f


def test_resolve_pending_registrations_is_thread_safe():
    """Test that `_resolve_pending_registrations` is thread-safe.

    Without the lock, this test raises `AssertionError` because `beartype`'s
    `resolve_pep563` mutates the shared `__annotations__` dict concurrently. See GitHub
    issue #274.
    """
    n_threads = 16
    # Force frequent GIL hand-offs so the race reliably reproduces pre-fix: the window
    # is tiny at the default 5ms switch interval.
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        # The race only occurs on a `Function`'s first resolution, so use a fresh,
        # unresolved function each iteration and loop enough to trip it reliably.
        # Without the lock this fails on essentially every iteration.
        for _ in range(100):
            f = _make_function_with_string_annotations()
            barrier = threading.Barrier(n_threads)
            errors: list[BaseException] = []

            def worker(f=f, barrier=barrier, errors=errors):
                try:
                    barrier.wait()  # Release all threads onto resolution together.
                    f._resolve_pending_registrations()
                except BaseException as e:  # noqa: BLE001
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors, errors
            # Resolution completed exactly once and left a clean, usable state.
            assert f._pending == []
            assert len(f._resolver) == 3
            assert f(1) == "int"
            assert f("x") == "str"
            assert f(1.0) == "float"
    finally:
        sys.setswitchinterval(old_interval)


@pytest.mark.incompatible_with_mypyc
def test_call_does_not_cache_a_result_a_clear_invalidated(dispatch: plum.Dispatcher):
    """A registration landing mid-resolution must not leave a stale method cached.

    `clear_cache` clears `_cache` under `_lock`, but `_resolve_method_with_cache`
    resolves and stores outside it, so a method resolved before the clear can be
    written after it. `_pending` is empty by then, so nothing would ever invalidate
    it again and every later call would get the superseded method. See GitHub issue
    #274.
    """

    @dispatch
    def f(x: int):
        return "v1"

    f._resolve_pending_registrations()

    resolved, invalidated = threading.Event(), threading.Event()
    original = Function.resolve_method
    target, park = f, [True]

    def parked(self, *args, **kw_args):
        out = original(self, *args, **kw_args)
        # Scoped by identity: `Function` is a `mypyc` native class, so there is no
        # instance `__dict__` to hang a flag on, and other functions resolve here too.
        if self is target and park[0]:
            resolved.set()
            # Park between resolving and storing, which is where the clear lands.
            invalidated.wait(5)
        return out

    # A bare `Thread` swallows whatever the target raises, and `join(timeout)` returns
    # whether or not the thread finished, so both are checked explicitly below: without
    # that this test would pass just as happily if the parked thread crashed or hung.
    errors: list[BaseException] = []

    def call_in_thread() -> None:
        try:
            f(1)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    Function.resolve_method = parked
    try:
        thread = threading.Thread(target=call_in_thread)
        thread.start()
        assert resolved.wait(5), "the parked thread never reached the park"

        @dispatch
        def f(x: int):  # noqa: F811
            return "v2"

        f._resolve_pending_registrations()
        invalidated.set()
        thread.join(5)
    finally:
        park[0] = False
        Function.resolve_method = original

    assert not thread.is_alive(), "the parked thread did not finish"
    assert not errors, errors
    assert f(1) == "v2"


def test_wraps_matches_functools_wraps():
    """The fast metadata copy must be observationally identical to `functools.wraps`.

    Everything plum or `inspect` reads back off an invoke wrapper is compared here;
    `__type_params__` is deliberately not copied, since nothing reads it.
    """
    import functools
    import inspect

    from plum._function import _wraps

    def target(x: int) -> str:
        """The docstring."""
        return "s"

    target.custom_attr = 42  # `functools.wraps` merges `__dict__`; so must we.

    class W:
        def __call__(self, *args, **kw_args):
            return None

    reference, fast = W(), W()
    functools.wraps(target)(reference)
    _wraps(fast, target)

    for attr in ("__name__", "__qualname__", "__module__", "__doc__", "custom_attr"):
        assert getattr(fast, attr) == getattr(reference, attr), attr
    assert fast.__wrapped__ is target is reference.__wrapped__
    assert inspect.signature(fast) == inspect.signature(reference)
    assert inspect.unwrap(fast) is target

    # Annotations, which `functools.wraps` carries on `__annotations__` before Python
    # 3.14 and on the lazy `__annotate__` from 3.14. Whichever this interpreter uses,
    # the two must agree; before 3.14 the copy is visible, so assert the value too.
    sentinel = object()
    for attr in ("__annotations__", "__annotate__"):
        assert getattr(fast, attr, sentinel) == getattr(reference, attr, sentinel), attr
    if "__annotate__" not in functools.WRAPPER_ASSIGNMENTS:
        assert fast.__annotations__ == {"x": int, "return": str}


def test_wraps_tolerates_a_wrapped_without_a_dict():
    """`functools.wraps` merges `getattr(wrapped, "__dict__", {})`, so a slotted
    callable must not make the copy raise."""
    from plum._function import _wraps

    class Slotted:
        __slots__ = ()
        __name__ = "slotted"
        __qualname__ = "Slotted.slotted"
        __module__ = "somewhere"
        __doc__ = "doc"

        def __call__(self):
            return None

    class W:
        def __call__(self):
            return None

    wrapped, wrapper = Slotted(), W()
    assert not hasattr(wrapped, "__dict__")
    _wraps(wrapper, wrapped)  # Must not raise.
    assert wrapper.__name__ == "slotted"
    assert wrapper.__wrapped__ is wrapped


def test_wraps_without_qualname():
    """A callable object need not have `__qualname__`; the fallback is `__name__`."""
    from plum._function import _wraps

    class Callable:
        __name__ = "no_qualname"
        __doc__ = None
        __module__ = "somewhere"

        def __call__(self):
            return None

    class W:
        def __call__(self):
            return None

    wrapped, wrapper = Callable(), W()
    assert not hasattr(wrapped, "__qualname__")
    _wraps(wrapper, wrapped)
    assert wrapper.__name__ == wrapper.__qualname__ == "no_qualname"


@pytest.mark.incompatible_with_mypyc
def test_invoke_does_not_cache_a_result_a_clear_invalidated(dispatch: plum.Dispatcher):
    """A registration landing mid-`invoke` must not leave a stale wrapper cached.

    `clear_cache` clears `_invoke_cache` under `_lock`, but `invoke` resolves and
    stores outside it, so without the generation check a wrapper resolved before the
    clear can be written after it. `_pending` is empty by then, so nothing would ever
    invalidate it again and `invoke` would disagree with `__call__` for good. The
    resolver here is deliberately uncacheable -- `list[int]` matches on the elements,
    not the type -- which is the case `_cache` sidesteps by refusing to store at all,
    so a stale answer here can only have come from the wrapper cache. See GitHub
    issue #274.
    """

    @dispatch
    def f(x: list[int]):
        return "list"

    @dispatch
    def f(x: int):  # noqa: F811
        return "int-v1"

    f._resolve_pending_registrations()
    assert not f._resolver.is_faithful

    resolved, invalidated = threading.Event(), threading.Event()
    original = Function.resolve_method
    target, park = f, [True]

    def parked(self, *args, **kw_args):
        out = original(self, *args, **kw_args)
        # Scoped by identity, not by an attribute: `Function` is a `mypyc` native
        # class, so its instances have no `__dict__` to hang a flag on. Other
        # functions (`_convert`, say) resolve during this test and must not park.
        if self is target and park[0]:
            resolved.set()
            # Park between resolving and storing, which is where the clear lands.
            invalidated.wait(5)
        return out

    Function.resolve_method = parked
    try:
        thread = threading.Thread(target=lambda: f.invoke(int))
        thread.start()
        assert resolved.wait(5)

        @dispatch
        def f(x: int):  # noqa: F811
            return "int-v2"

        f._resolve_pending_registrations()
        invalidated.set()
        thread.join(5)
    finally:
        park[0] = False
        Function.resolve_method = original

    assert f(2) == "int-v2"
    assert f.invoke(int)(2) == "int-v2"


def test_invoke_cache_is_bounded(dispatch: plum.Dispatcher):
    """`_invoke_cache` is not gated on `is_faithful`, so it must be bounded instead.

    Its keys are whatever hints callers pass, and for a process-global function such
    as `_promotion._convert` that is bounded only by the caller's data.
    """

    @dispatch
    def f(x: typing.Literal[1]):
        return "literal"

    @dispatch
    def f(x: object):  # noqa: F811
        return "object"

    f._resolve_pending_registrations()
    assert not f._resolver.is_faithful
    assert f._cache == {}  # `_cache` refuses to store at all here.

    for i in range(_INVOKE_CACHE_LIMIT + 100):
        f.invoke(type(f"T{i}", (object,), {}))
    assert len(f._invoke_cache) == _INVOKE_CACHE_LIMIT

    # Past the cap dispatch still resolves, it just stops being memoised.
    class Late:
        pass

    assert f.invoke(Late)(Late()) == "object"
    assert f.invoke(typing.Literal[1])(1) == "literal"


def test_bound_invoke_sees_later_methods(dispatch: plum.Dispatcher):
    """`_BoundInvokedMethod.__call__` re-enters `Function.invoke`, so the bound path
    inherits the wrapper cache and must see later registrations too."""

    class A:
        @dispatch
        def do(self, x: object):
            return "object"

    a = A()
    assert a.do.invoke(int)(1) == "object"

    @A.do.dispatch
    def do(self, x: int):  # noqa: F811
        return "int"

    assert a.do.invoke(int)(1) == "int"


def test_type_dispatch_correctness(dispatch):
    class Base:
        pass

    class Sub(Base):
        pass

    @dispatch
    def f(x: int):
        return "inst-int"

    @dispatch
    def f(x: type[int]):
        return "type[int]"

    @dispatch
    def f(x: type[Base]):
        return "type[Base]"

    @dispatch
    def f(x: type[Sub]):
        return "type[Sub]"

    assert f(5) == "inst-int"  # instance vs class: no collision
    assert f(int) == "type[int]"
    assert f(Sub) == "type[Sub]"  # subclass beats base
    assert f(Base) == "type[Base]"


def test_type_dispatch_pathological_metaclass(dispatch):
    # Unhashable class must dispatch, not raise TypeError.
    class MetaUnhashable(type):
        def __eq__(cls, other):
            return cls is other

    class C(metaclass=MetaUnhashable):
        pass

    @dispatch
    def f(x: type[int]):
        return "int"

    @dispatch
    def f(x: type[object]):
        return "object"

    assert f(C) == "object"

    # Lying-eq metaclass must not mis-cache.
    class MetaLie(type):
        def __eq__(cls, other):
            return True

        def __hash__(cls):
            return 7

    class A(int, metaclass=MetaLie):
        pass

    class B(metaclass=MetaLie):
        pass

    assert f(A) == "int"
    assert f(B) == "object"


def test_type_match_implies_identity_slot_beartype_invariant():
    # Pins the one external assumption behind cacheable `type[X]`: whenever `x`
    # matches `type[X]`, the cache key's identity slot is non-`None`, so the key
    # captures what the match depended on. If beartype ever matches an `x` that
    # `_identity` maps to `None`, `cache_key` soundness breaks.
    #
    # Asserting instead that no non-class matches `type[T]` would be weaker (with
    # `type[object]` beartype short-circuits to `isinstance(x, type)`, never reaching
    # the `issubclass` half) and outright false for `LiesAboutClass` below.
    from plum._bear import is_bearable
    from plum._type import _identity

    class SomeClass:
        pass

    class LiesAboutClass:
        @property
        def __class__(self):
            return type

    liar = LiesAboutClass()
    corpus = [5, list[int], tuple[int], (lambda: 0), int | str, int, SomeClass, liar]
    matched = []
    for x in corpus:
        for hint in (type[object], type[int], type[SomeClass]):
            try:
                match = is_bearable(x, hint)
            except TypeError:
                # `issubclass` rejects `x`. Not a match, so nothing to capture.
                continue
            if match:
                matched.append((x, hint))
                assert _identity(x) is not None

    # `isinstance` consults `__class__`, so the liar really does match `type[object]`.
    assert (liar, type[object]) in matched
    # And the corpus must not have degenerated into vacuous truth.
    assert (int, type[int]) in matched


def test_keyerror_from_method_body_propagates(dispatch):
    # `Function.__call__` inlines the cache hit in a `try`/`except KeyError`. The
    # dispatched call must stay outside it, so a `KeyError` raised by user code
    # propagates instead of being caught and re-dispatched.
    calls = []

    @dispatch
    def f(x: int):
        calls.append(x)
        raise KeyError("from the method body")

    for _ in range(2):  # once on a cache miss, once on a cache hit
        with pytest.raises(KeyError, match="from the method body"):
            f(1)
    assert calls == [1, 1]


class UncacheableBase:
    def do_uncacheable(self, x):
        return "base"


class UncacheableChild(UncacheableBase):
    @dispatch
    def do_uncacheable(self, x: list[int]):
        return "child"


def test_call_mro_uncacheable():
    # The tier-two verify cache narrows the methods that dispatch considers. It must
    # not swallow the fallback to the next method in the MRO, warm or cold.
    c = UncacheableChild()
    assert c.do_uncacheable([1]) == "child"
    assert UncacheableChild.do_uncacheable._verify_cache  # The bucket is warm.
    assert c.do_uncacheable(["a"]) == "base"
    assert c.do_uncacheable(["a"]) == "base"
    assert c.do_uncacheable([1]) == "child"


def test_instances_does_not_pin_functions():
    """Global tracking must not keep a dead `Function` alive."""
    import gc

    def f(x):
        pass

    # Asserted through the registry rather than a `weakref.ref` to the function: a
    # `mypyc`-compiled `Function` is a native class and cannot be weakly referenced.
    gc.collect()
    before = len(Function._instances)

    # While it is reachable it must be tracked, so that `clear_all_cache` reaches it.
    # Checking this as well as the count means an unrelated function being collected
    # between the two `gc.collect()` calls cannot net out to a spurious pass.
    live = Function(f)
    assert live in Function._instances
    assert len(Function._instances) == before + 1

    # Once unreachable it must go, which is the point of the weak registry.
    del live
    gc.collect()
    assert len(Function._instances) == before
