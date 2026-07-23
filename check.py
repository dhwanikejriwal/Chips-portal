import re
import json

with open('c:/chips-portal/app/templates/report/upload.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's extract the Custom Datasets section to see its structure
match = re.search(r'<div id="custom-datasets" class="report-section">([\s\S]*?)</div>\n\s*</div>\n</div>', text)
if match:
    print(match.group(1)[:1500])
else:
    print("Not found")
