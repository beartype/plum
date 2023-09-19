import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Tuple

FileLineInfo = Dict[Path, Dict[int, List[str]]]
"""type: Type of a nested dictionary that gives for a collection of files line-wise
information, where the information is of the form `list[str]`."""


def next_noncomment_line(index: int, lines: List[str], path: Path) -> int:
    """Starting at `index`, find the next line with code.

    Args:
        index (int): Index to start at.
        lines (list[str]): Source code lines.
        path (:class:`pathlib.Path`): Path where the source code is from.

    Returns:
        int: Index of the next line with code.
    """
    i = index + 1  # Start at the next line.
    while i < len(lines):
        line_content = lines[i].strip()
        if line_content and not line_content.startswith("#"):
            return i
        i += 1
    raise RuntimeError(f"{path}:{index}: Cannot match error assertion to code line.")


def parse_assertions(source_dir: Path, linter: str) -> FileLineInfo:
    """Parse all assertions in all Python files in `source_dir` for linter `linter`.

    Args:
        source_dir (:class:`pathlib.Path`): Source directory.
        linter (str): Linter.

    Returns:
        :obj:`FileLineInfo`: Assertions.
    """
    asserted_errors: FileLineInfo = defaultdict(lambda: defaultdict(list))

    for path in source_dir.resolve().rglob("*.py"):  # Important to `resolve` here!
        with open(path, "r") as f:
            lines = f.read().splitlines()
        for i, line in enumerate(lines):
            # Check if the line has an error assertion.
            try:
                code, comment = line.rsplit("# E:", 1)
            except ValueError:
                continue

            # Find error assertions.
            assertions = re.findall(linter + r"\(([^\)]*)\)", comment)

            # There is nothing to do if there are no assertions.
            if not assertions:
                continue

            # Find line number of the code that the assertions pertains to. If there is
            # no code on the line, find the next non-comment line.
            if not code.strip():
                i = next_noncomment_line(i, lines, path)

            line_number = i + 1  # Line numbers start at one.
            asserted_errors[path][line_number].extend(assertions)

    return asserted_errors


def parse_mypy_line(line: str) -> Tuple[Path, int, str, str]:
    """Parse a line of the output of `mypy`.

    Args:
        line (str): Line.

    Raises:
        ValueError: If the line cannot be parsed.

    Returns:
        :class:`pathlib.Path`: Path of file.
        int: Line number.
        str: Kind of message.
        str: Message.
    """
    path, line_number, status, message = line.split(":", 3)
    # Path must be `resolve`d!
    return Path(path).resolve(), int(line_number), status, message


def parse_pyright_line(line: str) -> Tuple[Path, int, str, str]:
    """Parse a line of the output of `pyright`.

    Args:
        line (str): Line.

    Raises:
        ValueError: If the line cannot be parsed.

    Returns:
        :class:`pathlib.Path`: Path of file.
        int: Line number.
        str: Kind of message.
        str: Message.
    """
    specification, status_message = line.split(" - ", 1)
    path, line_number, _ = specification.split(":", 2)
    status, message = status_message.split(":", 1)
    # Path must be `resolve`d!
    return Path(path.strip()).resolve(), int(line_number), status, message


parse_line: Dict[str, Callable[[str], Tuple[Path, int, str, str]]] = {
    "mypy": parse_mypy_line,
    "pyright": parse_pyright_line,
}
"""dict[str, Callable[[str], tuple[:class:`pathlib.Path`, int, str, str]]]: Map a
linter to a function that parses a line of the output of the linter."""


def parse_output(stdout: str, linter: str) -> FileLineInfo:
    """Parse the whole output of a linter.

    Args:
        stdout (str): `stdout` of the linter.
        linter (str): Name of the linter.

    Returns:
        :obj:`FileLineInfo`: Linter errors.
    """
    errors: FileLineInfo = defaultdict(lambda: defaultdict(list))

    for line in stdout.splitlines():
        # Parse line in the output of `mypy`. If it cannot be parsed, just skip it.
        try:
            path, line_number, status, message = parse_line[linter](line)
        except ValueError:
            continue

        # We only need to validate errors.
        if status.lower().strip() != "error":
            continue

        errors[Path(path)][line_number].append(message)

    return errors


def run_linter(linter: str) -> str:
    """Run a linter and get the `stdout`.

    Args:
        linter (str): Name of the linter.

    Returns:
        str: `stdout`.
    """
    p = subprocess.Popen(
        [linter, source_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate()
    assert not stderr, f"`stderr` must be empty, but is not:\n{stderr.decode()}"
    return stdout.decode()


def get_missed(
    errors: FileLineInfo,
    assertions: FileLineInfo,
    match: Callable[[str, str], bool],
) -> FileLineInfo:
    """Find unasserted errors.

    Args:
        error (:obj:`FileLineInfo`): Errors.
        assertions (:obj:`FileLineInfo`): Assertions.
        match (Callable[[str, str], bool]): Function that takes in an error and an
            assertion and checks whether the assertion asserts the error.

    Returns:
        :obj:`FileLineInfo`: Unasserted errors.
    """
    missed_errors: FileLineInfo = defaultdict(lambda: defaultdict(list))
    for path, path_errors in errors.items():
        # If there are no assertions for `path`, report all errors as missing.
        if path not in assertions:
            for line_number in errors[path]:
                missed_errors[path][line_number].extend(errors[path][line_number])
            continue
        for line_number, line_errors in path_errors.items():
            # If there are no assertions for `line_number`, report all errors as
            # missing.
            if line_number not in assertions[path]:
                missed_errors[path][line_number].extend(errors[path][line_number])
                continue
            # Check every error for the line.
            for e in line_errors:
                if not any(match(e, a) for a in assertions[path][line_number]):
                    missed_errors[path][line_number].append(e)
    return missed_errors


def check_linter(source_dir: Path, linter: str) -> bool:
    """Run a linter and check if all errors were asserted and all assertions yielded
    errors. If not, print an overview of what was missed.

    Args:
        source_dir (:class:`pathlib.Path`): Source directory.
        linter (str): Name of the linter.

    Returns:
        bool: `True` if nothing was missed, else `False`.
    """
    stdout = run_linter(linter)

    errors = parse_output(stdout, linter)
    assertions = parse_assertions(source_dir, linter)

    missed_errors = get_missed(
        errors,
        assertions,
        lambda e, a: a.strip().lower() in e.strip().lower(),
    )
    missed_assertions = get_missed(
        assertions,
        errors,
        lambda a, e: a.strip().lower() in e.strip().lower(),
    )

    for path, path_errors in missed_errors.items():
        for line_number, line_errors in path_errors.items():
            for error in line_errors:
                print(f"{linter}:{path}:{line_number}: Error: {error.strip()}")

    for path, path_assertions in missed_assertions.items():
        for line_number, line_assertions in path_assertions.items():
            for assertion in line_assertions:
                print(
                    f"{linter}:{path}:{line_number}: "
                    f"Missed assertion: {assertion.strip()}"
                )

    return not missed_errors and not missed_assertions


if __name__ == "__main__":
    source_dir = Path(sys.argv[1])  # Files that must be validated
    status = True
    status &= check_linter(source_dir, "mypy")
    status &= check_linter(source_dir, "pyright")
    if status:
        print("All OK!")
    exit(0 if status else 1)
