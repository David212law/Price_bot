import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    print(">>", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=HERE, check=False, text=True,
                       capture_output=True)
    if p.stdout:
        print(p.stdout, flush=True)
    if p.stderr:
        print(p.stderr, file=sys.stderr, flush=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}")
    return p.returncode

def main():
    run([sys.executable, "prefilter.py"])
    run([sys.executable, "researcher.py"])
    run([sys.executable, "verify.py"])

if __name__ == "__main__":
    main()
