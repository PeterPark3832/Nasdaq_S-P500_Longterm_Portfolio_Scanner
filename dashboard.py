import os, json, logging, re
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

log = logging.getLogger("dashboard")
BASE  = Path(__file__).parent
TOKEN = os.getenv("DASHBOARD_TOKEN", "scanner2024")
app   = FastAPI(docs_url=None, redoc_url=None)

def _load(fname):
    try:    return json.loads((BASE / fname).read_text())
    except: return None

@app.get("/api/data")
def api_data(token: str = ""):
    if token != TOKEN: raise HTTPException(401)
    return JSONResponse({
        "portfolio":   _load("portfolio_state_us.json") or {},
        "performance": _load("performance_history.json") or {"records": []},
        "last_rebal":  _load("last_rebal_us.json") or {},
        "updated":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

@app.get("/api/benchmark")
def api_benchmark(token: str = "", start: str = ""):
    """SPY/QQQ 일별 누적 수익률 (포트폴리오 시작일 기준)."""
    if token != TOKEN: raise HTTPException(401)
    try:
        import yfinance as yf
        import pandas as pd

        if not start:
            perf = _load("performance_history.json") or {}
            records = perf.get("records", [])
            if records:
                start = records[0]["date"]   # 첫 리밸런싱일 기준 (포트폴리오 진입가와 동일 기준점)
            else:
                port = _load("portfolio_state_us.json") or {}
                month = port.get("month", "")
                start = f"{month}-01" if month else (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        end = datetime.now().strftime("%Y-%m-%d")
        raw = yf.download(
            ["SPY", "QQQ"], start=start, end=end,
            progress=False, auto_adjust=True,
        )

        if raw.empty:
            return JSONResponse({"spy": [], "qqq": [], "start_date": start, "updated": end, "error": "no_data"})

        def _extract_close(sym: str) -> pd.Series:
            if isinstance(raw.columns, pd.MultiIndex):
                if ("Close", sym) in raw.columns:
                    return raw[("Close", sym)].dropna()
                if (sym, "Close") in raw.columns:
                    return raw[(sym, "Close")].dropna()
                try:
                    return raw[sym]["Close"].dropna()
                except Exception:
                    return pd.Series(dtype=float)
            else:
                if "Close" in raw.columns:
                    return raw["Close"].dropna()
                return pd.Series(dtype=float)

        def _to_ret_series(series: pd.Series) -> list[dict]:
            if series.empty or len(series) < 1:
                return []
            base = float(series.iloc[0])
            if base <= 0:
                return []
            return [
                {"date": str(idx.date()), "ret": round((float(v) / base - 1) * 100, 2)}
                for idx, v in series.items()
                if pd.notna(v)
            ]

        spy_series = _extract_close("SPY")
        qqq_series = _extract_close("QQQ")

        return JSONResponse({
            "spy":        _to_ret_series(spy_series),
            "qqq":        _to_ret_series(qqq_series),
            "start_date": start,
            "updated":    end,
        })

    except Exception as e:
        log.warning(f"/api/benchmark error: {e}")
        return JSONResponse({"spy": [], "qqq": [], "start_date": start, "updated": "", "error": str(e)})

@app.get("/api/logs")
def api_logs(token: str = "", n: int = 300):
    if token != TOKEN: raise HTTPException(401)
    log_file = BASE / "longterm_scanner_us.log"
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        return JSONResponse({"lines": lines[-n:], "total": len(lines)})
    except:
        return JSONResponse({"lines": [], "total": 0})

@app.get("/api/changes")
def api_changes(token: str = ""):
    if token != TOKEN: raise HTTPException(401)
    return JSONResponse({
        "changes":      _load("rebalancing_changes.json") or {},
        "prev":         _load("portfolio_prev_us.json") or {},
        "current":      _load("portfolio_state_us.json") or {},
        "updated":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

@app.get("/", response_class=HTMLResponse)
def index(token: str = ""):
    if token != TOKEN:
        return HTMLResponse("""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>US Portfolio</title>
<style>*{margin:0;padding:0;box-sizing:border-box}
body{background:#EEEEFF;color:#1a1a3e;font-family:system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.c{background:#fff;border:1px solid rgba(108,92,231,.12);border-radius:20px;
  padding:48px 40px;text-align:center;box-shadow:0 8px 32px rgba(108,92,231,.1)}
.lock{margin-bottom:20px;color:#6C5CE7}.lock svg{width:52px;height:52px}
.t{font-size:22px;font-weight:800;margin-bottom:8px}
code{color:#6C5CE7;background:rgba(108,92,231,.1);padding:2px 8px;border-radius:4px;font-size:13px}
</style></head><body><div class="c"><div class="lock"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="11" width="16" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></div>
<div class="t">접근 제한</div>
<p style="color:#8892a5;font-size:14px;margin-top:8px">URL에 <code>?token=scanner2024</code> 추가</p>
</div></body></html>""")
    return HTMLResponse(
        MAIN.replace("__TOKEN__", token),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

MAIN = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>US Portfolio Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>
/* ── DESIGN TOKENS ── */
:root{
  --bg:#EEEEFF;
  --sidebar:#1A1744;
  --sidebar-hover:rgba(255,255,255,.07);
  --sidebar-active:rgba(108,92,231,.3);
  --card:#fff;
  --card-bg2:#F5F4FF;
  --accent:#6C5CE7;
  --accent2:#4834D4;
  --accent-soft:rgba(108,92,231,.1);
  --tx:#1a1a3e;
  --tx2:#4a4a7a;
  --mu:#8892a5;
  --bd:rgba(108,92,231,.1);
  --gn:#00b894;
  --gn-s:rgba(0,184,148,.12);
  --rd:#e17055;
  --rd-s:rgba(225,112,85,.12);
  --yw:#b8860b;
  --yw-s:rgba(253,203,110,.18);
  --bl:#4a90d9;
  --bl-s:rgba(74,144,217,.12);
  --shadow:0 4px 24px rgba(108,92,231,.08);
  --shadow-md:0 8px 32px rgba(108,92,231,.14);
  --r:16px;
  --r-sm:10px;
  --sb:240px;
}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:16px;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--tx);
  font-family:system-ui,-apple-system,'Segoe UI',sans-serif;min-height:100vh}

/* ══ SIDEBAR ══ */
.sidebar{
  position:fixed;top:0;left:0;bottom:0;width:var(--sb);
  background:var(--sidebar);
  display:flex;flex-direction:column;padding:24px 14px 20px;
  z-index:300;transition:width .25s ease;overflow:hidden;
}
.sb-brand{display:flex;align-items:center;gap:12px;padding:0 6px;margin-bottom:8px}
.sb-icon-wrap{
  width:38px;height:38px;border-radius:10px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;
  font-size:18px;flex-shrink:0;box-shadow:0 4px 12px rgba(108,92,231,.4);
}
.sb-brand-text .sb-name{font-size:15px;font-weight:800;color:#fff}
.sb-brand-text .sb-live{font-size:11px;color:rgba(255,255,255,.45);
  display:flex;align-items:center;gap:5px;margin-top:3px}
.dot{width:7px;height:7px;border-radius:50%;background:#00b894;
  box-shadow:0 0 7px #00b894;animation:pulse 2s infinite;flex-shrink:0}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.sb-month{font-size:11px;color:rgba(255,255,255,.3);
  padding:0 6px;margin-bottom:18px;margin-top:4px}

.sidenav{list-style:none;flex:1;display:flex;flex-direction:column;gap:2px}
.snitem{
  display:flex;align-items:center;gap:10px;
  padding:11px 12px;border-radius:var(--r-sm);
  cursor:pointer;font-size:14px;font-weight:500;
  color:rgba(255,255,255,.5);transition:all .15s;
  white-space:nowrap;overflow:hidden;
}
.snitem:hover{background:var(--sidebar-hover);color:rgba(255,255,255,.85)}
.snitem.on{background:var(--sidebar-active);color:#fff;font-weight:700}
.snitem .sn-ic{font-size:16px;width:20px;text-align:center;flex-shrink:0}

.sb-footer{
  border-top:1px solid rgba(255,255,255,.08);
  padding-top:14px;margin-top:6px;
}
.sb-clock{font-size:12px;color:rgba(255,255,255,.35);padding:0 6px}
.sb-upd{font-size:10px;color:rgba(255,255,255,.2);padding:4px 6px 0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ══ MOBILE TOP BAR ══ */
.topbar{
  display:none;position:fixed;top:0;left:0;right:0;height:56px;
  background:var(--card);border-bottom:1px solid var(--bd);
  align-items:center;padding:0 16px;gap:8px;z-index:200;
  box-shadow:0 2px 12px rgba(108,92,231,.07);
}
.tb-logo{display:flex;align-items:center;gap:8px;flex:1}
.tb-icon{
  width:30px;height:30px;border-radius:8px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;font-size:14px;
}
.tb-txt{font-size:15px;font-weight:800;color:var(--tx)}
.tb-month{font-size:11px;color:var(--mu);margin-left:4px}
.tb-clock{font-size:12px;color:var(--mu)}

/* ══ MOBILE BOTTOM NAV ══ */
.mnav{
  display:none;position:fixed;bottom:0;left:0;right:0;height:64px;
  background:var(--card);border-top:1px solid var(--bd);z-index:200;
  box-shadow:0 -2px 12px rgba(108,92,231,.07);
}
.mnavitems{display:flex;height:100%}
.mnavitem{
  flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:3px;border:none;background:transparent;
  color:var(--mu);font-size:10px;cursor:pointer;transition:color .15s;font-weight:500;
}
.mnavitem.on{color:var(--accent)}
.mnavitem .mic{font-size:20px;line-height:1}

/* ══ MAIN CONTENT ══ */
.main{margin-left:var(--sb);padding:28px;min-height:100vh}
.sec{display:none}.sec.on{display:block}

/* ══ PAGE HEADER ══ */
.phdr{margin-bottom:24px}
.ptitle{font-size:22px;font-weight:800;color:var(--tx)}
.psub{font-size:13px;color:var(--mu);margin-top:5px}

/* ══ HERO CARD ══ */
.hero-card{
  background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);
  border-radius:20px;padding:24px 28px;color:#fff;
  position:relative;overflow:hidden;margin-bottom:22px;
  box-shadow:0 8px 32px rgba(108,92,231,.35);
}
.hero-card::before{
  content:'';position:absolute;top:-40px;right:-40px;
  width:160px;height:160px;border-radius:50%;
  background:rgba(255,255,255,.06);pointer-events:none;
}
.hero-card::after{
  content:'';position:absolute;bottom:-60px;right:60px;
  width:200px;height:200px;border-radius:50%;
  background:rgba(255,255,255,.04);pointer-events:none;
}
.hero-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
.hero-label{font-size:11px;opacity:.65;text-transform:uppercase;letter-spacing:.07em;font-weight:600}
.hero-badge{
  background:rgba(255,255,255,.18);border-radius:20px;
  padding:4px 12px;font-size:11px;font-weight:700;
  backdrop-filter:blur(8px);letter-spacing:.02em;
}
.hero-return{font-size:38px;font-weight:800;letter-spacing:-.03em;line-height:1;margin-bottom:6px}
.hero-meta{font-size:12px;opacity:.65;display:flex;gap:14px;margin-bottom:22px;flex-wrap:wrap}
.hero-bottom{display:flex;justify-content:space-between;align-items:center}
.hero-info{display:flex;gap:28px;flex-wrap:wrap}
.hero-stat .hl{font-size:10px;opacity:.55;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;font-weight:600}
.hero-stat .hv{font-size:14px;font-weight:700}
.hero-logo{
  width:44px;height:44px;border-radius:12px;
  background:rgba(255,255,255,.15);display:flex;
  align-items:center;justify-content:center;font-size:14px;font-weight:800;
  backdrop-filter:blur(4px);flex-shrink:0;
}

/* ══ KPI GRID ══ */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.kpi{
  background:var(--card);border-radius:var(--r);
  padding:20px 22px;box-shadow:var(--shadow);border:1px solid var(--bd);
}
.klabel{font-size:11px;color:var(--mu);margin-bottom:8px;
  text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.kval{font-size:28px;font-weight:800;line-height:1;letter-spacing:-.02em;color:var(--tx)}
.ksub{font-size:12px;color:var(--mu);margin-top:6px}
.pos{color:var(--gn)!important}.neg{color:var(--rd)!important}.neu{color:var(--accent)!important}
.kval.pos{color:var(--gn)}.kval.neg{color:var(--rd)}.kval.neu{color:var(--accent)}

/* ══ CARD ══ */
.card{background:var(--card);border-radius:var(--r);
  padding:22px;box-shadow:var(--shadow);border:1px solid var(--bd)}
.cc{background:var(--card);border-radius:var(--r);
  padding:22px;box-shadow:var(--shadow);border:1px solid var(--bd)}
.ctitle{font-size:11px;font-weight:700;color:var(--mu);
  text-transform:uppercase;letter-spacing:.07em;margin-bottom:16px}

/* ══ PC LAYOUT GRIDS ══ */
.home-grid{display:grid;grid-template-columns:2fr 1fr;gap:18px;align-items:start}
.home-list{max-height:520px;overflow-y:auto}
.port-grid{display:grid;grid-template-columns:320px 1fr;gap:18px;margin-bottom:18px;align-items:start}
.risk-grid{display:grid;grid-template-columns:1fr 1.6fr;gap:18px;margin-bottom:18px;align-items:start}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}
.mb18{margin-bottom:18px}

/* ══ CHART FILTER ══ */
.cf{display:flex;align-items:center;gap:6px;margin-bottom:16px}
.cf-lbl{font-size:11px;color:var(--mu);margin-right:4px;font-weight:600}
.cfbtn{
  padding:5px 14px;border-radius:20px;
  border:1.5px solid var(--bd);background:transparent;
  color:var(--mu);font-size:12px;font-weight:600;cursor:pointer;transition:all .15s;
}
.cfbtn.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.cfbtn:hover:not(.on){background:var(--accent-soft);color:var(--accent);border-color:var(--accent)}

/* ══ TABLE ══ */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:10px 14px;background:#f0efff;color:var(--mu);
  font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;white-space:nowrap}
th:first-child{border-radius:8px 0 0 8px}th:last-child{border-radius:0 8px 8px 0}
td{padding:12px 14px;border-bottom:1px solid rgba(108,92,231,.06);
  white-space:nowrap;color:var(--tx)}
tr:hover td{background:rgba(108,92,231,.025)}
tr:last-child td{border-bottom:none}

/* ══ WEIGHT BAR ══ */
.wb{display:flex;align-items:center;gap:8px;min-width:110px}
.wbg{flex:1;height:5px;border-radius:3px;background:rgba(108,92,231,.12);overflow:hidden}
.wbf{height:5px;border-radius:3px;background:var(--accent)}
.wpct{font-size:12px;font-weight:700;min-width:38px;text-align:right;color:var(--tx)}

/* ══ BADGES ══ */
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600}
.bg{background:var(--gn-s);color:var(--gn)}
.br{background:var(--rd-s);color:var(--rd)}
.bb{background:var(--accent-soft);color:var(--accent)}
.bo{background:var(--yw-s);color:var(--yw)}
.bt{background:var(--bl-s);color:var(--bl)}

/* ══ SECTOR LIST ══ */
.slist{list-style:none}
.si{display:flex;align-items:center;gap:10px;padding:10px 0;
  border-bottom:1px solid rgba(108,92,231,.07)}
.si:last-child{border-bottom:none}
.sdot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.sname{flex:1;font-size:13px;color:var(--tx)}
.spct{font-size:13px;font-weight:700;color:var(--accent)}

/* ══ GAUGE ══ */
.gauge-wrap{display:flex;flex-direction:column;align-items:center;padding:10px 0 4px}
.gval{font-size:34px;font-weight:800;margin:8px 0 4px;line-height:1}
.glabel{font-size:12px;color:var(--mu)}

/* ══ REGIME ══ */
.regime{padding:16px;border-radius:var(--r-sm);text-align:center;margin-bottom:14px}
.r-normal{background:var(--gn-s);border:1px solid rgba(0,184,148,.2)}
.r-caution{background:var(--yw-s);border:1px solid rgba(184,134,11,.2)}
.r-fear{background:var(--rd-s);border:1px solid rgba(225,112,85,.2)}
.rlabel{font-size:22px;font-weight:800;color:var(--tx)}
.rsub{font-size:12px;color:var(--mu);margin-top:4px}

/* ══ ALERTS ══ */
.al{padding:12px 16px;border-radius:8px;margin-bottom:8px;font-size:13px}
.al-ok{background:var(--gn-s);border:1px solid rgba(0,184,148,.2);color:var(--gn)}
.al-err{background:var(--rd-s);border:1px solid rgba(225,112,85,.2);color:var(--rd)}

/* ══ MOBILE HOLDING CARDS ══ */
.mcards{display:none}
.mcard{background:var(--card);border:1px solid var(--bd);border-radius:var(--r);
  padding:16px;margin-bottom:10px;box-shadow:var(--shadow)}
.mcard-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}
.mcard-ticker{font-size:17px;font-weight:800;color:var(--accent)}
.mcard-name{font-size:11px;color:var(--mu);margin-top:2px;
  max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mcard-score-val{font-size:17px;font-weight:800}
.mcard-score-lbl{font-size:10px;color:var(--mu);text-align:right}
.mcard-wbar{margin-bottom:12px}
.mcard-wlbl{display:flex;justify-content:space-between;font-size:11px;
  color:var(--mu);margin-bottom:4px}
.mcard-wpct{font-weight:700;color:var(--tx)}
.mcard-wbg{height:6px;border-radius:3px;background:rgba(108,92,231,.1);overflow:hidden}
.mcard-wbf{height:6px;border-radius:3px;background:var(--accent)}
.mcard-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.mcard-item label{font-size:10px;color:var(--mu);display:block;margin-bottom:3px}
.mcard-item span{font-size:13px;font-weight:600;color:var(--tx)}
.mcard-badge{display:inline-block;padding:2px 7px;border-radius:20px;
  font-size:10px;font-weight:600;background:var(--accent-soft);color:var(--accent)}

/* ══ RESPONSIVE ══ */
@media(max-width:1280px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .g4{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:1024px){
  :root{--sb:68px}
  .sidebar .sn-text,.sidebar .sb-brand-text,
  .sidebar .sb-month,.sidebar .sb-upd{display:none}
  .sidebar .snitem{padding:11px 0;justify-content:center}
  .sidebar .sb-brand{justify-content:center;padding:0}
  .home-grid{grid-template-columns:1fr}
  .port-grid{grid-template-columns:1fr}
  .risk-grid{grid-template-columns:1fr}
}
@media(max-width:768px){
  :root{--sb:0px}
  .sidebar{display:none}
  .topbar{display:flex}
  .mnav{display:block}
  .main{margin-left:0;padding:66px 14px 76px}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .kval{font-size:24px}
  .g4,.g3{grid-template-columns:1fr 1fr}
  th,td{padding:9px 10px}
  table{font-size:12px}
  .desk-tbl{display:none}
  .mcards{display:block}
  .hero-card{padding:20px}
  .hero-return{font-size:28px}
  .hero-info{gap:16px}
}
@media(max-width:420px){
  .kpis{grid-template-columns:1fr 1fr}
  .g4,.g3{grid-template-columns:1fr}
}

/* ══ LOG VIEWER ══ */
.log-wrap{
  background:#f8f7ff;border:1px solid var(--bd);border-radius:var(--r-sm);
  padding:14px;font-family:'JetBrains Mono','Fira Code',monospace;
  font-size:11px;line-height:1.6;max-height:600px;overflow-y:auto;
}
.log-line{white-space:pre-wrap;word-break:break-all;padding:1px 0}
.log-err{color:#d63031}.log-warn{color:#b8860b}
.log-info{color:#636e72}.log-ok{color:#00b894}
.log-ctrl{display:flex;align-items:center;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.log-badge{font-size:10px;padding:4px 10px;border-radius:20px;font-weight:700;
  cursor:pointer;border:1.5px solid transparent;transition:all .15s}
.lb-all{background:var(--accent-soft);color:var(--accent);border-color:var(--accent)}
.lb-err{background:var(--rd-s);color:var(--rd)}
.lb-ok{background:var(--gn-s);color:var(--gn)}
.log-refresh{margin-left:auto;padding:5px 14px;border-radius:20px;
  border:1.5px solid var(--bd);background:transparent;color:var(--mu);
  font-size:12px;cursor:pointer;transition:all .15s;font-weight:600}
.log-refresh:hover{background:var(--accent-soft);color:var(--accent);border-color:var(--accent)}

/* ══ CHANGE CARDS ══ */
.ch-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-bottom:16px}
.ch-card{background:var(--card);border-radius:var(--r);padding:16px 18px;
  border-left:3px solid;box-shadow:var(--shadow)}
.ch-new{border-color:var(--gn)}.ch-exit{border-color:var(--rd)}
.ch-up{border-color:var(--accent)}.ch-dn{border-color:#fdcb6e}.ch-keep{border-color:var(--bd)}
.ch-ticker{font-size:16px;font-weight:800;margin-bottom:2px;color:var(--tx)}
.ch-name{font-size:11px;color:var(--mu);margin-bottom:10px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ch-row{display:flex;justify-content:space-between;font-size:12px;margin-top:5px;
  padding-top:5px;border-top:1px solid rgba(108,92,231,.06)}
.ch-row:first-of-type{border-top:none;padding-top:0;margin-top:0}
.ch-label{color:var(--mu)}.ch-val{font-weight:600;color:var(--tx)}
.chg-hdr{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.chg-title{font-size:14px;font-weight:700;color:var(--tx)}
.chg-cnt{font-size:11px;background:var(--accent-soft);padding:2px 10px;
  border-radius:20px;color:var(--accent);font-weight:600}

/* ══ ROADMAP ══ */
.rm-section{margin-bottom:28px}
.rm-title{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:14px;padding-bottom:10px;
  border-bottom:1px solid var(--bd)}
.rm-item{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid rgba(108,92,231,.06)}
.rm-item:last-child{border-bottom:none}
.rm-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:4px}
.rm-done{background:var(--gn)}.rm-wip{background:#fdcb6e}
.rm-plan{background:var(--accent)}.rm-idea{background:var(--mu)}
.rm-body{flex:1}
.rm-name{font-size:14px;font-weight:600;margin-bottom:4px;color:var(--tx)}
.rm-desc{font-size:12px;color:var(--mu);line-height:1.55}
.rm-tag{display:inline-block;font-size:10px;padding:2px 8px;
  border-radius:10px;font-weight:700;margin-top:6px}
.rm-tag-done{background:var(--gn-s);color:var(--gn)}
.rm-tag-wip{background:var(--yw-s);color:var(--yw)}
.rm-tag-plan{background:var(--accent-soft);color:var(--accent)}
.rm-tag-idea{background:rgba(136,146,165,.12);color:var(--mu)}

</style>
</head>
<body>

<!-- ══ SIDEBAR (PC + Tablet) ══ -->
<nav class="sidebar" id="sidebar">
  <div class="sb-brand">
    <div class="sb-icon-wrap">{{ic:trend}}</div>
    <div class="sb-brand-text">
      <div class="sb-name">US Portfolio</div>
      <div class="sb-live"><div class="dot"></div>Live</div>
    </div>
  </div>
  <div class="sb-month" id="sb-month"></div>
  <ul class="sidenav">
    <li class="snitem on" onclick="go('home')"><span class="sn-ic">{{ic:home}}</span><span class="sn-text">홈</span></li>
    <li class="snitem"   onclick="go('port')"><span class="sn-ic">{{ic:portfolio}}</span><span class="sn-text">포트폴리오</span></li>
    <li class="snitem"   onclick="go('perf')"><span class="sn-ic">{{ic:trend}}</span><span class="sn-text">성과 분석</span></li>
    <li class="snitem"   onclick="go('risk')"><span class="sn-ic">{{ic:risk}}</span><span class="sn-text">리스크</span></li>
    <li class="snitem"   onclick="go('changes')"><span class="sn-ic">{{ic:changes}}</span><span class="sn-text">변경 내역</span></li>
    <li class="snitem"   onclick="go('logs')"><span class="sn-ic">{{ic:logs}}</span><span class="sn-text">로그</span></li>
    <li class="snitem"   onclick="go('roadmap')"><span class="sn-ic">{{ic:roadmap}}</span><span class="sn-text">로드맵</span></li>
  </ul>
  <div class="sb-footer">
    <div class="sb-clock" id="sb-clock"></div>
    <div class="sb-upd" id="sb-upd"></div>
  </div>
</nav>

<!-- ══ MOBILE TOP BAR ══ -->
<div class="topbar">
  <div class="tb-logo">
    <div class="tb-icon">{{ic:trend}}</div>
    <span class="tb-txt">US Portfolio</span>
    <span class="tb-month" id="tb-month"></span>
  </div>
  <span class="tb-clock" id="tb-clock"></span>
</div>

<div class="main">

  <!-- ═══ HOME ═══ -->
  <div class="sec on" id="s-home">
    <div class="phdr">
      <div class="ptitle">US Long-Term Portfolio</div>
      <div class="psub" id="home-sub">로딩 중…</div>
    </div>
    <div id="hero-wrap"></div>
    <div class="kpis" id="kpis"></div>
    <div class="home-grid">
      <div class="cc">
        <div class="ctitle">성과 추이 — 포트폴리오 vs SPY vs QQQ</div>
        <div class="cf">
          <span class="cf-lbl">기간</span>
          <button class="cfbtn" id="cfbtn-home-1M" onclick="setRange('1M','home')">1M</button>
          <button class="cfbtn" id="cfbtn-home-3M" onclick="setRange('3M','home')">3M</button>
          <button class="cfbtn" id="cfbtn-home-6M" onclick="setRange('6M','home')">6M</button>
          <button class="cfbtn on" id="cfbtn-home-ALL" onclick="setRange('ALL','home')">ALL</button>
        </div>
        <canvas id="ch-home" height="220"></canvas>
      </div>
      <div class="card home-list">
        <div class="ctitle">보유 종목</div>
        <div class="desk-tbl tw" id="home-tbl"></div>
        <div class="mcards" id="home-cards"></div>
      </div>
    </div>
  </div>

  <!-- ═══ PORTFOLIO ═══ -->
  <div class="sec" id="s-port">
    <div class="phdr"><div class="ptitle">포트폴리오 현황</div></div>
    <div class="port-grid">
      <div style="display:flex;flex-direction:column;gap:18px">
        <div class="card">
          <div class="ctitle">섹터 배분</div>
          <canvas id="ch-sector" height="260"></canvas>
        </div>
        <div class="card">
          <div class="ctitle">섹터 목록</div>
          <ul class="slist" id="slist"></ul>
        </div>
      </div>
      <div class="card">
        <div class="ctitle">보유 종목 상세</div>
        <div class="desk-tbl tw" id="port-tbl"></div>
        <div class="mcards" id="port-cards"></div>
      </div>
    </div>
  </div>

  <!-- ═══ PERFORMANCE ═══ -->
  <div class="sec" id="s-perf">
    <div class="phdr"><div class="ptitle">성과 분석</div></div>
    <div class="cc mb18">
      <div class="ctitle">누적 수익률 추이</div>
      <div class="cf">
        <span class="cf-lbl">기간</span>
        <button class="cfbtn" id="cfbtn-perf-1M" onclick="setRange('1M','perf')">1M</button>
        <button class="cfbtn" id="cfbtn-perf-3M" onclick="setRange('3M','perf')">3M</button>
        <button class="cfbtn" id="cfbtn-perf-6M" onclick="setRange('6M','perf')">6M</button>
        <button class="cfbtn on" id="cfbtn-perf-ALL" onclick="setRange('ALL','perf')">ALL</button>
      </div>
      <canvas id="ch-perf" height="200"></canvas>
    </div>
    <div class="g4" id="perf-kpis"></div>
    <div class="card">
      <div class="ctitle">성과 이력</div>
      <div class="tw" id="perf-tbl"></div>
    </div>
  </div>

  <!-- ═══ RISK ═══ -->
  <div class="sec" id="s-risk">
    <div class="phdr"><div class="ptitle">리스크 모니터링</div></div>
    <div class="risk-grid">
      <div class="card" style="text-align:center">
        <div class="ctitle">MDD 모니터</div>
        <div id="mdd-gauge"></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:18px">
        <div class="card">
          <div class="ctitle">VIX 레짐</div>
          <div id="vix-regime"></div>
          <div class="tw"><table>
            <tr><th>레짐</th><th>조건</th><th>현금비중</th></tr>
            <tr><td>{{ic:dot-gn}} 정상</td><td>VIX &lt; 30</td><td>30%</td></tr>
            <tr><td>{{ic:dot-yw}} 주의</td><td>VIX ≥ 30</td><td>50%</td></tr>
            <tr><td>{{ic:dot-rd}} 공포</td><td>VIX ≥ 40</td><td>60%</td></tr>
          </table></div>
        </div>
        <div class="card">
          <div class="ctitle">스톱로스 현황</div>
          <div id="sl-alerts"></div>
        </div>
      </div>
    </div>
    <div class="card mb18">
      <div class="ctitle">진입가 기준 스톱로스 가격표</div>
      <div class="tw" id="sl-tbl"></div>
    </div>
    <div class="card">
      <div class="ctitle">종목별 스코어 분석</div>
      <canvas id="ch-score" height="220"></canvas>
    </div>
  </div>

  <!-- ═══ CHANGES ═══ -->
  <div class="sec" id="s-changes">
    <div class="phdr">
      <div class="ptitle">포트폴리오 변경 내역</div>
      <div class="psub" id="chg-sub">최근 리밸런싱 기준</div>
    </div>
    <div class="g4" id="chg-kpis"></div>
    <div id="chg-new-wrap" class="mb18">
      <div class="chg-hdr"><span class="chg-title">{{ic:dot-gn}} 신규 편입</span><span class="chg-cnt" id="cnt-new">0종목</span></div>
      <div class="ch-grid" id="chg-new"></div>
    </div>
    <div id="chg-exit-wrap" class="mb18">
      <div class="chg-hdr"><span class="chg-title">{{ic:dot-rd}} 편출</span><span class="chg-cnt" id="cnt-exit">0종목</span></div>
      <div class="ch-grid" id="chg-exit"></div>
    </div>
    <div id="chg-up-wrap" class="mb18">
      <div class="chg-hdr"><span class="chg-title">{{ic:up}} 비중 확대</span><span class="chg-cnt" id="cnt-up">0종목</span></div>
      <div class="ch-grid" id="chg-up"></div>
    </div>
    <div id="chg-dn-wrap" class="mb18">
      <div class="chg-hdr"><span class="chg-title">{{ic:down}} 비중 축소</span><span class="chg-cnt" id="cnt-dn">0종목</span></div>
      <div class="ch-grid" id="chg-dn"></div>
    </div>
    <div>
      <div class="chg-hdr"><span class="chg-title">{{ic:dot-mu}} 유지</span><span class="chg-cnt" id="cnt-keep">0종목</span></div>
      <div class="ch-grid" id="chg-keep"></div>
    </div>
  </div>

  <!-- ═══ LOGS ═══ -->
  <div class="sec" id="s-logs">
    <div class="phdr">
      <div class="ptitle">봇 로그</div>
      <div class="psub" id="log-sub">최근 300줄</div>
    </div>
    <div class="card">
      <div class="log-ctrl">
        <button class="log-badge lb-all" onclick="filterLog('all')">전체</button>
        <button class="log-badge lb-err" onclick="filterLog('error')">에러</button>
        <button class="log-badge lb-ok"  onclick="filterLog('info')">INFO</button>
        <button class="log-refresh" onclick="loadLogs()">새로고침</button>
      </div>
      <div class="log-wrap" id="log-box">로딩 중…</div>
    </div>
  </div>

  <!-- ═══ ROADMAP ═══ -->
  <div class="sec" id="s-roadmap">
    <div class="phdr">
      <div class="ptitle">로드맵</div>
      <div class="psub">개발 계획 및 현황</div>
    </div>
    <div class="card">
      <div class="rm-section">
        <div class="rm-title">{{ic:check}} 완료</div>
        <div class="rm-item"><div class="rm-dot rm-done"></div><div class="rm-body">
          <div class="rm-name">미국주식 롱텀 포트폴리오 봇 v4.11</div>
          <div class="rm-desc">Nasdaq/S&P500 ~500종목 스캔, 모멘텀+재무 복합 스코어링, 월간 리밸런싱, 텔레그램 브리핑</div>
          <span class="rm-tag rm-tag-done">완료</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-done"></div><div class="rm-body">
          <div class="rm-name">FastAPI 대시보드 — 라벤더 뱅킹 UI</div>
          <div class="rm-desc">홈/포트폴리오/성과분석/리스크 탭, 라이트 퍼플 테마, 반응형 (PC·태블릿·모바일)</div>
          <span class="rm-tag rm-tag-done">완료</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-done"></div><div class="rm-body">
          <div class="rm-name">VIX 레짐 기반 현금 비중 조절</div>
          <div class="rm-desc">VIX 30 이상 시 현금 50%, VIX 40 이상 시 60%로 자동 확대</div>
          <span class="rm-tag rm-tag-done">완료</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-done"></div><div class="rm-body">
          <div class="rm-name">MDD 모니터링 + 스톱로스 알림</div>
          <div class="rm-desc">진입가 기준 -20% 도달 시 텔레그램 알림, 대시보드 게이지 시각화</div>
          <span class="rm-tag rm-tag-done">완료</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-done"></div><div class="rm-body">
          <div class="rm-name">변경 내역 탭 + 로그 탭</div>
          <div class="rm-desc">리밸런싱 편입/편출/비중변화 카드뷰, 실시간 봇 로그 조회</div>
          <span class="rm-tag rm-tag-done">완료</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-done"></div><div class="rm-body">
          <div class="rm-name">텔레그램 한글 청크 버그 수정</div>
          <div class="rm-desc">UTF-8 바이트 기준으로 4096 byte 제한 체크 (한글 1자=3bytes)</div>
          <span class="rm-tag rm-tag-done">완료</span></div></div>
      </div>
      <div class="rm-section">
        <div class="rm-title">{{ic:tool}} 진행 중</div>
        <div class="rm-item"><div class="rm-dot rm-wip"></div><div class="rm-body">
          <div class="rm-name">유니버스 품질 개선 — 상장폐지 종목 자동 제거</div>
          <div class="rm-desc">SPLK, ANSS 등 M&A/상폐 종목이 유니버스에 남아 매월 에러 발생. 자동 정리 로직 추가 예정</div>
          <span class="rm-tag rm-tag-wip">진행중</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-wip"></div><div class="rm-body">
          <div class="rm-name">성과 이력 차트 개선</div>
          <div class="rm-desc">리밸런싱 기준점별 수익률 분리 표시, 진입가 vs 현재가 실시간 수익률</div>
          <span class="rm-tag rm-tag-wip">진행중</span></div></div>
      </div>
      <div class="rm-section">
        <div class="rm-title">{{ic:pin}} 계획</div>
        <div class="rm-item"><div class="rm-dot rm-plan"></div><div class="rm-body">
          <div class="rm-name">매매 실행 체크리스트 탭</div>
          <div class="rm-desc">이번 달 매도 순서 → 매수 순서 가이드, 각 종목 실행 완료 체크 기능</div>
          <span class="rm-tag rm-tag-plan">계획</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-plan"></div><div class="rm-body">
          <div class="rm-name">백테스트 결과 시각화</div>
          <div class="rm-desc">2015~현재 CAGR, 최대 낙폭, 샤프비율 등 백테스트 결과 대시보드에 통합</div>
          <span class="rm-tag rm-tag-plan">계획</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-plan"></div><div class="rm-body">
          <div class="rm-name">종목 드릴다운 상세 팝업</div>
          <div class="rm-desc">티커 클릭 시 재무 상세, 차트, 스코어 근거 팝업으로 표시</div>
          <span class="rm-tag rm-tag-plan">계획</span></div></div>
      </div>
      <div class="rm-section">
        <div class="rm-title">{{ic:idea}} 아이디어</div>
        <div class="rm-item"><div class="rm-dot rm-idea"></div><div class="rm-body">
          <div class="rm-name">멀티 전략 포트폴리오</div>
          <div class="rm-desc">현재 전략 D 외에 모멘텀 위주 전략 A, 가치주 전략 B 병행 추적</div>
          <span class="rm-tag rm-tag-idea">아이디어</span></div></div>
        <div class="rm-item"><div class="rm-dot rm-idea"></div><div class="rm-body">
          <div class="rm-name">ETF 벤치마크 자동 비교</div>
          <div class="rm-desc">QQQ/SPY 외에 QQQM, VGT, SOXX 등 섹터 ETF와 성과 비교</div>
          <span class="rm-tag rm-tag-idea">아이디어</span></div></div>
      </div>
    </div>
  </div>

</div><!-- /main -->

<!-- ══ MOBILE BOTTOM NAV ══ -->
<nav class="mnav">
  <div class="mnavitems">
    <button class="mnavitem on" onclick="go('home')"><span class="mic">{{ic:home}}</span><span>홈</span></button>
    <button class="mnavitem"   onclick="go('port')"><span class="mic">{{ic:portfolio}}</span><span>포트폴리오</span></button>
    <button class="mnavitem"   onclick="go('perf')"><span class="mic">{{ic:trend}}</span><span>성과</span></button>
    <button class="mnavitem"   onclick="go('risk')"><span class="mic">{{ic:risk}}</span><span>리스크</span></button>
    <button class="mnavitem"   onclick="go('changes')"><span class="mic">{{ic:changes}}</span><span>변경</span></button>
    <button class="mnavitem"   onclick="go('logs')"><span class="mic">{{ic:logs}}</span><span>로그</span></button>
    <button class="mnavitem"   onclick="go('roadmap')"><span class="mic">{{ic:roadmap}}</span><span>로드맵</span></button>
  </div>
</nav>

<script>
const TK='__TOKEN__';
const SCOL={
  'Technology':'#6C5CE7','Communication Services':'#00b894',
  'Energy':'#fdcb6e','Basic Materials':'#fd79a8',
  'Healthcare':'#55efc4','Consumer Discretionary':'#fd79a8',
  'Financials':'#74b9ff','Industrials':'#a29bfe',
  'Cash':'#dfe6e9','Unknown':'#b2bec3'
};
let D=null,BM=null,CHS={},RANGE={home:'ALL',perf:'ALL'};

Chart.defaults.color='#8892a5';
Chart.defaults.borderColor='rgba(108,92,231,.07)';

const fp=(v,s=true)=>v==null||isNaN(v)?'—':(s&&v>0?'+':'')+v.toFixed(2)+'%';
const fm=v=>v==null?'—':'$'+v.toFixed(2);
const fc=v=>v>0?'pos':v<0?'neg':'';

function go(name){
  document.querySelectorAll('.sec').forEach(e=>e.classList.remove('on'));
  document.querySelectorAll('.snitem,.mnavitem').forEach(e=>e.classList.remove('on'));
  document.getElementById('s-'+name).classList.add('on');
  document.querySelectorAll('[onclick="go(\''+name+'\')"]').forEach(e=>e.classList.add('on'));
  if(name==='port'    && !CHS.sector)     renderSector();
  if(name==='perf'    && !CHS.perf)       renderPerfChart('ch-perf','perf');
  if(name==='risk'    && !CHS.score)      renderScore();
  if(name==='changes' && !_changesLoaded) loadChanges();
  if(name==='logs'    && !_logsLoaded)    loadLogs();
}

let _logsLoaded=false,_changesLoaded=false,_logFilter='all',_allLogLines=[];

/* ── CHANGES TAB ── */
async function loadChanges(){
  try{
    const r=await fetch('/api/changes?token='+TK);
    if(!r.ok)throw new Error();
    const data=await r.json();
    renderChanges(data);
    _changesLoaded=true;
  }catch{
    document.getElementById('chg-new').innerHTML='<p style="color:var(--rd)">데이터 로드 실패</p>';
  }
}

function renderChanges(data){
  const ch=data.changes||{};
  const date=ch.date||data.current&&data.current.month||'—';
  document.getElementById('chg-sub').textContent='리밸런싱 날짜: '+date;
  const nw=ch.new||[],ex=ch.exited||[],up=ch.increased||[],dn=ch.decreased||[],kp=ch.unchanged||[];
  document.getElementById('chg-kpis').innerHTML=[
    {l:'신규 편입',v:nw.length+'종목',c:'pos'},
    {l:'편출',v:ex.length+'종목',c:'neg'},
    {l:'비중 확대',v:up.length+'종목',c:'neu'},
    {l:'비중 축소',v:dn.length+'종목',c:'neg'},
  ].map(k=>'<div class="card"><div class="ctitle">'+k.l+'</div><div class="kval '+k.c+'" style="font-size:22px">'+k.v+'</div></div>').join('');
  document.getElementById('cnt-new').textContent=nw.length+'종목';
  document.getElementById('cnt-exit').textContent=ex.length+'종목';
  document.getElementById('cnt-up').textContent=up.length+'종목';
  document.getElementById('cnt-dn').textContent=dn.length+'종목';
  document.getElementById('cnt-keep').textContent=kp.length+'종목';
  const chCard=(h,cls,tag,extra)=>{
    const diff=extra||'';
    return '<div class="ch-card '+cls+'">'+
      '<div class="ch-ticker">'+h.ticker+'</div>'+
      '<div class="ch-name">'+(h.name||'')+'</div>'+
      '<div class="ch-row"><span class="ch-label">비중</span><span class="ch-val">'+((h.weight||0).toFixed(1))+'%'+diff+'</span></div>'+
      '<div class="ch-row"><span class="ch-label">스코어</span><span class="ch-val">'+(h.score||'—')+'</span></div>'+
      '<div class="ch-row"><span class="ch-label">섹터</span><span class="ch-val" style="font-size:10px">'+((h.sector||'—').replace('Communication Services','Comm.'))+'</span></div>'+
      '<span class="badge" style="margin-top:6px;display:inline-block;'+tag+'">'+{ch_new:'신규',ch_exit:'편출',ch_up:'확대',ch_dn:'축소',ch_keep:'유지'}[cls.replace('-','_')]+'</span>'+
      '</div>';
  };
  const noItem='<p style="color:var(--mu);font-size:13px">없음</p>';
  document.getElementById('chg-new').innerHTML=nw.map(h=>chCard(h,'ch-new','background:var(--gn-s);color:var(--gn)','')).join('')||noItem;
  document.getElementById('chg-exit').innerHTML=ex.map(h=>chCard(h,'ch-exit','background:var(--rd-s);color:var(--rd)','')).join('')||noItem;
  document.getElementById('chg-up').innerHTML=up.map(h=>chCard(h,'ch-up','background:var(--accent-soft);color:var(--accent)',h.prev_weight!=null?' (+'+(h.weight-h.prev_weight).toFixed(1)+'%p)':'')).join('')||noItem;
  document.getElementById('chg-dn').innerHTML=dn.map(h=>chCard(h,'ch-dn','background:var(--yw-s);color:var(--yw)',h.prev_weight!=null?' (-'+Math.abs(h.weight-h.prev_weight).toFixed(1)+'%p)':'')).join('')||noItem;
  document.getElementById('chg-keep').innerHTML=kp.map(h=>chCard(h,'ch-keep','background:var(--bl-s);color:var(--bl)','')).join('')||noItem;
}

/* ── LOGS TAB ── */
async function loadLogs(){
  document.getElementById('log-box').textContent='로딩 중…';
  try{
    const r=await fetch('/api/logs?token='+TK+'&n=300');
    if(!r.ok)throw new Error();
    const data=await r.json();
    _allLogLines=data.lines||[];
    document.getElementById('log-sub').textContent='전체 '+data.total+'줄 중 최근 '+_allLogLines.length+'줄';
    renderLogLines(_logFilter);
    _logsLoaded=true;
  }catch{
    document.getElementById('log-box').textContent='로그 로드 실패';
  }
}
function filterLog(f){_logFilter=f;renderLogLines(f)}
function renderLogLines(filter){
  const box=document.getElementById('log-box');
  if(!box)return;
  const lines=_allLogLines.filter(l=>{
    if(filter==='all')return true;
    if(filter==='error')return l.includes('[ERROR]')||l.includes('[WARNING]');
    if(filter==='info')return l.includes('[INFO]');
    return true;
  });
  box.innerHTML=[...lines].reverse().map(l=>{
    let cls='log-info';
    if(l.includes('[ERROR]'))cls='log-err';
    else if(l.includes('[WARNING]'))cls='log-warn';
    else if(l.includes('완료')||l.includes('저장'))cls='log-ok';
    const esc=l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    return'<div class="log-line '+cls+'">'+esc+'</div>';
  }).join('');
}

async function load(){
  try{
    const [rD,rB]=await Promise.all([
      fetch('/api/data?token='+TK),
      fetch('/api/benchmark?token='+TK),
    ]);
    if(!rD.ok)throw new Error('data');
    D=await rD.json();
    if(rB.ok){try{BM=await rB.json();}catch{}}
    render();
  }catch{
    document.querySelector('.main').innerHTML=
      '<div style="text-align:center;padding:80px;color:var(--rd)">데이터 로드 실패</div>';
  }
}

function render(){
  if(!D)return;
  const{portfolio:p,performance:pf,updated}=D;
  const holdings=p.holdings||[];
  const stocks=holdings.filter(h=>h.ticker!=='CASH');
  const cash=holdings.find(h=>h.ticker==='CASH');
  const cw=cash?cash.weight:30;
  const recs=pf.records||[];
  const checks=recs.filter(r=>r.type==='performance_check'&&r.portfolio_ret_pct!=null);
  const lat=checks.slice(-1)[0];
  const pr=lat?lat.portfolio_ret_pct:0;
  const sr=(BM?.spy?.slice(-1)[0]?.ret)??(lat?.spy_ret_pct??null);
  const qr=(BM?.qqq?.slice(-1)[0]?.ret)??(lat?.qqq_ret_pct??null);
  const al=sr!=null?pr-sr:(lat?.alpha_vs_spy??null);
  const mon=p.month||'';

  document.getElementById('sb-month').innerHTML=mon?'{{ic:calendar}} '+mon:'';
  document.getElementById('tb-month').textContent=mon?mon:'';
  document.getElementById('sb-upd').textContent='갱신 '+updated;
  document.getElementById('home-sub').textContent=
    `리밸런싱 월: ${mon||'—'} | ${stocks.length}종목 + 현금 ${cw}%`;

  /* ── HERO CARD ── */
  const hw=document.getElementById('hero-wrap');
  if(hw){
    const rc=pr>=0?'rgba(255,255,255,.9)':pr>-5?'#ffeaa7':'#ffb3b3';
    hw.innerHTML=`
    <div class="hero-card">
      <div class="hero-top">
        <div><div class="hero-label">US Long-Term Portfolio</div></div>
        <div class="hero-badge">${mon||'—'}</div>
      </div>
      <div class="hero-return" style="color:${rc}">${fp(pr)}</div>
      <div class="hero-meta">
        <span>누적 수익률</span><span>${stocks.length}종목 보유</span><span>현금 ${cw}%</span>
      </div>
      <div class="hero-bottom">
        <div class="hero-info">
          <div class="hero-stat">
            <div class="hl">SPY Alpha</div>
            <div class="hv">${al!=null?fp(al)+'p':'—'}</div>
          </div>
          <div class="hero-stat">
            <div class="hl">QQQ Alpha</div>
            <div class="hv">${qr!=null&&pr!=null?fp(pr-qr)+'p':'—'}</div>
          </div>
          <div class="hero-stat">
            <div class="hl">섹터 수</div>
            <div class="hv">${new Set(stocks.map(h=>h.sector)).size}개</div>
          </div>
        </div>
        <div class="hero-logo">US</div>
      </div>
    </div>`;
  }

  /* ── KPIs ── */
  const prev=checks.slice(-2,-1)[0];
  const deltaPr=prev?pr-prev.portfolio_ret_pct:null;
  const ks=[
    {l:'포트폴리오 수익률',v:fp(pr),c:fc(pr),s:deltaPr!=null?`전일比 ${fp(deltaPr)}`:'최근 성과 체크'},
    {l:'Alpha vs SPY',v:al!=null?fp(al)+'p':'—',c:fc(al),s:'SPY '+fp(sr)},
    {l:'Alpha vs QQQ',v:qr!=null?fp(pr-qr)+'p':'—',c:fc(qr!=null?pr-qr:0),s:'QQQ '+fp(qr)},
    {l:'현금 비중',v:cw+'%',c:cw>30?'neg':'neu',s:cw>30?'VIX 방어 중':'기본 비중'},
  ];
  document.getElementById('kpis').innerHTML=ks.map(k=>
    `<div class="kpi"><div class="klabel">${k.l}</div>
     <div class="kval ${k.c}">${k.v}</div>
     <div class="ksub">${k.s}</div></div>`
  ).join('');

  renderTable('home-tbl',holdings,false);
  renderCards('home-cards',holdings);
  renderTable('port-tbl',holdings,true);
  renderCards('port-cards',holdings);
  renderSectorList(holdings);
  renderPerfKPIs(checks);
  renderPerfHistTable(recs);
  renderRisk(p,holdings,cw);
  renderPerfChart('ch-home','home');
}

/* ── DATE FILTER ── */
function filterByRange(recs,range){
  if(range==='ALL')return recs;
  const days={'1M':30,'3M':90,'6M':180}[range]||9999;
  const cut=new Date(Date.now()-days*864e5);
  return recs.filter(r=>new Date(r.date)>=cut);
}
function setRange(range,key){
  RANGE[key]=range;
  ['1M','3M','6M','ALL'].forEach(r=>{
    const b=document.getElementById(`cfbtn-${key}-${r}`);
    if(b)b.classList.toggle('on',r===range);
  });
  // destroy() 먼저 호출해야 canvas에 구 차트가 남지 않음
  if(CHS[key]){CHS[key].destroy();delete CHS[key];}
  renderPerfChart('ch-'+key,key);
}

/* ── LINE CHART ── */
function renderPerfChart(canvasId,key){
  if(!D)return;
  const ctx=document.getElementById(canvasId);
  if(!ctx)return;

  const range=RANGE[key]||'ALL';
  const allRecs=D.performance.records||[];
  const rebalDates=allRecs.filter(r=>r.type==='rebalancing').map(r=>r.date);

  const nDays={'1M':30,'3M':90,'6M':180}[range];
  const cutDate=nDays?new Date(Date.now()-nDays*864e5).toISOString().slice(0,10):'0000-00-00';

  const perfRecs=filterByRange(
    allRecs.filter(r=>r.type!=='rebalancing'&&r.portfolio_ret_pct!=null),
    range
  );
  const pm=Object.fromEntries(perfRecs.map(r=>[r.date,r]));

  function rebase(arr){
    const base=arr.find(v=>v!=null);
    if(base==null)return arr;
    return arr.map(v=>v==null?null:parseFloat((v-base).toFixed(2)));
  }

  // 모든 범위: 포트폴리오 첫 측정일 기준으로 BM 시작 맞춤 → 공정 비교
  // ALL/3M/6M: 데이터 짧으면 동일 (논리적으로 정확)
  const spyAll=Object.fromEntries((BM?.spy||[]).filter(p=>p.date>=cutDate).map(p=>[p.date,p.ret]));
  const qqqAll=Object.fromEntries((BM?.qqq||[]).filter(p=>p.date>=cutDate).map(p=>[p.date,p.ret]));
  const pfDates=perfRecs.map(r=>r.date);
  const pfStart=pfDates[0]||cutDate;
  const spyBM=Object.fromEntries(Object.entries(spyAll).filter(([d])=>d>=pfStart));
  const qqqBM=Object.fromEntries(Object.entries(qqqAll).filter(([d])=>d>=pfStart));
  const bmDates=Object.keys(spyBM).sort();
  const allDates=[...new Set([...pfDates,...bmDates])].sort();

  if(!allDates.length){
    if(CHS[key]){CHS[key].destroy();delete CHS[key];}
    return;
  }

  const portData=rebase(allDates.map(d=>pm[d]?.portfolio_ret_pct??null));
  const spyData =rebase(allDates.map(d=>spyBM[d]??null));
  const qqqData =rebase(allDates.map(d=>qqqBM[d]??null));

  const firstDate=allDates[0], lastDate=allDates[allDates.length-1];
  const rebalIn=rebalDates.filter(d=>d>=firstDate&&d<=lastDate);
  const annotations={
    zeroline:{type:'line',yMin:0,yMax:0,
      borderColor:'rgba(108,92,231,.2)',borderWidth:1,borderDash:[2,4]}
  };
  rebalIn.forEach((d,i)=>{
    annotations['r'+i]={type:'line',xMin:d,xMax:d,
      borderColor:'rgba(108,92,231,.3)',borderWidth:1.5,borderDash:[4,4],
      label:{display:true,content:'리밸',position:'start',
        font:{size:9,weight:'bold'},color:'#6C5CE7',
        backgroundColor:'rgba(108,92,231,.1)',padding:{x:4,y:2},yAdjust:-4}};
  });

  // 구 차트 완전 제거 (안전망)
  if(CHS[key]){CHS[key].destroy();delete CHS[key];}
  const existing=Chart.getChart(ctx);
  if(existing)existing.destroy();
  const big=allDates.length>60;

  CHS[key]=new Chart(ctx,{
    type:'line',
    data:{labels:allDates,datasets:[
      {label:'포트폴리오',data:portData,
       borderColor:'#6C5CE7',backgroundColor:'rgba(108,92,231,.07)',
       borderWidth:2.5,pointRadius:big?0:4,pointHoverRadius:6,
       fill:true,tension:.3,spanGaps:true},
      {label:'SPY',data:spyData,
       borderColor:'#00b894',backgroundColor:'transparent',
       borderWidth:1.5,borderDash:[6,3],pointRadius:0,pointHoverRadius:5,
       fill:false,tension:.3,spanGaps:true},
      {label:'QQQ',data:qqqData,
       borderColor:'#e17055',backgroundColor:'transparent',
       borderWidth:1.5,borderDash:[3,3],pointRadius:0,pointHoverRadius:5,
       fill:false,tension:.3,spanGaps:true},
    ]},
    options:{responsive:true,
      interaction:{mode:'index',intersect:false},
      plugins:{
        legend:{labels:{color:'#8892a5',font:{size:12},
          usePointStyle:true,pointStyleWidth:10,boxHeight:8,padding:14}},
        tooltip:{
          backgroundColor:'rgba(26,23,68,.95)',borderColor:'rgba(108,92,231,.2)',
          borderWidth:1,padding:12,titleColor:'#fff',bodyColor:'#c8c5e8',
          callbacks:{
            label:c=>{
              if(c.raw==null)return null;
              return` ${c.dataset.label}: ${c.raw>0?'+':''}${c.raw.toFixed(2)}%`;
            },
            afterBody:items=>{
              const p=items.find(i=>i.dataset.label==='포트폴리오');
              const s=items.find(i=>i.dataset.label==='SPY');
              if(p?.raw!=null&&s?.raw!=null){
                const a=(p.raw-s.raw).toFixed(2);
                return['─────────',` Alpha vs SPY: ${a>0?'+':''}${a}%p`];
              }
              return[];
            }
          }
        },
        annotation:{annotations}
      },
      scales:{
        x:{ticks:{color:'#8892a5',maxTicksLimit:8,font:{size:11}},
           grid:{color:'rgba(108,92,231,.06)'}},
        y:{ticks:{color:'#8892a5',font:{size:11},callback:v=>(v>0?'+':'')+v+'%'},
           grid:{color:'rgba(108,92,231,.06)'}}
      }}
  });
}

/* ── SECTOR DONUT ── */
function renderSector(){
  if(!D)return;
  const ctx=document.getElementById('ch-sector');
  const wts={};
  (D.portfolio.holdings||[]).forEach(h=>{const s=h.sector||'Unknown';wts[s]=(wts[s]||0)+h.weight});
  const ent=Object.entries(wts).sort((a,b)=>b[1]-a[1]);
  if(CHS.sector)CHS.sector.destroy();
  CHS.sector=new Chart(ctx,{type:'doughnut',
    data:{labels:ent.map(([s])=>s),
      datasets:[{data:ent.map(([,w])=>w),
        backgroundColor:ent.map(([s])=>SCOL[s]||'#b2bec3'),
        borderColor:'#ffffff',borderWidth:2,hoverOffset:10}]},
    options:{responsive:true,cutout:'60%',
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>` ${c.label}: ${c.raw.toFixed(1)}%`}}}}
  });
}

/* ── SECTOR LIST ── */
function renderSectorList(holdings){
  const wts={};
  holdings.forEach(h=>{const s=h.sector||'Unknown';wts[s]=(wts[s]||0)+h.weight});
  const el=document.getElementById('slist');
  if(!el)return;
  el.innerHTML=Object.entries(wts).sort((a,b)=>b[1]-a[1]).map(([s,w])=>
    `<li class="si"><div class="sdot" style="background:${SCOL[s]||'#b2bec3'}"></div>
     <span class="sname">${s}</span><span class="spct">${w.toFixed(1)}%</span></li>`
  ).join('');
}

/* ── DESKTOP TABLE ── */
function renderTable(id,holdings,detail){
  const el=document.getElementById(id);if(!el)return;
  const hdr=detail
    ?'<tr><th></th><th>티커</th><th>종목명</th><th>섹터</th><th>비중</th><th>스코어</th><th>진입가</th><th>ROE%</th><th>마진%</th><th>6M수익</th><th>52W위치</th></tr>'
    :'<tr><th>티커</th><th>종목명</th><th>비중</th><th>스코어</th><th>진입가</th></tr>';
  const rows=holdings.map(h=>{
    const wb=`<div class="wb"><div class="wbg"><div class="wbf" style="width:${Math.min(h.weight/15*100,100)}%"></div></div><span class="wpct">${h.weight.toFixed(1)}%</span></div>`;
    const sc=h.score>=80?'pos':h.score>=60?'':'neg';
    if(detail)return`<tr>
      <td>${h.data_stale?'{{ic:warn}}':'{{ic:check}}'}</td>
      <td><b style="color:var(--accent)">${h.ticker}</b></td>
      <td style="max-width:130px;overflow:hidden;text-overflow:ellipsis;color:var(--mu)">${h.name}</td>
      <td><span class="badge bb">${h.sector||'—'}</span></td>
      <td>${wb}</td>
      <td>${h.score?`<span class="${sc}">${h.score.toFixed(1)}</span>`:'—'}</td>
      <td style="color:var(--mu)">${fm(h.entry_price)}</td>
      <td class="${fc(h.roe)}">${h.roe?h.roe.toFixed(1)+'%':'—'}</td>
      <td>${h.margin?h.margin.toFixed(1)+'%':'—'}</td>
      <td class="${fc(h.ret_6m)}">${h.ret_6m?fp(h.ret_6m):'—'}</td>
      <td>${h.w52_pos?h.w52_pos.toFixed(1)+'%':'—'}</td></tr>`;
    return`<tr>
      <td><b style="color:var(--accent)">${h.ticker}</b></td>
      <td style="color:var(--mu);font-size:12px">${h.name}</td>
      <td>${wb}</td>
      <td>${h.score?`<span class="${sc}">${h.score.toFixed(1)}</span>`:'—'}</td>
      <td style="color:var(--mu)">${fm(h.entry_price)}</td></tr>`;
  }).join('');
  el.innerHTML=`<table><thead>${hdr}</thead><tbody>${rows}</tbody></table>`;
}

/* ── MOBILE CARDS ── */
function renderCards(id,holdings){
  const el=document.getElementById(id);if(!el)return;
  el.innerHTML=holdings.filter(h=>h.ticker!=='CASH').map(h=>{
    const sc=h.score>=80?'pos':h.score>=60?'neu':'neg';
    const wp=Math.min(h.weight/15*100,100);
    return`<div class="mcard">
      <div class="mcard-head">
        <div><div class="mcard-ticker">${h.ticker}</div>
          <div class="mcard-name">${h.name}</div></div>
        <div><div class="mcard-score-val ${sc}">${h.score?h.score.toFixed(1):'—'}</div>
          <div class="mcard-score-lbl">스코어</div></div>
      </div>
      <div class="mcard-wbar">
        <div class="mcard-wlbl"><span>비중</span><span class="mcard-wpct">${h.weight.toFixed(1)}%</span></div>
        <div class="mcard-wbg"><div class="mcard-wbf" style="width:${wp}%"></div></div>
      </div>
      <div class="mcard-grid">
        <div class="mcard-item"><label>섹터</label>
          <span><span class="mcard-badge">${(h.sector||'—').replace('Communication Services','Comm.')}</span></span></div>
        <div class="mcard-item"><label>진입가</label><span style="color:var(--mu)">${fm(h.entry_price)}</span></div>
        <div class="mcard-item"><label>ROE</label><span class="${fc(h.roe)}">${h.roe?h.roe.toFixed(1)+'%':'—'}</span></div>
        <div class="mcard-item"><label>6M수익</label><span class="${fc(h.ret_6m)}">${h.ret_6m?fp(h.ret_6m):'—'}</span></div>
        <div class="mcard-item"><label>순이익률</label><span>${h.margin?h.margin.toFixed(1)+'%':'—'}</span></div>
        <div class="mcard-item"><label>52W위치</label><span>${h.w52_pos?h.w52_pos.toFixed(1)+'%':'—'}</span></div>
      </div></div>`;
  }).join('');
}

/* ── PERF KPIs ── */
function renderPerfKPIs(checks){
  const el=document.getElementById('perf-kpis');if(!el)return;
  const lat=checks.slice(-1)[0];
  const latPr=lat?.portfolio_ret_pct??null;
  const latSpy=(BM?.spy?.slice(-1)[0]?.ret)??(lat?.spy_ret_pct??null);
  const latQqq=(BM?.qqq?.slice(-1)[0]?.ret)??(lat?.qqq_ret_pct??null);
  const latAlpha=latSpy!=null&&latPr!=null?latPr-latSpy:(lat?.alpha_vs_spy??null);
  const alphas=checks.filter(r=>r.alpha_vs_spy!=null).map(r=>r.alpha_vs_spy);
  const avgA=alphas.length?alphas.reduce((a,b)=>a+b,0)/alphas.length:null;
  const ks=[
    {l:'최근 수익률',v:fp(latPr),c:fc(latPr||0)},
    {l:'SPY 대비 Alpha',v:latAlpha!=null?fp(latAlpha)+'p':'—',c:fc(latAlpha||0),s:latSpy!=null?'SPY '+fp(latSpy):''},
    {l:'QQQ 대비 Alpha',v:latQqq!=null&&latPr!=null?fp(latPr-latQqq)+'p':'—',
     c:fc(latQqq!=null&&latPr!=null?latPr-latQqq:0),s:latQqq!=null?'QQQ '+fp(latQqq):''},
    {l:'평균 Alpha vs SPY',v:avgA!=null?fp(avgA)+'p':'—',c:fc(avgA||0)},
  ];
  el.innerHTML=ks.map(k=>
    `<div class="card"><div class="ctitle">${k.l}</div>
     <div class="kval ${k.c}" style="font-size:26px">${k.v}</div>
     ${k.s?`<div class="ksub">${k.s}</div>`:''}
     </div>`
  ).join('');
}

/* ── PERF HISTORY TABLE ── */
function renderPerfHistTable(recs){
  const el=document.getElementById('perf-tbl');if(!el)return;
  const rows=[...recs].reverse().map(r=>`<tr>
    <td>${r.date}</td>
    <td><span class="badge ${r.type==='rebalancing'?'bb':'bt'}">${r.type==='rebalancing'?'리밸런싱':'성과체크'}</span></td>
    <td class="${fc(r.portfolio_ret_pct)}">${fp(r.portfolio_ret_pct)}</td>
    <td class="${fc(r.spy_ret_pct)}">${r.spy_ret_pct!=null?fp(r.spy_ret_pct):'—'}</td>
    <td class="${fc(r.qqq_ret_pct)}">${r.qqq_ret_pct!=null?fp(r.qqq_ret_pct):'—'}</td>
    <td class="${fc(r.alpha_vs_spy)}">${r.alpha_vs_spy!=null?fp(r.alpha_vs_spy)+'p':'—'}</td>
  </tr>`).join('');
  el.innerHTML=`<table><thead><tr>
    <th>날짜</th><th>구분</th><th>포트폴리오</th><th>SPY</th><th>QQQ</th><th>Alpha</th>
  </tr></thead><tbody>${rows}</tbody></table>`;
}

/* ── RISK ── */
function renderRisk(p,holdings,cw){
  const me=p.max_equity||0,MDD=-15;
  const pct=Math.min(Math.max((me+30)/60,0),1),angle=pct*180;
  const col=me>=0?'#00b894':me>-10?'#fdcb6e':me>MDD?'#e17055':'#d63031';
  const rad=(angle-180)*Math.PI/180;
  const ex=(100+80*Math.cos(rad)).toFixed(1),ey=(100+80*Math.sin(rad)).toFixed(1);
  const la=angle>180?1:0;
  document.getElementById('mdd-gauge').innerHTML=`
    <div class="gauge-wrap">
      <svg viewBox="0 0 200 110" style="width:210px">
        <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="rgba(108,92,231,.1)" stroke-width="14" stroke-linecap="round"/>
        <path d="M20,100 A80,80 0 0,1 60,27"  fill="none" stroke="#e17055" stroke-width="14" opacity=".2" stroke-linecap="butt"/>
        <path d="M60,27 A80,80 0 0,1 100,20"  fill="none" stroke="#fdcb6e" stroke-width="14" opacity=".2" stroke-linecap="butt"/>
        <path d="M100,20 A80,80 0 0,1 180,100" fill="none" stroke="#00b894" stroke-width="14" opacity=".2" stroke-linecap="round"/>
        ${angle>0?`<path d="M20,100 A80,80 0 ${la},1 ${ex},${ey}" fill="none" stroke="${col}" stroke-width="14" stroke-linecap="round"/>`:''}
        <circle cx="${ex}" cy="${ey}" r="7" fill="${col}"/>
      </svg>
      <div class="gval" style="color:${col}">${fp(me)}</div>
      <div class="glabel">MDD 기준 수익률 | 경보: ${MDD}%</div>
    </div>`;

  const [rcl,rl,re]=cw>=50?['r-fear','공포','{{ic:dot-rd}}']:cw>=40?['r-caution','주의','{{ic:dot-yw}}']:['r-normal','정상','{{ic:dot-gn}}'];
  document.getElementById('vix-regime').innerHTML=
    `<div class="regime ${rcl}"><div class="rlabel">${re} ${rl}</div>
     <div class="rsub">현금 비중: ${cw}%</div></div>`;

  const alerted=p.last_stoploss_alerts||{};
  document.getElementById('sl-alerts').innerHTML=Object.keys(alerted).length
    ?Object.entries(alerted).map(([t,d])=>
        `<div class="al al-err">{{ic:warn}} <b>${t}</b> — 알림: ${d}</div>`).join('')
    :'<div class="al al-ok">{{ic:check}} 이번 달 스톱로스 알림 없음</div>';

  const SL=-15,WN=-10;
  const stks=holdings.filter(h=>h.ticker!=='CASH');
  document.getElementById('sl-tbl').innerHTML=`<table><thead><tr>
    <th></th><th>티커</th><th>종목명</th><th>진입가</th>
    <th>경고(${WN}%)</th><th>스톱로스(${SL}%)</th><th>진입일</th>
  </tr></thead><tbody>${stks.map(h=>{
    const ep=h.entry_price||0;
    return`<tr><td>${h.ticker in alerted?'{{ic:warn}}':'{{ic:check}}'}</td>
      <td><b style="color:var(--accent)">${h.ticker}</b></td>
      <td style="color:var(--mu)">${h.name}</td>
      <td>${fm(ep)}</td>
      <td style="color:var(--yw)">${fm(ep*(1+WN/100))}</td>
      <td style="color:var(--rd)">${fm(ep*(1+SL/100))}</td>
      <td style="color:var(--mu)">${h.entry_date||'—'}</td></tr>`;
  }).join('')}</tbody></table>`;
}

/* ── SCORE CHART ── */
function renderScore(){
  if(!D)return;
  const ctx=document.getElementById('ch-score');if(!ctx)return;
  const stks=(D.portfolio.holdings||[]).filter(h=>h.ticker!=='CASH')
    .sort((a,b)=>(b.score||0)-(a.score||0));
  const fin=stks.map(h=>{
    let s=0;
    if(h.roe>=40)s+=10;else if(h.roe>=25)s+=8;else if(h.roe>=15)s+=5;else s+=2;
    if(h.margin>=30)s+=10;else if(h.margin>=20)s+=8;else if(h.margin>=10)s+=5;else s+=2;
    if(h.fcf_margin>=20)s+=10;else if(h.fcf_margin>=10)s+=8;else if(h.fcf_margin>=0)s+=5;
    if(h.rev_growth>=20)s+=10;else if(h.rev_growth>=10)s+=7;else if(h.rev_growth>=0)s+=4;
    return Math.min(s,40);
  });
  const tec=stks.map(h=>h.w52_pos>=80?20:h.w52_pos>=60?15:h.w52_pos>=40?10:5);
  const mom=stks.map((h,i)=>Math.max((h.score||0)-fin[i]-tec[i],0));
  if(CHS.score)CHS.score.destroy();
  CHS.score=new Chart(ctx,{type:'bar',
    data:{labels:stks.map(h=>h.ticker),datasets:[
      {label:'재무품질(40pt)',data:fin,backgroundColor:'#6C5CE7'},
      {label:'기술적(20pt)', data:tec,backgroundColor:'#00b894'},
      {label:'모멘텀(40pt)', data:mom,backgroundColor:'#fdcb6e'},
    ]},
    options:{indexAxis:'y',responsive:true,
      plugins:{legend:{labels:{color:'#8892a5',font:{size:12}}}},
      scales:{
        x:{stacked:true,max:105,ticks:{color:'#8892a5'},grid:{color:'rgba(108,92,231,.06)'}},
        y:{stacked:true,ticks:{color:'#1a1a3e',font:{weight:'bold'}},grid:{display:false}}
      }}
  });
}

setInterval(()=>{
  const t=new Date().toLocaleTimeString('ko-KR');
  ['sb-clock','tb-clock'].forEach(id=>{const e=document.getElementById(id);if(e)e.textContent=t});
},1000);

load();
setInterval(load,300_000);
</script>
</body>
</html>
"""

# ── Inline SVG icon set (replaces emoji glyphs for consistent cross-platform rendering) ──
def _ic(paths, sw="2"):
    return (f'<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
            f'xmlns="http://www.w3.org/2000/svg" style="vertical-align:-0.15em;flex-shrink:0">{paths}</svg>')

def _dot(var):
    return (f'<svg viewBox="0 0 24 24" width="0.6em" height="0.6em" xmlns="http://www.w3.org/2000/svg" '
            f'style="vertical-align:0.05em;flex-shrink:0"><circle cx="12" cy="12" r="10" fill="var({var})"/></svg>')

ICONS = {
    'home':      _ic('<path d="M3 9.5 12 3l9 6.5V20a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>'),
    'portfolio': _ic('<path d="M3 3v16a2 2 0 0 0 2 2h16"/><rect x="7" y="13" width="3" height="5" rx="1"/><rect x="12" y="9" width="3" height="9" rx="1"/><rect x="17" y="5" width="3" height="13" rx="1"/>'),
    'trend':     _ic('<polyline points="3 17 9 11 13 15 21 6"/><polyline points="15 6 21 6 21 12"/>'),
    'risk':      _ic('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>'),
    'changes':   _ic('<path d="M21 12A9 9 0 0 0 6 5.3L3 8"/><path d="M3 4v4h4"/><path d="M3 12a9 9 0 0 0 15 6.7l3-2.7"/><path d="M21 16v4h-4"/>'),
    'logs':      _ic('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h6"/>'),
    'roadmap':   _ic('<path d="M9 18 3 21V6l6-3 6 3 6-3v15l-6 3-6-3Z"/><path d="M9 3v15"/><path d="M15 6v15"/>'),
    'calendar':  _ic('<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M4 10h16"/><path d="M8 3v4"/><path d="M16 3v4"/>'),
    'check':     _ic('<path d="M21 11.5a9 9 0 1 1-5.5-8.3"/><path d="M21 5 12 14l-3-3"/>'),
    'warn':      _ic('<circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16h.01"/>'),
    'tool':      _ic('<path d="M15 6a4.5 4.5 0 0 1 6 6l-7.5 7.5a2.1 2.1 0 0 1-3-3L18 9a4.5 4.5 0 0 1-6-6L9.5 5.5l3 3Z"/>'),
    'pin':       _ic('<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>'),
    'idea':      _ic('<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.7.6 1 1.5 1 2.5h6c0-1 .3-1.9 1-2.5A6 6 0 0 0 12 3Z"/>'),
    'up':        _ic('<path d="M12 19V5"/><path d="m6 11 6-6 6 6"/>'),
    'down':      _ic('<path d="M12 5v14"/><path d="m6 13 6 6 6-6"/>'),
    'dot-gn':    _dot('--gn'),
    'dot-rd':    _dot('--rd'),
    'dot-yw':    _dot('--yw'),
    'dot-mu':    _dot('--mu'),
}

MAIN = re.sub(r'\{\{ic:([\w-]+)\}\}', lambda m: ICONS.get(m.group(1), ''), MAIN)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8502)
