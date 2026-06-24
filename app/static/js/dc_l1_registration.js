// app/static/js/dc_l1_registration.js

document.addEventListener("DOMContentLoaded", () => {
    // Show dashboard by default
    showL1Dashboard();
    filterL1Table();
});

function showL1Dashboard() {
    document.getElementById('view-l1-dashboard-panel').style.display = 'block';
    document.getElementById('view-l1-application-panel').style.display = 'none';
}

function showL1Form() {
    document.getElementById('view-l1-dashboard-panel').style.display = 'none';
    document.getElementById('view-l1-application-panel').style.display = 'block';
}

function filterL1Table() {
    const input = document.getElementById('l1-search-input');
    const filter = input.value.toUpperCase();

    const dateFilterEl = document.getElementById('l1-date-filter');
    const dateFilter = dateFilterEl ? dateFilterEl.value : 'month'; // default to month

    const now = new Date();
    const y = now.getFullYear();
    const m = (now.getMonth() + 1).toString().padStart(2, '0');
    const d = now.getDate().toString().padStart(2, '0');

    const todayPrefix = `${y}-${m}-${d}`;
    const monthPrefix = `${y}-${m}`;

    ['pending', 'log'].forEach(sec => {
        const rows = document.querySelectorAll(`#${sec}-tbody tr[data-status]`);
        let visibleCount = 0;
        const statusFilterEl = document.getElementById(`${sec}-status-filter`);
        const statusFilter = statusFilterEl ? statusFilterEl.value.toUpperCase() : 'ALL';

        rows.forEach(row => {
            const reqCode = (row.getAttribute('data-request-code') || '').toUpperCase();
            const stationId = (row.getAttribute('data-station-id') || '').toUpperCase();
            const model = (row.getAttribute('data-model') || '').toUpperCase();
            const rowStatus = (row.getAttribute('data-status') || '').toUpperCase();
            const createdDate = row.getAttribute('data-created') || '';

            const matchQuery = !filter ||
                reqCode.indexOf(filter) > -1 ||
                stationId.indexOf(filter) > -1 ||
                model.indexOf(filter) > -1;

            const matchStatus = (statusFilter === 'ALL') || (rowStatus === statusFilter);

            let matchDate = true;
            if (dateFilter === 'today') {
                matchDate = createdDate.startsWith(todayPrefix);
            } else if (dateFilter === 'week') {
                if (!createdDate) {
                    matchDate = false;
                } else {
                    const rowDate = new Date(createdDate.replace(' ', 'T'));
                    const startOfWeek = new Date(now);
                    const day = startOfWeek.getDay();
                    startOfWeek.setDate(now.getDate() - day);
                    startOfWeek.setHours(0, 0, 0, 0);

                    const endOfWeek = new Date(startOfWeek);
                    endOfWeek.setDate(startOfWeek.getDate() + 6);
                    endOfWeek.setHours(23, 59, 59, 999);

                    matchDate = rowDate >= startOfWeek && rowDate <= endOfWeek;
                }
            } else if (dateFilter === 'month') {
                matchDate = createdDate.startsWith(monthPrefix);
            }

            if (matchQuery && matchStatus && matchDate) {
                row.style.display = "";
                visibleCount++;
            } else {
                row.style.display = "none";
            }
        });

        const tbl = document.getElementById(`${sec}-table`);
        const emg = document.getElementById(`${sec}-empty-msg`);
        const cnt = document.getElementById(`${sec}-count`);

        if (tbl) tbl.style.display = (visibleCount === 0 && rows.length > 0) ? 'none' : '';
        if (emg) emg.style.display = (visibleCount === 0) ? 'block' : 'none';
        if (cnt) cnt.textContent = visibleCount;
    });
}

function clearAllFilters() {
    document.getElementById('l1-search-input').value = '';
    const pendingStatusEl = document.getElementById('pending-status-filter');
    if (pendingStatusEl) pendingStatusEl.value = 'all';
    const logStatusEl = document.getElementById('log-status-filter');
    if (logStatusEl) logStatusEl.value = 'all';
    const dateFilterEl = document.getElementById('l1-date-filter');
    if (dateFilterEl) dateFilterEl.value = 'month';
    filterL1Table();
}

function submitL1Registration(event) {
    event.preventDefault();
    const formElement = document.getElementById('l1RegistrationForm');
    const formData = new FormData(formElement);

    const requiredFields = ['station_id', 'machine_id', 'model_type', 'software_version', 'uv_id', 'uv_password'];
    for (let field of requiredFields) {
        if (!formData.get(field) || formData.get(field).trim() === '') {
            Swal.fire('Validation Error', `Please fill out all required fields.`, 'warning');
            return;
        }
    }

    Swal.fire({
        title: 'Submitting Request...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    const routingTargetUrl = window.location.origin + '/auth/l1-registration/submit';

    fetch(routingTargetUrl, { method: 'POST', body: formData })
        .then(res => {
            return res.json().then(data => {
                if (!res.ok) throw new Error(data.detail || "Server transaction processing failure.");
                return data;
            });
        })
        .then(() => {
            Swal.fire({
                title: 'Submitted Successfully',
                text: 'Your L1 registration request has been sent to CHIPS.',
                icon: 'success',
                confirmButtonColor: '#007bff',
                allowOutsideClick: false
            }).then(() => {
                window.location.reload();
            });
        })
        .catch(err => {
            Swal.fire({ title: 'Submission Error', text: err.message, icon: 'error' });
        });
}

function openL1ReapplyModal(requestCode) {
    Swal.fire({
        title: `Fetching Request Details...`,
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    fetch(`/auth/l1-registration/requests/${requestCode}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to extract details.");
            return res.json();
        })
        .then(data => {
            Swal.close();

            const htmlContent = `
            <div style="text-align: left; font-size: 14px; color: #334155; font-family: sans-serif;">
                <div style="margin-bottom: 15px; padding: 10px; background: #fee2e2; border-radius: 6px; color: #b91c1c;">
                    <strong>Revert Reason:</strong> ${data.revert_reason || 'No reason provided.'}
                </div>
                <form id="reapplyL1Form">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">Station ID *</label>
                            <input type="text" name="station_id" value="${data.station_id}" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                        </div>
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">Machine ID *</label>
                            <input type="text" name="machine_id" value="${data.machine_id}" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">Operator Name</label>
                            <input type="text" name="operator_name" value="${data.operator_name || ''}" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                        </div>
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">Operator ID</label>
                            <input type="text" name="operator_id" value="${data.operator_id || ''}" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">Model Type *</label>
                            <select name="model_type" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                                <option value="ECMP" ${data.model_type === 'ECMP' ? 'selected' : ''}>ECMP</option>
                                <option value="UCL" ${data.model_type === 'UCL' ? 'selected' : ''}>UCL</option>
                                <option value="VLE" ${data.model_type === 'VLE' ? 'selected' : ''}>VLE</option>
                            </select>
                        </div>
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">Software Version *</label>
                            <input type="text" name="software_version" value="${data.software_version}" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">UV ID *</label>
                            <input type="text" name="uv_id" value="${data.uv_id}" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                        </div>
                        <div>
                            <label style="font-weight: 600; font-size: 13px;">UV Password *</label>
                            <div style="position: relative;">
                                <input type="password" id="reapply_uv_password_input" name="uv_password" value="${data.uv_password}" style="width: 100%; padding: 8px; padding-right: 40px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box;">
                                <button type="button" onclick="togglePasswordVisibility('reapply_uv_password_input', this)" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center; justify-content: center; color: #64748b;">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                        <circle cx="12" cy="12" r="3"></circle>
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </form>
            </div>
        `;

            Swal.fire({
                title: `Edit & Reapply L1 Request (${requestCode})`,
                html: htmlContent,
                width: '600px',
                showCancelButton: true,
                confirmButtonText: 'Reapply',
                confirmButtonColor: '#007bff',
                preConfirm: () => {
                    const form = document.getElementById('reapplyL1Form');
                    const formData = new FormData(form);
                    const payload = new URLSearchParams();
                    for (const pair of formData) {
                        payload.append(pair[0], pair[1]);
                    }
                    return fetch(`/auth/l1-registration/requests/${requestCode}/reapply`, { method: 'PUT', body: payload })
                        .then(response => {
                            if (!response.ok) throw new Error("Failed to reapply");
                            return response.json();
                        });
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    Swal.fire('Success', 'Request reapplied successfully.', 'success').then(() => window.location.reload());
                }
            });
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
}

function getStatusBadgeHtml(status) {
    const s = (status || '').trim().toLowerCase().replace(/_/g, ' ');
    let badgeClass = 'badge-pending';
    let label = 'Pending';
    if (s.includes('approve') || s.includes('reviewed')) { badgeClass = 'badge-approved'; label = 'Approved'; }
    else if (s.includes('revert')) { badgeClass = 'badge-reverted'; label = 'Reverted'; }
    else if (s.includes('forward') || s.includes('uidai')) { badgeClass = 'badge-forwarded'; label = s.includes('again') ? 'Forwarded Again' : 'Forwarded'; }
    else if (s.includes('reappl')) { badgeClass = 'badge-reapplied'; label = 'Reapplied'; }
    else if (s.includes('reject')) { badgeClass = 'badge-reverted'; label = 'Rejected'; }
    return `<span class="badge ${badgeClass}">${label}</span>`;
}

function buildL1RemarksHtml(remarks) {
    if (!remarks || remarks.length === 0) return '';
    let html = `<div class="remarks-timeline" style="margin-top: 15px;">
        <div class="timeline-title">Audit Action History Log</div>
        <div class="timeline-track">`;
    remarks.forEach(r => {
        const isChips = r.user_role === 'chips' || r.user_role === 'CHIPS_ADMIN';
        const sender = isChips ? 'CHiPS Admin' : 'District Coordinator';
        const senderClass = isChips ? 'chips' : 'dc';

        const statusAfter = r.action || '';
        let statusBadgeHtmlInline = '';
        let markerClass = 'marker-pending';
        if (statusAfter) {
            statusBadgeHtmlInline = ' ' + getStatusBadgeHtml(statusAfter);
            const sLower = statusAfter.toLowerCase();
            if (sLower.includes('approve') || sLower.includes('reviewed')) markerClass = 'marker-approved';
            else if (sLower.includes('revert') || sLower.includes('reject')) markerClass = 'marker-reverted';
            else if (sLower.includes('forward') || sLower.includes('uidai')) markerClass = 'marker-forwarded';
            else if (sLower.includes('reappl')) markerClass = 'marker-reapplied';
        }

        html += `
            <div class="timeline-item ${senderClass}">
                <div class="timeline-marker ${markerClass}"></div>
                <div class="timeline-content">
                    <div class="timeline-section-row">
                        <span class="timeline-step-label">L1 Registration</span>${statusBadgeHtmlInline}
                    </div>
                    <div class="timeline-by-row">
                        <span class="timeline-by">By: <strong>${sender}</strong></span>
                        <span class="timeline-time">${r.timestamp}</span>
                    </div>
                    <div class="timeline-body">${r.remark}</div>
                </div>
            </div>
        `;
    });
    html += `</div></div>`;
    return html;
}

window.showL1Details = function (d, activeView) {
    const statusBadge = getStatusBadgeHtml(d.status);

    if (activeView === 'details') {
        const infoHtml = `
            <div style="text-align: left; padding: 0 5px; max-height: 60vh; overflow-y: auto; font-family: 'Inter', sans-serif;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                    <span style="font-size: 14px; color: #666; font-weight: 600;">Request: ${d.request_code}</span>
                    <span>${statusBadge}</span>
                </div>
                
                <!-- Hardware & User Details Card -->
                <div style="margin-bottom: 20px;">
                    <div style="font-size: 11px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 6px;">Hardware &amp; User Details</div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Station ID</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.station_id}</div>
                        </div>
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Machine ID</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.machine_id}</div>
                        </div>
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Operator Name</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.operator_name || 'N/A'}</div>
                        </div>
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Operator ID</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.operator_id || 'N/A'}</div>
                        </div>
                    </div>
                </div>

                <!-- System Details Card -->
                <div style="margin-bottom: 20px;">
                    <div style="font-size: 11px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 6px;">System Details</div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Model Type</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.model_type}</div>
                        </div>
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Software Version</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.software_version}</div>
                        </div>
                    </div>
                </div>

                <!-- Authentication Details Card -->
                <div style="margin-bottom: 20px;">
                    <div style="font-size: 11px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 6px;">Authentication Details</div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">UV ID</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.uv_id}</div>
                        </div>
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                            <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">UV Password</div>
                            <div style="font-size: 13px; font-weight: 600; color: #495057;">${d.uv_password}</div>
                        </div>
                    </div>
                </div>

                <!-- View Remarks Button -->
                <div style="display: flex; justify-content: center; gap: 12px; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                    <button type="button" id="btn-show-remarks" style="padding: 8px 16px; border-radius: 8px; background: #4f46e5; color: white; border: none; font-weight: 600; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#4338ca'" onmouseout="this.style.background='#4f46e5'">View Remarks</button>
                </div>
            </div>`;

        Swal.fire({
            title: `<span style="font-family:inherit; font-weight:800;">L1 Request Details</span>`,
            html: infoHtml,
            width: '600px',
            showCancelButton: false, // NO Cancel button
            confirmButtonText: 'Close',
            customClass: {
                confirmButton: 'swal-btn-close'
            },
            focusConfirm: false,
            didOpen: () => {
                const btnRemarks = document.getElementById('btn-show-remarks');
                if (btnRemarks) {
                    btnRemarks.onclick = () => {
                        window.showL1Details(d, 'remarks');
                    };
                }
            }
        });
    }
    else if (activeView === 'remarks') {
        const remarksHtml = buildL1RemarksHtml(d.remarks);

        const remarksHtmlContent = `
            <div style="text-align: left; padding: 0 5px; max-height: 60vh; overflow-y: auto; font-family: 'Inter', sans-serif;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                    <span style="font-size: 14px; color: #666; font-weight: 600;">Request: ${d.request_code}</span>
                    <span>${statusBadge}</span>
                </div>
                ${remarksHtml || '<div style="margin-top: 15px; font-style: italic; color: #888; text-align: center; font-size: 13px;">No remarks history/actions logged yet.</div>'}
            </div>`;

        Swal.fire({
            title: `<span style="font-family:inherit; font-weight:800;">Audit Remarks History</span>`,
            html: remarksHtmlContent,
            showCancelButton: false, // NO Cancel button
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
                window.showL1Details(d, 'details');
            }
        });
    }
};

function openL1DetailsModal(requestCode) {
    Swal.fire({
        title: `Fetching Request Details...`,
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    fetch(`/auth/l1-registration/requests/${requestCode}`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to extract details.");
            return res.json();
        })
        .then(data => {
            Swal.close();
            window.showL1Details(data, 'details');
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
}

function clearL1Form() {
    document.getElementById('l1RegistrationForm').reset();
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

    window.location.href = `/l1-registration/export-v2?ids=${ids.join(',')}`;
}

