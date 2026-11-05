"""D-537: Pipeline Health Check — Auto-detect drift & bugs.

Run before every pipeline execution. Exits with code 1 on FAIL.
If FAIL, weekly_research.yml will alert (Bale) and skip pipeline.

Checks:
  1. Contract integrity (CONFIG matches all stages)
  2. Blacklist compliance (MLP, improvements respect blacklist)
  3. Stale outputs (upstream newer than downstream)
  4. Profiler schema drift (validation vs metrics_by_regime)
  5. Stage outputs exist
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "research_lab" / "logs"


def check_contract():
    """Verify CONFIG is single source of truth."""
    issues = []
    try:
        from research_lab.pipeline_contract import CONFIG, BLACKLIST, validate
        c_issues = validate()
        for i in c_issues:
            issues.append(f"contract: {i}")
    except Exception as e:
        return [f"contract: cannot import ({e})"]

    # Verify composer uses same CONFIG
    try:
        from research_lab.composer import CONFIG as comp_config
        if dict(comp_config) != dict(CONFIG):
            issues.append("contract: composer.CONFIG != pipeline_contract.CONFIG")
    except Exception as e:
        issues.append(f"contract: cannot import composer ({e})")

    # Verify MLP imports from pipeline_contract (not composer)
    mlp_src = (ROOT / "research_lab" / "multi_layer_portfolio.py").read_text()
    if "from research_lab.composer import CONFIG" in mlp_src:
        issues.append("contract: MLP still imports CONFIG from composer (should be pipeline_contract)")
    if "from research_lab.pipeline_contract import CONFIG" not in mlp_src:
        issues.append("contract: MLP does not import CONFIG from pipeline_contract")

    return issues


def check_blacklist_compliance():
    """Verify MLP picks respect blacklist."""
    from research_lab.pipeline_contract import BLACKLIST
    issues = []

    mlp_path = LOGS / "multi_layer_portfolio.json"
    if mlp_path.exists():
        try:
            mlp = json.loads(mlp_path.read_text())
            for pick in mlp.get("picks", []):
                if pick.get("strategy") in BLACKLIST:
                    issues.append(
                        f"blacklist: MLP includes blacklisted {pick['strategy']}_{pick.get('symbol','?')}"
                    )
        except Exception as e:
            issues.append(f"blacklist: cannot read MLP output ({e})")

    return issues


def check_stale_outputs():
    """Verify upstream outputs are not newer than downstream (which would mean stale downstream)."""
    issues = []
    chain = [
        ("thesis_evidence.json", "thesis_deduped.json", "thesis_dedup"),
        ("thesis_deduped.json", "multi_layer_portfolio.json", "MLP"),
    ]
    for upstream_name, downstream_name, downstream_label in chain:
        up = LOGS / upstream_name
        down = LOGS / downstream_name
        if up.exists() and down.exists():
            up_mtime = up.stat().st_mtime
            down_mtime = down.stat().st_mtime
            # If upstream generated AFTER downstream, downstream is stale
            if up_mtime > down_mtime + 60:  # 60s grace
                issues.append(
                    f"stale: {downstream_label} is older than upstream "
                    f"(diff {int(up_mtime - down_mtime)}s)"
                )
    return issues


def check_profiler_schema():
    """Check that profiler has a healthy ratio of validation vs metrics_by_regime."""
    issues = []
    state_path = LOGS / "profiles" / "state.json"
    if not state_path.exists():
        return ["schema: profiles/state.json missing"]

    try:
        state = json.loads(state_path.read_text())
        done = state.get("done", {})
        total = len(done)
        with_val = sum(1 for v in done.values()
                      if isinstance(v, dict) and v.get("validation"))
        with_mbr = sum(1 for v in done.values()
                      if isinstance(v, dict) and v.get("metrics_by_regime"))
        # Healthy: at least 30% have validation
        if total > 0 and with_val / total < 0.20:
            issues.append(
                f"schema: only {with_val}/{total} ({100*with_val//total}%) have validation "
                f"(expected >20%)"
            )
        if total > 0 and with_mbr / total < 0.40:
            issues.append(
                f"schema: only {with_mbr}/{total} ({100*with_mbr//total}%) have metrics_by_regime "
                f"(expected >40%)"
            )
    except Exception as e:
        issues.append(f"schema: cannot parse state.json ({e})")

    return issues


def check_stage_outputs():
    """Verify all expected stage outputs exist."""
    from research_lab.pipeline_contract import STAGES_MANIFEST
    issues = []
    for stage_name, meta in STAGES_MANIFEST.items():
        for output in meta.get("outputs", []):
            # Composer report, thesis files, MLP json, etc.
            if output == "composer_report.md":
                path = LOGS / "composer_report.md"
            else:
                path = LOGS / output
            if not path.exists():
                issues.append(f"missing: {stage_name} output {output} does not exist")
    return issues


def run_all_checks():
    print(f"Pipeline Health Check — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 72)

    checks = [
        ("contract", check_contract),
        ("blacklist", check_blacklist_compliance),
        ("stale_outputs", check_stale_outputs),
        ("profiler_schema", check_profiler_schema),
        ("stage_outputs", check_stage_outputs),
    ]

    all_issues = []
    for name, fn in checks:
        try:
            issues = fn()
            if issues:
                print(f"  ❌ {name}: {len(issues)} issue(s)")
                for i in issues:
                    print(f"     - {i}")
                all_issues.extend([f"{name}: {i}" for i in issues])
            else:
                print(f"  ✅ {name}: OK")
        except Exception as e:
            print(f"  ❌ {name}: EXCEPTION ({e})")
            all_issues.append(f"{name}: exception ({e})")

    print("=" * 72)
    if all_issues:
        print(f"❌ HEALTH CHECK FAILED — {len(all_issues)} issue(s)")
        print("   Pipeline execution should be SKIPPED.")
        return 1
    else:
        print("✅ HEALTH CHECK PASSED — pipeline is consistent")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_checks())
