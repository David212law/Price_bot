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
    Runtime smoke: execute the module by file path in a subprocess.

    Debug-friendly: if "m12" isn't importable inside the subprocess,
    we return error details including sys.path head.
    """
    root = pathlib.Path(repo_root).resolve() if repo_root else pathlib.Path.cwd().resolve()

    p = pathlib.Path(path)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        return False, f"missing:{path}"

    code = r"""
import importlib.util, sys, os, traceback
root = os.environ.get("SMOKE_ROOT", "")
if root:
    # Force repo_root at sys.path[0]
    if not sys.path or sys.path[0] != root:
        sys.path.insert(0, root)

p = sys.argv[1]

# pre-check
try:
    __import__("m12")
except Exception as e:
    raise RuntimeError(f"preimport m12 failed: {e} | root={root} | sys.path_head={sys.path[:8]}")

spec = importlib.util.spec_from_file_location("m12_smoke_mod", p)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except ImportError as e:
    raise RuntimeError(f"importerr: {e} | root={root} | sys.path_head={sys.path[:8]}")
except Exception as e:
    # show tail traceback to avoid huge logs
    tb = traceback.format_exc()
    raise RuntimeError(f"exc: {e} | root={root} | sys.path_head={sys.path[:8]} | tb_tail={tb[-600:]}")
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
        return False, f"exc_outer:{e}"
