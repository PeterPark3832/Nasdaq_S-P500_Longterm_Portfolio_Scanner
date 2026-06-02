"""
미국 주식 장기 투자 포트폴리오 스캐너 v4.11
────────────────────────────────────────────────────────
v3.1(한국주식) → v4.0(미국주식) 전면 전환

v4.10 → v4.11 개별 종목 스톱로스 경보 (Stage 8):
  [신규] _check_and_alert_stoploss() — 매일 Heartbeat에서 개별 종목 손실 감지
         진입가 대비 stoploss_threshold(-20%) 이하 손실 종목 텔레그램 즉시 경보
         포트폴리오 MDD가 울리지 않아도 개별 종목 급락 조기 포착 가능
         per-ticker 1일 쿨다운(last_stoploss_alerts: {ticker: date}): 중복 발송 방지
  [개선] /status 종목 목록에 진입가 대비 현재 손실% 추가 표시
         스톱로스 임계 도달 시 🔴, 임계 50% 초과(경고 구간) 시 🟡 표시
  [개선] /help 명령어 설명 갱신
  [보안] 리밸런싱 시 last_stoploss_alerts 초기화 — 새 포지션 기준으로 재시작

v4.0 → v4.1 안정성 개선:
  [핵심] yfinance 401 Invalid Crumb 해결
         개별 yf.download() × 168회 → yf.download([list]) 벌크 다운로드
         단일 세션으로 전종목 수신 → Yahoo 봇 감지 회피
  [개선] 재무(info) 병렬 workers 8→3 축소 + 재시도 로직 (지수 백오프)
  [개선] 벌크 청크 실패 시 개별 재시도 fallback 추가
  [개선] _analyze_ticker에 info 외부 주입 → 중복 조회 제거

v4.9 → v4.10 인트라월 드리프트 경보 (Stage 7):
  [신규] _check_and_alert_drift() — 매일 Heartbeat에서 비중 드리프트 감지
         CASH 불변, 주식은 (진입비중 × 현재가/진입가) 정규화로 현재 비중 재계산
         목표 비중 대비 ±drift_alert_threshold(10%p) 이상 이탈 시 텔레그램 경보
         1일 쿨다운(last_drift_alert_date): 중복 발송 방지
  [개선] /status 보유 종목 표시에 현재 비중 + 드리프트(%p) 추가
         임계 초과 시 ⚠️ 표시 → 비중 이탈 종목 즉시 확인 가능
  [개선] /help 명령어 설명 갱신

v4.8 → v4.9 텔레그램 양방향 제어 (Stage 6):
  [신규] 텔레그램 Long-polling 명령어 수신 — _telegram_poll_loop() 데몬 스레드
         별도 서버/webhook 없이 getUpdates API로 명령어 수신
  [신규] 명령어 4종:
         /status — 포트폴리오 현황 + 수익률 + 낙폭 즉시 조회
         /scan   — 수동 리밸런싱 강제 실행 (평일만, 중복 실행 방지)
         /perf   — 성과 점검 즉시 실행 (벤치마크 비교 포함)
         /help   — 명령어 목록
  [보안] TELEGRAM_CHAT_IDS에 등록된 chat_id만 명령어 수락
         미등록 chat_id 명령어 무시 + 로그 기록
  [보안] chat_id 비교 시 str 정규화 + strip() — int/str 혼용 타입 우회 공격 방지
         루프 진입 시 _allowed_ids = {str(cid).strip() for cid in TELEGRAM_CHAT_IDS} 선계산
  [안정성] _telegram_poll_loop while True 내부 try-except Exception 추가
           네트워크 오류 등 예외 발생 시 5초 대기 후 재시도 (데몬 스레드 사망 방지)

v4.7 → v4.8 MDD 아키텍처 재설계:
  [개선] MDD 기반을 performance_history.json → portfolio_state_us.json의 max_equity 필드로 전환
         기존 문제: 한 달 내내 하락만 하면 period_rets에 기록된 값이 이미 최저이므로
         peak = current_ret → drawdown = 0 → 경보 영구 침묵하는 논리적 결함 수정
  [신규] _check_and_alert_mdd() — 매일 Heartbeat에서 MDD 체크
         portfolio["max_equity"]에 이번 달 포트폴리오 고점 수익률 누적 갱신
         낙폭 < mdd_alert_threshold 시 텔레그램 경보 + 1일 쿨다운(중복 발송 방지)
  [신규] 리밸런싱 시 max_equity=0.0 리셋 — 새 포트폴리오 기준으로 MDD 재시작
  [개선] get_quick_portfolio_return float 반환으로 변경 → 호출부에서 직접 연산 가능
  [개선] Heartbeat 메시지에 낙폭 표시 추가 (낙폭 -3% 이하 시만 노출)
  [삭제] check_mdd_alert() 제거 (history 기반 MDD — 논리 결함으로 폐기)

v4.6 → v4.7 성과 추적 & 벤치마크 비교 (Stage 5):
  [신규] 월별 성과 이력 저장 — performance_history.json
         리밸런싱 완료 + 15일 성과 점검 시마다 수익률 snapshot 자동 저장
         월별 포트폴리오 수익률 / SPY·QQQ 수익률 / 알파 이력 보관 (최대 24건)
  [신규] 벤치마크 비교 — 15일 성과 점검에 SPY·QQQ 동기간 수익률 추가
         포트폴리오 구성 기준월 초(月初)부터 현재까지 수익률 비교
         초과 수익률(알파 vs SPY) 자동 계산 + 표시
  [신규] MDD 드로다운 경보 — check_mdd_alert()
         성과 이력에서 포트폴리오 가중 수익률 고점 추적
         고점 대비 mdd_alert_threshold(-15%p) 이하 낙폭 발생 시 즉시 텔레그램 경보
         성과 점검 브리핑에 현재 낙폭 / 고점 표시 추가

v4.5 → v4.6 실전 운용 강화 (Stage 4):
  [신규] build_trade_checklist() — 매매 실행 체크리스트 자동 생성
         매도 → 비중 축소 → 비중 확대 → 신규 매수 순서 정렬 (유동성 확보 후 매수)
         리밸런싱 브리핑 마지막 섹션으로 자동 포함
  [버그] build_performance_brief 개별 yf.download 루프 → 벌크 1회로 교체
         Stage 1에서 Heartbeat만 수정, 15일 성과 점검은 여전히 개별 루프였던 문제 수정
  [개선] 스캔 중간 진행 텔레그램 알림 추가
         Step 2 완료(가격 로딩) / Step 3 완료(재무 분석) 시 즉시 발송
         30분 스캔 동안 생존 확인 및 진행 상황 파악 가능

v4.4 → v4.5 버그 수정:
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

    # ── [v4.7] Stage 5 성과 추적 파라미터 ──────────────────
    # 5-3. MDD 드로다운 경보
    # 성과 이력 내 포트폴리오 가중 수익률 고점 대비 낙폭이 이 값 이하이면 경보
    "mdd_alert_threshold": -15.0,  # 고점 대비 낙폭 임계값 (%)
    # 5-1. 성과 이력 보존 건수
    "perf_history_keep":    500,   # 최대 보존 건수 (일별 기록 → 약 2년치)

    # ── [v4.10] Stage 7 인트라월 드리프트 파라미터 ──────────
    # 리밸런싱 이후 개별 종목 비중이 목표 비중 대비 이 값 이상 벗어나면 경보
    # 비중 계산: CASH 불변, 주식은 (진입비중 × 현재가/진입가) 정규화
    # [백테스트 근거 없음] — 실전 운용 경험 기반 보수적 값. 필요 시 조정
    "drift_alert_threshold": 10.0,  # 비중 이탈 임계값 (%p, 절댓값)

    # ── [v4.11] Stage 8 개별 종목 스톱로스 파라미터 ──────────
    # 개별 종목이 진입가 대비 이 값 이하로 손실 시 텔레그램 즉시 경보
    # MDD(포트폴리오 전체 고점 낙폭)와 별개 — 소수 종목 급락 단독 포착
    # 경고 구간: stoploss_threshold × 0.5 초과 시 🟡 (임계의 절반 초과)
    # [백테스트 근거 없음] — 개별 종목 -20% 이하 시 전략적 재검토 일반 기준
    "stoploss_threshold": -20.0,  # 진입가 대비 손실 임계값 (%)
}

# ==========================================
# 파일 경로
# ==========================================
PORTFOLIO_FILE          = Path("portfolio_state_us.json")
PORTFOLIO_PREV_FILE     = Path("portfolio_prev_us.json")   # [dashboard] 리밸런싱 직전 이전 포트폴리오
LAST_REBAL_FILE         = Path("last_rebal_us.json")
INFO_CACHE_FILE         = Path("yf_info_cache.json")         # 재무 캐시 (재시작 시 재활용)
UNIVERSE_SNAPSHOT_DIR   = Path("universe_snapshots")         # [v4.4] 월별 유니버스 스냅샷 디렉터리
PERFORMANCE_HISTORY_FILE = Path("performance_history.json")  # [v4.7] 월별 성과 이력

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
    # [v4.11.1] bytes 기준 Telegram 4096 byte 제한 준수 (한글 1자=3bytes)
    if len(text.encode("utf-8")) <= 4000:
        send_telegram(text, topic_id=topic_id)
        return
    lines, current = text.split("\n"), ""
    for line in lines:
        if len((current + line + "\n").encode("utf-8")) > 3800:
            if current.strip():
                send_telegram(current.strip(), topic_id=topic_id)
                time.sleep(0.5)
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        send_telegram(current.strip(), topic_id=topic_id)


def _reply_to(chat_id: str, text: str) -> None:
    """[v4.9] 명령어 응답 전용 — 특정 chat_id로만 발송.

    send_telegram()은 TELEGRAM_CHAT_IDS 전체에 broadcast.
    명령어 응답은 요청한 채팅방에만 보내는 것이 올바른 UX.
    슈퍼그룹 topic 지원은 send_telegram()과 동일하게 처리.
    """
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
            log.error(f"_reply_to 실패 ({chat_id}): {res.text}")
    except Exception as e:
        log.error(f"_reply_to 예외 ({chat_id}): {e}")


def _reply_to_chunks(chat_id: str, text: str) -> None:
    """[v4.9] 긴 메시지용 _reply_to — 4000자 초과 시 분할 발송."""
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
# 상태 관리
# ══════════════════════════════════════════
def load_portfolio() -> dict | None:
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"포트폴리오 파일 읽기 실패: {e}")
    return None


REBALANCING_CHANGES_FILE = Path(__file__).parent / "rebalancing_changes.json"
PORTFOLIO_PREV_FILE      = Path(__file__).parent / "portfolio_prev_us.json"

def _save_rebalancing_changes(prev: dict | None, new_holdings: list[dict]) -> None:
    prev_map = {h["ticker"]: h for h in (prev or {}).get("holdings", [])}
    new_map  = {h["ticker"]: h for h in new_holdings}
    result   = {
        "date":      datetime.now(KST).strftime("%Y-%m-%d"),
        "month":     datetime.now(KST).strftime("%Y-%m"),
        "new":       [], "exited": [], "increased": [],
        "decreased": [], "unchanged": [],
    }
    for t in set(new_map) | set(prev_map):
        if t == "CASH":
            continue
        c, p = new_map.get(t), prev_map.get(t)
        if c and not p:
            result["new"].append(c)
        elif p and not c:
            result["exited"].append(p)
        else:
            diff = round(c["weight"] - p["weight"], 2)
            enriched = {**c, "prev_weight": p["weight"], "weight_diff": diff}
            if diff > 0.5:
                result["increased"].append(enriched)
            elif diff < -0.5:
                result["decreased"].append(enriched)
            else:
                result["unchanged"].append(enriched)
    try:
        REBALANCING_CHANGES_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("변경 내역 저장 -> rebalancing_changes.json")
    except Exception as e:
        log.warning(f"변경 내역 저장 실패: {e}")

def save_portfolio(data: dict) -> None:
    if PORTFOLIO_FILE.exists():
        try:
            PORTFOLIO_PREV_FILE.write_text(
                PORTFOLIO_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as e:
            log.warning(f"이전 포트폴리오 백업 실패: {e}")
    PORTFOLIO_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"포트폴리오 저장 -> {PORTFOLIO_FILE}")


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

    stale_tickers: list[str] = []

    portfolio_body = ""
    for h in new_holdings:
        if h["ticker"] == "CASH":
            portfolio_body += f"  💵 현금  {h['weight']}%\n"
        else:
            stale_flag = "⚠️" if h.get("data_stale") else ""
            if h.get("data_stale"):
                stale_tickers.append(h["ticker"])
            sector_short = (h.get("sector") or "?").replace("Communication Services", "Comm.").replace("Consumer Discretionary", "Cons.Disc").replace("Basic Materials", "소재")
            portfolio_body += (
                f"  *{h['ticker']}* {stale_flag}  {h['weight']}% | {h['score']}pt | {sector_short}\n"
                f"  ${h['entry_price']:,.0f} | 6M {h['ret_6m']:+.1f}% | ROE {h['roe']:.0f}%\n"
            )

    change_body = ""
    if prev and prev.get("holdings"):
        prev_map = {h["ticker"]: h for h in prev["holdings"]}
        new_map  = {h["ticker"]: h for h in new_holdings}
        exits    = set(prev_map) - set(new_map)
        entries  = set(new_map)  - set(prev_map)
        retained = set(prev_map) & set(new_map)

        new_parts  = [f"🟢 {t} {new_map[t]['weight']}%"  for t in sorted(entries)  if t != "CASH"]
        exit_parts = [f"🔴 {t}"                           for t in sorted(exits)    if t != "CASH"]
        up_parts   = []
        dn_parts   = []
        for t in sorted(retained):
            if t == "CASH":
                continue
            diff = round(new_map[t]["weight"] - prev_map[t]["weight"], 1)
            if diff > 0.5:
                up_parts.append(f"🔼 {t} {prev_map[t]['weight']}→{new_map[t]['weight']}%")
            elif diff < -0.5:
                dn_parts.append(f"🔽 {t} {prev_map[t]['weight']}→{new_map[t]['weight']}%")

        change_body = "📊 *변경 내역*\n"
        if new_parts:  change_body += "  " + "  ".join(new_parts)  + "\n"
        if exit_parts: change_body += "  " + "  ".join(exit_parts) + "\n"
        if up_parts:   change_body += "  " + "  ".join(up_parts)   + "\n"
        if dn_parts:   change_body += "  " + "  ".join(dn_parts)   + "\n"
        change_body += "\n"
    else:
        change_body = "📌 *첫 번째 포트폴리오 구성*\n\n"

    stale_body = (
        f"⚠️ 재무구식: {', '.join(stale_tickers)}\n"
        if stale_tickers else ""
    )

    footer = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗓 다음 리밸런싱: {next_month} 초\n"
        f"⚠️ 투자 판단은 본인 책임"
    )

    return header + portfolio_body + "\n" + change_body + stale_body + footer


# ══════════════════════════════════════════
# [v4.7] 성과 이력 관리
# ══════════════════════════════════════════
def load_performance_history() -> list[dict]:
    """성과 이력 파일 로드. 없거나 파싱 실패 시 빈 리스트."""
    if not PERFORMANCE_HISTORY_FILE.exists():
        return []
    try:
        return json.loads(PERFORMANCE_HISTORY_FILE.read_text(encoding="utf-8")).get("records", [])
    except Exception as e:
        log.warning(f"성과 이력 로드 실패: {e}")
        return []


def save_performance_record(
    record_type: str,           # "rebalancing" | "performance_check"
    portfolio_ret_pct: float,
    spy_ret_pct: float | None = None,
    qqq_ret_pct: float | None = None,
) -> None:
    """성과 스냅샷을 이력 파일에 추가 저장.

    같은 날짜 + 같은 type이면 덮어씀 (중복 방지).
    perf_history_keep 초과 시 오래된 것부터 삭제.
    """
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    new_rec = {
        "date":              today_str,
        "month":             datetime.now(KST).strftime("%Y-%m"),
        "type":              record_type,
        "portfolio_ret_pct": round(portfolio_ret_pct, 2),
        "spy_ret_pct":       round(spy_ret_pct, 2) if spy_ret_pct is not None else None,
        "qqq_ret_pct":       round(qqq_ret_pct, 2) if qqq_ret_pct is not None else None,
        "alpha_vs_spy":      round(portfolio_ret_pct - spy_ret_pct, 2)
                             if spy_ret_pct is not None else None,
    }
    records = load_performance_history()
    # 같은 날 + 같은 type 제거 (재실행 시 덮어쓰기)
    records = [r for r in records if not (r["date"] == today_str and r["type"] == record_type)]
    records.append(new_rec)
    # 최대 보존 건수 제한
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



# ══════════════════════════════════════════
# [v4.6] 매매 실행 체크리스트
# ══════════════════════════════════════════
def build_trade_checklist(prev: dict | None, new_holdings: list[dict]) -> str:
    """이번 달 매매 실행 순서 목록.

    유동성 확보를 위해 매도/축소를 먼저 실행한 뒤 매수/확대하는 순서로 정렬.
      1. 전량 매도  — 포트폴리오 이탈 종목
      2. 비중 축소  — 기존 보유 / 비중 감소
      3. 비중 확대  — 기존 보유 / 비중 증가
      4. 신규 매수  — 신규 편입 종목
      5. 유지       — 변경 없음 (참고용)
    """
    new_map = {h["ticker"]: h for h in new_holdings if h["ticker"] != "CASH"}

    if not prev or not prev.get("holdings"):
        # 첫 구성: 전부 신규 매수
        lines = ["📋 *매매 실행 목록 (첫 구성 — 전종목 신규 매수)*"]
        for h in new_holdings:
            if h["ticker"] != "CASH":
                lines.append(f"  🟢 신규 매수: *{h['name']}* ({h['ticker']}) {h['weight']}%")
        lines.append("\n  ※ CASH 항목은 달러 예수금/MMF로 보유")
        return "\n".join(lines)

    prev_map = {h["ticker"]: h for h in prev["holdings"] if h["ticker"] != "CASH"}

    sells     = []   # 전량 매도
    reduces   = []   # 비중 축소
    increases = []   # 비중 확대
    buys      = []   # 신규 매수
    holds     = []   # 유지

    for ticker, ph in prev_map.items():
        if ticker not in new_map:
            sells.append(f"  🔴 *전량 매도*: {ph['name']} ({ticker}) — 현재 {ph['weight']}% 전량")
        else:
            nh   = new_map[ticker]
            diff = round(nh["weight"] - ph["weight"], 1)
            if diff < -0.5:
                reduces.append(
                    f"  🔽 *비중 축소*: {nh['name']} ({ticker}) "
                    f"{ph['weight']}% → {nh['weight']}% ({diff:+.1f}%p)"
                )
            elif diff > 0.5:
                increases.append(
                    f"  🔼 *비중 확대*: {nh['name']} ({ticker}) "
                    f"{ph['weight']}% → {nh['weight']}% ({diff:+.1f}%p)"
                )
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


# ══════════════════════════════════════════
# 성과 브리핑
# ══════════════════════════════════════════
def build_performance_brief(portfolio: dict) -> str:
    """15일 성과 점검 브리핑.

    [v4.6] 개별 yf.download() 루프 → 벌크 1회 다운로드로 교체.
           Stage 1에서 Heartbeat만 수정했고 성과 점검은 누락되어 있던 문제 수정.
           단일 세션으로 전종목 수신 → 401 Invalid Crumb 재발 가능성 제거.
    """
    holdings = portfolio.get("holdings", [])
    if not holdings:
        return "📭 보유 포트폴리오 없음"

    now_str     = datetime.now(KST).strftime("%Y-%m-%d")
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")

    stock_holdings = [h for h in holdings if h["ticker"] != "CASH"]
    tickers        = [h["ticker"] for h in stock_holdings]

    # 벌크 다운로드 — 단일 세션으로 전종목 수신 (401 방지)
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
            raw = yf.download(
                tickers, start=start_fetch,
                group_by="ticker", auto_adjust=True,
                progress=False, threads=True,
            )
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

    # [v4.7] 벤치마크 비교 — SPY·QQQ 동기간 수익률
    # 포트폴리오 구성 기준월 초(月初)부터 현재까지 수익률 계산
    port_month  = portfolio.get("month", "")
    bench_ref   = f"{port_month}-01" if port_month else start_fetch
    spy_ret: float | None = None
    qqq_ret: float | None = None
    try:
        bench_raw = yf.download(
            ["SPY", "QQQ"], start=bench_ref,
            progress=False, auto_adjust=True,
        )
        for sym in ["SPY", "QQQ"]:
            try:
                if isinstance(bench_raw.columns, pd.MultiIndex):
                    if ("Close", sym) in bench_raw.columns:
                        s = bench_raw[("Close", sym)].dropna()
                    elif (sym, "Close") in bench_raw.columns:
                        s = bench_raw[(sym, "Close")].dropna()
                    else:
                        s = bench_raw.xs(sym, axis=1, level=1)["Close"].dropna()
                else:
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

    # [v4.8] 이력 저장 (MDD 경보는 Heartbeat에서 처리 — 여기서는 저장만)
    save_performance_record("performance_check", weighted_ret, spy_ret, qqq_ret)

    # [v4.8] portfolio["max_equity"] 기반 낙폭 계산 (history 기반 MDD 제거)
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

    # [v4.7] 벤치마크 비교 섹션
    bench_body = "━━━━━━━━━━━━━━━━━━\n📊 *수익률 비교* (기준: {ref})\n".format(
        ref=bench_ref if port_month else "최근 10일"
    )
    bench_body += f"  포트폴리오: *{weighted_ret:+.2f}%*\n"
    if spy_ret is not None:
        alpha = weighted_ret - spy_ret
        alpha_icon = "✅" if alpha >= 0 else "❌"
        bench_body += f"  SPY:        {spy_ret:+.2f}%  ({alpha_icon} 알파 {alpha:+.2f}%p)\n"
    if qqq_ret is not None:
        bench_body += f"  QQQ:        {qqq_ret:+.2f}%\n"

    # [v4.7] MDD 표시
    dd_icon  = "🟢" if drawdown > -5 else ("🟡" if drawdown > -10 else "🔴")
    mdd_line = f"  {dd_icon} 고점 대비 낙폭: {drawdown:+.1f}%p (고점 {peak_ret:+.1f}%)\n"

    footer = (
        bench_body
        + mdd_line
        + f"\n⚠️ ⚠️ 표시: 시세 조회 실패 — 진입가로 대체\n"
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

        # [v4.6] Step 2 완료 중간 알림
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

        # [v4.6] Step 3 완료 중간 알림
        elapsed_s3 = time.time() - t_start
        send_telegram(
            f"✅ *[Step 3 완료]* 재무 분석 완료 ({elapsed_s3:.0f}초)\n"
            f"  필터 통과: {len(scored)}/{len(valid_tickers)}개\n"
            f"⏳ 최종 순위 산정 + 브리핑 생성 중..."
        )

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

        # [v4.11.1] 변경 내역 저장 + 이전 포트폴리오 백업 (대시보드용)
        _save_rebalancing_changes(prev_portfolio, new_holdings)

        save_portfolio({
            "month":                now_month,
            "holdings":             new_holdings,
            "max_equity":           0.0,   # [v4.8] 새 포트폴리오 기준 MDD 재시작
            "last_stoploss_alerts": {},    # [v4.11] 새 진입가 기준 스톱로스 재시작
        })
        _last_rebal_cache["month"] = now_month
        _save_last_rebal(now_month)

        # [v4.7] 리밸런싱 시점 성과 이력 저장 (진입가 기준 → 수익률 0.0%)
        # 새 포트폴리오 구성 직후이므로 수익률은 0 기준으로 기록
        # SPY/QQQ 기준점도 함께 저장 (다음 비교 기준용)
        save_performance_record("rebalancing", portfolio_ret_pct=0.0)

        log.info(f"[완료] 리밸런싱 완료 / {elapsed:.0f}초")
        for h in new_holdings:
            if h["ticker"] != "CASH":
                log.info(f"  {h['ticker']:8s} 비중:{h['weight']:5.1f}% 점수:{h['score']:.1f}")

    except Exception as e:
        log.exception(f"[ERROR] 스캔 예외: {e}")
        send_telegram(f"🚨 *리밸런싱 오류*\n```{e}```")


# ══════════════════════════════════════════
# 성과 점검 (매일 장 종료 후)
# ══════════════════════════════════════════
def job_performance_check() -> None:
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 주말 제외
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
def get_quick_portfolio_return(portfolio: dict) -> float:
    """Heartbeat용 가중 수익률 — float(%) 반환. 주식 종목만 계산 (CASH 제외).

    [v4.2] 개별 yf.download() 루프 → 벌크 1회 다운로드로 교체
           개별 반복 시 401 Invalid Crumb 유발 가능성 제거.
    [v4.8] 반환 타입 str → float 변경 (MDD 연산 및 Heartbeat 표시에서 직접 활용).
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
    return weighted_ret   # float(%) — 호출부에서 포맷팅


def _update_max_equity(portfolio: dict, current_ret: float) -> float:
    """현재 수익률로 max_equity(이번 달 포트폴리오 고점) 갱신.

    [v4.8] portfolio_state_us.json에 max_equity 필드 보존.
    고점 갱신 시에만 파일 저장 → I/O 최소화.
    리밸런싱 시 max_equity=0.0으로 리셋 → 새 포트폴리오 기준 MDD 재시작.
    """
    old_max = float(portfolio.get("max_equity", current_ret))
    new_max = max(old_max, current_ret)
    if new_max > old_max:
        portfolio["max_equity"] = new_max
        save_portfolio(portfolio)
    return new_max


def _check_and_alert_mdd(portfolio: dict, current_ret: float) -> float:
    """MDD 경보 체크. 낙폭이 임계값 이하이면 텔레그램 발송.

    [v4.8] portfolio["max_equity"] 기반 — 매일 Heartbeat에서 호출.
    1일 쿨다운(last_mdd_alert_date): 매일 경보 중복 발송 방지.

    Args:
        portfolio: 현재 포트폴리오 dict (max_equity 필드 포함)
        current_ret: 현재 포트폴리오 가중 수익률 (%)
    Returns:
        drawdown (%p) — Heartbeat 메시지 표시용
    """
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


def _check_and_alert_drift(portfolio: dict) -> list[dict]:
    """[v4.10] 인트라월 비중 드리프트 감지 + 텔레그램 경보.

    리밸런싱 이후 개별 종목의 현재 비중(가격 변동 반영)이
    목표 비중 대비 drift_alert_threshold 이상 벗어나면 경보 발송.
    1일 쿨다운(last_drift_alert_date): 같은 날 중복 발송 방지.

    비중 계산 방식:
      - CASH 비중: 진입 비중 그대로 (가치 불변)
      - 주식 비중: (진입 비중 × 현재가/진입가) → 전체 대비 정규화
      급등 종목 비중 과다 / 급락 종목 비중 과소 양쪽 모두 포착

    Returns:
        drifted: 이탈 종목 리스트 [{ticker, target_w, current_w, drift}, ...]
                 (Heartbeat 로그용 — 경보 없으면 빈 리스트)
    """
    threshold = STRATEGY["drift_alert_threshold"]
    today_str = datetime.now(KST).strftime("%Y-%m-%d")

    # 1일 쿨다운 — 오늘 이미 경보 발송 시 가격 조회도 생략
    if portfolio.get("last_drift_alert_date", "") == today_str:
        return []

    stock_holdings = [h for h in portfolio.get("holdings", []) if h["ticker"] != "CASH"]
    cash_holdings  = [h for h in portfolio.get("holdings", []) if h["ticker"] == "CASH"]
    if not stock_holdings:
        return []

    # ── 현재가 벌크 조회 ──────────────────────────────────────
    tickers     = [h["ticker"] for h in stock_holdings]
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")
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
        log.warning(f"드리프트 체크 가격 조회 실패: {e}")
        return []

    # ── 현재 비중 재계산 ─────────────────────────────────────
    # CASH는 가치 불변, 주식은 (진입비중 × 수익배수)로 상대 가중치 산정
    cash_val = sum(h["weight"] for h in cash_holdings)
    stock_vals: dict[str, float] = {}
    for h in stock_holdings:
        cur  = price_map.get(h["ticker"], h["entry_price"])
        mult = (cur / h["entry_price"]) if h["entry_price"] > 0 else 1.0
        stock_vals[h["ticker"]] = h["weight"] * mult

    total_val = cash_val + sum(stock_vals.values())
    if total_val <= 0:
        return []

    # ── 임계 초과 종목 수집 ──────────────────────────────────
    drifted: list[dict] = []

    # 1. 주식 드리프트 검사
    for h in stock_holdings:
        target_w  = h["weight"]
        current_w = stock_vals[h["ticker"]] / total_val * 100
        drift     = current_w - target_w
        if abs(drift) >= threshold:
            drifted.append({
                "ticker":    h["ticker"],
                "target_w":  target_w,
                "current_w": current_w,
                "drift":     drift,
            })

    # 2. CASH 드리프트 검사 — 주식 급등 시 현금 비중 희석 포착
    if cash_holdings:
        target_cash_w  = cash_val   # 진입 시 현금 비중 합계 (불변)
        current_cash_w = cash_val / total_val * 100
        cash_drift     = current_cash_w - target_cash_w
        if abs(cash_drift) >= threshold:
            drifted.append({
                "ticker":    "CASH",
                "target_w":  target_cash_w,
                "current_w": current_cash_w,
                "drift":     cash_drift,
            })

    if not drifted:
        return []

    # ── 경보 발송 ────────────────────────────────────────────
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


def _check_and_alert_stoploss(portfolio: dict) -> None:
    """[v4.11] 개별 종목 스톱로스 경보 체크. 매일 Heartbeat에서 호출.

    진입가 대비 stoploss_threshold 이하 손실 발생 시 텔레그램 즉시 경보.
    포트폴리오 MDD 경보와 별개 — 소수 종목의 단독 급락도 조기 포착.
    per-ticker 1일 쿨다운(last_stoploss_alerts): 매일 중복 발송 방지.
    리밸런싱 시 last_stoploss_alerts 초기화 — 새 진입가 기준으로 재시작.
    """
    stock_holdings = [h for h in portfolio.get("holdings", []) if h["ticker"] != "CASH"]
    if not stock_holdings:
        return

    threshold    = STRATEGY["stoploss_threshold"]          # 음수, 예: -20.0
    warn_level   = threshold * 0.5                         # 경고 구간: 임계의 50% (예: -10.0)
    today_str    = datetime.now(KST).strftime("%Y-%m-%d")
    last_alerts: dict[str, str] = portfolio.get("last_stoploss_alerts", {})

    # ── 현재가 벌크 조회 ───────────────────────────────────────
    tickers     = [h["ticker"] for h in stock_holdings]
    start_fetch = (datetime.now(KST) - timedelta(days=10)).strftime("%Y-%m-%d")
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
        log.warning(f"[스톱로스 체크] 가격 조회 실패: {e}")
        return

    # ── 종목별 손실 계산 + 경보 ───────────────────────────────
    portfolio_updated = False
    for h in stock_holdings:
        ticker      = h["ticker"]
        entry_price = h["entry_price"]
        if entry_price <= 0:
            continue

        cur  = price_map.get(ticker, entry_price)
        loss = (cur / entry_price - 1) * 100   # 음수: 손실, 양수: 이익

        # 스톱로스 임계 도달 여부 (이익 종목은 건너뜀)
        if loss > threshold:
            continue

        # 1일 쿨다운: 오늘 이미 경보 발송한 종목은 스킵
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
    """별도 스레드에서 실행 — 스케줄러 블로킹 방지"""
    now       = datetime.now(KST)
    now_month = now.strftime("%Y-%m")
    status    = "✅ 완료" if already_ran_this_month() else "⏳ 오늘 07:10 실행 예정"
    portfolio = load_portfolio()

    if portfolio and portfolio.get("holdings"):
        pf_len    = len(portfolio["holdings"])
        ret_float = get_quick_portfolio_return(portfolio)   # [v4.8] float 반환
        ret_str   = f"{ret_float:+.2f}%"

        # [v4.8] MDD 경보 체크 (낙폭 < 임계값 시 별도 텔레그램 발송, 1일 쿨다운)
        drawdown  = _check_and_alert_mdd(portfolio, ret_float)
        # 낙폭 -3% 이하일 때만 Heartbeat에 추가 표시 (정상 범위 노이즈 방지)
        dd_str    = f" | 낙폭 *{drawdown:+.1f}%p*" if drawdown < -3.0 else ""

        # [v4.10] 드리프트 경보 체크 (이탈 종목 있으면 별도 텔레그램 발송, 1일 쿨다운)
        _check_and_alert_drift(portfolio)

        # [v4.11] 개별 종목 스톱로스 경보 체크 (진입가 대비 손실 임계 도달 시 별도 발송)
        _check_and_alert_stoploss(portfolio)

        pf_str  = f"총 {pf_len}항목 보유 중 (수익률: *{ret_str}*{dd_str}, USD)"
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
# [v4.9] 텔레그램 양방향 명령어 제어
# ══════════════════════════════════════════
def _get_telegram_updates(offset: int, timeout: int = 30) -> list[dict]:
    """Telegram getUpdates Long-polling. timeout초 동안 대기 후 반환."""
    if not TELEGRAM_TOKEN:
        return []
    try:
        res = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": timeout},
            timeout=timeout + 10,
        )
        if res.status_code == 200:
            return res.json().get("result", [])
    except Exception as e:
        log.debug(f"getUpdates 실패: {e}")
    return []


def _cmd_status(chat_id: str) -> None:
    """/status — 현재 포트폴리오 수익률 + 낙폭 + 비중 드리프트 즉시 조회.

    [v4.10] 보유 종목 목록에 현재 비중 + 드리프트(%p) 추가 표시.
    """
    portfolio = load_portfolio()
    if not portfolio or not portfolio.get("holdings"):
        _reply_to(chat_id, "📭 보유 포트폴리오 없음 — 리밸런싱 후 다시 시도하세요")
        return

    ret_float = get_quick_portfolio_return(portfolio)
    max_eq    = float(portfolio.get("max_equity", ret_float))
    drawdown  = ret_float - max(max_eq, ret_float)
    month     = portfolio.get("month", "?")

    stock_holdings = [h for h in portfolio["holdings"] if h["ticker"] != "CASH"]
    cash_holdings  = [h for h in portfolio["holdings"] if h["ticker"] == "CASH"]

    # [v4.10] 현재 비중 재계산 — 가격 조회 후 정규화
    tickers     = [h["ticker"] for h in stock_holdings]
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
        log.warning(f"/status 가격 조회 실패: {e}")

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
    sl_threshold    = STRATEGY["stoploss_threshold"]       # 음수, 예: -20.0
    sl_warn_level   = sl_threshold * 0.5                   # 경고 구간: 예: -10.0
    for h in sorted(stock_holdings, key=lambda x: -x["weight"]):
        # 비중 드리프트 계산
        if total_val > 0:
            cur_w = stock_vals.get(h["ticker"], h["weight"] * 1.0) / total_val * 100
            drift = cur_w - h["weight"]
            drift_tag = f" ⚠️{drift:+.1f}%p" if abs(drift) >= drift_threshold else f" ({drift:+.1f}%p)"
        else:
            cur_w, drift_tag = h["weight"], ""

        # 진입가 대비 손실 계산 + 스톱로스 지시자
        entry = h["entry_price"]
        cur   = price_map.get(h["ticker"], entry)
        if entry > 0:
            loss = (cur / entry - 1) * 100
            if loss <= sl_threshold:
                loss_tag = f"🔴{loss:+.1f}%"   # 스톱로스 임계 도달
            elif loss <= sl_warn_level:
                loss_tag = f"🟡{loss:+.1f}%"   # 경고 구간 (임계의 50% 초과)
            else:
                loss_tag = f"{loss:+.1f}%"
        else:
            loss_tag = "N/A"

        lines.append(
            f"  {h['ticker']}  {h['weight']:.1f}%→{cur_w:.1f}%{drift_tag}"
            f" | {loss_tag} | 진입 ${entry:,.2f}"
        )
    _reply_to(chat_id, "\n".join(lines))


def _cmd_scan(chat_id: str) -> None:
    """/scan — 수동 리밸런싱 강제 실행 (평일 + 중복 방지)."""
    now = datetime.now(KST)
    if now.weekday() >= 5:
        _reply_to(chat_id, "⛔ /scan — 주말에는 실행할 수 없습니다 (평일 전용)")
        return
    with _scan_lock:
        if _scan_running:
            _reply_to(chat_id, "⏳ 스캔이 이미 진행 중입니다 — 완료 후 결과가 발송됩니다")
            return
    _reply_to(chat_id, "⚡ *수동 리밸런싱 시작* (명령어 트리거)")
    job_monthly_scan()


def _cmd_perf(chat_id: str) -> None:
    """/perf — 성과 점검 즉시 실행 (날짜 제한 없음)."""
    portfolio = load_portfolio()
    if not portfolio:
        _reply_to(chat_id, "📭 포트폴리오 없음 — 리밸런싱 후 다시 시도하세요")
        return
    _reply_to(chat_id, "⏳ 성과 점검 중... (벤치마크 다운로드 포함)")
    brief = build_performance_brief(portfolio)
    _reply_to_chunks(chat_id, brief)


def _cmd_help(chat_id: str) -> None:
    """/help — 명령어 목록."""
    _reply_to(
        chat_id,
        "🤖 *미국주식 스캐너 명령어 목록*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "/status — 수익률 + 낙폭 + 비중 드리프트 + 스퇱로스 즉시 조회\n"
        "/scan   — 수동 리밸런싱 강제 실행 (평일 전용)\n"
        "/perf   — 성과 점검 즉시 실행 (벤치마크 포함)\n"
        "/help   — 이 메시지\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ 등록된 채팅방에서만 동작합니다",
    )


def _telegram_poll_loop() -> None:
    """[v4.9] 텔레그램 명령어 수신 데몬 스레드.

    Long-polling 방식 — 별도 서버/webhook 없이 getUpdates API 사용.
    등록된 TELEGRAM_CHAT_IDS 외 chat_id는 무시 (보안).
    """
    offset = 0
    log.info("📨 텔레그램 명령어 수신 시작 (Long-polling)")
    # 보안: TELEGRAM_CHAT_IDS 값을 str로 정규화 (int/str 혼용 방지)
    _allowed_ids = {str(cid).strip() for cid in TELEGRAM_CHAT_IDS}
    while True:
        try:
            updates = _get_telegram_updates(offset, timeout=30)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg     = upd.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", "")).strip()
                text    = msg.get("text", "").strip()
                if not text:
                    continue

                # 보안: 등록된 chat_id만 허용 (str 정규화 후 비교)
                if chat_id not in _allowed_ids:
                    log.warning(f"[명령어 차단] 미등록 chat_id={chat_id} text={text!r}")
                    continue

                cmd = text.split()[0].lower().split("@")[0]   # /cmd@botname 형식 대응
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
                    _reply_to(chat_id, f"❓ 알 수 없는 명령어: {cmd}\n/help 로 목록 확인")

            if not updates:
                time.sleep(1)   # 빈 응답 시 1초 대기 후 재시도

        except Exception as e:
            log.error(f"[TG Poll] 데몬 스레드 예외 발생: {e}")
            time.sleep(5)   # 연속 오류 시 5초 대기 후 재시도


# ══════════════════════════════════════════
_watchdog_last_tick: float = time.time()
_WATCHDOG_TIMEOUT_SEC = 600   # 10분 이상 틱 없으면 이상 감지

def _watchdog_loop() -> None:
    """[v4.2] 별도 데몬 스레드로 실행 — 스케줄 루프 생존 여부 감시.
    10분 이상 메인 루프 틱이 없으면 텔레그램 경보 발송.
    """
    global _watchdog_last_tick  # 함수 내 재할당 전에 전역 선언 필수
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
    schedule.every().day.at("07:00", "Asia/Seoul").do(job_performance_check)  # 매 평일 실행 (장 종료 후)
    schedule.every().day.at("07:10", "Asia/Seoul").do(job_daily_rebal_check)  # 한국 봇(08:50~09:10)과 충돌 회피

    log.info("✅ 미국주식 장기 투자 스캐너 v4.11 시작")
    log.info(f"  전략: D 혼합 / 상위 {STRATEGY['portfolio_size']}종목 / 현금 {STRATEGY['safe_asset_weight']}%")
    log.info("  ⏰ 07:00 Heartbeat + 성과 점검(매일) — 전날 미국 장 종가 기준")
    log.info("  ⏰ 07:10 리밸런싱 체크 (한국 봇과 시간 분산)")
    log.info(f"  📝 로그: {LOG_FILE}")

    # 서버 재시작 알림 (항상 발송)
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

    # [v4.2] Watchdog 데몬 스레드 시작
    threading.Thread(target=_watchdog_loop, daemon=True, name="watchdog").start()
    log.info("  🐕 Watchdog 시작 (무응답 감지 10분)")

    # [v4.9] 텔레그램 명령어 수신 데몬 스레드 시작
    threading.Thread(target=_telegram_poll_loop, daemon=True, name="tg-poll").start()
    log.info("  📨 텔레그램 명령어 수신 시작 (/status /scan /perf /help)")

    while True:
        schedule.run_pending()
        _watchdog_last_tick = time.time()   # [v4.2] 스케줄러 생존 신호
        time.sleep(1)
