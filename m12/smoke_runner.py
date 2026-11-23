import importlib.util
import subprocess
import sys
import pathlib
import os
from typing import Tuple, Optional


def _find_repo_root_from_file(p: pathlib.Path) -> pathlib.Path:
    p = p.resolve()
    for parent in [p] + list(p.parents):
        if (parent / "m12").exists():
            return parent
    return p.parent


def smoke_import(
    path: str,
    timeout: int = 15,
    repo_root: Optional[str] = None,
) -> Tuple[bool, str]:
    p = pathlib.Path(path)
    if not p.is_absolute():
        # fall back: try relative to cwd, but root will be recomputed below
        p = pathlib.Path.cwd() / p

    if not p.exists():
        return False, f"missing:{path}"

    # robust root detection: always derive from target file location
    root = _find_repo_root_from_file(p)
    if repo_root:
        # if provided repo_root is valid and contains m12, prefer it
        rr = pathlib.Path(repo_root).resolve()
        if (rr / "m12").exists():
            root = rr

    code = r"""
import importlib.util, sys, os, traceback
root = os.environ.get("SMOKE_ROOT", "")
if root and root not in sys.path:
    sys.path.insert(0, root)

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

        msg_tail = (r.stderr.strip()[-800:] or r.stdout.strip()[-800:] or f"rc={r.returncode}")
        return False, f"smoke_exc:{msg_tail} | root={root}"
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s | root={root}"
    except Exception as e:
        return False, f"exc_outer:{e} | root={root}"
