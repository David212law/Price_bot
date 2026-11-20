import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    print(">>", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=HERE, check=True)

def main():
    run([sys.executable, "prefilter.py"])
    run([sys.executable, "researcher.py"])
    run([sys.executable, "verify.py"])

if __name__ == "__main__":
    main()
