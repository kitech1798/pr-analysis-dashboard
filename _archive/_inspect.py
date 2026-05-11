import pandas as pd
from pathlib import Path

folder = Path(r"c:\Users\admin\Desktop\교육\출연연 홍보 분석")
files = sorted(folder.glob("*.xlsx"))

for f in files:
    print("="*80)
    print("FILE:", f.name)
    xl = pd.ExcelFile(f)
    print("SHEETS:", xl.sheet_names)
    for s in xl.sheet_names:
        df = pd.read_excel(f, sheet_name=s, header=None, nrows=5)
        print(f"-- sheet: {s}  shape head: {df.shape}")
        print(df.to_string(max_cols=30))
        print()
