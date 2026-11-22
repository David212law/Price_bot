"""M12 Verify — independent check with awk."""
import subprocess, os, json, csv

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(_HERE, "research")

def awk_win_rate(csv_path):
    r = subprocess.run(
        ["awk", "-F,", "NR>1{w+=$2; n++} END{if(n>0) print w/n; else print 0}", csv_path],
        capture_output=True, text=True)
    return float(r.stdout.strip())

def awk_mean(csv_path, col):
    r = subprocess.run(
        ["awk", "-F,", f"NR>1{{s+=${col}; n++}} END{{if(n>0) print s/n; else print 0}}", csv_path],
        capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    print("=" * 70)
    print(" M12 Verify — Python vs Shell")
    print("=" * 70)
    print()

    if not os.path.exists(CSV_DIR):
        print(f"❌ {CSV_DIR} not found. Run researcher first.")
        return

    csvs = sorted([f for f in os.listdir(CSV_DIR)
                   if f.endswith(".csv") and f != "SUMMARY.csv"])
    if not csvs:
        print(f"❌ No CSV files in {CSV_DIR}")
        return

    print(f"Found {len(csvs)} CSV files\n")
    print(f"  {'File':32s} {'Py_WR':>8s} {'Sh_WR':>8s} {'Py_Ret':>10s} {'Sh_Ret':>10s} {'Status':>8s}")
    print("  " + "-" * 84)

    all_pass = True
    summary_rows = []

    for fname in csvs:
        path = os.path.join(CSV_DIR, fname)
        json_path = path.replace(".csv", ".json")
        if not os.path.exists(json_path):
            print(f"  {fname:32s} ⚠️  no .json")
            continue

        py = json.load(open(json_path))
        sh_wr = awk_win_rate(path)
        sh_ret = awk_mean(path, 3)

        wr_ok = abs(sh_wr - py["win_rate"]) < 0.01
        ret_ok = abs(sh_ret - py["avg_ret"]) < 0.001
        ok = wr_ok and ret_ok
        if not ok: all_pass = False
        status = "PASS" if ok else "FAIL"

        print(f"  {fname:32s} {py['win_rate']:8.4f} {sh_wr:8.4f} "
              f"{py['avg_ret']:10.6f} {sh_ret:10.6f} {status:>8s}")

        summary_rows.append({
            "file": fname, "strategy": py["strategy"], "regime": py["regime"],
            "n": py["n"], "win_rate": py["win_rate"], "shell_win_rate": sh_wr,
            "avg_ret": py["avg_ret"], "shell_avg_ret": sh_ret,
            "match": "YES" if ok else "NO",
        })

    print()
    print("=" * 70)
    if all_pass:
        print(" ALL VERIFICATIONS PASSED")
        print(" -> Python = Shell on every number")
        print(" -> Results are TRUSTED")
    else:
        print(" VERIFICATION FAILED")
        print(" -> STOP. Find bug in calc.py first.")
    print("=" * 70)

    with open(f"{CSV_DIR}/SUMMARY.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "file", "strategy", "regime", "n", "win_rate", "shell_win_rate",
            "avg_ret", "shell_avg_ret", "match"])
        w.writeheader()
        w.writerows(summary_rows)
    print(f"\nSUMMARY.csv written")

if __name__ == "__main__":
    main()
