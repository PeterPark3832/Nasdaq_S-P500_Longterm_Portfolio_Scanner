"""
Unit tests — scanner.portfolio (pure functions, no file I/O)
"""
import pytest

from scanner.portfolio import build_trade_checklist, is_fresh_start
from scanner.scoring import calc_stock_weights


# ── helpers ─────────────────────────────────────────────────────────

def _holding(ticker, name, weight, entry_price=100.0):
    return {
        "ticker": ticker, "name": name, "weight": weight,
        "entry_price": entry_price, "entry_date": "2025-01-01",
        "score": 80.0, "sector": "Technology",
        "roe": 30.0, "margin": 20.0, "peg": 1.5,
        "rev_growth": 15.0, "fcf_margin": 10.0, "de_ratio": 50.0,
        "ret_6m": 10.0, "w52_pos": 75.0,
        "data_stale": False, "fin_report_dt": "2025-03-31",
    }


CASH = {
    "ticker": "CASH", "name": "안전 자산", "weight": 30.0,
    "entry_price": 1.0, "entry_date": "2025-01-01",
    "score": 0.0, "sector": "Cash",
    "roe": 0.0, "margin": 0.0, "peg": 0.0,
    "rev_growth": 0.0, "fcf_margin": 0.0, "de_ratio": 0.0,
    "ret_6m": 0.0, "w52_pos": 0.0,
    "data_stale": False, "fin_report_dt": "",
}


# ── build_trade_checklist ────────────────────────────────────────────

def test_checklist_first_build():
    """prev=None → all new buys."""
    new_holdings = [CASH, _holding("AAPL", "Apple", 40.0), _holding("NVDA", "NVIDIA", 30.0)]
    result = build_trade_checklist(None, new_holdings)
    assert "신규 매수" in result
    assert "AAPL" in result
    assert "NVDA" in result
    assert "전종목 신규 매수" in result


def test_checklist_exit_on_removal():
    prev = {"holdings": [CASH, _holding("AAPL", "Apple", 40.0), _holding("META", "Meta", 30.0)]}
    new_holdings = [CASH, _holding("AAPL", "Apple", 45.0), _holding("NVDA", "NVIDIA", 25.0)]
    result = build_trade_checklist(prev, new_holdings)
    assert "전량 매도" in result
    assert "META" in result


def test_checklist_increase_and_decrease():
    prev = {"holdings": [CASH, _holding("AAPL", "Apple", 40.0), _holding("MSFT", "Microsoft", 30.0)]}
    new_holdings = [CASH, _holding("AAPL", "Apple", 45.0), _holding("MSFT", "Microsoft", 25.0)]
    result = build_trade_checklist(prev, new_holdings)
    assert "비중 확대" in result
    assert "AAPL" in result
    assert "비중 축소" in result
    assert "MSFT" in result


def test_checklist_no_change():
    prev = {"holdings": [CASH, _holding("AAPL", "Apple", 40.0)]}
    new_holdings = [CASH, _holding("AAPL", "Apple", 40.0)]
    result = build_trade_checklist(prev, new_holdings)
    assert "유지" in result


def test_checklist_new_entry():
    prev = {"holdings": [CASH, _holding("AAPL", "Apple", 70.0)]}
    new_holdings = [CASH, _holding("AAPL", "Apple", 50.0), _holding("NVDA", "NVIDIA", 20.0)]
    result = build_trade_checklist(prev, new_holdings)
    assert "신규 매수" in result
    assert "NVDA" in result


def test_checklist_cash_excluded_from_stock_sections():
    """CASH should not appear in buy/sell/increase/decrease sections."""
    prev = {"holdings": [CASH, _holding("AAPL", "Apple", 70.0)]}
    new_holdings = [
        {**CASH, "weight": 40.0},   # cash weight changed
        _holding("AAPL", "Apple", 60.0),
    ]
    result = build_trade_checklist(prev, new_holdings)
    # CASH weight change should not produce a "전량 매도" line
    lines_with_cash = [l for l in result.split("\n") if "CASH" in l and "전량 매도" in l]
    assert len(lines_with_cash) == 0


# ── calc_stock_weights (re-verify with real scenarios) ───────────────

def test_weights_round_trip_70():
    scores  = [85.0, 78.0, 72.0, 68.0, 65.0]
    weights = calc_stock_weights(scores, 70.0)
    assert len(weights) == len(scores)
    assert abs(sum(weights) - 70.0) < 0.05


def test_single_stock_gets_full_weight():
    weights = calc_stock_weights([90.0], 70.0)
    assert weights == [70.0]


def test_weights_ordering():
    """Higher score → higher weight."""
    scores  = [90.0, 60.0]
    weights = calc_stock_weights(scores, 70.0)
    assert weights[0] > weights[1]


# ── is_fresh_start ───────────────────────────────────────────────────

def test_fresh_start_none():
    assert is_fresh_start(None) is True

def test_fresh_start_empty_holdings():
    assert is_fresh_start({"holdings": []}) is True

def test_fresh_start_cash_only():
    """CASH만 있으면 신규/재진입으로 취급."""
    assert is_fresh_start({"holdings": [CASH]}) is True

def test_fresh_start_has_stocks():
    port = {"holdings": [CASH, _holding("AAPL", "Apple", 40.0)]}
    assert is_fresh_start(port) is False


# ── build_trade_checklist — re-entry ────────────────────────────────

def test_checklist_reentry_after_full_exit():
    """주식 보유 없는 이전 포트폴리오 → 재진입 가이드 출력."""
    prev = {"holdings": [CASH]}   # 주식 없음 = 전량 청산 상태
    new_holdings = [CASH, _holding("AAPL", "Apple", 40.0), _holding("NVDA", "NVIDIA", 30.0)]
    result = build_trade_checklist(prev, new_holdings)
    assert "재진입" in result
    assert "AAPL" in result
    assert "NVDA" in result
    assert "에피소드" in result

def test_checklist_reentry_sorted_by_weight():
    """재진입 체크리스트는 비중 내림차순 정렬."""
    prev = {"holdings": [CASH]}
    new_holdings = [
        CASH,
        _holding("AAPL", "Apple", 20.0),
        _holding("NVDA", "NVIDIA", 40.0),
        _holding("MSFT", "Microsoft", 30.0),
    ]
    result = build_trade_checklist(prev, new_holdings)
    nvda_pos = result.index("NVDA")
    msft_pos = result.index("MSFT")
    aapl_pos = result.index("AAPL")
    assert nvda_pos < msft_pos < aapl_pos   # 40% > 30% > 20%

def test_checklist_fresh_first_time_vs_reentry_different_header():
    """첫 구성과 재진입은 헤더가 달라야 함."""
    new_holdings = [CASH, _holding("AAPL", "Apple", 70.0)]
    first  = build_trade_checklist(None, new_holdings)
    reentry = build_trade_checklist({"holdings": [CASH]}, new_holdings)
    assert "첫 구성" in first
    assert "재진입" in reentry
