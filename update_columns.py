import re

filepath = 'c:/chips-portal/backend/routers/report.py'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r"(        # Define columns to keep\n        keep_cols = \[dist_col\]\n        if 'Academic Year' in df\.columns:\n            keep_cols\.append\('Academic Year'\))"

new_code = r"""\1
            
        # Filter specific columns based on report type
        if report_type == '18_plus_pendency':
            desired = ['Total Pending', 'Pending at SubDistrict', 'Pending at District']
            matched = []
            for d in desired:
                for c in df.columns:
                    if str(c).strip().lower() == d.lower():
                        matched.append(c)
                        break
            if matched:
                df = df[keep_cols + matched]
        elif report_type == 'mbu_district_wise':
            desired = ['MBU Pending (Age 5-15)', 'MBU Pending (Age 15 and above)']
            matched = []
            for d in desired:
                for c in df.columns:
                    if str(c).strip().lower() == d.lower():
                        matched.append(c)
                        break
            if matched:
                df = df[keep_cols + matched]"""

new_text = re.sub(pattern, new_code, text)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Added column filtering logic successfully!")
