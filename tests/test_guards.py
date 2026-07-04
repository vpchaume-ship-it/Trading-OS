import pytest

from trading_os.forward import guards


def test_demo_url_enforced():
    guards.assert_demo_url("https://demo.tradovateapi.com/v1/auth")
    with pytest.raises(guards.SafetyViolation):
        guards.assert_demo_url("https://live.tradovateapi.com/v1")
    with pytest.raises(guards.SafetyViolation):
        guards.assert_demo_url("https://api.tradovate.com/v1")


def test_order_size_and_symbol():
    guards.assert_order_allowed("MESU5", 1)
    guards.assert_order_allowed("MNQZ5", 1)
    with pytest.raises(guards.SafetyViolation):
        guards.assert_order_allowed("MESU5", 2)      # > 1 contrat
    with pytest.raises(guards.SafetyViolation):
        guards.assert_order_allowed("ESU5", 1)       # mini interdit, micros only
    with pytest.raises(guards.SafetyViolation):
        guards.assert_order_allowed("NQZ5", 1)


def test_daily_loss_limit_capped_by_hard_limit():
    # config plus permissive que le garde-fou dur -> le dur gagne
    assert guards.effective_daily_loss_limit(10_000) == guards.HARD_DAILY_LOSS_LIMIT_USD
    assert guards.effective_daily_loss_limit(100) == 100
    with pytest.raises(guards.SafetyViolation):
        guards.assert_daily_loss_ok(-150, 150)
    guards.assert_daily_loss_ok(-149, 150)
