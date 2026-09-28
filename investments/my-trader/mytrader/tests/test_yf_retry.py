from __future__ import annotations

import pytest
from yfinance.exceptions import YFRateLimitError

from mytrader import yf_retry


def test_call_returns_result_on_first_success(monkeypatch):
    monkeypatch.setattr(yf_retry.time, "sleep", lambda s: None)
    assert yf_retry.call(lambda: 42) == 42


def test_call_retries_and_succeeds_after_rate_limit(monkeypatch):
    sleeps = []
    monkeypatch.setattr(yf_retry.time, "sleep", lambda s: sleeps.append(s))

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise YFRateLimitError()
        return "ok"

    result = yf_retry.call(flaky)

    assert result == "ok"
    assert calls["n"] == 3
    assert sleeps == [5, 15]  # two retries needed, backoff delays in order


def test_call_reraises_after_exhausting_all_retries(monkeypatch):
    monkeypatch.setattr(yf_retry.time, "sleep", lambda s: None)

    def always_rate_limited():
        raise YFRateLimitError()

    with pytest.raises(YFRateLimitError):
        yf_retry.call(always_rate_limited)


def test_call_does_not_retry_other_exceptions(monkeypatch):
    monkeypatch.setattr(yf_retry.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("not a rate limit")

    with pytest.raises(ValueError):
        yf_retry.call(boom)

    assert calls["n"] == 1  # no retry attempted for a non-rate-limit error
