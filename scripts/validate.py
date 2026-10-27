"""Run tests with workspace-local scratch space and preserve each result, including failures."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from partlens.records import new_run_id
from partlens.secrets import redact


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stamp = new_run_id()
    scratch = Path(".partlens/tmp") / stamp
    scratch.mkdir(parents=True)
    log = Path(".partlens/validation") / f"tests-{stamp}.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(scratch.resolve()), TMP=str(scratch.resolve()), PYTHONIOENCODING="utf-8")
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=short",
               "--basetemp", str(scratch / "pytest"), *sys.argv[1:]]
    result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = redact(result.stdout + result.stderr)
    with log.open("x", encoding="utf-8") as f:
        f.write(output + f"\nexit_code={result.returncode}\n")
    print(output)
    print(f"Preserved test record: {log}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
