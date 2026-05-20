import os, json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

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

@app.get("/", response_class=HTMLResponse)
def index(token: str = ""):
    if token != TOKEN:
        return HTMLResponse("""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>US Portfolio</title>
<style>*{margin:0;padding:0;box-sizing:border-box}
body{background:#0B0E17;color:#e2e8f0;font-family:system-ui,sans-serif;
  display:flex;align-items:center;justify-content:center;min-height:100vh}
.c{background:#131820;border:1px solid #1E2840;border-radius:16px;padding:48px 40px;text-align:center}
.lock{font-size:52px;margin-bottom:20px}.t{font-size:22px;font-weight:700;margin-bottom:8px}
code{color:#00C6A9;background:rgba(0,198,169,.12);padding:2px 8px;border-radius:4px;font-size:13px}
</style></head><body><div class="c"><div class="lock">🔒</div>
<div class="t">접근 제한</div>
<p style="color:#64748b;font-size:14px;margin-top:8px">URL에 <code>?token=scanner2024</code> 추가</p>
</div></body></html>""")
    return HTMLResponse(MAIN.replace("__TOKEN__", token))

MAIN = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>US Portfolio Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>
:root{
  --bg:#0B0E17; --s1:#131820; --s2:#1B2236; --bd:#1E2840;
  --tx:#e2e8f0; --mu:#64748b;
  --pr:#00C6A9; --gn:#22c55e; --rd:#ef4444;
  --bl:#6366f1; --gd:#f59e0b; --or:#f97316;
  --sb:220px;
}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:16px;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--tx);
  font-family:system-ui,-apple-system,'Segoe UI',sans-serif;min-height:100vh}

/* ══ SIDEBAR (PC) ══ */
.sidebar{
  position:fixed;top:0;left:0;bottom:0;width:var(--sb);
  background:var(--s1);border-right:1px solid var(--bd);
  display:flex;flex-direction:column;padding:20px 12px;z-index:200;
}
.sb-logo{display:flex;align-items:center;gap:8px;padding:4px 8px;margin-bottom:6px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--gn);
  box-shadow:0 0 8px var(--gn);flex-shrink:0;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.sb-logo-txt{font-size:15px;font-weight:800}
.sb-month{font-size:11px;color:var(--mu);padding:0 8px;margin-bottom:20px}
.sidenav{list-style:none;flex:1}
.snitem{display:flex;align-items:center;gap:10px;padding:10px 12px;
  border-radius:9px;cursor:pointer;font-size:14px;font-weight:500;
  color:var(--mu);transition:all .15s;margin-bottom:2px}
.snitem:hover{background:var(--s2);color:var(--tx)}
.snitem.on{background:rgba(0,198,169,.12);color:var(--pr);font-weight:700}
.snitem .ic{font-size:16px;width:20px;text-align:center}
.sb-footer{border-top:1px solid var(--bd);padding-top:14px;margin-top:4px}
.sb-clock{font-size:12px;color:var(--mu);padding:0 8px}
.sb-upd{font-size:11px;color:var(--mu);padding:4px 8px 0;opacity:.7}

/* ══ MOBILE TOP BAR ══ */
.topbar{display:none;position:fixed;top:0;left:0;right:0;height:54px;
  background:var(--s1);border-bottom:1px solid var(--bd);
  align-items:center;padding:0 16px;gap:8px;z-index:200}
.tb-logo{display:flex;align-items:center;gap:7px;flex:1}
.tb-txt{font-size:15px;font-weight:800}
.tb-month{font-size:12px;color:var(--mu)}
.tb-clock{font-size:12px;color:var(--mu)}

/* ══ MOBILE BOTTOM NAV ══ */
.mnav{display:none;position:fixed;bottom:0;left:0;right:0;height:62px;
  background:var(--s1);border-top:1px solid var(--bd);z-index:200}
.mnavitems{display:flex;height:100%}
.mnavitem{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:3px;border:none;background:transparent;
  color:var(--mu);font-size:10px;cursor:pointer;transition:color .15s}
.mnavitem.on{color:var(--pr)}
.mnavitem .mic{font-size:20px;line-height:1}

/* ══ MAIN CONTENT ══ */
.main{margin-left:var(--sb);padding:28px;min-height:100vh}
.sec{display:none}.sec.on{display:block}

/* ══ PAGE HEADER ══ */
.phdr{margin-bottom:22px}
.ptitle{font-size:20px;font-weight:800}
.psub{font-size:13px;color:var(--mu);margin-top:4px}

/* ══ KPI GRID ══ */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
.kpi{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:18px 20px}
.klabel{font-size:11px;color:var(--mu);margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em}
.kval{font-size:26px;font-weight:800;line-height:1;letter-spacing:-.02em}
.ksub{font-size:11px;color:var(--mu);margin-top:5px}
.pos{color:var(--gn)}.neg{color:var(--rd)}.neu{color:var(--pr)}

/* ══ CARDS ══ */
.card{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:20px}
.cc{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:20px}
.ctitle{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:14px}

/* ══ PC LAYOUT GRIDS ══ */
.home-grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;align-items:start}
.home-list{max-height:520px;overflow-y:auto}
.port-grid{display:grid;grid-template-columns:340px 1fr;gap:16px;margin-bottom:16px;align-items:start}
.risk-grid{display:grid;grid-template-columns:1fr 1.6fr;gap:16px;margin-bottom:16px;align-items:start}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
.mb16{margin-bottom:16px}

/* ══ CHART FILTER ══ */
.cf{display:flex;align-items:center;gap:6px;margin-bottom:14px}
.cf-lbl{font-size:11px;color:var(--mu);margin-right:4px}
.cfbtn{padding:4px 12px;border-radius:6px;border:1px solid var(--bd);
  background:transparent;color:var(--mu);font-size:12px;font-weight:600;
  cursor:pointer;transition:all .15s}
.cfbtn.on{background:var(--pr);color:#fff;border-color:var(--pr)}
.cfbtn:hover:not(.on){background:var(--s2);color:var(--tx)}

/* ══ TABLE ══ */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px 12px;background:var(--s2);color:var(--mu);
  font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:.06em;white-space:nowrap}
th:first-child{border-radius:6px 0 0 6px}th:last-child{border-radius:0 6px 6px 0}
td{padding:10px 12px;border-bottom:1px solid var(--bd);white-space:nowrap}
tr:hover td{background:rgba(255,255,255,.025)}
tr:last-child td{border-bottom:none}

/* ══ WEIGHT BAR ══ */
.wb{display:flex;align-items:center;gap:8px;min-width:110px}
.wbg{flex:1;height:5px;border-radius:3px;background:var(--bd);overflow:hidden}
.wbf{height:5px;border-radius:3px;background:var(--pr)}
.wpct{font-size:12px;font-weight:700;min-width:38px;text-align:right}

/* ══ BADGES ══ */
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600}
.bg{background:rgba(34,197,94,.12);color:var(--gn)}
.br{background:rgba(239,68,68,.12);color:var(--rd)}
.bb{background:rgba(99,102,241,.12);color:var(--bl)}
.bo{background:rgba(245,158,11,.12);color:var(--gd)}
.bt{background:rgba(0,198,169,.12);color:var(--pr)}

/* ══ SECTOR LIST ══ */
.slist{list-style:none}
.si{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--bd)}
.si:last-child{border-bottom:none}
.sdot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.sname{flex:1;font-size:13px}
.spct{font-size:13px;font-weight:700;color:var(--pr)}

/* ══ GAUGE ══ */
.gauge-wrap{display:flex;flex-direction:column;align-items:center;padding:10px 0 4px}
.gval{font-size:34px;font-weight:800;margin:8px 0 4px;line-height:1}
.glabel{font-size:12px;color:var(--mu)}

/* ══ REGIME ══ */
.regime{padding:16px;border-radius:10px;text-align:center;margin-bottom:14px}
.r-normal{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2)}
.r-caution{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.2)}
.r-fear{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2)}
.rlabel{font-size:22px;font-weight:800}
.rsub{font-size:12px;color:var(--mu);margin-top:4px}

/* ══ ALERTS ══ */
.al{padding:12px 16px;border-radius:8px;margin-bottom:8px;font-size:13px}
.al-ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:var(--gn)}
.al-err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);color:var(--rd)}

/* ══ MOBILE HOLDING CARDS ══ */
.mcards{display:none}
.mcard{background:var(--s2);border:1px solid var(--bd);border-radius:12px;
  padding:14px 16px;margin-bottom:10px}
.mcard-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}
.mcard-ticker{font-size:17px;font-weight:800;color:var(--pr)}
.mcard-name{font-size:11px;color:var(--mu);margin-top:2px;
  max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mcard-score-val{font-size:17px;font-weight:800}
.mcard-score-lbl{font-size:10px;color:var(--mu);text-align:right}
.mcard-wbar{margin-bottom:12px}
.mcard-wlbl{display:flex;justify-content:space-between;font-size:11px;
  color:var(--mu);margin-bottom:4px}
.mcard-wpct{font-weight:700;color:var(--tx)}
.mcard-wbg{height:6px;border-radius:3px;background:var(--bd);overflow:hidden}
.mcard-wbf{height:6px;border-radius:3px;background:var(--pr)}
.mcard-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.mcard-item label{font-size:10px;color:var(--mu);display:block;margin-bottom:3px}
.mcard-item span{font-size:13px;font-weight:600}
.mcard-badge{display:inline-block;padding:2px 7px;border-radius:20px;
  font-size:10px;font-weight:600;background:rgba(99,102,241,.12);color:var(--bl)}

/* ══ RESPONSIVE ══ */
@media(max-width:1024px){
  .home-grid{grid-template-columns:1fr}
  .port-grid{grid-template-columns:1fr}
  .risk-grid{grid-template-columns:1fr}
}
@media(max-width:768px){
  :root{--sb:0px}
  .sidebar{display:none}
  .topbar{display:flex}
  .mnav{display:block}
  .main{margin-left:0;padding:62px 14px 74px}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .kpis .kpi:nth-child(5){grid-column:1/-1}
  .kval{font-size:22px}
  .g3{grid-template-columns:1fr}
  th,td{padding:8px 10px}
  table{font-size:12px}
  .desk-tbl{display:none}
  .mcards{display:block}
  .home-list{max-height:none;overflow-y:visible}
}
@media(max-width:420px){
  .kpis{grid-template-columns:1fr 1fr}
}
</style>
</head>
<body>

<!-- ══ SIDEBAR (PC) ══ -->
<nav class="sidebar">
  <div class="sb-logo">
    <div class="dot"></div>
    <span class="sb-logo-txt">US Portfolio</span>
  </div>
  <div class="sb-month" id="sb-month"></div>
  <ul class="sidenav">
    <li class="snitem on" onclick="go('home')"><span class="ic">🏠</span>홈</li>
    <li class="snitem"    onclick="go('port')"><span class="ic">📊</span>포트폴리오</li>
    <li class="snitem"    onclick="go('perf')"><span class="ic">📈</span>성과 분석</li>
    <li class="snitem"    onclick="go('risk')"><span class="ic">⚠️</span>리스크</li>
  </ul>
  <div class="sb-footer">
    <div class="sb-clock" id="sb-clock"></div>
    <div class="sb-upd" id="sb-upd"></div>
  </div>
</nav>

<!-- ══ MOBILE TOP BAR ══ -->
<div class="topbar">
  <div class="tb-logo">
    <div class="dot"></div>
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
    <div class="kpis" id="kpis"></div>
    <div class="home-grid">
      <div class="cc">
        <div class="ctitle">성과 추이 — 포트폴리오 vs SPY vs QQQ</div>
        <div class="cf">
          <span class="cf-lbl">기간</span>
          <button class="cfbtn" onclick="setRange('1M','home')">1M</button>
          <button class="cfbtn" onclick="setRange('3M','home')">3M</button>
          <button class="cfbtn" onclick="setRange('6M','home')">6M</button>
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
      <div style="display:flex;flex-direction:column;gap:16px">
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
    <div class="cc mb16">
      <div class="ctitle">누적 수익률 추이</div>
      <div class="cf">
        <span class="cf-lbl">기간</span>
        <button class="cfbtn" onclick="setRange('1M','perf')">1M</button>
        <button class="cfbtn" onclick="setRange('3M','perf')">3M</button>
        <button class="cfbtn" onclick="setRange('6M','perf')">6M</button>
        <button class="cfbtn on" id="cfbtn-perf-ALL" onclick="setRange('ALL','perf')">ALL</button>
      </div>
      <canvas id="ch-perf" height="200"></canvas>
    </div>
    <div class="g3" id="perf-kpis"></div>
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
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="card">
          <div class="ctitle">VIX 레짐</div>
          <div id="vix-regime"></div>
          <div class="tw"><table>
            <tr><th>레짐</th><th>조건</th><th>현금비중</th></tr>
            <tr><td>🟢 정상</td><td>VIX &lt; 30</td><td>30%</td></tr>
            <tr><td>🟡 주의</td><td>VIX ≥ 30</td><td>50%</td></tr>
            <tr><td>🔴 공포</td><td>VIX ≥ 40</td><td>60%</td></tr>
          </table></div>
        </div>
        <div class="card">
          <div class="ctitle">스톱로스 현황</div>
          <div id="sl-alerts"></div>
        </div>
      </div>
    </div>
    <div class="card mb16">
      <div class="ctitle">진입가 기준 스톱로스 가격표</div>
      <div class="tw" id="sl-tbl"></div>
    </div>
    <div class="card">
      <div class="ctitle">종목별 스코어 분석</div>
      <canvas id="ch-score" height="220"></canvas>
    </div>
  </div>

</div><!-- /main -->

<!-- ══ MOBILE BOTTOM NAV ══ -->
<nav class="mnav">
  <div class="mnavitems">
    <button class="mnavitem on" onclick="go('home')"><span class="mic">🏠</span><span>홈</span></button>
    <button class="mnavitem"   onclick="go('port')"><span class="mic">📊</span><span>포트폴리오</span></button>
    <button class="mnavitem"   onclick="go('perf')"><span class="mic">📈</span><span>성과</span></button>
    <button class="mnavitem"   onclick="go('risk')"><span class="mic">⚠️</span><span>리스크</span></button>
  </div>
</nav>

<script>
const TK='__TOKEN__';
const SCOL={
  'Technology':'#6366f1','Communication Services':'#00C6A9',
  'Energy':'#f59e0b','Basic Materials':'#f97316',
  'Healthcare':'#22c55e','Consumer Discretionary':'#ec4899',
  'Financials':'#3b82f6','Industrials':'#8b5cf6',
  'Cash':'#374151','Unknown':'#94a3b8'
};
let D=null,CHS={},RANGE={home:'ALL',perf:'ALL'};

const fp=(v,s=true)=>v==null||isNaN(v)?'—':(s&&v>0?'+':'')+v.toFixed(2)+'%';
const fm=v=>v==null?'—':'$'+v.toFixed(2);
const fc=v=>v>0?'pos':v<0?'neg':'';

function go(name){
  document.querySelectorAll('.sec').forEach(e=>e.classList.remove('on'));
  document.querySelectorAll('.snitem,.mnavitem').forEach(e=>e.classList.remove('on'));
  document.getElementById('s-'+name).classList.add('on');
  document.querySelectorAll('[onclick="go(\''+name+'\')"]').forEach(e=>e.classList.add('on'));
  if(name==='port' && !CHS.sector) renderSector();
  if(name==='perf' && !CHS.perf)  renderPerfChart('ch-perf','perf');
  if(name==='risk' && !CHS.score) renderScore();
}

async function load(){
  try{
    const r=await fetch('/api/data?token='+TK);
    if(!r.ok) throw new Error();
    D=await r.json(); render();
  }catch{
    document.querySelector('.main').innerHTML=
      '<div style="text-align:center;padding:80px;color:#ef4444">데이터 로드 실패</div>';
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
  const sr=lat?lat.spy_ret_pct:null;
  const qr=lat?lat.qqq_ret_pct:null;
  const al=lat?lat.alpha_vs_spy:null;

  // nav labels
  const mon=p.month||'';
  document.getElementById('sb-month').textContent=mon;
  document.getElementById('tb-month').textContent=mon?'  '+mon:'';
  document.getElementById('sb-upd').textContent='갱신 '+updated;
  document.getElementById('home-sub').textContent=
    `리밸런싱 월: ${mon||'—'} | ${stocks.length}종목 + 현금 ${cw}%`;

  // KPIs
  const prev=checks.slice(-2,-1)[0];
  const deltaPr=prev?pr-prev.portfolio_ret_pct:null;
  const ks=[
    {l:'포트폴리오 수익률',v:fp(pr),c:fc(pr),
      s:deltaPr!=null?`전일比 ${fp(deltaPr)}`:'최근 성과 체크'},
    {l:'Alpha vs SPY',v:al!=null?fp(al)+'p':'—',c:fc(al),s:'SPY '+fp(sr)},
    {l:'Alpha vs QQQ',v:qr!=null?fp(pr-qr)+'p':'—',c:fc(qr!=null?pr-qr:0),s:'QQQ '+fp(qr)},
    {l:'보유 종목',v:stocks.length+'종목',c:'neu',
      s:new Set(stocks.map(h=>h.sector)).size+'개 섹터'},
    {l:'현금 비중',v:cw+'%',c:cw>30?'neg':'neu',
      s:cw>30?'VIX 방어 중':'기본 비중'},
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
    if(b) b.classList.toggle('on',r===range);
  });
  delete CHS[key];
  renderPerfChart('ch-'+key,key);
}

/* ── LINE CHART (chart + rebalancing markers) ── */
function renderPerfChart(canvasId,key){
  if(!D)return;
  const ctx=document.getElementById(canvasId);
  if(!ctx)return;
  const allRecs=D.performance.records||[];
  const rebalDates=allRecs.filter(r=>r.type==='rebalancing').map(r=>r.date);
  const perfRecs=filterByRange(
    allRecs.filter(r=>r.type!=='rebalancing'&&r.portfolio_ret_pct!=null),
    RANGE[key]||'ALL'
  );
  if(!perfRecs.length){if(CHS[key])CHS[key].destroy();delete CHS[key];return;}

  const firstDate=perfRecs[0].date, lastDate=perfRecs[perfRecs.length-1].date;
  // 리밸런싱 날짜를 labels에 삽입해 순서 보장, 데이터는 null
  const rebalIn=rebalDates.filter(d=>d>firstDate&&d<lastDate);
  const allDates=[...new Set([...perfRecs.map(r=>r.date),...rebalIn])].sort();
  const pm=Object.fromEntries(perfRecs.map(r=>[r.date,r]));

  const annotations={};
  rebalIn.forEach((d,i)=>{
    annotations['r'+i]={type:'line',xMin:d,xMax:d,
      borderColor:'rgba(99,102,241,.55)',borderWidth:1.5,borderDash:[4,4],
      label:{display:true,content:'리밸',position:'start',
        font:{size:9,weight:'bold'},color:'#818cf8',
        backgroundColor:'rgba(99,102,241,.12)',
        padding:{x:4,y:2},yAdjust:-4}};
  });

  if(CHS[key])CHS[key].destroy();
  const big=allDates.length>60;
  CHS[key]=new Chart(ctx,{
    type:'line',
    data:{labels:allDates,datasets:[
      {label:'포트폴리오',
       data:allDates.map(d=>pm[d]?.portfolio_ret_pct??null),
       borderColor:'#00C6A9',backgroundColor:'rgba(0,198,169,.1)',
       borderWidth:2.5,pointRadius:big?0:5,fill:true,tension:.3,spanGaps:true},
      {label:'SPY',
       data:allDates.map(d=>pm[d]?.spy_ret_pct??null),
       borderColor:'#6366f1',backgroundColor:'transparent',
       borderWidth:1.5,borderDash:[6,3],pointRadius:big?0:4,tension:.3,spanGaps:true},
      {label:'QQQ',
       data:allDates.map(d=>pm[d]?.qqq_ret_pct??null),
       borderColor:'#f59e0b',backgroundColor:'transparent',
       borderWidth:1.5,borderDash:[3,3],pointRadius:big?0:4,tension:.3,spanGaps:true},
    ]},
    options:{responsive:true,
      plugins:{
        legend:{labels:{color:'#94a3b8',font:{size:12}}},
        tooltip:{mode:'index',intersect:false,
          filter:i=>i.raw!=null,
          callbacks:{label:c=>` ${c.dataset.label}: ${c.raw!=null?c.raw.toFixed(2)+'%':'—'}`}},
        annotation:{annotations}},
      scales:{
        x:{ticks:{color:'#64748b',maxTicksLimit:8},grid:{color:'#1E2840'}},
        y:{ticks:{color:'#64748b',callback:v=>v+'%'},grid:{color:'#1E2840'}}
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
        backgroundColor:ent.map(([s])=>SCOL[s]||'#94a3b8'),
        borderColor:'#0B0E17',borderWidth:2,hoverOffset:10}]},
    options:{responsive:true,cutout:'58%',
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
    `<li class="si"><div class="sdot" style="background:${SCOL[s]||'#94a3b8'}"></div>
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
      <td>${h.data_stale?'⚠️':'✅'}</td>
      <td><b style="color:var(--pr)">${h.ticker}</b></td>
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
      <td><b style="color:var(--pr)">${h.ticker}</b></td>
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
  const alphas=checks.filter(r=>r.alpha_vs_spy!=null).map(r=>r.alpha_vs_spy);
  const avgA=alphas.length?alphas.reduce((a,b)=>a+b,0)/alphas.length:null;
  const ks=[
    {l:'최근 수익률',v:fp(lat?.portfolio_ret_pct),c:fc(lat?.portfolio_ret_pct||0)},
    {l:'최근 Alpha vs SPY',v:lat?.alpha_vs_spy!=null?fp(lat.alpha_vs_spy)+'p':'—',c:fc(lat?.alpha_vs_spy||0)},
    {l:'평균 Alpha',v:avgA!=null?fp(avgA)+'p':'—',c:fc(avgA||0)},
  ];
  el.innerHTML=ks.map(k=>
    `<div class="card"><div class="ctitle">${k.l}</div>
     <div class="kval ${k.c}" style="font-size:28px">${k.v}</div></div>`
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
  const me=p.max_equity||0, MDD=-15;
  const pct=Math.min(Math.max((me+30)/60,0),1), angle=pct*180;
  const col=me>=0?'#22c55e':me>-10?'#f59e0b':me>MDD?'#f97316':'#ef4444';
  const rad=(angle-180)*Math.PI/180;
  const ex=(100+80*Math.cos(rad)).toFixed(1), ey=(100+80*Math.sin(rad)).toFixed(1);
  const la=angle>180?1:0;
  document.getElementById('mdd-gauge').innerHTML=`
    <div class="gauge-wrap">
      <svg viewBox="0 0 200 110" style="width:210px">
        <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="#1E2840" stroke-width="14" stroke-linecap="round"/>
        <path d="M20,100 A80,80 0 0,1 60,27"  fill="none" stroke="#ef4444" stroke-width="14" opacity=".3" stroke-linecap="butt"/>
        <path d="M60,27 A80,80 0 0,1 100,20"  fill="none" stroke="#f97316" stroke-width="14" opacity=".3" stroke-linecap="butt"/>
        <path d="M100,20 A80,80 0 0,1 180,100" fill="none" stroke="#22c55e" stroke-width="14" opacity=".3" stroke-linecap="round"/>
        ${angle>0?`<path d="M20,100 A80,80 0 ${la},1 ${ex},${ey}" fill="none" stroke="${col}" stroke-width="14" stroke-linecap="round"/>`:''}
        <circle cx="${ex}" cy="${ey}" r="7" fill="${col}"/>
      </svg>
      <div class="gval" style="color:${col}">${fp(me)}</div>
      <div class="glabel">MDD 기준 수익률 | 경보: ${MDD}%</div>
    </div>`;

  const [rcl,rl,re]=cw>=50?['r-fear','공포','🔴']:cw>=40?['r-caution','주의','🟡']:['r-normal','정상','🟢'];
  document.getElementById('vix-regime').innerHTML=
    `<div class="regime ${rcl}"><div class="rlabel">${re} ${rl}</div>
     <div class="rsub">현금 비중: ${cw}%</div></div>`;

  const alerted=p.last_stoploss_alerts||{};
  document.getElementById('sl-alerts').innerHTML=Object.keys(alerted).length
    ?Object.entries(alerted).map(([t,d])=>
        `<div class="al al-err">🔴 <b>${t}</b> — 알림: ${d}</div>`).join('')
    :'<div class="al al-ok">✅ 이번 달 스톱로스 알림 없음</div>';

  const SL=-15,WN=-10;
  const stocks=holdings.filter(h=>h.ticker!=='CASH');
  document.getElementById('sl-tbl').innerHTML=`<table><thead><tr>
    <th></th><th>티커</th><th>종목명</th><th>진입가</th>
    <th>경고(${WN}%)</th><th>스톱로스(${SL}%)</th><th>진입일</th>
  </tr></thead><tbody>${stocks.map(h=>{
    const ep=h.entry_price||0;
    return`<tr><td>${h.ticker in alerted?'🔴':'✅'}</td>
      <td><b style="color:var(--pr)">${h.ticker}</b></td>
      <td style="color:var(--mu)">${h.name}</td>
      <td>${fm(ep)}</td>
      <td style="color:var(--gd)">${fm(ep*(1+WN/100))}</td>
      <td style="color:var(--rd)">${fm(ep*(1+SL/100))}</td>
      <td style="color:var(--mu)">${h.entry_date||'—'}</td></tr>`;
  }).join('')}</tbody></table>`;
}

/* ── SCORE CHART ── */
function renderScore(){
  if(!D)return;
  const ctx=document.getElementById('ch-score');if(!ctx)return;
  const stocks=(D.portfolio.holdings||[]).filter(h=>h.ticker!=='CASH')
    .sort((a,b)=>(b.score||0)-(a.score||0));
  const fin=stocks.map(h=>{
    let s=0;
    if(h.roe>=40)s+=10;else if(h.roe>=25)s+=8;else if(h.roe>=15)s+=5;else s+=2;
    if(h.margin>=30)s+=10;else if(h.margin>=20)s+=8;else if(h.margin>=10)s+=5;else s+=2;
    if(h.fcf_margin>=20)s+=10;else if(h.fcf_margin>=10)s+=8;else if(h.fcf_margin>=0)s+=5;
    if(h.rev_growth>=20)s+=10;else if(h.rev_growth>=10)s+=7;else if(h.rev_growth>=0)s+=4;
    return Math.min(s,40);
  });
  const tec=stocks.map(h=>h.w52_pos>=80?20:h.w52_pos>=60?15:h.w52_pos>=40?10:5);
  const mom=stocks.map((h,i)=>Math.max((h.score||0)-fin[i]-tec[i],0));
  if(CHS.score)CHS.score.destroy();
  CHS.score=new Chart(ctx,{type:'bar',
    data:{labels:stocks.map(h=>h.ticker),datasets:[
      {label:'재무품질(40pt)',data:fin,backgroundColor:'#6366f1'},
      {label:'기술적(20pt)', data:tec,backgroundColor:'#22c55e'},
      {label:'모멘텀(40pt)', data:mom,backgroundColor:'#f59e0b'},
    ]},
    options:{indexAxis:'y',responsive:true,
      plugins:{legend:{labels:{color:'#94a3b8',font:{size:12}}}},
      scales:{
        x:{stacked:true,max:105,ticks:{color:'#64748b'},grid:{color:'#1E2840'}},
        y:{stacked:true,ticks:{color:'#e2e8f0',font:{weight:'bold'}},grid:{display:false}}
      }}
  });
}

// 시계
setInterval(()=>{
  const t=new Date().toLocaleTimeString('ko-KR');
  const a=document.getElementById('sb-clock');
  const b=document.getElementById('tb-clock');
  if(a)a.textContent=t;if(b)b.textContent=t;
},1000);

load();
setInterval(load,300_000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8502)
