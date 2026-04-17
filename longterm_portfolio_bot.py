"""
미국주식 장기투자 포트폴리오 봇 v1.0
────────────────────────────────────────────────────────────────────
v4.11(월별 스캐너) → v1.0(장기투자 전문 봇) 전면 재설계

[전략 브리핑 — QM전략: Quality-Momentum Long-Term]

■ 왜 이 팩터인가?
  · Quality: 우량 기업은 장기적으로 시장을 초과 수익 (Novy-Marx 2013,
             Fama-French 5-factor 2015). 복리의 마법을 극대화.
  · Momentum: 12개월 가격 모멘텀은 가장 강력한 예측 팩터 중 하나.
              (Jegadeesh & Titman 1993, Carhart 4-factor 1997)
              장기 보유(분기 리밸런싱)에서 모멘텀 반전 위험 최소화.
  · Value: P/FCF 기반 저평가 필터로 과매수 리스크 완화.

■ 과최적화 방지 원칙
  1. 학술적으로 검증된 팩터만 사용 (임의 조합 금지)
  2. 팩터 가중치 고정 (백테스트로 최적화 안 함)
  3. 워크포워드 백테스트 — 미래 데이터 사용 없음
  4. 파라미터는 사전 지식 기반 상식적 임계값 사용
  5. SPY/QQQ 벤치마크 동기간 비교

■ 스크리닝 조건 (필터, 순서대로 적용)
  Step 1. 유니버스: S&P500 + NASDAQ100 + S&P MidCap400 + S&P SmallCap600
                    ≈ 1,500종목 (미국 전체 상장주의 유동성 상위 80%)
  Step 2. 유동성 필터:
          · 주가 ≥ $5 (패니 스톡 제외)
          · 시가총액 ≥ $1B (대·중형주)
          · 일평균거래량 ≥ 10만주 (유동성 보장)
  Step 3. 재무 안전성 필터:
          · 비금융 섹터 D/E ≤ 300% (과도한 레버리지 제외)
          · 재무 보고서 신선도 ≤ 400일 (구식 데이터 제외)
  Step 4. 추세 필터:
          · 200일 이동평균 위 (하락장 보호, 옵션)
  Step 5. 시장 레짐 필터:
          · VIX ≥ 30: 현금 비중 +20%p
          · VIX ≥ 40: 현금 비중 +30%p

[QM 스코어링 — 100점 만점]

  ① Quality (50점) — 재무 우량성
     ROE (자기자본이익률)      0~15점  높을수록
     순이익률                  0~10점  높을수록
     매출성장률 (YoY or 3yr)   0~10점  높을수록
     FCF 마진 (FCF/매출)       0~10점  높을수록
     부채 안전성 (D/E 역수)    0~5점   낮을수록

  ② Momentum (30점) — 가격 추세 (퍼센타일)
     12개월 수익률 퍼센타일    0~20점  높을수록
     6개월 수익률 퍼센타일     0~10점  높을수록

  ③ Value (20점) — 저평가 (퍼센타일 역순)
     P/FCF 퍼센타일 역순       0~10점  낮을수록 (저평가)
     EV/EBITDA 퍼센타일 역순   0~10점  낮을수록 (저평가)

[자산 배분]
  주식 70% (top 15종목 점수 비례 배분)
  현금 30% (VIX 레짐 시 자동 확대, 최대 60%)
  리밸런싱: 분기 1회 (1·4·7·10월 첫 거래일)

[백테스트 방법론]
  기간: 2010년 ~ 현재 (15년)
  방식: 워크포워드 (Walk-Forward)
        - 각 분기 시작일 기준으로 스코어 계산
        - 가격 팩터: 완전 point-in-time (편향 없음)
        - 재무 팩터: yfinance.info 현재값 프록시 사용
                     ⚠️ 미래참조 편향 존재 (단순화 트레이드오프)
  유니버스 백테스트: S&P500 (속도 최적화, 재무 데이터 조회)
  성과지표: CAGR, MDD, Sharpe, Sortino, Calmar, Alpha vs SPY/QQQ

[편향 경고]
  ⚠️ 생존자 편향: 현재 S&P1500 구성종목 기준 → 상폐/퇴출 종목 미포함
  ⚠️ 재무 미래참조: yfinance.info는 현재 재무값 반환 (백테스트 한계)
  ⚠️ 유동성 편향: 과거 소형주가 현재 기준으로 필터될 수 있음
  ⚠️ 섹터 편향: 현재 섹터 분류 사용 (과거 섹터 변경 미반영)

[성과 지표 정의]
  CAGR     연평균 복리수익률 (Compound Annual Growth Rate)
  MDD      최대 낙폭 (Maximum Drawdown, 고점 대비 최대 손실)
  Sharpe   위험 대비 초과수익 (무위험 수익률 4% 가정)
  Sortino  하방 위험만 고려한 샤프 비율
  Calmar   CAGR / |MDD| (낙폭 대비 수익)
  Alpha    SPY 대비 연간 초과수익률
  Win Rate 양수 수익률 분기 비율

[스케줄 — KST 기준]
  매일 07:00   → Heartbeat (전날 미국 장 마감 종가 기준 수익률)
  매일 07:10   → 리밸런싱 체크 (분기 미실행 시 즉시 실행)
  매월 15일 07:00 → 중간 성과 점검 (SPY·QQQ 벤치마크 비교)

[실행 방법]
  python longterm_portfolio_bot.py            # 라이브 봇 시작
  python longterm_portfolio_bot.py --backtest # 백테스트 실행 후 봇 시작
  python longterm_portfolio_bot.py --bt-only  # 백테스트만 실행 후 종료

[텔레그램 명령어]
  /status    포트폴리오 현황 + 수익률
  /scan      수동 리밸런싱 강제 실행
  /perf      성과 점검 즉시 실행
  /backtest  백테스트 결과 조회 (저장된 결과 표시)
  /help      명령어 목록
────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import json
import math
import logging
import threading
import argparse
import requests
import schedule
import numpy as np
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

# ══════════════════════════════════════════
# SSL 인증서 경로 수정 (Windows 한글 사용자명)
# ══════════════════════════════════════════
# yfinance 내부의 curl_cffi 라이브러리는 certifi 인증서 파일을 사용하는데,
# 사용자 폴더명에 한글(쩡이 등)이 있으면 curl이 해당 경로를 읽지 못함.
# → 인증서를 ASCII 경로인 시스템 임시 폴더로 복사 후 환경변수로 등록.
def _fix_ssl_cert_path() -> None:
    """
    Windows 한글 사용자명 경로에서 yfinance(curl_cffi) SSL 인증서 오류 수정.

    문제: curl_cffi가 certifi의 cacert.pem을 로드할 때 한글 경로를 처리 못함.
    해결: certifi 파일을 ASCII-only 경로로 복사 후 CURL_CA_BUNDLE 환경변수 등록.
    """
    import shutil
    import ssl
    try:
        import certifi
        src = certifi.where()
    except ImportError:
        return  # certifi 없으면 스킵

    # 경로에 비ASCII 문자가 없으면 수정 불필요
    try:
        src.encode("ascii")
        os.environ.setdefault("CURL_CA_BUNDLE",    src)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", src)
        return
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # 한글 등 비ASCII 포함 → 복사 필요

    # ASCII-only 경로 후보 (우선순위 순)
    sysroot = os.environ.get("SYSTEMROOT", "C:\\Windows")
    candidates = [
        os.path.join(sysroot, "Temp", "yf_ssl"),   # C:\Windows\Temp\yf_ssl
        "C:\\ProgramData\\yf_ssl",                  # C:\ProgramData\yf_ssl
        "C:\\Temp\\yf_ssl",                          # C:\Temp\yf_ssl
        "C:\\Users\\Public\\yf_ssl",                 # C:\Users\Public\yf_ssl
    ]

    dst = None
    for candidate in candidates:
        try:
            candidate.encode("ascii")  # 경로 ASCII 검증
            os.makedirs(candidate, exist_ok=True)
            dst_path = os.path.join(candidate, "cacert.pem")
            # 이미 복사된 파일이 있으면 재사용
            if not os.path.exists(dst_path):
                shutil.copy2(src, dst_path)
            dst = dst_path
            break
        except Exception:
            continue

    if dst:
        os.environ["CURL_CA_BUNDLE"]    = dst
        os.environ["REQUESTS_CA_BUNDLE"] = dst
        print(f"[SSL] 인증서 경로 수정: {dst}")
    else:
        # 모든 후보 실패 → SSL 검증 비활성화 (폴백)
        ssl._create_default_https_context = ssl._create_unverified_context
        os.environ["CURL_CA_BUNDLE"]    = ""
        os.environ["REQUESTS_CA_BUNDLE"] = ""
        print("[SSL] 경고: SSL 인증서 우회 (모든 ASCII 경로 접근 실패)")

_fix_ssl_cert_path()

# ══════════════════════════════════════════
# 로깅
# ══════════════════════════════════════════
LOG_FILE = Path("longterm_portfolio_bot.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════
# 환경변수
# ══════════════════════════════════════════
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
_raw_ids = os.getenv("TELEGRAM_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID") or ""
TELEGRAM_CHAT_IDS = [cid.strip() for cid in _raw_ids.split(",") if cid.strip()]

_raw_topic = os.getenv("TELEGRAM_TOPIC_ID", "").split("#")[0].strip()
TELEGRAM_TOPIC_ID = int(_raw_topic) if _raw_topic.isdigit() else None

def _is_supergroup(chat_id: str) -> bool:
    return str(chat_id).startswith("-100")

# ══════════════════════════════════════════
# 전략 파라미터 (QM전략 — 과최적화 방지 설계)
# ══════════════════════════════════════════
STRATEGY = {
    # ── 포트폴리오 구성 ──────────────────────────────────
    # [근거] 분산 vs 집중의 균형: 15종목이 MDD·샤프 최적
    #        top_n=10: 집중도 높아 변동성↑, top_n=20: 수익률↓
    "portfolio_size":    15,

    # [근거] 장기투자: 안전자산 30% = 심리적 MDD 방어 + 기회 현금
    "safe_asset_weight": 30.0,

    # ── 리밸런싱 주기 ────────────────────────────────────
    # 장기투자: 분기 1회 (1/4/7/10월)
    # [근거] 월별 리밸런싱 대비 거래비용↓, 모멘텀 반전 위험↓
    "rebal_months":      [1, 4, 7, 10],

    # ── 유동성 필터 ──────────────────────────────────────
    "min_price":         5.0,      # 최소 주가 ($)
    "min_market_cap":    1e9,      # 최소 시가총액 ($1B)
    "min_avg_volume":    100_000,  # 최소 일평균 거래량 (주)

    # ── 재무 안전성 필터 ─────────────────────────────────
    # [근거] D/E 300% 초과는 이자 부담으로 성장 저해 위험
    #        금융·부동산 섹터는 레버리지 사업 특성상 면제
    "de_ratio_max":      300.0,    # 비금융 최대 부채비율 (%)

    # 재무 보고서 신선도 (최근 분기 기준)
    "fin_stale_skip_days": 400,    # 이 일수 초과 시 제외
    "fin_stale_warn_days": 200,    # 이 일수 초과 시 ⚠️ 경고

    # ── 추세 필터 ────────────────────────────────────────
    "use_ma200":         True,     # MA200 위 필터 (하락장 보호)
    "max_stale_days":    10,       # 거래정지 판단 기준일

    # ── 섹터 다양성 ──────────────────────────────────────
    # [근거] IT 편중 방지. Unknown 면제 (섹터 미분류)
    "sector_max":        3,        # 동일 섹터 최대 종목 수

    # ── 시장 레짐 (VIX 기반) ────────────────────────────
    # [근거] VIX 30+ = 공포 구간, 현금 확대로 MDD 방어
    "vix_caution":       30,       # 현금 +20%p
    "vix_fear":          40,       # 현금 +30%p
    "vix_cash_cap":      60.0,     # 최대 현금 비중 (%)

    # ── 경보 임계값 ──────────────────────────────────────
    "mdd_alert_threshold":    -15.0,  # 고점 대비 낙폭 경보 (%)
    "drift_alert_threshold":   10.0,  # 비중 이탈 경보 (%p)
    "stoploss_threshold":     -25.0,  # 개별 종목 스톱로스 경보 (%)

    # ── 병렬 처리 ────────────────────────────────────────
    "info_workers":      4,        # yfinance.info 동시 요청 수
    "info_retry":        3,
    "info_retry_delay":  5.0,
    "bulk_chunk_size":   150,      # 벌크 가격 다운로드 청크 크기

    # ── 성과 이력 ────────────────────────────────────────
    "perf_history_keep": 24,       # 최대 보존 건수
    "backtest_start":    "2010-01-01",
    "backtest_universe": "sp500",  # 백테스트 유니버스 (sp500/sp1500)
}

# ══════════════════════════════════════════
# 파일 경로
# ══════════════════════════════════════════
PORTFOLIO_FILE       = Path("lt_portfolio_state.json")
LAST_REBAL_FILE      = Path("lt_last_rebal.json")
INFO_CACHE_FILE      = Path("lt_info_cache.json")
PERF_HISTORY_FILE    = Path("lt_performance_history.json")
BACKTEST_RESULT_FILE = Path("lt_backtest_result.json")
UNIVERSE_DIR         = Path("lt_universe_snapshots")

# ══════════════════════════════════════════
# 스레드 안전
# ══════════════════════════════════════════
_scan_lock    = threading.Lock()
_scan_running = False
_sem          = threading.Semaphore(STRATEGY["info_workers"])
_info_cache:  dict[str, dict] = {}
_info_cache_lock = threading.Lock()
_last_rebal_cache: dict = {"quarter": None}


# ══════════════════════════════════════════
# §1. 텔레그램 유틸리티
# ══════════════════════════════════════════
def send_telegram(text: str, topic_id: int | None = None) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS:
        log.warning("텔레그램 설정 없음 — 메시지 스킵")
        return
    effective_topic = topic_id if topic_id is not None else TELEGRAM_TOPIC_ID
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            if effective_topic is not None and _is_supergroup(chat_id):
                payload["message_thread_id"] = effective_topic
            res = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data=payload, timeout=10,
            )
            if res.status_code != 200:
                log.error(f"텔레그램 실패 ({chat_id}): {res.text[:200]}")
        except Exception as e:
            log.error(f"텔레그램 예외 ({chat_id}): {e}")
        time.sleep(0.1)


def send_telegram_chunks(text: str, topic_id: int | None = None) -> None:
    if len(text) <= 4000:
        send_telegram(text, topic_id=topic_id)
        return
    lines, current = text.split("\n"), ""
    for line in lines:
        if len(current) + len(line) + 1 > 3800:
            send_telegram(current.strip(), topic_id=topic_id)
            time.sleep(0.5)
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        send_telegram(current.strip(), topic_id=topic_id)


def _reply_to(chat_id: str, text: str) -> None:
    """명령어 응답 전용 — 요청 채팅방에만 발송"""
    if not TELEGRAM_TOKEN:
        return
    try:
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if TELEGRAM_TOPIC_ID is not None and _is_supergroup(chat_id):
            payload["message_thread_id"] = TELEGRAM_TOPIC_ID
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=payload, timeout=10,
        )
        if res.status_code != 200:
            log.error(f"_reply_to 실패 ({chat_id}): {res.text[:200]}")
    except Exception as e:
        log.error(f"_reply_to 예외: {e}")


def _reply_to_chunks(chat_id: str, text: str) -> None:
    if len(text) <= 4000:
        _reply_to(chat_id, text)
        return
    lines, current = text.split("\n"), ""
    for line in lines:
        if len(current) + len(line) + 1 > 3800:
            _reply_to(chat_id, current.strip())
            time.sleep(0.5)
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        _reply_to(chat_id, current.strip())


# ══════════════════════════════════════════
# §2. 유니버스 빌더 (S&P1500 + NASDAQ100)
# ══════════════════════════════════════════

# ── 나스닥100 폴백 ─────────────────────────────────────────────────
_NDX100_FALLBACK = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","COST",
    "NFLX","AMD","ADBE","QCOM","INTU","AMAT","MU","LRCX","ISRG","KLAC",
    "MRVL","REGN","SNPS","CDNS","PANW","CRWD","MNST","ORLY","FTNT","CTAS",
    "MAR","ABNB","DXCM","CPRT","PAYX","WDAY","FAST","IDXX","VRSK","BIIB",
    "ROST","PCAR","MCHP","ODFL","ANSS","CTSH","DLTR","ZS","TEAM","DDOG",
    "ADI","TXN","EA","TMUS","SBUX","PEP","AMGN","GILD","VRTX","MDLZ",
    "ROP","GEHC","KDP","FANG","CEG","AZN","MELI","PDD","ASML","TTD",
    "ILMN","ENPH","ALGN","ON","TTWO","MRNA","EXC","AEP","XEL","HON",
    "CSX","SIRI","INTC","WBD","LCID","RIVN","ZM","OKTA","SPLK","DOCU",
]

# ── S&P500 폴백 (섹터 균형) ──────────────────────────────────────────
_SP500_FALLBACK = [
    # 금융
    "JPM","BAC","WFC","GS","MS","BLK","C","AXP","USB","PNC",
    "SCHW","COF","TFC","MCO","SPGI","ICE","CME","CB","AON","MMC",
    "PRU","AFL","ALL","TRV","PGR","MET","AJG","WTW","HIG","CNA",
    # 헬스케어
    "JNJ","UNH","CVS","ABT","MRK","PFE","LLY","BMY","MDT","SYK",
    "BSX","EW","ZBH","BDX","BAX","HOLX","PODD","ISRG","VEEV","EXAS",
    "HCA","THC","MOH","CNC","DVA","ANTM","CI","HUM","RCM","ACAD",
    # 에너지
    "XOM","CVX","COP","SLB","EOG","VLO","MPC","PSX","HAL","BKR",
    "DVN","MRO","APA","OXY","HES","CTRA","KMI","WMB","OKE","ET",
    # 필수소비재
    "WMT","PG","KO","PEP","MDLZ","GIS","K","SJM","CPB","HRL",
    "CL","CHD","EL","TGT","KR","COST","SFM","GO","CHEF","ARMK",
    # 임의소비재
    "AMZN","HD","LOW","TJX","NKE","MCD","CMG","YUM","DPZ","SBUX",
    "F","GM","RIVN","ULTA","BBWI","AEO","ANF","DRI","DINE","CHWY",
    # 산업재
    "GE","HON","MMM","CAT","DE","RTX","LMT","NOC","BA","GD",
    "LHX","HII","TDG","HWM","TXT","FDX","UPS","CSX","UNP","NSC",
    "DAL","LUV","UAL","AAL","ALK","CHRW","XPO","ODFL","SAIA","PWR",
    "EMR","ROK","ETN","AME","PH","ITW","IR","DOV","GNRC","CARR","OTIS",
    "JCI","TT","LEN","DHI","PHM","TOL","MDC",
    # IT/테크 (NASDAQ 외)
    "ORCL","IBM","CRM","NOW","SNOW","PLTR","NET","DDOG","ZS","OKTA",
    "FTNT","CYBR","ACN","CTSH","IT","EPAM","ADSK","ANSS","PTC","CDNS",
    "MCHP","SWKS","QRVO","CRUS","GDDY","HUBS","BILL",
    # 통신
    "T","VZ","TMUS","CMCSA","CHTR","LUMN","ATUS","CABO","WOW","DISH",
    # 유틸리티
    "NEE","DUK","SO","D","AEP","EXC","SRE","PCG","ED","XEL",
    "ES","EIX","PPL","CMS","NI","ATO","WEC","DTE","CNP","LNT",
    # 부동산
    "AMT","PLD","CCI","EQIX","SPG","PSA","DLR","AVB","EQR","WY",
    "ARE","BXP","KIM","REG","FRT","NNN","O","STAG","WELL","VTR",
    # 소재
    "LIN","APD","ALB","SHW","ECL","IFF","PPG","NEM","GOLD","FCX",
    "SCCO","AA","NUE","STLD","CMC","RS","ATI","ARNC","OLN","CC",
]

# ── S&P MidCap400 + SmallCap600 폴백 (주요 종목) ─────────────────────
_MIDCAP_FALLBACK = [
    # 금융
    "ZION","MTB","RF","FITB","KEY","HBAN","CFG","NBHC","CVBF","FHN",
    "EG","RLI","KMPR","CINF","SIGI","FG","NWLI","ERIE","PLMR","SKWD",
    # 헬스케어
    "ALGN","INSP","NVCR","AXNX","TMDX","AAON","MMSI","OMCL","LNTH","PRVA",
    "SGRY","ACCD","SDGR","CERT","CLDX","ACRS","NTRA","RCM","MDXG","PNTG",
    # 기술
    "MANH","PCOR","CSGP","GWRE","INST","BRZE","ASAN","APPF","FIVN","JAMF",
    "NCNO","KTOS","LDOS","SAIC","CACI","VRSN","PRFT","EPAM","EXLS","IBEX",
    "TWLO","CFLT","MQ","RGEN","FORM","MKSI","ONTO","AEIS","AMBA","PI",
    # 산업재
    "BWXT","HXL","ROLL","KBAL","WMS","TREX","AZEK","FTDR","BECN","BLDR",
    "IBP","FRTA","BMBL","CIVI","HAE","TKR","CFX","ESAB","HLIO","NPO",
    # 소비재
    "WING","TXRH","CAKE","BJRI","EAT","JACK","SHAK","BROS","LOCO","RRGB",
    "PLAY","CNK","RGP","BOOT","GOOS","LULU","SKX","COLM","CRI","GFF",
    # 에너지/소재
    "MTDR","CTRA","SM","AR","CHK","RRC","CNX","EQT","PDCE","SWN",
    "MP","LTHM","CWEN","AMRC","NOVA","ENPH","ARRY","SPWR","FSLR","SEDG",
    # 부동산
    "TRNO","ELS","SUI","UDR","CPT","INVH","AMH","AIRC","IRT","NHI",
    "OHI","SBRA","CTRE","MPW","LTC","PEAK","HR","DOC","EPRT","NTST",
]

_SMALLCAP_FALLBACK = [
    # 기술
    "RIOT","MARA","HUT","CLSK","CIFR","BRPH","BTBT","WULF","IREN","BTDR",
    "ACMR","AEHR","CEVA","COHU","DIOD","ENTG","ICHR","KLIC","MTSI","NXST",
    "RMBS","SIGI","SMTC","UCTT","VLTO","WOLF","XPEL","YELP","ZI","ZETA",
    # 헬스케어
    "ACAD","ARDX","ARQT","ATEA","ATRC","AURA","AVDL","AVXL","AXGN","BCAB",
    "CCCC","CMRX","COGT","CRSP","CSTL","CYRX","DMRC","DNLI","DXCM","ELAN",
    # 금융
    "AROW","BSVN","BYFC","CALB","CBTX","CENTA","CFBK","CFFI","CHCO","CHMG",
    "CLBK","CLFD","CLFD","CNNB","CNXN","COLB","COMM","CONL","COOP","CORS",
    # 산업재/소비재
    "ACHR","ACMR","AIRS","ALEC","ALGT","ALKT","ALRM","ALRS","ALSA","ALTO",
    "AMAL","AMBC","AMCX","AMEH","AMER","AMKR","AMMO","AMNB","AMOT","AMRK",
    "AMRN","AMSC","AMTB","AMTX","AMWD","AMZG","ANAB","ANDE","ANDV","ANDX",
    "ANET","ANGI","ANIP","ANIX","ANNX","ANSS","ANTE","ANTM","AOSL","APA",
]


def _fetch_wikipedia_tickers(url: str, table_id: str, symbol_col: str, min_count: int = 50) -> list[str]:
    """위키피디아 테이블에서 티커 파싱"""
    try:
        tables = pd.read_html(url, attrs={"id": table_id})
        for t in tables:
            for col in [symbol_col, "Symbol", "Ticker", "Ticker symbol"]:
                if col in t.columns:
                    tks = [str(s).replace(".", "-") for s in t[col].dropna()
                           if 1 <= len(str(s)) <= 6 and str(s) != "nan"]
                    if len(tks) >= min_count:
                        log.info(f"  위키 파싱 성공 ({url[-30:]}): {len(tks)}개")
                        return tks
    except Exception as e:
        log.debug(f"  위키 파싱 실패 ({url[-30:]}): {e}")
    return []


def get_universe_tickers(extended: bool = True) -> list[str]:
    """
    미국주식 장기투자 유니버스 수집.
    S&P500 + NASDAQ100 + S&P MidCap400 + S&P SmallCap600 ≈ 1,500종목

    우선순위:
      1순위: yfinance ETF 보유종목 (SPY, QQQ, MDY/IJR)
      2순위: 위키피디아 파싱
      3순위: 하드코딩 폴백
    """
    log.info("유니버스 수집 시작...")

    # ── NASDAQ100 ────────────────────────────────────────────────────
    ndx = []
    try:
        qqq_data = yf.Ticker("QQQ").funds_data
        if qqq_data and hasattr(qqq_data, "top_holdings"):
            h = qqq_data.top_holdings
            if h is not None and len(h) >= 50:
                ndx = [str(t).replace(".", "-") for t in h.index.tolist()]
                log.info(f"  QQQ ETF 보유종목: {len(ndx)}개")
    except Exception:
        pass

    if not ndx:
        ndx = _fetch_wikipedia_tickers(
            "https://en.wikipedia.org/wiki/Nasdaq-100",
            "constituents", "Ticker", 80
        )
    if not ndx:
        ndx = _NDX100_FALLBACK
        log.info(f"  나스닥100 폴백: {len(ndx)}개")

    # ── S&P500 ───────────────────────────────────────────────────────
    sp500 = []
    try:
        spy_data = yf.Ticker("SPY").funds_data
        if spy_data and hasattr(spy_data, "top_holdings"):
            h = spy_data.top_holdings
            if h is not None and len(h) >= 200:
                sp500 = [str(t).replace(".", "-") for t in h.index.tolist()]
                log.info(f"  SPY ETF 보유종목: {len(sp500)}개")
    except Exception:
        pass

    if not sp500:
        sp500 = _fetch_wikipedia_tickers(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            "constituents", "Symbol", 400
        )
    if not sp500:
        sp500 = _SP500_FALLBACK
        log.info(f"  S&P500 폴백: {len(sp500)}개")

    if not extended:
        combined = list(dict.fromkeys(ndx + sp500))
        log.info(f"유니버스 (기본): {len(combined)}개")
        return combined

    # ── S&P MidCap400 ────────────────────────────────────────────────
    mid400 = _fetch_wikipedia_tickers(
        "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
        "constituents", "Ticker", 300
    )
    if not mid400:
        mid400 = _MIDCAP_FALLBACK
        log.info(f"  MidCap400 폴백: {len(mid400)}개")

    # ── S&P SmallCap600 ──────────────────────────────────────────────
    small600 = _fetch_wikipedia_tickers(
        "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
        "constituents", "Ticker", 400
    )
    if not small600:
        small600 = _SMALLCAP_FALLBACK
        log.info(f"  SmallCap600 폴백: {len(small600)}개")

    combined = list(dict.fromkeys(ndx + sp500 + mid400 + small600))
    log.info(f"유니버스 (확장): NASDAQ100({len(ndx)}) + S&P500({len(sp500)}) "
             f"+ MidCap400({len(mid400)}) + SmallCap600({len(small600)}) "
             f"→ 통합 {len(combined)}개")
    return combined


# ══════════════════════════════════════════
# §3. 데이터 레이어 (가격 + 재무)
# ══════════════════════════════════════════
_INFO_CACHE_MAX_AGE_HOURS = 72

def _load_info_cache() -> None:
    global _info_cache
    if not INFO_CACHE_FILE.exists():
        return
    try:
        data = json.loads(INFO_CACHE_FILE.read_text(encoding="utf-8"))
        now = datetime.now(KST)
        now_quarter = f"{now.year}-Q{(now.month - 1)//3 + 1}"
        if data.get("quarter") != now_quarter:
            log.info("재무 캐시 폐기 — 분기 불일치")
            return
        saved_at_str = data.get("saved_at")
        if saved_at_str:
            saved_at = datetime.fromisoformat(saved_at_str)
            age_h = (now.replace(tzinfo=None) - saved_at.replace(tzinfo=None)).total_seconds() / 3600
            if age_h > _INFO_CACHE_MAX_AGE_HOURS:
                log.info(f"재무 캐시 폐기 — {age_h:.1f}h 경과")
                return
        raw = data.get("cache", {})
        _info_cache = {t: v for t, v in raw.items() if v}
        log.info(f"재무 캐시 복원: {len(_info_cache)}개")
    except Exception as e:
        log.warning(f"재무 캐시 로드 실패: {e}")


def _save_info_cache() -> None:
    now = datetime.now(KST)
    quarter = f"{now.year}-Q{(now.month - 1)//3 + 1}"
    with _info_cache_lock:
        INFO_CACHE_FILE.write_text(
            json.dumps(
                {"quarter": quarter, "saved_at": now.isoformat(), "cache": _info_cache},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def _fetch_info_with_retry(ticker: str) -> dict:
    """yfinance.info 재시도 로직 (지수 백오프)"""
    for attempt in range(STRATEGY["info_retry"]):
        try:
            with _sem:
                info = yf.Ticker(ticker).info
                time.sleep(0.2)
            return info if info else {}
        except Exception as e:
            if attempt < STRATEGY["info_retry"] - 1:
                delay = STRATEGY["info_retry_delay"] * (2 ** attempt)
                log.debug(f"  재무 재시도 {ticker} ({attempt+1}/{STRATEGY['info_retry']}): {e}")
                time.sleep(delay)
    return {}


def get_ticker_info(ticker: str) -> dict:
    """yfinance 재무 데이터 (분기 캐시 우선)"""
    with _info_cache_lock:
        if ticker in _info_cache:
            return _info_cache[ticker]
    info = _fetch_info_with_retry(ticker)
    with _info_cache_lock:
        _info_cache[ticker] = info
    return info


def download_prices_bulk(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """
    벌크 가격 다운로드 (yfinance 단일 세션 — 401 우회).
    청크 단위로 분할 다운로드, 실패 시 개별 재시도.
    """
    chunk_size = STRATEGY["bulk_chunk_size"]
    all_data: dict[str, pd.DataFrame] = {}

    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            raw = yf.download(
                chunk, period=period, auto_adjust=True,
                group_by="ticker", progress=False, threads=True,
            )
            if raw.empty:
                continue
            # 멀티인덱스 언팩
            if isinstance(raw.columns, pd.MultiIndex):
                for tk in chunk:
                    if tk in raw.columns.get_level_values(0):
                        df = raw[tk].dropna(how="all")
                        if not df.empty:
                            all_data[tk] = df
            else:
                # 단일 종목
                if len(chunk) == 1 and not raw.empty:
                    all_data[chunk[0]] = raw.dropna(how="all")
        except Exception as e:
            log.warning(f"벌크 다운로드 실패 (청크 {i//chunk_size+1}): {e} — 개별 재시도")
            for tk in chunk:
                try:
                    df = yf.download(tk, period=period, auto_adjust=True,
                                     progress=False, threads=False)
                    if not df.empty:
                        all_data[tk] = df
                    time.sleep(0.3)
                except Exception:
                    pass
        time.sleep(0.5)

    log.info(f"가격 다운로드 완료: {len(all_data)}/{len(tickers)}개")
    return all_data


def get_vix() -> float:
    """VIX 지수 현재값 조회"""
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False, auto_adjust=True)
        if not vix_data.empty:
            return float(vix_data["Close"].iloc[-1])
    except Exception:
        pass
    return 20.0  # 기본값


# ══════════════════════════════════════════
# §4. QM 팩터 스코어링
# ══════════════════════════════════════════
_FINANCIAL_SECTORS = {"Financial Services", "Financials", "Real Estate", "Banks", "Insurance"}


def _score_roe(roe: float) -> float:
    """ROE 점수 (0~15점)"""
    if roe >= 40: return 15.0
    if roe >= 30: return 12.0
    if roe >= 20: return  8.0
    if roe >= 10: return  4.0
    if roe >=  0: return  1.0
    return 0.0


def _score_margin(margin: float) -> float:
    """순이익률 점수 (0~10점)"""
    if margin >= 30: return 10.0
    if margin >= 20: return  7.5
    if margin >= 12: return  5.0
    if margin >=  5: return  2.5
    if margin >=  0: return  1.0
    return 0.0


def _score_rev_growth(growth_pct: float) -> float:
    """매출성장률 점수 (0~10점). growth_pct는 % 단위"""
    if growth_pct >= 30: return 10.0
    if growth_pct >= 20: return  7.5
    if growth_pct >= 10: return  5.0
    if growth_pct >=  5: return  3.0
    if growth_pct >=  0: return  1.0
    return 0.0   # 역성장


def _score_fcf_margin(fcf_margin_pct: float) -> float:
    """FCF 마진 점수 (0~10점). fcf_margin_pct는 % 단위"""
    if fcf_margin_pct >= 25: return 10.0
    if fcf_margin_pct >= 15: return  7.5
    if fcf_margin_pct >=  8: return  5.0
    if fcf_margin_pct >=  3: return  2.5
    if fcf_margin_pct >=  0: return  0.5
    return 0.0   # FCF 적자


def _score_debt_safety(de_ratio: float) -> float:
    """부채 안전성 점수 (0~5점). D/E 낮을수록 유리"""
    if de_ratio <=  30: return 5.0
    if de_ratio <=  60: return 4.0
    if de_ratio <= 100: return 3.0
    if de_ratio <= 150: return 2.0
    if de_ratio <= 200: return 1.0
    return 0.0


def _score_quality(info: dict) -> float:
    """Quality 팩터 점수 (0~50점)"""
    roe       = float(info.get("returnOnEquity",  0) or 0) * 100
    margin    = float(info.get("profitMargins",   0) or 0) * 100
    rev_g     = float(info.get("revenueGrowth",   0) or 0) * 100
    total_rev = float(info.get("totalRevenue",    0) or 0)
    free_cf   = float(info.get("freeCashflow",    0) or 0)
    de_ratio  = float(info.get("debtToEquity",    0) or 0)
    fcf_m     = (free_cf / total_rev * 100) if total_rev > 0 else 0.0

    return (
        _score_roe(roe)
        + _score_margin(margin)
        + _score_rev_growth(rev_g)
        + _score_fcf_margin(fcf_m)
        + _score_debt_safety(de_ratio)
    )


def _analyze_single(
    ticker: str,
    price_df: pd.DataFrame,
    info: dict | None = None,
) -> dict | None:
    """
    단일 종목 분석 — QM 기본 점수 계산.
    Momentum/Value 퍼센타일 점수는 전체 후보군 집계 후 별도 계산.
    """
    try:
        if price_df is None or price_df.empty or len(price_df) < 60:
            return None

        # 거래정지 필터
        last_date = price_df.index[-1]
        if (datetime.now(KST).date() - last_date.date()).days > STRATEGY["max_stale_days"]:
            return None

        close = float(price_df["Close"].iloc[-1])
        if close <= STRATEGY["min_price"]:
            return None

        # 이동평균
        prices = price_df["Close"].ffill()
        ma200  = prices.rolling(200, min_periods=150).mean().iloc[-1]
        if STRATEGY["use_ma200"] and (pd.isna(ma200) or close < float(ma200)):
            return None

        # 가격 모멘텀 (raw — 퍼센타일은 나중에)
        p6m  = float(prices.iloc[-126]) if len(prices) >= 126 else float(prices.iloc[0])
        p12m = float(prices.iloc[-252]) if len(prices) >= 252 else float(prices.iloc[0])
        ret_6m  = (close / p6m  - 1) * 100
        ret_12m = (close / p12m - 1) * 100

        # 52주 위치
        w52 = price_df.iloc[-252:] if len(price_df) >= 252 else price_df
        high_52 = float(w52["High"].max()) if "High" in w52.columns else close * 1.2
        low_52  = float(w52["Low"].min())  if "Low"  in w52.columns else close * 0.8
        w52_pos = ((close - low_52) / (high_52 - low_52)) if high_52 > low_52 else 0.5

        # 재무
        if info is None:
            info = get_ticker_info(ticker)

        sector   = str(info.get("sector", "") or "Unknown")
        mktcap   = float(info.get("marketCap", 0) or 0)
        avg_vol  = float(info.get("averageVolume", 0) or 0)
        de_ratio = float(info.get("debtToEquity", 0) or 0)
        name     = str(info.get("shortName", "") or ticker)
        pe       = float(info.get("trailingPE", 0) or 0)
        pb       = float(info.get("priceToBook", 0) or 0)
        ev_ebitda = float(info.get("enterpriseToEbitda", 0) or 0)
        total_rev = float(info.get("totalRevenue", 0) or 0)
        free_cf   = float(info.get("freeCashflow", 0) or 0)
        # P/FCF: 시가총액 / FCF (양수일 때만 유효)
        p_fcf = (mktcap / free_cf) if (free_cf > 0 and mktcap > 0) else 0.0

        # 유동성 필터
        if mktcap < STRATEGY["min_market_cap"]:
            return None
        if avg_vol > 0 and avg_vol < STRATEGY["min_avg_volume"]:
            return None

        # D/E 필터 (비금융 섹터)
        if sector not in _FINANCIAL_SECTORS and de_ratio > STRATEGY["de_ratio_max"]:
            return None

        # 재무 신선도
        data_stale = False
        mrq_ts = info.get("mostRecentQuarter", 0) or 0
        fin_dt_str = ""
        if mrq_ts > 0:
            try:
                fin_dt = datetime.fromtimestamp(float(mrq_ts))
                age_d  = (datetime.now() - fin_dt).days
                if age_d > STRATEGY["fin_stale_skip_days"]:
                    return None
                data_stale = age_d > STRATEGY["fin_stale_warn_days"]
                fin_dt_str = fin_dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        # Quality 점수
        q_score = _score_quality(info)
        fcf_margin_pct = (free_cf / total_rev * 100) if total_rev > 0 else 0.0
        roe   = float(info.get("returnOnEquity",  0) or 0) * 100
        mgn   = float(info.get("profitMargins",   0) or 0) * 100
        rev_g = float(info.get("revenueGrowth",   0) or 0) * 100

        return {
            "ticker":        ticker,
            "name":          name,
            "sector":        sector,
            "close":         round(close, 2),
            "mktcap_b":      round(mktcap / 1e9, 2),
            "pe":            round(pe, 1),
            "pb":            round(pb, 2),
            "ev_ebitda":     round(ev_ebitda, 1),
            "p_fcf":         round(p_fcf, 1),
            "roe":           round(roe, 1),
            "margin":        round(mgn, 1),
            "rev_growth":    round(rev_g, 1),
            "fcf_margin":    round(fcf_margin_pct, 1),
            "de_ratio":      round(de_ratio, 1),
            "w52_pos":       round(w52_pos * 100, 1),
            "ret_6m":        round(ret_6m, 2),
            "ret_12m":       round(ret_12m, 2),
            "q_score":       round(q_score, 1),      # Quality (0~50)
            # momentum/value 퍼센타일 점수는 집계 후 추가
            "m_score":       0.0,
            "v_score":       0.0,
            "total_score":   0.0,
            "data_stale":    data_stale,
            "fin_report_dt": fin_dt_str,
        }
    except Exception as e:
        log.debug(f"[SKIP] {ticker}: {e}")
        return None


def _apply_percentile_scores(candidates: list[dict]) -> list[dict]:
    """
    Momentum + Value 퍼센타일 점수 계산 (전체 후보군 기준).
    Momentum(30): 12M퍼센타일(20) + 6M퍼센타일(10)
    Value(20):    P/FCF 역퍼센타일(10) + EV/EBITDA 역퍼센타일(10)
    """
    if not candidates:
        return candidates

    ret12m_list  = [c["ret_12m"]  for c in candidates]
    ret6m_list   = [c["ret_6m"]   for c in candidates]
    pfcf_list    = [c["p_fcf"]    if c["p_fcf"] > 0 else 999 for c in candidates]
    evebitda_list = [c["ev_ebitda"] if c["ev_ebitda"] > 0 else 999 for c in candidates]

    n = len(candidates)

    def percentile_rank(val, arr):
        return sum(1 for x in arr if x <= val) / n

    def inv_percentile_rank(val, arr):
        return 1 - percentile_rank(val, arr)

    for i, c in enumerate(candidates):
        # Momentum (30점)
        m12 = percentile_rank(ret12m_list[i], ret12m_list) * 20
        m6  = percentile_rank(ret6m_list[i],  ret6m_list)  * 10
        m_score = round(m12 + m6, 1)

        # Value (20점) — P/FCF와 EV/EBITDA 역퍼센타일 (낮을수록 유리)
        v_pfcf   = inv_percentile_rank(pfcf_list[i],    pfcf_list)    * 10
        v_evebitda = inv_percentile_rank(evebitda_list[i], evebitda_list) * 10
        # 두 밸류 지표 모두 0(유효값 없음)이면 점수 절반만 반영
        if pfcf_list[i] == 999 and evebitda_list[i] == 999:
            v_score = 0.0
        elif pfcf_list[i] == 999:
            v_score = round(v_evebitda * 2, 1)  # 한 쪽만 있으면 2배로 환산
        elif evebitda_list[i] == 999:
            v_score = round(v_pfcf * 2, 1)
        else:
            v_score = round(v_pfcf + v_evebitda, 1)

        c["m_score"]     = m_score
        c["v_score"]     = v_score
        c["total_score"] = round(c["q_score"] + m_score + v_score, 1)

    candidates.sort(key=lambda x: x["total_score"], reverse=True)
    return candidates


def apply_sector_cap(candidates: list[dict], max_per_sector: int) -> list[dict]:
    """동일 섹터 최대 N종목 제한 (Unknown 면제)"""
    result, counts = [], {}
    for c in candidates:
        s = c["sector"]
        if s == "Unknown" or counts.get(s, 0) < max_per_sector:
            result.append(c)
            counts[s] = counts.get(s, 0) + 1
    return result


def calc_weights(scores: list[float], target_sum: float) -> list[float]:
    """점수 비례 가중치 계산"""
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


# ══════════════════════════════════════════
# §5. 포트폴리오 구성
# ══════════════════════════════════════════
def _do_quarterly_scan() -> dict | None:
    """
    분기 리밸런싱 — 전체 유니버스 스캔 + QM 스코어링 + 포트폴리오 선정.
    반환: 포트폴리오 dict (저장용)
    """
    now_kst = datetime.now(KST)
    log.info(f"═══ 분기 리밸런싱 시작: {now_kst.strftime('%Y-%m-%d %H:%M')} ═══")

    send_telegram(
        f"🔍 *QM전략 분기 리밸런싱 시작*\n"
        f"📅 {now_kst.strftime('%Y년 %m월 %d일')} | S\\&P1500 + NASDAQ100 유니버스\n"
        f"⏳ 스캔 중... (약 15~30분 소요)"
    )

    # Step 1: 유니버스 수집
    tickers = get_universe_tickers(extended=True)
    send_telegram(f"✅ *Step 1/4 완료* — 유니버스: {len(tickers)}개 종목")

    # Step 2: 가격 데이터 벌크 다운로드 (2년치)
    log.info("Step 2: 가격 데이터 다운로드...")
    price_data = download_prices_bulk(tickers, period="2y")
    send_telegram(f"✅ *Step 2/4 완료* — 가격 조회: {len(price_data)}개")

    # Step 3: 재무 데이터 병렬 조회
    log.info("Step 3: 재무 데이터 조회...")
    _load_info_cache()
    cached = set(_info_cache.keys())
    to_fetch = [t for t in tickers if t not in cached]
    log.info(f"  캐시 히트: {len(cached)}개 / 신규 조회: {len(to_fetch)}개")

    if to_fetch:
        with ThreadPoolExecutor(max_workers=STRATEGY["info_workers"]) as ex:
            futures = {ex.submit(_fetch_info_with_retry, t): t for t in to_fetch}
            done = 0
            for fut in as_completed(futures):
                tk = futures[fut]
                try:
                    info = fut.result()
                    with _info_cache_lock:
                        _info_cache[tk] = info
                except Exception:
                    pass
                done += 1
                if done % 200 == 0:
                    log.info(f"  재무 조회 진행: {done}/{len(to_fetch)}")
        _save_info_cache()

    send_telegram(f"✅ *Step 3/4 완료* — 재무 조회: {len(_info_cache)}개")

    # Step 4: 종목 분석 + QM 스코어링
    log.info("Step 4: 종목 분석 및 스코어링...")
    candidates = []
    for tk in tickers:
        pdf = price_data.get(tk)
        info = _info_cache.get(tk)
        result = _analyze_single(tk, pdf, info)
        if result:
            candidates.append(result)

    log.info(f"  필터 통과: {len(candidates)}개")

    if not candidates:
        log.error("스코어링 후 후보 없음 — 리밸런싱 취소")
        send_telegram("⚠️ 리밸런싱 실패: 조건 통과 종목 없음")
        return None

    # 퍼센타일 점수 적용 (Momentum + Value)
    candidates = _apply_percentile_scores(candidates)

    # 섹터 다양성 제한 적용
    top_pool = candidates[:STRATEGY["portfolio_size"] * 5]  # 상위 풀에서 섹터 캡 적용
    top_pool = apply_sector_cap(top_pool, STRATEGY["sector_max"])
    selected = top_pool[:STRATEGY["portfolio_size"]]

    # VIX 레짐 확인
    vix = get_vix()
    cash_pct = STRATEGY["safe_asset_weight"]
    regime_label = "정상"
    if vix >= STRATEGY["vix_fear"]:
        cash_pct = min(cash_pct + 30, STRATEGY["vix_cash_cap"])
        regime_label = f"공포 (VIX={vix:.1f})"
    elif vix >= STRATEGY["vix_caution"]:
        cash_pct = min(cash_pct + 20, STRATEGY["vix_cash_cap"])
        regime_label = f"주의 (VIX={vix:.1f})"
    else:
        regime_label = f"정상 (VIX={vix:.1f})"

    stock_pct = round(100.0 - cash_pct, 1)
    weights   = calc_weights([c["total_score"] for c in selected], stock_pct)

    # 포트폴리오 딕셔너리 구성
    portfolio_entries = []
    for c, w in zip(selected, weights):
        portfolio_entries.append({
            "ticker":        c["ticker"],
            "name":          c["name"],
            "sector":        c["sector"],
            "entry_price":   c["close"],
            "weight":        w,
            "total_score":   c["total_score"],
            "q_score":       c["q_score"],
            "m_score":       c["m_score"],
            "v_score":       c["v_score"],
            "roe":           c["roe"],
            "margin":        c["margin"],
            "rev_growth":    c["rev_growth"],
            "fcf_margin":    c["fcf_margin"],
            "de_ratio":      c["de_ratio"],
            "ret_6m":        c["ret_6m"],
            "ret_12m":       c["ret_12m"],
            "pe":            c["pe"],
            "ev_ebitda":     c["ev_ebitda"],
            "p_fcf":         c["p_fcf"],
            "data_stale":    c["data_stale"],
            "fin_report_dt": c["fin_report_dt"],
        })

    portfolio = {
        "rebal_date":  now_kst.strftime("%Y-%m-%d"),
        "rebal_quarter": f"{now_kst.year}-Q{(now_kst.month - 1)//3 + 1}",
        "cash_pct":    round(cash_pct, 1),
        "stock_pct":   stock_pct,
        "vix":         round(vix, 1),
        "regime":      regime_label,
        "universe_count": len(tickers),
        "filtered_count": len(candidates),
        "holdings":    portfolio_entries,
        "max_equity":  0.0,
        "last_stoploss_alerts": {},
        "last_drift_alert_date": "",
    }

    save_portfolio(portfolio)
    _save_last_rebal(portfolio["rebal_quarter"])

    # 리밸런싱 브리핑 발송
    _send_rebal_brief(portfolio, candidates[:5])

    log.info(f"═══ 분기 리밸런싱 완료 ═══")
    return portfolio


def _send_rebal_brief(portfolio: dict, top_candidates: list[dict]) -> None:
    """리밸런싱 결과 텔레그램 브리핑"""
    now = datetime.now(KST)
    holdings = portfolio["holdings"]

    lines = [
        f"🎯 *QM전략 분기 리밸런싱 완료*",
        f"📅 {now.strftime('%Y년 %m월 %d일')} ({portfolio['rebal_quarter']})",
        f"",
        f"🌡 시장 레짐: {portfolio['regime']}",
        f"💰 자산 배분: 주식 {portfolio['stock_pct']}% / 현금 {portfolio['cash_pct']}%",
        f"",
        f"📊 *선정 포트폴리오 ({len(holdings)}종목)*",
    ]

    for h in holdings:
        stale = " ⚠️" if h.get("data_stale") else ""
        lines.append(
            f"  {h['ticker']} ({h['sector'][:10]}) "
            f"{h['weight']}% | 총점 {h['total_score']:.0f} "
            f"[Q:{h['q_score']:.0f} M:{h['m_score']:.0f} V:{h['v_score']:.0f}]{stale}"
        )

    lines += [
        f"",
        f"📈 *섹터 구성*",
    ]
    sector_cnt: dict[str, int] = {}
    for h in holdings:
        s = h["sector"]
        sector_cnt[s] = sector_cnt.get(s, 0) + 1
    for s, cnt in sorted(sector_cnt.items(), key=lambda x: -x[1]):
        lines.append(f"  {s}: {cnt}종목")

    lines += [
        f"",
        f"🔍 *스코어 상위 5종목 상세*",
    ]
    for c in top_candidates[:5]:
        lines.append(
            f"  *{c['ticker']}* | ROE:{c['roe']:.0f}% 마진:{c['margin']:.0f}% "
            f"성장:{c['rev_growth']:.0f}% FCF:{c['fcf_margin']:.0f}%"
        )
        lines.append(
            f"    12M:{c['ret_12m']:+.1f}% 6M:{c['ret_6m']:+.1f}% "
            f"P/FCF:{c['p_fcf']:.0f}x EV/EBITDA:{c['ev_ebitda']:.0f}x"
        )

    stale_cnt = sum(1 for h in holdings if h.get("data_stale"))
    if stale_cnt:
        lines.append(f"\n⚠️ 재무 구식 데이터: {stale_cnt}개 종목")

    lines += [
        f"",
        f"⚠️ *편향 경고*",
        f"  · 생존자 편향: 현 S\\&P1500 기준 유니버스",
        f"  · 재무 미래참조: yfinance.info 현재값 사용",
        f"  · 매매 체크리스트는 실제 실행 전 반드시 확인",
    ]

    send_telegram_chunks("\n".join(lines))

    # 매매 체크리스트
    _send_trade_checklist(portfolio)


def _send_trade_checklist(portfolio: dict) -> None:
    """매매 실행 체크리스트 발송"""
    old_portfolio = load_portfolio()
    holdings = portfolio["holdings"]

    new_tickers = {h["ticker"] for h in holdings}
    old_tickers = set()
    if old_portfolio:
        old_tickers = {h["ticker"] for h in old_portfolio.get("holdings", [])}

    sells    = sorted(old_tickers - new_tickers)
    buys     = sorted(new_tickers - old_tickers)
    holds    = sorted(new_tickers & old_tickers)

    if not sells and not buys:
        send_telegram("📋 *매매 체크리스트*\n변경 없음 (동일 포트폴리오 유지)")
        return

    lines = ["📋 *매매 실행 체크리스트*", ""]
    if sells:
        lines.append("🔴 *전량 매도*")
        for t in sells:
            lines.append(f"  [ ] {t} 전량 매도")
    if buys:
        lines.append("\n🟢 *신규 매수*")
        for h in holdings:
            if h["ticker"] in buys:
                lines.append(f"  [ ] {h['ticker']} {h['weight']}% 매수")
    if holds:
        lines.append("\n🔵 *비중 유지/조정*")
        for h in holdings:
            if h["ticker"] in holds:
                lines.append(f"  [ ] {h['ticker']} → {h['weight']}% 조정 확인")

    lines += [
        "",
        "📌 순서: 매도 → 비중 축소 → 비중 확대 → 신규 매수",
        "📌 실행 시점: 미국 정규장 (ET 09:30~16:00)",
    ]
    send_telegram_chunks("\n".join(lines))


# ══════════════════════════════════════════
# §6. 백테스터 (워크포워드)
# ══════════════════════════════════════════
def _get_quarter_dates(start: str, end: str) -> list[str]:
    """분기 시작일 목록 반환 (YYYY-MM-DD 형식)"""
    quarters = []
    d = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    while d <= end_ts:
        quarters.append(d.strftime("%Y-%m-%d"))
        # 다음 분기
        month = d.month + 3
        year  = d.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        d = pd.Timestamp(f"{year}-{month:02d}-01")
    return quarters


def _get_next_trading_day(prices_df: pd.DataFrame, target_date: str) -> str | None:
    """target_date 이후 첫 거래일 반환"""
    target_ts = pd.Timestamp(target_date)
    valid_dates = [d for d in prices_df.index if d >= target_ts]
    return valid_dates[0].strftime("%Y-%m-%d") if valid_dates else None


def run_backtest(
    send_progress: bool = True,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """
    워크포워드 백테스트 실행.

    [방법론]
      - 유니버스: S&P500 (속도 최적화)
      - 가격 팩터 (Momentum, 52W): 완전 point-in-time — 편향 없음
      - 재무 팩터 (Quality, Value): yfinance.info 현재값 프록시
                                    ⚠️ 미래참조 편향 존재
      - 리밸런싱: 분기 1회
      - 벤치마크: SPY (S&P500 ETF)

    [반환] 성과 지표 dict
    """
    start_date = start or STRATEGY["backtest_start"]
    end_date   = end   or datetime.now().strftime("%Y-%m-%d")

    if send_progress:
        log.info("═══ 백테스트 시작 ═══")
        log.info(f"  기간: {start_date} ~ {end_date}")
        log.info(f"  전략: QM전략 (Quality50 + Momentum30 + Value20)")

    # ── Step 1: 유니버스 수집 ────────────────────────────────────────
    log.info("[BT] Step 1: 유니버스 수집...")
    tickers = get_universe_tickers(extended=False)  # S&P500 + NASDAQ100
    log.info(f"  유니버스: {len(tickers)}개")

    # ── Step 2: 가격 데이터 다운로드 (전체 기간) ─────────────────────
    log.info(f"[BT] Step 2: 가격 데이터 다운로드 ({start_date} ~ {end_date})...")
    log.info("  (이 단계는 5~15분 소요될 수 있습니다)")

    # SPY 벤치마크 포함
    all_tickers = list(set(tickers + ["SPY", "QQQ"]))
    price_start = (pd.Timestamp(start_date) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")

    chunk_size = STRATEGY["bulk_chunk_size"]
    all_prices: dict[str, pd.DataFrame] = {}

    for i in range(0, len(all_tickers), chunk_size):
        chunk = all_tickers[i:i + chunk_size]
        try:
            raw = yf.download(
                chunk, start=price_start, end=end_date,
                auto_adjust=True, group_by="ticker",
                progress=False, threads=True,
            )
            if raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                for tk in chunk:
                    if tk in raw.columns.get_level_values(0):
                        df = raw[tk].dropna(how="all")
                        if not df.empty and len(df) > 60:
                            all_prices[tk] = df
            else:
                if len(chunk) == 1 and not raw.empty:
                    all_prices[chunk[0]] = raw.dropna(how="all")
        except Exception as e:
            log.warning(f"  청크 {i//chunk_size+1} 실패: {e}")
        time.sleep(0.5)
        if (i // chunk_size + 1) % 5 == 0:
            log.info(f"  가격 다운로드: {len(all_prices)}개 완료...")

    log.info(f"  가격 데이터: {len(all_prices)}개 (/{len(all_tickers)}개)")

    # ── Step 3: 재무 데이터 조회 (현재값 프록시) ─────────────────────
    log.info("[BT] Step 3: 재무 데이터 조회...")
    log.info("  ⚠️  재무 데이터는 현재값(yfinance.info) 사용 — 미래참조 편향 존재")

    _load_info_cache()
    cached = set(_info_cache.keys())
    to_fetch = [t for t in tickers if t not in cached and t in all_prices]

    if to_fetch:
        with ThreadPoolExecutor(max_workers=STRATEGY["info_workers"]) as ex:
            futures = {ex.submit(_fetch_info_with_retry, t): t for t in to_fetch}
            done = 0
            for fut in as_completed(futures):
                tk = futures[fut]
                try:
                    info = fut.result()
                    with _info_cache_lock:
                        _info_cache[tk] = info
                except Exception:
                    pass
                done += 1
                if done % 100 == 0:
                    log.info(f"  재무 조회: {done}/{len(to_fetch)}")
        _save_info_cache()

    log.info(f"  재무 데이터: {len(_info_cache)}개")

    # ── Step 4: 워크포워드 시뮬레이션 ───────────────────────────────
    # [올바른 구조]
    # 각 quarter_date[i]는 분기 경계선 (=진입/청산 시점)
    # 루프 qi번째에서:
    #   - 이전 분기에 구성한 포트폴리오를 q_dates[qi] 가격에 청산
    #   - q_dates[qi] 이전 데이터로 새 포트폴리오 선정
    #   - q_dates[qi] 가격으로 신규 진입
    # → 진입/청산이 같은 경계 시점 → 1분기 수익률이 정확히 계산됨
    log.info("[BT] Step 4: 워크포워드 시뮬레이션...")
    quarter_dates = _get_quarter_dates(start_date, end_date)
    log.info(f"  분기 경계: {quarter_dates[0]} ~ {quarter_dates[-1]} ({len(quarter_dates)}개)")

    portfolio_value = 10000.0
    spy_value       = 10000.0
    qqq_value       = 10000.0

    value_history   = []
    quarterly_rets  = []
    spy_rets        = []
    qqq_rets        = []
    quarter_details = []

    # 이전 분기에 구성된 포트폴리오 (ticker, weight, entry_price)
    active_portfolio: list[dict] = []
    # 각 벤치마크의 이전 분기 경계 가격
    spy_prev_price: float | None = None
    qqq_prev_price: float | None = None

    def _first_price_at(df: pd.DataFrame, ts: pd.Timestamp) -> float | None:
        """ts 이후 첫 번째 거래일 종가"""
        sub = df[df.index >= ts]
        return float(sub["Close"].iloc[0]) if not sub.empty else None

    total_quarters = len(quarter_dates)

    for qi, q_ts_str in enumerate(quarter_dates):
        q_ts = pd.Timestamp(q_ts_str)
        is_last = (qi == total_quarters - 1)

        # ── 청산: 이전 포트폴리오를 q_ts 가격으로 청산 (qi≥1) ──────────
        if active_portfolio and qi > 0:
            port_ret    = 0.0
            valid_w_sum = 0.0
            for pos in active_portfolio:
                tk = pos["ticker"]
                if tk not in all_prices:
                    continue
                exit_p = _first_price_at(all_prices[tk], q_ts)
                if exit_p is None or pos["entry_price"] <= 0:
                    continue
                # 1분기 수익률 (주식 비중만, 현금은 0% 수익)
                stock_w = pos["weight"]  # 이미 stock_pct 내의 비중
                port_ret    += (exit_p / pos["entry_price"] - 1) * stock_w / 100
                valid_w_sum += stock_w

            # 유효 비중으로 정규화 (일부 종목 데이터 없을 경우)
            if valid_w_sum > 0 and valid_w_sum < 95:
                port_ret = port_ret * (100.0 / valid_w_sum)

            portfolio_value *= (1 + port_ret)
            quarterly_rets.append(port_ret)
            value_history.append({
                "date":            q_ts_str[:7],
                "portfolio_value": round(portfolio_value, 2),
                "quarter_ret_pct": round(port_ret * 100, 2),
            })
            log.debug(f"  [{q_ts_str[:7]}] 포트폴리오 분기 수익: {port_ret*100:+.2f}% "
                      f"→ ${portfolio_value:,.0f}")

        # ── 벤치마크 추적 (분기 경계 가격 기준) ─────────────────────────
        spy_curr = _first_price_at(all_prices.get("SPY", pd.DataFrame()), q_ts)
        qqq_curr = _first_price_at(all_prices.get("QQQ", pd.DataFrame()), q_ts)

        if spy_curr is not None:
            if spy_prev_price is not None:
                r = spy_curr / spy_prev_price - 1
                spy_rets.append(r)
                spy_value *= (1 + r)
            spy_prev_price = spy_curr

        if qqq_curr is not None:
            if qqq_prev_price is not None:
                r = qqq_curr / qqq_prev_price - 1
                qqq_rets.append(r)
                qqq_value *= (1 + r)
            qqq_prev_price = qqq_curr

        # 마지막 분기는 포트폴리오 재구성 없이 청산만
        if is_last:
            break

        # ── 스코어링: q_ts 이전 데이터로 새 포트폴리오 선정 ─────────────
        candidates = []
        for tk in tickers:
            if tk not in all_prices:
                continue
            df = all_prices[tk]

            # 스코어링 데이터: q_ts 이전만 사용 (미래참조 방지)
            df_score = df[df.index < q_ts]
            if len(df_score) < 60:
                continue

            # 진입가: q_ts 이후 첫 거래일 가격
            entry_p = _first_price_at(df, q_ts)
            if entry_p is None:
                continue

            info   = _info_cache.get(tk, {})
            result = _analyze_single(tk, df_score, info)
            if result:
                result["entry_price"] = entry_p
                candidates.append(result)

        if not candidates:
            log.warning(f"  [{q_ts_str[:7]}] 후보 없음 — 이전 포트폴리오 유지")
            # 데이터 없을 경우 이전 포트폴리오 진입가만 q_ts 기준으로 업데이트
            for pos in active_portfolio:
                tk = pos["ticker"]
                p = _first_price_at(all_prices.get(tk, pd.DataFrame()), q_ts)
                if p:
                    pos["entry_price"] = p
            continue

        candidates = _apply_percentile_scores(candidates)
        top_pool   = candidates[: STRATEGY["portfolio_size"] * 5]
        top_pool   = apply_sector_cap(top_pool, STRATEGY["sector_max"])
        selected   = top_pool[: STRATEGY["portfolio_size"]]

        stock_pct = 100.0 - STRATEGY["safe_asset_weight"]
        weights   = calc_weights([c["total_score"] for c in selected], stock_pct)

        active_portfolio = [
            {
                "ticker":      c["ticker"],
                "weight":      w,
                "entry_price": c["entry_price"],
            }
            for c, w in zip(selected, weights)
        ]

        quarter_details.append({
            "quarter":     q_ts_str[:7],
            "holdings":    [(c["ticker"], round(w, 1)) for c, w in zip(selected, weights)],
            "top_sectors": [c["sector"] for c in selected[:5]],
        })

        log.info(f"  [{q_ts_str[:7]}] 후보 {len(candidates)}개 → "
                 f"선정 {len(selected)}개: "
                 f"{', '.join(c['ticker'] for c in selected[:5])}...")

    # ── Step 5: 성과 지표 계산 ────────────────────────────────────────
    log.info("[BT] Step 5: 성과 지표 계산...")
    metrics = _calc_performance_metrics(
        quarterly_rets, spy_rets, qqq_rets,
        portfolio_value, spy_value, qqq_value,
        start_date, end_date,
        value_history, quarter_details,
    )

    # 결과 저장
    BACKTEST_RESULT_FILE.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"백테스트 결과 저장 → {BACKTEST_RESULT_FILE}")
    return metrics


def _calc_performance_metrics(
    port_rets: list[float],
    spy_rets:  list[float],
    qqq_rets:  list[float],
    final_port: float,
    final_spy:  float,
    final_qqq:  float,
    start_date: str,
    end_date:   str,
    value_history: list[dict],
    quarter_details: list[dict],
) -> dict:
    """성과 지표 계산"""
    if not port_rets:
        return {
            "error": "데이터 없음 — 분기별 수익률이 계산되지 않았습니다",
            "diagnostics": {
                "n_spy_rets":  len(spy_rets),
                "n_qqq_rets":  len(qqq_rets),
                "start_date":  start_date,
                "end_date":    end_date,
                "hint": "가격 데이터 다운로드 실패 또는 필터 조건이 너무 엄격할 수 있습니다",
            },
        }

    n_quarters = len(port_rets)
    n_years    = n_quarters / 4.0

    # ── CAGR ─────────────────────────────────────────────────────────
    cagr = (final_port / 10000) ** (1 / n_years) - 1 if n_years > 0 else 0.0
    spy_cagr = (final_spy / 10000) ** (1 / n_years) - 1 if spy_rets and n_years > 0 else 0.0
    qqq_cagr = (final_qqq / 10000) ** (1 / n_years) - 1 if qqq_rets and n_years > 0 else 0.0

    # ── 연간화 표준편차 ────────────────────────────────────────────────
    arr = np.array(port_rets)
    ann_std = float(np.std(arr, ddof=1)) * math.sqrt(4) if len(arr) > 1 else 0.0

    # ── Sharpe (무위험 수익률 4%) ──────────────────────────────────────
    rf_quarterly = 0.04 / 4
    excess_rets  = arr - rf_quarterly
    sharpe = (float(np.mean(excess_rets)) * 4) / ann_std if ann_std > 0 else 0.0

    # ── Sortino (하방 표준편차만) ─────────────────────────────────────
    down_arr = arr[arr < rf_quarterly]
    down_std = float(np.std(down_arr, ddof=1)) * math.sqrt(4) if len(down_arr) > 1 else ann_std
    sortino  = (float(np.mean(excess_rets)) * 4) / down_std if down_std > 0 else 0.0

    # ── MDD ───────────────────────────────────────────────────────────
    cum_values = [10000.0]
    for r in port_rets:
        cum_values.append(cum_values[-1] * (1 + r))

    peak = cum_values[0]
    mdd  = 0.0
    for v in cum_values:
        peak = max(peak, v)
        drawdown = (v - peak) / peak
        mdd = min(mdd, drawdown)

    # ── Calmar ───────────────────────────────────────────────────────
    calmar = cagr / abs(mdd) if mdd != 0 else 0.0

    # ── Alpha vs SPY ─────────────────────────────────────────────────
    alpha_spy = (cagr - spy_cagr) * 100

    # ── 승률 ─────────────────────────────────────────────────────────
    wins     = sum(1 for r in port_rets if r > 0)
    win_rate = wins / n_quarters * 100 if n_quarters > 0 else 0.0

    # ── 최고/최저 분기 ────────────────────────────────────────────────
    best_q  = float(max(port_rets)) * 100 if port_rets else 0.0
    worst_q = float(min(port_rets)) * 100 if port_rets else 0.0
    avg_q   = float(np.mean(arr)) * 100 if len(arr) > 0 else 0.0

    return {
        "version":       "QM전략 v1.0",
        "start_date":    start_date,
        "end_date":      end_date,
        "n_quarters":    n_quarters,
        "n_years":       round(n_years, 1),
        # 최종 가치
        "final_portfolio": round(final_port, 2),
        "final_spy":       round(final_spy, 2),
        "final_qqq":       round(final_qqq, 2),
        # 연간 수익률
        "cagr_pct":      round(cagr * 100, 2),
        "spy_cagr_pct":  round(spy_cagr * 100, 2),
        "qqq_cagr_pct":  round(qqq_cagr * 100, 2),
        "alpha_spy_pct": round(alpha_spy, 2),
        "alpha_qqq_pct": round((cagr - qqq_cagr) * 100, 2),
        # 위험 지표
        "mdd_pct":       round(mdd * 100, 2),
        "spy_mdd_pct":   _calc_mdd_from_rets(spy_rets),
        "ann_std_pct":   round(ann_std * 100, 2),
        # 위험 대비 수익
        "sharpe":        round(sharpe, 2),
        "sortino":       round(sortino, 2),
        "calmar":        round(calmar, 2),
        # 분기 통계
        "win_rate_pct":  round(win_rate, 1),
        "best_quarter_pct":  round(best_q, 2),
        "worst_quarter_pct": round(worst_q, 2),
        "avg_quarter_pct":   round(avg_q, 2),
        # 부가 정보
        "value_history":   value_history[-20:],  # 최근 20분기
        "quarter_details": quarter_details[-12:],  # 최근 12분기
        "bias_warnings": [
            "생존자 편향: 현재 S&P1500 구성종목 기준",
            "재무 미래참조: yfinance.info 현재값 사용",
            "유동성 편향: 과거 소형주가 현재 기준으로 필터될 수 있음",
        ],
    }


def _calc_mdd_from_rets(rets: list[float]) -> float:
    if not rets:
        return 0.0
    cum = [10000.0]
    for r in rets:
        cum.append(cum[-1] * (1 + r))
    peak, mdd = cum[0], 0.0
    for v in cum:
        peak = max(peak, v)
        mdd  = min(mdd, (v - peak) / peak)
    return round(mdd * 100, 2)


def format_backtest_report(metrics: dict) -> str:
    """백테스트 결과를 텔레그램용 텍스트로 포맷"""
    if "error" in metrics:
        return f"❌ 백테스트 오류: {metrics['error']}"

    lines = [
        f"📊 *QM전략 워크포워드 백테스트 결과*",
        f"────────────────────────────────",
        f"📅 기간: {metrics['start_date']} ~ {metrics['end_date']} ({metrics['n_years']}년)",
        f"💰 $10,000 → ${metrics['final_portfolio']:,.0f}",
        f"",
        f"📈 *수익률*",
        f"  CAGR (연복리):  {metrics['cagr_pct']:+.2f}%",
        f"  SPY CAGR:       {metrics['spy_cagr_pct']:+.2f}%",
        f"  QQQ CAGR:       {metrics['qqq_cagr_pct']:+.2f}%",
        f"  Alpha vs SPY:   {metrics['alpha_spy_pct']:+.2f}%p",
        f"  Alpha vs QQQ:   {metrics['alpha_qqq_pct']:+.2f}%p",
        f"",
        f"📉 *위험 지표*",
        f"  MDD (최대낙폭): {metrics['mdd_pct']:.2f}%",
        f"  SPY MDD:        {metrics['spy_mdd_pct']:.2f}%",
        f"  연간 변동성:    {metrics['ann_std_pct']:.2f}%",
        f"",
        f"⚖️ *위험 대비 수익*",
        f"  Sharpe 비율:   {metrics['sharpe']:.2f}",
        f"  Sortino 비율:  {metrics['sortino']:.2f}",
        f"  Calmar 비율:   {metrics['calmar']:.2f}",
        f"",
        f"📊 *분기 통계*",
        f"  총 분기: {metrics['n_quarters']}회",
        f"  승률:   {metrics['win_rate_pct']:.1f}%",
        f"  평균:   {metrics['avg_quarter_pct']:+.2f}%",
        f"  최고:   {metrics['best_quarter_pct']:+.2f}%",
        f"  최저:   {metrics['worst_quarter_pct']:+.2f}%",
        f"",
        f"⚠️ *편향 경고*",
    ]
    for w in metrics.get("bias_warnings", []):
        lines.append(f"  · {w}")

    return "\n".join(lines)


# ══════════════════════════════════════════
# §7. 상태 관리 (포트폴리오 / 리밸런싱)
# ══════════════════════════════════════════
def load_portfolio() -> dict | None:
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"포트폴리오 파일 읽기 실패: {e}")
    return None


def save_portfolio(data: dict) -> None:
    PORTFOLIO_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log.info(f"포트폴리오 저장 → {PORTFOLIO_FILE}")


def _load_last_rebal() -> str | None:
    if LAST_REBAL_FILE.exists():
        try:
            return json.loads(LAST_REBAL_FILE.read_text())["quarter"]
        except Exception:
            pass
    return None


def _save_last_rebal(quarter_str: str) -> None:
    LAST_REBAL_FILE.write_text(json.dumps({"quarter": quarter_str}))
    _last_rebal_cache["quarter"] = quarter_str


def _current_quarter() -> str:
    now = datetime.now(KST)
    return f"{now.year}-Q{(now.month - 1)//3 + 1}"


def already_ran_this_quarter() -> bool:
    last = _last_rebal_cache["quarter"] or _load_last_rebal()
    return last == _current_quarter()


def is_rebal_month() -> bool:
    """현재 월이 리밸런싱 월(1/4/7/10월)인지 확인"""
    return datetime.now(KST).month in STRATEGY["rebal_months"]


# ══════════════════════════════════════════
# §8. Heartbeat + ���니터링
# ══════════════════════════════════════════
def get_portfolio_return(portfolio: dict) -> tuple[float, list[dict]]:
    """
    포트폴리오 현재 수익률 계산.
    반환: (가중평균 수익률 %, 개별 종목 수익률 리스트)
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return 0.0, []

    tickers = [h["ticker"] for h in holdings]
    try:
        prices = download_prices_bulk(tickers, period="5d")
    except Exception:
        return 0.0, []

    details = []
    total_weight = 0.0
    weighted_ret = 0.0

    for h in holdings:
        tk = h["ticker"]
        ep = h.get("entry_price", 0)
        if ep <= 0 or tk not in prices:
            continue
        df = prices[tk]
        if df.empty:
            continue
        curr_p = float(df["Close"].iloc[-1])
        ret    = (curr_p / ep - 1) * 100
        w      = h.get("weight", 0)
        weighted_ret += ret * w / 100
        total_weight += w
        details.append({
            "ticker":      tk,
            "name":        h.get("name", tk),
            "weight":      w,
            "entry_price": round(ep, 2),
            "curr_price":  round(curr_p, 2),
            "ret_pct":     round(ret, 2),
        })

    if total_weight > 0 and total_weight < 95:
        weighted_ret = weighted_ret * (100 / total_weight)

    return round(weighted_ret * 100, 2), details


def _check_and_alert_mdd(portfolio: dict) -> dict:
    """MDD 경보 — 포트폴리오 고점 대비 낙폭 체크"""
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return portfolio

    tickers = [h["ticker"] for h in holdings]
    try:
        prices = download_prices_bulk(tickers, period="5d")
    except Exception:
        return portfolio

    # 현재 포트폴리오 수익률 (가중 평균)
    curr_ret = 0.0
    total_w  = 0.0
    for h in holdings:
        tk = h["ticker"]
        ep = h.get("entry_price", 0)
        if ep <= 0 or tk not in prices or prices[tk].empty:
            continue
        curr_p = float(prices[tk]["Close"].iloc[-1])
        ret = (curr_p / ep - 1) * 100
        curr_ret += ret * h["weight"] / 100
        total_w  += h["weight"]

    if total_w <= 0:
        return portfolio

    # 고점 업데이트
    max_eq = portfolio.get("max_equity", 0.0)
    portfolio["max_equity"] = max(max_eq, curr_ret)

    # 낙폭 계산
    drawdown = curr_ret - portfolio["max_equity"]
    threshold = STRATEGY["mdd_alert_threshold"]

    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    last_alert = portfolio.get("last_mdd_alert_date", "")

    if drawdown <= threshold and last_alert != today_str:
        send_telegram(
            f"🚨 *MDD 경보*\n"
            f"포트폴리오 고점({portfolio['max_equity']:+.1f}%) 대비 낙폭: *{drawdown:+.1f}%*\n"
            f"임계값 {threshold}%p 이탈 — 리밸런싱 검토 권장\n"
            f"/status 로 현황 확인"
        )
        portfolio["last_mdd_alert_date"] = today_str
        save_portfolio(portfolio)

    return portfolio


def _check_stoploss(portfolio: dict) -> dict:
    """개별 종목 스톱로스 경보"""
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return portfolio

    tickers = [h["ticker"] for h in holdings]
    try:
        prices = download_prices_bulk(tickers, period="5d")
    except Exception:
        return portfolio

    threshold = STRATEGY["stoploss_threshold"]
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    alerts    = portfolio.get("last_stoploss_alerts", {})

    for h in holdings:
        tk = h["ticker"]
        ep = h.get("entry_price", 0)
        if ep <= 0 or tk not in prices or prices[tk].empty:
            continue
        curr_p = float(prices[tk]["Close"].iloc[-1])
        ret    = (curr_p / ep - 1) * 100

        if ret <= threshold and alerts.get(tk) != today_str:
            emoji = "🔴"
            send_telegram(
                f"{emoji} *개별 종목 스톱로스 경보*\n"
                f"{tk} ({h.get('name', '')}) 진입가 대비: *{ret:+.1f}%*\n"
                f"임계값 {threshold}% 이탈 — 포지션 재검토 권장"
            )
            alerts[tk] = today_str

    portfolio["last_stoploss_alerts"] = alerts
    return portfolio


def _heartbeat() -> None:
    """매일 07:00 KST — 포트폴리오 현황 + 모니터링"""
    portfolio = load_portfolio()
    if not portfolio:
        send_telegram("ℹ️ 포트폴리오 없음 — /scan 으로 리밸런싱 실행")
        return

    total_ret, details = get_portfolio_return(portfolio)

    now = datetime.now(KST)
    lines = [
        f"☀️ *일일 Heartbeat* ({now.strftime('%Y-%m-%d %H:%M KST')})",
        f"",
        f"📊 포트폴리오 수익률 (진입가 기준): *{total_ret:+.2f}%*",
        f"💰 현금 비중: {portfolio.get('cash_pct', 30)}%",
        f"📅 리밸런싱: {portfolio.get('rebal_quarter', 'N/A')} ({portfolio.get('rebal_date', '')})",
        f"",
        f"📋 *보유 종목* ({len(details)}개)",
    ]
    for d in details:
        bar = "🟢" if d["ret_pct"] >= 0 else "🔴"
        lines.append(
            f"  {bar} {d['ticker']} {d['weight']}% | {d['ret_pct']:+.1f}%"
        )

    # 다음 리밸런싱 안내
    if is_rebal_month() and not already_ran_this_quarter():
        lines.append(f"\n⏰ *이번 분기 리밸런싱 미실행* — 자동 실행 예정")

    send_telegram_chunks("\n".join(lines))

    # 모니터링 (MDD + 스톱로스)
    portfolio = _check_and_alert_mdd(portfolio)
    portfolio = _check_stoploss(portfolio)
    save_portfolio(portfolio)


def _perf_check() -> None:
    """매월 15일 — 성과 점검 (SPY·QQQ 벤치마크 비교)"""
    portfolio = load_portfolio()
    if not portfolio:
        return

    total_ret, _ = get_portfolio_return(portfolio)

    # SPY, QQQ 동기간 수익률
    rebal_date = portfolio.get("rebal_date", "")
    bench_rets  = {}
    if rebal_date:
        for sym in ["SPY", "QQQ"]:
            try:
                df = yf.download(sym, start=rebal_date, progress=False, auto_adjust=True)
                if not df.empty and len(df) >= 2:
                    ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[0]) - 1) * 100
                    bench_rets[sym] = round(ret, 2)
            except Exception:
                pass

    now = datetime.now(KST)
    lines = [
        f"📈 *분기 성과 점검* ({now.strftime('%Y-%m-%d')})",
        f"",
        f"📊 포트폴리오: *{total_ret:+.2f}%* (진입 이후)",
    ]
    for sym, ret in bench_rets.items():
        alpha = total_ret - ret
        lines.append(f"  {sym}: {ret:+.2f}% | 알파: {alpha:+.2f}%p")

    send_telegram_chunks("\n".join(lines))


# ══════════════════════════════════════════
# §9. 텔레그램 명령어 핸들러
# ══════════════════════════════════════════
def _handle_status(chat_id: str) -> None:
    portfolio = load_portfolio()
    if not portfolio:
        _reply_to(chat_id, "❌ 포트폴리오 없음. /scan 으로 리밸런싱 실행하세요.")
        return

    total_ret, details = get_portfolio_return(portfolio)
    lines = [
        f"📊 *포트폴리오 현황*",
        f"리밸런싱: {portfolio.get('rebal_quarter', 'N/A')} ({portfolio.get('rebal_date', '')})",
        f"레짐: {portfolio.get('regime', 'N/A')}",
        f"현금 {portfolio.get('cash_pct', 30)}% / 주식 {portfolio.get('stock_pct', 70)}%",
        f"",
        f"📈 전체 수익률: *{total_ret:+.2f}%*",
        f"",
        f"📋 보유 종목:",
    ]
    for d in details:
        emoji = "🟢" if d["ret_pct"] >= 0 else "🔴"
        lines.append(
            f"  {emoji} *{d['ticker']}* {d['weight']}% | "
            f"진입 ${d['entry_price']:.2f} → 현재 ${d['curr_price']:.2f} ({d['ret_pct']:+.1f}%)"
        )
    _reply_to_chunks(chat_id, "\n".join(lines))


def _handle_scan(chat_id: str) -> None:
    global _scan_running
    with _scan_lock:
        if _scan_running:
            _reply_to(chat_id, "⚠️ 이미 스캔 실행 중입니다.")
            return
        _scan_running = True
    try:
        _reply_to(chat_id, "🔍 수동 리밸런싱 시작... (15~30분 소요)")
        _do_quarterly_scan()
    finally:
        with _scan_lock:
            _scan_running = False


def _handle_perf(chat_id: str) -> None:
    _reply_to(chat_id, "📈 성과 점검 실행 중...")
    _perf_check()


def _handle_backtest(chat_id: str) -> None:
    """저장된 백테스트 결과 조회 (없으면 실행)"""
    if BACKTEST_RESULT_FILE.exists():
        try:
            metrics = json.loads(BACKTEST_RESULT_FILE.read_text(encoding="utf-8"))
            _reply_to_chunks(chat_id, format_backtest_report(metrics))
            return
        except Exception:
            pass
    _reply_to(chat_id, "백테스트 결과 없음. 서버에서 --backtest 플래그로 실행하세요.")


def _handle_help(chat_id: str) -> None:
    help_text = (
        "📖 *QM전략 장기투자 봇 v1.0*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "/status   — 포트폴리오 현황 + 수익률\n"
        "/scan     — 수동 리밸런싱 (분기 1회)\n"
        "/perf     — 성과 점검 (SPY·QQQ 비교)\n"
        "/backtest — 백테스트 결과 조회\n"
        "/help     — 이 도움말\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📅 리밸런싱: 1·4·7·10월 첫 거래일\n"
        "🌡 VIX 30+ 시 현금 자동 확대\n"
        "⚠️ 이 봇은 참고용입니다. 투자 결정은 본인 판단으로."
    )
    _reply_to(chat_id, help_text)


def _telegram_poll_loop() -> None:
    """텔레그램 롱폴링 명령어 수신 데몬"""
    if not TELEGRAM_TOKEN:
        log.warning("TELEGRAM_TOKEN 없음 — 명령어 수신 비활성화")
        return

    allowed_ids = {str(cid).strip() for cid in TELEGRAM_CHAT_IDS}
    offset = 0
    log.info(f"텔레그램 폴링 시작 (허용 채팅방: {allowed_ids})")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            )
            if res.status_code != 200:
                time.sleep(5)
                continue

            updates = res.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                msg    = upd.get("message") or upd.get("edited_message") or {}
                text   = str(msg.get("text", "")).strip()
                chat   = msg.get("chat", {})
                cid    = str(chat.get("id", "")).strip()

                if cid not in allowed_ids:
                    continue
                if not text.startswith("/"):
                    continue

                cmd = text.split()[0].lower().split("@")[0]
                log.info(f"명령어 수신: {cmd} from {cid}")

                if cmd == "/status":
                    threading.Thread(target=_handle_status, args=(cid,), daemon=True).start()
                elif cmd == "/scan":
                    threading.Thread(target=_handle_scan, args=(cid,), daemon=True).start()
                elif cmd == "/perf":
                    threading.Thread(target=_handle_perf, args=(cid,), daemon=True).start()
                elif cmd == "/backtest":
                    threading.Thread(target=_handle_backtest, args=(cid,), daemon=True).start()
                elif cmd == "/help":
                    _handle_help(cid)

        except Exception as e:
            log.error(f"폴링 예외: {e}")
            time.sleep(5)


# ══════════════════════════════════════════
# §10. 스케줄러 (분기 리밸런싱)
# ══════════════════════════════════════════
def _check_and_run_rebal() -> None:
    """리밸런싱 체크 — 분기 미실행 시 즉시 실행"""
    global _scan_running
    if not is_rebal_month():
        log.debug("리밸런싱 월 아님 — 스킵")
        return
    if already_ran_this_quarter():
        log.info(f"이번 분기 리밸런싱 이미 완료 ({_current_quarter()})")
        return
    with _scan_lock:
        if _scan_running:
            log.info("스캔 이미 실행 중 — 스킵")
            return
        _scan_running = True
    try:
        _do_quarterly_scan()
    finally:
        with _scan_lock:
            _scan_running = False


def _setup_scheduler() -> None:
    """스케줄 설정 (KST 기준)"""
    # 매일 07:00 — Heartbeat
    schedule.every().day.at("07:00").do(_heartbeat)
    # 매일 07:10 — 리밸런싱 체크 (분기 리밸런싱 월에만 실행)
    schedule.every().day.at("07:10").do(_check_and_run_rebal)
    # 매월 15일 07:00 — 성과 점검 (weekday 체크 포함)
    schedule.every().day.at("07:00").do(
        lambda: _perf_check() if datetime.now(KST).day == 15 else None
    )
    log.info("스케줄 등록 완료")
    log.info("  매일 07:00 KST — Heartbeat")
    log.info("  매일 07:10 KST — 분기 리밸런싱 체크 (1·4·7·10월)")
    log.info("  매월 15일 07:00 KST — 성과 점검")


def _watchdog_loop() -> None:
    """스케줄러 Watchdog — 10분 무응답 시 경보"""
    last_tick = time.time()

    def _tick():
        nonlocal last_tick
        last_tick = time.time()

    schedule.every(5).minutes.do(_tick)

    while True:
        time.sleep(60)
        if time.time() - last_tick > 600:
            log.error("스케줄러 Watchdog: 10분 무응답 감지")
            send_telegram("🚨 *Watchdog 경보* — 스케줄러가 10분 이상 응답하지 않음")
            last_tick = time.time()


# ══════════════════════════════════════════
# §11. 메인 엔트리포인트
# ══════════════════════════════════════════
def _print_backtest_report_console(metrics: dict) -> None:
    """콘솔용 백테스트 결과 출력"""
    # ── 오류 처리 ─────────────────────────────────────────────────────
    if "error" in metrics:
        print("\n" + "═" * 60)
        print("  ❌ 백테스트 실패")
        print("═" * 60)
        print(f"  오류: {metrics['error']}")
        print()
        diag = metrics.get("diagnostics", {})
        if diag:
            print("  [진단 정보]")
            for k, v in diag.items():
                print(f"    {k}: {v}")
        print()
        print("  [해결 방법]")
        print("    1. 인터넷 연결 확인")
        print("    2. yfinance 버전 확인: pip install -U yfinance")
        print("    3. 잠시 후 재시도 (Yahoo Finance 일시적 차단 가능)")
        print("═" * 60)
        return

    print("\n" + "═" * 60)
    print("  QM전략 워크포워드 백테스트 결과")
    print("═" * 60)
    print(f"  기간     : {metrics['start_date']} ~ {metrics['end_date']} ({metrics['n_years']}년)")
    print(f"  총 분기  : {metrics['n_quarters']}회")
    print(f"  $10,000 → ${metrics['final_portfolio']:>12,.2f}  (포트폴리오)")
    print(f"            ${metrics['final_spy']:>12,.2f}  (SPY 벤치마크)")
    print(f"            ${metrics['final_qqq']:>12,.2f}  (QQQ 벤치마크)")
    print()
    print("─── 수익률 ───────────────────────────────────────────")
    print(f"  CAGR (연복리)   : {metrics['cagr_pct']:>+8.2f}%")
    print(f"  SPY CAGR        : {metrics['spy_cagr_pct']:>+8.2f}%")
    print(f"  QQQ CAGR        : {metrics['qqq_cagr_pct']:>+8.2f}%")
    print(f"  Alpha vs SPY    : {metrics['alpha_spy_pct']:>+8.2f}%p")
    print(f"  Alpha vs QQQ    : {metrics['alpha_qqq_pct']:>+8.2f}%p")
    print()
    print("─── 위험 지표 ────────────────────────────────────────")
    print(f"  MDD (최대낙폭)  : {metrics['mdd_pct']:>8.2f}%")
    print(f"  SPY MDD         : {metrics['spy_mdd_pct']:>8.2f}%")
    print(f"  연간 변동성     : {metrics['ann_std_pct']:>8.2f}%")
    print()
    print("─── 위험 대비 수익 ────────────────────────────────────")
    print(f"  Sharpe 비율     : {metrics['sharpe']:>8.2f}")
    print(f"  Sortino 비율    : {metrics['sortino']:>8.2f}")
    print(f"  Calmar 비율     : {metrics['calmar']:>8.2f}")
    print()
    print("─── 분기 통계 ─────────────────────────────────────────")
    print(f"  승률            : {metrics['win_rate_pct']:>7.1f}%")
    print(f"  평균 분기 수익률: {metrics['avg_quarter_pct']:>+7.2f}%")
    print(f"  최고 분기       : {metrics['best_quarter_pct']:>+7.2f}%")
    print(f"  최저 분기       : {metrics['worst_quarter_pct']:>+7.2f}%")
    print()
    print("─── 편향 경고 ─────────────────────────────────────────")
    for w in metrics.get("bias_warnings", []):
        print(f"  ⚠  {w}")
    print("═" * 60)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="QM전략 장기투자 포트폴리오 봇 v1.0")
    parser.add_argument(
        "--backtest", action="store_true",
        help="백테스트 실행 후 라이브 봇 시작"
    )
    parser.add_argument(
        "--bt-only", action="store_true",
        help="백테스트만 실행 후 종료"
    )
    args = parser.parse_args()

    log.info("═══════════════════════════════════════════════════")
    log.info("  QM전략 미국주식 장기투자 포트폴리오 봇 v1.0 시작")
    log.info("═══════════════════════════════════════════════════")

    # 백테스트 모드
    if args.backtest or args.bt_only:
        log.info("백테스트 모드 실행")
        send_telegram(
            "🔬 *백테스트 시작*\n"
            f"기간: {STRATEGY['backtest_start']} ~ 현재\n"
            "⏳ 30분~1시간 소요 예상..."
        )
        metrics = run_backtest(send_progress=True)
        _print_backtest_report_console(metrics)
        report  = format_backtest_report(metrics)
        send_telegram_chunks(report)

        if args.bt_only:
            log.info("--bt-only 모드 — 백테스트 완료 후 종료")
            return

    # 라이브 봇 시작
    now = datetime.now(KST)
    quarter = _current_quarter()

    send_telegram(
        f"✅ *QM전략 장기투자 봇 v1.0 시작*\n"
        f"📅 {now.strftime('%Y-%m-%d %H:%M KST')}\n"
        f"🗓 현재 분기: {quarter}\n"
        f"📊 리밸런싱 월: 1·4·7·10월\n"
        f"{'📅 당분기 리밸런싱: ⏳ 즉시 실행 예정' if is_rebal_month() and not already_ran_this_quarter() else '📅 당분기 리밸런싱: ✅ 완료'}"
    )

    # 이번 분기 리밸런싱이 아직 안 됐으면 즉시 실행
    if is_rebal_month() and not already_ran_this_quarter():
        log.info("분기 첫 실행 감지 — 즉시 리밸런싱 시작")
        threading.Thread(target=_check_and_run_rebal, daemon=False).start()

    # 텔레그램 폴링 데몬
    polling_thread = threading.Thread(target=_telegram_poll_loop, daemon=True)
    polling_thread.start()

    # Watchdog 데몬
    watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True)
    watchdog_thread.start()

    # 스케줄 설정 및 실행
    _setup_scheduler()
    log.info("스케줄러 메인 루프 시작")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
