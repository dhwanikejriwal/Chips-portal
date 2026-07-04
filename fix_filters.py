import os
import re

files_to_update = [
    "app/templates/dc/dc_candidate_requests.html",
    "app/templates/dc/dc_l1_registration.html",
    "app/templates/dc/dc_lms.html",
    "app/templates/dc/dc_nseit.html",
    "app/templates/dc/dc_reactivation.html",
    "app/templates/l2_registration/dc_list.html",
    "app/templates/operator_activation/dc_list.html",
    "app/templates/station_id/dc_list.html",
]

base_dir = "d:/project/Chips-II"

js_replacement = """} else if (dateFilter === 'week') {
                if (!rowCreated) {
                    matchesDate = false;
                } else {
                    const rowDate = new Date(rowCreated.replace(' ', 'T'));
                    const last7Days = new Date(now);
                    last7Days.setDate(now.getDate() - 7);
                    last7Days.setHours(0, 0, 0, 0);
                    matchesDate = rowDate >= last7Days;
                }
            } else if (dateFilter === 'month') {
                if (!rowCreated) {
                    matchesDate = false;
                } else {
                    const rowDate = new Date(rowCreated.replace(' ', 'T'));
                    const last30Days = new Date(now);
                    last30Days.setDate(now.getDate() - 30);
                    last30Days.setHours(0, 0, 0, 0);
                    matchesDate = rowDate >= last30Days;
                }
            }"""

# Regex to find the existing week/month logic
js_pattern = re.compile(r"\} else if \(dateFilter === 'week'\) \{.*?(?=\s*if \(matchesQuery)", re.DOTALL)

for file_path in files_to_update:
    full_path = os.path.join(base_dir, file_path)
    if not os.path.exists(full_path):
        print(f"File not found: {full_path}")
        continue
        
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace HTML labels
    content = content.replace('>This Week</option>', '>Week</option>')
    content = content.replace('>This Month</option>', '>Month</option>')
    
    # Replace JS logic
    def replacer(match):
        # We need to make sure we preserve the indentation of the replacement
        return js_replacement + "\n"

    # We use a pattern that matches the whole week and month block up to the next if condition
    new_content, count = re.subn(r"\}\s*else if\s*\(dateFilter\s*===\s*'week'\)\s*\{[\s\S]*?(?=\}\s*else if\s*\(dateFilter\s*===\s*'month'\))\}\s*else if\s*\(dateFilter\s*===\s*'month'\)\s*\{[\s\S]*?(?=\n\s*if\s*\()", js_replacement, content)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"Updated {file_path}: {count} JS blocks replaced.")
