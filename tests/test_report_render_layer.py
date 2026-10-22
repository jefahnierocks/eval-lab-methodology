from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.publication_safety import (
    assert_publication_content_is_safe,
    normalized_name_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_methodology_report.py"
SAMPLE = ROOT / "evidence" / "sample-lab-report.json"
REPORT = ROOT / "reports" / "methodology-report.qmd"


class ReportRenderLayerTests(unittest.TestCase):
    def test_validate_only_accepts_public_safe_sample(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--evidence", str(SAMPLE), "--validate-only"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("validated public-safe evidence", completed.stdout)

    def test_validate_only_refuses_non_public_safe_json(self) -> None:
        sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
        invalid = copy.deepcopy(sample)
        invalid["manifest"]["sanitization"]["status"] = "pending"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "non-public-safe.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--evidence",
                    str(path),
                    "--validate-only",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("public-safe", completed.stderr)

    def test_validate_only_refuses_independent_content_leak(self) -> None:
        sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
        sample["manifest"]["identity_domain"]["reason"] = (
            "synthetic leak probe at https://example.internal/v1"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "content-leak.json"
            path.write_text(json.dumps(sample), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--evidence",
                    str(path),
                    "--validate-only",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("independent recursive content scan", completed.stderr)

    def test_content_scan_refuses_hash_only_private_name_match(self) -> None:
        marker = "synthetic-public-boundary-marker"
        with self.assertRaisesRegex(
            ValueError, "hashed private-identifier denylist"
        ) as raised:
            assert_publication_content_is_safe(
                {"text": marker},
                private_name_sha256s=frozenset({normalized_name_sha256(marker)}),
            )
        self.assertNotIn(marker, str(raised.exception))

    def test_report_contains_required_verbatim_labels(self) -> None:
        qmd = REPORT.read_text(encoding="utf-8")
        for needle in (
            "enforcing:superiority-by-margin",
            "bootstrap_ci_low_gt_margin",
            "enhanced:two-stage-bootstrap",
            "enhanced:wilcoxon-signed-rank",
            "enhanced:glmm-logistic",
            "alternative:",
            "sign['alternative']",
            "reported_only:{text(sign['reported_only'])}",
            "does not gate",
            "non-gating additive estimator",
        ):
            self.assertIn(needle, qmd)


class QuartoRenderSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="quarto render selection ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / ".quarto-version").write_text("1.10.18\n", encoding="utf-8")
        self.tool = self.root / "explicit tool/quarto"
        self.tool.parent.mkdir()
        self.tool.write_text("#!/bin/sh\nprintf '1.10.18\\n'\n", encoding="utf-8")
        self.tool.chmod(0o755)
        self.report = self.root / "methodology-report.qmd"
        self.report.write_text("synthetic report fixture", encoding="utf-8")
        self.output = self.root / "output"
        spec = importlib.util.spec_from_file_location("renderer_under_test", SCRIPT)
        self.renderer = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            spec.loader.exec_module(self.renderer)
        self.args = argparse.Namespace(
            evidence=str(self.root / "synthetic.json"),
            report=str(self.report),
            output_dir=str(self.output),
            validate_only=False,
        )
        self.document = {"report": {"campaign_id": "synthetic"}}

    def test_validate_only_does_not_select_or_probe_quarto(self) -> None:
        self.args.validate_only = True
        with (
            patch.object(self.renderer, "parse_args", return_value=self.args),
            patch.object(
                self.renderer, "load_and_validate", return_value=self.document
            ),
            patch.object(self.renderer, "select_quarto") as selector,
            patch.object(self.renderer.subprocess, "run") as process,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(self.renderer.main(), 0)
        selector.assert_not_called()
        process.assert_not_called()
        self.assertFalse(self.output.exists())

    def gate_selection(
        self, environment: dict[str, str]
    ) -> subprocess.CompletedProcess:
        """Run only the gate's real selection prelude, never its native gate."""
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "quarto_tool.py").write_bytes(
            (ROOT / "scripts/quarto_tool.py").read_bytes()
        )
        binaries = self.root / "binaries"
        binaries.mkdir()
        (binaries / "python3").symlink_to(Path(sys.executable).resolve())
        gate = (ROOT / "scripts/run-merge-gate.sh").read_text(encoding="utf-8")
        prelude = gate[gate.index('QUARTO="$(') : gate.index("wheel_dir=")]
        return subprocess.run(
            ["/bin/bash", "-c", "set -e\n" + prelude + '\nprintf "%s\\n" "$QUARTO"'],
            cwd=self.root,
            env={**environment, "PATH": f"{binaries}{os.pathsep}/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_gate_and_renderer_use_the_same_selected_spaced_path(self) -> None:
        environment = {
            **os.environ,
            "QUARTO": str(self.tool),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        gate = self.gate_selection(environment)
        self.assertEqual(gate.returncode, 0, gate.stderr)
        self.assertEqual(gate.stdout.strip(), str(self.tool))
        self.report.with_suffix(".html").write_text(
            "synthetic rendered fixture", encoding="utf-8"
        )
        with (
            patch.dict(os.environ, environment),
            patch.object(self.renderer, "REPO_ROOT", self.root),
            patch.object(self.renderer, "parse_args", return_value=self.args),
            patch.object(
                self.renderer, "load_and_validate", return_value=self.document
            ),
            patch.object(
                self.renderer.subprocess,
                "run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, "1.10.18\n", ""),
                    subprocess.CompletedProcess([], 0),
                ],
            ) as process,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(self.renderer.main(), 0)
        self.assertEqual(process.call_count, 2)
        self.assertEqual(
            process.call_args_list[0].args[0], [gate.stdout.strip(), "--version"]
        )
        self.assertEqual(process.call_args_list[1].args[0][0], gate.stdout.strip())
        self.assertEqual(process.call_args_list[1].args[0][1], "render")
        self.assertTrue((self.output / "methodology-report.html").is_file())

    def test_invalid_explicit_choice_stops_gate_and_renderer_before_render(
        self,
    ) -> None:
        environment = {**os.environ, "QUARTO": str(self.root / "missing tool")}
        gate = self.gate_selection(environment)
        self.assertNotEqual(gate.returncode, 0)
        self.assertEqual(gate.stdout, "")
        with (
            patch.dict(os.environ, environment),
            patch.object(self.renderer, "REPO_ROOT", self.root),
            patch.object(self.renderer, "parse_args", return_value=self.args),
            patch.object(
                self.renderer, "load_and_validate", return_value=self.document
            ),
            patch.object(self.renderer.subprocess, "run") as process,
            redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            self.renderer.main()
        process.assert_not_called()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
