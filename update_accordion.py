import re

with open('c:/chips-portal/app/templates/report/upload.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the HTML block
old_html = '''                    <div class="system-report-list">
                        {% for group in history|groupby('report_type') %}
                        <div class="list-item" style="display: block;">
                            <div class="list-item-content" style="border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 12px;">
                                <h3>{{ group.grouper | replace('_', ' ') | title }}</h3>
                            </div>
                            <div class="history-list" style="display: flex; flex-direction: column; gap: 8px; max-height: 250px; overflow-y: auto; padding-right: 5px;">'''

new_html = '''                    <div class="system-report-list">
                        {% for group in history|groupby('report_type') %}
                        {% set group_id = group.grouper %}
                        <div class="list-item" style="display: block; padding: 0; overflow: hidden; border: 1px solid #e2e8f0; margin-bottom: 15px;">
                            <div class="list-item-content" onclick="toggleHistory('{{ group_id }}')" style="cursor: pointer; padding: 20px; display: flex; justify-content: space-between; align-items: center; background: #fff; transition: background 0.2s;">
                                <h3 style="margin: 0;">{{ group.grouper | replace('_', ' ') | title }}</h3>
                                <svg id="icon-{{ group_id }}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #64748b; transition: transform 0.3s;">
                                    <polyline points="6 9 12 15 18 9"></polyline>
                                </svg>
                            </div>
                            <div id="history-{{ group_id }}" class="history-list" style="display: none; flex-direction: column; gap: 8px; max-height: 350px; overflow-y: auto; padding: 0 20px 20px 20px; background: #fafbfc; border-top: 1px solid #f1f5f9; margin-top: 5px;">'''

text = text.replace(old_html, new_html)

# Add the JS function
js_func = '''    function toggleHistory(groupId) {
        const historyDiv = document.getElementById('history-' + groupId);
        const icon = document.getElementById('icon-' + groupId);
        if (historyDiv.style.display === 'none' || historyDiv.style.display === '') {
            historyDiv.style.display = 'flex';
            icon.style.transform = 'rotate(180deg)';
        } else {
            historyDiv.style.display = 'none';
            icon.style.transform = 'rotate(0deg)';
        }
    }
'''

text = text.replace('let currentIsLwe = false;', js_func + '\n    let currentIsLwe = false;')

with open('c:/chips-portal/app/templates/report/upload.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated upload.html successfully!")
