import re

with open('c:/chips-portal/app/templates/report/upload.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update the header in history-detail-view
header_pattern = r'<div style="padding: 20px; background: white; border-bottom: 1px solid #e2e8f0;">\s*<h2 id="detail-title" style="margin: 0; font-size: 18px; color: #1e293b;"></h2>\s*</div>'

new_header = '''<div style="padding: 20px; background: white; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
                                <h2 id="detail-title" style="margin: 0; font-size: 18px; color: #1e293b;"></h2>
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <label for="history-district-filter" style="font-size: 14px; font-weight: 500; color: #475569;">Filter by District:</label>
                                    <select id="history-district-filter" onchange="filterHistoryTable()" style="padding: 8px 12px; border-radius: 6px; border: 1px solid #cbd5e1; outline: none; font-size: 14px; background: white;">
                                        <option value="all">All Districts</option>
                                        {% for dist in districts %}
                                        <option value="{{ dist.district_name }}">{{ dist.district_name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>'''

text = re.sub(header_pattern, new_header, text)

# 2. Update openHistoryDetail
js_pattern = r'    function openHistoryDetail\(groupId, title\) \{[\s\S]*?document\.getElementById\(\'detail-list-\' \+ groupId\)\.style\.display = \'block\';\n    \}'

new_js = '''    function openHistoryDetail(groupId, title) {
        document.getElementById('history-main-view').style.display = 'none';
        document.getElementById('history-detail-view').style.display = 'block';
        document.getElementById('detail-title').innerText = title + " History";
        
        document.querySelectorAll('.detail-list-container').forEach(c => c.style.display = 'none');
        document.getElementById('detail-list-' + groupId).style.display = 'block';
        
        document.getElementById('history-district-filter').value = 'all';
        filterHistoryTable();
    }
    
    function filterHistoryTable() {
        const filterValue = document.getElementById('history-district-filter').value.toLowerCase();
        const activeContainer = Array.from(document.querySelectorAll('.detail-list-container')).find(c => c.style.display === 'block');
        
        if (activeContainer) {
            const rows = activeContainer.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const districtText = row.cells[1].innerText.trim().toLowerCase();
                if (filterValue === 'all') {
                    row.style.display = '';
                } else {
                    if (districtText === filterValue || districtText.includes(filterValue)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                }
            });
        }
    }'''

text = re.sub(js_pattern, new_js, text)

with open('c:/chips-portal/app/templates/report/upload.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated history detail view successfully!")
