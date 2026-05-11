"""
Load all weekly KISTEP press monitoring files, standardize schema, output unified CSV.
"""
import pandas as pd
import re
from pathlib import Path

FOLDER = Path(r"c:\Users\admin\Desktop\교육\출연연 홍보 분석")
OUT_CSV = FOLDER / "_unified_press.csv"
OUT_SUMMARY = FOLDER / "_load_summary.txt"

COLS = [
    "페이지", "순번", "구분", "매체", "온오프", "지면", "기사수",
    "스크랩일자", "기사게재일", "제목", "기자", "분류", "해당기관",
    "보도내용", "세부업무", "영향", "보도비중", "보도자료", "보도건수",
    "기고자", "보도매체수", "URL",
]

def file_week_label(name: str) -> str:
    m = re.search(r"~(\d{2})(\d{2})", name)
    if not m:
        return name
    mm, dd = m.group(1), m.group(2)
    return f"~{mm}/{dd}"

frames = []
log_lines = []

for f in sorted(FOLDER.glob("*.xlsx")):
    df = pd.read_excel(f, sheet_name="2026년", header=None)
    # row 0 = classification legend, row 1 = header, row 2+ = data
    data = df.iloc[2:].copy()
    data.columns = COLS[: data.shape[1]]
    # forward-fill 페이지/순번 (merged-cell artifact)
    data["페이지"] = data["페이지"].ffill()
    data["순번"] = data["순번"].ffill()
    # drop fully empty rows
    data = data.dropna(subset=["제목"])
    data["주차"] = file_week_label(f.name)
    data["원본파일"] = f.name
    frames.append(data)
    log_lines.append(f"{f.name}: {len(data)} rows")

unified = pd.concat(frames, ignore_index=True)

# normalize date columns
for c in ["스크랩일자", "기사게재일"]:
    unified[c] = pd.to_datetime(unified[c], errors="coerce")

unified.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

with open(OUT_SUMMARY, "w", encoding="utf-8") as fp:
    fp.write("=== Load summary ===\n")
    for ln in log_lines:
        fp.write(ln + "\n")
    fp.write(f"\nTOTAL ROWS: {len(unified)}\n")
    fp.write(f"WEEKS: {sorted(unified['주차'].unique().tolist())}\n\n")

    fp.write("=== 분류 distribution ===\n")
    fp.write(unified["분류"].value_counts(dropna=False).to_string() + "\n\n")

    fp.write("=== 해당기관 top 30 ===\n")
    fp.write(unified["해당기관"].value_counts(dropna=False).head(30).to_string() + "\n\n")

    fp.write("=== 구분(매체타입) distribution ===\n")
    fp.write(unified["구분"].value_counts(dropna=False).to_string() + "\n\n")

    fp.write("=== 온오프 distribution ===\n")
    fp.write(unified["온오프"].value_counts(dropna=False).to_string() + "\n")

print("WROTE", OUT_CSV)
print("WROTE", OUT_SUMMARY)
