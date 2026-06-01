"""
MDD·드리프트·스톱로스 경보 + Heartbeat
"""
import logging
import threading
from datetime import datetime

from scanner.config import STRATEGY, KST
from scanner.portfolio import load_portfolio, save_portfolio, already_ran_this_month
from scanner.telegram_io import send_telegram

log = logging.getLogger("scanner")


def _update_max_equity(portfolio: dict, current_ret: float) -> float:
    """고점 수익률 갱신. 갱신 시에만 파일 저장."""
    old_max = float(portfolio.get("max_equity", current_ret))
    new_max = max(old_max, current_ret)
    if new_max > old_max:
        portfolio["max_equity"] = new_max
        save_portfolio(portfolio)
    return new_max


def check_and_alert_mdd(portfolio: dict, current_ret: float) -> float:
    """낙폭 임계 초과 시 텔레그램 경보 (1일 쿨다운). 낙폭(%p) 반환."""
    max_eq    = _update_max_equity(portfolio, current_ret)
    drawdown  = current_ret - max_eq
    threshold = STRATEGY["mdd_alert_threshold"]

    if drawdown < threshold:
        today_str  = datetime.now(KST).strftime("%Y-%m-%d")
        last_alert = portfolio.get("last_mdd_alert_date", "")
        if last_alert != today_str:
            log.warning(f"[MDD 경보] 고점 {max_eq:+.1f}% / 현재 {current_ret:+.1f}% / 낙폭 {drawdown:+.1f}%p")
            send_telegram(
                f"🚨 *MDD 경보 — 드로다운 {drawdown:+.1f}%p*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"  이번 달 포트폴리오 고점: *{max_eq:+.1f}%*\n"
                f"  현재 수익률:             *{current_ret:+.1f}%*\n"
                f"  낙폭:                    *{drawdown:+.1f}%p* (임계 {threshold:.0f}%p)\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ 리밸런싱 또는 현금 비중 재검토 권장"
            )
            portfolio["last_mdd_alert_date"] = today_str
            save_portfolio(portfolio)

    return drawdown


def check_and_alert_drift(portfolio: dict) -> list[dict]:
    """비중 드리프트 ±임계 초과 시 경보 (1일 쿨다운). 이탈 종목 리스트 반환."""
    from scanner.data import fetch_current_prices
    threshold = STRATEGY["drift_alert_threshold"]
    today_str = datetime.now(KST).strftime("%Y-%m-%d")

    if portfolio.get("last_drift_alert_date", "") == today_str:
        return []

    stock_holdings = [h for h in portfolio.get("holdings", []) if h["ticker"] != "CASH"]
    cash_holdings  = [h for h in portfolio.get("holdings", []) if h["ticker"] == "CASH"]
    if not stock_holdings:
        return []

    tickers   = [h["ticker"] for h in stock_holdings]
    price_map = fetch_current_prices(tickers)
    if not price_map:
        return []

    cash_val = sum(h["weight"] for h in cash_holdings)
    stock_vals: dict[str, float] = {}
    for h in stock_holdings:
        cur  = price_map.get(h["ticker"], h["entry_price"])
        mult = (cur / h["entry_price"]) if h["entry_price"] > 0 else 1.0
        stock_vals[h["ticker"]] = h["weight"] * mult

    total_val = cash_val + sum(stock_vals.values())
    if total_val <= 0:
        return []

    drifted: list[dict] = []
    for h in stock_holdings:
        target_w  = h["weight"]
        current_w = stock_vals[h["ticker"]] / total_val * 100
        drift     = current_w - target_w
        if abs(drift) >= threshold:
            drifted.append({"ticker": h["ticker"], "target_w": target_w,
                            "current_w": current_w, "drift": drift})

    if cash_holdings:
        target_cash_w  = cash_val
        current_cash_w = cash_val / total_val * 100
        cash_drift     = current_cash_w - target_cash_w
        if abs(cash_drift) >= threshold:
            drifted.append({"ticker": "CASH", "target_w": target_cash_w,
                            "current_w": current_cash_w, "drift": cash_drift})

    if not drifted:
        return []

    drifted.sort(key=lambda x: abs(x["drift"]), reverse=True)
    lines = []
    for d in drifted:
        arrow = "⬆️" if d["drift"] > 0 else "⬇️"
        lines.append(
            f"  {arrow} *{d['ticker']}*  "
            f"목표 {d['target_w']:.1f}% → 현재 {d['current_w']:.1f}%  "
            f"({d['drift']:+.1f}%p)"
        )

    log.warning(f"[드리프트 경보] {len(drifted)}종목 비중 이탈 (임계 ±{threshold:.0f}%p)")
    send_telegram(
        f"⚖️ *비중 드리프트 경보 — {len(drifted)}종목 이탈*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) + "\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"임계값: ±{threshold:.0f}%p\n"
        f"리밸런싱 필요 시 /scan 실행 또는 수동 조정 검토"
    )
    portfolio["last_drift_alert_date"] = today_str
    save_portfolio(portfolio)
    return drifted


def check_and_alert_stoploss(portfolio: dict) -> None:
    """진입가 대비 손실 임계 도달 시 종목별 경보 (1일 쿨다운)."""
    from scanner.data import fetch_current_prices
    stock_holdings = [h for h in portfolio.get("holdings", []) if h["ticker"] != "CASH"]
    if not stock_holdings:
        return

    threshold  = STRATEGY["stoploss_threshold"]
    today_str  = datetime.now(KST).strftime("%Y-%m-%d")
    last_alerts: dict[str, str] = portfolio.get("last_stoploss_alerts", {})

    tickers   = [h["ticker"] for h in stock_holdings]
    price_map = fetch_current_prices(tickers)

    portfolio_updated = False
    for h in stock_holdings:
        ticker      = h["ticker"]
        entry_price = h["entry_price"]
        if entry_price <= 0:
            continue
        cur  = price_map.get(ticker, entry_price)
        loss = (cur / entry_price - 1) * 100
        if loss > threshold:
            continue
        if last_alerts.get(ticker) == today_str:
            continue

        log.warning(
            f"[스톱로스 경보] {ticker} 진입가 ${entry_price:,.2f} → "
            f"현재 ${cur:,.2f} ({loss:+.1f}%) / 임계 {threshold:.0f}%"
        )
        send_telegram(
            f"🔴 *스톱로스 경보 — {ticker}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"  진입가:    *${entry_price:,.2f}*\n"
            f"  현재가:    *${cur:,.2f}*\n"
            f"  손실:      *{loss:+.1f}%* (임계 {threshold:.0f}%)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ 해당 종목 전략 적합성 재검토 또는 /scan 으로 리밸런싱 고려"
        )
        last_alerts[ticker] = today_str
        portfolio_updated   = True

    if portfolio_updated:
        portfolio["last_stoploss_alerts"] = last_alerts
        save_portfolio(portfolio)


def _send_heartbeat() -> None:
    from scanner.performance import get_quick_portfolio_return
    now       = datetime.now(KST)
    now_month = now.strftime("%Y-%m")
    status    = "✅ 완료" if already_ran_this_month() else "⏳ 오늘 07:10 실행 예정"
    portfolio = load_portfolio()

    if portfolio and portfolio.get("holdings"):
        pf_len    = len(portfolio["holdings"])
        ret_float = get_quick_portfolio_return(portfolio)
        ret_str   = f"{ret_float:+.2f}%"

        drawdown = check_and_alert_mdd(portfolio, ret_float)
        dd_str   = f" | 낙폭 *{drawdown:+.1f}%p*" if drawdown < -3.0 else ""

        check_and_alert_drift(portfolio)
        check_and_alert_stoploss(portfolio)

        pf_str = f"총 {pf_len}항목 보유 중 (수익률: *{ret_str}*{dd_str}, USD)"
    else:
        pf_str = "없음"

    send_telegram(
        f"💚 *미국주식 스캐너 정상 작동* ({now.strftime('%Y-%m-%d %H:%M')})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 {now_month} 리밸런싱: {status}\n"
        f"🗂 현재 상태: {pf_str}"
    )
    log.info("Heartbeat 발송")


def job_heartbeat() -> None:
    if datetime.now(KST).weekday() >= 5:
        return
    threading.Thread(target=_send_heartbeat, daemon=True).start()
