import re

filepath = 'c:/chips-portal/app/templates/report/upload.html'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# The button in fetchSystemPreview is currently:
# <button onclick="sortTableByTotalPending()" style="padding: 6px 14px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; color: #475569; font-size: 13px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='white'"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M6 12h12M10 18h4"></path></svg> Sort by Requests</button>

pattern = r'\s*<button onclick="sortTableByTotalPending\(\)".*?>.*?Sort by Requests</button>'

# We want to remove it ONLY from the fetchSystemPreview function.
# Let's just find the occurrence that is inside fetchSystemPreview.
# fetchSystemPreview has: LWE</button>\n                </div>\n                <button onclick="sortTableByTotalPending()"...

text = re.sub(r'(LWE</button>\s+</div>)\s*<button onclick="sortTableByTotalPending\(\)".*?</button>', r'\1', text)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Removed from system reports")
