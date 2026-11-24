import importlib
import importlib.util
import subprocess
import sys
import pathlib
import os
from typing import Tuple, Optional


def _find_repo_root_from_target(p: pathlib.Path) -> pathlib.Path:
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
        p = pathlib.Path.cwd() / p
    if not p.exists():
        return False, f"missing:{path}"

    if repo_root and pathlib.Path(repo_root, "m12").exists():
        root = pathlib.Path(repo_root).resolve()
    else:
        root = _find_repo_root_from_target(p)

    root_s = str(root)
    target_s = str(p)

    code = r"""
import importlib, importlib.util, sys, os, traceback
root = os.environ["SMOKE_ROOT"]
target = os.environ["SMOKE_TARGET"]

if root not in sys.path:
    sys.path.insert(0, root)

print("LAB_DEBUG root=", root)
print("LAB_DEBUG has_m12=", os.path.isdir(os.path.join(root, "m12")))
print("LAB_DEBUG sys.path_head=", sys.path[:8])

importlib.import_module("m12")
print("LAB_IMPORT_m12=OK")

spec = importlib.util.spec_from_file_location("lab_target_mod", target)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("LAB_IMPORT_TARGET=OK")
"""

    env = dict(os.environ)
    env["SMOKE_ROOT"] = root_s
    env["SMOKE_TARGET"] = target_s

    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=root_s,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode == 0:
            return True, "ok"

        # include stdout/stderr fully enough so CI prints the debug
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        diag = (out + "\n" + err).strip()
        return False, diag[-3000:] if diag else f"rc={r.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s | root={root_s}"
    except Exception as e:
        return False, f"exc_outer:{e} | root={root_s}"
