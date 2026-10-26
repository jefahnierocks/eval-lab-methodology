"""Select one prepared Quarto executable with the repository's exact version."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_TIMEOUT_SECONDS = 10


class QuartoUnavailableError(RuntimeError):
    """A prepared selection is unavailable; never install or silently replace it."""


def select_quarto(
    root: Path = ROOT, *, environ: Mapping[str, str] | None = None
) -> str:
    """Prefer explicit QUARTO, then the pinned local installation, then PATH."""
    environment = os.environ if environ is None else environ
    try:
        required = (root / ".quarto-version").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise QuartoUnavailableError("Cannot read the repository Quarto pin") from None
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", required) is None:
        raise QuartoUnavailableError("Invalid repository Quarto pin")

    local = root / ".cache" / "tools" / f"quarto-{required}"
    if "QUARTO" in environment:
        choice = environment["QUARTO"]
        origin = "explicit QUARTO"
    elif local.exists() or local.is_symlink():
        choice = str(local / "bin" / "quarto")
        origin = "prepared local Quarto"
    else:
        choice = "quarto"
        origin = "PATH Quarto"

    try:
        selected = shutil.which(choice, path=environment.get("PATH", os.defpath))
        if not selected:
            raise QuartoUnavailableError(f"Quarto {required}: {origin} is unavailable")
        executable = Path(selected).resolve(strict=True)
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise QuartoUnavailableError(
                f"Quarto {required}: {origin} is not executable"
            )
        completed = subprocess.run(
            [str(executable), "--version"],
            cwd=root,
            env=dict(environment),
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise QuartoUnavailableError(
            f"Quarto {required}: {origin} probe failed"
        ) from None
    if completed.returncode != 0 or completed.stdout.strip() != required:
        raise QuartoUnavailableError(f"Quarto {required}: {origin} version mismatch")
    return str(executable)


def main() -> int:
    try:
        print(select_quarto())
    except QuartoUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
