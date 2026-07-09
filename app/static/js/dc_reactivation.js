/**
 * ============================================================================
 * 💾 DISTRICT COORDINATOR WORKSPACE ENGINE CORE - PIPELINE MANAGEMENT
 * ============================================================================
 */

let structuredOperatorList = [];
window.currentViewingOperators = [];

// 🟢 INITIALIZATION ADAPTER: SET LIMIT BOUNDARIES AND TAB PERSISTENCE
document.addEventListener("DOMContentLoaded", () => {
    window.switchReactivationView('dashboard');

    // Capture precise local calendar boundary configurations (YYYY-MM-DD)
    const todayIsoString = new Date().toISOString().split("T")[0];

    // 1. Enforce max boundaries on step 2 document training calendar
    const trainingDateInput = document.getElementById("doc_training_date");
    if (trainingDateInput) {
        trainingDateInput.max = todayIsoString;
    }

    // 2. Enforce max boundaries on step 1 single profile certification calendar
    const certDateInput = document.getElementById("op_cert_date");
    if (certDateInput) {
        certDateInput.max = todayIsoString;
    }
});

// 🔄 DYNAMIC VIEW PANEL ROUTER (Bound to global context)
window.switchReactivationView = function (targetPanel) {
    const dashboardView = document.getElementById('view-reactivation-dashboard-panel');
    const appView = document.getElementById('view-workspace-application-panel');
    const historyView = document.getElementById('view-workspace-history-panel');

    if (dashboardView) dashboardView.style.display = 'none';
    if (appView) appView.style.display = 'none';
    if (historyView) historyView.style.display = 'none';

    if (targetPanel === 'dashboard') {
        if (dashboardView) dashboardView.style.display = 'block';
        if (historyView) historyView.style.display = 'block';
        window.currentReapplyCode = null;
        const titleEl = document.querySelector('.container-title');
        if (titleEl) {
            titleEl.innerText = 'AADHAAR OPERATOR REACTIVATION';
        }
    } else if (targetPanel === 'app') {
        if (appView) appView.style.display = 'block';
    } else if (targetPanel === 'history') {
        if (historyView) historyView.style.display = 'block';
    }
};

// 🎛️ STEP-1 CACHE ENTRY VALIDATOR
function addOperatorRecordToExcelLog() {
    document.querySelectorAll('.error-msg').forEach(el => el.innerText = '');
    let hasValidationError = false;

    const fields = {
        role: document.getElementById('op_role').value.trim(),
        name: document.getElementById('op_name').value.trim(),
        reg: document.getElementById('op_reg').value.trim(),
        ea: document.getElementById('op_ea').value.trim(),
        user: document.getElementById('op_user').value.trim(),
        cert: document.getElementById('op_cert').value.trim(),
        mobile: document.getElementById('op_mobile').value.trim(),
        email: document.getElementById('op_email').value.trim(),
        aadhar: document.getElementById('op_aadhaar').value.trim(),
        certDate: document.getElementById('op_cert_date').value,
        model: document.getElementById('op_model').value.trim(),
        lmsId: document.getElementById('op_lms_id').value.trim(),
        remarks: document.getElementById('op_remarks').value.trim()
    };

    // Evaluate required entries
    for (const key in fields) {
        if (key === 'remarks') continue;
        if (!fields[key]) {
            const errNode = document.getElementById(`err_op_${key === 'aadhar' ? 'aadhaar' : key}`);
            if (errNode) errNode.innerText = 'This field is mandatory.';
            hasValidationError = true;
        }
    }

    if (fields.name && !/^[a-zA-Z\s]+$/.test(fields.name)) {
        document.getElementById('err_op_name').innerText = 'Name must only contain alphabets and spaces.';
        hasValidationError = true;
    }

    if (fields.mobile && !/^[6-9]\d{9}$/.test(fields.mobile)) {
        document.getElementById('err_op_mobile').innerText = 'Must be a valid 10-digit number starting with 6-9.';
        hasValidationError = true;
    }

    if (fields.aadhar && !/^\d{4}$/.test(fields.aadhar)) {
        document.getElementById('err_op_aadhaar').innerText = 'Must be exactly 4 numeric digits.';
        hasValidationError = true;
    }

    if (fields.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) {
        document.getElementById('err_op_email').innerText = 'Please enter a valid email format.';
        hasValidationError = true;
    }

    if (fields.certDate && new Date(fields.certDate) > new Date().setHours(23, 59, 59, 999)) {
        document.getElementById('err_op_cert_date').innerText = 'Certification date cannot be in the future.';
        hasValidationError = true;
    }

    if (hasValidationError) return;

    const verifiedRecord = {
        role: fields.role, name: fields.name, reg: fields.reg, ea: fields.ea,
        user: fields.user, cert: fields.cert, mobile: fields.mobile,
        email: fields.email, aadhar: fields.aadhar, certDate: fields.certDate,
        remarks: fields.remarks, model: fields.model, lmsId: fields.lmsId
    };

    structuredOperatorList.push(verifiedRecord);
    renderOperatorSpreadsheetRows();
    clearFormInputs();
}

// 📊 SPREADSHEET ROW LAYOUT BUILDER
function renderOperatorSpreadsheetRows() {
    const tbody = document.getElementById('excel-log-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (structuredOperatorList.length === 0) {
        tbody.innerHTML = `
            <tr id="empty-state-row">
                <td colspan="15" style="text-align: center; color: #94a3b8; padding: 30px; font-style: italic;">
                    No operator entries added to the tracking index matrix yet. Use the data form container inputs above.
                </td>
            </tr>`;
        document.getElementById('next-step-trigger-btn').disabled = true;
        return;
    }

    structuredOperatorList.forEach((op, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${index + 1}</strong></td>
            <td>${escapeHtmlString(op.role)}</td>
            <td><strong>${escapeHtmlString(op.name)}</strong></td>
            <td>${escapeHtmlString(op.reg)}</td>
            <td>${escapeHtmlString(op.ea)}</td>
            <td>${escapeHtmlString(op.user)}</td>
            <td>${escapeHtmlString(op.cert)}</td>
            <td>${escapeHtmlString(op.lmsId)}</td>
            <td>${escapeHtmlString(op.mobile)}</td>
            <td>${escapeHtmlString(op.email)}</td>
            <td>XXXX-XXXX-${escapeHtmlString(op.aadhar)}</td>
            <td>${escapeHtmlString(op.certDate)}</td>
            <td>${escapeHtmlString(op.remarks) || 'N/A'}</td>
            <td>${escapeHtmlString(op.model)}</td>
            <td style="text-align: center;">
                <button type="button" class="btn-primary-sm" onclick="editOperatorInStateArray(${index})" style="background-color: #f59e0b; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; margin-right: 5px; margin-bottom: 4px;">Edit</button>
                <button type="button" class="btn-danger-sm" onclick="removeOperatorFromStateArray(${index})">Remove</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('next-step-trigger-btn').disabled = false;
}

function removeOperatorFromStateArray(index) {
    structuredOperatorList.splice(index, 1);
    renderOperatorSpreadsheetRows();
}

function editOperatorInStateArray(index) {
    const op = structuredOperatorList[index];

    // Populate form fields
    if (document.getElementById('op_role')) document.getElementById('op_role').value = op.role || 'Operator';
    if (document.getElementById('op_name')) document.getElementById('op_name').value = op.name || '';
    if (document.getElementById('op_reg')) document.getElementById('op_reg').value = op.reg || '';
    if (document.getElementById('op_ea')) document.getElementById('op_ea').value = op.ea || '';
    if (document.getElementById('op_user')) document.getElementById('op_user').value = op.user || '';
    if (document.getElementById('op_cert')) document.getElementById('op_cert').value = op.cert || '';
    if (document.getElementById('op_mobile')) document.getElementById('op_mobile').value = op.mobile || '';
    if (document.getElementById('op_email')) document.getElementById('op_email').value = op.email || '';
    if (document.getElementById('op_aadhaar')) document.getElementById('op_aadhaar').value = op.aadhar || '';
    if (document.getElementById('op_cert_date')) document.getElementById('op_cert_date').value = op.certDate || '';
    if (document.getElementById('op_model')) document.getElementById('op_model').value = op.model || '';
    if (document.getElementById('op_lms_id')) document.getElementById('op_lms_id').value = op.lmsId || '';
    if (document.getElementById('op_remarks')) document.getElementById('op_remarks').value = op.remarks || '';

    // Remove from array and re-render
    structuredOperatorList.splice(index, 1);
    renderOperatorSpreadsheetRows();

    // Scroll to top to focus on form
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// 🧙‍♂️ WIZARD PAGE SWITCH PANEL CONTROL
function navigateWizardStep(stepTarget) {
    const s1Form = document.getElementById('section-operator-form-view');
    const s2Docs = document.getElementById('section-documents-upload-view');
    const node2 = document.getElementById('node-step-2');

    if (stepTarget === 2) {
        if (s1Form) s1Form.style.display = 'none';
        if (s2Docs) s2Docs.style.display = 'block';
        if (node2) node2.classList.add('active');
    } else {
        if (s1Form) s1Form.style.display = 'block';
        if (s2Docs) s2Docs.style.display = 'none';
        if (node2) node2.classList.remove('active');
    }
}

// 🚀 TRANSACTION ASYNC SUBMIT HANDLER
function handleFormSubmissionPipeline(event) {
    event.preventDefault();

    if (structuredOperatorList.length === 0) {
        Swal.fire({ title: 'Submission Refused', text: 'Staged operator spreadsheet matrix cannot be empty.', icon: 'error' });
        return;
    }

    const dateField = document.getElementById('doc_training_date');
    if (!dateField || !dateField.value) {
        Swal.fire({ title: 'Validation Error', text: 'Training completion date is required.', icon: 'warning' });
        return;
    }

    const formElement = document.getElementById('reactivationForm');
    const formData = new FormData(formElement);
    formData.append('manual_operators', JSON.stringify(structuredOperatorList));

    if (window.currentReapplyCode) {
        formData.append('reapply_request_code', window.currentReapplyCode);
    }

    // Dynamic destination URL resolution preventing deployment proxy collisions
    const routingTargetUrl = '/auth/dc/submit';

    fetch(routingTargetUrl, { method: 'POST', body: formData })
        .then(res => {
            return res.json().then(data => {
                if (!res.ok) throw new Error(data.error || "Server transaction processing failure.");
                return data;
            });
        })
        .then(data => {
            Swal.fire({ title: 'Submitted', text: 'Reactivation request sent to CHIPS successfully.', icon: 'success' }).then(() => {
                window.location.reload();
            });
        })
        .catch(err => {
            Swal.close();
            Swal.fire({ title: 'Submission Error', text: err.message, icon: 'error' });
        });
}

// 👁️ BATCH POPUP OPERATOR ROWS LOOKUP RENDERING
window.openHistoricalOperatorsModal = function (requestCode) {
    Swal.fire({
        title: `Operators Detail N/A Request ${requestCode}`,
        width: '750px',
        html: `
            <div style="text-align: left; margin-bottom: 12px; font-size: 13px; color: #64748b; font-family: sans-serif;">
                Reviewing individual operator tracking records associated with this request batch.
            </div>
            <div style="overflow-x: auto; width: 100%; border: 1px solid #e2e8f0; border-radius: 6px; max-height: 350px;">
                <table style="width: 100%; min-width: 600px; border-collapse: collapse; text-align: left; font-size: 13px; font-family: sans-serif;">
                    <thead>
                        <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; color: #475569;">
                            <th style="padding: 10px; width: 10%; text-align: center; font-weight:600;">S.No</th>
                            <th style="padding: 10px; width: 45%; padding-left: 15px; font-weight:600;">Operator Name</th>
                            <th style="padding: 10px; width: 25%; text-align: center; font-weight:600;">Status</th>
                            <th style="padding: 10px; width: 20%; text-align: center; font-weight:600;">View Profile</th>
                        </tr>
                    </thead>
                    <tbody id="modal-history-rows-body">
                        <tr><td colspan="4" style="text-align: center; padding: 20px; color: #94a3b8;">Fetching records...</td></tr>
                    </tbody>
                </table>
            </div>
            <div id="modal-timeline-container" style="margin-top: 25px; text-align: left;"></div>`,
        confirmButtonText: 'Close Window',
        confirmButtonColor: '#475569'
    });

    fetch(`http://127.0.0.1:8000/reactivation/operators/${requestCode}`)
        .then(res => {
            if (!res.ok) throw new Error('Server returned an error');
            return res.json();
        })
        .then(payload => {
            const modalBody = document.getElementById('modal-history-rows-body');
            if (!modalBody) return;
            modalBody.innerHTML = '';

            const operators = payload.operators || [];
            const timelineLogs = payload.timeline_logs || [];

            if (!operators || !Array.isArray(operators) || operators.length === 0) {
                modalBody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:20px; color:#94a3b8;">No records found.</td></tr>`;
                return;
            }

            window.currentViewingOperators = operators;
            window.currentViewingRequestCode = requestCode;

            const timelineContainer = document.getElementById('modal-timeline-container');
            if (timelineContainer) {
                if (timelineLogs && timelineLogs.length > 0) {
                    timelineContainer.innerHTML = `
                    <h4 style="font-size: 15px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 15px;">Reactivation Log Timeline</h4>
                    <div style="display: flex; flex-direction: column; gap: 12px; max-height: 250px; overflow-y: auto; padding-right: 10px;">
                        ${timelineLogs.map(log => {
                        const dateObj = new Date(log.timestamp.replace(' ', 'T'));
                        const formattedTime = dateObj.toLocaleDateString('en-GB') + ' ' + dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                        const isDC = log.sender_role === 'DC';
                        return `
                                <div style="background: ${isDC ? '#f8fafc' : '#eff6ff'}; border-left: 4px solid ${isDC ? '#94a3b8' : '#3b82f6'}; padding: 12px 16px; border-radius: 6px; display: flex; flex-direction: column; gap: 4px; text-align: left;">
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <span style="font-weight: 700; font-size: 12px; color: ${isDC ? '#475569' : '#1d4ed8'};">${isDC ? 'DC Panel' : 'CHiPS Admin'}</span>
                                        <span style="font-size: 11px; color: #64748b; font-weight: 600;">${formattedTime}</span>
                                    </div>
                                    <div style="font-size: 13px; color: #334155; margin-top: 4px;">
                                        ${escapeHtmlString(log.message)}
                                    </div>
                                </div>
                            `;
                    }).join('')}
                    </div>
                `;
                } else {
                    timelineContainer.innerHTML = `
                    <h4 style="font-size: 15px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 15px;">Reactivation Log Timeline</h4>
                    <div style="text-align: center; color: #94a3b8; font-size: 13px; padding: 20px;">No timeline logs available for this batch.</div>
                `;
                }
            }

            operators.forEach((op, idx) => {
                const row = document.createElement('tr');
                row.style.borderBottom = "1px solid #f1f5f9";

                let statusStyle = "color: #b45309; font-weight: 700; background: #fef3c7; padding: 2px 8px; border-radius: 4px; font-size: 11px;";
                const normalizedStatus = String(op.status || 'PENDING').toLowerCase();

                if (normalizedStatus === 'sent to uidai' || normalizedStatus === 'sent_to_uidai') {
                    statusStyle = "color: #0369a1; font-weight: 700; background: #e0f2fe; padding: 2px 8px; border-radius: 4px; font-size: 11px;";
                } else if (normalizedStatus === 'active' || normalizedStatus === 'activated') {
                    statusStyle = "color: #065f46; font-weight: 700; background: #d1fae5; padding: 2px 8px; border-radius: 4px; font-size: 11px;";
                } else if (normalizedStatus === 'reverted' || normalizedStatus === 'revert back') {
                    statusStyle = "color: #991b1b; font-weight: 700; background: #fee2e2; padding: 2px 8px; border-radius: 4px; font-size: 11px;";
                }

                row.innerHTML = `
                <td style="padding: 10px; text-align: center; color: #64748b;">${idx + 1}</td>
                <td style="padding: 10px; padding-left: 15px; color: #1e293b;"><strong>${escapeHtmlString(op.operator_name)}</strong></td>
                <td style="padding: 10px; text-align: center;"><span style="${statusStyle}">${String(op.status).toUpperCase()}</span></td>
                <td style="padding: 10px; text-align: center;">
                    <button type="button" class="btn btn-sm" 
                            style="background-color: #4b5563; color: white; border: none; padding: 4px 14px; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight:600;"
                            onclick="openIndividualOperatorDetailCard(${idx})">
                        Detail
                    </button>
                </td>
            `;
                modalBody.appendChild(row);
            });
        })
        .catch((err) => {
            const modalBody = document.getElementById('modal-history-rows-body');
            if (modalBody) modalBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#dc2626; padding:20px;">Error: ${err.message || 'Failed to fetch operator data.'}</td></tr>`;
        });
}

window.reapplyReactivatedBatch = function (requestCode, trainingDate) {
    window.currentReapplyCode = requestCode;
    const titleEl = document.querySelector('.container-title');
    if (titleEl) {
        titleEl.innerText = `Reapplying Batch: ${requestCode}`;
    }

    if (trainingDate) {
        document.getElementById('doc_training_date').value = trainingDate;
    }

    Swal.fire({
        title: 'Loading Previous Data...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    fetch(`http://127.0.0.1:8000/reactivation/operators/${requestCode}`)
        .then(res => {
            if (!res.ok) throw new Error('Failed to load previous operators');
            return res.json();
        })
        .then(payload => {
            Swal.close();
            structuredOperatorList = [];
            const operators = payload.operators || [];
            operators.forEach(op => {
                structuredOperatorList.push({
                    name: op.operator_name || '',
                    mobile: op.operator_mobile || '',
                    role: op.role || 'Operator',
                    email: op.email_id || '',
                    reg: op.registrar_code || '986',
                    ea: op.ea_code || '',
                    user: op.user_code || '',
                    model: op.model_type || '',
                    lmsId: op.lms_certificate_id || '',
                    cert: op.certificate_number || '',
                    certDate: op.certification_date || '',
                    remarks: op.remarks || ''
                });
            });
            renderOperatorSpreadsheetRows();
            window.switchReactivationView('app');
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
}

// 💳 DETAILS MODAL MAPPING INTERFACE CARD BUILDER
window.openIndividualOperatorDetailCard = function (arrayIndex) {
    const op = window.currentViewingOperators[arrayIndex];
    if (!op) {
        console.error("Index target context maps outside viewing operator bounds matrix.");
        return;
    }

    const displayStatus = (op.status || 'PENDING').toUpperCase();
    let badgeStyle = 'background: #e2e8f0; color: #475569;';
    if (displayStatus === 'ACTIVE' || displayStatus === 'ACTIVATED') badgeStyle = 'background: #d1fae5; color: #065f46;';
    else if (displayStatus === 'REVERTED' || displayStatus === 'REVERT BACK') badgeStyle = 'background: #fee2e2; color: #991b1b;';
    else if (displayStatus === 'SENT TO UIDAI' || displayStatus === 'SENT_TO_UIDAI') badgeStyle = 'background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;';
    else if (displayStatus === 'REAPPLIED') badgeStyle = 'background: #ede9fe; color: #6d28d9; border: 1px solid #ddd6fe;';

    const fullName = op.operator_name || op.name || 'N/A';
    const roleProfile = op.role || 'Operator';
    const mobileNumber = op.operator_mobile || op.mobile || 'N/A';
    const emailAddress = op.email_id || op.email || 'N/A';
    const registrarCode = op.registrar_code || '986';
    const eaCode = op.ea_code || 'N/A';
    const userCode = op.user_code || 'N/A';
    const modelType = op.model_type || 'N/A';
    const lmsCertId = op.lms_certificate_id || 'N/A';
    const nseitCertNo = op.certificate_number || 'N/A';
    const certificationDate = op.certification_date || 'N/A';
    const explicitRemarks = op.remarks || 'N/A';

    Swal.fire({
        title: 'Submitted Operator Details',
        width: '560px',
        html: `
            <div style="font-family: sans-serif; text-align: left; color: #334155; font-size: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;">
                    <span style="font-size:12px; color:#64748b;">Record Identity Mapping</span>
                    <span style="${badgeStyle} padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;">${displayStatus}</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>Full Name:</strong> ${escapeHtmlString(fullName)}</div>
                    <div><strong>Role Profile:</strong> ${escapeHtmlString(roleProfile)}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>Mobile Number:</strong> ${escapeHtmlString(mobileNumber)}</div>
                    <div><strong>Primary Email ID:</strong> ${escapeHtmlString(emailAddress)}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>Registrar Code:</strong> ${escapeHtmlString(registrarCode)}</div>
                    <div><strong>EA Code:</strong> ${escapeHtmlString(eaCode)}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 12px;">
                    <div><strong>User Code:</strong> ${escapeHtmlString(userCode)}</div>
                    <div><strong>Model Type:</strong> ${escapeHtmlString(modelType)}</div>
                </div>
                <div style="border-top: 1px dashed #cbd5e1; margin-top: 15px; padding-top: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 15px;">
                    <div><strong>LMS Certificate ID:</strong> <span style="font-family: monospace; font-weight: 700; color: #2563eb;">${escapeHtmlString(lmsCertId)}</span></div>
                    <div><strong>NSEIT Certificate #:</strong> ${escapeHtmlString(nseitCertNo)}</div>
                </div>
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 12px;">
                    <div style="margin-bottom: 4px;"><strong>Certification Date:</strong> ${escapeHtmlString(certificationDate)}</div>
                    <div style="margin-bottom: 4px;"><strong>Remarks:</strong> ${escapeHtmlString(explicitRemarks)}</div>
                    ${op.reject_reason ? `<div style="margin-top: 6px; color:#b91c1c;"><strong>Revert Reason:</strong> ${escapeHtmlString(op.reject_reason)}</div>` : ''}
                </div>
                
                <div style="margin-top: 20px; display: flex; justify-content: flex-end; gap: 10px;">
                    <button type="button" class="btn btn-secondary" style="padding: 8px 16px; border-radius: 4px; background: #64748b; color: white; border: none; cursor: pointer; font-weight: 600;" onclick="Swal.close()">Back to List</button>
                    ${(displayStatus === 'REVERTED' || displayStatus === 'REVERT BACK') ?
                `<button type="button" class="btn btn-warning" style="padding: 8px 16px; border-radius: 4px; background: #f59e0b; color: white; border: none; cursor: pointer; font-weight: 600;" onclick="Swal.close(); openIndividualOperatorEditForm(${arrayIndex})">Quick Edit</button>
                         <button type="button" class="btn btn-warning" style="padding: 8px 16px; border-radius: 4px; background: #0284c7; color: white; border: none; cursor: pointer; font-weight: 600;" onclick="Swal.close(); reapplyReactivatedBatch('${window.currentViewingRequestCode}')">Reapply Full Batch</button>`
                : ''}
                </div>
            </div>`,
        showConfirmButton: false
    });
};

// 🧼 WORKSPACE INPUT FIELD CLEANSER
function clearFormInputs() {
    document.getElementById('op_role').value = '';
    document.getElementById('op_name').value = '';
    document.getElementById('op_reg').value = '986';
    document.getElementById('op_ea').value = '';
    document.getElementById('op_user').value = '';
    document.getElementById('op_cert').value = '';
    document.getElementById('op_mobile').value = '';
    document.getElementById('op_email').value = '';
    document.getElementById('op_aadhaar').value = '';
    document.getElementById('op_cert_date').value = '';
    document.getElementById('op_remarks').value = '';
    document.getElementById('op_model').value = '';
    document.getElementById('op_lms_id').value = '';
    document.querySelectorAll('.error-msg').forEach(el => el.innerText = '');
}

// 🛡️ SECURITY STRING ESCAPER
function escapeHtmlString(text) {
    if (!text) return '';
    return text.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// 🔍 DATA INDEX FILTERS PROCESSING STREAM
// 🔍 MAIN VIEW TABS (BATCHES VS ACTIVATED)
function switchMainView(viewType, btnElement) {
    const buttons = document.querySelectorAll('.main-view-tab');
    buttons.forEach(btn => {
        btn.classList.remove('active-view');
        btn.style.color = '#64748b';
        btn.style.borderBottom = '3px solid transparent';
    });

    btnElement.classList.add('active-view');
    btnElement.style.color = '#2563eb';
    btnElement.style.borderBottom = '3px solid #2563eb';

    if (viewType === 'batches') {
        document.getElementById('view-batches-container').style.display = 'block';
        document.getElementById('view-activated-container').style.display = 'none';
    } else {
        document.getElementById('view-batches-container').style.display = 'none';
        document.getElementById('view-activated-container').style.display = 'block';
    }
}

function filterFlatActivatedOperators() {
    const searchInput = document.getElementById('flat-op-search');
    const searchText = searchInput ? searchInput.value.toLowerCase().trim() : "";

    const rows = document.querySelectorAll('.flat-op-row');
    rows.forEach(row => {
        const opName = row.getAttribute('data-name') || "";
        if (opName.includes(searchText)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

// 🔍 DISTRICT HISTORY DATA GRID CLIENT-SIDE FILTER PIPELINE
function applyHistoryPanelFiltersPipeline() {
    // 1. Gather all input conditions safely
    const searchIdInput = document.getElementById("filter-search-id");
    const statusInput = document.getElementById("filter-status");
    const dateFromInput = document.getElementById("filter-date-from");
    const dateToInput = document.getElementById("filter-date-to");
    const globalOpSearchInput = document.getElementById("global-op-search");

    const searchIdValue = searchIdInput ? searchIdInput.value.trim().toUpperCase() : "";
    const statusValue = statusInput ? statusInput.value : "ALL";
    const dateFromValue = dateFromInput ? dateFromInput.value : "";
    const dateToValue = dateToInput ? dateToInput.value : "";
    const globalOpSearchValue = globalOpSearchInput ? globalOpSearchInput.value.trim().toLowerCase() : "";

    const rows = document.querySelectorAll(".history-data-row");
    let matchCount = 0;

    window.currentReapplyCode = null;

    rows.forEach(row => {
        const rowId = row.getAttribute("data-request-id") || "";
        let rowStatus = row.getAttribute("data-status") || "";
        const rowTrainingDateStr = row.getAttribute("data-training-date") || "";

        rowStatus = rowStatus.toUpperCase().replace(" ", "_").trim();
        const cleanStatusFilter = statusValue.toUpperCase().replace(" ", "_").trim();

        const matchesId = !searchIdValue || rowId.includes(searchIdValue);
        const matchesStatus = (statusValue === "ALL") || (rowStatus === cleanStatusFilter);

        let matchesDateRange = true;
        if (dateFromValue || dateToValue) {
            if (rowTrainingDateStr) {
                const trainingTime = new Date(rowTrainingDateStr).getTime();
                if (dateFromValue && trainingTime < new Date(dateFromValue).getTime()) {
                    matchesDateRange = false;
                }
                if (dateToValue && trainingTime > new Date(dateToValue).getTime()) {
                    matchesDateRange = false;
                }
            } else {
                matchesDateRange = false;
            }
        }

        // If batch-level filters match, evaluate individual operators inside the card
        if (matchesId && matchesStatus && matchesDateRange) {
            let visibleOpsCount = 0;
            const opRows = row.querySelectorAll('.op-row-item');

            opRows.forEach(opRow => {
                const opName = opRow.getAttribute('data-name') || "";

                const matchesOpSearch = !globalOpSearchValue || opName.includes(globalOpSearchValue);

                if (matchesOpSearch) {
                    opRow.style.display = "flex";
                    visibleOpsCount++;
                } else {
                    opRow.style.display = "none";
                }
            });

            // Show card if it has matching operators, or if it has none natively but no operator filters are active
            if (visibleOpsCount > 0 || (opRows.length === 0 && !globalOpSearchValue)) {
                row.style.display = "";
                matchCount++;
            } else {
                row.style.display = "none";
            }
        } else {
            row.style.display = "none";
        }
    });

    // Handle empty state views gracefully
    const noMatchFallback = document.getElementById("history-no-match-fallback");
    const standardEmptyState = document.getElementById("history-fallback-empty-row");

    if (noMatchFallback) {
        noMatchFallback.style.display = (matchCount === 0 && rows.length > 0) ? "" : "none";
    }
    if (standardEmptyState) {
        standardEmptyState.style.display = (rows.length === 0) ? "" : "none";
    }
}

function resetHistoryPanelFilters() {
    document.getElementById("filter-search-id").value = "";
    document.getElementById("filter-status").value = "ALL";
    document.getElementById("filter-date-from").value = "";
    document.getElementById("filter-date-to").value = "";

    const globalOpSearch = document.getElementById("global-op-search");
    if (globalOpSearch) globalOpSearch.value = "";

    // reset tabs? Or just leave the view where it is.
    applyHistoryPanelFiltersPipeline();
}

window.openIndividualOperatorEditForm = function (arrayIndex) {
    const op = window.currentViewingOperators[arrayIndex];
    if (!op) return;

    Swal.fire({
        title: 'Quick Edit Operator',
        width: '600px',
        html: `
            <div style="text-align: left; font-size: 13px; font-family: sans-serif; color: #334155;">
                <p style="margin-top: 0; margin-bottom: 15px; color: #64748b;">Update the operator details and reapply immediately.</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">Name as per Aadhaar <span style="color:#ef4444;">*</span></label>
                        <input type="text" id="edit_op_name" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.operator_name || '')}">
                    </div>
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">Mobile Number <span style="color:#ef4444;">*</span></label>
                        <input type="text" id="edit_op_mobile" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.operator_mobile || '')}">
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">Primary Email ID</label>
                        <input type="email" id="edit_op_email" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.email_id || '')}">
                    </div>
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">Model Type</label>
                        <select id="edit_op_model" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;">
                            <option value="ECMP" ${op.model_type === 'ECMP' ? 'selected' : ''}>ECMP</option>
                            <option value="UCL" ${op.model_type === 'UCL' ? 'selected' : ''}>UCL</option>
                            <option value="VLE" ${op.model_type === 'VLE' ? 'selected' : ''}>VLE</option>
                            <option value="Inhouse" ${op.model_type === 'Inhouse' ? 'selected' : ''}>Inhouse</option>
                        </select>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">LMS Certificate ID</label>
                        <input type="text" id="edit_op_lms" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.lms_certificate_id || '')}">
                    </div>
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">NSEIT Certificate #</label>
                        <input type="text" id="edit_op_cert" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.certificate_number || '')}">
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">Role</label>
                        <input type="text" id="edit_op_role" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.role || '')}">
                    </div>
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">EA Code</label>
                        <input type="text" id="edit_op_ea" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.ea_code || '')}">
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                    <div>
                        <label style="display:block; margin-bottom: 5px; font-weight: 600;">User Code</label>
                        <input type="text" id="edit_op_user_code" class="form-control-input" style="width:100%; box-sizing:border-box; height:36px; padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px;" value="${escapeHtmlString(op.user_code || '')}">
                    </div>
                    <div></div>
                </div>
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Submit Reapplication',
        confirmButtonColor: '#f59e0b',
        cancelButtonColor: '#64748b',
        preConfirm: () => {
            const name = document.getElementById('edit_op_name').value.trim();
            const mobile = document.getElementById('edit_op_mobile').value.trim();
            const email = document.getElementById('edit_op_email').value.trim();
            const model = document.getElementById('edit_op_model').value;
            const lms = document.getElementById('edit_op_lms').value.trim();
            const cert = document.getElementById('edit_op_cert').value.trim();

            const role = document.getElementById('edit_op_role').value.trim();
            const ea = document.getElementById('edit_op_ea').value.trim();
            const userCode = document.getElementById('edit_op_user_code').value.trim();

            if (!name || !mobile) {
                Swal.showValidationMessage('Name and Mobile Number are required fields.');
                return false;
            }
            return { id: op.id, name, mobile, email, model, lms, cert, role, ea, userCode };
        }
    }).then(result => {
        if (result.isConfirmed) {
            submitOperatorReapplication(result.value);
        }
    });
};

window.submitOperatorReapplication = function (data) {
    Swal.fire({
        title: 'Reapplying Operator...',
        text: 'Please wait while the records are updated.',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    const formData = new FormData();
    formData.append('operator_name', data.name);
    formData.append('operator_mobile', data.mobile);
    formData.append('email_id', data.email);
    formData.append('model_type', data.model);
    formData.append('lms_certificate_id', data.lms);
    formData.append('certificate_number', data.cert);
    formData.append('role', data.role);
    formData.append('ea_code', data.ea);
    formData.append('user_code', data.userCode);

    fetch(`http://127.0.0.1:8000/reactivation/operator/${data.id}/update_reapply`, {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                Swal.fire('Success', 'Operator reapplied successfully!', 'success').then(() => {
                    window.location.reload();
                });
            } else {
                throw new Error(data.error || 'Failed to update operator details.');
            }
        })
        .catch(err => {
            Swal.close();
            Swal.fire('Error', err.message, 'error');
        });
};
