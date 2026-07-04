import os
import re

files = [
    "app/templates/dc/dc_l1_registration.html",
    "app/templates/dc/dc_lms.html",
    "app/templates/dc/dc_nseit.html",
    "app/templates/dc/dc_reactivation.html",
    "app/templates/station_id/dc_list.html",
]

base = "d:/project/Chips-II"

replacement = """} else if (filterVal === 'week') {
            const last7Days = new Date(now);
            last7Days.setDate(now.getDate() - 7);
            last7Days.setHours(0, 0, 0, 0);
            return rowDate >= last7Days;
        } else if (filterVal === 'month') {
            const last30Days = new Date(now);
            last30Days.setDate(now.getDate() - 30);
            last30Days.setHours(0, 0, 0, 0);
            return rowDate >= last30Days;
        }"""

for fp in files:
    full = os.path.join(base, fp)
    if not os.path.exists(full): continue
    with open(full, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace labels just in case they were missed (they were already replaced by the previous script)
    # The previous script did replace the labels in all files because it was simple string replacement
    # But let's be safe. Wait, the labels were already correctly substituted by the previous script, 
    # since file sizes dropped by 10 bytes! So no need.
        
    new_content, count = re.subn(r"\}\s*else if\s*\(filterVal\s*===\s*'week'\)\s*\{[\s\S]*?(?=\n\s*return true;)", replacement, content)
    
    with open(full, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Updated {fp}: {count} replacements")
