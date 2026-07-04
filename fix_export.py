import os
import re

file_path = "d:/project/Chips-II/app/templates/dc/dc_candidate_requests.html"

if not os.path.exists(file_path):
    print("File not found.")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# The export button is an anchor tag. Let's find it.
# It looks like: <a href="{{ url_for('auth.proxy_backend_excel_export', module_endpoint='candidate-requests') }}" ...> Export to CSV </a>
# Let's replace the first one (which is in the pending section)
pending_button = """<button type="button" onclick="downloadTableAsCSV('admin-pending-table', 'pending_candidate_requests.csv')" class="btn btn-sm" style="display: inline-flex; align-items: center; background-color: #007bff; color: white; border: none; cursor: pointer;">
            Export to CSV
        </button>"""

# Replace the first occurrence
content = re.sub(
    r"<a href=\"\{\{\s*url_for\('auth\.proxy_backend_excel_export'[^>]+>[\s]*Export to CSV[\s]*</a>",
    pending_button,
    content,
    count=1
)

approved_button = """<button type="button" onclick="downloadTableAsCSV('admin-approved-table', 'approved_candidate_requests.csv')" class="btn btn-sm" style="display: inline-flex; align-items: center; background-color: #007bff; color: white; border: none; cursor: pointer;">
            Export to CSV
        </button>"""

# Replace the second occurrence
content = re.sub(
    r"<a href=\"\{\{\s*url_for\('auth\.proxy_backend_excel_export'[^>]+>[\s]*Export to CSV[\s]*</a>",
    approved_button,
    content,
    count=1
)

# Append the javascript function
js_func = """
<script>
function downloadTableAsCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        let row = [], cols = rows[i].querySelectorAll('td, th');
        if (rows[i].style.display === 'none') continue;
        if (cols.length <= 1) continue;

        for (let j = 0; j < cols.length - 1; j++) {
            let data = cols[j].innerText.replace(/(\\r\\n|\\n|\\r)/gm, '').replace(/(\\s\\s)/gm, ' ');
            data = data.replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        csv.push(row.join(','));
    }

    const csvFile = new Blob(["\\uFEFF" + csv.join('\\n')], {type: "text/csv;charset=utf-8;"});
    const downloadLink = document.createElement("a");
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = "none";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}
</script>
{% endblock %}
"""

# We'll replace the very last {% endblock %} with our JS func + endblock
if "function downloadTableAsCSV" not in content:
    idx = content.rfind("{% endblock %}")
    if idx != -1:
        content = content[:idx] + js_func + "\n" + content[idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done.")
