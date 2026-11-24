import os
import subprocess
import sys
import pathlib
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
    """
    Tool-based runtime smoke:
    - compute repo_root from target file location (robust on CI)
    - inject repo_root into sys.path
    - execute target via runpy.run_path
    """
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

    root_s = str(root)
    target_s = str(p)

    code = r"""
import runpy, sys, os
root = os.environ["SMOKE_ROOT"]
target = os.environ["SMOKE_TARGET"]

if root not in sys.path:
    sys.path.insert(0, root)

print(f"SMOKE_DEBUG root={root} has_m12={os.path.isdir(os.path.join(root,'m12'))} sys_path_head={sys.path[:6]}")
runpy.run_path(target, run_name="__main__")
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

        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        return False, (out + "\n" + err)[-2000:] or f"rc={r.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s | root={root_s}"
    except Exception as e:
        return False, f"exc_outer:{e} | root={root_s}"
