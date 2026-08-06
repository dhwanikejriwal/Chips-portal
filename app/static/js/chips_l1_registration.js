// app/static/js/chips_l1_registration.js

function approveL1Request(requestCode) {
    Swal.fire({
        title: `<div style="text-align:left; font-size:18px; font-weight:800;">Approve L1 Request</div>`,
        html: `
            <div style="text-align:left; font-family:'Inter', sans-serif;">
                <div style="background:#f8fafc; border-radius:10px; padding:12px 16px; margin-bottom:18px;">
                    <div style="font-size:10px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.4px;">Request ID</div>
                    <div style="font-weight:700; color:#16a34a; margin-top:2px;">${requestCode}</div>
                </div>
                <div>
                    <div style="font-size:11px; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px;">
                        Admin Remarks <span style="font-size:10px; text-transform:none; font-weight:400; color:#94a3b8;">(Optional — default note used if blank)</span>
                    </div>
                    <textarea id="swal-chips-l1-remarks"
                        style="width:100%; padding:10px 14px; border:1.5px solid #e2e8f0; border-radius:10px; font-size:13px; font-family:inherit; resize:vertical; min-height:80px; outline:none; box-sizing:border-box;"
                        placeholder="Add optional notes about this approval..."></textarea>
                </div>
            </div>`,
        showCancelButton: true,
        confirmButtonText: '✓ Approve Request',
        confirmButtonColor: '#10b981',
        cancelButtonText: 'Cancel',
        cancelButtonColor: '#64748b',
        width: '480px',
        focusConfirm: false,
        showLoaderOnConfirm: true,
        preConfirm: () => {
            const adminRemarks = document.getElementById('swal-chips-l1-remarks').value.trim();
            const payload = new URLSearchParams();
            payload.append('chips_remarks', adminRemarks); // 🌟 Sends raw text (empty strings will trigger the backend default)

            return fetch(`/auth/l1-registration/requests/${requestCode}/perform`, {
                method: 'POST',
                body: payload
            })
                .then(res => {
                    if (!res.ok) throw new Error("Approval transaction failed");
                    return res.json();
                })
                .catch(err => {
                    Swal.showValidationMessage(`Action failed: ${err.message}`);
                    return false;
                });
        }
    }).then(result => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'Marked as Done!', text: 'L1 registration has been successfully marked as Done.', icon: 'success', showConfirmButton: true, timer: 3000, timerProgressBar: true })
                .then(() => {
                    sessionStorage.setItem('chips_action_reloading', 'true');
                    window.location.reload();
                });
        }
    });
}

function revertL1Request(requestCode) {
    Swal.fire({
        title: `<div style="text-align:left;font-size:18px;color:#dc2626;font-weight:800;">Revert Request</div>`,
        html: `<div style="text-align:left;">
            <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:12px 14px;margin-bottom:16px;font-size:13px;color:#c2410c;">
                Request <strong>${requestCode}</strong> will be sent back to the DC with your remark.
            </div>
            <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                Revert Reason <span style="color:#ef4444;">*</span>
            </div>
            <textarea id="swal-revert-reason"
                style="width:100%;padding:10px 14px;border:1.5px solid #fca5a5;border-radius:10px;font-size:13px;font-family:inherit;resize:vertical;min-height:90px;outline:none;box-sizing:border-box;"
                placeholder="Clearly explain why this request is being reverted so the DC can correct it..." autofocus></textarea>
        </div>`,
        showCancelButton: true,
        confirmButtonText: '↩ Revert Request',
        confirmButtonColor: '#378ADD',
        cancelButtonText: 'Cancel',
        cancelButtonColor: '#6c757d',
        width: '500px',
        focusConfirm: false,
        showLoaderOnConfirm: true,
        preConfirm: () => {
            const reason = document.getElementById('swal-revert-reason').value.trim();
            if (!reason) {
                Swal.showValidationMessage('A revert reason is required.');
                return false;
            }

            const payload = new URLSearchParams();
            payload.append('revert_reason', reason);

            return fetch(`/auth/l1-registration/requests/${requestCode}/revert`, { method: 'POST', body: payload })
                .then(res => {
                    if (!res.ok) throw new Error("Revert failed");
                    return res.json();
                })
                .catch(err => {
                    Swal.showValidationMessage(`Action failed: ${err.message}`);
                    return false;
                });
        }
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({ title: 'Reverted!', text: 'Request has been sent back to the DC.', icon: 'success', showConfirmButton: true, timer: 3000, timerProgressBar: true }).then(() => {
                sessionStorage.setItem('chips_action_reloading', 'true');
                window.location.reload();
            });
        }
    });
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function getStatusBadgeHtml(status) {
    const s = (status || '').trim().toLowerCase().replace(/_/g, ' ');
    let badgeClass = 'badge-pending';
    let label = 'Pending';
    if (s.includes('approve') || s.includes('l1 done') || s.includes('l1_done')) { badgeClass = 'badge-approved'; label = 'L1 Done'; }
    else if (s.includes('revert')) { badgeClass = 'badge-reverted'; label = 'Reverted'; }
    else if (s.includes('forward') || s.includes('uidai')) { badgeClass = 'badge-forwarded'; label = s.includes('again') ? 'Forwarded Again' : 'Forwarded'; }
    else if (s.includes('reappl')) { badgeClass = 'badge-reapplied'; label = 'Reapplied'; }
    else if (s.includes('reject')) { badgeClass = 'badge-reverted'; label = 'Rejected'; }
    return `<span class="badge ${badgeClass}">${label}</span>`;
}

function buildRemarksHtml(remarks) {
    if (!remarks || remarks.length === 0) {
        return `<div style="text-align:center;padding:20px;font-style:italic;color:#94a3b8;font-size:13px;background:#f8fafc;border-radius:8px;border:1px dashed #e2e8f0;">No remarks or action history logged yet.</div>`;
    }
    let html = `<div class="remarks-timeline" style="display: flex; flex-direction: column; overflow: hidden; flex: 1 1 auto;">
        <div class="timeline-title" style="flex: 0 0 auto; margin-bottom: 10px;">Audit Action History Log</div>
        <div class="timeline-track" style="flex: 1 1 auto; overflow-y: auto; padding-right: 5px; padding-left: 35px !important; margin-left: 0 !important; border-left: none !important; background: linear-gradient(to right, transparent 12px, #e2e8f0 12px, #e2e8f0 14px, transparent 14px); background-attachment: local;">`;
    remarks.forEach(r => {
        const isChips = r.user_role !== 'dc';
        const sender = isChips ? 'CHiPS Admin' : 'District Coordinator';
        const senderClass = isChips ? 'chips' : 'dc';

        const action = r.action || '';
        let statusBadgeHtmlInline = '';
        let markerClass = 'marker-pending';
        if (action) {
            statusBadgeHtmlInline = ' ' + getStatusBadgeHtml(action);
            const aLower = action.toLowerCase();
            if (aLower.includes('approve') || aLower.includes('l1 done') || aLower.includes('l1_done')) markerClass = 'marker-approved';
            else if (aLower.includes('revert') || aLower.includes('reject')) markerClass = 'marker-reverted';
            else if (aLower.includes('forward') || aLower.includes('uidai')) markerClass = 'marker-forwarded';
            else if (aLower.includes('reappl')) markerClass = 'marker-reapplied';
        }

        const stepLabel = 'L1 Registration';

        const username = r.author_username || '';
        const hasUsername = username && username !== 'system';

        html += `
            <div class="timeline-item ${senderClass}">
                <div class="timeline-marker ${markerClass}" style="left: -31px !important;"></div>
                <div class="timeline-content">
                    <div class="timeline-section-row">
                        <span class="timeline-step-label">${stepLabel}</span>${statusBadgeHtmlInline}
                    </div>
                    <div class="timeline-by-row">
                        <span class="timeline-by">By: <strong>${sender}</strong>${hasUsername ? ' (' + escapeHtml(username) + ')' : ''}</span>
                        <span class="timeline-time">${r.timestamp || ''}</span>
                    </div>
                    <div class="timeline-body">${escapeHtml(r.remark)}</div>
                </div>
            </div>
        `;
    });
    html += `</div></div>`;
    return html;
}

function openL1DetailsModal(requestCode) {
    Swal.fire({
        html: `<div style="padding:40px;text-align:center;font-family:'Inter',sans-serif;">
            <div style="width:40px;height:40px;border:3px solid #e2e8f0;border-top-color:#4f46e5;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 16px;"></div>
            <div style="color:#94a3b8;font-size:14px;">Fetching request details…</div>
            <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
        </div>`,
        showConfirmButton: false,
        allowOutsideClick: false,
        width: '600px',
        padding: '0',
        background: '#fff'
    });

    fetch(`/auth/l1-registration/requests/${requestCode}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to extract details.");
            return res.json();
        })
        .then(data => {
            window.showL1Details(data, 'details');
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
}

window.showL1Details = function (data, activeView) {
    const displayStatus = data.status || '';
    const statusBadge = getStatusBadgeHtml(displayStatus);
    const remarksHtml = buildRemarksHtml(data.remarks || []);

    if (activeView === 'details') {
        function infoCell(label, value) {
            const v = (value && value !== 'null' && value !== 'undefined') ? escapeHtml(String(value)) : '<span style="color:#cbd5e1;">—</span>';
            return `
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01); display: flex; flex-direction: column; gap: 3px;">
                <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">${label}</div>
                <div style="font-size: 13px; font-weight: 600; color: #495057; word-break: break-word;">${v}</div>
            </div>`;
        }

        function sectionHead(title) {
            return `<div style="font-size: 11px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.8px; margin: 16px 0 12px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 6px;">${title}</div>`;
        }

        let htmlContent = `
        <div style="text-align: left; padding: 0 5px; max-height: 60vh; overflow-y: auto; font-family: 'Inter', sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                <span style="font-size: 14px; color: #666; font-weight: 600;">Request: ${data.request_code}</span>
                <span>${statusBadge}</span>
            </div>
            <div style="margin-top: -10px; margin-bottom: 15px; font-size: 12px; color: #888;">
                Submitted At: <strong>${data.created_at || '—'}</strong>
            </div>

            ${displayStatus === 'REVERTED' ? `
            <!-- Revert Reason / Remark Box -->
            <div class="revert-reason-box" style="margin-bottom: 18px;">
                <div class="revert-reason-header" style="gap: 6px;">
                    <span>💬</span> REVERT REASON / REMARK
                </div>
                <div class="revert-reason-text">
                    ${escapeHtml(data.revert_reason || 'No reason note provided.')}
                </div>
            </div>` : ''}

            ${sectionHead('Hardware & User Details')}
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px;">
                ${infoCell('Station ID', data.station_id)}
                ${infoCell('Machine ID', data.machine_id)}
                ${infoCell('Operator Name', data.operator_name || 'N/A')}
                ${infoCell('Operator ID', data.operator_id || 'N/A')}
            </div>

            ${sectionHead('System Details')}
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px;">
                ${infoCell('Model Type', data.model_type)}
                ${infoCell('Software Version', data.software_version)}
                ${infoCell('Laptop Serial Number', data.laptop_serial_no || 'N/A')}
                ${infoCell('Laptop Brand', data.laptop_brand || 'N/A')}
            </div>

            ${sectionHead('Authentication Details')}
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 12px;">
                ${infoCell('Ultra Viewer ID', data.uv_id)}
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01); display: flex; flex-direction: column; gap: 3px;">
                    <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Ultra Viewer Password</div>
                ${infoCell('Laptop Serial Number', data.laptop_serial_no)}
                ${infoCell('Laptop Brand', data.laptop_brand)}
            </div>

            ${sectionHead('Operator Details')}
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                ${infoCell('Operator Name', data.operator_name)}
                ${infoCell('Operator ID', data.operator_id)}
            </div>

            ${sectionHead('Ultra Viewer Credentials')}
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                ${infoCell('Ultra Viewer ID', data.uv_id)}
                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:11px 14px;display:flex;flex-direction:column;gap:3px;">
                    <div style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Ultra Viewer Password</div>
                    <div style="display: flex; align-items: center; gap: 8px; margin-top: 2px;">
                        <input type="password" id="chips_uv_password_display" value="${escapeHtml(data.uv_password || '')}" readonly style="background: transparent; border: none; font-size: 13px; font-weight: 600; color: #495057; width: 100%; outline: none;" />
                        <button type="button" onclick="togglePasswordVisibility('chips_uv_password_display', this)" style="background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center; color: #64748b;">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>

            <!-- View Remarks Button -->
            <div style="display: flex; justify-content: center; gap: 12px; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                <button type="button" id="btn-show-remarks" style="padding: 8px 16px; border-radius: 8px; background: #4f46e5; color: white; border: none; font-weight: 600; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#4338ca'" onmouseout="this.style.background='#4f46e5'">View Remarks</button>
            </div>
        </div>
        `;

        Swal.fire({
            title: `<span style="font-family:inherit; font-weight:800;">L1 Request Details</span>`,
            html: htmlContent,
            showCancelButton: false,
            showConfirmButton: true,
            confirmButtonText: 'Close',
            customClass: {
                confirmButton: 'swal-btn-close'
            },
            width: '600px',
            focusConfirm: false,
            didOpen: () => {
                document.getElementById('btn-show-remarks').onclick = () => {
                    window.showL1Details(data, 'remarks');
                };
            }
        });
    }
    else if (activeView === 'remarks') {
        let htmlContent = `
        <div style="text-align: left; padding: 0 5px; max-height: 60vh; display: flex; flex-direction: column; font-family: 'Inter', sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px; flex: 0 0 auto;">
                <span style="font-size: 14px; color: #666;">Request: <strong>${data.request_code}</strong></span>
                <span>${statusBadge}</span>
            </div>
            ${remarksHtml}
        </div>
        `;

        Swal.fire({
            title: `<span style="font-family:inherit; font-weight:800;">Audit Remarks History</span>`,
            html: htmlContent,
            showCancelButton: false,
            showConfirmButton: true,
            confirmButtonText: 'Close',
            showDenyButton: true,
            denyButtonText: 'Back',
            customClass: {
                confirmButton: 'swal-btn-close',
                denyButton: 'swal-btn-back'
            },
            width: '600px',
            focusConfirm: false
        }).then((result) => {
            if (result.isDenied) {
                window.showL1Details(data, 'details');
            }
        });
    }
}

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === "password") {
        input.type = "text";
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`;
    } else {
        input.type = "password";
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
    }
}

// Export helper function to fetch Excel stream from backend
function exportTableToExcel(tableID, filename = 'export.xlsx') {
    const table = document.getElementById(tableID);
    if (!table) return;

    const bodyRows = table.querySelectorAll('tbody tr');
    const ids = [];
    bodyRows.forEach(row => {
        if (row.style.display !== 'none' && row.cells.length > 1) {
            const id = row.getAttribute('data-id');
            if (id) ids.push(id);
        }
    });

    if (ids.length === 0) {
        Swal.fire({ title: 'No Data', text: 'No records found to export.', icon: 'warning', confirmButtonColor: '#3085d6' });
        return;
    }

    window.location.href = `/auth/l1-registration/export-v2?ids=${ids.join(',')}`;
}
