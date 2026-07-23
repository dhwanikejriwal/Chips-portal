import pandas as pd
import io
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# Simulating the report.py logic
try:
    df = pd.read_excel('c:/chips-portal/sample reports/MBU_Entry_Status_District_Wise 15-07-2026 12-10-17 PM.xlsx', header=None, engine='openpyxl')

    header_row = 0
    for i in range(min(15, len(df))):
        row_vals = [str(x).strip().lower() for x in df.iloc[i].values if pd.notna(x)]
        if any('district' in v and ('name' in v or v == 'district') for v in row_vals):
            header_row = i
            break
            
    df = pd.read_excel('c:/chips-portal/sample reports/MBU_Entry_Status_District_Wise 15-07-2026 12-10-17 PM.xlsx', header=header_row, engine='openpyxl')

    dist_col = None
    for col in df.columns:
        c = str(col).strip().lower()
        if 'district' in c and ('name' in c or c == 'district'):
            dist_col = col
            break

    if not dist_col:
        raise Exception("District Name column not found in dataset")
        
    if 'Academic Year' in df.columns:
        df = df[df['Academic Year'] != '(3)']

    keep_cols = [dist_col]
    if 'Academic Year' in df.columns:
        keep_cols.append('Academic Year')
        
    desired = ['MBU Pending (Age 5-15)', 'MBU Pending (Age 15 and above)']
    matched = []
    for d in desired:
        for c in df.columns:
            if str(c).strip().lower() == d.lower():
                matched.append(c)
                break
    if len(matched) < len(desired):
        raise Exception(f"Invalid dataset uploaded for MBU District Wise. Please ensure you uploaded the correct dataset.")
    df = df[keep_cols + matched]

    numeric_cols = []
    for col in df.columns:
        if col not in keep_cols:
            converted = pd.to_numeric(df[col], errors='coerce')
            if not converted.isna().all():
                numeric_cols.append(col)
                df[col] = converted.fillna(0).astype(int)

    df = df.dropna(subset=[dist_col])

    if numeric_cols:
        df['Total Pending'] = df[numeric_cols].sum(axis=1)
        numeric_cols.append('Total Pending')

    print("Success!")
    print("Columns:", df.columns.tolist())
    print("Row 0:", df.iloc[0].to_dict())

except Exception as e:
    print(f"Error: {e}")
