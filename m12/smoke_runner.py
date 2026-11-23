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
        p = pathlib.Path.cwd() / p
    if not p.exists():
        return False, f"missing:{path}"

    root = _find_repo_root_from_file(p)
    if repo_root:
        rr = pathlib.Path(repo_root).resolve()
        if (rr / "m12").exists():
            root = rr

    code = r"""
import importlib.util, sys, os, traceback, importlib
root = os.environ.get("SMOKE_ROOT", "")
if root and root not in sys.path:
    sys.path.insert(0, root)

# verify m12 is importable in this subprocess
try:
    importlib.import_module("m12")
except Exception as e:
    raise RuntimeError(
        f"preimport m12 failed: {e} | root={root} | has_m12={os.path.isdir(os.path.join(root,'m12'))} | sys_path_head={sys.path[:6]}"
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

        tail = (r.stderr.strip()[-500:] or r.stdout.strip()[-500:] or f"rc={r.returncode}")
        return False, f"smoke_exc:{tail} | root={root} | has_m12={(root/'m12').exists()}"
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s | root={root}"
    except Exception as e:
        return False, f"exc_outer:{e} | root={root}"
