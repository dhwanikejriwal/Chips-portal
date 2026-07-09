// app/static/js/dc_l1_registration.js

document.addEventListener("DOMContentLoaded", () => {
    // Show dashboard by default
    showL1Dashboard();
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
    const table = document.querySelector('.history-data-table');
    if (!table) return;
    
    const trs = table.getElementsByTagName('tr');
    
    for (let i = 1; i < trs.length; i++) { // skip header
        const tds = trs[i].getElementsByTagName('td');
        let matchFound = false;
        
        // Search by Request ID (index 1), Station ID (index 2), Model (index 3)
        if (tds.length > 0) {
            const reqId = tds[1].textContent || tds[1].innerText;
            const stationId = tds[2].textContent || tds[2].innerText;
            const model = tds[3].textContent || tds[3].innerText;
            
            if (reqId.toUpperCase().indexOf(filter) > -1 || 
                stationId.toUpperCase().indexOf(filter) > -1 || 
                model.toUpperCase().indexOf(filter) > -1) {
                matchFound = true;
            }
        }
        
        if (matchFound || trs[i].classList.contains('no-results')) {
            trs[i].style.display = "";
        } else {
            trs[i].style.display = "none";
        }
    }
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
            confirmButtonColor: '#2563eb',
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
            confirmButtonColor: '#2563eb',
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

        let statusStyle = "background: #fef3c7; color: #b45309;";
        if (data.status === 'REVIEWED') statusStyle = "background: #d1fae5; color: #065f46;";
        else if (data.status === 'REVERTED') statusStyle = "background: #fee2e2; color: #b91c1c;";
        else if (data.status === 'REAPPLIED') statusStyle = "background: #f3e8ff; color: #7e22ce;";

        const htmlContent = `
            <div style="text-align: left; font-size: 14px; color: #334155; font-family: sans-serif;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
                    <span style="font-weight: 600;">Request: ${data.request_code}</span>
                    <span style="${statusStyle} padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;">${data.status}</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>Station ID:</strong> ${data.station_id}</div>
                    <div><strong>Machine ID:</strong> ${data.machine_id}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>Operator Name:</strong> ${data.operator_name || 'N/A'}</div>
                    <div><strong>Operator ID:</strong> ${data.operator_id || 'N/A'}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>Model Type:</strong> ${data.model_type}</div>
                    <div><strong>Software Version:</strong> ${data.software_version}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>UV ID:</strong> ${data.uv_id}</div>
                    <div><strong>UV Password:</strong> ${data.uv_password}</div>
                </div>
                ${data.remarks && data.remarks.length > 0 ? `
                <div style="margin-top: 15px;">
                    <strong style="display: block; margin-bottom: 8px;">Remarks History:</strong>
                    <div style="max-height: 150px; overflow-y: auto; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;">
                        ${data.remarks.map(r => `
                            <div style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0;">
                                <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">
                                    <span style="font-weight: bold; color: ${r.user_role === 'dc' ? '#2563eb' : '#059669'};">${r.user_role === 'dc' ? 'District Coordinator' : 'CHIPS Admin'}</span> - ${r.timestamp}
                                </div>
                                <div style="font-size: 13px; color: #334155;">
                                    <strong style="color: #475569;">[${r.action}]</strong> ${r.remark}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
            </div>
        `;

        Swal.fire({
            title: `L1 Request Details`,
            html: htmlContent,
            width: '600px',
            confirmButtonText: 'Close',
            confirmButtonColor: '#475569'
        });
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
