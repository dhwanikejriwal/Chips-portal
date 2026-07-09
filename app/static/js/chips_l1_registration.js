// app/static/js/chips_l1_registration.js

function approveL1Request(requestCode) {
    Swal.fire({
        title: 'Approve Request?',
        text: 'Are you sure you want to approve this L1 request?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Approve',
        confirmButtonColor: '#10b981'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/auth/l1-registration/requests/${requestCode}/perform`, { method: 'POST' })
            .then(res => {
                if (!res.ok) throw new Error("Approval failed");
                return res.json();
            })
            .then(() => {
                Swal.fire('Approved!', 'Request has been successfully approved.', 'success').then(() => window.location.reload());
            })
            .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
}

function revertL1Request(requestCode) {
    Swal.fire({
        title: 'Revert L1 Request',
        input: 'textarea',
        inputPlaceholder: 'Enter reason for reverting...',
        showCancelButton: true,
        confirmButtonText: 'Revert',
        confirmButtonColor: '#ef4444',
        preConfirm: (reason) => {
            if (!reason || reason.trim() === '') {
                Swal.showValidationMessage('A revert reason is required.');
                return false;
            }
            return reason;
        }
    }).then((result) => {
        if (result.isConfirmed) {
            const payload = new URLSearchParams();
            payload.append('revert_reason', result.value.trim());
            
            fetch(`/auth/l1-registration/requests/${requestCode}/revert`, { method: 'POST', body: payload })
            .then(res => {
                if (!res.ok) throw new Error("Revert failed");
                return res.json();
            })
            .then(() => {
                Swal.fire('Reverted!', 'Request has been sent back to the DC.', 'success').then(() => window.location.reload());
            })
            .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
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
        if (data.status === 'APPROVED') statusStyle = "background: #d1fae5; color: #065f46;";
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
                    <div>
                        <strong>UV Password:</strong>
                        <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                            <input type="password" id="chips_uv_password_display" value="${data.uv_password}" readonly style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px 8px; font-size: 13px; color: #334155; width: 100%;" />
                            <button type="button" onclick="togglePasswordVisibility('chips_uv_password_display', this)" style="background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center; color: #64748b;">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                    <circle cx="12" cy="12" r="3"></circle>
                                </svg>
                            </button>
                        </div>
                    </div>
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
