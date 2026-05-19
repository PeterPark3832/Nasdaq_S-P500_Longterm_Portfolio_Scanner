import json
import os
from pathlib import Path
from datetime import datetime

import streamlit as st

# ── 파일 경로 ──────────────────────────────────────────────────────
BASE_DIR             = Path(os.getenv("SCANNER_DIR", Path(__file__).parent))
PORTFOLIO_FILE       = BASE_DIR / "portfolio_state_us.json"
PORTFOLIO_PREV_FILE  = BASE_DIR / "portfolio_prev_us.json"
PERFORMANCE_FILE     = BASE_DIR / "performance_history.json"
LAST_REBAL_FILE      = BASE_DIR / "last_rebal_us.json"

# ── 전략 임계치 (봇의 STRATEGY dict 미러) ─────────────────────────
STOPLOSS_THRESHOLD  = -20.0
STOPLOSS_WARN_LEVEL = -10.0
DRIFT_THRESHOLD     = 10.0
MDD_THRESHOLD       = -15.0
VIX_CAUTION         = 30
VIX_FEAR            = 40

# ── 색상 팔레트 ───────────────────────────────────────────────────
COLORS = {
    "new":       "#00C853",
    "exited":    "#EF5350",
    "increased": "#42A5F5",
    "decreased": "#FFA726",
    "unchanged": "#78909C",
    "cash":      "#FFD600",
    "spy":       "#9E9E9E",
    "qqq":       "#CE93D8",
    "portfolio": "#00E5FF",
    "background":"#0E1117",
    "card_bg":   "#1C2333",
}

PLOTLY_TEMPLATE = "plotly_dark"


# ── 데이터 로딩 ───────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_portfolio() -> dict | None:
    if not PORTFOLIO_FILE.exists():
        return None
    try:
        return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_prev_portfolio() -> dict | None:
    if not PORTFOLIO_PREV_FILE.exists():
        return None
    try:
        return json.loads(PORTFOLIO_PREV_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_performance_history() -> list[dict]:
    if not PERFORMANCE_FILE.exists():
        return []
    try:
        data = json.loads(PERFORMANCE_FILE.read_text(encoding="utf-8"))
        return sorted(data.get("records", []), key=lambda r: r.get("date", ""))
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_last_rebal() -> str | None:
    if not LAST_REBAL_FILE.exists():
        return None
    try:
        return json.loads(LAST_REBAL_FILE.read_text(encoding="utf-8")).get("month")
    except Exception:
        return None


# ── 리밸런싱 변동 계산 ────────────────────────────────────────────

def compute_rebalancing_changes(curr: dict, prev: dict | None) -> dict:
    """현재/이전 포트폴리오 간 변동 내역을 계산합니다."""
    curr_map = {h["ticker"]: h for h in curr.get("holdings", [])}
    prev_map = {h["ticker"]: h for h in (prev or {}).get("holdings", [])} if prev else {}

    result: dict[str, list] = {
        "new": [], "exited": [], "increased": [], "decreased": [],
        "unchanged": [], "trade_order": [],
    }

    all_tickers = set(curr_map) | set(prev_map)

    for ticker in all_tickers:
        if ticker == "CASH":
            continue
        c = curr_map.get(ticker)
        p = prev_map.get(ticker)

        if c and not p:
            result["new"].append(c)
            result["trade_order"].append(("buy", ticker, 0.0, c["weight"], c["weight"], c))
        elif p and not c:
            result["exited"].append(p)
            result["trade_order"].append(("sell", ticker, p["weight"], 0.0, -p["weight"], p))
        else:
            diff = round(c["weight"] - p["weight"], 2)
            enriched = {**c, "prev_weight": p["weight"]}
            if diff > 0.5:
                result["increased"].append(enriched)
                result["trade_order"].append(("increase", ticker, p["weight"], c["weight"], diff, enriched))
            elif diff < -0.5:
                result["decreased"].append(enriched)
                result["trade_order"].append(("decrease", ticker, p["weight"], c["weight"], diff, enriched))
            else:
                result["unchanged"].append(enriched)

    _ORDER = {"sell": 0, "decrease": 1, "increase": 2, "buy": 3}
    result["trade_order"].sort(key=lambda x: _ORDER[x[0]])

    return result


# ── 스코어 서브컴포넌트 재계산 ────────────────────────────────────
# 봇의 scoring 함수를 그대로 복사 (portfolio_state_us.json에는 raw 메트릭만 저장됨)

def _score_roe(v: float) -> float:
    if v >= 40: return 10.0
    if v >= 25: return 8.0
    if v >= 15: return 5.0
    if v >= 5:  return 2.0
    return 0.0

def _score_margin(v: float) -> float:
    if v >= 25: return 10.0
    if v >= 15: return 8.0
    if v >= 7:  return 5.0
    if v >= 4:  return 3.0
    if v >= 1:  return 1.0
    return 0.0

def _score_peg(v: float) -> float:
    if v <= 0:   return 0.0
    if v < 1.0:  return 8.0
    if v < 2.0:  return 5.0
    if v < 3.0:  return 2.0
    return 0.0

def _score_rev_growth(v: float) -> float:
    if v >= 0.30: return 7.0
    if v >= 0.15: return 5.0
    if v >= 0.05: return 3.0
    if v >= 0.0:  return 1.0
    return 0.0

def _score_fcf_margin(v: float) -> float:
    if v >= 0.20: return 5.0
    if v >= 0.10: return 3.0
    if v >= 0.05: return 1.5
    if v >= 0.0:  return 0.5
    return 0.0

def _score_52w(v: float) -> float:
    if v > 85: return 20.0
    if v > 70: return 15.0
    if v > 55: return 10.0
    if v > 40: return 5.0
    return 0.0


def compute_score_breakdown(holding: dict) -> dict:
    """보유 종목의 스코어 서브컴포넌트를 재계산합니다."""
    roe_pts    = _score_roe(holding.get("roe", 0))
    margin_pts = _score_margin(holding.get("margin", 0))
    peg_pts    = _score_peg(holding.get("peg", 0))
    rev_pts    = _score_rev_growth(holding.get("rev_growth", 0) / 100)
    fcf_pts    = _score_fcf_margin(holding.get("fcf_margin", 0) / 100)
    t_pts      = _score_52w(holding.get("w52_pos", 0))
    f_pts      = roe_pts + margin_pts + peg_pts + rev_pts + fcf_pts
    total      = holding.get("score", 0)
    mom_pts    = max(0.0, total - f_pts - t_pts)

    return {
        "roe":    roe_pts,
        "margin": margin_pts,
        "peg":    peg_pts,
        "rev":    rev_pts,
        "fcf":    fcf_pts,
        "financial": f_pts,
        "technical": t_pts,
        "momentum":  round(mom_pts, 1),
        "total":     total,
    }


# ── VIX 레짐 추론 (현금 비중 → VIX 레짐) ─────────────────────────

def infer_vix_regime(cash_weight: float) -> tuple[str, str, str]:
    """(label, emoji, color) 반환"""
    if cash_weight >= 60.0:
        return "공포 (Fear)", "🔴", "red"
    if cash_weight >= 50.0:
        return "주의 (Caution)", "🟡", "orange"
    return "정상 (Normal)", "🟢", "green"


# ── 최신 성과 레코드 ──────────────────────────────────────────────

def get_latest_perf(history: list[dict]) -> dict | None:
    checks = [r for r in history if r.get("type") == "performance_check"
              and r.get("portfolio_ret_pct") is not None]
    return checks[-1] if checks else None


def get_latest_rebal_perf(history: list[dict]) -> dict | None:
    rebals = [r for r in history if r.get("type") == "rebalancing"]
    return rebals[-1] if rebals else None


# ── 섹터별 종목 수 집계 ────────────────────────────────────────────

def sector_counts(holdings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for h in holdings:
        if h["ticker"] == "CASH":
            continue
        sec = h.get("sector", "Unknown")
        counts[sec] = counts.get(sec, 0) + 1
    return counts
