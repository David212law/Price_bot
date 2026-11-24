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

    # IMPORTANT: root is injected as a literal into the subprocess code
    code = f"""
import importlib, sys
root = {root_s!r}
if root not in sys.path:
    sys.path.insert(0, root)

# hard pre-check
importlib.import_module("m12")

import importlib.util
p = {str(p)!r}
spec = importlib.util.spec_from_file_location("m12_smoke_mod", p)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
"""

    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            cwd=root_s,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode == 0:
            return True, "ok"

        msg = (r.stderr.strip()[-800:] or r.stdout.strip()[-800:] or f"rc={r.returncode}")
        # include minimal diagnostics
        return False, f"{msg} | root={root_s}"
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s | root={root_s}"
    except Exception as e:
        return False, f"exc:{e} | root={root_s}"
