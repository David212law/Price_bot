import importlib.util
import subprocess
import sys
import pathlib
import os
from typing import Tuple, Optional


def smoke_import(path: str, timeout: int = 15, repo_root: Optional[str] = None) -> Tuple[bool, str]:
    """
    Tool-based runtime smoke: execute the module by file path in a subprocess.

    Avoids using __file__ so the project's undefined-name detector stays clean.
    """
    root = pathlib.Path(repo_root).resolve() if repo_root else pathlib.Path.cwd().resolve()

    p = pathlib.Path(path)
    if not p.is_absolute():
        p = root / p

    if not p.exists():
        return False, f"missing:{path}"

    code = r"""
import importlib.util, sys
p = sys.argv[1]
spec = importlib.util.spec_from_file_location("m12_smoke_mod", p)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
"""

    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)

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
        msg = (r.stderr.strip()[-400:] or r.stdout.strip()[-400:] or f"rc={r.returncode}")
        return False, msg
    except subprocess.TimeoutExpired:
        return False, f"timeout>{timeout}s"
    except Exception as e:
        return False, f"exc:{e}"
