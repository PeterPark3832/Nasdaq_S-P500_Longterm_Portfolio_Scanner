"""
유니버스 로딩 — 3단계 폴백 (ETF → Wikipedia → 하드코딩)
"""
import json
import logging
from datetime import datetime

import pandas as pd

from scanner.config import KST, UNIVERSE_SNAPSHOT_DIR, STRATEGY

log = logging.getLogger("scanner")

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
    """S&P500 + 나스닥100 통합 유니버스. 3단계 폴백."""
    import yfinance as yf
    ndx, sp = [], []

    try:
        qqq_info = yf.Ticker("QQQ").funds_data
        if qqq_info and hasattr(qqq_info, "top_holdings"):
            holdings = qqq_info.top_holdings
            if holdings is not None and len(holdings) >= 50:
                ndx = [str(t).replace(".", "-") for t in holdings.index.tolist()]
                log.info(f"  QQQ ETF 보유종목 조회 성공: {len(ndx)}개")
    except Exception:
        pass

    try:
        spy_info = yf.Ticker("SPY").funds_data
        if spy_info and hasattr(spy_info, "top_holdings"):
            holdings = spy_info.top_holdings
            if holdings is not None and len(holdings) >= 200:
                sp = [str(t).replace(".", "-") for t in holdings.index.tolist()]
                log.info(f"  SPY ETF 보유종목 조회 성공: {len(sp)}개")
    except Exception:
        pass

    if not ndx:
        try:
            ndx_tables = pd.read_html(
                "https://en.wikipedia.org/wiki/Nasdaq-100",
                attrs={"id": "constituents"},
            )
            for t in ndx_tables:
                for col in ["Ticker", "Symbol", "Ticker symbol"]:
                    if col in t.columns:
                        tks = [str(s).replace(".", "-") for s in t[col].dropna()
                               if 1 <= len(str(s)) <= 6]
                        if len(tks) >= 80:
                            ndx = tks[:100]
                            log.info(f"  나스닥100 위키 파싱 성공: {len(ndx)}개")
                            break
                if ndx:
                    break
        except Exception:
            pass

    if not sp:
        try:
            sp_tables = pd.read_html(
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                attrs={"id": "constituents"},
            )
            for t in sp_tables:
                for col in ["Symbol", "Ticker", "Ticker symbol"]:
                    if col in t.columns:
                        tks = [str(s).replace(".", "-") for s in t[col].dropna()
                               if 1 <= len(str(s)) <= 6]
                        if len(tks) >= 400:
                            sp = tks[:500]
                            log.info(f"  S&P500 위키 파싱 성공: {len(sp)}개")
                            break
                if sp:
                    break
        except Exception:
            pass

    if not ndx:
        ndx = NDX100_FALLBACK
        log.info(f"  나스닥100 폴백 사용: {len(ndx)}개")
    if not sp:
        sp = SP500_EXTRA_FALLBACK
        log.info(f"  S&P500 폴백 사용: {len(sp)}개")

    combined = list(dict.fromkeys(ndx + sp))
    log.info(f"유니버스: 나스닥100 {len(ndx)}개 + S&P500추가 {len(sp)}개 → 통합 {len(combined)}개")
    return combined


def save_universe_snapshot(tickers: list[str]) -> None:
    """월별 유니버스 스냅샷 저장 (12개월치 보존)."""
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
    prev_snaps = [s for s in snapshots if s.stem != f"universe_{now_month}"]
    if not prev_snaps:
        return []
    try:
        data = json.loads(prev_snaps[-1].read_text(encoding="utf-8"))
        return data.get("tickers", [])
    except Exception:
        return []
