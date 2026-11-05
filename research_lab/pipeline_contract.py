"""D-537: Pipeline Contract — Single Source of Truth

All pipeline stages MUST import CONFIG/BLACKLIST from here.
This prevents GAP-1 (MLP not seeing blacklist) type bugs.

History:
  D-536: 3 gaps discovered (MLP blacklist, dedup SR, profiler schema)
  D-537: centralized config to prevent future drift
"""

CONTRACT_VERSION = "D-537.1"

# ═══════════════════════════════════════════════════════════════════════
# CANONICAL CONFIG (single source for all stages)
# ═══════════════════════════════════════════════════════════════════════
CONFIG = {
    "min_n": 30, "min_q_pass": 4, "min_ann_sr": 1.5,
    "max_corr": 0.4, "min_improvement": 1.10, "max_components": 3,
    "exclude_families": ["FUNDING_M31"],
    "blacklist": ["M31_THRESHOLD", "M31_SMA", "M31_MOMENTUM", "M31_EMA", "M31_QUANTILE"],
    "m31_cap": {"hyperliquid": 0.65, "aster": 0.40, "kucoin": 0.30},
    "min_overlap_days": 60,
    # D-408: Strict thresholds for auto-suggesting to Bale
    "strict_approval": {
        "min_sr_ratio": 1.30,      # combination >= M31 x 1.30
        "max_corr": 0.30,           # all components corr < 0.30 with M31
        "max_dd_ratio": 0.80,       # combo MaxDD <= M31 MaxDD x 0.80
        "min_n_days": 50,          # need 200+ overlapping days
    },   # D-400c: was 20, too noisy
}

# ═══════════════════════════════════════════════════════════════════════
# Convenience aliases
# ═══════════════════════════════════════════════════════════════════════
BLACKLIST = CONFIG["blacklist"]
EXCLUDE_FAMILIES = CONFIG["exclude_families"]
M31_CAPS = CONFIG["m31_cap"]

# ═══════════════════════════════════════════════════════════════════════
# STAGE MANIFEST — what each stage consumes/produces
# ═══════════════════════════════════════════════════════════════════════
STAGES_MANIFEST = {
    "composer": {
        "module": "research_lab.composer",
        "inputs":  ["profiles/state.json"],
        "outputs": ["composer_report.md"],
        "respects_blacklist": True,
    },
    "thesis_detection": {
        "module": "research_lab.thesis_detection",
        "inputs":  ["profiles/state.json"],
        "outputs": ["thesis_evidence.json"],
        "respects_blacklist": True,
    },
    "thesis_dedup": {
        "module": "research_lab.thesis_dedup",
        "inputs":  ["thesis_evidence.json"],
        "outputs": ["thesis_deduped.json"],
        "respects_blacklist": True,
    },
    "multi_layer_portfolio": {
        "module": "research_lab.multi_layer_portfolio",
        "inputs":  ["thesis_deduped.json"],
        "outputs": ["multi_layer_portfolio.json"],
        "respects_blacklist": True,
    },
    "improve_strategy": {
        "module": "research_lab.improve_strategy",
        "inputs":  ["profiles/state.json"],
        "outputs": ["improvements.json"],
        "respects_blacklist": True,
    },
}


def validate():
    """Internal consistency check. Called by health_check.py."""
    issues = []
    if not BLACKLIST:
        issues.append("BLACKLIST is empty — expected 5 M31 variants")
    for strat in BLACKLIST:
        if not strat.startswith("M31_"):
            issues.append(f"Non-M31 strategy in blacklist: {strat}")
    for exch, cap in M31_CAPS.items():
        if not (0 < cap <= 1):
            issues.append(f"M31 cap out of range for {exch}: {cap}")
    for stage, meta in STAGES_MANIFEST.items():
        if "respects_blacklist" not in meta:
            issues.append(f"Stage {stage} missing respects_blacklist")
    return issues


if __name__ == "__main__":
    print(f"Pipeline Contract {CONTRACT_VERSION}")
    print(f"  Blacklist ({len(BLACKLIST)}): {BLACKLIST}")
    print(f"  M31 caps:  {M31_CAPS}")
    print(f"  Stages ({len(STAGES_MANIFEST)}): {list(STAGES_MANIFEST.keys())}")
    issues = validate()
    if issues:
        print("\n⚠️ Issues:")
        for i in issues:
            print(f"  - {i}")
    else:
        print("\n✅ Contract internally consistent")


# ═══════════════════════════════════════════════════════════════════════
# DSR E_max Reference (D-538)
# ═══════════════════════════════════════════════════════════════════════
# deflated_sharpe_family(sr, n, family) computes:
#   E[max_SR] = expected maximum Sharpe under null across N trials
#   DSR_z = sr_annual / se - E_max
# As N grows, E_max grows (multiple testing penalty).
# DSR >= 0.50 at N=8766 = survived very strong selection bias.
# This does NOT prove live profitability — only "better than chance".
# See research_lab/audit_core.py:deflated_sharpe_family
# Any change to N_trials must be logged in DECISIONS.md.
