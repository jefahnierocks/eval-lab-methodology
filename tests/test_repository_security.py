"""Exercise repository security boundaries using synthetic data only."""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import check_repository_security as security


def fixture_environment() -> dict[str, str]:
    allowed = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_SYSTEM=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    return env


def git(
    repo: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        env=fixture_environment(),
        capture_output=True,
        check=check,
        timeout=10,
    )


class PathTests(unittest.TestCase):
    def test_similar_names_and_leaf_are_permitted(self):
        data = b"private.txt\0privacy/a\0not-private/a\0private\0docs/private-note.md\0"
        self.assertEqual(security.private_paths(data), [])

    def test_root_nested_and_case_variants_are_rejected(self):
        for path in (b"private/a", b"nested/private/a", b"other/PrIvAtE/a"):
            with self.subTest(path=path):
                self.assertEqual(security.private_paths(path + b"\0"), [path])

    def test_nul_and_newline_names_are_not_split_as_lines(self):
        data = b"line\nbreak.txt\0nested/private/line\nbreak.txt\0safe.txt\0"
        self.assertEqual(
            security.private_paths(data), [b"nested/private/line\nbreak.txt"]
        )

    def test_malformed_git_output_fails_closed(self):
        for data in (b"unterminated", b"\0", b"name\0\0"):
            with self.subTest(data=data), self.assertRaises(security.SecurityError):
                security.private_paths(data)

    def test_empty_index_is_valid(self):
        self.assertEqual(security.private_paths(b""), [])

    def test_real_index_and_ignored_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "-q")
            (root / ".gitignore").write_text("private/\n.cache/\n")
            (root / "private.txt").write_text("synthetic\n")
            (root / "line\nbreak.txt").write_text("synthetic\n")
            git(root, "add", "--", ".gitignore", "private.txt", "line\nbreak.txt")
            security.check_paths(root)
            for index, directory in enumerate(("private", "private", "PrIvAtE")):
                # Distinct parents avoid case-insensitive filesystem collisions.
                path = root / f"parent-{index}" / directory / "example.txt"
                path.parent.mkdir(parents=True)
                path.write_text("synthetic\n")
                relative = path.relative_to(root).as_posix()
                if directory == "private":
                    ignored = git(
                        root, "check-ignore", "--quiet", relative, check=False
                    )
                    self.assertEqual(ignored.returncode, 0)
                git(root, "add", "-f", "--", relative)
            with self.assertRaises(security.SecurityError):
                security.check_paths(root)


class ScannerTests(unittest.TestCase):
    def test_environment_uses_only_bundled_rules(self):
        with patch.dict(
            os.environ,
            {
                "GITLEAKS_CONFIG": "untrusted-policy",
                "GITLEAKS_CONFIG_TOML": "untrusted-rules",
                "GITLEAKS_BASELINE_PATH": "untrusted-baseline",
                "GITLEAKS_LOG_LEVEL": "trace",
                "GIT_DIR": "untrusted-git-dir",
                "GIT_WORK_TREE": "untrusted-work-tree",
                "GIT_INDEX_FILE": "untrusted-index",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "alias.diff",
                "GIT_CONFIG_VALUE_0": "untrusted-command",
                "GIT_CONFIG_GLOBAL": "untrusted-global-config",
                "GIT_CONFIG_SYSTEM": "untrusted-system-config",
                "GIT_CONFIG_NOSYSTEM": "0",
                "UNRELATED_AMBIENT_VALUE": "omit-this",
            },
        ):
            environment = security.scanner_environment()
        keys = [key for key in environment if key.upper().startswith("GITLEAKS_")]
        self.assertEqual(keys, ["GITLEAKS_CONFIG_TOML"])
        self.assertEqual(environment["GITLEAKS_CONFIG_TOML"], security.NATIVE_CONFIG)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertLessEqual(
            set(environment),
            {
                "PATH",
                "HOME",
                "TMPDIR",
                "LANG",
                "LC_ALL",
                "SYSTEMROOT",
                "GIT_CONFIG_GLOBAL",
                "GIT_CONFIG_NOSYSTEM",
                "GITLEAKS_CONFIG_TOML",
            },
        )
        for key in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"):
            if key in os.environ:
                self.assertEqual(environment[key], os.environ[key])

    def test_separate_scans_and_non_suppressible_native_flags(self):
        with patch.object(
            security,
            "command",
            side_effect=[
                os.fsencode(Path.cwd()) + b"\n",
                b"source.py\0",
                b"false\n",
                b"8.30.1\n",
                b"",
                b"staged",
                b"",
                b"unstaged",
                b"",
            ],
        ) as command:
            security.check_security(Path("."))
        calls = command.call_args_list
        self.assertEqual(
            calls[0].args[0],
            ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"],
        )
        self.assertEqual(
            calls[2].args[0], ["git", "rev-parse", "--is-shallow-repository"]
        )
        self.assertIn("--all", calls[4].args[0][-2])
        self.assertIn("--full-history", calls[4].args[0][-2])
        self.assertIn("--cached", calls[5].args[0])
        self.assertNotIn("--cached", calls[7].args[0])
        self.assertEqual(calls[6].kwargs["payload"], b"staged")
        self.assertEqual(calls[8].kwargs["payload"], b"unstaged")
        for call in (calls[4], calls[6], calls[8]):
            self.assertIn("--redact=100", call.args[0])
            self.assertIn("--ignore-gitleaks-allow", call.args[0])
            self.assertIn(os.devnull, call.args[0])

    def test_staged_data_reverted_in_worktree_is_still_scanned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "-q")
            path = root / "example.txt"
            path.write_text("staged-only-marker\n")
            git(root, "add", "example.txt")
            path.write_text("")
            original_run = subprocess.run
            payloads = []

            def run(arguments, **kwargs):
                if arguments[0] == "gitleaks":
                    if arguments[1] == "stdin":
                        payloads.append(kwargs["input"])
                    output = b"8.30.1\n" if arguments[1] == "version" else b""
                    return subprocess.CompletedProcess(arguments, 0, output, b"")
                return original_run(arguments, **kwargs)

            with patch.object(security.subprocess, "run", side_effect=run):
                security.check_security(root)
            self.assertEqual(len(payloads), 2)
            self.assertIn(b"+staged-only-marker", payloads[0])
            self.assertIn(b"-staged-only-marker", payloads[1])

    def test_repository_policy_files_are_rejected_without_reading(self):
        for name in (".gitleaks.toml", ".gitleaksignore"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / name).symlink_to(root / "absent")
                with patch.object(security, "command") as command:
                    with self.assertRaisesRegex(security.SecurityError, "policy files"):
                        security.check_security(root, paths_only=True)
                    command.assert_not_called()

    def test_scanner_failure_stops_before_later_scans(self):
        for failure_position in (4, 6, 8):
            with self.subTest(failure_position=failure_position):
                responses = [
                    os.fsencode(Path.cwd()) + b"\n",
                    b"",
                    b"false\n",
                    b"8.30.1\n",
                    b"",
                    b"staged",
                    b"",
                    b"unstaged",
                    b"",
                ]
                responses[failure_position] = security.SecurityError("scan refused")
                with (
                    patch.object(security, "command", side_effect=responses) as command,
                    self.assertRaises(security.SecurityError),
                ):
                    security.check_security(Path("."))
                self.assertEqual(command.call_count, failure_position + 1)

    def test_paths_only_does_not_require_scanner(self):
        with patch.object(
            security,
            "command",
            side_effect=[os.fsencode(Path.cwd()) + b"\n", b"safe\0"],
        ) as command:
            security.check_security(Path("."), paths_only=True)
        self.assertEqual(command.call_count, 2)
        self.assertEqual(
            command.call_args_list[0].args[0],
            ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"],
        )

    def test_wrong_scanner_version_is_rejected(self):
        with (
            patch.object(
                security,
                "command",
                side_effect=[
                    os.fsencode(Path.cwd()) + b"\n",
                    b"",
                    b"false\n",
                    b"8.29.0\n",
                ],
            ),
            self.assertRaises(security.SecurityError),
        ):
            security.check_security(Path("."))

    def test_missing_scanner_is_rejected_without_output(self):
        with (
            patch.object(
                security.subprocess, "run", side_effect=FileNotFoundError("opaque")
            ),
            self.assertRaisesRegex(security.SecurityError, "could not complete"),
        ):
            security.command(["gitleaks", "version"], Path("."))

    def test_git_errors_are_rejected(self):
        failure = subprocess.CompletedProcess([], 128, b"opaque", b"opaque")
        with (
            patch.object(security.subprocess, "run", return_value=failure),
            self.assertRaises(security.SecurityError),
        ):
            security.check_paths(Path("."))

    def test_scanner_findings_and_errors_are_not_echoed(self):
        for exit_code in (1, 2, 127):
            with self.subTest(exit_code=exit_code):
                failure = subprocess.CompletedProcess(
                    [], exit_code, b"opaque", b"opaque"
                )
                output = io.StringIO()
                with (
                    patch.object(security.subprocess, "run", return_value=failure),
                    patch.object(security.sys, "argv", ["security"]),
                    redirect_stdout(output),
                    redirect_stderr(output),
                ):
                    self.assertEqual(security.main(), 1)
                self.assertNotIn("opaque", output.getvalue())
                self.assertIn("repository security: FAIL", output.getvalue())

    def test_subprocess_timeout_fails_closed(self):
        with (
            patch.object(
                security.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("opaque", 1),
            ),
            self.assertRaises(security.SecurityError),
        ):
            security.command(["gitleaks", "version"], Path("."))


class RepositoryIdentityTests(unittest.TestCase):
    def test_wrong_git_root_is_rejected_before_index_or_scanner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            git(root, "init", "-q")
            nested = root / "nested"
            nested.mkdir()
            for paths_only in (False, True):
                with (
                    self.subTest(paths_only=paths_only),
                    self.assertRaisesRegex(security.SecurityError, "does not match"),
                ):
                    security.check_security(nested, paths_only=paths_only)

    def test_malformed_root_answer_fails_before_index(self):
        for answer in (
            b"",
            b"relative\n",
            b"/missing-terminator",
            b"/root\nextra\n",
            b"/root\0\n",
        ):
            with (
                self.subTest(answer=answer),
                patch.object(security, "command", return_value=answer) as command,
                self.assertRaises(security.SecurityError),
            ):
                security.check_security(Path("."), paths_only=True)
            self.assertEqual(command.call_count, 1)

    def test_failed_root_answer_fails_before_index(self):
        with (
            patch.object(
                security, "command", side_effect=security.SecurityError("root failed")
            ) as command,
            self.assertRaises(security.SecurityError),
        ):
            security.check_security(Path("."), paths_only=True)
        self.assertEqual(command.call_count, 1)

    def test_malformed_or_shallow_answers_fail_before_scanner(self):
        for answer in (
            b"",
            b"true\n",
            b"false",
            b"False\n",
            b" false\n",
            b"false\nextra\n",
        ):
            with (
                self.subTest(answer=answer),
                patch.object(
                    security,
                    "command",
                    side_effect=[os.fsencode(Path.cwd()) + b"\n", b"", answer],
                ) as command,
                self.assertRaisesRegex(security.SecurityError, "non-shallow"),
            ):
                security.check_security(Path("."))
            self.assertEqual(command.call_count, 3)

    def test_failed_shallow_answer_fails_before_scanner(self):
        with (
            patch.object(
                security,
                "command",
                side_effect=[
                    os.fsencode(Path.cwd()) + b"\n",
                    b"",
                    security.SecurityError("history failed"),
                ],
            ) as command,
            self.assertRaises(security.SecurityError),
        ):
            security.check_security(Path("."))
        self.assertEqual(command.call_count, 3)

    def test_real_shallow_clone_is_rejected_without_scanner(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            clone = base / "shallow"
            git(base, "init", "-q", str(source))
            for number in (1, 2):
                (source / "example.txt").write_text(
                    f"synthetic fixture revision {number}\n"
                )
                git(source, "add", "example.txt")
                git(
                    source,
                    "-c",
                    "user.name=Synthetic Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    f"test: synthetic revision {number}",
                )
            git(base, "clone", "--quiet", "--depth=1", source.as_uri(), str(clone))
            self.assertEqual(
                git(clone, "rev-parse", "--is-shallow-repository").stdout, b"true\n"
            )
            original_command = security.command
            with (
                patch.object(security, "command", wraps=original_command) as command,
                self.assertRaisesRegex(security.SecurityError, "non-shallow"),
            ):
                security.check_security(clone)
            self.assertTrue(
                all(call.args[0][0] == "git" for call in command.call_args_list)
            )
            self.assertEqual(len(command.call_args_list), 3)
            # Path-only validation remains useful without claiming full-history coverage.
            security.check_security(clone, paths_only=True)

    def test_process_invocations_receive_sanitized_environment(self):
        result = subprocess.CompletedProcess([], 0, b"safe", b"")
        with (
            patch.dict(
                os.environ,
                {
                    "GIT_DIR": "redirect",
                    "GITLEAKS_CONFIG": "override",
                    "UNRELATED_AMBIENT_VALUE": "omit",
                },
            ),
            patch.object(security.subprocess, "run", return_value=result) as run,
        ):
            security.command(["git", "rev-parse", "--show-toplevel"], Path("."))
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("GIT_DIR", environment)
        self.assertNotIn("GITLEAKS_CONFIG", environment)
        self.assertNotIn("UNRELATED_AMBIENT_VALUE", environment)
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GITLEAKS_CONFIG_TOML"], security.NATIVE_CONFIG)


if __name__ == "__main__":
    unittest.main()
