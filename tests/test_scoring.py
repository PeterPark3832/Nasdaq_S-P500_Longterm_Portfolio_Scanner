"""
Unit tests — scanner.scoring (pure functions, no network)
"""
import pandas as pd
import pytest

from scanner.scoring import (
    score_roe, score_margin, score_peg, score_rev_growth,
    score_fcf_margin, score_52w, financial_score,
    calc_stock_weights, apply_sector_cap, analyze_ticker,
)


# ── score_roe ───────────────────────────────────────────────────────
def test_score_roe_thresholds():
    assert score_roe(50)  == 10.0
    assert score_roe(40)  == 10.0
    assert score_roe(39)  == 8.0
    assert score_roe(25)  == 8.0
    assert score_roe(24)  == 5.0
    assert score_roe(15)  == 5.0
    assert score_roe(14)  == 2.0
    assert score_roe(5)   == 2.0
    assert score_roe(4)   == 0.0
    assert score_roe(-10) == 0.0


# ── score_margin ────────────────────────────────────────────────────
def test_score_margin_thresholds():
    assert score_margin(30)  == 10.0
    assert score_margin(25)  == 10.0
    assert score_margin(24)  == 7.0
    assert score_margin(15)  == 7.0
    assert score_margin(14)  == 4.0
    assert score_margin(8)   == 4.0
    assert score_margin(7)   == 1.0
    assert score_margin(0)   == 1.0
    assert score_margin(-1)  == 0.0


# ── score_peg ───────────────────────────────────────────────────────
def test_score_peg_thresholds():
    assert score_peg(0)    == 0.0   # 적자/데이터 없음
    assert score_peg(-1)   == 0.0
    assert score_peg(0.5)  == 8.0
    assert score_peg(0.99) == 8.0
    assert score_peg(1.0)  == 5.0
    assert score_peg(1.99) == 5.0
    assert score_peg(2.0)  == 2.0
    assert score_peg(2.99) == 2.0
    assert score_peg(3.0)  == 0.0


# ── score_rev_growth ────────────────────────────────────────────────
def test_score_rev_growth():
    assert score_rev_growth(0.30) == 7.0
    assert score_rev_growth(0.50) == 7.0
    assert score_rev_growth(0.15) == 5.0
    assert score_rev_growth(0.29) == 5.0
    assert score_rev_growth(0.05) == 3.0
    assert score_rev_growth(0.14) == 3.0
    assert score_rev_growth(0.0)  == 1.0
    assert score_rev_growth(0.04) == 1.0
    assert score_rev_growth(-0.1) == 0.0


# ── score_fcf_margin ────────────────────────────────────────────────
def test_score_fcf_margin():
    assert score_fcf_margin(0.20) == 5.0
    assert score_fcf_margin(0.50) == 5.0
    assert score_fcf_margin(0.10) == 3.0
    assert score_fcf_margin(0.19) == 3.0
    assert score_fcf_margin(0.05) == 1.5
    assert score_fcf_margin(0.09) == 1.5
    assert score_fcf_margin(0.0)  == 0.5
    assert score_fcf_margin(0.04) == 0.5
    assert score_fcf_margin(-0.1) == 0.0


# ── score_52w ───────────────────────────────────────────────────────
def test_score_52w():
    assert score_52w(0.90) == 20.0
    assert score_52w(0.85) == 20.0
    assert score_52w(0.70) == 15.0
    assert score_52w(0.84) == 15.0
    assert score_52w(0.55) == 10.0
    assert score_52w(0.69) == 10.0
    assert score_52w(0.40) == 5.0
    assert score_52w(0.54) == 5.0
    assert score_52w(0.39) == 1.0
    assert score_52w(0.0)  == 1.0


# ── financial_score ─────────────────────────────────────────────────
def test_financial_score_max():
    max_score = financial_score(roe=50, margin=30, peg=0.5,
                                rev_growth=0.30, fcf_margin=0.20)
    assert max_score == 10 + 10 + 8 + 7 + 5  # = 40


def test_financial_score_zero():
    assert financial_score(0, -1, 0, -0.1, -0.1) == 0.0


# ── calc_stock_weights ──────────────────────────────────────────────
def test_weights_proportional():
    weights = calc_stock_weights([60.0, 40.0], 70.0)
    assert len(weights) == 2
    assert abs(sum(weights) - 70.0) < 0.01
    assert weights[0] > weights[1]


def test_weights_equal_when_all_zero():
    weights = calc_stock_weights([0.0, 0.0, 0.0], 90.0)
    assert len(weights) == 3
    assert all(w == pytest.approx(30.0) for w in weights)


def test_weights_sum_exact():
    weights = calc_stock_weights([10.0, 20.0, 30.0], 70.0)
    assert sum(weights) == pytest.approx(70.0, abs=0.01)


# ── apply_sector_cap ────────────────────────────────────────────────
def _make_df(rows):
    return pd.DataFrame(rows, columns=["ticker", "sector", "total_score"])


def test_sector_cap_basic():
    df = _make_df([
        ("A", "Tech", 90), ("B", "Tech", 85), ("C", "Tech", 80),
        ("D", "Finance", 75), ("E", "Finance", 70),
    ])
    result = apply_sector_cap(df, n=4, max_per_sector=2)
    assert len(result) == 4
    tech_count = (result["sector"] == "Tech").sum()
    assert tech_count <= 2


def test_sector_cap_unknown_exempt():
    df = _make_df([
        ("A", "Unknown", 100), ("B", "Unknown", 99), ("C", "Unknown", 98),
        ("D", "Unknown", 97),
    ])
    result = apply_sector_cap(df, n=3, max_per_sector=2)
    assert len(result) == 3


# ── analyze_ticker ──────────────────────────────────────────────────
def _make_price_df(n_days=300):
    import numpy as np
    from datetime import date, timedelta
    dates  = pd.date_range(end=date.today(), periods=n_days, freq="B")
    prices = 100 * (1 + pd.Series(np.random.randn(n_days) * 0.01)).cumprod()
    prices = prices * 1.5  # ensure above MA200
    df = pd.DataFrame({
        "Close": prices.values,
        "High":  (prices * 1.02).values,
        "Low":   (prices * 0.98).values,
    }, index=dates)
    return df


def test_analyze_ticker_returns_dict_with_valid_data():
    info = {
        "shortName": "Test Corp",
        "sector": "Technology",
        "returnOnEquity": 0.30,
        "profitMargins": 0.20,
        "pegRatio": 1.5,
        "revenueGrowth": 0.15,
        "totalRevenue": 1e9,
        "freeCashflow": 1.5e8,
        "debtToEquity": 50.0,
        "trailingPE": 25.0,
        "priceToBook": 5.0,
        "mostRecentQuarter": 0,
    }
    df = _make_price_df(300)
    result = analyze_ticker("TEST", df, spy_6m_ret=0.05, info=info)
    assert result is not None
    assert result["ticker"] == "TEST"
    assert "base_score" in result
    assert result["base_score"] >= 0


def test_analyze_ticker_too_short_returns_none():
    df = _make_price_df(30)
    result = analyze_ticker("TEST", df, spy_6m_ret=0.0, info={})
    assert result is None


def test_analyze_ticker_high_de_ratio_filtered():
    info = {
        "sector": "Technology",
        "returnOnEquity": 0.40,
        "profitMargins": 0.30,
        "pegRatio": 1.0,
        "revenueGrowth": 0.20,
        "totalRevenue": 1e9,
        "freeCashflow": 2e8,
        "debtToEquity": 300.0,  # > STRATEGY["de_ratio_max"] = 200
        "mostRecentQuarter": 0,
    }
    df = _make_price_df(300)
    result = analyze_ticker("TEST", df, spy_6m_ret=0.0, info=info)
    assert result is None
