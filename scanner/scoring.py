"""
전략 D 스코어링 — 순수 함수만 포함 (부작용 없음, 테스트 가능)
"""
import logging
from datetime import datetime

import pandas as pd

from scanner.config import STRATEGY, KST

log = logging.getLogger("scanner")

# 금융·부동산 섹터 — D/E 필터 면제
_FINANCIAL_SECTORS = {"Financial Services", "Financials", "Real Estate", "Banks"}


# ── 재무 점수 함수 (40점 만점) ──────────────────────────────────────

def score_roe(roe: float) -> float:
    """ROE 점수 (0~10점)"""
    if roe >= 40: return 10.0
    if roe >= 25: return 8.0
    if roe >= 15: return 5.0
    if roe >= 5:  return 2.0
    return 0.0


def score_margin(margin: float) -> float:
    """순이익률 점수 (0~10점)"""
    if margin >= 25: return 10.0
    if margin >= 15: return 7.0
    if margin >= 8:  return 4.0
    if margin >= 0:  return 1.0
    return 0.0


def score_peg(peg: float) -> float:
    """PEG 점수 (0~8점). 낮을수록 유리"""
    if peg <= 0:  return 0.0
    if peg < 1.0: return 8.0
    if peg < 2.0: return 5.0
    if peg < 3.0: return 2.0
    return 0.0


def score_rev_growth(growth: float) -> float:
    """매출성장률 점수 (0~7점). 소수 형태 입력 (0.15 = 15%)"""
    if growth >= 0.30: return 7.0
    if growth >= 0.15: return 5.0
    if growth >= 0.05: return 3.0
    if growth >= 0.0:  return 1.0
    return 0.0


def score_fcf_margin(fcf_margin: float) -> float:
    """FCF 마진 점수 (0~5점). 소수 형태 입력"""
    if fcf_margin >= 0.20: return 5.0
    if fcf_margin >= 0.10: return 3.0
    if fcf_margin >= 0.05: return 1.5
    if fcf_margin >= 0.0:  return 0.5
    return 0.0


def score_52w(pos: float) -> float:
    """52주 위치 점수 (0~20점). 소수 형태 입력 (0.85 = 85%)"""
    if pos >= 0.85: return 20.0
    if pos >= 0.70: return 15.0
    if pos >= 0.55: return 10.0
    if pos >= 0.40: return 5.0
    return 1.0


def financial_score(roe: float, margin: float, peg: float,
                    rev_growth: float, fcf_margin: float) -> float:
    """재무 점수 합계 (최대 40점)"""
    return (score_roe(roe) + score_margin(margin) + score_peg(peg)
            + score_rev_growth(rev_growth) + score_fcf_margin(fcf_margin))


# ── 비중 계산 ──────────────────────────────────────────────────────

def calc_stock_weights(scores: list[float], target_sum: float) -> list[float]:
    """점수 비례로 비중 배분. 오차는 마지막 항목에 흡수."""
    total = sum(scores)
    if total <= 0:
        n = len(scores)
        return [round(target_sum / n, 1)] * n
    raw     = [s / total * target_sum for s in scores]
    rounded = [round(w, 1) for w in raw]
    diff    = round(target_sum - sum(rounded), 1)
    if rounded:
        rounded[-1] = round(rounded[-1] + diff, 1)
    return rounded


# ── 섹터 다양성 제한 ────────────────────────────────────────────────

def apply_sector_cap(df: "pd.DataFrame", n: int, max_per_sector: int) -> "pd.DataFrame":
    """점수 순 greedy 선택, 동일 섹터 max_per_sector 초과 방지.
    Unknown 섹터는 제한 면제 (데이터 누락 종목 불이익 방어).
    """
    sorted_df     = df.sort_values("total_score", ascending=False)
    sector_count: dict[str, int] = {}
    selected_rows = []
    for _, row in sorted_df.iterrows():
        sector = str(row.get("sector", "Unknown"))
        cnt    = sector_count.get(sector, 0)
        if sector == "Unknown" or cnt < max_per_sector:
            selected_rows.append(row)
            sector_count[sector] = cnt + 1
        if len(selected_rows) >= n:
            break
    return pd.DataFrame(selected_rows).reset_index(drop=True)


# ── 단일 종목 분석 ──────────────────────────────────────────────────

def analyze_ticker(
    ticker: str,
    price_df: "pd.DataFrame",
    spy_6m_ret: float,
    info: dict | None = None,
    get_info_fn=None,
) -> dict | None:
    """
    전략 D: 재무(40) + 기술(20) + 모멘텀 raw.
    퍼센타일 점수는 _do_monthly_scan에서 후처리.

    Args:
        price_df: 벌크 다운로드로 수신한 개별 종목 가격 DataFrame
        spy_6m_ret: SPY 6개월 수익률 (모멘텀 상대강도 계산용)
        info: 외부에서 주입된 재무 dict. None이면 get_info_fn 호출.
        get_info_fn: info=None 시 사용할 fallback 조회 함수
    """
    try:
        if price_df is None or price_df.empty or len(price_df) < 60:
            return None

        last_date = price_df.index[-1]
        if (datetime.now(KST).date() - last_date.date()).days > STRATEGY["max_stale_days"]:
            return None

        close = float(price_df["Close"].iloc[-1])
        if close <= 0:
            return None

        price_df = price_df.copy()
        price_df["Close"] = price_df["Close"].ffill()
        price_df["MA200"] = price_df["Close"].rolling(200, min_periods=200).mean()

        last  = price_df.iloc[-1]
        ma200 = last["MA200"]
        if pd.isna(ma200) or close < float(ma200):
            return None

        w52      = price_df.iloc[-252:] if len(price_df) >= 252 else price_df
        high_52w = float(w52["High"].max())
        low_52w  = float(w52["Low"].min())
        w52_pos  = (close - low_52w) / (high_52w - low_52w) if high_52w > low_52w else 0.5

        ref_6m  = float(price_df["Close"].iloc[-126]) if len(price_df) >= 126 else float(price_df["Close"].iloc[0])
        ref_12m = float(price_df["Close"].iloc[-252]) if len(price_df) >= 252 else float(price_df["Close"].iloc[0])
        ret_6m  = close / ref_6m  - 1
        ret_12m = close / ref_12m - 1
        rel_str = ret_6m - spy_6m_ret

        if info is None and get_info_fn is not None:
            info = get_info_fn(ticker)
        if info is None:
            info = {}

        company_name = str(info.get("shortName", "") or ticker)
        sector       = str(info.get("sector", "") or "Unknown")
        roe          = float(info.get("returnOnEquity",  0) or 0) * 100
        margin       = float(info.get("profitMargins",   0) or 0) * 100
        peg          = float(info.get("pegRatio",         0) or 0)
        pe           = float(info.get("trailingPE",       0) or 0)
        pb           = float(info.get("priceToBook",      0) or 0)
        rev_growth   = float(info.get("revenueGrowth",   0) or 0)
        total_rev    = float(info.get("totalRevenue",     0) or 0)
        free_cf      = float(info.get("freeCashflow",     0) or 0)
        fcf_margin   = (free_cf / total_rev) if total_rev > 0 else 0.0
        de_ratio     = float(info.get("debtToEquity",    0) or 0)

        if sector not in _FINANCIAL_SECTORS and de_ratio > STRATEGY["de_ratio_max"]:
            return None

        data_stale    = False
        fin_report_dt = None
        mrq_ts = info.get("mostRecentQuarter", 0) or 0
        if mrq_ts > 0:
            try:
                fin_report_dt = datetime.fromtimestamp(float(mrq_ts))
                age_days      = (datetime.now() - fin_report_dt).days
                if age_days > STRATEGY["fin_stale_skip_days"]:
                    return None
                data_stale = age_days > STRATEGY["fin_stale_warn_days"]
            except Exception:
                pass

        f_score    = financial_score(roe, margin, peg, rev_growth, fcf_margin)
        t_score    = score_52w(w52_pos)
        base_score = f_score + t_score

        return {
            "ticker":         ticker,
            "name":           company_name,
            "sector":         sector,
            "close":          round(close, 2),
            "pe":             round(pe, 1),
            "pb":             round(pb, 2),
            "roe":            round(roe, 1),
            "margin":         round(margin, 1),
            "peg":            round(peg, 2),
            "rev_growth":     round(rev_growth * 100, 1),
            "fcf_margin":     round(fcf_margin * 100, 1),
            "de_ratio":       round(de_ratio, 1),
            "w52_pos":        round(w52_pos * 100, 1),
            "ret_6m":         round(ret_6m * 100, 2),
            "ret_12m":        round(ret_12m * 100, 2),
            "rel_str":        round(rel_str * 100, 2),
            "f_score":        round(f_score, 1),
            "t_score":        round(t_score, 1),
            "base_score":     round(base_score, 1),
            "data_stale":     data_stale,
            "fin_report_dt":  fin_report_dt.strftime("%Y-%m-%d") if fin_report_dt else "",
        }
    except Exception as e:
        log.debug(f"[SKIP] {ticker}: {e}")
        return None
