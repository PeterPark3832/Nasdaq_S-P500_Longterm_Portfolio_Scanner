"""
월간 리밸런싱 스캔 — 메인 파이프라인
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd

from scanner.config import PORTFOLIO_PREV_FILE, STRATEGY, KST
from scanner.data import (
    load_info_cache, save_info_cache,
    fetch_info_with_retry, get_vix_level, get_regime_cash_weight,
    bulk_download_prices,
)
from scanner.portfolio import (
    load_portfolio, save_portfolio, save_last_rebal,
    already_ran_this_month, build_rebalancing_brief, is_fresh_start,
)
from scanner.performance import save_performance_record
from scanner.scoring import analyze_ticker, apply_sector_cap, calc_stock_weights
from scanner.telegram_io import send_telegram, send_telegram_chunks
from scanner.universe import get_universe_tickers, save_universe_snapshot, load_prev_universe_snapshot

log = logging.getLogger("scanner")

_scan_lock    = threading.Lock()
_scan_running = False


def _do_monthly_scan() -> None:
    now_month = datetime.now(KST).strftime("%Y-%m")
    if already_ran_this_month():
        return

    t_start        = time.time()
    prev_portfolio = load_portfolio()
    fresh_start    = is_fresh_start(prev_portfolio)

    # 에피소드 번호 결정
    if fresh_start and prev_portfolio:
        episode        = prev_portfolio.get("episode", 1) + 1
        episode_start  = datetime.now(KST).strftime("%Y-%m-%d")
    elif fresh_start:
        episode        = 1
        episode_start  = datetime.now(KST).strftime("%Y-%m-%d")
    else:
        episode        = prev_portfolio.get("episode", 1)
        episode_start  = prev_portfolio.get("episode_start_date",
                                            datetime.now(KST).strftime("%Y-%m-%d"))

    mode_label = (
        f"🆕 에피소드 {episode} — 첫 구성" if (fresh_start and not prev_portfolio) else
        f"🔄 에피소드 {episode} — 재진입" if fresh_start else
        f"📅 에피소드 {episode} — 정기 리밸런싱"
    )
    log.info(f"[리밸런싱] 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M')} / {mode_label}")
    send_telegram(
        f"{'🔄' if not fresh_start else '🆕'} *{datetime.now(KST).strftime('%Y년 %m월')} 미국주식 리밸런싱 시작*\n"
        f"{mode_label}\n"
        f"⚙️ D 전략 (재무40+기술20+모멘텀40) / 상위 {STRATEGY['portfolio_size']}종목\n"
        f"⏳ 약 15~30분 소요 (유니버스 ~550종목 분석)..."
    )

    try:
        # ── Step 1. 유니버스 + 스냅샷 저장 ──────────────────
        tickers       = get_universe_tickers()
        prev_universe = load_prev_universe_snapshot()
        save_universe_snapshot(tickers)
        if prev_universe:
            new_entries = set(tickers) - set(prev_universe)
            removed     = set(prev_universe) - set(tickers)
            if new_entries or removed:
                log.info(f"  유니버스 변동: 신규 +{len(new_entries)}개 / 제외 -{len(removed)}개")

        # ── Step 2. 가격 데이터 벌크 다운로드 + VIX 조회 ────
        import yfinance as yf
        log.info("[Step 2] 가격 데이터 벌크 다운로드...")
        price_start = (datetime.now(KST) - timedelta(days=420)).strftime("%Y-%m-%d")

        vix_level   = get_vix_level()
        cash_weight = get_regime_cash_weight(vix_level)
        if vix_level > 0:
            regime_label = (
                "🔴 공포" if vix_level >= STRATEGY["vix_fear"] else
                "🟡 주의" if vix_level >= STRATEGY["vix_caution"] else
                "🟢 정상"
            )
            log.info(f"  VIX: {vix_level:.1f} ({regime_label}) → 현금 비중 {cash_weight:.0f}%")
        else:
            log.warning("  VIX 조회 실패 → 기본 현금 비중 유지")

        spy_6m = 0.0
        try:
            spy_df = yf.download("SPY", start=price_start, progress=False, auto_adjust=True)
            if isinstance(spy_df.columns, pd.MultiIndex):
                spy_df.columns = spy_df.columns.get_level_values(0)
            if len(spy_df) >= 126:
                spy_6m = float(spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-126] - 1)
            log.info(f"  SPY 6개월 수익률: {spy_6m*100:+.1f}%")
        except Exception as e:
            log.warning(f"  SPY 로딩 실패 ({e})")

        price_data = bulk_download_prices(tickers, price_start)
        log.info(f"  가격 데이터 수신: {len(price_data)}개 / {len(tickers)}개")

        elapsed_s2 = time.time() - t_start
        regime_label_s2 = (
            "🔴 공포" if vix_level >= STRATEGY["vix_fear"] else
            "🟡 주의" if vix_level >= STRATEGY["vix_caution"] else
            "🟢 정상" if vix_level > 0 else "⚪ 조회불가"
        )
        send_telegram(
            f"📊 *[Step 2 완료]* 가격 데이터 수신 {len(price_data)}/{len(tickers)}개 ({elapsed_s2:.0f}초)\n"
            f"  VIX: {vix_level:.1f} ({regime_label_s2}) → 현금 {cash_weight:.0f}%\n"
            f"⏳ Step 3 재무 분석 중... (약 10~20분 소요)"
        )

        # ── Step 3. 재무 데이터 로딩 + 스코어링 ─────────────
        log.info("[Step 3] 재무 데이터 로딩 + 스코어링...")
        load_info_cache()
        valid_tickers = list(price_data.keys())

        scored = []
        with ThreadPoolExecutor(max_workers=STRATEGY["info_workers"]) as executor:
            futures = {executor.submit(fetch_info_with_retry, t): t for t in valid_tickers}
            done = 0
            for future in as_completed(futures):
                done += 1
                ticker = futures[future]
                try:
                    info_data = future.result()
                    result = analyze_ticker(ticker, price_data[ticker], spy_6m, info=info_data)
                    if result:
                        scored.append(result)
                except Exception as e:
                    log.debug(f"  [SKIP] {ticker}: {e}")
                if done % 50 == 0:
                    elapsed = time.time() - t_start
                    log.info(f"  진행: {done}/{len(valid_tickers)} | 통과: {len(scored)}개 | {elapsed:.0f}초")

        log.info(f"  기술+재무 필터 통과: {len(scored)}개")

        if not scored:
            send_telegram("❌ *통과 종목 없음* — 필터 조건 검토 필요")
            return

        elapsed_s3 = time.time() - t_start
        send_telegram(
            f"✅ *[Step 3 완료]* 재무 분석 완료 ({elapsed_s3:.0f}초)\n"
            f"  필터 통과: {len(scored)}/{len(valid_tickers)}개\n"
            f"⏳ 최종 순위 산정 + 브리핑 생성 중..."
        )

        # ── Step 4. 모멘텀 퍼센타일 + 섹터 다양성 적용 ────
        df_s = pd.DataFrame(scored)
        df_s["mom_6m"]  = df_s["ret_6m"].rank(pct=True) * 20
        df_s["mom_12m"] = df_s["ret_12m"].rank(pct=True) * 20
        df_s["total_score"] = (df_s["base_score"] + df_s["mom_6m"] + df_s["mom_12m"]).round(1)

        top = apply_sector_cap(df_s, STRATEGY["portfolio_size"], STRATEGY["sector_max"])
        sector_dist = top["sector"].value_counts().to_dict()
        log.info(f"  섹터 분포: {sector_dist}")

        # ── Step 5. 비중 계산 (VIX 레짐 반영) ────────────
        stock_weight = 100.0 - cash_weight
        weights      = calc_stock_weights(top["total_score"].tolist(), stock_weight)

        # ── Step 6. 포트폴리오 빌드 ───────────────────────
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        prev_map  = {h["ticker"]: h for h in (prev_portfolio or {}).get("holdings", [])}

        new_holdings = [{
            "ticker":      "CASH",
            "name":        "안전 자산 (달러 예수금/MMF)",
            "weight":      float(cash_weight),
            "entry_price": 1.0,
            "entry_date":  today_str,
            "score":       0.0,
            "sector":      "Cash",
            "roe": 0.0, "margin": 0.0, "peg": 0.0,
            "rev_growth": 0.0, "fcf_margin": 0.0, "de_ratio": 0.0,
            "ret_6m": 0.0, "w52_pos": 0.0,
            "data_stale": False, "fin_report_dt": "",
        }]

        for i, (_, row) in enumerate(top.iterrows()):
            ticker = str(row["ticker"])
            if ticker in prev_map and prev_map[ticker]["ticker"] != "CASH":
                entry_price = float(prev_map[ticker]["entry_price"])
                entry_date  = str(prev_map[ticker]["entry_date"])
            else:
                entry_price = float(row["close"])
                entry_date  = today_str

            new_holdings.append({
                "ticker":        ticker,
                "name":          str(row["name"]),
                "sector":        str(row.get("sector", "Unknown")),
                "weight":        float(weights[i]),
                "entry_price":   entry_price,
                "entry_date":    entry_date,
                "score":         float(round(row["total_score"], 1)),
                "roe":           float(row["roe"]),
                "margin":        float(row["margin"]),
                "peg":           float(row["peg"]),
                "rev_growth":    float(row.get("rev_growth",    0.0)),
                "fcf_margin":    float(row.get("fcf_margin",    0.0)),
                "de_ratio":      float(row.get("de_ratio",      0.0)),
                "ret_6m":        float(row["ret_6m"]),
                "w52_pos":       float(row["w52_pos"]),
                "data_stale":    bool(row.get("data_stale",     False)),
                "fin_report_dt": str(row.get("fin_report_dt",   "")),
            })

        # ── Step 7. 브리핑 발송 + 저장 ────────────────────
        elapsed = time.time() - t_start
        log.info(f"[Step 7] 브리핑 발송 — 소요: {elapsed:.0f}초")

        brief = build_rebalancing_brief(
            prev_portfolio, new_holdings,
            vix_level=vix_level, cash_weight=cash_weight,
            episode=episode,
        )
        send_telegram_chunks(brief)
        save_info_cache()

        if prev_portfolio and prev_portfolio.get("holdings"):
            import json
            PORTFOLIO_PREV_FILE.write_text(
                json.dumps(prev_portfolio, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        save_portfolio({
            "month":                now_month,
            "episode":              episode,
            "episode_start_date":   episode_start,
            "holdings":             new_holdings,
            "max_equity":           0.0,
            "last_stoploss_alerts": {},
        })
        save_last_rebal(now_month)
        save_performance_record("rebalancing", portfolio_ret_pct=0.0, episode=episode)

        log.info(f"[완료] 리밸런싱 완료 / {elapsed:.0f}초")
        for h in new_holdings:
            if h["ticker"] != "CASH":
                log.info(f"  {h['ticker']:8s} 비중:{h['weight']:5.1f}% 점수:{h['score']:.1f}")

    except Exception as e:
        log.exception(f"[ERROR] 스캔 예외: {e}")
        send_telegram(f"🚨 *리밸런싱 오류*\n```{e}```")


def _run_scan_in_thread() -> None:
    global _scan_running
    with _scan_lock:
        if _scan_running:
            log.warning("스캔 이미 진행 중")
            return
        _scan_running = True
    try:
        _do_monthly_scan()
    finally:
        with _scan_lock:
            _scan_running = False


def job_monthly_scan() -> None:
    threading.Thread(target=_run_scan_in_thread, daemon=True).start()


def job_daily_rebal_check() -> None:
    if datetime.now(KST).weekday() >= 5:
        return
    if not already_ran_this_month():
        log.info("당월 미실행 → 스캔 트리거")
        job_monthly_scan()


def is_scan_running() -> bool:
    with _scan_lock:
        return _scan_running
