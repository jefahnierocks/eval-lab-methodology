#!/usr/bin/env python3
"""Validate index paths and scan Git source with pinned native Gitleaks rules."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITLEAKS_VERSION = "8.30.1"
NATIVE_CONFIG = "[extend]\nuseDefault = true\n"


class SecurityError(Exception):
    """A safe failure message that never includes command output or file contents."""


def scanner_environment() -> dict[str, str]:
    allowed = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    # Select only the bundled rules; never auto-load a repository or ambient policy.
    environment["GITLEAKS_CONFIG_TOML"] = NATIVE_CONFIG
    return environment


def command(arguments: list[str], root: Path, *, payload: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            arguments,
            cwd=root,
            input=payload,
            capture_output=True,
            env=scanner_environment(),
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise SecurityError("Required security command could not complete.") from None
    if result.returncode != 0:
        raise SecurityError("Required security command failed; output withheld.")
    return result.stdout


def private_paths(index: bytes) -> list[bytes]:
    if index and not index.endswith(b"\0"):
        raise SecurityError("Git returned malformed index paths.")
    paths = index.split(b"\0")[:-1]
    if any(not path for path in paths):
        raise SecurityError("Git returned malformed index paths.")
    return [path for path in paths if b"private" in path.lower().split(b"/")[:-1]]


def check_root(root: Path) -> None:
    answer = command(
        ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"], root
    )
    if not answer.endswith(b"\n") or answer.count(b"\n") != 1 or b"\0" in answer:
        raise SecurityError("Git returned a malformed repository root.")
    reported = Path(os.fsdecode(answer[:-1]))
    try:
        matches = reported.is_absolute() and reported.resolve(
            strict=True
        ) == root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise SecurityError("Git repository root could not be verified.") from None
    if not matches:
        raise SecurityError("Git repository root does not match the requested root.")


def check_paths(root: Path) -> None:
    check_root(root)
    index = command(["git", "ls-files", "--cached", "-z"], root)
    if private_paths(index):
        raise SecurityError("Tracked or staged private-directory paths are forbidden.")


def check_security(root: Path, *, paths_only: bool = False) -> None:
    for name in (".gitleaks.toml", ".gitleaksignore"):
        if os.path.lexists(root / name):
            raise SecurityError(
                "Repository scanner policy files require owner disposition."
            )
    check_paths(root)
    if paths_only:
        return
    shallow = command(["git", "rev-parse", "--is-shallow-repository"], root)
    if shallow != b"false\n":
        raise SecurityError("A complete, non-shallow Git repository is required.")
    version = command(["gitleaks", "version"], root)
    if version.strip() != GITLEAKS_VERSION.encode("ascii"):
        raise SecurityError("Gitleaks 8.30.1 is required.")
    flags = [
        "--redact=100",
        "--no-banner",
        "--ignore-gitleaks-allow",
        "--gitleaks-ignore-path",
        os.devnull,
    ]
    command(
        [
            "gitleaks",
            "git",
            *flags,
            "--log-opts=--all --full-history --no-ext-diff --no-textconv --no-renames --diff-merges=first-parent",
            ".",
        ],
        root,
    )
    # Never combine these with a HEAD diff: staged data can be reverted on disk.
    for stage in (["--cached"], []):
        payload = command(
            [
                "git",
                "diff",
                *stage,
                "--binary",
                "--no-ext-diff",
                "--no-textconv",
                "--no-color",
                "--",
            ],
            root,
        )
        command(["gitleaks", "stdin", *flags], root, payload=payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths-only", action="store_true")
    arguments = parser.parse_args()
    try:
        check_security(ROOT, paths_only=arguments.paths_only)
    except SecurityError as error:
        print(f"repository security: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "repository security: PASS"
        + (" (index paths only)" if arguments.paths_only else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
