"""
US Long-Term Portfolio Scanner — 대시보드
접속: http://<server-ip>:8502/?token=scanner2024
"""
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_data import (
    COLORS, DRIFT_THRESHOLD, MDD_THRESHOLD, PLOTLY_TEMPLATE,
    STOPLOSS_THRESHOLD, STOPLOSS_WARN_LEVEL, VIX_CAUTION, VIX_FEAR,
    compute_rebalancing_changes, compute_score_breakdown,
    get_latest_perf, infer_vix_regime, load_last_rebal,
    load_performance_history, load_portfolio, load_prev_portfolio,
    sector_counts,
)

# ── 페이지 설정 ───────────────────────────────────────────────────
st.set_page_config(
    page_title="US Portfolio Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 인증 ─────────────────────────────────────────────────────────
_TOKEN = os.getenv("DASHBOARD_TOKEN", "scanner2024")
_params = st.query_params
if _params.get("token") != _TOKEN:
    st.markdown("## 🔒 접근 제한")
    st.error("올바른 토큰이 URL에 없습니다.  \n예: `http://server:8502/?token=scanner2024`")
    st.stop()

# ── 커스텀 CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #0E1117; }
[data-testid="metric-container"] {
    background: #1C2333; border-radius: 8px; padding: 12px 16px;
}
.status-new      { color: #00C853; font-weight: 700; }
.status-exit     { color: #EF5350; font-weight: 700; }
.status-up       { color: #42A5F5; font-weight: 700; }
.status-down     { color: #FFA726; font-weight: 700; }
.status-ok       { color: #78909C; }
.section-title   { font-size: 1.15rem; font-weight: 700; margin-top: 8px; }
</style>
""", unsafe_allow_html=True)

# ── 자동 갱신 (5분) ───────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=300_000, key="auto_refresh")
except ImportError:
    pass  # streamlit-autorefresh 미설치 시 수동 갱신으로 동작

# ── 데이터 로드 ───────────────────────────────────────────────────
portfolio = load_portfolio()
prev_port = load_prev_portfolio()
history   = load_performance_history()
last_rebal = load_last_rebal()

if portfolio is None:
    st.warning("포트폴리오 데이터가 없습니다. 봇이 아직 리밸런싱을 실행하지 않았습니다.")
    st.stop()

holdings      = portfolio.get("holdings", [])
stock_holdings = [h for h in holdings if h["ticker"] != "CASH"]
cash_h        = next((h for h in holdings if h["ticker"] == "CASH"), None)
cash_weight   = cash_h["weight"] if cash_h else 30.0
port_month    = portfolio.get("month", "—")
latest_perf   = get_latest_perf(history)
vix_label, vix_emoji, _ = infer_vix_regime(cash_weight)

# ═══════════════════════════════════════════════════════════════════
# 헤더: 핵심 지표
# ═══════════════════════════════════════════════════════════════════
st.markdown("## 📊 US Long-Term Portfolio Dashboard")
st.caption(f"리밸런싱 월: **{port_month}** | 데이터 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 자동 갱신 5분")

col1, col2, col3, col4, col5 = st.columns(5)

_ret    = latest_perf["portfolio_ret_pct"] if latest_perf else 0.0
_spy    = latest_perf.get("spy_ret_pct") if latest_perf else None
_qqq    = latest_perf.get("qqq_ret_pct") if latest_perf else None
_alpha  = latest_perf.get("alpha_vs_spy") if latest_perf else None

col1.metric("포트폴리오 수익률", f"{_ret:+.2f}%", delta=None)
col2.metric("SPY 대비 알파",
            f"{_alpha:+.2f}%p" if _alpha is not None else "—",
            delta=f"SPY {_spy:+.2f}%" if _spy is not None else None)
col3.metric("QQQ 대비",
            f"{(_ret - _qqq):+.2f}%p" if _qqq is not None else "—",
            delta=f"QQQ {_qqq:+.2f}%" if _qqq is not None else None)
col4.metric("현금 비중", f"{cash_weight:.0f}%",
            delta=f"{'기본 30%' if cash_weight == 30 else f'+{cash_weight-30:.0f}%p 추가'}")
col5.metric(f"VIX 레짐 {vix_emoji}", vix_label,
            delta=f"VIX {'<30 정상' if cash_weight == 30 else '≥30 주의' if cash_weight < 60 else '≥40 공포'}")

st.divider()

# ═══════════════════════════════════════════════════════════════════
# 4탭 구조
# ═══════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 포트폴리오 현황", "🔄 리밸런싱 변동", "📈 성과 분석", "⚠️ 리스크 모니터링"]
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1: 포트폴리오 현황
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab1:
    col_chart, col_table = st.columns([1, 2])

    # 섹터 도넛 차트
    with col_chart:
        st.markdown('<p class="section-title">섹터 배분</p>', unsafe_allow_html=True)
        sec_weights: dict[str, float] = {}
        for h in holdings:
            sec = h.get("sector", "Unknown")
            sec_weights[sec] = sec_weights.get(sec, 0) + h["weight"]

        sc = sector_counts(holdings)
        pull = [0.12 if sc.get(s, 0) >= 3 else 0 for s in sec_weights]

        fig_pie = go.Figure(go.Pie(
            labels=list(sec_weights.keys()),
            values=list(sec_weights.values()),
            hole=0.42,
            pull=pull,
            marker=dict(line=dict(color="#0E1117", width=2)),
            hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
            textinfo="label+percent",
        ))
        fig_pie.update_layout(
            template=PLOTLY_TEMPLATE,
            height=350,
            margin=dict(t=20, b=10, l=10, r=10),
            showlegend=False,
            annotations=[dict(text="섹터", x=0.5, y=0.5, font_size=13, showarrow=False)],
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        capped = [s for s, c in sc.items() if c >= 3]
        if capped:
            st.caption(f"섹터 상한(3종목) 도달: {', '.join(capped)}")

    # 보유 종목 테이블
    with col_table:
        st.markdown('<p class="section-title">보유 종목 상세</p>', unsafe_allow_html=True)
        alerted_sl = portfolio.get("last_stoploss_alerts", {})

        rows = []
        for h in holdings:
            if h["ticker"] == "CASH":
                rows.append({
                    "경보": "💵", "티커": "CASH", "종목명": h["name"][:22],
                    "섹터": "—", "비중%": h["weight"],
                    "진입가": "—", "스코어": "—",
                    "ROE%": "—", "마진%": "—", "PEG": "—",
                    "6M수익%": "—", "52W위치%": "—",
                    "재무일자": "—", "데이터": "✅",
                })
                continue

            sl_icon = ""
            if h["ticker"] in alerted_sl:
                sl_icon = "🔴"
            elif h.get("data_stale"):
                sl_icon = "⚠️"

            rows.append({
                "경보":    sl_icon or "✅",
                "티커":    h["ticker"],
                "종목명":  h["name"][:22],
                "섹터":    h.get("sector", "—"),
                "비중%":   h["weight"],
                "진입가":  h["entry_price"],
                "스코어":  h["score"],
                "ROE%":    h.get("roe", 0),
                "마진%":   h.get("margin", 0),
                "PEG":     h.get("peg", 0),
                "6M수익%": h.get("ret_6m", 0),
                "52W위치%":h.get("w52_pos", 0),
                "재무일자": h.get("fin_report_dt", "—"),
                "데이터":  "⚠️ 오래됨" if h.get("data_stale") else "✅",
            })

        df_hold = pd.DataFrame(rows)
        st.dataframe(
            df_hold,
            column_config={
                "비중%": st.column_config.ProgressColumn(
                    "비중%", min_value=0, max_value=100, format="%.1f%%"
                ),
                "스코어": st.column_config.ProgressColumn(
                    "스코어/100", min_value=0, max_value=100, format="%.1f"
                ),
                "진입가": st.column_config.NumberColumn("진입가 $", format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True,
            height=380,
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2: 리밸런싱 변동 (핵심)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab2:
    prev_month = prev_port.get("month", "이전") if prev_port else None

    if prev_port is None:
        st.info(
            "이전 달 포트폴리오 데이터(`portfolio_prev_us.json`)가 없습니다.  \n"
            "다음 리밸런싱 실행 후 자동으로 비교 데이터가 생성됩니다."
        )
    else:
        diff = compute_rebalancing_changes(portfolio, prev_port)

        st.markdown(
            f'<p class="section-title">리밸런싱 변동: {prev_month} → {port_month}</p>',
            unsafe_allow_html=True,
        )

        # 요약 카드
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 신규 편입", f"{len(diff['new'])}종목")
        c2.metric("🔴 제외",      f"{len(diff['exited'])}종목")
        c3.metric("🔼 비중 증가", f"{len(diff['increased'])}종목")
        c4.metric("🔽 비중 감소", f"{len(diff['decreased'])}종목")

        st.markdown("---")

        # Before/After 비중 비교 바 차트
        curr_map = {h["ticker"]: h["weight"] for h in holdings if h["ticker"] != "CASH"}
        prev_map = {h["ticker"]: h["weight"]
                    for h in prev_port.get("holdings", []) if h["ticker"] != "CASH"}

        all_tickers_sorted = sorted(
            set(curr_map) | set(prev_map),
            key=lambda t: -curr_map.get(t, 0),
        )

        bar_labels, bar_prev, bar_curr, bar_colors, bar_texts = [], [], [], [], []
        for t in all_tickers_sorted:
            pw = prev_map.get(t, 0)
            cw = curr_map.get(t, 0)
            d  = cw - pw
            if pw == 0:
                color = COLORS["new"]
            elif cw == 0:
                color = COLORS["exited"]
            elif d > 0.5:
                color = COLORS["increased"]
            elif d < -0.5:
                color = COLORS["decreased"]
            else:
                color = COLORS["unchanged"]

            bar_labels.append(t)
            bar_prev.append(pw)
            bar_curr.append(cw)
            bar_colors.append(color)
            suffix = " 🟢NEW" if pw == 0 else " 🔴EXIT" if cw == 0 else \
                     f" ▲+{d:.1f}%p" if d > 0.5 else f" ▼{d:.1f}%p" if d < -0.5 else ""
            bar_texts.append(f"{cw:.1f}%{suffix}")

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="이전 달",
            y=bar_labels, x=bar_prev,
            orientation="h",
            marker=dict(color="rgba(120,120,120,0.35)",
                        line=dict(color="rgba(180,180,180,0.5)", width=1)),
            hovertemplate="%{y} 이전: %{x:.1f}%<extra></extra>",
        ))
        fig_bar.add_trace(go.Bar(
            name="현재",
            y=bar_labels, x=bar_curr,
            orientation="h",
            marker=dict(color=bar_colors),
            text=bar_texts,
            textposition="outside",
            hovertemplate="%{y} 현재: %{x:.1f}%<extra></extra>",
        ))
        fig_bar.update_layout(
            barmode="overlay",
            template=PLOTLY_TEMPLATE,
            title="포트폴리오 비중 Before / After",
            xaxis=dict(title="비중 %", range=[0, max(bar_curr + bar_prev or [35]) * 1.35]),
            height=max(380, len(bar_labels) * 46),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=70, r=20, t=60, b=30),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # 변동 상세 테이블
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("**변동 종목 상세**")
            change_rows = []
            _STATUS_ICON = {"NEW": "🟢 신규", "EXIT": "🔴 제외",
                            "INCREASE": "🔼 증가", "DECREASE": "🔽 감소", "UNCHANGED": "⚪ 유지"}

            for status_key, items in [
                ("NEW", diff["new"]), ("EXIT", diff["exited"]),
                ("INCREASE", diff["increased"]), ("DECREASE", diff["decreased"]),
            ]:
                for h in items:
                    pw = h.get("prev_weight", 0)
                    cw = h.get("weight", 0)
                    change_rows.append({
                        "구분": _STATUS_ICON[status_key],
                        "티커": h["ticker"],
                        "종목명": h.get("name", "")[:20],
                        "이전 비중": f"{pw:.1f}%" if pw else "—",
                        "현재 비중": f"{cw:.1f}%" if cw else "—",
                        "변화": f"{cw - pw:+.1f}%p",
                        "스코어": f"{h.get('score', 0):.1f}" if h.get('score') else "—",
                    })

            if change_rows:
                st.dataframe(pd.DataFrame(change_rows), hide_index=True,
                             use_container_width=True, height=340)
            else:
                st.success("변동 없음 — 포트폴리오가 그대로 유지되었습니다.")

        with col_right:
            st.markdown("**📋 매매 실행 체크리스트**")
            st.caption("이 순서대로 실행: 매도 → 비중 축소 → 비중 확대 → 신규 매수")

            _STEP_LABELS = {
                "sell":     ("1단계 🔴 매도", "전량 매도"),
                "decrease": ("2단계 🔽 비중 축소", "일부 매도"),
                "increase": ("3단계 🔼 비중 확대", "추가 매수"),
                "buy":      ("4단계 🟢 신규 매수", "신규 매수"),
            }
            current_step = None
            for item in diff["trade_order"]:
                action, ticker, pw, cw, dw = item[0], item[1], item[2], item[3], item[4]
                step_label, action_label = _STEP_LABELS[action]
                if action != current_step:
                    st.markdown(f"**{step_label}**")
                    current_step = action

                if action == "sell":
                    desc = f"**{ticker}** 전량 매도 (이전 {pw:.1f}%)"
                elif action == "decrease":
                    desc = f"**{ticker}** {pw:.1f}% → {cw:.1f}% ({dw:+.1f}%p)"
                elif action == "increase":
                    desc = f"**{ticker}** {pw:.1f}% → {cw:.1f}% ({dw:+.1f}%p)"
                else:
                    desc = f"**{ticker}** 신규 매수 → {cw:.1f}%"

                st.checkbox(desc, key=f"chk_{ticker}_{action}", value=False)

        if diff["unchanged"]:
            with st.expander(f"⚪ 유지 종목 ({len(diff['unchanged'])}개)"):
                for h in diff["unchanged"]:
                    st.write(f"- **{h['ticker']}** ({h.get('name','')[:20]}) — {h['weight']:.1f}%")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: 성과 분석
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab3:
    st.markdown('<p class="section-title">누적 수익률 vs 벤치마크</p>', unsafe_allow_html=True)

    if not history:
        st.info("아직 성과 이력이 없습니다. 리밸런싱을 1회 이상 실행하면 표시됩니다.")
    else:
        df_hist = pd.DataFrame(history)
        df_hist["date"] = pd.to_datetime(df_hist["date"])
        df_hist = df_hist.sort_values("date")

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=df_hist["date"], y=df_hist["portfolio_ret_pct"],
            name="포트폴리오", mode="lines+markers",
            line=dict(color=COLORS["portfolio"], width=2.5),
            marker=dict(
                size=9,
                symbol=["diamond" if t == "performance_check" else "circle"
                        for t in df_hist.get("type", ["circle"] * len(df_hist))],
            ),
            hovertemplate="<b>포트폴리오</b>: %{y:+.2f}%<br>%{x|%Y-%m-%d}<extra></extra>",
        ))

        spy_df = df_hist.dropna(subset=["spy_ret_pct"])
        if not spy_df.empty:
            fig_line.add_trace(go.Scatter(
                x=spy_df["date"], y=spy_df["spy_ret_pct"],
                name="SPY", mode="lines+markers",
                line=dict(color=COLORS["spy"], width=1.5, dash="dash"),
                hovertemplate="<b>SPY</b>: %{y:+.2f}%<extra></extra>",
            ))

        qqq_df = df_hist.dropna(subset=["qqq_ret_pct"])
        if not qqq_df.empty:
            fig_line.add_trace(go.Scatter(
                x=qqq_df["date"], y=qqq_df["qqq_ret_pct"],
                name="QQQ", mode="lines+markers",
                line=dict(color=COLORS["qqq"], width=1.5, dash="dot"),
                hovertemplate="<b>QQQ</b>: %{y:+.2f}%<extra></extra>",
            ))

        fig_line.add_hline(y=0, line_color="rgba(200,200,200,0.3)", line_dash="dot")
        fig_line.update_layout(
            template=PLOTLY_TEMPLATE,
            yaxis_title="수익률 %",
            height=400,
            legend=dict(orientation="h"),
            hovermode="x unified",
            margin=dict(t=20, b=30),
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # 알파 요약
        alpha_df = df_hist.dropna(subset=["alpha_vs_spy"])
        if not alpha_df.empty:
            avg_alpha = alpha_df["alpha_vs_spy"].mean()
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("평균 알파 (vs SPY)", f"{avg_alpha:+.2f}%p")
            latest_a = alpha_df.iloc[-1]
            mc2.metric("최근 알파",
                       f"{latest_a['alpha_vs_spy']:+.2f}%p",
                       delta=latest_a["date"].strftime("%Y-%m-%d"))
            positive = (alpha_df["alpha_vs_spy"] > 0).sum()
            mc3.metric("양의 알파 비율", f"{positive}/{len(alpha_df)} 회")

        # 월별 성과 테이블
        st.markdown("---")
        st.markdown("**월별 성과 이력**")
        df_display = df_hist.copy()
        df_display["date"] = df_display["date"].dt.strftime("%Y-%m-%d")
        df_display = df_display.rename(columns={
            "date": "날짜", "type": "타입",
            "portfolio_ret_pct": "포트폴리오%",
            "spy_ret_pct": "SPY%",
            "qqq_ret_pct": "QQQ%",
            "alpha_vs_spy": "알파 vs SPY",
        })
        for c in ["포트폴리오%", "SPY%", "QQQ%", "알파 vs SPY"]:
            if c in df_display.columns:
                df_display[c] = df_display[c].apply(
                    lambda v: f"{v:+.2f}%" if pd.notna(v) else "—"
                )
        st.dataframe(df_display[["날짜","타입","포트폴리오%","SPY%","QQQ%","알파 vs SPY"]],
                     hide_index=True, use_container_width=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4: 리스크 모니터링
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab4:
    r1, r2 = st.columns([1, 2])

    # MDD 게이지
    with r1:
        max_equity = portfolio.get("max_equity", 0.0)
        mdd_pct = max_equity  # 양수 = 고점 대비 상승 여력, 음수 = MDD 진행

        fig_mdd = go.Figure(go.Indicator(
            mode="gauge+number",
            value=max_equity,
            number={"suffix": "%", "valueformat": "+.2f"},
            title={"text": "포트폴리오 수익률 (MDD 기준)"},
            gauge={
                "axis": {"range": [-30, 30]},
                "bar":  {"color": COLORS["portfolio"]},
                "steps": [
                    {"range": [-30, MDD_THRESHOLD], "color": "#B71C1C"},
                    {"range": [MDD_THRESHOLD, -5],  "color": "#E65100"},
                    {"range": [-5, 0],              "color": "#F9A825"},
                    {"range": [0, 30],              "color": "#1B5E20"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": MDD_THRESHOLD,
                },
            },
        ))
        fig_mdd.update_layout(template=PLOTLY_TEMPLATE, height=280,
                              margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig_mdd, use_container_width=True)
        st.caption(f"MDD 경보 임계치: {MDD_THRESHOLD:.0f}%")

    # 스톱로스 + 드리프트 상태
    with r2:
        st.markdown("**스톱로스 알림 현황**")
        alerted = portfolio.get("last_stoploss_alerts", {})
        if alerted:
            for ticker, alert_date in alerted.items():
                st.error(f"🔴 **{ticker}** — 스톱로스 알림 발생: {alert_date}")
        else:
            st.success("이번 달 스톱로스 알림 없음")
        st.caption(f"임계치: {STOPLOSS_THRESHOLD:.0f}% (경고: {STOPLOSS_WARN_LEVEL:.0f}%)")

        st.markdown("---")
        st.markdown("**포지션 드리프트 현황**")
        last_drift = portfolio.get("last_drift_alert_date")
        if last_drift:
            st.warning(f"⚠️ 드리프트 알림 발생 날짜: {last_drift} — 텔레그램 메시지 확인 바람")
        else:
            st.success("이번 달 드리프트 알림 없음")
        st.caption(f"드리프트 임계치: ±{DRIFT_THRESHOLD:.0f}%p")

        # 진입가 기준 보유 종목 테이블
        st.markdown("---")
        st.markdown("**보유 종목 진입가 기준표**")
        sl_rows = []
        for h in stock_holdings:
            ep = h.get("entry_price", 0)
            warn_price = ep * (1 + STOPLOSS_WARN_LEVEL / 100)
            sl_price   = ep * (1 + STOPLOSS_THRESHOLD / 100)
            sl_rows.append({
                "티커":    h["ticker"],
                "진입가":  f"${ep:.2f}",
                f"경고({STOPLOSS_WARN_LEVEL:.0f}%)": f"${warn_price:.2f}",
                f"스톱로스({STOPLOSS_THRESHOLD:.0f}%)": f"${sl_price:.2f}",
                "진입일":  h.get("entry_date", "—"),
                "경보":    "🔴" if h["ticker"] in alerted else "✅",
            })
        st.dataframe(pd.DataFrame(sl_rows), hide_index=True, use_container_width=True)

    st.divider()

    # VIX 레짐 시각화
    rc1, rc2, rc3 = st.columns([1, 1, 1])

    with rc1:
        st.markdown("**VIX 레짐 현황**")
        fig_vix = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cash_weight,
            number={"suffix": "% 현금"},
            title={"text": "현금 비중 (VIX 레짐 반영)"},
            gauge={
                "axis": {"range": [0, 70]},
                "bar":  {"color": COLORS["cash"]},
                "steps": [
                    {"range": [0, 30],  "color": "#1B5E20"},
                    {"range": [30, 50], "color": "#E65100"},
                    {"range": [50, 70], "color": "#B71C1C"},
                ],
            },
        ))
        fig_vix.update_layout(template=PLOTLY_TEMPLATE, height=260,
                              margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig_vix, use_container_width=True)

    with rc2:
        st.markdown("**VIX 레짐 기준표**")
        regime_df = pd.DataFrame([
            {"레짐": "🟢 정상", "VIX": f"< {VIX_CAUTION}", "현금 비중": "30% (기본)"},
            {"레짐": "🟡 주의", "VIX": f"≥ {VIX_CAUTION}", "현금 비중": "+20%p → 50%"},
            {"레짐": "🔴 공포", "VIX": f"≥ {VIX_FEAR}",    "현금 비중": "+30%p → 60%"},
        ])
        st.table(regime_df)
        st.metric("현재 레짐", f"{vix_emoji} {vix_label}", delta=f"현금 {cash_weight:.0f}%")

    with rc3:
        st.markdown("**일정 정보**")
        if port_month and port_month != "—":
            try:
                curr_dt = datetime.strptime(port_month + "-01", "%Y-%m-%d")
                next_rebal = (curr_dt.replace(day=1) + timedelta(days=32)).replace(day=1)
                days_left = (next_rebal - datetime.now()).days
                st.metric("현재 포트폴리오 월", port_month)
                st.metric("다음 리밸런싱 예상", next_rebal.strftime("%Y-%m"),
                          delta=f"약 {days_left}일 후")
            except ValueError:
                st.metric("현재 포트폴리오 월", port_month)
        st.metric("마지막 리밸런싱", last_rebal or "—")

    st.divider()

    # 스코어 브레이크다운 (Tab4 하단)
    st.markdown('<p class="section-title">종목별 스코어 구성</p>', unsafe_allow_html=True)
    st.caption("재무품질(40pt) + 기술적(20pt) + 모멘텀(40pt, 추정)")

    bd_tickers, bd_fin, bd_tech, bd_mom = [], [], [], []
    bd_rows = []
    for h in sorted(stock_holdings, key=lambda x: -x.get("score", 0)):
        bd = compute_score_breakdown(h)
        bd_tickers.append(h["ticker"])
        bd_fin.append(bd["financial"])
        bd_tech.append(bd["technical"])
        bd_mom.append(bd["momentum"])
        bd_rows.append({
            "티커":     h["ticker"],
            "합계":     f"{bd['total']:.1f}",
            "재무(40)": f"{bd['financial']:.1f}",
            "기술(20)": f"{bd['technical']:.1f}",
            "모멘텀(40)": f"{bd['momentum']:.1f}",
            "ROE%":  f"{h.get('roe',0):.1f}",
            "마진%": f"{h.get('margin',0):.1f}",
            "PEG":   f"{h.get('peg',0):.2f}",
            "FCF%":  f"{h.get('fcf_margin',0):.1f}",
            "52W위치": f"{h.get('w52_pos',0):.1f}%",
        })

    sc_col1, sc_col2 = st.columns([3, 2])
    with sc_col1:
        fig_score = go.Figure()
        fig_score.add_trace(go.Bar(
            name="재무품질 (40pt max)",
            y=bd_tickers, x=bd_fin, orientation="h",
            marker_color="#1976D2",
            hovertemplate="%{y} 재무: %{x:.1f}pt<extra></extra>",
        ))
        fig_score.add_trace(go.Bar(
            name="기술적/52W (20pt max)",
            y=bd_tickers, x=bd_tech, orientation="h",
            marker_color="#388E3C",
            hovertemplate="%{y} 기술: %{x:.1f}pt<extra></extra>",
        ))
        fig_score.add_trace(go.Bar(
            name="모멘텀 (40pt max, 추정)",
            y=bd_tickers, x=bd_mom, orientation="h",
            marker_color="#F57C00",
            hovertemplate="%{y} 모멘텀: %{x:.1f}pt<extra></extra>",
        ))
        fig_score.update_layout(
            barmode="stack",
            template=PLOTLY_TEMPLATE,
            xaxis=dict(range=[0, 105], title="스코어 (pt)"),
            height=max(280, len(bd_tickers) * 48),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=60, r=20, t=30, b=30),
        )
        st.plotly_chart(fig_score, use_container_width=True)

    with sc_col2:
        st.dataframe(pd.DataFrame(bd_rows), hide_index=True, use_container_width=True,
                     height=max(280, len(bd_rows) * 40 + 40))


# ── 푸터 ─────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"📡 데이터 소스: portfolio_state_us.json | "
    f"갱신: {datetime.now().strftime('%H:%M:%S')} | "
    f"대시보드 v1.0"
)
