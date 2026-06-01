"""
전략 파라미터, 파일 경로, 환경변수, 로깅 — 모든 모듈의 공통 설정
"""
import os
import logging
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

# ── 로깅 ──────────────────────────────────────────────────────────
LOG_FILE = Path("longterm_scanner_us.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("scanner")

# ── 환경변수 ────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
_raw_ids          = os.getenv("TELEGRAM_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID") or ""
TELEGRAM_CHAT_IDS = [cid.strip() for cid in _raw_ids.split(",") if cid.strip()]
_raw_topic        = os.getenv("TELEGRAM_TOPIC_ID", "").split("#")[0].strip()
TELEGRAM_TOPIC_ID = int(_raw_topic) if _raw_topic.isdigit() else None

# ── 파일 경로 ────────────────────────────────────────────────────────
PORTFOLIO_FILE          = Path("portfolio_state_us.json")
PORTFOLIO_PREV_FILE     = Path("portfolio_prev_us.json")
LAST_REBAL_FILE         = Path("last_rebal_us.json")
INFO_CACHE_FILE         = Path("yf_info_cache.json")
UNIVERSE_SNAPSHOT_DIR   = Path("universe_snapshots")
PERFORMANCE_HISTORY_FILE = Path("performance_history.json")

# ── 전략 파라미터 ────────────────────────────────────────────────────
STRATEGY: dict = {
    "portfolio_size":       10,
    "safe_asset_weight":    30.0,
    "use_ma200":            True,
    "max_stale_days":       10,

    "info_workers":         3,
    "info_retry":           3,
    "info_retry_delay":     5.0,
    "bulk_chunk_size":      100,

    "de_ratio_max":         200.0,
    "sector_max":           3,

    "vix_caution":          30,
    "vix_fear":             40,
    "vix_cash_cap":         60.0,

    "fin_stale_skip_days":  400,
    "fin_stale_warn_days":  200,
    "universe_snapshot_keep": 12,

    "mdd_alert_threshold":  -15.0,
    "perf_history_keep":    500,

    "drift_alert_threshold": 10.0,
    "stoploss_threshold":   -20.0,
}
