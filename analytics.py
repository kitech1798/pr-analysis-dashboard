"""
Data loading + aggregations for the PR analysis dashboard.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

import pandas as pd

# ── 컬럼 정의 ──────────────────────────────────────────────────────────
COLS = [
    "페이지", "순번", "구분", "매체", "온오프", "지면", "기사수",
    "스크랩일자", "기사게재일", "제목", "기자", "분류", "해당기관",
    "보도내용", "세부업무", "영향", "보도비중", "보도자료", "보도건수",
    "기고자", "보도매체수", "URL",
]

# ── 출연연 카테고리 매핑 ────────────────────────────────────────────────
CATEGORY = {
    "산업기술계": ["생기연", "기계연", "재료연", "화학연", "표준연"],
    "정보통신계": ["ETRI", "KIST", "KISTI"],
    "바이오·식품계": ["생명연", "한의학연", "식품연", "김치연", "독성연"],
    "에너지·원자력계": ["원자력연", "에너지연", "핵융합연", "KERI"],
    "기초·기반계": ["기초연", "지자연", "천문연"],
    "인프라·건설계": ["철도연", "건설연"],
    "환경계": ["녹색연"],
}
INST_TO_CAT = {inst: cat for cat, lst in CATEGORY.items() for inst in lst}
ALL_INSTS = [i for lst in CATEGORY.values() for i in lst]

KITECH = "생기연"
KITECH_PEERS_DEFAULT = ["기계연", "재료연", "화학연", "표준연"]

# ── 매체 등급 (영향력 점수용) ────────────────────────────────────────────
MEDIA_TIER_WEIGHT = {
    "종합지": 5,
    "경제지": 4,
    "전문지": 3,
    "지방지": 2,
    "인터넷": 1,
}

# ── 보도내용 코드 → 유형 라벨 (가이드라인_안내 시트 기반) ─────────────────
BODO_TYPE_LABELS = {
    1: "연구성과",
    2: "현황·이슈",
    3: "사업화·기술이전",
    4: "MOU·협력",
    5: "학술·산학연 행사",
    6: "대국민 행사",
    7: "포상·수상",
    8: "임원·인사",
    9: "동정·기타",
}
BODO_TYPE_ORDER = list(BODO_TYPE_LABELS.values())

FILE_PATTERN = re.compile(r"~(\d{2})(\d{2})")


# ── 파일 로딩 ───────────────────────────────────────────────────────────
def list_xlsx(folder: Path) -> list[Path]:
    return sorted([p for p in folder.glob("*.xlsx") if not p.name.startswith("~$")])


def file_label(path: Path) -> str:
    m = FILE_PATTERN.search(path.name)
    if not m:
        return path.stem
    return f"~{m.group(1)}/{m.group(2)}"


def file_end_date(path: Path, year: int = 2026) -> Optional[pd.Timestamp]:
    m = FILE_PATTERN.search(path.name)
    if not m:
        return None
    return pd.Timestamp(year=year, month=int(m.group(1)), day=int(m.group(2)))


def load_one(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="2026년", header=None)
    df = raw.iloc[2:].copy()
    df.columns = COLS[: df.shape[1]]
    df["페이지"] = df["페이지"].ffill()
    df["순번"] = df["순번"].ffill()
    df = df.dropna(subset=["제목"])
    df["기사게재일"] = pd.to_datetime(df["기사게재일"], errors="coerce")
    df["스크랩일자"] = pd.to_datetime(df["스크랩일자"], errors="coerce")
    df["_파일"] = path.name
    df["_파일레이블"] = file_label(path)
    df["_파일종료일"] = file_end_date(path)
    return df.reset_index(drop=True)


def load_all(folder: Path) -> dict[str, pd.DataFrame]:
    """
    Returns dict of {file_label: dataframe}.
    Each file is a cumulative snapshot up to that label.
    """
    files = list_xlsx(folder)
    return {file_label(p): load_one(p) for p in files}


def latest_df(snapshots: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if not snapshots:
        return pd.DataFrame(columns=COLS)
    last_key = sorted(snapshots.keys())[-1]
    return snapshots[last_key]


def previous_df(snapshots: dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    if len(snapshots) < 2:
        return None
    keys = sorted(snapshots.keys())
    return snapshots[keys[-2]]


# ── 필터/태깅 ──────────────────────────────────────────────────────────
def add_category(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["계열"] = df["해당기관"].map(INST_TO_CAT)
    return df


def filter_C(df: pd.DataFrame) -> pd.DataFrame:
    """분류 C(각 출연연 직접 보도) + 알려진 출연연만"""
    out = df[df["분류"] == "C"].copy()
    out = out[out["해당기관"].isin(ALL_INSTS)]
    return add_category(out)


def filter_by_week(df: pd.DataFrame, iso_week: str) -> pd.DataFrame:
    """iso_week format: '2026-W05'"""
    if df.empty:
        return df
    weeks = df["기사게재일"].dt.strftime("%Y-W%V")
    return df[weeks == iso_week].copy()


def diff_new_rows(latest: pd.DataFrame, prev: pd.DataFrame) -> pd.DataFrame:
    """Rows in latest but not in prev (by URL or 제목+매체+기사게재일)"""
    if prev is None or prev.empty:
        return latest.copy()
    key_cols = ["제목", "매체", "기사게재일"]
    prev_keys = set(map(tuple, prev[key_cols].astype(str).itertuples(index=False, name=None)))
    mask = ~latest[key_cols].astype(str).apply(tuple, axis=1).isin(prev_keys)
    return latest[mask].copy()


# ── 집계: 기본 6 ───────────────────────────────────────────────────────
def kpi_cards(df_c: pd.DataFrame, prev_df_c: Optional[pd.DataFrame] = None) -> dict:
    """KITECH 위치 핵심 지표"""
    counts = df_c.groupby("해당기관").size().sort_values(ascending=False)
    total_count = int(counts.sum())
    kitech_count = int(counts.get(KITECH, 0))
    kitech_rank = int((counts > kitech_count).sum() + 1) if kitech_count > 0 else None

    industry = df_c[df_c["계열"] == "산업기술계"]
    peer_avg = float(industry.groupby("해당기관").size().mean()) if not industry.empty else 0.0

    kitech = df_c[df_c["해당기관"] == KITECH]
    kitech_media = int(kitech["매체"].nunique())

    new_count = None
    delta_rank = None
    if prev_df_c is not None and not prev_df_c.empty:
        prev_counts = prev_df_c.groupby("해당기관").size()
        prev_kitech = int(prev_counts.get(KITECH, 0))
        new_count = kitech_count - prev_kitech
        if kitech_count > 0 and prev_kitech > 0:
            prev_rank = int((prev_counts > prev_kitech).sum() + 1)
            delta_rank = prev_rank - kitech_rank  # +면 상승

    return {
        "total_articles": total_count,
        "kitech_count": kitech_count,
        "kitech_rank": kitech_rank,
        "peer_avg": peer_avg,
        "kitech_media_count": kitech_media,
        "kitech_new_this_period": new_count,
        "kitech_rank_delta": delta_rank,
        "vs_peer_pct": (kitech_count / peer_avg * 100) if peer_avg else None,
    }


def ranking_table(df_c: pd.DataFrame) -> pd.DataFrame:
    g = (
        df_c.groupby("해당기관")
        .agg(
            보도건수=("제목", "count"),
            매체수=("매체", "nunique"),
            오프라인=("온오프", lambda s: (s == "오프라인").sum()),
            온라인=("온오프", lambda s: (s == "온라인").sum()),
            최근=("기사게재일", "max"),
        )
        .reset_index()
    )
    g["계열"] = g["해당기관"].map(INST_TO_CAT)
    g["순위"] = g["보도건수"].rank(method="min", ascending=False).astype(int)
    g["KITECH"] = g["해당기관"] == KITECH
    return g.sort_values("보도건수", ascending=False).reset_index(drop=True)


def add_bodo_type(df: pd.DataFrame) -> pd.DataFrame:
    """보도내용 코드(1~9)를 사람이 읽을 수 있는 유형 라벨로 매핑."""
    df = df.copy()
    code = pd.to_numeric(df["보도내용"], errors="coerce")
    df["보도유형"] = code.map(BODO_TYPE_LABELS).fillna("미분류")
    return df


def bodo_type_summary(df_c: pd.DataFrame) -> pd.DataFrame:
    """전체 보도유형별 건수·비율."""
    df = add_bodo_type(df_c)
    s = df["보도유형"].value_counts()
    out = s.rename_axis("보도유형").reset_index(name="건수")
    total = int(out["건수"].sum())
    out["비율(%)"] = (out["건수"] / max(total, 1) * 100).round(1)
    # 정의된 순서대로 정렬 (있는 것만)
    order = [t for t in BODO_TYPE_ORDER + ["미분류"] if t in out["보도유형"].values]
    out["_order"] = out["보도유형"].map({t: i for i, t in enumerate(order)})
    return out.sort_values("_order").drop(columns="_order").reset_index(drop=True)


def bodo_type_by_institute(df_c: pd.DataFrame, insts: list[str]) -> pd.DataFrame:
    """기관 × 보도유형 건수 매트릭스."""
    df = add_bodo_type(df_c)
    df = df[df["해당기관"].isin(insts)]
    pv = df.pivot_table(
        index="해당기관", columns="보도유형", values="제목", aggfunc="count", fill_value=0
    )
    types_in_data = [t for t in BODO_TYPE_ORDER if t in pv.columns]
    pv = pv.reindex(columns=types_in_data, fill_value=0)
    pv = pv.reindex(insts).fillna(0).astype(int)
    return pv


def category_summary(df_c: pd.DataFrame) -> pd.DataFrame:
    rk = ranking_table(df_c)
    s = (
        rk.groupby("계열")
        .agg(총건수=("보도건수", "sum"), 기관수=("해당기관", "nunique"))
        .reset_index()
    )
    s["기관평균"] = (s["총건수"] / s["기관수"]).round(1)
    return s.sort_values("총건수", ascending=False)


def weekly_trend(df_c: pd.DataFrame, insts: list[str]) -> pd.DataFrame:
    df = df_c.dropna(subset=["기사게재일"]).copy()
    df["주차"] = df["기사게재일"].dt.strftime("%Y-W%V")
    pivot = (
        df[df["해당기관"].isin(insts)]
        .groupby(["주차", "해당기관"])
        .size()
        .unstack(fill_value=0)
    )
    return pivot.sort_index()


def kitech_detail(df_c: pd.DataFrame) -> dict:
    k = df_c[df_c["해당기관"] == KITECH].copy()
    return {
        "by_media": k["매체"].value_counts().rename_axis("매체").reset_index(name="건수"),
        "by_reporter": (
            k["기자"].dropna().value_counts().rename_axis("기자").reset_index(name="건수")
        ),
        "recent": k.sort_values("기사게재일", ascending=False)[
            ["기사게재일", "구분", "매체", "제목", "기자", "URL"]
        ].head(30),
    }


def gap_subjects(df_c: pd.DataFrame, peers: list[str]) -> pd.DataFrame:
    """
    동급(peers)이 다룬 세부업무인데 KITECH는 누락한 주제 추출.
    세부업무 컬럼이 비어 있으면 제목 키워드 기반으로 폴백.
    """
    df = df_c.copy()
    subj_col = "세부업무"
    # peer subjects
    peer_subj = df[df["해당기관"].isin(peers)][subj_col].dropna().value_counts()
    kitech_subj = set(df[df["해당기관"] == KITECH][subj_col].dropna().unique())
    gap = peer_subj[~peer_subj.index.isin(kitech_subj)]
    out = gap.rename_axis("세부업무").reset_index(name="동급_보도수")
    return out.head(30)


# ── 집계: A. 홍보 ROI ───────────────────────────────────────────────────
def media_type_share(df_c: pd.DataFrame, insts: list[str]) -> pd.DataFrame:
    df = df_c[df_c["해당기관"].isin(insts)]
    return (
        df.groupby(["해당기관", "구분"])
        .size()
        .unstack(fill_value=0)
        .reindex(insts)
        .fillna(0)
        .astype(int)
    )


def online_offline_ratio(df_c: pd.DataFrame, insts: list[str]) -> pd.DataFrame:
    df = df_c[df_c["해당기관"].isin(insts)]
    pv = df.groupby(["해당기관", "온오프"]).size().unstack(fill_value=0)
    if "오프라인" not in pv.columns:
        pv["오프라인"] = 0
    if "온라인" not in pv.columns:
        pv["온라인"] = 0
    pv["오프라인_비율"] = pv["오프라인"] / pv.sum(axis=1).replace(0, 1) * 100
    return pv.reindex(insts).reset_index()


def front_page_ratio(df_c: pd.DataFrame, insts: list[str]) -> pd.DataFrame:
    """앞면(1~3면) 노출 비율 추정 — 지면 컬럼에서 숫자 추출."""
    df = df_c[df_c["해당기관"].isin(insts)].copy()
    df["_지면숫자"] = df["지면"].astype(str).str.extract(r"(\d{1,3})").astype(float)
    df["_앞면"] = df["_지면숫자"].between(1, 3, inclusive="both")
    g = (
        df.groupby("해당기관")
        .agg(전체오프라인=("지면", lambda s: s.notna().sum()), 앞면=("_앞면", "sum"))
        .reset_index()
    )
    g["앞면비율"] = (g["앞면"] / g["전체오프라인"].replace(0, 1) * 100).round(1)
    return g.set_index("해당기관").reindex(insts).reset_index()


def impact_distribution(df_c: pd.DataFrame, insts: list[str]) -> pd.DataFrame:
    df = df_c[df_c["해당기관"].isin(insts)].copy()
    df["영향_수치"] = pd.to_numeric(df["영향"], errors="coerce")
    g = (
        df.dropna(subset=["영향_수치"])
        .groupby("해당기관")["영향_수치"]
        .agg(평균영향="mean", 건수="count")
        .reset_index()
    )
    g["평균영향"] = g["평균영향"].round(2)
    return g.set_index("해당기관").reindex(insts).reset_index()


# ── 집계: B. 매체·기자 인텔리전스 ───────────────────────────────────────
def media_institute_heatmap(df_c: pd.DataFrame, insts: list[str], top_media: int = 25) -> pd.DataFrame:
    df = df_c[df_c["해당기관"].isin(insts)]
    pv = df.pivot_table(index="매체", columns="해당기관", values="제목", aggfunc="count", fill_value=0)
    pv = pv.reindex(columns=insts, fill_value=0)
    pv["_총합"] = pv.sum(axis=1)
    pv = pv.sort_values("_총합", ascending=False).head(top_media).drop(columns="_총합")
    return pv


def new_reporter_candidates(df_c: pd.DataFrame, peers: list[str], min_peer: int = 2) -> pd.DataFrame:
    """동급 peers는 최소 min_peer회 다뤘는데 KITECH는 한 번도 안 다룬 기자."""
    df = df_c.dropna(subset=["기자"]).copy()
    kitech_reporters = set(df[df["해당기관"] == KITECH]["기자"].unique())
    peer_df = df[df["해당기관"].isin(peers)]
    rep_stats = (
        peer_df.groupby("기자")
        .agg(동급보도=("제목", "count"), 동급기관수=("해당기관", "nunique"), 매체=("매체", "first"))
        .reset_index()
    )
    rep_stats = rep_stats[~rep_stats["기자"].isin(kitech_reporters)]
    rep_stats = rep_stats[rep_stats["동급보도"] >= min_peer]
    return rep_stats.sort_values(["동급기관수", "동급보도"], ascending=[False, False]).reset_index(drop=True)


def reporter_influence(df_c: pd.DataFrame) -> pd.DataFrame:
    """KITECH 기사를 다룬 기자별 영향력 점수 = sum(매체등급가중)."""
    k = df_c[df_c["해당기관"] == KITECH].dropna(subset=["기자"]).copy()
    k["가중치"] = k["구분"].map(MEDIA_TIER_WEIGHT).fillna(1)
    g = (
        k.groupby("기자")
        .agg(보도수=("제목", "count"), 영향력점수=("가중치", "sum"), 매체수=("매체", "nunique"))
        .reset_index()
        .sort_values(["영향력점수", "보도수"], ascending=[False, False])
    )
    return g


# ── 집계: D. 변화 카드 ──────────────────────────────────────────────────
def change_summary(latest: pd.DataFrame, prev: Optional[pd.DataFrame]) -> dict:
    if prev is None or prev.empty:
        return {"available": False}

    cur = filter_C(latest)
    pre = filter_C(prev)

    cur_counts = cur.groupby("해당기관").size()
    pre_counts = pre.groupby("해당기관").size()

    cur_kitech = int(cur_counts.get(KITECH, 0))
    pre_kitech = int(pre_counts.get(KITECH, 0))
    delta = cur_kitech - pre_kitech

    cur_rank = int((cur_counts > cur_kitech).sum() + 1) if cur_kitech else None
    pre_rank = int((pre_counts > pre_kitech).sum() + 1) if pre_kitech else None
    rank_delta = (pre_rank - cur_rank) if (cur_rank and pre_rank) else None

    cur_kitech_media = set(cur[cur["해당기관"] == KITECH]["매체"].dropna().unique())
    pre_kitech_media = set(pre[pre["해당기관"] == KITECH]["매체"].dropna().unique())
    new_media = sorted(cur_kitech_media - pre_kitech_media)
    lost_media = sorted(pre_kitech_media - cur_kitech_media)

    new_rows = diff_new_rows(latest, prev)
    new_C = filter_C(new_rows)
    new_kitech_articles = new_C[new_C["해당기관"] == KITECH][
        ["기사게재일", "매체", "제목", "기자", "URL"]
    ].sort_values("기사게재일", ascending=False)

    # rising peers (산업기술계)
    industry_now = cur[cur["계열"] == "산업기술계"].groupby("해당기관").size()
    industry_pre = pre[pre["계열"] == "산업기술계"].groupby("해당기관").size()
    industry_delta = (industry_now - industry_pre.reindex(industry_now.index, fill_value=0)).sort_values(ascending=False)

    return {
        "available": True,
        "kitech_delta": delta,
        "kitech_rank_now": cur_rank,
        "kitech_rank_prev": pre_rank,
        "rank_delta": rank_delta,
        "new_media": new_media,
        "lost_media": lost_media,
        "new_kitech_articles": new_kitech_articles,
        "industry_delta": industry_delta,
        "total_new_rows": len(new_rows),
    }
