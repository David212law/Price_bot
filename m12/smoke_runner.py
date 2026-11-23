import importlib.util
import subprocess
import sys
import pathlib
import os
from typing import Tuple, Optional


def smoke_import(
    path: str,
    timeout: int = 15,
    repo_root: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Tool-based runtime smoke: execute the module by file path in a subprocess.

    We also pre-import `m12` to diagnose CI import-path issues.
    """
    root = pathlib.Path(repo_root).resolve() if repo_root else pathlib.Path.cwd().resolve()

    p = pathlib.Path(path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        return False, f"missing:{path}"

    code = r"""
import importlib.util, sys, os, importlib
root = os.environ.get("SMOKE_ROOT", "")
if root and root not in sys.path:
    sys.path.insert(0, root)

# pre-check: ensure `m12` is importable
try:
    importlib.import_module("m12")
except Exception as e:
    raise RuntimeError(
        f"preimport m12 failed: {e}; sys.path_head={sys.path[:8]}"
    )

p = sys.argv[1]
spec = importlib.util.spec_from_file_location("m12_smoke_mod", p)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
"""

    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env["SMOKE_ROOT"] = str(root)

    try:
        r = subprocess.run(
            [sys.executable, "-c", code, str(p)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if r.returncode == 0:
            return True, "ok"
        msg = (r.stderr.strip()[-800:] or r.stdout.strip()[-800:] or f"rc={r.returncode}")
        return False, msg
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s"
    except Exception as e:
        return False, f"exc:{e}"
