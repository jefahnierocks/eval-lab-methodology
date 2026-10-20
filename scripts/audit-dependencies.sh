#!/usr/bin/env bash
set -euo pipefail

readonly pip_audit_version="2.10.1"
readonly audit_python="${PROJECT_PIP_AUDIT_PYTHON:-$PWD/.cache/pip-audit/bin/python}"
if [[ ! -x "${audit_python}" ]]; then
  echo "Prepared pip-audit 2.10.1 environment is required; no tool was installed." >&2
  exit 2
fi
actual_audit_version="$("${audit_python}" -I -B -c 'import importlib.metadata; import sys; assert sys.version_info[:3] == (3, 13, 15); print(importlib.metadata.version("pip-audit"))')"
if [[ "${actual_audit_version}" != "${pip_audit_version}" ]]; then
  echo "Prepared pip-audit version does not match 2.10.1." >&2
  exit 2
fi
requirements_file="$(mktemp "${TMPDIR:-/tmp}/eval-lab-methodology-requirements.XXXXXX.txt")"
trap 'rm -f "${requirements_file}"' EXIT

uv export \
  --frozen \
  --all-extras \
  --no-emit-project \
  --format requirements-txt \
  --output-file "${requirements_file}" \
  --quiet
# This mandatory audit queries the advisory service; it is not an offline gate.
"${audit_python}" -I -B -m pip_audit --disable-pip -r "${requirements_file}"
