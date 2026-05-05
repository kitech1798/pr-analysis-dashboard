"""
Build full 25-institute scoreboard from the latest cumulative snapshot.
Output: ranking table + category-grouped view + weekly trend.
"""
import pandas as pd
from pathlib import Path

FOLDER = Path(r"c:\Users\admin\Desktop\교육\출연연 홍보 분석")
LATEST = FOLDER / "국가과학기술연구회_스크랩 목록(~0430).xlsx"
OUT_DIR = FOLDER / "산출물"
OUT_DIR.mkdir(exist_ok=True)

COLS = [
    "페이지", "순번", "구분", "매체", "온오프", "지면", "기사수",
    "스크랩일자", "기사게재일", "제목", "기자", "분류", "해당기관",
    "보도내용", "세부업무", "영향", "보도비중", "보도자료", "보도건수",
    "기고자", "보도매체수", "URL",
]

# 25 출연연 카테고리 매핑
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
ALL_25 = [i for lst in CATEGORY.values() for i in lst]

# Load
df = pd.read_excel(LATEST, sheet_name="2026년", header=None)
data = df.iloc[2:].copy()
data.columns = COLS[: data.shape[1]]
data["페이지"] = data["페이지"].ffill()
data["순번"] = data["순번"].ffill()
data = data.dropna(subset=["제목"])
data["기사게재일"] = pd.to_datetime(data["기사게재일"], errors="coerce")
data["스크랩일자"] = pd.to_datetime(data["스크랩일자"], errors="coerce")

# Filter to 분류 C (각 출연연) only
c_only = data[data["분류"] == "C"].copy()
c_only = c_only[c_only["해당기관"].isin(ALL_25)].copy()
c_only["계열"] = c_only["해당기관"].map(INST_TO_CAT)

# === Layer 1: full 25 ranking ===
ranking = (
    c_only.groupby(["해당기관"])
    .agg(
        보도건수=("제목", "count"),
        오프라인_지면=("온오프", lambda s: (s == "오프라인").sum()),
        온라인=("온오프", lambda s: (s == "온라인").sum()),
        매체수=("매체", "nunique"),
        최근기사일=("기사게재일", "max"),
    )
    .reset_index()
)
ranking["계열"] = ranking["해당기관"].map(INST_TO_CAT)
ranking["순위"] = ranking["보도건수"].rank(method="min", ascending=False).astype(int)
ranking = ranking.sort_values("보도건수", ascending=False).reset_index(drop=True)
# add KITECH marker
ranking["표시"] = ranking["해당기관"].apply(lambda x: "★ KITECH" if x == "생기연" else "")
ranking_out = ranking[["순위", "표시", "계열", "해당기관", "보도건수", "오프라인_지면", "온라인", "매체수", "최근기사일"]]
ranking_out.to_csv(OUT_DIR / "01_전체랭킹_25출연연.csv", index=False, encoding="utf-8-sig")

# === Layer 2: category-grouped ===
cat_view = ranking.copy()
cat_view = cat_view.sort_values(["계열", "보도건수"], ascending=[True, False])
cat_summary = (
    cat_view.groupby("계열")
    .agg(계열_총건수=("보도건수", "sum"), 기관수=("해당기관", "nunique"))
    .reset_index()
)
cat_summary["계열_평균"] = (cat_summary["계열_총건수"] / cat_summary["기관수"]).round(1)
cat_summary = cat_summary.sort_values("계열_총건수", ascending=False)

cat_view.to_csv(OUT_DIR / "02_계열별_정렬.csv", index=False, encoding="utf-8-sig")
cat_summary.to_csv(OUT_DIR / "03_계열_요약.csv", index=False, encoding="utf-8-sig")

# === Layer 3: weekly trend (기사게재일 기준 ISO week) ===
c_only["주차"] = c_only["기사게재일"].dt.strftime("%Y-W%V")
trend = (
    c_only.groupby(["주차", "해당기관"])
    .size()
    .unstack(fill_value=0)
    .reindex(columns=ALL_25, fill_value=0)
)
trend.to_csv(OUT_DIR / "04_주차별_트렌드.csv", encoding="utf-8-sig")

# === KITECH-focused detail ===
kitech = c_only[c_only["해당기관"] == "생기연"].copy()
kitech_top_media = kitech["매체"].value_counts().head(15)
kitech_top_reporters = kitech["기자"].value_counts().head(15)
kitech_top_media.to_csv(OUT_DIR / "05_KITECH_매체별.csv", encoding="utf-8-sig", header=["건수"])
kitech_top_reporters.to_csv(OUT_DIR / "06_KITECH_기자별.csv", encoding="utf-8-sig", header=["건수"])

# === Summary text for quick reading ===
summary_lines = []
summary_lines.append("=" * 70)
summary_lines.append("출연연 홍보 분석 — 첫 스코어보드")
summary_lines.append("데이터 기간: ~2026-04-30 누적 스냅샷")
summary_lines.append(f"총 분류 C (출연연 직접 보도) 건수: {len(c_only):,}건")
summary_lines.append("=" * 70)
summary_lines.append("")

summary_lines.append("[1] 25개 출연연 전체 랭킹")
summary_lines.append("-" * 70)
for _, r in ranking_out.iterrows():
    mark = r["표시"] if r["표시"] else "  "
    summary_lines.append(
        f"{r['순위']:>3}위 {mark:<10} [{r['계열']:<10}] {r['해당기관']:<8} {r['보도건수']:>5}건  (매체 {r['매체수']:>3}곳)"
    )
summary_lines.append("")

summary_lines.append("[2] 계열별 요약")
summary_lines.append("-" * 70)
for _, r in cat_summary.iterrows():
    summary_lines.append(
        f"  {r['계열']:<14} 총 {r['계열_총건수']:>5}건  /  기관 {r['기관수']}곳  /  기관평균 {r['계열_평균']:>6.1f}건"
    )
summary_lines.append("")

# KITECH position within its 계열
ind_cat = ranking[ranking["계열"] == "산업기술계"].sort_values("보도건수", ascending=False).reset_index(drop=True)
summary_lines.append("[3] KITECH(생기연) 산업기술계 내 위치")
summary_lines.append("-" * 70)
for i, r in ind_cat.iterrows():
    mk = "★" if r["해당기관"] == "생기연" else " "
    summary_lines.append(f"  {mk} 계열 {i+1}위: {r['해당기관']:<8} {r['보도건수']:>5}건")
summary_lines.append("")

summary_lines.append("[4] KITECH 보도 매체 TOP 10")
summary_lines.append("-" * 70)
for media, cnt in kitech_top_media.head(10).items():
    summary_lines.append(f"  {media:<20} {cnt:>4}건")
summary_lines.append("")

summary_lines.append("[5] KITECH 자주 다루는 기자 TOP 10")
summary_lines.append("-" * 70)
for rep, cnt in kitech_top_reporters.head(10).items():
    summary_lines.append(f"  {str(rep):<14} {cnt:>4}건")

summary_text = "\n".join(summary_lines)
(OUT_DIR / "_요약리포트.txt").write_text(summary_text, encoding="utf-8")

print(summary_text)
print()
print("OUTPUTS in:", OUT_DIR)
