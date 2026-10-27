"""Run each historical Tcl/Tk widget case in a fresh interpreter, retaining every assertion.

On CPython 3.14/Windows, the retained chat and settings cases pass independently but the later Tcl
interpreter can fail loading existing runtime files when both cases share pytest's process. The modern
WebView2 application is tested separately in its real renderer; no widget test is skipped or mocked here.
"""
import os
from pathlib import Path
import subprocess
import sys


def isolated_case(node, tmp_path):
    if os.environ.get('_PARTLENS_NATIVE_WIDGET_CASE') == node:
        return False
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--tb=short', node,
         '--basetemp', str(tmp_path/'native-process')],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, '_PARTLENS_NATIVE_WIDGET_CASE': node},
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    assert result.returncode == 0, result.stdout + result.stderr
    return True
