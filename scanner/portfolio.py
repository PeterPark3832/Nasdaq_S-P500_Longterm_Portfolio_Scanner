"""
포트폴리오 상태 관리 — JSON 파일 I/O + 리밸런싱 브리핑 + 매매 체크리스트
"""
import json
import logging
from datetime import datetime, timedelta

from scanner.config import (
    PORTFOLIO_FILE, PORTFOLIO_PREV_FILE, LAST_REBAL_FILE,
    STRATEGY, KST,
)

log = logging.getLogger("scanner")

# 리밸런싱 월 캐시 (프로세스 재시작 시 파일에서 복원)
_last_rebal_cache: dict = {"month": None}


# ── CRUD ────────────────────────────────────────────────────────────

def load_portfolio() -> dict | None:
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"포트폴리오 파일 읽기 실패: {e}")
    return None


def save_portfolio(data: dict) -> None:
    PORTFOLIO_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"포트폴리오 저장 → {PORTFOLIO_FILE}")


def save_prev_portfolio(portfolio: dict | None) -> None:
    """리밸런싱 직전 포트폴리오 백업 (대시보드 Before/After 비교용)"""
    if portfolio and portfolio.get("holdings"):
        PORTFOLIO_PREV_FILE.write_text(
            json.dumps(portfolio, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load_last_rebal() -> str | None:
    if LAST_REBAL_FILE.exists():
        try:
            return json.loads(LAST_REBAL_FILE.read_text())["month"]
        except Exception:
            pass
    return None


def save_last_rebal(month_str: str) -> None:
    LAST_REBAL_FILE.write_text(json.dumps({"month": month_str}))
    _last_rebal_cache["month"] = month_str


def already_ran_this_month() -> bool:
    now_month = datetime.now(KST).strftime("%Y-%m")
    last_run  = _last_rebal_cache["month"] or load_last_rebal()
    return last_run == now_month


def is_fresh_start(portfolio: dict | None) -> bool:
    """이전 포트폴리오에 주식 보유가 없으면 신규/재진입 모드."""
    if not portfolio or not portfolio.get("holdings"):
        return True
    return not any(h["ticker"] != "CASH" for h in portfolio["holdings"])


# ── 리밸런싱 브리핑 ────────────────────────────────────────────────

def build_rebalancing_brief(
    prev: dict | None,
    new_holdings: list[dict],
    vix_level: float = 0.0,
    cash_weight: float | None = None,
    episode: int = 1,
) -> str:
    date_str   = datetime.now(KST).strftime("%Y년 %m월")
    fresh      = is_fresh_start(prev)

    if vix_level >= STRATEGY["vix_fear"]:
        regime_str = f"🔴 공포 (VIX {vix_level:.1f}) — 현금 {cash_weight:.0f}%로 확대"
    elif vix_level >= STRATEGY["vix_caution"]:
        regime_str = f"🟡 주의 (VIX {vix_level:.1f}) — 현금 {cash_weight:.0f}%로 확대"
    elif vix_level > 0:
        regime_str = f"🟢 정상 (VIX {vix_level:.1f})"
    else:
        regime_str = "⚪ VIX 조회 불가"

    # 신규/재진입이면 에피소드 정보 + 다른 제목
    if fresh and prev and prev.get("holdings"):
        mode_line = f"🔄 에피소드 {episode} 시작 — 재진입 (오늘 종가 기준 신규 매수)\n"
    elif fresh:
        mode_line = f"🆕 에피소드 {episode} 시작 — 첫 구성\n"
    else:
        mode_line = f"📅 에피소드 {episode} 진행 중\n"

    header = (
        f"📋 *{date_str} 미국주식 포트폴리오 리밸런싱*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📡 시장 레짐: {regime_str}\n"
        f"{mode_line}"
        f"🗂 *신규 포트폴리오 (총 {len(new_holdings)}항목)*\n"
    )

    stale_tickers: list[str] = []
    portfolio_body = ""
    for h in new_holdings:
        if h["ticker"] == "CASH":
            portfolio_body += f"  💵 *{h['name']}*  비중 {h['weight']}%\n\n"
        else:
            stale_flag = ""
            if h.get("data_stale"):
                stale_flag = " ⚠️_재무구식_"
                stale_tickers.append(h["ticker"])
            fin_dt_str = f" | 재무기준 {h['fin_report_dt']}" if h.get("fin_report_dt") else ""
            portfolio_body += (
                f"  *{h['name']}* ({h['ticker']}){stale_flag}\n"
                f"  섹터: {h.get('sector','?')} | 비중 {h['weight']}% | 점수 {h['score']}점{fin_dt_str}\n"
                f"  진입가 ${h['entry_price']:,.2f}\n"
                f"  ROE {h['roe']}% | 마진 {h['margin']}% | PEG {h['peg']}\n"
                f"  매출성장 {h.get('rev_growth',0):+.1f}% | FCF마진 {h.get('fcf_margin',0):.1f}% | D/E {h.get('de_ratio',0):.0f}%\n"
                f"  6개월 {h['ret_6m']:+.1f}% | 52주위치 {h['w52_pos']}%\n\n"
            )

    # 신규/재진입은 before/after 비교 의미 없음 → 생략
    change_body = "" if fresh else _build_change_section(prev, new_holdings)

    data_quality_body = ""
    if stale_tickers:
        data_quality_body = (
            f"⚠️ *재무 데이터 주의 ({len(stale_tickers)}종목)*\n"
            + "\n".join(f"  • {t}" for t in stale_tickers)
            + "\n\n"
        )

    footer = (
        f"⚠️ *편향 경고*\n"
        f"  • yfinance.info는 현재 재무값 → 재무점수 미래참조 편향\n"
        f"  • 현재 S&P500/나스닥100 기준 → 생존자 편향\n"
        f"  • 모멘텀(40점)은 가격 기반 → 상대적으로 신뢰도 높음\n"
        f"⚠️ 투자 판단은 본인 책임 — 참고 자료입니다"
    )

    checklist_body = (
        "\n━━━━━━━━━━━━━━━━━━\n"
        + build_trade_checklist(prev, new_holdings)
        + "\n"
    )

    return header + portfolio_body + change_body + data_quality_body + checklist_body + footer


def _build_change_section(prev: dict | None, new_holdings: list[dict]) -> str:
    if not prev or not prev.get("holdings"):
        return ""
    prev_map = {h["ticker"]: h for h in prev["holdings"]}
    new_map  = {h["ticker"]: h for h in new_holdings}
    exits    = set(prev_map) - set(new_map)
    entries  = set(new_map)  - set(prev_map)
    retained = set(prev_map) & set(new_map)

    body = "📊 *변경 내역*\n"
    for t in sorted(entries):
        h = new_map[t]
        if t != "CASH":
            body += f"  🟢 신규 편입: *{h['name']}* ({t}) {h['weight']}%\n"
    for t in sorted(exits):
        h = prev_map[t]
        if t != "CASH":
            body += f"  🔴 제외: *{h['name']}* ({t})\n"
    for t in sorted(retained):
        if t == "CASH":
            continue
        diff = round(new_map[t]["weight"] - prev_map[t]["weight"], 1)
        if abs(diff) > 0.5:
            arrow = "🔼" if diff > 0 else "🔽"
            body += f"  {arrow} 비중 조정: *{new_map[t]['name']}* ({t}) {prev_map[t]['weight']}% → {new_map[t]['weight']}% ({diff:+.1f}%p)\n"
    return body + "\n"


# ── 매매 체크리스트 ────────────────────────────────────────────────

def build_trade_checklist(prev: dict | None, new_holdings: list[dict]) -> str:
    """매도→축소→확대→신규 매수 순서로 체크리스트 생성.
    신규/재진입(is_fresh_start)이면 전종목 신규 매수 가이드로 대체.
    """
    new_stocks = [h for h in new_holdings if h["ticker"] != "CASH"]
    new_map    = {h["ticker"]: h for h in new_stocks}

    if is_fresh_start(prev):
        # 첫 구성 vs 재진입 구분
        if not prev or not prev.get("holdings"):
            header = "📋 *매매 실행 목록 (첫 구성 — 전종목 신규 매수)*"
            footer = "  ※ CASH 항목은 달러 예수금/MMF로 보유"
        else:
            header = "📋 *재진입 가이드 — 포트폴리오 재구성*"
            footer = (
                "  ※ 이전 포트폴리오 청산 후 재진입\n"
                "  ※ 오늘 종가 기준 신규 매수 — 수익률 추적 에피소드 새로 시작"
            )
        lines = [header]
        for h in sorted(new_stocks, key=lambda x: -x["weight"]):
            lines.append(f"  🟢 신규 매수: *{h['name']}* ({h['ticker']}) {h['weight']}%")
        lines.append("")
        lines.append(footer)
        return "\n".join(lines)

    prev_map  = {h["ticker"]: h for h in prev["holdings"] if h["ticker"] != "CASH"}
    sells, reduces, increases, buys, holds = [], [], [], [], []

    for ticker, ph in prev_map.items():
        if ticker not in new_map:
            sells.append(f"  🔴 *전량 매도*: {ph['name']} ({ticker}) — {ph['weight']}% 전량")
        else:
            nh   = new_map[ticker]
            diff = round(nh["weight"] - ph["weight"], 1)
            if diff < -0.5:
                reduces.append(f"  🔽 *비중 축소*: {nh['name']} ({ticker}) {ph['weight']}% → {nh['weight']}% ({diff:+.1f}%p)")
            elif diff > 0.5:
                increases.append(f"  🔼 *비중 확대*: {nh['name']} ({ticker}) {ph['weight']}% → {nh['weight']}% ({diff:+.1f}%p)")
            else:
                holds.append(f"  ⚪ 유지: {nh['name']} ({ticker}) {nh['weight']}%")

    for ticker, nh in new_map.items():
        if ticker not in prev_map:
            buys.append(f"  🟢 *신규 매수*: {nh['name']} ({ticker}) {nh['weight']}%")

    lines = ["📋 *매매 실행 목록 (이 순서대로 실행 권장)*"]
    for section in [sells, reduces, increases, buys, holds]:
        if section:
            lines.append("")
            lines.extend(section)
    lines.append("")
    lines.append("  ※ 매도·축소 먼저 → 확대·매수 순 (유동성 확보 후 진입)")
    return "\n".join(lines)
