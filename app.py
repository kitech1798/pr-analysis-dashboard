"""
출연연 홍보 분석 — Streamlit 대시보드
실행:  streamlit run app.py
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analytics as A

# ── 페이지 설정 ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="출연연 홍보 분석",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 비밀번호 게이트 ─────────────────────────────────────────────────────
def _check_password() -> bool:
    """secrets에 비밀번호가 설정되어 있으면 통과 전 입력 요구."""
    try:
        expected = st.secrets.get("password")
    except Exception:
        expected = None
    if not expected:  # secrets 없으면 보호 비활성 (로컬 개발 편의)
        return True

    def _on_submit():
        st.session_state["_pw_ok"] = (
            st.session_state.get("_pw_input", "") == expected
        )

    if st.session_state.get("_pw_ok"):
        return True

    st.title("🔒 출연연 홍보 분석 대시보드")
    st.caption("열람 권한이 있는 사람에게 발급된 비밀번호를 입력해 주세요.")
    st.text_input(
        "비밀번호",
        type="password",
        key="_pw_input",
        on_change=_on_submit,
    )
    if st.session_state.get("_pw_ok") is False:
        st.error("비밀번호가 틀렸습니다.")
    return False


if not _check_password():
    st.stop()

DEFAULT_FOLDER = Path(__file__).parent
KITECH_COLOR = "#E63946"
PEER_COLOR = "#457B9D"
OTHER_COLOR = "#A8DADC"

# ── 사이드바 ────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ 설정")

folder_input = st.sidebar.text_input(
    "데이터 폴더",
    value=str(DEFAULT_FOLDER),
    help="이 폴더의 .xlsx 파일을 모두 읽어 들입니다.",
)
folder = Path(folder_input)

if not folder.exists():
    st.sidebar.error("폴더가 존재하지 않습니다.")
    st.stop()

@st.cache_data(show_spinner="엑셀 파일 로딩 중…")
def load_snapshots(folder_str: str, mtime_key: float):
    return A.load_all(Path(folder_str))

# 캐시 무효화 키: 파일 mtime 합
files = A.list_xlsx(folder)
if not files:
    st.warning("폴더에 .xlsx 파일이 없습니다. 데이터 파일을 추가해주세요.")
    st.stop()

mtime_key = sum(p.stat().st_mtime for p in files)
snapshots = load_snapshots(str(folder), mtime_key)

snapshot_keys = sorted(snapshots.keys())
st.sidebar.success(f"파일 {len(snapshot_keys)}개 로딩 완료")
st.sidebar.caption("주차별 누적 스냅샷:\n" + "\n".join(f"• {k}" for k in snapshot_keys))

# 분석 모드
mode = st.sidebar.radio(
    "분석 모드",
    ["누적 (최신 스냅샷 전체)", "특정 주차만", "직전 주 신규만"],
    index=0,
)

selected_snapshot = st.sidebar.selectbox(
    "기준 스냅샷",
    options=snapshot_keys,
    index=len(snapshot_keys) - 1,
)
latest = snapshots[selected_snapshot]
prev_key_idx = snapshot_keys.index(selected_snapshot) - 1
prev = snapshots[snapshot_keys[prev_key_idx]] if prev_key_idx >= 0 else None

# 데이터 산정
if mode == "누적 (최신 스냅샷 전체)":
    df = latest.copy()
elif mode == "직전 주 신규만":
    if prev is None:
        st.sidebar.warning("직전 스냅샷이 없습니다. 누적 모드로 표시합니다.")
        df = latest.copy()
    else:
        df = A.diff_new_rows(latest, prev)
else:  # 특정 주차만
    weeks_in_data = sorted(latest["기사게재일"].dropna().dt.strftime("%Y-W%V").unique())
    if not weeks_in_data:
        st.sidebar.warning("기사게재일이 비어있습니다.")
        df = latest.copy()
    else:
        sel_week = st.sidebar.select_slider(
            "ISO 주차 선택",
            options=weeks_in_data,
            value=weeks_in_data[-1],
        )
        df = A.filter_by_week(latest, sel_week)

# 비교 대상 출연연
peer_options = A.ALL_INSTS
default_peers = A.KITECH_PEERS_DEFAULT
selected_peers = st.sidebar.multiselect(
    "비교 대상 출연연",
    options=[i for i in peer_options if i != A.KITECH],
    default=default_peers,
)

st.sidebar.divider()
st.sidebar.caption("Made for KITECH 전략홍보실")

# ── 메인 헤더 ───────────────────────────────────────────────────────────
st.title("📊 출연연 홍보 분석 대시보드")
st.caption(
    f"기준 스냅샷: **{selected_snapshot}** · 분석 모드: **{mode}** · "
    f"표시 행수: **{len(df):,}**"
)

# 분류 C 필터링
df_c = A.filter_C(df)
prev_c = A.filter_C(prev) if prev is not None else None

# ── 1. KPI 카드 ────────────────────────────────────────────────────────
st.subheader("1️⃣ KITECH 핵심 지표")

kpi = A.kpi_cards(df_c, prev_c)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "KITECH 보도건수",
    f"{kpi['kitech_count']:,}건",
    delta=f"{kpi['kitech_new_this_period']:+}건" if kpi["kitech_new_this_period"] is not None else None,
)
c2.metric(
    "전체 순위 (분류 C 출연연 중)",
    f"{kpi['kitech_rank']}위" if kpi["kitech_rank"] else "—",
    delta=f"{kpi['kitech_rank_delta']:+}" if kpi["kitech_rank_delta"] is not None else None,
    delta_color="inverse",  # 순위는 작을수록 좋음
)
c3.metric(
    "산업기술계 평균 대비",
    f"{kpi['vs_peer_pct']:.0f}%" if kpi["vs_peer_pct"] else "—",
    help=f"산업기술계 5개 기관 평균 {kpi['peer_avg']:.1f}건 대비 KITECH 비율",
)
c4.metric("매체 다양성", f"{kpi['kitech_media_count']}곳")
c5.metric("전체 분석 건수", f"{kpi['total_articles']:,}건")

st.divider()

# ── 2. 25개 출연연 랭킹 ────────────────────────────────────────────────
st.subheader("2️⃣ 출연연 보도 랭킹")
rk = A.ranking_table(df_c)
if not rk.empty:
    rk_disp = rk.copy()
    rk_disp["bar_color"] = rk_disp["KITECH"].map({True: KITECH_COLOR, False: PEER_COLOR})

    fig = go.Figure(
        go.Bar(
            x=rk_disp["보도건수"],
            y=rk_disp["해당기관"],
            orientation="h",
            marker_color=rk_disp["bar_color"],
            text=rk_disp["보도건수"],
            textposition="outside",
            customdata=rk_disp[["계열", "매체수"]].values,
            hovertemplate="%{y}<br>건수: %{x}<br>계열: %{customdata[0]}<br>매체수: %{customdata[1]}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(400, 25 * len(rk_disp)),
        yaxis=dict(autorange="reversed", title=None),
        xaxis_title="보도건수",
        margin=dict(l=80, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("표시할 데이터가 없습니다.")

st.divider()

# ── 2-A. 보도자료 유형 분포 ─────────────────────────────────────────────
st.subheader("📋 보도자료 유형")
st.caption("연구성과·MOU·행사 등 보도내용 코드 기준 분류 (출처: 가이드라인_안내 시트)")

type_sum = A.bodo_type_summary(df_c)
left_t, right_t = st.columns([1, 1])

with left_t:
    st.markdown("**전체 유형별 건수**")
    if not type_sum.empty:
        type_sum_disp = type_sum.copy()
        type_sum_disp["라벨"] = (
            type_sum_disp["건수"].astype(str)
            + " ("
            + type_sum_disp["비율(%)"].astype(str)
            + "%)"
        )
        fig = px.bar(
            type_sum_disp,
            x="건수",
            y="보도유형",
            orientation="h",
            text="라벨",
            color="보도유형",
        )
        fig.update_layout(
            height=360,
            showlegend=False,
            yaxis=dict(autorange="reversed", title=None),
            margin=dict(l=80, r=40, t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("보도내용 데이터가 없습니다.")

with right_t:
    st.markdown("**🏭 산업기술계 5개 기관 — 유형별 비중(%)**")
    type_by_inst = A.bodo_type_by_institute(df_c, A.CATEGORY["산업기술계"])
    if not type_by_inst.empty and type_by_inst.sum().sum() > 0:
        type_pct = type_by_inst.div(
            type_by_inst.sum(axis=1).replace(0, 1), axis=0
        ) * 100
        type_long = (
            type_pct.reset_index()
            .melt(id_vars="해당기관", var_name="보도유형", value_name="비율")
        )
        fig = px.bar(
            type_long,
            x="해당기관",
            y="비율",
            color="보도유형",
            text=type_long["비율"].round(0).astype(int),
            barmode="stack",
        )
        fig.update_layout(
            height=360,
            yaxis_title="비율(%)",
            margin=dict(l=40, r=40, t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("💡 KITECH(생기연)의 막대를 동급 기관과 비교 — 어느 유형에 치우쳤는지 보임")
    else:
        st.info("산업기술계 데이터가 없습니다.")

st.divider()

# ── 3. 계열별 그룹 비교 ────────────────────────────────────────────────
st.subheader("3️⃣ 계열별 분포")
cat_sum = A.category_summary(df_c)
left, right = st.columns([1, 1])
with left:
    if not cat_sum.empty:
        fig = px.bar(
            cat_sum,
            x="총건수",
            y="계열",
            orientation="h",
            text="총건수",
            color="계열",
        )
        fig.update_layout(
            height=320,
            showlegend=False,
            yaxis=dict(autorange="reversed"),
            margin=dict(l=80, r=40, t=20, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
with right:
    st.dataframe(cat_sum, hide_index=True, use_container_width=True)

# 산업기술계 zoom
st.markdown("**🏭 산업기술계 5개 기관 비교** (KITECH 동급 그룹)")
ind = rk[rk["계열"] == "산업기술계"][["순위", "해당기관", "보도건수", "매체수"]].reset_index(drop=True)
st.dataframe(ind, hide_index=True, use_container_width=True)

st.divider()

# ── 4. 주차별 시계열 ───────────────────────────────────────────────────
st.subheader("4️⃣ 주차별 트렌드 (KITECH + 비교 출연연)")
trend_insts = [A.KITECH] + selected_peers
# 시계열은 항상 latest 누적 기준 (분석 모드와 무관)
trend_df = A.weekly_trend(A.filter_C(latest), trend_insts)
if not trend_df.empty:
    trend_long = trend_df.reset_index().melt(id_vars="주차", var_name="기관", value_name="건수")
    color_map = {A.KITECH: KITECH_COLOR}
    fig = px.line(
        trend_long,
        x="주차",
        y="건수",
        color="기관",
        markers=True,
        color_discrete_map=color_map,
    )
    fig.update_traces(line=dict(width=3), selector=dict(name=A.KITECH))
    fig.update_layout(height=380, margin=dict(l=40, r=40, t=20, b=40))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("주차별 데이터가 부족합니다.")

st.divider()

# ── 5. KITECH 상세 패널 ───────────────────────────────────────────────
st.subheader("5️⃣ KITECH 상세")
detail = A.kitech_detail(df_c)
col_m, col_r = st.columns(2)
with col_m:
    st.markdown("**보도 매체 TOP 15**")
    st.dataframe(detail["by_media"].head(15), hide_index=True, use_container_width=True)
with col_r:
    st.markdown("**기자 TOP 15**")
    st.dataframe(detail["by_reporter"].head(15), hide_index=True, use_container_width=True)

st.markdown("**최근 KITECH 보도 30건**")
recent = detail["recent"].copy()
recent["기사게재일"] = recent["기사게재일"].dt.strftime("%Y-%m-%d")
st.dataframe(
    recent,
    hide_index=True,
    use_container_width=True,
    column_config={"URL": st.column_config.LinkColumn("URL", display_text="🔗")},
)

st.divider()

# ── 6. 갭 테이블 ───────────────────────────────────────────────────────
st.subheader("6️⃣ 갭 분석 — 동급은 다뤘는데 KITECH는 누락한 주제")
gap = A.gap_subjects(df_c, selected_peers)
if not gap.empty:
    st.dataframe(gap, hide_index=True, use_container_width=True)
else:
    st.info("누락 주제가 없거나 세부업무 컬럼이 비어있습니다.")

st.divider()

# ── 7. 보도 ROI: 매체 타입 점유율 ───────────────────────────────────────
st.subheader("7️⃣ 보도 ROI — 매체 타입 분포 (산업기술계 비교)")
ind_insts = A.CATEGORY["산업기술계"]
share = A.media_type_share(df_c, ind_insts)
if not share.empty:
    share_pct = share.div(share.sum(axis=1).replace(0, 1), axis=0) * 100
    share_long = share_pct.reset_index().melt(id_vars="해당기관", var_name="매체타입", value_name="비율")
    fig = px.bar(
        share_long,
        x="해당기관",
        y="비율",
        color="매체타입",
        text=share_long["비율"].round(0).astype(int),
        barmode="stack",
    )
    fig.update_layout(height=360, yaxis_title="비율(%)", margin=dict(l=40, r=40, t=20, b=40))
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("원시 건수 보기"):
        st.dataframe(share, use_container_width=True)

# ── 8. 온/오프라인 + 앞면 노출 ─────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("8️⃣ 온/오프라인 비율")
    oo = A.online_offline_ratio(df_c, ind_insts)
    if not oo.empty:
        fig = px.bar(
            oo,
            x="해당기관",
            y="오프라인_비율",
            text=oo["오프라인_비율"].round(0).astype(int),
            color="해당기관",
        )
        fig.update_layout(height=320, showlegend=False, yaxis_title="오프라인 비율(%)")
        st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("9️⃣ 앞면(1~3면) 노출 비율")
    fp = A.front_page_ratio(df_c, ind_insts)
    if not fp.empty:
        fig = px.bar(
            fp,
            x="해당기관",
            y="앞면비율",
            text=fp["앞면비율"].round(0).astype(int),
            color="해당기관",
        )
        fig.update_layout(height=320, showlegend=False, yaxis_title="앞면 비율(%)")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 10. 영향력 평균 ─────────────────────────────────────────────────────
st.subheader("🔟 보도 영향 점수 평균 (산업기술계)")
imp = A.impact_distribution(df_c, ind_insts)
if not imp.empty and imp["평균영향"].notna().any():
    fig = px.bar(
        imp.dropna(subset=["평균영향"]),
        x="해당기관",
        y="평균영향",
        text="평균영향",
        color="해당기관",
    )
    fig.update_layout(height=320, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("영향 컬럼 데이터가 부족합니다.")

st.divider()

# ── 11. 매체 × 출연연 히트맵 ────────────────────────────────────────────
st.subheader("1️⃣1️⃣ 매체 × 출연연 히트맵 (TOP 25 매체)")
heat_insts = [A.KITECH] + selected_peers
heat = A.media_institute_heatmap(df_c, heat_insts, top_media=25)
if not heat.empty:
    fig = go.Figure(
        go.Heatmap(
            z=heat.values,
            x=heat.columns,
            y=heat.index,
            colorscale="Reds",
            text=heat.values,
            texttemplate="%{text}",
            hovertemplate="%{y} × %{x}: %{z}건<extra></extra>",
        )
    )
    fig.update_layout(
        height=600,
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(l=120, r=40, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("💡 KITECH 열에서 0인 매체 = 공략 후보. 동급 출연연이 모두 보도된 매체일수록 우선순위.")

st.divider()

# ── 12. 신규 기자 발굴 + KITECH 기자 영향력 ────────────────────────────
col_n, col_i = st.columns(2)

with col_n:
    st.subheader("1️⃣2️⃣ 신규 기자 발굴 후보")
    st.caption("동급 출연연(선택한 비교 출연연)을 다룬 기자 중 KITECH는 한 번도 안 다룬 기자")
    cand = A.new_reporter_candidates(df_c, selected_peers, min_peer=2)
    if not cand.empty:
        st.dataframe(cand.head(20), hide_index=True, use_container_width=True)
    else:
        st.info("후보가 없습니다.")

with col_i:
    st.subheader("1️⃣3️⃣ KITECH 기자 영향력 점수")
    st.caption("매체 등급(종합지=5, 경제지=4, 전문지=3, 지방지=2, 인터넷=1) × 빈도 가중")
    inf = A.reporter_influence(df_c)
    if not inf.empty:
        st.dataframe(inf.head(20), hide_index=True, use_container_width=True)
    else:
        st.info("기자 데이터가 부족합니다.")

st.divider()

# ── 14. 변화 카드 ───────────────────────────────────────────────────────
st.subheader("1️⃣4️⃣ 직전 주 대비 변화")
chg = A.change_summary(latest, prev)
if not chg["available"]:
    st.info("이전 주 스냅샷이 없어 비교할 수 없습니다.")
else:
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric(
        "KITECH 보도건수 변화",
        "—",
        delta=f"{chg['kitech_delta']:+}건",
    )
    cc2.metric(
        "순위 변화",
        f"{chg['kitech_rank_now']}위" if chg["kitech_rank_now"] else "—",
        delta=f"{chg['rank_delta']:+}" if chg["rank_delta"] is not None else None,
        delta_color="inverse",
    )
    cc3.metric("이번 주 신규 행 (전 출연연)", f"{chg['total_new_rows']:,}")
    cc4.metric("KITECH 신규 매체", f"{len(chg['new_media'])}곳")

    col_nm, col_lm = st.columns(2)
    with col_nm:
        st.markdown("**🆕 KITECH 새로 등장한 매체**")
        if chg["new_media"]:
            st.write(", ".join(chg["new_media"]))
        else:
            st.caption("없음")
    with col_lm:
        st.markdown("**📉 KITECH 사라진 매체** (이전엔 있었으나 이번엔 누락)")
        if chg["lost_media"]:
            st.write(", ".join(chg["lost_media"]))
        else:
            st.caption("없음")

    st.markdown("**📰 이번 주 KITECH 신규 보도**")
    if not chg["new_kitech_articles"].empty:
        nk = chg["new_kitech_articles"].copy()
        nk["기사게재일"] = nk["기사게재일"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            nk,
            hide_index=True,
            use_container_width=True,
            column_config={"URL": st.column_config.LinkColumn("URL", display_text="🔗")},
        )
    else:
        st.caption("이번 주 KITECH 신규 보도 없음")

    st.markdown("**📈 산업기술계 변화**")
    ind_d = chg["industry_delta"].reset_index()
    ind_d.columns = ["기관", "증감"]
    st.dataframe(ind_d, hide_index=True, use_container_width=True)

st.divider()
st.caption(
    f"📁 데이터: {folder} · 새 파일을 폴더에 추가하면 좌측 상단 'Rerun'으로 즉시 반영됩니다."
)
