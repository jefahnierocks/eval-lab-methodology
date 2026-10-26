"""Prepared-tool selection tests; no installed Quarto, network or rendering."""

from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import quarto_tool


class QuartoToolTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="quarto selection ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / ".quarto-version").write_text("1.10.18\n", encoding="utf-8")
        self.local = self.root / ".cache/tools/quarto-1.10.18/bin/quarto"
        self.path_tool = self.root / "path tools/quarto"
        self.explicit = self.root / "explicit tool/quarto"

    @staticmethod
    def executable(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nprintf '1.10.18\\n'\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_explicit_selection_precedes_local_and_path(self) -> None:
        for path in (self.local, self.path_tool, self.explicit):
            self.executable(path)
        env = {"QUARTO": str(self.explicit), "PATH": str(self.path_tool.parent)}
        with patch.object(
            quarto_tool.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "1.10.18\n", ""),
        ) as probe:
            selected = quarto_tool.select_quarto(self.root, environ=env)
        self.assertEqual(selected, str(self.explicit))
        probe.assert_called_once_with(
            [str(self.explicit), "--version"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_local_selection_precedes_path(self) -> None:
        self.executable(self.local)
        self.executable(self.path_tool)
        with patch.object(
            quarto_tool.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "1.10.18\n", ""),
        ) as probe:
            selected = quarto_tool.select_quarto(
                self.root, environ={"PATH": str(self.path_tool.parent)}
            )
        self.assertEqual(selected, str(self.local))
        self.assertEqual(probe.call_args.args[0], [str(self.local), "--version"])

    def test_path_is_used_only_when_local_installation_is_absent(self) -> None:
        self.executable(self.path_tool)
        with patch.object(
            quarto_tool.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "1.10.18", ""),
        ):
            selected = quarto_tool.select_quarto(
                self.root, environ={"PATH": str(self.path_tool.parent)}
            )
        self.assertEqual(selected, str(self.path_tool))

    def test_explicit_command_name_is_resolved_on_path(self) -> None:
        self.executable(self.path_tool)
        with patch.object(
            quarto_tool.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "1.10.18", ""),
        ):
            selected = quarto_tool.select_quarto(
                self.root,
                environ={"QUARTO": "quarto", "PATH": str(self.path_tool.parent)},
            )
        self.assertEqual(selected, str(self.path_tool))

    def test_invalid_explicit_selections_never_fall_back(self) -> None:
        self.executable(self.local)
        self.executable(self.path_tool)
        ordinary_file = self.root / "not executable"
        ordinary_file.write_text("not a tool", encoding="utf-8")
        directory = self.root / "directory"
        directory.mkdir()
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "absent target")
        choices = (
            "",
            str(self.root / "absent"),
            str(ordinary_file),
            str(directory),
            str(dangling),
        )
        for choice in choices:
            with (
                self.subTest(choice=choice),
                patch.object(quarto_tool.subprocess, "run") as probe,
                self.assertRaises(quarto_tool.QuartoUnavailableError),
            ):
                quarto_tool.select_quarto(
                    self.root,
                    environ={"QUARTO": choice, "PATH": str(self.path_tool.parent)},
                )
            probe.assert_not_called()

    def test_present_local_installation_without_launcher_refuses_path(self) -> None:
        self.local.parent.mkdir(parents=True)
        self.executable(self.path_tool)
        with (
            patch.object(quarto_tool.subprocess, "run") as probe,
            self.assertRaises(quarto_tool.QuartoUnavailableError),
        ):
            quarto_tool.select_quarto(
                self.root, environ={"PATH": str(self.path_tool.parent)}
            )
        probe.assert_not_called()

    def test_nonexecutable_local_launcher_refuses_path(self) -> None:
        self.local.parent.mkdir(parents=True)
        self.local.write_text("not executable", encoding="utf-8")
        self.executable(self.path_tool)
        with (
            patch.object(quarto_tool.subprocess, "run") as probe,
            self.assertRaises(quarto_tool.QuartoUnavailableError),
        ):
            quarto_tool.select_quarto(
                self.root, environ={"PATH": str(self.path_tool.parent)}
            )
        probe.assert_not_called()

    def test_dangling_local_installation_refuses_path(self) -> None:
        installation = self.local.parent.parent
        installation.parent.mkdir(parents=True)
        installation.symlink_to(self.root / "absent installation")
        self.executable(self.path_tool)
        with (
            patch.object(quarto_tool.subprocess, "run") as probe,
            self.assertRaises(quarto_tool.QuartoUnavailableError),
        ):
            quarto_tool.select_quarto(
                self.root, environ={"PATH": str(self.path_tool.parent)}
            )
        probe.assert_not_called()

    def test_wrong_version_or_nonzero_exit_never_falls_back(self) -> None:
        self.executable(self.local)
        self.executable(self.path_tool)
        for code, output in (
            (0, "1.10.19\n"),
            (0, "1.10.18-rc.1\n"),
            (0, "v1.10.18\n"),
            (0, "1.10.18\nextra output\n"),
            (1, "1.10.18\n"),
        ):
            with (
                self.subTest(code=code, output=output),
                patch.object(
                    quarto_tool.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], code, output, ""),
                ) as probe,
                self.assertRaises(quarto_tool.QuartoUnavailableError),
            ):
                quarto_tool.select_quarto(
                    self.root, environ={"PATH": str(self.path_tool.parent)}
                )
            probe.assert_called_once()
            self.assertEqual(probe.call_args.args[0][0], str(self.local))

    def test_probe_errors_and_timeout_fail_closed(self) -> None:
        self.executable(self.explicit)
        self.executable(self.local)
        for error in (
            OSError("synthetic probe error"),
            subprocess.TimeoutExpired([str(self.explicit), "--version"], 10),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "synthetic"),
        ):
            with (
                self.subTest(error=type(error).__name__),
                patch.object(quarto_tool.subprocess, "run", side_effect=error) as probe,
                self.assertRaises(quarto_tool.QuartoUnavailableError),
            ):
                quarto_tool.select_quarto(
                    self.root, environ={"QUARTO": str(self.explicit), "PATH": ""}
                )
            probe.assert_called_once()

    def test_absent_path_tool_refuses_without_probe(self) -> None:
        with (
            patch.object(quarto_tool.subprocess, "run") as probe,
            self.assertRaises(quarto_tool.QuartoUnavailableError),
        ):
            quarto_tool.select_quarto(self.root, environ={"PATH": ""})
        probe.assert_not_called()

    def test_pin_must_be_present_and_valid(self) -> None:
        pin = self.root / ".quarto-version"
        for content in ("", "1.10.18-rc.1", "1.10.18\nextra"):
            pin.write_text(content, encoding="utf-8")
            with (
                self.subTest(content=content),
                patch.object(quarto_tool.subprocess, "run") as probe,
                self.assertRaises(quarto_tool.QuartoUnavailableError),
            ):
                quarto_tool.select_quarto(self.root, environ={"PATH": ""})
            probe.assert_not_called()
        pin.unlink()
        with self.assertRaises(quarto_tool.QuartoUnavailableError):
            quarto_tool.select_quarto(self.root, environ={"PATH": ""})

    def test_real_synthetic_version_probe_handles_spaces(self) -> None:
        self.executable(self.explicit)
        self.assertEqual(
            quarto_tool.select_quarto(
                self.root,
                environ={"QUARTO": str(self.explicit), "PATH": "/usr/bin:/bin"},
            ),
            str(self.explicit),
        )

    def test_cli_refusal_has_nonzero_exit_and_no_selected_path(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(
                quarto_tool,
                "select_quarto",
                side_effect=quarto_tool.QuartoUnavailableError("synthetic refusal"),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(quarto_tool.main(), 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("synthetic refusal", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
