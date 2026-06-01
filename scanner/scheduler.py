"""
스케줄러 메인 — 스케줄 설정, Watchdog, 텔레그램 명령어 폴 루프
"""
import logging
import threading
import time
from datetime import datetime

import schedule

from scanner.config import STRATEGY, KST
from scanner.portfolio import load_portfolio, already_ran_this_month
from scanner.telegram_io import send_telegram, reply_to, reply_to_chunks, get_updates
from scanner.performance import get_quick_portfolio_return, build_performance_brief, job_performance_check
from scanner.alerts import job_heartbeat, check_and_alert_mdd
from scanner.rebalancing import job_monthly_scan, job_daily_rebal_check, is_scan_running

log = logging.getLogger("scanner")

_watchdog_last_tick: float = time.time()
_WATCHDOG_TIMEOUT_SEC = 600


# ── 텔레그램 명령어 핸들러 ──────────────────────────────────────────

def _cmd_status(chat_id: str) -> None:
    """/status — 포트폴리오 수익률 + 낙폭 + 비중 드리프트."""
    from scanner.data import fetch_current_prices
    from scanner.config import TELEGRAM_CHAT_IDS
    portfolio = load_portfolio()
    if not portfolio or not portfolio.get("holdings"):
        reply_to(chat_id, "📭 보유 포트폴리오 없음 — 리밸런싱 후 다시 시도하세요")
        return

    ret_float = get_quick_portfolio_return(portfolio)
    max_eq    = float(portfolio.get("max_equity", ret_float))
    drawdown  = ret_float - max(max_eq, ret_float)
    month     = portfolio.get("month", "?")

    stock_holdings = [h for h in portfolio["holdings"] if h["ticker"] != "CASH"]
    cash_holdings  = [h for h in portfolio["holdings"] if h["ticker"] == "CASH"]

    tickers   = [h["ticker"] for h in stock_holdings]
    price_map = fetch_current_prices(tickers) if tickers else {}

    cash_val = sum(h["weight"] for h in cash_holdings)
    stock_vals: dict[str, float] = {}
    for h in stock_holdings:
        cur  = price_map.get(h["ticker"], h["entry_price"])
        mult = (cur / h["entry_price"]) if h["entry_price"] > 0 else 1.0
        stock_vals[h["ticker"]] = h["weight"] * mult
    total_val = cash_val + sum(stock_vals.values())

    lines = [
        f"📊 *포트폴리오 현황* ({datetime.now(KST).strftime('%Y-%m-%d %H:%M')})",
        f"━━━━━━━━━━━━━━━━━━",
        f"📅 기준월: {month}",
        f"💹 수익률: *{ret_float:+.2f}%*",
        f"📉 고점 대비 낙폭: {drawdown:+.1f}%p (고점 {max(max_eq, ret_float):+.1f}%)",
        "",
        "*보유 종목 (목표비중 → 현재비중 | 손실%):*",
    ]
    drift_threshold = STRATEGY["drift_alert_threshold"]
    sl_threshold    = STRATEGY["stoploss_threshold"]
    sl_warn_level   = sl_threshold * 0.5

    for h in sorted(stock_holdings, key=lambda x: -x["weight"]):
        if total_val > 0:
            cur_w = stock_vals.get(h["ticker"], h["weight"]) / total_val * 100
            drift = cur_w - h["weight"]
            drift_tag = f" ⚠️{drift:+.1f}%p" if abs(drift) >= drift_threshold else f" ({drift:+.1f}%p)"
        else:
            cur_w, drift_tag = h["weight"], ""

        entry = h["entry_price"]
        cur   = price_map.get(h["ticker"], entry)
        if entry > 0:
            loss = (cur / entry - 1) * 100
            if loss <= sl_threshold:
                loss_tag = f"🔴{loss:+.1f}%"
            elif loss <= sl_warn_level:
                loss_tag = f"🟡{loss:+.1f}%"
            else:
                loss_tag = f"{loss:+.1f}%"
        else:
            loss_tag = "N/A"

        lines.append(
            f"  {h['ticker']}  {h['weight']:.1f}%→{cur_w:.1f}%{drift_tag}"
            f" | {loss_tag} | 진입 ${entry:,.2f}"
        )
    reply_to(chat_id, "\n".join(lines))


def _cmd_scan(chat_id: str) -> None:
    """/scan — 수동 리밸런싱 강제 실행 (평일 + 중복 방지)."""
    now = datetime.now(KST)
    if now.weekday() >= 5:
        reply_to(chat_id, "⛔ /scan — 주말에는 실행할 수 없습니다 (평일 전용)")
        return
    if is_scan_running():
        reply_to(chat_id, "⏳ 스캔이 이미 진행 중입니다 — 완료 후 결과가 발송됩니다")
        return
    reply_to(chat_id, "⚡ *수동 리밸런싱 시작* (명령어 트리거)")
    job_monthly_scan()


def _cmd_perf(chat_id: str) -> None:
    """/perf — 성과 점검 즉시 실행."""
    portfolio = load_portfolio()
    if not portfolio:
        reply_to(chat_id, "📭 포트폴리오 없음 — 리밸런싱 후 다시 시도하세요")
        return
    reply_to(chat_id, "⏳ 성과 점검 중... (벤치마크 다운로드 포함)")
    brief = build_performance_brief(portfolio)
    reply_to_chunks(chat_id, brief)


def _cmd_help(chat_id: str) -> None:
    """/help — 명령어 목록."""
    reply_to(
        chat_id,
        "🤖 *미국주식 스캐너 명령어 목록*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "/status — 수익률 + 낙폭 + 비중 드리프트 + 스톱로스 즉시 조회\n"
        "/scan   — 수동 리밸런싱 강제 실행 (평일 전용)\n"
        "/perf   — 성과 점검 즉시 실행 (벤치마크 포함)\n"
        "/help   — 이 메시지\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ 등록된 채팅방에서만 동작합니다",
    )


def _telegram_poll_loop() -> None:
    """Long-polling 명령어 수신 데몬."""
    from scanner.config import TELEGRAM_CHAT_IDS
    offset = 0
    log.info("📨 텔레그램 명령어 수신 시작 (Long-polling)")
    allowed_ids = {str(cid).strip() for cid in TELEGRAM_CHAT_IDS}
    while True:
        try:
            updates = get_updates(offset, timeout=30)
            for upd in updates:
                offset  = upd["update_id"] + 1
                msg     = upd.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", "")).strip()
                text    = msg.get("text", "").strip()
                if not text:
                    continue
                if chat_id not in allowed_ids:
                    log.warning(f"[명령어 차단] 미등록 chat_id={chat_id} text={text!r}")
                    continue
                cmd = text.split()[0].lower().split("@")[0]
                log.info(f"[명령어 수신] chat_id={chat_id} cmd={cmd!r}")
                if cmd == "/status":
                    threading.Thread(target=_cmd_status, args=(chat_id,), daemon=True).start()
                elif cmd == "/scan":
                    threading.Thread(target=_cmd_scan,   args=(chat_id,), daemon=True).start()
                elif cmd == "/perf":
                    threading.Thread(target=_cmd_perf,   args=(chat_id,), daemon=True).start()
                elif cmd == "/help":
                    _cmd_help(chat_id)
                else:
                    reply_to(chat_id, f"❓ 알 수 없는 명령어: {cmd}\n/help 로 목록 확인")
            if not updates:
                time.sleep(1)
        except Exception as e:
            log.error(f"[TG Poll] 데몬 스레드 예외 발생: {e}")
            time.sleep(5)


def _watchdog_loop() -> None:
    """스케줄러 무응답 감지 데몬 (10분)."""
    global _watchdog_last_tick
    while True:
        time.sleep(60)
        age = time.time() - _watchdog_last_tick
        if age > _WATCHDOG_TIMEOUT_SEC:
            log.error(f"[Watchdog] 스케줄러 무응답 {age:.0f}초 — 텔레그램 경보")
            send_telegram(
                f"🚨 *스캐너 이상 감지*\n"
                f"스케줄러 루프가 {age/60:.0f}분째 응답 없음\n"
                f"서버 재시작이 필요할 수 있습니다"
            )
            _watchdog_last_tick = time.time()


def main() -> None:
    from scanner.config import LOG_FILE
    schedule.every().day.at("07:00", "Asia/Seoul").do(job_heartbeat)
    schedule.every().day.at("07:00", "Asia/Seoul").do(job_performance_check)
    schedule.every().day.at("07:10", "Asia/Seoul").do(job_daily_rebal_check)

    log.info("✅ 미국주식 장기 투자 스캐너 v4.11 시작")
    log.info(f"  전략: D 혼합 / 상위 {STRATEGY['portfolio_size']}종목 / 현금 {STRATEGY['safe_asset_weight']}%")
    log.info("  ⏰ 07:00 Heartbeat + 성과 점검(매일) — 전날 미국 장 종가 기준")
    log.info("  ⏰ 07:10 리밸런싱 체크 (한국 봇과 시간 분산)")
    log.info(f"  📝 로그: {LOG_FILE}")

    send_telegram(
        f"✅ *미국주식 장기 투자 스캐너 v4.11 시작*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}\n"
        f"📋 전략: D 혼합 (재무40+기술20+모멘텀40)\n"
        f"🗂 유니버스: S&P500 + 나스닥100 통합\n"
        f"🔢 포트폴리오: 주식 {STRATEGY['portfolio_size']}종목 + 현금 {STRATEGY['safe_asset_weight']}%\n"
        f"📊 백테스트: CAGR +19.49% / MDD -20.54% (2015~2024)\n"
        f"{'📅 당월 리밸런싱: ✅ 완료' if already_ran_this_month() else '📅 당월 리밸런싱: ⏳ 즉시 실행 예정'}"
    )

    if datetime.now(KST).weekday() < 5 and not already_ran_this_month():
        send_telegram("⚡ 이번 달 리밸런싱 미실행 → 즉시 스캔 시작합니다")
        job_monthly_scan()

    threading.Thread(target=_watchdog_loop,       daemon=True, name="watchdog").start()
    threading.Thread(target=_telegram_poll_loop,  daemon=True, name="tg-poll").start()
    log.info("  🐕 Watchdog 시작 (무응답 감지 10분)")
    log.info("  📨 텔레그램 명령어 수신 시작 (/status /scan /perf /help)")

    global _watchdog_last_tick
    while True:
        schedule.run_pending()
        _watchdog_last_tick = time.time()
        time.sleep(1)
