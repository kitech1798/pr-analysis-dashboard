"""Quick smoke test for analytics functions before launching Streamlit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import analytics as A

folder = Path(__file__).parent
print("Files:", [p.name for p in A.list_xlsx(folder)])

snaps = A.load_all(folder)
print("Snapshots loaded:", list(snaps.keys()))

latest = A.latest_df(snaps)
prev = A.previous_df(snaps)
print("Latest rows:", len(latest), "Prev rows:", len(prev) if prev is not None else None)

df_c = A.filter_C(latest)
prev_c = A.filter_C(prev) if prev is not None else None
print("C-only rows:", len(df_c))

print("\n[KPI]")
kpi = A.kpi_cards(df_c, prev_c)
for k, v in kpi.items():
    print(f"  {k}: {v}")

print("\n[Ranking head]")
print(A.ranking_table(df_c).head(8).to_string())

print("\n[Category summary]")
print(A.category_summary(df_c).to_string())

print("\n[Weekly trend shape]")
print(A.weekly_trend(df_c, [A.KITECH] + A.KITECH_PEERS_DEFAULT).tail(8).to_string())

print("\n[KITECH detail]")
d = A.kitech_detail(df_c)
print("media count:", len(d["by_media"]))
print("reporters:", len(d["by_reporter"]))
print("recent rows:", len(d["recent"]))

print("\n[Gap subjects head]")
print(A.gap_subjects(df_c, A.KITECH_PEERS_DEFAULT).head(5).to_string())

print("\n[Media type share]")
print(A.media_type_share(df_c, A.CATEGORY["산업기술계"]).to_string())

print("\n[Online/offline]")
print(A.online_offline_ratio(df_c, A.CATEGORY["산업기술계"]).to_string())

print("\n[Front page ratio]")
print(A.front_page_ratio(df_c, A.CATEGORY["산업기술계"]).to_string())

print("\n[Impact distribution]")
print(A.impact_distribution(df_c, A.CATEGORY["산업기술계"]).to_string())

print("\n[Heatmap shape]")
hm = A.media_institute_heatmap(df_c, [A.KITECH] + A.KITECH_PEERS_DEFAULT)
print("shape:", hm.shape)

print("\n[New reporter candidates head]")
print(A.new_reporter_candidates(df_c, A.KITECH_PEERS_DEFAULT).head(5).to_string())

print("\n[Reporter influence head]")
print(A.reporter_influence(df_c).head(5).to_string())

print("\n[Change summary]")
chg = A.change_summary(latest, prev)
for k, v in chg.items():
    if hasattr(v, "shape"):
        print(f"  {k}: shape {v.shape}")
    elif isinstance(v, list):
        print(f"  {k}: {len(v)} items — {v[:5]}")
    else:
        print(f"  {k}: {v}")

print("\nALL SMOKE TESTS PASSED")
