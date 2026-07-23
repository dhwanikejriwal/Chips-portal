import re

with open('c:/chips-portal/app/templates/report/upload.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace padding: 10px; with height: 45px; padding: 0 12px; for the report_type select
text = re.sub(
    r'<select id="report_type" name="report_type" class="filter-input" style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; background-color: white;" required>',
    r'<select id="report_type" name="report_type" class="filter-input" style="width: 100%; height: 45px; padding: 0 12px; border-radius: 6px; border: 1px solid #cbd5e1; background-color: white;" required>',
    text
)

# Replace padding: 10px; with height: 45px; padding: 0 12px; for the custom-district-filter select
text = re.sub(
    r'<select id="custom-district-filter" name="district" class="filter-input" style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #cbd5e1; background-color: white;">',
    r'<select id="custom-district-filter" name="district" class="filter-input" style="width: 100%; height: 45px; padding: 0 12px; border-radius: 6px; border: 1px solid #cbd5e1; background-color: white;">',
    text
)

with open('c:/chips-portal/app/templates/report/upload.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated upload.html successfully!")
