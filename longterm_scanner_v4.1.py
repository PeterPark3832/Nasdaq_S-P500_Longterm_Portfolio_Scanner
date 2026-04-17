"""
미국 주식 장기 투자 포트폴리오 스캐너 v4.5
────────────────────────────────────────────────────────
v3.1(한국주식) → v4.0(미국주식) 전면 전환

v4.0 → v4.1 안정성 개선:
  [핵심] yfinance 401 Invalid Crumb 해결
         개별 yf.download() × 168회 → yf.download([list]) 벌크 다운로드
         단일 세션으로 전종목 수신 → Yahoo 봇 감지 회피
  [개선] 재무(info) 병렬 workers 8→3 축소 + 재시도 로직 (지수 백오프)
  [개선] 벌크 청크 실패 시 개별 재시도 fallback 추가
  [개선] _analyze_ticker에 info 외부 주입 → 중복 조회 제거

v4.4 → v4.5 버그 수정 (Stage 4):
  [버그] _do_monthly_scan에서 future.result() 미사용 문제 수정
         _fetch_info_with_retry 결과값을 _analyze_ticker에 주입하지 않아
         외부 주입 패턴이 무용지물이 된 문제 — info=future.result() 명시적 전달
  [버그] apply_sector_cap에서 "Unknown" 섹터 쏠림 방어 추가
         yfinance 응답 누락 시 섹터="Unknown" 종목들이 max_per_sector(3)에 걸려
         재무 우량주가 억울하게 탈락하는 문제 — Unknown 면제 조건 추가

v4.3 → v4.4 데이터 신뢰도 개선 (Stage 3):
  [신규] 재무 데이터 신선도 필터 — mostRecentQuarter 기반
         fin_stale_skip_days(400일) 초과 시 스코어링 제외
         fin_stale_warn_days(200일) 초과 시 ⚠️_재무구식_ 표시
  [신규] 유니버스 스냅샷 저장 — universe_snapshots/universe_YYYY-MM.json
         매월 리밸런싱 시 유니버스 목록 저장 (최대 12개월치 보존)
         직전 달 대비 유니버스 변동(신규/제외 종목) 로그 출력
  [개선] 리밸런싱 브리핑에 재무 기준일, 데이터 품질 경고 섹션 추가
  [개선] 편향 경고 섹션 강화 — 스냅샷 저장 경로 안내 포함

v4.2 → v4.3 전략 품질 개선 (Stage 2):
  [개선] 재무 40점 재배분: ROE(15)·마진(15)·PEG(10) → ROE(10)·마진(10)·PEG(8)·매출성장(7)·FCF마진(5)
         매출성장률(revenueGrowth) 추가 — 이익 편향 완화
         FCF 마진(freeCashflow/totalRevenue) 추가 — 이익의 현금화 품질 반영
  [신규] D/E 필터: 비금융 섹터 debtToEquity > 200 시 제외 (금융·부동산 면제)
  [신규] 섹터 다양성 제약: apply_sector_cap() — 동일 섹터 최대 3종목 (IT 쏠림 방지)
  [신규] VIX 시장 레짐 필터: VIX≥30 현금+20%p / VIX≥40 현금+30%p (최대 60%)
         리밸런싱 브리핑에 레짐 상태 표시
  [개선] 브리핑에 섹터·매출성장·FCF마진·D/E 추가 표시

v4.1 → v4.2 안정성 개선 (Stage 1):
  [버그] _analyze_ticker의 불필요한 _sem 래핑 제거
         _fetch_info_with_retry(with _sem) 완료 후 동일 세마포어 재획득 시도 →
         workers 3개 전부 점유 중일 때 main 스레드 블로킹 유발하던 문제 수정
  [버그] 미사용 변수 ma50 제거
  [개선] Heartbeat get_quick_portfolio_return 개별 download 루프 → 벌크 1회로 교체
         401 Invalid Crumb 재발 가능성 제거
  [개선] 재무 캐시 타임스탬프(saved_at) 추가 + 72h 초과 시 자동 폐기
         빈 dict({}) 항목 복원 제외 → 다음 스캔에서 자동 재조회
  [신규] Watchdog 데몬 스레드 — 스케줄러 10분 무응답 시 텔레그램 경보

[백테스트 검증 설정]
  유니버스:  S&P500 + 나스닥100 통합 (~550종목)
  전략:      D — 혼합 전략 (재무40 + 기술20 + 모멘텀40)
  top_n:     10종목
  리밸런싱:  매월 1회
  검증 기간: 2015~2024 (10년)
  검증 결과: CAGR +19.49% / MDD -20.54% / 샤프 0.78 / QQQ 초과 +1.12%p

[전략 D 스코어링 — 100점 만점]
  재무 (40점):
    ROE        0~10점  높을수록
    순이익률   0~10점  높을수록
    PEG        0~8점   낮을수록 (PER÷성장률, 성장성 감안 밸류에이션)
    매출성장률 0~7점   높을수록 (이익 편향 보완)
    FCF 마진   0~5점   높을수록 (이익의 현금화 품질)
  기술 (20점):
    52주 위치  0~20점  신고가 근접 = 모멘텀 확인
  모멘텀 퍼센타일 (40점):
    6개월 수익률  0~20점  후보군 내 퍼센타일
    12개월 수익률 0~20점  후보군 내 퍼센타일

[필터 — v4.3 추가]
  D/E 비율    비금융 섹터 200% 초과 시 제외
  섹터 다양성 동일 섹터 최대 3종목
  시장 레짐   VIX≥30 현금+20%p / VIX≥40 현금+30%p

[자산 배분]
  안전 자산(현금/파킹) 30% 고정
  주식 70%를 10종목 점수 비례 배분

[스케줄 — 미국 시장 기준 KST]
  07:00 매일    → Heartbeat (전날 미국 장 마감 종가 기준 수익률, USD)
  07:10 매일    → 리밸런싱 체크 (당월 미실행 시 즉시, 한국 봇과 시간 분산)
  07:00 매월 15일 → 중간 성과 점검 (15일 주말 시 월요일 순연)

[의존성]
  pip install yfinance schedule python-dotenv pandas requests

[편향 경고]
  yfinance.info는 현재 재무값 반환 → 재무 점수는 미래참조 편향 존재
  유니버스는 현재 S&P500/나스닥100 기준 → 생존자 편향 존재
  가격 기반 모멘텀(40점)은 상대적으로 신뢰도 높음
────────────────────────────────────────────────────────
"""

import os
import time
import json
import logging
import threading
import requests
import schedule
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

# ==========================================
# 로깅
# ==========================================
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
log = logging.getLogger(__name__)

# ==========================================
# 환경변수
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
_raw_ids = os.getenv("TELEGRAM_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID") or ""
TELEGRAM_CHAT_IDS = [cid.strip() for cid in _raw_ids.split(",") if cid.strip()]

# 토픽(Forum) 그룹 지원 — .env의 주석(#)도 안전하게 파싱
# 예: TELEGRAM_TOPIC_ID=4        → 4
#     TELEGRAM_TOPIC_ID=4  # 미국주식 → 4
_raw_topic = os.getenv("TELEGRAM_TOPIC_ID", "").split("#")[0].strip()
TELEGRAM_TOPIC_ID = int(_raw_topic) if _raw_topic.isdigit() else None

def _is_supergroup(chat_id: str) -> bool:
    """슈퍼그룹 여부 판별 — 슈퍼그룹은 -100으로 시작"""
    return str(chat_id).startswith("-100")

# ==========================================
# 전략 파라미터 (백테스트 v1.0 D전략 검증값)
# ==========================================
STRATEGY = {
    # ── 유니버스 ─────────────────────────────────────────
    # [백테스트 근거] S&P500+나스닥100 통합 유니버스
    # 10년(2015~2024) CAGR +19.49% / MDD -20.54% / 샤프 0.78

    # ── 포트폴리오 ────────────────────────────────────────
    # [백테스트 근거] top_n=10이 top_n=5보다 MDD 개선 (-20.54% vs -29.05%)
    # 수익률은 소폭 낮지만 장기 운용 시 심리적 안정성 우위
    "portfolio_size":    10,

    # [백테스트 근거] 주식 100% MDD -20.54% → 현금 30% 추가 보수적 운용
    "safe_asset_weight": 30.0,

    # ── 기술 필터 ─────────────────────────────────────────
    # [백테스트 근거] MA200 위 필터: D전략 기본 조건
    "use_ma200":         True,

    # ── 거래정지 필터 ─────────────────────────────────────
    # 미국은 공휴일 길어서 여유있게 설정
    "max_stale_days":    10,

    # ── 성능 ─────────────────────────────────────────────
    # [v4.1] 가격은 벌크 다운로드로 workers 불필요
    # 재무(info) 조회만 병렬 — 너무 많으면 401 유발
    "info_workers":      3,      # yfinance.info 동시 요청 수 (보수적)
    "info_retry":        3,      # 재시도 횟수
    "info_retry_delay":  5.0,    # 재시도 대기 (초)
    "bulk_chunk_size":   100,    # 벌크 다운로드 한 번에 처리할 종목 수

    # ── [v4.3] Stage 2 전략 품질 파라미터 ──────────────────
    # 2-1. 재무 지표 확장
    # 비금융 섹터(금융/부동산 제외) D/E 최대 허용값
    # 금융·부동산은 레버리지 사업 구조상 D/E가 원래 높으므로 필터 면제
    "de_ratio_max":      200.0,  # 비금융 최대 부채비율 (%)

    # 2-2. 섹터 다양성
    # 동일 섹터 최대 편입 종목 수 — IT 쏠림 방지
    "sector_max":        3,

    # 2-3. 시장 레짐 필터 (VIX 기반 현금 비중 자동 조정)
    "vix_caution":       30,     # VIX ≥ 이 값 → 현금 +20%p
    "vix_fear":          40,     # VIX ≥ 이 값 → 현금 +30%p
    "vix_cash_cap":      60.0,   # 레짐 조정 시 현금 비중 상한

    # ── [v4.4] Stage 3 데이터 신뢰도 파라미터 ──────────────
    # 3-1. 재무 데이터 신선도
    # yfinance.info의 mostRecentQuarter(Unix ts)로 재무 보고서 시점 판별
    # → 너무 오래된 종목은 스코어링에서 제외(또는 경고 flag)
    "fin_stale_skip_days": 400,  # 재무 보고서가 이 일수 초과이면 제외 (약 13개월)
    "fin_stale_warn_days": 200,  # 재무 보고서가 이 일수 초과이면 ⚠️ stale 표시 (약 6.5개월)

    # 3-2. 유니버스 스냅샷
    "universe_snapshot_keep": 12,  # 보존할 스냅샷 최대 개수 (월 단위, 1년치)
}

# ==========================================
# 파일 경로
# ==========================================
PORTFOLIO_FILE         = Path("portfolio_state_us.json")
LAST_REBAL_FILE        = Path("last_rebal_us.json")
INFO_CACHE_FILE        = Path("yf_info_cache.json")        # 재무 캐시 (재시작 시 재활용)
UNIVERSE_SNAPSHOT_DIR  = Path("universe_snapshots")        # [v4.4] 월별 유니버스 스냅샷 디렉터리

# ==========================================
# 스레드 안전
# ==========================================
_last_rebal_cache: dict = {"month": None}
_scan_lock    = threading.Lock()
_scan_running = False
_sem          = threading.Semaphore(STRATEGY["info_workers"])

# yfinance 재무 데이터 캐시 (월별로 1회만 조회)
_info_cache: dict[str, dict] = {}
_info_cache_lock = threading.Lock()


# ══════════════════════════════════════════
# 유니버스: S&P500 + 나스닥100
# ══════════════════════════════════════════
# ══════════════════════════════════════════
# 하드코딩 유니버스 폴백 (완전판)
# 위키피디아/yfinance ETF 조회 모두 실패 시 사용
# 나스닥100 + S&P500 주요 종목 커버
# ══════════════════════════════════════════

# 나스닥100 전종목 (2024년 기준)
NDX100_FALLBACK = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","COST",
    "NFLX","AMD","ADBE","QCOM","INTC","INTU","AMAT","MU","LRCX","ISRG",
    "KLAC","MRVL","REGN","SNPS","CDNS","PANW","CRWD","MNST","ORLY","FTNT",
    "CTAS","MAR","ABNB","DXCM","CPRT","PAYX","WDAY","FAST","IDXX","VRSK",
    "BIIB","ROST","PCAR","MCHP","ODFL","ANSS","CTSH","DLTR","ZS","TEAM",
    "DDOG","ADI","TXN","EA","TMUS","SBUX","PEP","AMGN","GILD","VRTX","MDLZ",
    "ROP","GEHC","KDP","FANG","CEG","AZN","MELI","PDD","ASML","TTD",
    "ABNB","ILMN","ENPH","ALGN","WBD","LCID","RIVN","ZM","OKTA","DOCU",
    "SPLK","ON","TTWO","MRNA","EXC","AEP","XEL","CINF","SIRI","HON",
    "CSX","PCAR","FAST","CTAS","ROST","DLTR","CPRT","PAYX","WDAY","ORLY",
]

# S&P500 전 섹터 대표 종목 (나스닥100 미포함, 섹터별 균형 구성)
SP500_EXTRA_FALLBACK = [
    # ── 금융 ──────────────────────────────────────────
    "JPM","BAC","WFC","GS","MS","BLK","C","AXP","USB","PNC",
    "SCHW","COF","TFC","MTB","RF","FITB","KEY","HBAN","CFG","ZION",
    "MCO","SPGI","ICE","CME","CB","AON","MMC","AJG","WTW","MET",
    "PRU","AFL","ALL","TRV","PGR","HIG","CNA","AIZ","UNM","GL",
    # ── 헬스케어 ────────────────────────────────────────
    "JNJ","UNH","CVS","ABT","MRK","PFE","LLY","BMY","MDT","SYK",
    "BSX","EW","ZBH","BDX","BAX","HOLX","DXCM","PODD","INSP","NVCR",
    "HCA","THC","UHS","CYH","AMED","AMEDISYS","ACAD","JAZZ","EXAS","VEEV",
    "ANTM","CI","HUM","MOH","CNC","WCG","DVA","FMS","ESNT","RCM",
    # ── 에너지 ──────────────────────────────────────────
    "XOM","CVX","COP","SLB","EOG","VLO","MPC","PSX","HAL","BKR",
    "DVN","FANG","MRO","APA","OXY","HES","CTRA","SM","CHK","AR",
    "KMI","WMB","OKE","ET","EPD","MMP","PAA","TRGP","DT","LNG",
    # ── 소비재 (필수/임의) ───────────────────────────────
    "WMT","TGT","HD","LOW","TJX","NKE","MCD","CMG","YUM","DPZ",
    "SBUX","COST","KR","SFM","GO","CHWY","CHEF","ARMK","DINE","DRI",
    "PG","KO","PEP","MDLZ","GIS","K","SJM","CPB","CAG","HRL",
    "CL","CHD","EL","COTY","REV","SKIN","ULTA","BBWI","AEO","ANF",
    "F","GM","STLA","TM","HMC","RIVN","LCID","NKLA","PTRA","WKHS",
    # ── 산업재 ──────────────────────────────────────────
    "GE","HON","MMM","CAT","DE","RTX","LMT","NOC","BA","GD",
    "LHX","HII","TDG","HWM","TXT","SPR","KTOS","PLTR","LDOS","SAIC",
    "FDX","UPS","CSX","UNP","NSC","DAL","LUV","UAL","AAL","ALK",
    "JBLU","SAVE","CHRW","XPO","ODFL","SAIA","WERN","LSTR","ARCB","GXO",
    "PWR","EMR","ROK","ETN","AME","PH","ITW","IR","DOV","GNRC",
    "CARR","OTIS","JCI","TT","LEN","DHI","PHM","TOL","MDC","MHO",
    # ── IT/테크 (나스닥100 외) ────────────────────────────
    "ORCL","IBM","CRM","NOW","SNOW","PLTR","NET","DDOG","ZS","OKTA",
    "FTNT","CYBR","S","TENB","QLYS","RPM","VRNS","SAIL","BCYC","IDCC",
    "ACN","CTSH","IT","EPAM","WIT","INFY","WEX","GDDY","HUBS","BILL",
    "ADSK","ANSS","PTC","CDNS","MTSI","MCHP","SWKS","QRVO","CRUS","SLAB",
    # ── 통신 ────────────────────────────────────────────
    "T","VZ","TMUS","CMCSA","CHTR","DISH","LUMN","ATUS","CABO","WOW",
    # ── 유틸리티 ────────────────────────────────────────
    "NEE","DUK","SO","D","AEP","EXC","SRE","PCG","ED","XEL",
    "ES","EIX","PPL","CMS","NI","ATO","WEC","DTE","CNP","LNT",
    # ── 부동산 ──────────────────────────────────────────
    "AMT","PLD","CCI","EQIX","SPG","PSA","DLR","AVB","EQR","WY",
    "ARE","BXP","KIM","REG","FRT","NNN","O","STAG","TRNO","ELS",
    "WELL","VTR","PEAK","HR","DOC","MPW","SBRA","CTRE","NHI","OHI",
    # ── 소재/기초소재 ────────────────────────────────────
    "LIN","APD","ALB","SHW","ECL","IFF","PPG","RPM","CC","OLN",
    "NEM","GOLD","AEM","WPM","FNV","RGLD","PAAS","CDE","HL","FSM",
    "FCX","SCCO","AA","NUE","STLD","CMC","RS","ATI","ARNC","CRS",
]

def get_universe_tickers() -> list[str]:
    """
    S&P500 + 나스닥100 통합 유니버스.
    3단계 폴백:
      1순위: yfinance ETF 보유종목 (QQQ + SPY)  — 가장 정확
      2순위: Wikipedia User-Agent 우회 파싱     — 준정확
      3순위: 하드코딩 완전판                     — 항상 동작
    """
    ndx, sp = [], []

    # ── 1순위: yfinance ETF 보유종목 조회 ────────────────
    try:
        import yfinance as yf
        qqq_info = yf.Ticker("QQQ").funds_data
        if qqq_info and hasattr(qqq_info, "top_holdings"):
            holdings = qqq_info.top_holdings
            if holdings is not None and len(holdings) >= 50:
                ndx = [str(t).replace(".", "-") for t in holdings.index.tolist()]
                log.info(f"  QQQ ETF 보유종목 조회 성공: {len(ndx)}개")
    except Exception:
        pass

    try:
        import yfinance as yf
        spy_info = yf.Ticker("SPY").funds_data
        if spy_info and hasattr(spy_info, "top_holdings"):
            holdings = spy_info.top_holdings
            if holdings is not None and len(holdings) >= 200:
                sp = [str(t).replace(".", "-") for t in holdings.index.tolist()]
                log.info(f"  SPY ETF 보유종목 조회 성공: {len(sp)}개")
    except Exception:
        pass

    # ── 2순위: Wikipedia User-Agent 우회 파싱 ────────────
    if not ndx:
        try:
            ndx_tables = pd.read_html(
                "https://en.wikipedia.org/wiki/Nasdaq-100",
                attrs={"id": "constituents"},    # 특정 테이블 ID 지정
            )
            for t in ndx_tables:
                for col in ["Ticker","Symbol","Ticker symbol"]:
                    if col in t.columns:
                        tks = [str(s).replace(".","-") for s in t[col].dropna()
                               if 1 <= len(str(s)) <= 6]
                        if len(tks) >= 80:
                            ndx = tks[:100]
                            log.info(f"  나스닥100 위키 파싱 성공: {len(ndx)}개")
                            break
                if ndx: break
        except Exception:
            pass

    if not sp:
        try:
            sp_tables = pd.read_html(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                attrs={"id": "constituents"},
            )
            for t in sp_tables:
                for col in ["Symbol","Ticker","Ticker symbol"]:
                    if col in t.columns:
                        tks = [str(s).replace(".","-") for s in t[col].dropna()
                               if 1 <= len(str(s)) <= 6]
                        if len(tks) >= 400:
                            sp = tks[:500]
                            log.info(f"  S&P500 위키 파싱 성공: {len(sp)}개")
                            break
                if sp: break
        except Exception:
            pass

    # ── 3순위: 하드코딩 완전판 폴백 ──────────────────────
    if not ndx:
        ndx = NDX100_FALLBACK
        log.info(f"  나스닥100 폴백 사용: {len(ndx)}개")
    if not sp:
        sp = SP500_EXTRA_FALLBACK
        log.info(f"  S&P500 폴백 사용: {len(sp)}개")

    combined = list(dict.fromkeys(ndx + sp))  # 중복 제거, 순서 유지
    log.info(f"유니버스: 나스닥100 {len(ndx)}개 + S&P500추가 {len(sp)}개 → 통합 {len(combined)}개")
    return combined


# ══════════════════════════════════════════
# 텔레그램
# ══════════════════════════════════════════
def send_telegram(text: str, topic_id: int | None = None) -> None:
    """
    텔레그램 메시지 발송.
    슈퍼그룹(-100으로 시작)에만 message_thread_id 적용.
    일반 채팅방은 topic_id 무시 — 두 가지 채팅방 혼용 시 에러 방지.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS:
        log.warning("텔레그램 설정 없음")
        return
    effective_topic = topic_id if topic_id is not None else TELEGRAM_TOPIC_ID
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            # 슈퍼그룹에만 message_thread_id 추가 (일반 채팅방 에러 방지)
            if effective_topic is not None and _is_supergroup(chat_id):
                payload["message_thread_id"] = effective_topic
            res = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data=payload,
                timeout=10,
            )
            if res.status_code != 200:
                log.error(f"텔레그램 실패 ({chat_id}): {res.text}")
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


# ══════════════════════════════════════════
# 상태 관리
# ══════════════════════════════════════════
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


def _load_last_rebal() -> str | None:
    if LAST_REBAL_FILE.exists():
        try:
            return json.loads(LAST_REBAL_FILE.read_text())["month"]
        except Exception:
            pass
    return None


def _save_last_rebal(month_str: str) -> None:
    LAST_REBAL_FILE.write_text(json.dumps({"month": month_str}))


def already_ran_this_month() -> bool:
    now_month = datetime.now(KST).strftime("%Y-%m")
    last_run  = _last_rebal_cache["month"] or _load_last_rebal()
    return last_run == now_month


# ══════════════════════════════════════════
# yfinance 재무 캐시 관리
# ══════════════════════════════════════════
_INFO_CACHE_MAX_AGE_HOURS = 72   # 캐시 유효 시간 (시간). 72h = 3일

def _load_info_cache() -> None:
    """서버 재시작 시 파일에서 재무 캐시 복원 — 불필요한 재조회 방지

    [v4.2] 타임스탬프 기반 만료 추가:
      - 당월 + saved_at 기준 _INFO_CACHE_MAX_AGE_HOURS 이내만 복원
      - 빈 dict({})로 저장된 항목은 제외 → 다음 스캔에서 재조회
    """
    global _info_cache
    if not INFO_CACHE_FILE.exists():
        return
    try:
        data = json.loads(INFO_CACHE_FILE.read_text(encoding="utf-8"))
        now  = datetime.now(KST)
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
        # 빈 항목 제외 (조회 실패했던 종목은 다음 스캔에서 재시도)
        raw_cache = data.get("cache", {})
        _info_cache = {t: v for t, v in raw_cache.items() if v}
        skipped = len(raw_cache) - len(_info_cache)
        log.info(f"재무 캐시 복원: {len(_info_cache)}개 종목 (빈 항목 {skipped}개 제외)")
    except Exception as e:
        log.warning(f"재무 캐시 로드 실패: {e}")


def _save_info_cache() -> None:
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
    """yfinance 재무 데이터 (당월 캐시 우선)"""
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


# ══════════════════════════════════════════
# 비중 계산
# ══════════════════════════════════════════
def calc_stock_weights(scores: list[float], target_sum: float) -> list[float]:
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
# 전략 D 스코어 함수
# ══════════════════════════════════════════
# [v4.3] 재무 40점 재배분: ROE(15)·마진(15)·PEG(10) → ROE(10)·마진(10)·PEG(8)·매출성장(7)·FCF마진(5)
# 기술·모멘텀 점수 배분(20+40) 및 총합(100) 변경 없음

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
    """PEG 점수 (0~8점). 낮을수록 유리 (성장 대비 저평가)"""
    if peg <= 0:   return 0.0   # 적자 또는 데이터 없음
    if peg < 1.0:  return 8.0
    if peg < 2.0:  return 5.0
    if peg < 3.0:  return 2.0
    return 0.0


def score_rev_growth(growth: float) -> float:
    """매출성장률 점수 (0~7점). 이익 편향 보완 — 지속 성장 기업 포착"""
    if growth >= 0.30: return 7.0
    if growth >= 0.15: return 5.0
    if growth >= 0.05: return 3.0
    if growth >= 0.0:  return 1.0
    return 0.0   # 역성장


def score_fcf_margin(fcf_margin: float) -> float:
    """FCF 마진 점수 (0~5점). 이익의 현금화 품질 — 분식 회계 버퍼"""
    if fcf_margin >= 0.20: return 5.0
    if fcf_margin >= 0.10: return 3.0
    if fcf_margin >= 0.05: return 1.5
    if fcf_margin >= 0.0:  return 0.5
    return 0.0   # FCF 적자


def score_52w(pos: float) -> float:
    """52주 위치 점수 (0~20점). 신고가 근접 = 추세 확인"""
    if pos >= 0.85: return 20.0
    if pos >= 0.70: return 15.0
    if pos >= 0.55: return 10.0
    if pos >= 0.40: return 5.0
    return 1.0


# 금융·부동산 섹터 — D/E 필터 면제 대상
_FINANCIAL_SECTORS = {"Financial Services", "Financials", "Real Estate", "Banks"}


# ══════════════════════════════════════════
# 단일 종목 분석 (스레드 워커)
# ══════════════════════════════════════════
def _analyze_ticker(
    ticker: str,
    price_df: pd.DataFrame,
    spy_6m_ret: float,
    info: dict | None = None,   # [v4.1] 외부에서 주입 — 내부 재조회 불필요
) -> dict | None:
    """
    전략 D: 재무(40) + 기술(20) + 모멘텀 raw(퍼센타일은 별도 처리)
    price_df: 벌크 다운로드로 수신한 가격 데이터
    info: Step3에서 조회한 재무 dict (None이면 내부에서 재조회 — 폴백용)

    [v4.2] _sem 래핑 제거 — 가격 계산은 CPU 작업이므로 세마포어 불필요.
           info=None 폴백 시 get_ticker_info() 내부에서 _sem 획득하므로 충분.
           기존 래핑은 _fetch_info_with_retry(with _sem) 완료 후 재획득 시도 →
           workers=3 전부 점유 중일 때 main 스레드까지 대기하는 처리량 저하 유발.
    """
    try:
        if price_df is None or price_df.empty or len(price_df) < 60:
            return None

        # 거래정지 필터
        last_date = price_df.index[-1]
        if (datetime.now(KST).date() - last_date.date()).days > STRATEGY["max_stale_days"]:
            return None

        close = float(price_df["Close"].iloc[-1])
        if close <= 0:
            return None

        # ── 기술 지표 ──────────────────────────────────
        price_df = price_df.copy()
        price_df["Close"] = price_df["Close"].ffill()
        price_df["MA200"] = price_df["Close"].rolling(200, min_periods=200).mean()
        price_df["MA50"]  = price_df["Close"].rolling(50,  min_periods=50).mean()

        last   = price_df.iloc[-1]
        ma200  = last["MA200"]

        # MA200 위 필터 (하락 추세 제외)
        if pd.isna(ma200) or close < float(ma200):
            return None

        # 52주 위치
        w52 = price_df.iloc[-252:] if len(price_df) >= 252 else price_df
        high_52w = float(w52["High"].max())
        low_52w  = float(w52["Low"].min())
        w52_pos  = (close - low_52w) / (high_52w - low_52w) if high_52w > low_52w else 0.5

        # 모멘텀
        ref_6m  = float(price_df["Close"].iloc[-126]) if len(price_df) >= 126 else float(price_df["Close"].iloc[0])
        ref_12m = float(price_df["Close"].iloc[-252]) if len(price_df) >= 252 else float(price_df["Close"].iloc[0])
        ret_6m  = close / ref_6m  - 1
        ret_12m = close / ref_12m - 1
        rel_str = ret_6m - spy_6m_ret

        # ── 재무 데이터 ────────────────────────────────
        # 외부 주입 우선, 없으면 직접 조회 (폴백)
        if info is None:
            info = get_ticker_info(ticker)
        company_name = str(info.get("shortName", "") or ticker)
        sector  = str(info.get("sector", "") or "Unknown")
        roe     = float(info.get("returnOnEquity",  0) or 0) * 100
        margin  = float(info.get("profitMargins",   0) or 0) * 100
        peg     = float(info.get("pegRatio",         0) or 0)
        pe      = float(info.get("trailingPE",       0) or 0)
        pb      = float(info.get("priceToBook",      0) or 0)

        # [v4.3] 신규 재무지표
        rev_growth  = float(info.get("revenueGrowth",  0) or 0)   # 연간 매출성장률 (소수)
        total_rev   = float(info.get("totalRevenue",   0) or 0)
        free_cf     = float(info.get("freeCashflow",   0) or 0)
        fcf_margin  = (free_cf / total_rev) if total_rev > 0 else 0.0

        # [v4.3] D/E 필터 — 비금융 섹터만 적용
        # 금융·부동산은 레버리지 사업 구조상 D/E가 원래 높으므로 면제
        de_ratio = float(info.get("debtToEquity", 0) or 0)
        if sector not in _FINANCIAL_SECTORS and de_ratio > STRATEGY["de_ratio_max"]:
            return None

        # [v4.4] 재무 데이터 신선도 체크 — mostRecentQuarter(Unix timestamp)
        # 너무 오래된 재무 보고서를 가진 종목은 스코어링 신뢰도 낮음
        data_stale    = False
        fin_report_dt = None
        mrq_ts = info.get("mostRecentQuarter", 0) or 0
        if mrq_ts > 0:
            try:
                fin_report_dt = datetime.fromtimestamp(float(mrq_ts))
                age_days      = (datetime.now() - fin_report_dt).days
                if age_days > STRATEGY["fin_stale_skip_days"]:
                    # 재무 데이터가 너무 오래됨 → 완전 제외
                    return None
                data_stale = age_days > STRATEGY["fin_stale_warn_days"]
            except Exception:
                pass

        # ── 재무 점수 (40점) + 기술 점수 (20점) ────────
        # ROE(10) + 마진(10) + PEG(8) + 매출성장(7) + FCF마진(5) = 40점
        f_score = (
            score_roe(roe)
            + score_margin(margin)
            + score_peg(peg)
            + score_rev_growth(rev_growth)
            + score_fcf_margin(fcf_margin)
        )
        t_score    = score_52w(w52_pos)                   # 최대 20점
        base_score = f_score + t_score                    # 최대 60점

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
            # [v4.4] 재무 신선도
            "data_stale":     data_stale,
            "fin_report_dt":  fin_report_dt.strftime("%Y-%m-%d") if fin_report_dt else "",
        }
    except Exception as e:
        log.debug(f"[SKIP] {ticker}: {e}")
        return None


# ══════════════════════════════════════════
# [v4.4] 유니버스 스냅샷
# ══════════════════════════════════════════
def save_universe_snapshot(tickers: list[str]) -> None:
    """매월 리밸런싱 시 유니버스 종목 목록을 날짜별 파일로 저장.

    저장 위치: universe_snapshots/universe_YYYY-MM.json
    보존 개수: STRATEGY["universe_snapshot_keep"] 개월치 (초과분 자동 삭제)

    활용 목적:
      - 다음 달 스캔 시 종목 변동 추적 (생존자 편향 사후 분석)
      - 과거 유니버스 복원 가능 (추후 백테스트 개선 시 활용)
    """
    UNIVERSE_SNAPSHOT_DIR.mkdir(exist_ok=True)
    now_month = datetime.now(KST).strftime("%Y-%m")
    snap_file = UNIVERSE_SNAPSHOT_DIR / f"universe_{now_month}.json"
    snap_file.write_text(
        json.dumps({
            "month":   now_month,
            "date":    datetime.now(KST).strftime("%Y-%m-%d"),
            "count":   len(tickers),
            "tickers": tickers,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info(f"  유니버스 스냅샷 저장: {snap_file} ({len(tickers)}개)")

    # 오래된 스냅샷 정리 (keep 개수 초과분 삭제)
    keep = STRATEGY["universe_snapshot_keep"]
    snapshots = sorted(UNIVERSE_SNAPSHOT_DIR.glob("universe_*.json"))
    for old in snapshots[:-keep]:
        try:
            old.unlink()
            log.info(f"  오래된 스냅샷 삭제: {old.name}")
        except Exception as e:
            log.warning(f"  스냅샷 삭제 실패 ({old.name}): {e}")


def load_prev_universe_snapshot() -> list[str]:
    """직전 달 유니버스 스냅샷 로드. 없으면 빈 리스트 반환."""
    snapshots = sorted(UNIVERSE_SNAPSHOT_DIR.glob("universe_*.json"))
    now_month = datetime.now(KST).strftime("%Y-%m")
    # 현재 월 제외한 가장 최신 스냅샷
    prev_snaps = [s for s in snapshots if s.stem != f"universe_{now_month}"]
    if not prev_snaps:
        return []
    try:
        data = json.loads(prev_snaps[-1].read_text(encoding="utf-8"))
        return data.get("tickers", [])
    except Exception:
        return []


# ══════════════════════════════════════════
# [v4.3] VIX 시장 레짐 + 섹터 다양성
# ══════════════════════════════════════════
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
    """VIX 레벨에 따른 현금 비중 반환.
    정상(<30): 기본값(safe_asset_weight)
    주의(≥30): +20%p
    공포(≥40): +30%p
    """
    base = STRATEGY["safe_asset_weight"]
    cap  = STRATEGY["vix_cash_cap"]
    if vix >= STRATEGY["vix_fear"]:
        return min(base + 30.0, cap)
    if vix >= STRATEGY["vix_caution"]:
        return min(base + 20.0, cap)
    return base


def apply_sector_cap(df: pd.DataFrame, n: int, max_per_sector: int) -> pd.DataFrame:
    """점수 순으로 greedy 선택하되 동일 섹터 max_per_sector 초과 방지.

    Args:
        df: total_score, sector 컬럼 포함 DataFrame (내림차순 정렬 불필요)
        n: 선택할 종목 수
        max_per_sector: 동일 섹터 최대 허용 수
    Returns:
        선택된 n개 행의 DataFrame (reset_index)
    """
    sorted_df     = df.sort_values("total_score", ascending=False)
    sector_count: dict[str, int] = {}
    selected_rows = []
    for _, row in sorted_df.iterrows():
        sector = str(row.get("sector", "Unknown"))
        cnt    = sector_count.get(sector, 0)
        # [v4.5 버그수정] Unknown 섹터는 제한 룰 면제
        # yfinance 응답 누락으로 Unknown 분류된 우량주가 3종목 한도에 걸려 탈락하는 문제 방어
        if sector == "Unknown" or cnt < max_per_sector:
            selected_rows.append(row)
            sector_count[sector] = cnt + 1
        if len(selected_rows) >= n:
            break
    return pd.DataFrame(selected_rows).reset_index(drop=True)


# ══════════════════════════════════════════
# 리밸런싱 브리핑
# ══════════════════════════════════════════
def build_rebalancing_brief(
    prev: dict | None,
    new_holdings: list[dict],
    vix_level: float = 0.0,
    cash_weight: float | None = None,
) -> str:
    date_str   = datetime.now(KST).strftime("%Y년 %m월")
    next_month = (datetime.now(KST).replace(day=1) + timedelta(days=32)).strftime("%Y년 %m월")

    # VIX 레짐 라벨
    if vix_level >= STRATEGY["vix_fear"]:
        regime_str = f"🔴 공포 (VIX {vix_level:.1f}) — 현금 {cash_weight:.0f}%로 확대"
    elif vix_level >= STRATEGY["vix_caution"]:
        regime_str = f"🟡 주의 (VIX {vix_level:.1f}) — 현금 {cash_weight:.0f}%로 확대"
    elif vix_level > 0:
        regime_str = f"🟢 정상 (VIX {vix_level:.1f})"
    else:
        regime_str = "⚪ VIX 조회 불가"

    header = (
        f"📋 *{date_str} 미국주식 포트폴리오 리밸런싱*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📡 시장 레짐: {regime_str}\n"
        f"🗂 *신규 포트폴리오 (총 {len(new_holdings)}항목)*\n"
    )

    stale_tickers: list[str] = []   # [v4.4] stale 종목 수집

    portfolio_body = ""
    for h in new_holdings:
        if h["ticker"] == "CASH":
            portfolio_body += f"  💵 *{h['name']}*  비중 {h['weight']}%\n\n"
        else:
            # [v4.4] 재무 신선도 표시
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

    change_body = ""
    if prev and prev.get("holdings"):
        prev_map = {h["ticker"]: h for h in prev["holdings"]}
        new_map  = {h["ticker"]: h for h in new_holdings}
        exits    = set(prev_map) - set(new_map)
        entries  = set(new_map)  - set(prev_map)
        retained = set(prev_map) & set(new_map)

        change_body += "📊 *변경 내역*\n"
        for t in sorted(entries):
            h = new_map[t]
            if t != "CASH":
                change_body += f"  🟢 신규 편입: *{h['name']}* ({t}) {h['weight']}%\n"
        for t in sorted(exits):
            h = prev_map[t]
            if t != "CASH":
                change_body += f"  🔴 포트폴리오 제외: *{h['name']}* ({t})\n"
        for t in sorted(retained):
            p, n = prev_map[t], new_map[t]
            diff = round(n["weight"] - p["weight"], 1)
            name = f"*{n['name']}*" if t == "CASH" else f"*{n['name']}* ({t})"
            if diff > 0.5:
                change_body += f"  🔼 비중 확대: {name} {p['weight']}%→{n['weight']}% (+{diff}%p)\n"
            elif diff < -0.5:
                change_body += f"  🔽 비중 축소: {name} {p['weight']}%→{n['weight']}% ({diff}%p)\n"
            else:
                change_body += f"  ⚪ 유지: {name} {n['weight']}%\n"
        change_body += "\n"
    else:
        change_body = "📌 *첫 번째 포트폴리오 구성입니다*\n\n"

    # [v4.4] 데이터 품질 경고 섹션
    data_quality_body = ""
    if stale_tickers:
        data_quality_body = (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *데이터 신선도 경고* ({len(stale_tickers)}개 종목)\n"
            f"  재무 보고서 기준일이 {STRATEGY['fin_stale_warn_days']}일 이상 경과:\n"
            f"  {', '.join(stale_tickers)}\n"
            f"  → 해당 종목의 재무 점수는 신뢰도가 낮을 수 있습니다\n\n"
        )

    effective_cash = cash_weight if cash_weight is not None else STRATEGY["safe_asset_weight"]
    footer = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 *비중 적용 방법 (예: 총 $10,000)*\n"
        f"  안전 자산: ${effective_cash * 100:,.0f} 현금 보관\n"
        f"  나머지 주식: 비중(%) × $100씩 매수\n\n"
        f"📌 *전략: D 혼합 (백테스트 2015~2024 CAGR +19.49%)*\n"
        f"🗓 다음 리밸런싱: {next_month} 초\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔬 *편향 경고 (v4.4)*\n"
        f"  • 재무 데이터: yfinance 현재값 → 미래참조 편향 존재\n"
        f"    (⚠️ 표시 종목은 보고서 기준일 {STRATEGY['fin_stale_warn_days']}일+ 경과)\n"
        f"  • 유니버스: 현재 S&P500/나스닥100 구성 → 생존자 편향 존재\n"
        f"    (스냅샷은 universe_snapshots/ 폴더에 월별 보존)\n"
        f"  • 모멘텀(40점)은 가격 기반 → 상대적으로 신뢰도 높음\n"
        f"⚠️ 투자 판단은 본인 책임 — 참고 자료입니다"
    )

    return header + portfolio_body + change_body + data_quality_body + footer


# ══════════════════════════════════════════
# 성과 브리핑
# ══════════════════════════════════════════
def build_performance_brief(portfolio: dict) -> str:
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return "📭 보유 포트폴리오 없음"

    now_str     = datetime.now(KST).strftime("%Y-%m-%d")
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

    rows = []
    for h in holdings:
        if h["ticker"] == "CASH":
            rows.append({**h, "cur_price": h["entry_price"], "ret_pct": 0.0, "stale": False})
            continue
        try:
            df = yf.download(h["ticker"], start=start_fetch, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            cur_price = float(df["Close"].iloc[-1]) if not df.empty else h["entry_price"]
            stale     = df.empty
        except Exception:
            cur_price, stale = h["entry_price"], True

        ret_pct = (cur_price - h["entry_price"]) / h["entry_price"] * 100
        rows.append({**h, "cur_price": cur_price, "ret_pct": round(ret_pct, 2), "stale": stale})
        time.sleep(0.1)

    weighted_ret = sum(r["ret_pct"] * r["weight"] / 100 for r in rows)
    emoji_ret    = "📈" if weighted_ret >= 0 else "📉"

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

    footer = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 *포트폴리오 가중 수익률: {weighted_ret:+.2f}%* (USD 기준)\n"
        f"  (현금 {STRATEGY['safe_asset_weight']}% 포함 전체 계좌 기준)\n"
        f"⚠️ ⚠️ 표시: 시세 조회 실패 — 진입가로 대체\n"
        f"🗓 다음 리밸런싱에서 자동 갱신 예정"
    )

    return header + body + footer


# ══════════════════════════════════════════
# 메인 스캔
# ══════════════════════════════════════════
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


def _do_monthly_scan() -> None:
    now_month = datetime.now(KST).strftime("%Y-%m")
    if already_ran_this_month():
        return

    t_start = time.time()
    log.info(f"[리밸런싱] 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}")
    send_telegram(
        f"🔄 *{datetime.now(KST).strftime('%Y년 %m월')} 미국주식 리밸런싱 시작*\n"
        f"⚙️ D 전략 (재무40+기술20+모멘텀40) / 상위 {STRATEGY['portfolio_size']}종목\n"
        f"⏳ 약 15~30분 소요 (유니버스 ~550종목 분석)..."
    )

    try:
        # ── Step 1. 유니버스 + 스냅샷 저장 ──────────────────
        tickers = get_universe_tickers()

        # [v4.4] 유니버스 스냅샷 저장 — 생존자 편향 사후 분석용
        prev_universe = load_prev_universe_snapshot()
        save_universe_snapshot(tickers)
        if prev_universe:
            new_entries = set(tickers) - set(prev_universe)
            removed     = set(prev_universe) - set(tickers)
            if new_entries or removed:
                log.info(f"  유니버스 변동: 신규 +{len(new_entries)}개 / 제외 -{len(removed)}개")

        # ── Step 2. 가격 데이터 벌크 다운로드 + VIX 조회 ────
        log.info("[Step 2] 가격 데이터 벌크 다운로드...")
        price_start = (datetime.now(KST) - timedelta(days=420)).strftime("%Y-%m-%d")
        chunk_size  = STRATEGY["bulk_chunk_size"]

        # [v4.3] VIX 시장 레짐 확인 — 현금 비중 동적 조정용
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

        # SPY 벤치마크
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

        # 전체 유니버스 벌크 다운로드 (chunk_size개씩 나눠서)
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
                # 단일 종목이면 MultiIndex 없이 반환 — 처리 분기
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
                time.sleep(1.0)   # 청크 간 대기 — Yahoo 서버 부하 분산
            except Exception as e:
                log.warning(f"  벌크 다운로드 청크 {ci} 실패: {e} — 개별 재시도...")
                # 청크 실패 시 개별 재시도 (fallback)
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
                            time.sleep(2 ** attempt)   # 지수 백오프

        log.info(f"  가격 데이터 수신: {len(price_data)}개 / {len(tickers)}개")

        # ── Step 3. 재무 데이터 로딩 + 스코어링 ─────────────
        # [v4.1] 재무(info) 병렬 조회 — workers 줄이고 재시도 추가
        log.info("[Step 3] 재무 데이터 로딩 + 스코어링...")
        _load_info_cache()

        valid_tickers = list(price_data.keys())

        def _fetch_info_with_retry(ticker: str) -> dict:
            """재시도 포함 yfinance.info 조회"""
            cached = _info_cache.get(ticker)
            if cached:
                return cached
            for attempt in range(STRATEGY["info_retry"]):
                try:
                    with _sem:
                        info = yf.Ticker(ticker).info
                        time.sleep(0.3)   # 개별 대기 — 401 방지
                    with _info_cache_lock:
                        _info_cache[ticker] = info
                    return info
                except Exception as e:
                    if attempt < STRATEGY["info_retry"] - 1:
                        wait = STRATEGY["info_retry_delay"] * (2 ** attempt)
                        log.debug(f"  {ticker} info 재시도 {attempt+1} ({wait:.0f}초 대기): {e}")
                        time.sleep(wait)
            return {}

        scored = []
        with ThreadPoolExecutor(max_workers=STRATEGY["info_workers"]) as executor:
            futures = {
                executor.submit(_fetch_info_with_retry, t): t
                for t in valid_tickers
            }
            done = 0
            for future in as_completed(futures):
                done += 1
                ticker = futures[future]
                try:
                    # [v4.5 버그수정] future.result()로 info를 받아서 명시적 주입
                    # 기존: info 파라미터 미전달 → 캐시 재조회로 폴백 (외부주입 무용지물)
                    info_data = future.result()
                    result = _analyze_ticker(ticker, price_data[ticker], spy_6m, info=info_data)
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

        # ── Step 4. 모멘텀 퍼센타일 + 섹터 다양성 적용 ────
        df_s = pd.DataFrame(scored)
        df_s["mom_6m"]  = df_s["ret_6m"].rank(pct=True) * 20   # 0~20점
        df_s["mom_12m"] = df_s["ret_12m"].rank(pct=True) * 20  # 0~20점
        df_s["total_score"] = (
            df_s["base_score"] + df_s["mom_6m"] + df_s["mom_12m"]
        ).round(1)
        # 최대: 재무40 + 기술20 + 모멘텀40 = 100점

        # [v4.3] 섹터 다양성 제약 — 동일 섹터 최대 sector_max 종목
        top = apply_sector_cap(df_s, STRATEGY["portfolio_size"], STRATEGY["sector_max"])

        # 섹터 분포 로깅
        sector_dist = top["sector"].value_counts().to_dict()
        log.info(f"  섹터 분포: {sector_dist}")

        # ── Step 5. 비중 계산 (VIX 레짐 반영) ────────────
        stock_weight = 100.0 - cash_weight   # [v4.3] 고정 safe_asset_weight → 동적 cash_weight
        weights      = calc_stock_weights(top["total_score"].tolist(), stock_weight)

        # ── Step 6. 포트폴리오 빌드 ───────────────────────
        today_str      = datetime.now(KST).strftime("%Y-%m-%d")
        prev_portfolio = load_portfolio()
        prev_map       = {h["ticker"]: h for h in (prev_portfolio or {}).get("holdings", [])}

        new_holdings = [{
            "ticker":      "CASH",
            "name":        "안전 자산 (달러 예수금/MMF)",
            "weight":      float(cash_weight),   # [v4.3] VIX 레짐 반영
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
        )
        send_telegram_chunks(brief)

        # 재무 캐시 저장 (다음 실행 시 재활용)
        _save_info_cache()

        save_portfolio({"month": now_month, "holdings": new_holdings})
        _last_rebal_cache["month"] = now_month
        _save_last_rebal(now_month)

        log.info(f"[완료] 리밸런싱 완료 / {elapsed:.0f}초")
        for h in new_holdings:
            if h["ticker"] != "CASH":
                log.info(f"  {h['ticker']:8s} 비중:{h['weight']:5.1f}% 점수:{h['score']:.1f}")

    except Exception as e:
        log.exception(f"[ERROR] 스캔 예외: {e}")
        send_telegram(f"🚨 *리밸런싱 오류*\n```{e}```")


# ══════════════════════════════════════════
# 성과 점검 (매월 15일)
# ══════════════════════════════════════════
def job_performance_check() -> None:
    now = datetime.now(KST)
    if now.weekday() >= 5:
        return
    is_15th = (now.day == 15)
    is_monday_after_15th_weekend = (now.weekday() == 0 and now.day in (16, 17))
    if not (is_15th or is_monday_after_15th_weekend):
        return
    portfolio = load_portfolio()
    if not portfolio:
        return
    brief = build_performance_brief(portfolio)
    send_telegram_chunks(brief)
    log.info("[성과 점검] 완료")


# ══════════════════════════════════════════
# Heartbeat
# ══════════════════════════════════════════
def get_quick_portfolio_return(portfolio: dict) -> str:
    """Heartbeat용 가중 수익률 — 주식 종목만 계산 (CASH 제외)

    [v4.2] 개별 yf.download() 루프 → 벌크 1회 다운로드로 교체
           개별 반복 시 401 Invalid Crumb 유발 가능성 제거.
    """
    stock_holdings = [h for h in portfolio.get("holdings", []) if h["ticker"] != "CASH"]
    if not stock_holdings:
        return "0.00%"

    tickers     = [h["ticker"] for h in stock_holdings]
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

    # 벌크 다운로드 — 단일 세션으로 전종목 수신
    price_map: dict[str, float] = {}
    try:
        if len(tickers) == 1:
            raw = yf.download(tickers[0], start=start_fetch, progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            if not raw.empty:
                price_map[tickers[0]] = float(raw["Close"].iloc[-1])
        else:
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
        log.warning(f"Heartbeat 벌크 다운로드 실패: {e}")

    weighted_ret = 0.0
    for h in stock_holdings:
        cur = price_map.get(h["ticker"], h["entry_price"])
        ret           = (cur - h["entry_price"]) / h["entry_price"] * 100
        weighted_ret += ret * (h["weight"] / 100)
    return f"{weighted_ret:+.2f}%"


def _send_heartbeat() -> None:
    """별도 스레드에서 실행 — 스케줄러 블로킹 방지"""
    now       = datetime.now(KST)
    now_month = now.strftime("%Y-%m")
    status    = "✅ 완료" if already_ran_this_month() else "⏳ 오늘 07:10 실행 예정"
    portfolio = load_portfolio()

    if portfolio and portfolio.get("holdings"):
        pf_len  = len(portfolio["holdings"])
        ret_str = get_quick_portfolio_return(portfolio)
        pf_str  = f"총 {pf_len}항목 보유 중 (수익률: *{ret_str}*, USD)"
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


# ══════════════════════════════════════════
# 스케줄 잡
# ══════════════════════════════════════════
# ══════════════════════════════════════════
# Watchdog — 스케줄러 무응답 감지
# ══════════════════════════════════════════
_watchdog_last_tick: float = time.time()
_WATCHDOG_TIMEOUT_SEC = 600   # 10분 이상 틱 없으면 이상 감지

def _watchdog_loop() -> None:
    """[v4.2] 별도 데몬 스레드로 실행 — 스케줄 루프 생존 여부 감시.
    10분 이상 메인 루프 틱이 없으면 텔레그램 경보 발송.
    """
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
            # 경보 후 타이머 리셋 — 중복 발송 방지
            global _watchdog_last_tick
            _watchdog_last_tick = time.time()


def job_monthly_scan() -> None:
    threading.Thread(target=_run_scan_in_thread, daemon=True).start()


def job_daily_rebal_check() -> None:
    if datetime.now(KST).weekday() >= 5:
        return
    if not already_ran_this_month():
        log.info("당월 미실행 → 스캔 트리거")
        job_monthly_scan()


# ══════════════════════════════════════════
# 메인
# ══════════════════════════════════════════
if __name__ == "__main__":
    schedule.every().day.at("07:00", "Asia/Seoul").do(job_heartbeat)
    schedule.every().day.at("07:00", "Asia/Seoul").do(job_performance_check)  # 15일에만 실제 실행
    schedule.every().day.at("07:10", "Asia/Seoul").do(job_daily_rebal_check)  # 한국 봇(08:50~09:10)과 충돌 회피

    log.info("✅ 미국주식 장기 투자 스캐너 v4.5 시작")
    log.info(f"  전략: D 혼합 / 상위 {STRATEGY['portfolio_size']}종목 / 현금 {STRATEGY['safe_asset_weight']}%")
    log.info("  ⏰ 07:00 Heartbeat + 성과 점검(15일) — 전날 미국 장 종가 기준")
    log.info("  ⏰ 07:10 리밸런싱 체크 (한국 봇과 시간 분산)")
    log.info(f"  📝 로그: {LOG_FILE}")

    # 서버 재시작 알림 (항상 발송)
    send_telegram(
        f"✅ *미국주식 장기 투자 스캐너 v4.3 시작*\n"
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

    # [v4.2] Watchdog 데몬 스레드 시작
    threading.Thread(target=_watchdog_loop, daemon=True, name="watchdog").start()
    log.info("  🐕 Watchdog 시작 (무응답 감지 10분)")

    while True:
        schedule.run_pending()
        _watchdog_last_tick = time.time()   # [v4.2] 스케줄러 생존 신호
        time.sleep(1)
