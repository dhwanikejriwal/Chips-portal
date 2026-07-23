import re

filepath = 'c:/chips-portal/app/templates/report/upload.html'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

# Add delete button to actions
btn_pattern = r'(<a href="{{ url_for\(\'report\.download\', report_id=report\.id\) }}"[^>]*>\s*Download\s*</a>\s*)</div>'
delete_btn = r'\1<button class="btn-delete" style="padding: 6px 14px; font-size: 13px; font-weight: 600; background: #fee2e2; color: #ef4444; border: none; border-radius: 6px; cursor: pointer; transition: all 0.2s;" onclick="deleteReport({{ report.id }})" onmouseover="this.style.background=\'#fecaca\'" onmouseout="this.style.background=\'#fee2e2\'">Delete</button>\n                                                </div>'

text = re.sub(btn_pattern, delete_btn, text)

# Add deleteReport JS function
js_pattern = r'(    function toggleViewMode\(mode\) \{)'
delete_js = r'''    async function deleteReport(reportId) {
        Swal.fire({
            title: 'Are you sure?',
            text: "This report will be permanently deleted.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#94a3b8',
            confirmButtonText: 'Delete'
        }).then(async (result) => {
            if (result.isConfirmed) {
                try {
                    const response = await fetch({{ config['BACKEND_API_URL'] }}/reports/, {
                        method: 'DELETE'
                    });
                    
                    if (response.ok) {
                        Swal.fire('Deleted!', 'Report deleted successfully.', 'success').then(() => {
                            location.reload();
                        });
                    } else {
                        const data = await response.json();
                        Swal.fire('Error', data.detail || 'Could not delete report.', 'error');
                    }
                } catch (err) {
                    Swal.fire('Error', 'Connection failed.', 'error');
                }
            }
        });
    }
    
\1'''

text = re.sub(js_pattern, delete_js, text)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Added delete button and logic successfully!")
