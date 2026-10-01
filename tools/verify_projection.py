"""Self-check verification executor for projection gating.

Runs this repository's projection test suite (native region policy,
admission, deterministic generation) and reports a check-result
envelope. The ambient projection system binds the verdict to the exact
subject it observed; this script only executes the provider's own
checks. Read-only against the checkout apart from git-ignored
interpreter scratch.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import which

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TARGET = "tests.test_projection"
TIMEOUT_SECONDS = 240


def _supports_call(candidate: str) -> bool:
    try:
        completed = subprocess.run(
            [candidate, "--help"], capture_output=True, text=True,
            timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return " call" in (completed.stdout + completed.stderr)


def find_mncs() -> str | None:
    for candidate in (
        os.environ.get("MNCS_BIN"),
        os.environ.get("MNCS_BINARY"),
        str(REPO_ROOT.parent / "mncs-language" / "target" / "release"
            / "mncs"),
        str(REPO_ROOT.parent / "mncs-language" / "target" / "debug"
            / "mncs"),
        which("mncs"),
    ):
        if (candidate and Path(candidate).is_file()
                and _supports_call(candidate)):
            return candidate
    return None


def report(verdict: str, **extra) -> int:
    payload = {"schema_version": "mncs.check-result/1",
               "verdict": verdict}
    payload.update(extra)
    print(json.dumps(payload, sort_keys=True))
    return {"pass": 0, "fail": 1}.get(verdict, 2)


def main() -> int:
    env = dict(os.environ)
    mncs = find_mncs()
    if mncs is None:
        return report("unknown", reason="toolchain-unavailable")
    env["MNCS_BIN"] = mncs
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", TEST_TARGET],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return report("unknown", reason="timeout")
    except OSError as error:
        return report("unknown", reason=f"launch-failed:{error}")
    tail = (completed.stderr.strip().splitlines() or [""])[-1][:200]
    if completed.returncode == 0:
        return report("pass", detail=tail)
    return report("fail", detail=tail)


if __name__ == "__main__":
    raise SystemExit(main())
