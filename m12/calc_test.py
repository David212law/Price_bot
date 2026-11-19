
def test_bot_math():
    from calc import cost_basis, pnl_long, pnl_short, position_qty, sl_tp, should_close, should_kill
    assert pnl_long(1, 100, 110, 0.02) == 7.9
    assert pnl_long(1, 100, 90, 0.02) == -11.9
    assert pnl_short(1, 100, 90, 0.02) == 8.1
    assert pnl_short(1, 100, 110, 0.02) == -12.1
    assert cost_basis(1.5, 100) == 150.0
    assert position_qty(1000, 0.15, 100) == 1.5
    assert position_qty(0, 0.15, 100) == 0.0
    assert sl_tp(100, "LONG") == (95.0, 110.0)
    assert sl_tp(100, "SHORT") == (105.0, 90.0)
    assert should_close("LONG", 94, 95, 110) == "SL"
    assert should_close("LONG", 111, 95, 110) == "TP"
    assert should_close("LONG", 100, 95, 110) is None
    assert should_close("SHORT", 106, 105, 90) == "SL"
    assert should_close("SHORT", 89, 105, 90) == "TP"
    assert should_close("SHORT", 100, 105, 90) is None
    assert should_kill(8400, 10000) is True
    assert should_kill(8600, 10000) is False
    print("✅ bot math: 17 cases")

"""M12 Calc Test — MUST pass before any research."""
from calc import regime_label, win_rate, mean, sharpe, bootstrap_ci, normalize

def test_all():
    assert regime_label(0.15) == "BULL"
    assert regime_label(0.0) == "FLAT"
    assert regime_label(-0.15) == "BEAR"
    assert regime_label(-0.30) == "CRASH"
    print("✅ regime_label: 4 cases")

    assert win_rate([1,1,0,1,0]) == 0.6
    assert win_rate([1,1,1]) == 1.0
    assert win_rate([]) == 0.0
    print("✅ win_rate: 3 cases")

    assert mean([1,2,3,4,5]) == 3.0
    assert mean([10]) == 10.0
    assert mean([]) == 0.0
    print("✅ mean: 3 cases")

    s = sharpe([0.01, 0.02, 0.03], periods_per_year=1)
    assert abs(s - 2.0) < 0.01, f"expected 2.0, got {s}"
    assert sharpe([0.01, 0.01, 0.01]) == 0.0
    print("✅ sharpe: 2 cases")

    lo, hi = bootstrap_ci([0.01] * 50)
    assert lo > 0, f"all positive, CI low >0 expected, got {lo}"
    lo, hi = bootstrap_ci([-0.01] * 50)
    assert hi < 0, f"all negative, CI high <0 expected, got {hi}"
    print("✅ bootstrap_ci: 2 cases")

    assert normalize({"a": 2, "b": 1}) == {"a": 0.6667, "b": 0.3333}
    assert normalize({}) == {}
    print("✅ normalize: 2 cases")
    test_bot_math()

    print()
    print("=" * 50)
    print("✅ ALL 16 TESTS PASSED — calc is trusted")
    print("=" * 50)

if __name__ == "__main__":
    test_all()
