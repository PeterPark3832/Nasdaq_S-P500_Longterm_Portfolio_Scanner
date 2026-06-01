"""
yfinance 재무 캐시, 벌크 가격 다운로드, VIX
"""
import logging
import threading
import time
from datetime import datetime

import pandas as pd
import yfinance as yf

from scanner.config import INFO_CACHE_FILE, STRATEGY, KST

log = logging.getLogger("scanner")

_INFO_CACHE_MAX_AGE_HOURS = 72

_info_cache: dict[str, dict] = {}
_info_cache_lock = threading.Lock()
_sem = threading.Semaphore(STRATEGY["info_workers"])


def load_info_cache() -> None:
    global _info_cache
    if not INFO_CACHE_FILE.exists():
        return
    try:
        data = INFO_CACHE_FILE.read_text(encoding="utf-8")
        import json
        data = __import__("json").loads(data)
        now = datetime.now(KST)
        now_month = now.strftime("%Y-%m")
        if data.get("month") != now_month:
            log.info("재무 캐시 폐기 — 월 불일치")
            return
        saved_at_str = data.get("saved_at")
        if saved_at_str:
            saved_at = datetime.fromisoformat(saved_at_str)
            age_hours = (now.replace(tzinfo=None) - saved_at.replace(tzinfo=None)).total_seconds() / 3600
            if age_hours > _INFO_CACHE_MAX_AGE_HOURS:
                log.info(f"재무 캐시 폐기 — {age_hours:.1f}h 경과 (허용 {_INFO_CACHE_MAX_AGE_HOURS}h)")
                return
        raw_cache = data.get("cache", {})
        _info_cache = {t: v for t, v in raw_cache.items() if v}
        skipped = len(raw_cache) - len(_info_cache)
        log.info(f"재무 캐시 복원: {len(_info_cache)}개 종목 (빈 항목 {skipped}개 제외)")
    except Exception as e:
        log.warning(f"재무 캐시 로드 실패: {e}")


def save_info_cache() -> None:
    import json
    now = datetime.now(KST)
    with _info_cache_lock:
        INFO_CACHE_FILE.write_text(
            json.dumps(
                {"month": now.strftime("%Y-%m"), "saved_at": now.isoformat(), "cache": _info_cache},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def get_ticker_info(ticker: str) -> dict:
    """yfinance 재무 데이터 (당월 캐시 우선)."""
    with _info_cache_lock:
        if ticker in _info_cache:
            return _info_cache[ticker]
    try:
        with _sem:
            info = yf.Ticker(ticker).info
            time.sleep(0.15)
    except Exception:
        info = {}
    with _info_cache_lock:
        _info_cache[ticker] = info
    return info


def fetch_info_with_retry(ticker: str) -> dict:
    """재시도 포함 yfinance.info 조회 (병렬 스캔 워커용)."""
    with _info_cache_lock:
        cached = _info_cache.get(ticker)
    if cached:
        return cached
    for attempt in range(STRATEGY["info_retry"]):
        try:
            with _sem:
                info = yf.Ticker(ticker).info
                time.sleep(0.3)
            with _info_cache_lock:
                _info_cache[ticker] = info
            return info
        except Exception as e:
            if attempt < STRATEGY["info_retry"] - 1:
                wait = STRATEGY["info_retry_delay"] * (2 ** attempt)
                log.debug(f"  {ticker} info 재시도 {attempt+1} ({wait:.0f}초 대기): {e}")
                time.sleep(wait)
    return {}


def get_vix_level() -> float:
    """현재 VIX 수준 조회. 실패 시 0.0 반환 (중립 처리)."""
    try:
        vix_df = yf.download("^VIX", period="5d", progress=False, auto_adjust=False)
        if isinstance(vix_df.columns, pd.MultiIndex):
            vix_df.columns = vix_df.columns.get_level_values(0)
        if not vix_df.empty:
            return float(vix_df["Close"].iloc[-1])
    except Exception as e:
        log.warning(f"VIX 조회 실패: {e}")
    return 0.0


def get_regime_cash_weight(vix: float) -> float:
    """VIX 레벨에 따른 현금 비중 반환."""
    base = STRATEGY["safe_asset_weight"]
    cap  = STRATEGY["vix_cash_cap"]
    if vix >= STRATEGY["vix_fear"]:
        return min(base + 30.0, cap)
    if vix >= STRATEGY["vix_caution"]:
        return min(base + 20.0, cap)
    return base


def bulk_download_prices(tickers: list[str], price_start: str) -> dict[str, pd.DataFrame]:
    """청크 단위 벌크 다운로드. 실패 시 개별 재시도."""
    chunk_size = STRATEGY["bulk_chunk_size"]
    price_data: dict[str, pd.DataFrame] = {}
    chunks = [tickers[i:i+chunk_size] for i in range(0, len(tickers), chunk_size)]
    for ci, chunk in enumerate(chunks, 1):
        log.info(f"  벌크 다운로드 [{ci}/{len(chunks)}] {len(chunk)}개...")
        try:
            raw = yf.download(
                chunk, start=price_start,
                group_by="ticker", auto_adjust=True,
                progress=False, threads=True,
            )
            if len(chunk) == 1:
                t = chunk[0]
                if not raw.empty:
                    price_data[t] = raw
            else:
                for t in chunk:
                    try:
                        df_t = raw[t].dropna(how="all")
                        if not df_t.empty:
                            price_data[t] = df_t
                    except Exception:
                        pass
            time.sleep(1.0)
        except Exception as e:
            log.warning(f"  벌크 다운로드 청크 {ci} 실패: {e} — 개별 재시도...")
            for t in chunk:
                for attempt in range(3):
                    try:
                        df_t = yf.download(t, start=price_start, progress=False, auto_adjust=True)
                        if isinstance(df_t.columns, pd.MultiIndex):
                            df_t.columns = df_t.columns.get_level_values(0)
                        if not df_t.empty:
                            price_data[t] = df_t
                        break
                    except Exception:
                        time.sleep(2 ** attempt)
    return price_data


def fetch_current_prices(tickers: list[str]) -> dict[str, float]:
    """최근 10일 벌크 다운로드로 현재가 조회."""
    from datetime import timedelta
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")
    price_map: dict[str, float] = {}
    try:
        if len(tickers) == 1:
            raw = yf.download(tickers[0], start=start_fetch, progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            if not raw.empty:
                price_map[tickers[0]] = float(raw["Close"].iloc[-1])
        elif tickers:
            raw = yf.download(tickers, start=start_fetch, group_by="ticker",
                              progress=False, auto_adjust=True, threads=True)
            for t in tickers:
                try:
                    df_t = raw[t].dropna(how="all")
                    if not df_t.empty:
                        price_map[t] = float(df_t["Close"].iloc[-1])
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"현재가 조회 실패: {e}")
    return price_map
