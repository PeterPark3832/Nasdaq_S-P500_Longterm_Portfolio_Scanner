"""
성과 이력 관리 — 저장/로드, 브리핑 생성, 성과 점검 잡
"""
import json
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from scanner.config import PERFORMANCE_HISTORY_FILE, STRATEGY, KST
from scanner.portfolio import load_portfolio
from scanner.telegram_io import send_telegram_chunks

log = logging.getLogger("scanner")


def load_performance_history() -> list[dict]:
    if not PERFORMANCE_HISTORY_FILE.exists():
        return []
    try:
        return json.loads(PERFORMANCE_HISTORY_FILE.read_text(encoding="utf-8")).get("records", [])
    except Exception as e:
        log.warning(f"성과 이력 로드 실패: {e}")
        return []


def save_performance_record(
    record_type: str,
    portfolio_ret_pct: float,
    spy_ret_pct: float | None = None,
    qqq_ret_pct: float | None = None,
    episode: int = 1,
) -> None:
    """성과 스냅샷 추가. 같은 날 + 같은 type이면 덮어씀."""
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    new_rec = {
        "date":              today_str,
        "month":             datetime.now(KST).strftime("%Y-%m"),
        "episode":           episode,
        "type":              record_type,
        "portfolio_ret_pct": round(portfolio_ret_pct, 2),
        "spy_ret_pct":       round(spy_ret_pct, 2) if spy_ret_pct is not None else None,
        "qqq_ret_pct":       round(qqq_ret_pct, 2) if qqq_ret_pct is not None else None,
        "alpha_vs_spy":      round(portfolio_ret_pct - spy_ret_pct, 2)
                             if spy_ret_pct is not None else None,
    }
    records = load_performance_history()
    records = [r for r in records if not (r["date"] == today_str and r["type"] == record_type)]
    records.append(new_rec)
    keep = STRATEGY["perf_history_keep"]
    records = records[-keep:]
    try:
        PERFORMANCE_HISTORY_FILE.write_text(
            json.dumps({"records": records}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(f"  성과 이력 저장: {today_str} / 포트폴리오 {portfolio_ret_pct:+.2f}%")
    except Exception as e:
        log.warning(f"성과 이력 저장 실패: {e}")


def get_quick_portfolio_return(portfolio: dict) -> float:
    """Heartbeat용 가중 수익률 (%). CASH 제외 주식만 계산."""
    from scanner.data import fetch_current_prices
    stock_holdings = [h for h in portfolio.get("holdings", []) if h["ticker"] != "CASH"]
    if not stock_holdings:
        return 0.0
    tickers   = [h["ticker"] for h in stock_holdings]
    price_map = fetch_current_prices(tickers)
    weighted_ret = 0.0
    for h in stock_holdings:
        cur           = price_map.get(h["ticker"], h["entry_price"])
        ret           = (cur - h["entry_price"]) / h["entry_price"] * 100
        weighted_ret += ret * (h["weight"] / 100)
    return weighted_ret


def build_performance_brief(portfolio: dict) -> str:
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return "📭 보유 포트폴리오 없음"

    now_str     = datetime.now(KST).strftime("%Y-%m-%d")
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")
    stock_holdings = [h for h in holdings if h["ticker"] != "CASH"]
    tickers        = [h["ticker"] for h in stock_holdings]

    price_map: dict[str, float] = {}
    stale_set: set[str]         = set()
    try:
        if len(tickers) == 1:
            raw = yf.download(tickers[0], start=start_fetch, progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            if not raw.empty:
                price_map[tickers[0]] = float(raw["Close"].iloc[-1])
            else:
                stale_set.add(tickers[0])
        elif tickers:
            raw = yf.download(tickers, start=start_fetch, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in tickers:
                try:
                    df_t = raw[t].dropna(how="all")
                    if not df_t.empty:
                        price_map[t] = float(df_t["Close"].iloc[-1])
                    else:
                        stale_set.add(t)
                except Exception:
                    stale_set.add(t)
    except Exception as e:
        log.warning(f"성과 점검 벌크 다운로드 실패: {e}")
        stale_set.update(tickers)

    rows = []
    for h in holdings:
        if h["ticker"] == "CASH":
            rows.append({**h, "cur_price": h["entry_price"], "ret_pct": 0.0, "stale": False})
            continue
        cur_price = price_map.get(h["ticker"], h["entry_price"])
        stale     = h["ticker"] in stale_set
        ret_pct   = (cur_price - h["entry_price"]) / h["entry_price"] * 100
        rows.append({**h, "cur_price": cur_price, "ret_pct": round(ret_pct, 2), "stale": stale})

    weighted_ret = sum(r["ret_pct"] * r["weight"] / 100 for r in rows)
    emoji_ret    = "📈" if weighted_ret >= 0 else "📉"

    port_month = portfolio.get("month", "")
    bench_ref  = f"{port_month}-01" if port_month else start_fetch
    spy_ret: float | None = None
    qqq_ret: float | None = None
    try:
        bench_raw = yf.download(["SPY", "QQQ"], start=bench_ref,
                                progress=False, auto_adjust=True)
        for sym in ["SPY", "QQQ"]:
            try:
                # MultiIndex (yfinance >= 0.2): columns = (Price, Ticker) or (Ticker, Price)
                if isinstance(bench_raw.columns, pd.MultiIndex):
                    if ("Close", sym) in bench_raw.columns:
                        s = bench_raw[("Close", sym)].dropna()
                    elif (sym, "Close") in bench_raw.columns:
                        s = bench_raw[(sym, "Close")].dropna()
                    else:
                        s = bench_raw.xs(sym, axis=1, level=1)["Close"].dropna()
                else:
                    # 단일 종목 flat columns
                    s = bench_raw["Close"].dropna()
                if len(s) >= 2:
                    val = round(float(s.iloc[-1] / s.iloc[0] - 1) * 100, 2)
                    if sym == "SPY":
                        spy_ret = val
                    else:
                        qqq_ret = val
            except Exception as ex:
                log.debug(f"벤치마크 파싱 실패 {sym}: {ex}")
    except Exception as e:
        log.warning(f"벤치마크 다운로드 실패: {e}")

    episode = int(portfolio.get("episode", 1))
    save_performance_record("performance_check", weighted_ret, spy_ret, qqq_ret, episode=episode)

    max_eq   = float(portfolio.get("max_equity", weighted_ret))
    peak_ret = max(max_eq, weighted_ret)
    drawdown = weighted_ret - peak_ret

    header = f"{emoji_ret} *미국주식 포트폴리오 성과 점검* ({now_str})\n━━━━━━━━━━━━━━━━━━\n\n"
    body   = ""
    for r in sorted(rows, key=lambda x: -x["ret_pct"]):
        if r["ticker"] == "CASH":
            body += f"💵 *{r['name']}* (비중 {r['weight']}%)\n\n"
            continue
        icon = "🟢" if r["ret_pct"] >= 0 else "🔴"
        warn = " ⚠️" if r["stale"] else ""
        body += (
            f"{icon} *{r['name']}* ({r['ticker']}){warn}\n"
            f"  비중 {r['weight']}% | 진입가 ${r['entry_price']:,.2f}\n"
            f"  현재가 ${r['cur_price']:,.2f} | 수익률 *{r['ret_pct']:+.2f}%*\n\n"
        )

    bench_body = "━━━━━━━━━━━━━━━━━━\n📊 *수익률 비교* (기준: {ref})\n".format(
        ref=bench_ref if port_month else "최근 10일"
    )
    bench_body += f"  포트폴리오: *{weighted_ret:+.2f}%*\n"
    if spy_ret is not None:
        alpha      = weighted_ret - spy_ret
        alpha_icon = "✅" if alpha >= 0 else "❌"
        bench_body += f"  SPY:        {spy_ret:+.2f}%  ({alpha_icon} 알파 {alpha:+.2f}%p)\n"
    if qqq_ret is not None:
        bench_body += f"  QQQ:        {qqq_ret:+.2f}%\n"

    dd_icon  = "🟢" if drawdown > -5 else ("🟡" if drawdown > -10 else "🔴")
    mdd_line = f"  {dd_icon} 고점 대비 낙폭: {drawdown:+.1f}%p (고점 {peak_ret:+.1f}%)\n"

    footer = (
        bench_body
        + mdd_line
        + f"\n⚠️ ⚠️ 표시: 시세 조회 실패 — 진입가로 대체\n"
        f"🗓 다음 리밸런싱에서 자동 갱신 예정"
    )

    return header + body + footer


def job_performance_check() -> None:
    from datetime import datetime as _dt
    now = _dt.now(KST)
    if now.weekday() >= 5:
        return
    portfolio = load_portfolio()
    if not portfolio:
        return
    brief = build_performance_brief(portfolio)
    send_telegram_chunks(brief)
    log.info("[성과 점검] 완료")
