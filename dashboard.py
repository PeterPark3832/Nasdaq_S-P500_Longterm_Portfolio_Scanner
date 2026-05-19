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
<style>
:root{
  --bg:#0B0E17; --s1:#131820; --s2:#1B2236; --bd:#1E2840;
  --tx:#e2e8f0; --mu:#64748b;
  --pr:#00C6A9; --gn:#22c55e; --rd:#ef4444;
  --bl:#6366f1; --gd:#f59e0b; --or:#f97316;
}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:16px;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--tx);font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
  min-height:100vh;overflow-x:hidden}

/* ── TOP NAV ── */
.topnav{position:fixed;top:0;left:0;right:0;height:58px;
  background:var(--s1);border-bottom:1px solid var(--bd);
  display:flex;align-items:center;padding:0 24px;gap:12px;z-index:200}
.logo{display:flex;align-items:center;gap:8px;margin-right:auto}
.dot{width:8px;height:8px;border-radius:50%;background:var(--gn);
  box-shadow:0 0 8px var(--gn);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.logo-txt{font-size:15px;font-weight:700}
.logo-sub{font-size:12px;color:var(--mu);font-weight:400}
.tabs{display:flex;gap:4px}
.tab{padding:7px 18px;border-radius:8px;border:none;cursor:pointer;
  background:transparent;color:var(--mu);font-size:14px;font-weight:500;
  transition:all .15s;white-space:nowrap}
.tab.on{background:var(--pr);color:#fff}
.tab:hover:not(.on){background:var(--s2);color:var(--tx)}
.clock{font-size:12px;color:var(--mu);white-space:nowrap}

/* ── MOBILE NAV ── */
.mnav{display:none;position:fixed;bottom:0;left:0;right:0;height:62px;
  background:var(--s1);border-top:1px solid var(--bd);z-index:200}
.mnavitems{display:flex;height:100%}
.mnavitem{flex:1;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:3px;border:none;background:transparent;
  color:var(--mu);font-size:10px;cursor:pointer;transition:color .15s}
.mnavitem.on{color:var(--pr)}
.mnavitem .ic{font-size:20px;line-height:1}

/* ── MAIN ── */
.main{padding:74px 24px 48px;max-width:1480px;margin:0 auto}
.sec{display:none}.sec.on{display:block}

/* ── CARDS ── */
.card{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:20px}
.ctitle{font-size:11px;font-weight:700;color:var(--mu);text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:14px}

/* ── KPI GRID ── */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}
.kpi{background:var(--s1);border:1px solid var(--bd);border-radius:12px;padding:18px 20px}
.klabel{font-size:11px;color:var(--mu);margin-bottom:6px}
.kval{font-size:28px;font-weight:800;line-height:1;letter-spacing:-.02em}
.ksub{font-size:11px;color:var(--mu);margin-top:5px}
.pos{color:var(--gn)}.neg{color:var(--rd)}.neu{color:var(--pr)}

/* ── CHART CARD ── */
.cc{background:var(--s1);border:1px solid var(--bd);border-radius:12px;
  padding:20px;margin-bottom:16px}

/* ── GRID ── */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}

/* ── TABLE ── */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:9px 12px;background:var(--s2);color:var(--mu);
  font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
th:first-child{border-radius:6px 0 0 6px}
th:last-child{border-radius:0 6px 6px 0}
td{padding:10px 12px;border-bottom:1px solid var(--bd);white-space:nowrap}
tr:hover td{background:rgba(255,255,255,.025)}
tr:last-child td{border-bottom:none}

/* ── WEIGHT BAR ── */
.wb{display:flex;align-items:center;gap:8px;min-width:110px}
.wbg{flex:1;height:5px;border-radius:3px;background:var(--bd);overflow:hidden}
.wbf{height:5px;border-radius:3px;background:var(--pr)}
.wpct{font-size:12px;font-weight:700;min-width:38px;text-align:right}

/* ── BADGE ── */
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600}
.bg{background:rgba(34,197,94,.12);color:var(--gn)}
.br{background:rgba(239,68,68,.12);color:var(--rd)}
.bb{background:rgba(99,102,241,.12);color:var(--bl)}
.bo{background:rgba(245,158,11,.12);color:var(--gd)}
.bt{background:rgba(0,198,169,.12);color:var(--pr)}

/* ── SECTOR LIST ── */
.slist{list-style:none}
.si{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--bd)}
.si:last-child{border-bottom:none}
.sdot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.sname{flex:1;font-size:13px}
.spct{font-size:13px;font-weight:700;color:var(--pr)}

/* ── GAUGE SVG ── */
.gauge-wrap{display:flex;flex-direction:column;align-items:center;padding:10px 0}
.gval{font-size:36px;font-weight:800;margin:8px 0 4px;line-height:1}
.glabel{font-size:12px;color:var(--mu)}

/* ── REGIME CARD ── */
.regime{padding:16px;border-radius:10px;text-align:center;margin-bottom:14px}
.r-normal{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2)}
.r-caution{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.2)}
.r-fear{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2)}
.rlabel{font-size:24px;font-weight:800}
.rsub{font-size:12px;color:var(--mu);margin-top:4px}

/* ── ALERT ── */
.al{padding:12px 16px;border-radius:8px;margin-bottom:8px;font-size:13px}
.al-ok{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:var(--gn)}
.al-err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);color:var(--rd)}
.al-warn{background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.2);color:var(--gd)}

/* ── HEADER ── */
.hrow{display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:20px;flex-wrap:wrap;gap:8px}
.htitle{font-size:22px;font-weight:800}
.hsub{font-size:13px;color:var(--mu);margin-top:4px}

/* ── LOADING ── */
.spin{width:36px;height:36px;border:3px solid var(--bd);border-top-color:var(--pr);
  border-radius:50%;animation:spin .8s linear infinite;margin:60px auto 12px}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── RESPONSIVE ── */
@media(max-width:768px){
  .tabs,.clock{display:none}
  .mnav{display:block}
  .main{padding:70px 14px 74px}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .kpis .kpi:nth-child(5){grid-column:1/-1}
  .kval{font-size:22px}
  .g2,.g3{grid-template-columns:1fr}
  th,td{padding:8px 10px}
  table{font-size:12px}
}
@media(max-width:420px){
  .kpis{grid-template-columns:1fr 1fr}
  .logo-sub{display:none}
}
</style>
</head>
<body>

<nav class="topnav">
  <div class="logo">
    <div class="dot"></div>
    <span class="logo-txt">US Portfolio</span>
    <span class="logo-sub" id="nav-month"></span>
  </div>
  <div class="tabs">
    <button class="tab on"  onclick="go('home')">홈</button>
    <button class="tab"     onclick="go('port')">포트폴리오</button>
    <button class="tab"     onclick="go('perf')">성과</button>
    <button class="tab"     onclick="go('risk')">리스크</button>
  </div>
  <span class="clock" id="clock"></span>
</nav>

<div class="main">

  <!-- ═══ HOME ═══ -->
  <div class="sec on" id="s-home">
    <div class="hrow">
      <div><div class="htitle">US Long-Term Portfolio</div>
           <div class="hsub" id="home-sub">로딩 중…</div></div>
      <div style="font-size:12px;color:var(--mu)" id="home-upd"></div>
    </div>
    <div class="kpis" id="kpis"></div>
    <div class="cc">
      <div class="ctitle">성과 추이 — 포트폴리오 vs SPY vs QQQ</div>
      <canvas id="ch-home" height="200"></canvas>
    </div>
    <div class="card">
      <div class="ctitle">보유 종목</div>
      <div class="tw" id="home-tbl"></div>
    </div>
  </div>

  <!-- ═══ PORTFOLIO ═══ -->
  <div class="sec" id="s-port">
    <div class="hrow"><div class="htitle">포트폴리오 현황</div></div>
    <div class="g2">
      <div class="card">
        <div class="ctitle">섹터 배분</div>
        <canvas id="ch-sector" height="270"></canvas>
      </div>
      <div class="card">
        <div class="ctitle">섹터 목록</div>
        <ul class="slist" id="slist"></ul>
      </div>
    </div>
    <div class="card">
      <div class="ctitle">보유 종목 상세</div>
      <div class="tw" id="port-tbl"></div>
    </div>
  </div>

  <!-- ═══ PERFORMANCE ═══ -->
  <div class="sec" id="s-perf">
    <div class="hrow"><div class="htitle">성과 분석</div></div>
    <div class="cc">
      <div class="ctitle">누적 수익률 추이</div>
      <canvas id="ch-perf" height="220"></canvas>
    </div>
    <div class="g3" id="perf-kpis"></div>
    <div class="card">
      <div class="ctitle">성과 이력</div>
      <div class="tw" id="perf-tbl"></div>
    </div>
  </div>

  <!-- ═══ RISK ═══ -->
  <div class="sec" id="s-risk">
    <div class="hrow"><div class="htitle">리스크 모니터링</div></div>
    <div class="g2" style="margin-bottom:16px">
      <div class="card" style="text-align:center">
        <div class="ctitle">MDD 모니터</div>
        <div id="mdd-gauge"></div>
      </div>
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
    </div>
    <div class="card" style="margin-bottom:16px">
      <div class="ctitle">스톱로스 현황</div>
      <div id="sl-alerts"></div>
      <div class="tw" id="sl-tbl"></div>
    </div>
    <div class="card">
      <div class="ctitle">종목별 스코어 분석</div>
      <canvas id="ch-score" height="220"></canvas>
    </div>
  </div>

</div><!-- /main -->

<nav class="mnav">
  <div class="mnavitems">
    <button class="mnavitem on" onclick="go('home')"><span class="ic">🏠</span><span>홈</span></button>
    <button class="mnavitem"    onclick="go('port')"><span class="ic">📊</span><span>포트폴리오</span></button>
    <button class="mnavitem"    onclick="go('perf')"><span class="ic">📈</span><span>성과</span></button>
    <button class="mnavitem"    onclick="go('risk')"><span class="ic">⚠️</span><span>리스크</span></button>
  </div>
</nav>

<script>
const TK = '__TOKEN__';
const SCOL = {
  'Technology':'#6366f1','Communication Services':'#00C6A9',
  'Energy':'#f59e0b','Basic Materials':'#f97316',
  'Healthcare':'#22c55e','Consumer Discretionary':'#ec4899',
  'Financials':'#3b82f6','Industrials':'#8b5cf6',
  'Cash':'#374151','Unknown':'#94a3b8'
};
let D=null, CHS={};

const fp=(v,s=true)=>v==null||isNaN(v)?'—':(s&&v>0?'+':'')+v.toFixed(2)+'%';
const fm=v=>v==null?'—':'$'+v.toFixed(2);
const fc=v=>v>0?'pos':v<0?'neg':'';
const chartOpts=(extra={})=>Object.assign({
  responsive:true,
  plugins:{legend:{labels:{color:'#94a3b8',font:{size:12}}},
           tooltip:{mode:'index',intersect:false}},
  scales:{
    x:{ticks:{color:'#64748b'},grid:{color:'#1E2840'}},
    y:{ticks:{color:'#64748b'},grid:{color:'#1E2840'}}
  }
},extra);

function go(name){
  document.querySelectorAll('.sec').forEach(e=>e.classList.remove('on'));
  document.querySelectorAll('.tab,.mnavitem').forEach(e=>e.classList.remove('on'));
  document.getElementById('s-'+name).classList.add('on');
  document.querySelectorAll('[onclick="go(\''+name+'\')"]').forEach(e=>e.classList.add('on'));
  if(name==='port'  && !CHS.sector) renderSector();
  if(name==='perf'  && !CHS.perf)   renderPerfChart('ch-perf','perf');
  if(name==='risk'  && !CHS.score)  renderScore();
}

async function load(){
  try{
    const r=await fetch('/api/data?token='+TK);
    if(!r.ok)throw new Error();
    D=await r.json(); render();
  }catch{
    document.querySelector('.main').innerHTML=
      '<div style="text-align:center;padding:80px;color:#ef4444">데이터 로드 실패</div>';
  }
}

function render(){
  if(!D)return;
  const {portfolio:p,performance:pf,updated}=D;
  const holdings=p.holdings||[];
  const stocks=holdings.filter(h=>h.ticker!=='CASH');
  const cash=holdings.find(h=>h.ticker==='CASH');
  const cw=cash?cash.weight:30;
  const recs=(pf.records||[]);
  const checks=recs.filter(r=>r.type==='performance_check'&&r.portfolio_ret_pct!=null);
  const lat=checks.slice(-1)[0];

  const pr=lat?lat.portfolio_ret_pct:0;
  const sr=lat?lat.spy_ret_pct:null;
  const qr=lat?lat.qqq_ret_pct:null;
  const al=lat?lat.alpha_vs_spy:null;

  document.getElementById('nav-month').textContent=p.month?'  '+p.month:'';
  document.getElementById('home-sub').textContent=
    `리밸런싱 월: ${p.month||'—'} | ${stocks.length}종목 + 현금 ${cw}%`;
  document.getElementById('home-upd').textContent='갱신: '+updated;

  // KPIs
  const ks=[
    {l:'포트폴리오 수익률',v:fp(pr),c:fc(pr),s:'최근 성과 체크 기준'},
    {l:'Alpha vs SPY',   v:al!=null?fp(al)+'p':'—',c:fc(al),s:'SPY '+fp(sr)},
    {l:'Alpha vs QQQ',   v:qr!=null?fp(pr-qr)+'p':'—',c:fc(qr!=null?pr-qr:0),s:'QQQ '+fp(qr)},
    {l:'보유 종목',       v:stocks.length+'종목',c:'neu',s:new Set(stocks.map(h=>h.sector)).size+'개 섹터'},
    {l:'현금 비중',       v:cw+'%',c:cw>30?'neg':'neu',s:cw>30?'VIX 방어 중':'기본 비중'},
  ];
  document.getElementById('kpis').innerHTML=ks.map(k=>
    `<div class="kpi"><div class="klabel">${k.l}</div>
     <div class="kval ${k.c}">${k.v}</div>
     <div class="ksub">${k.s}</div></div>`
  ).join('');

  renderTable('home-tbl', holdings, false);
  renderTable('port-tbl', holdings, true);
  renderSectorList(holdings);
  renderPerfKPIs(checks);
  renderPerfHistTable(recs);
  renderRisk(p,holdings,cw);
  renderPerfChart('ch-home','home');
}

/* ── LINE CHART ── */
function renderPerfChart(canvasId,key){
  if(!D)return;
  const ctx=document.getElementById(canvasId);
  if(!ctx)return;
  const recs=(D.performance.records||[]).filter(r=>r.type!=='rebalancing'&&r.portfolio_ret_pct!=null);
  const labels=recs.map(r=>r.date);
  if(CHS[key])CHS[key].destroy();
  CHS[key]=new Chart(ctx,{
    type:'line',
    data:{labels,datasets:[
      {label:'포트폴리오',data:recs.map(r=>r.portfolio_ret_pct),
       borderColor:'#00C6A9',backgroundColor:'rgba(0,198,169,.1)',
       borderWidth:2.5,pointRadius:6,fill:true,tension:.3},
      {label:'SPY',data:recs.map(r=>r.spy_ret_pct),
       borderColor:'#6366f1',backgroundColor:'transparent',
       borderWidth:2,borderDash:[6,3],pointRadius:4,tension:.3},
      {label:'QQQ',data:recs.map(r=>r.qqq_ret_pct),
       borderColor:'#f59e0b',backgroundColor:'transparent',
       borderWidth:2,borderDash:[3,3],pointRadius:4,tension:.3},
    ]},
    options:{...chartOpts(),scales:{
      x:{ticks:{color:'#64748b'},grid:{color:'#1E2840'}},
      y:{ticks:{color:'#64748b',callback:v=>v+'%'},grid:{color:'#1E2840'}}
    }}
  });
}

/* ── SECTOR DONUT ── */
function renderSector(){
  if(!D)return;
  const ctx=document.getElementById('ch-sector');
  const wts={};
  (D.portfolio.holdings||[]).forEach(h=>{
    const s=h.sector||'Unknown';
    wts[s]=(wts[s]||0)+h.weight;
  });
  const ent=Object.entries(wts).sort((a,b)=>b[1]-a[1]);
  if(CHS.sector)CHS.sector.destroy();
  CHS.sector=new Chart(ctx,{
    type:'doughnut',
    data:{
      labels:ent.map(([s])=>s),
      datasets:[{data:ent.map(([,w])=>w),
        backgroundColor:ent.map(([s])=>SCOL[s]||'#94a3b8'),
        borderColor:'#0B0E17',borderWidth:2,hoverOffset:10}]
    },
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
    `<li class="si">
       <div class="sdot" style="background:${SCOL[s]||'#94a3b8'}"></div>
       <span class="sname">${s}</span>
       <span class="spct">${w.toFixed(1)}%</span>
     </li>`
  ).join('');
}

/* ── HOLDINGS TABLE ── */
function renderTable(id,holdings,detail){
  const el=document.getElementById(id);
  if(!el)return;
  const hdr=detail
    ?'<tr><th></th><th>티커</th><th>종목명</th><th>섹터</th><th>비중</th><th>스코어</th><th>진입가</th><th>ROE%</th><th>마진%</th><th>6M수익</th><th>52W위치</th></tr>'
    :'<tr><th>티커</th><th>종목명</th><th>비중</th><th>스코어</th><th>진입가</th></tr>';
  const rows=holdings.map(h=>{
    const wbar=`<div class="wb"><div class="wbg"><div class="wbf" style="width:${Math.min(h.weight/15*100,100)}%"></div></div><span class="wpct">${h.weight.toFixed(1)}%</span></div>`;
    const stcl=h.score>=80?'pos':h.score>=60?'':'neg';
    if(detail)return `<tr>
      <td>${h.data_stale?'⚠️':'✅'}</td>
      <td><b style="color:var(--pr)">${h.ticker}</b></td>
      <td style="max-width:130px;overflow:hidden;text-overflow:ellipsis;color:var(--mu)">${h.name}</td>
      <td><span class="badge bb">${h.sector||'—'}</span></td>
      <td>${wbar}</td>
      <td>${h.score?`<span class="${stcl}">${h.score.toFixed(1)}</span>`:'—'}</td>
      <td style="color:var(--mu)">${fm(h.entry_price)}</td>
      <td class="${fc(h.roe)}">${h.roe?h.roe.toFixed(1)+'%':'—'}</td>
      <td>${h.margin?h.margin.toFixed(1)+'%':'—'}</td>
      <td class="${fc(h.ret_6m)}">${h.ret_6m?fp(h.ret_6m):'—'}</td>
      <td>${h.w52_pos?h.w52_pos.toFixed(1)+'%':'—'}</td>
    </tr>`;
    return `<tr>
      <td><b style="color:var(--pr)">${h.ticker}</b></td>
      <td style="color:var(--mu)">${h.name}</td>
      <td>${wbar}</td>
      <td>${h.score?`<span class="${stcl}">${h.score.toFixed(1)}</span>`:'—'}</td>
      <td style="color:var(--mu)">${fm(h.entry_price)}</td>
    </tr>`;
  }).join('');
  el.innerHTML=`<table><thead>${hdr}</thead><tbody>${rows}</tbody></table>`;
}

/* ── PERF KPIs ── */
function renderPerfKPIs(checks){
  const el=document.getElementById('perf-kpis');
  if(!el)return;
  const lat=checks.slice(-1)[0];
  const alphas=checks.filter(r=>r.alpha_vs_spy!=null).map(r=>r.alpha_vs_spy);
  const avgA=alphas.length?alphas.reduce((a,b)=>a+b,0)/alphas.length:null;
  const ks=[
    {l:'최근 수익률',  v:fp(lat?.portfolio_ret_pct), c:fc(lat?.portfolio_ret_pct||0)},
    {l:'최근 Alpha vs SPY',v:lat?.alpha_vs_spy!=null?fp(lat.alpha_vs_spy)+'p':'—',c:fc(lat?.alpha_vs_spy||0)},
    {l:'평균 Alpha',   v:avgA!=null?fp(avgA)+'p':'—',c:fc(avgA||0)},
  ];
  el.innerHTML=ks.map(k=>
    `<div class="card"><div class="ctitle">${k.l}</div>
     <div class="kval ${k.c}" style="font-size:30px">${k.v}</div></div>`
  ).join('');
}

/* ── PERF HISTORY TABLE ── */
function renderPerfHistTable(recs){
  const el=document.getElementById('perf-tbl');
  if(!el)return;
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
  const me=p.max_equity||0;
  const MDD=-15;

  // Gauge SVG
  const pct=Math.min(Math.max((me+30)/60,0),1);
  const angle=pct*180;
  const col=me>=0?'#22c55e':me>-10?'#f59e0b':me>MDD?'#f97316':'#ef4444';
  const rad=(angle-180)*Math.PI/180;
  const ex=100+80*Math.cos(rad), ey=100+80*Math.sin(rad);
  const la=angle>180?1:0;
  document.getElementById('mdd-gauge').innerHTML=`
    <div class="gauge-wrap">
      <svg viewBox="0 0 200 110" style="width:220px;transform:none">
        <path d="M20,100 A80,80 0 0,1 180,100" fill="none" stroke="#1E2840" stroke-width="14" stroke-linecap="round"/>
        <path d="M20,100 A80,80 0 0,1 60,27"   fill="none" stroke="#ef4444" stroke-width="14" opacity=".3" stroke-linecap="butt"/>
        <path d="M60,27  A80,80 0 0,1 100,20"  fill="none" stroke="#f97316" stroke-width="14" opacity=".3" stroke-linecap="butt"/>
        <path d="M100,20 A80,80 0 0,1 180,100" fill="none" stroke="#22c55e" stroke-width="14" opacity=".3" stroke-linecap="round"/>
        ${angle>0?`<path d="M20,100 A80,80 0 ${la},1 ${ex.toFixed(1)},${ey.toFixed(1)}" fill="none" stroke="${col}" stroke-width="14" stroke-linecap="round"/>`:''}
        <circle cx="${ex.toFixed(1)}" cy="${ey.toFixed(1)}" r="7" fill="${col}"/>
      </svg>
      <div class="gval" style="color:${col}">${fp(me)}</div>
      <div class="glabel">MDD 기준 수익률 | 경보: ${MDD}%</div>
    </div>`;

  // VIX
  const [rcl,rl,re]=cw>=50?['r-fear','공포','🔴']:cw>=40?['r-caution','주의','🟡']:['r-normal','정상','🟢'];
  document.getElementById('vix-regime').innerHTML=
    `<div class="regime ${rcl}"><div class="rlabel">${re} ${rl}</div>
     <div class="rsub">현금 비중: ${cw}%</div></div>`;

  // Stoploss
  const alerted=p.last_stoploss_alerts||{};
  const aKeys=Object.keys(alerted);
  document.getElementById('sl-alerts').innerHTML=aKeys.length
    ?aKeys.map(t=>`<div class="al al-err">🔴 <b>${t}</b> — 알림 발생: ${alerted[t]}</div>`).join('')
    :'<div class="al al-ok">✅ 이번 달 스톱로스 알림 없음</div>';

  const SL=-15,WN=-10;
  const stocks=holdings.filter(h=>h.ticker!=='CASH');
  document.getElementById('sl-tbl').innerHTML=`<table><thead><tr>
    <th></th><th>티커</th><th>종목명</th><th>진입가</th><th>경고(${WN}%)</th><th>스톱로스(${SL}%)</th><th>진입일</th>
  </tr></thead><tbody>${stocks.map(h=>{
    const ep=h.entry_price||0;
    return`<tr>
      <td>${h.ticker in alerted?'🔴':'✅'}</td>
      <td><b style="color:var(--pr)">${h.ticker}</b></td>
      <td style="color:var(--mu)">${h.name}</td>
      <td>${fm(ep)}</td>
      <td style="color:var(--gd)">${fm(ep*(1+WN/100))}</td>
      <td style="color:var(--rd)">${fm(ep*(1+SL/100))}</td>
      <td style="color:var(--mu)">${h.entry_date||'—'}</td>
    </tr>`;
  }).join('')}</tbody></table>`;
}

/* ── SCORE BAR CHART ── */
function renderScore(){
  if(!D)return;
  const ctx=document.getElementById('ch-score');
  if(!ctx)return;
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
  CHS.score=new Chart(ctx,{
    type:'bar',
    data:{labels:stocks.map(h=>h.ticker),datasets:[
      {label:'재무품질(40pt)',data:fin,backgroundColor:'#6366f1'},
      {label:'기술적(20pt)', data:tec,backgroundColor:'#22c55e'},
      {label:'모멘텀(40pt)', data:mom,backgroundColor:'#f59e0b'},
    ]},
    options:{indexAxis:'y',responsive:true,
      plugins:{legend:{labels:{color:'#94a3b8'}}},
      scales:{
        x:{stacked:true,max:105,ticks:{color:'#64748b'},grid:{color:'#1E2840'}},
        y:{stacked:true,ticks:{color:'#e2e8f0',font:{weight:'bold'}},grid:{display:false}}
      }}
  });
}

// clock
setInterval(()=>{
  const el=document.getElementById('clock');
  if(el)el.textContent=new Date().toLocaleTimeString('ko-KR');
},1000);

// init & auto-refresh
load();
setInterval(load,300_000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8502)
