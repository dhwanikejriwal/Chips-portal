/**
 * ============================================================================
 * 💾 DISTRICT COORDINATOR WORKSPACE ENGINE CORE - PIPELINE MANAGEMENT
 * ============================================================================
 */

let structuredOperatorList = [];
window.structuredOperatorList = structuredOperatorList;
window.currentViewingOperators = [];

window.escapeHtmlString = function (text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};

// 🟢 INITIALIZATION ADAPTER: SET LIMIT BOUNDARIES AND TAB PERSISTENCE
document.addEventListener("DOMContentLoaded", () => {
    window.switchReactivationView('dashboard', true);

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
    // 3. Reset filters to defaults on page load
    const urlParams = new URLSearchParams(window.location.search);
    const qStatus = urlParams.get("status");

    const searchOperatorInput = document.getElementById("filter-search-operator");
    if (searchOperatorInput) searchOperatorInput.value = "";

    const statusInput = document.getElementById("filter-status");
    if (statusInput) statusInput.value = "ALL";

    const datePeriodInput = document.getElementById("filter-date-period");
    if (datePeriodInput) datePeriodInput.value = (urlParams.has("from_notif") || qStatus) ? "all" : "month";

    if (qStatus) {
        const st = qStatus.toUpperCase().trim();
        const statusInput = document.getElementById("filter-status");
        if (statusInput) {
            if (st === "REVERTED_REJECTED" || st === "REVERTED" || st === "REVERTED_CHIPS" || st === "REVERTED_BY_CHIPS") {
                statusInput.value = "REVERTED";
            } else if (st === "REJECTED") {
                statusInput.value = "REJECTED";
            } else if (st === "PENDING") {
                statusInput.value = "PENDING";
            } else if (st === "APPROVED") {
                statusInput.value = "APPROVED";
            } else if (st === "SENT_TO_UIDAI" || st === "UIDAI") {
                statusInput.value = "SENT_TO_UIDAI";
            }
        }
    }

    // 4. Initialize counts by running the filter pipeline
    applyHistoryPanelFiltersPipeline();

    // 🌟 5. Instant Input Verification and Database Duplicate Lookups
    const mobileInput = document.getElementById("op_mobile");
    if (mobileInput) {
        mobileInput.addEventListener("input", async () => {
            const val = mobileInput.value.trim();
            const errNode = document.getElementById("err_op_mobile");
            if (!errNode) return;
            errNode.innerText = "";

            if (val.length === 10) {
                if (!/^[6-9]\d{9}$/.test(val)) {
                    errNode.innerText = "Must be a valid 10-digit number starting with 6-9.";
                    return;
                }
                const opId = document.getElementById('editing_op_id') ? document.getElementById('editing_op_id').value : '';
                // Check local duplicate
                const isLocalDup = structuredOperatorList.some(op => op.mobile === val && op.id !== opId);
                if (isLocalDup) {
                    errNode.innerText = "This mobile number is already added to this batch.";
                    return;
                }
                // Check DB duplicate
                try {
                    const res = await fetch(`/auth/dc/reactivation/check-duplicate?mobile=${val}&exclude_id=${opId}`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data.exists) {
                            errNode.innerText = data.message;
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            }
        });
    }

    const emailInput = document.getElementById("op_email");
    if (emailInput) {
        emailInput.addEventListener("change", async () => {
            const val = emailInput.value.trim();
            const errNode = document.getElementById("err_op_email");
            if (!errNode) return;
            errNode.innerText = "";

            if (val.length > 0) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(val)) {
                    errNode.innerText = "Please enter a valid email format.";
                    return;
                }
                const opId = document.getElementById('editing_op_id') ? document.getElementById('editing_op_id').value : '';
                // Check local duplicate
                const isLocalDup = structuredOperatorList.some(op => op.email === val && op.id !== opId);
                if (isLocalDup) {
                    errNode.innerText = "This email address is already added to this batch.";
                    return;
                }
                // Check DB duplicate
                try {
                    const res = await fetch(`/auth/dc/reactivation/check-duplicate?email=${encodeURIComponent(val)}&exclude_id=${opId}`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data.exists) {
                            errNode.innerText = data.message;
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            }
        });
    }

    if (certDateInput) {
        certDateInput.addEventListener("change", () => {
            const val = certDateInput.value;
            const errNode = document.getElementById("err_op_cert_date");
            if (!errNode) return;
            errNode.innerText = "";

            if (val) {
                const todayD = new Date();
                const yyyy = todayD.getFullYear();
                const mm = String(todayD.getMonth() + 1).padStart(2, '0');
                const dd = String(todayD.getDate()).padStart(2, '0');
                const todayStr = `${yyyy}-${mm}-${dd}`;

                if (val > todayStr) {
                    errNode.innerText = "Certification date cannot be in the future.";
                } else {
                    const certD = new Date(val);
                    const threeYearsAgo = new Date();
                    threeYearsAgo.setFullYear(todayD.getFullYear() - 3);
                    if (certD < threeYearsAgo) {
                        errNode.innerText = "NSEIT Certification Date must not be more than 3 years old.";
                    }
                }
            }
        });
    }
});

// 🔄 DYNAMIC VIEW PANEL ROUTER (Bound to global context)
window.switchReactivationView = function (targetPanel, shouldReset = false) {
    const dashboardView = document.getElementById('view-reactivation-dashboard-panel');
    const appView = document.getElementById('view-workspace-application-panel');
    const historyView = document.getElementById('view-workspace-history-panel');

    if (dashboardView) dashboardView.style.display = 'none';
    if (appView) appView.style.display = 'none';
    if (historyView) historyView.style.display = 'none';

    if (targetPanel === 'dashboard') {
        if (dashboardView) dashboardView.style.display = 'block';
        if (historyView) historyView.style.display = 'block';
        // Reset the form when returning to dashboard ONLY if shouldReset is true
        if (shouldReset) {
            window.currentReapplyCode = null;
            const noticeEl = document.getElementById('reapply-file-notice');
            if (noticeEl) noticeEl.style.display = 'none';
            document.querySelectorAll('.doc-required-star').forEach(star => {
                star.style.display = 'inline';
            });
            document.querySelectorAll('.prev-doc-indicator').forEach(el => {
                el.style.display = 'none';
                el.innerText = '';
            });
            const titleEl = document.getElementById('reactivation-form-title');
            if (titleEl) {
                titleEl.innerText = 'Submit Operator Reactivation Request';
            }
            const remarkEl = document.getElementById('reapply-remark-section');
            if (remarkEl) remarkEl.style.display = 'none';
            const remarksField = document.getElementById('reapply_remarks_field');
            if (remarksField) remarksField.value = '';

            window.isReapplyBatchReverted = false;
            const p1BatchContainer = document.getElementById('batch-revert-reason-container-p1');
            if (p1BatchContainer) p1BatchContainer.style.display = 'none';
            const p2BatchContainer = document.getElementById('batch-revert-reason-container-p2');
            if (p2BatchContainer) p2BatchContainer.style.display = 'none';
            if (typeof resetEntireNewRequestForm === 'function') {
                resetEntireNewRequestForm();
            } else {
                clearFormInputs();
                structuredOperatorList = [];
                window.structuredOperatorList = structuredOperatorList;
                renderOperatorSpreadsheetRows();
                ['training_photo', 'nodal_letter', 'om_letter', 'attendance_list', 'training_date'].forEach(name => {
                    const el = document.getElementsByName(name)[0];
                    if (el) el.value = '';
                });
                const s1Form = document.getElementById('section-operator-form-view');
                const s2Docs = document.getElementById('section-documents-upload-view');
                if (s1Form) s1Form.style.display = 'block';
                if (s2Docs) s2Docs.style.display = 'none';
            }
            window.currentReapplyCode = null;
        }
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
window.addOperatorRecordToExcelLog = async function () {
    document.querySelectorAll('.error-msg').forEach(el => el.innerText = '');
    let hasValidationError = false;

    const opId = document.getElementById('editing_op_id') ? document.getElementById('editing_op_id').value : '';

    const fields = {
        role: document.getElementById('op_role').value.trim(),
        name: document.getElementById('op_name').value.trim(),
        reg: document.getElementById('op_reg').value.trim(),
        ea: document.getElementById('op_ea').value.trim(),
        user: document.getElementById('user_code').value.trim(),
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
    const keyToErrorIdMap = {
        role: 'role',
        name: 'name',
        reg: 'reg',
        ea: 'ea',
        user: 'user',
        cert: 'cert',
        mobile: 'mobile',
        email: 'email',
        aadhar: 'aadhaar',
        certDate: 'cert_date',
        model: 'model',
        lmsId: 'lms_id'
    };
    for (const key in fields) {
        if (key === 'remarks') continue;
        if (!fields[key]) {
            const errNode = document.getElementById(`err_op_${keyToErrorIdMap[key]}`);
            if (errNode) errNode.innerText = 'This field is mandatory.';
            hasValidationError = true;
        }
    }

    if (fields.name && !/^[a-zA-Z\s]+$/.test(fields.name)) {
        document.getElementById('err_op_name').innerText = 'Name must only contain alphabets and spaces.';
        hasValidationError = true;
    }

    // Check local duplicate mobile in batch list
    let isMobileLocalDup = false;
    if (fields.mobile) {
        if (!/^[6-9]\d{9}$/.test(fields.mobile)) {
            document.getElementById('err_op_mobile').innerText = 'Must be a valid 10-digit number starting with 6-9.';
            hasValidationError = true;
        } else {
            isMobileLocalDup = structuredOperatorList.some(op => op.mobile === fields.mobile && op.id !== opId);
            if (isMobileLocalDup) {
                document.getElementById('err_op_mobile').innerText = 'This mobile number is already added to this batch.';
                hasValidationError = true;
            }
        }
    }

    if (fields.aadhar && !/^\d{4}$/.test(fields.aadhar)) {
        document.getElementById('err_op_aadhaar').innerText = 'Must be exactly 4 numeric digits.';
        hasValidationError = true;
    }

    // Check local duplicate email in batch list
    let isEmailLocalDup = false;
    if (fields.email) {
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) {
            document.getElementById('err_op_email').innerText = 'Please enter a valid email format.';
            hasValidationError = true;
        } else {
            isEmailLocalDup = structuredOperatorList.some(op => op.email === fields.email && op.id !== opId);
            if (isEmailLocalDup) {
                document.getElementById('err_op_email').innerText = 'This email address is already added to this batch.';
                hasValidationError = true;
            }
        }
    }

    // Check database duplicate mobile
    if (fields.mobile && /^[6-9]\d{9}$/.test(fields.mobile) && !isMobileLocalDup) {
        try {
            const res = await fetch(`/auth/dc/reactivation/check-duplicate?mobile=${fields.mobile}&exclude_id=${opId}`);
            if (res.ok) {
                const data = await res.json();
                if (data.exists) {
                    document.getElementById('err_op_mobile').innerText = data.message;
                    hasValidationError = true;
                }
            }
        } catch (e) {
            console.error("Mobile duplicate check failed", e);
        }
    }

    // Check database duplicate email
    if (fields.email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email) && !isEmailLocalDup) {
        try {
            const res = await fetch(`/auth/dc/reactivation/check-duplicate?email=${encodeURIComponent(fields.email)}&exclude_id=${opId}`);
            if (res.ok) {
                const data = await res.json();
                if (data.exists) {
                    document.getElementById('err_op_email').innerText = data.message;
                    hasValidationError = true;
                }
            }
        } catch (e) {
            console.error("Email duplicate check failed", e);
        }
    }

    if (fields.certDate) {
        const todayD = new Date();
        const yyyy = todayD.getFullYear();
        const mm = String(todayD.getMonth() + 1).padStart(2, '0');
        const dd = String(todayD.getDate()).padStart(2, '0');
        const todayStr = `${yyyy}-${mm}-${dd}`;

        if (fields.certDate > todayStr) {
            document.getElementById('err_op_cert_date').innerText = 'Certification date cannot be in the future.';
            hasValidationError = true;
        } else {
            // Validate NSEIT Certification Date does not cross 3 years
            const certD = new Date(fields.certDate);
            const threeYearsAgo = new Date();
            threeYearsAgo.setFullYear(todayD.getFullYear() - 3);
            if (certD < threeYearsAgo) {
                document.getElementById('err_op_cert_date').innerText = 'NSEIT Certification Date must not be more than 3 years old.';
                hasValidationError = true;
            }
        }
    }

    if (hasValidationError) {
        const firstErrorEl = Array.from(document.querySelectorAll('.error-msg')).find(el => el.innerText.trim() !== '');
        if (firstErrorEl) {
            const parentGroup = firstErrorEl.closest('.form-group') || firstErrorEl.parentElement;
            if (parentGroup) {
                parentGroup.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                firstErrorEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
        return;
    }

    const opStatus = document.getElementById('editing_op_status') ? document.getElementById('editing_op_status').value : '';
    const opRejectReason = document.getElementById('editing_op_reject_reason') ? document.getElementById('editing_op_reject_reason').value : '';

    const verifiedRecord = {
        id: opId,
        status: opStatus,
        reject_reason: opRejectReason,
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
                    No operator entry added yet.
                </td>
            </tr>`;
        if (typeof window.renderSuspendedOperatorDropdown === 'function') {
            window.renderSuspendedOperatorDropdown();
        }
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
            <td>${escapeHtmlString(op.remarks) || '—'}</td>
            <td>${escapeHtmlString(op.model)}</td>
            <td style="text-align: center;">
                <button type="button" class="btn-primary-sm" onclick="editOperatorInStateArray(${index})" style="background-color: #f59e0b; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; margin-right: 5px; margin-bottom: 4px;">Edit</button>
                <button type="button" class="btn-danger-sm" onclick="removeOperatorFromStateArray(${index})">Remove</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    if (typeof window.renderSuspendedOperatorDropdown === 'function') {
        window.renderSuspendedOperatorDropdown();
    }
}

window.removeOperatorFromStateArray = function (index) {
    structuredOperatorList.splice(index, 1);
    renderOperatorSpreadsheetRows();
}

window.editOperatorInStateArray = function (index) {
    if (window.isCurrentlyEditingOperator) {
        Swal.fire({
            title: 'Unsaved Operator Changes',
            text: 'You are currently editing an operator and have not added it back to the list. If you proceed, those changes will be lost (canceled). Do you want to proceed?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Yes, proceed',
            cancelButtonText: 'No, stay'
        }).then((result) => {
            if (result.isConfirmed) {
                window.isCurrentlyEditingOperator = false;
                editOperatorInStateArray(index);
            }
        });
        return;
    }
    window.isCurrentlyEditingOperator = true;

    const op = structuredOperatorList[index];
    structuredOperatorList.splice(index, 1);
    renderOperatorSpreadsheetRows();

    // Populate form fields
    if (document.getElementById('op_role')) document.getElementById('op_role').value = op.role || 'Operator';
    if (document.getElementById('op_name')) document.getElementById('op_name').value = op.name || '';
    if (document.getElementById('op_reg')) document.getElementById('op_reg').value = op.reg || '';
    if (document.getElementById('op_ea')) document.getElementById('op_ea').value = op.ea || '';
    if (document.getElementById('user_code')) document.getElementById('user_code').value = op.user || '';
    if (document.getElementById('op_cert')) document.getElementById('op_cert').value = op.cert || '';
    if (document.getElementById('op_mobile')) document.getElementById('op_mobile').value = op.mobile || '';
    if (document.getElementById('op_email')) document.getElementById('op_email').value = op.email || '';
    if (document.getElementById('op_aadhaar')) document.getElementById('op_aadhaar').value = op.aadhar || '';
    if (document.getElementById('op_cert_date')) document.getElementById('op_cert_date').value = op.certDate || '';
    if (document.getElementById('op_model')) document.getElementById('op_model').value = op.model || '';
    if (document.getElementById('op_lms_id')) document.getElementById('op_lms_id').value = op.lmsId || '';
    if (document.getElementById('op_remarks')) document.getElementById('op_remarks').value = op.remarks || '';

    if (document.getElementById('editing_op_id')) document.getElementById('editing_op_id').value = op.id || '';
    if (document.getElementById('editing_op_status')) document.getElementById('editing_op_status').value = op.status || '';
    if (document.getElementById('editing_op_reject_reason')) document.getElementById('editing_op_reject_reason').value = op.reject_reason || '';

    // Show operator revert reason if present
    const reasonContainer = document.getElementById('operator-revert-reason-container');
    const reasonText = document.getElementById('operator-revert-reason-text');
    const reasonLabel = document.getElementById('operator-revert-reason-label');

    if (!window.isReapplyBatchReverted && reasonContainer && reasonText && reasonLabel && op.reject_reason) {
        reasonText.innerText = op.reject_reason;
        const statusLower = (op.status || '').toLowerCase();
        if (statusLower.includes('reject')) {
            reasonLabel.innerText = 'REJECT REASON / REMARKS';
        } else {
            reasonLabel.innerText = 'REVERT REASON / REMARKS';
        }
        reasonContainer.style.display = 'block';
    } else if (reasonContainer) {
        reasonContainer.style.display = 'none';
    }

    if (stepTarget === 2) {
        if (s1Form) s1Form.style.display = 'none';
        if (s2Docs) s2Docs.style.display = 'block';
        if (node1) {
            node1.classList.remove('active');
            node1.classList.add('completed');
        }
        if (divider1) {
            divider1.classList.add('completed');
        }
        if (node2) {
            node2.classList.add('active');
        }
    } else {
        if (s1Form) s1Form.style.display = 'block';
        if (s2Docs) s2Docs.style.display = 'none';
        if (node1) {
            node1.classList.remove('completed');
            node1.classList.add('active');
        }
        if (divider1) {
            divider1.classList.remove('completed');
        }
        if (node2) {
            node2.classList.remove('active');
        }
    }
}

// 🚀 TRANSACTION ASYNC SUBMIT HANDLER
window.handleFormSubmissionPipeline = function (event) {
    event.preventDefault();

    if (window.isCurrentlyEditingOperator) {
        Swal.fire('Unsaved Changes', 'Please add or update the operator currently being edited to the list before submitting.', 'warning');
        return;
    }

    const formElement = document.getElementById('reactivationForm');

    // Check if training completion date is provided
    const trainingDateInput = document.getElementById("doc_training_date");
    if (trainingDateInput && !trainingDateInput.value) {
        Swal.fire({ title: 'Missing Information', text: 'Please select the Training Completion Date.', icon: 'warning' });
        trainingDateInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
    }

    const formData = new FormData(formElement);

    // 📁 STRICT DOCUMENT VALIDATION LAYER
    const requiredFiles = [
        { name: 'training_photo', label: 'Training Photo (.jpg/.png)', exts: ['.jpg', '.jpeg', '.png'], maxMB: 2 },
        { name: 'nodal_letter', label: 'District Nodal Endorsement Letter (.pdf)', exts: ['.pdf'], maxMB: 2 },
        { name: 'om_letter', label: 'Office Memorandum (OM) Copy (.pdf)', exts: ['.pdf'], maxMB: 2 },
        { name: 'attendance_list', label: 'Operator Attendance Excel Sheet (.xlsx)', exts: ['.xlsx', '.xls'], maxMB: 5 }
    ];

    for (const fileDef of requiredFiles) {
        const fileObj = formData.get(fileDef.name);

        // Check presence
        if (!fileObj || fileObj.size === 0) {
            if (window.currentReapplyCode) {
                // Documents are optional when reapplying; skip presence checks
                continue;
            }
            Swal.fire({ title: 'Missing Document', text: `Please upload the ${fileDef.label}.`, icon: 'warning' });
            const fileInput = document.querySelector(`input[name="${fileDef.name}"]`);
            if (fileInput) fileInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        // Check size boundaries
        const maxBytes = fileDef.maxMB * 1024 * 1024;
        if (fileObj.size > maxBytes) {
            Swal.fire({ title: 'File Too Large', text: `${fileDef.label} must be smaller than ${fileDef.maxMB}MB.`, icon: 'error' });
            const fileInput = document.querySelector(`input[name="${fileDef.name}"]`);
            if (fileInput) fileInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        // Check file extension extension validity
        const fileName = fileObj.name.toLowerCase();
        const hasValidExt = fileDef.exts.some(ext => fileName.endsWith(ext));
        if (!hasValidExt) {
            Swal.fire({ title: 'Invalid File Format', text: `The ${fileDef.label} must end with one of: ${fileDef.exts.join(', ')}`, icon: 'error' });
            const fileInput = document.querySelector(`input[name="${fileDef.name}"]`);
            if (fileInput) fileInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
    }

    formData.append('manual_operators', JSON.stringify(structuredOperatorList));

    const submitRequestAction = (remarksValue) => {
        if (remarksValue) {
            formData.append('reapply_remarks', remarksValue);
        }

        Swal.fire({
            title: 'Submitting Request...',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });

        const routingTargetUrl = '/auth/dc/submit';
        fetch(routingTargetUrl, { method: 'POST', body: formData })
            .then(res => {
                return res.json().then(data => {
                    if (!res.ok) {
                        let errMsg = "Server transaction processing failure.";
                        if (data && data.error) {
                            errMsg = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
                        } else if (data && data.detail) {
                            errMsg = typeof data.detail === 'object' ? JSON.stringify(data.detail) : data.detail;
                        }
                        throw new Error(errMsg);
                    }
                    return data;
                });
            })
            .then(data => {
                const isReapply = !!window.currentReapplyCode;
                Swal.fire({
                    title: isReapply ? 'Reapplied!' : 'Submitted Successfully',
                    text: isReapply ? 'Your corrected request has been sent back to CHiPS Admin.' : 'Reactivation request submitted successfully.',
                    icon: 'success',
                    confirmButtonColor: '#378ADD',
                    allowOutsideClick: false,
                    showConfirmButton: true,
                    timer: 3000,
                    timerProgressBar: true
                }).then(() => {
                    window.location.reload();
                });
            })
            .catch(err => {
                Swal.close();
                Swal.fire({ title: 'Submission Error', text: err.message, icon: 'error' });
            });
    };

    const startSubmissionProcess = () => {
        if (window.currentReapplyCode) {
            formData.append('reapply_request_code', window.currentReapplyCode);

            // Validate the reapply remarks field in the form itself
            const remarksField = document.getElementById('reapply_remarks_field');
            const remarks = remarksField ? remarksField.value.trim() : '';
            if (!remarks) {
                Swal.fire({ title: 'Validation Error', text: 'Please enter reapplication remarks.', icon: 'warning' });
                if (remarksField) remarksField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }
            submitRequestAction(remarks);
        } else {
            submitRequestAction(null);
        }
    };

    // 📊 CLIENT-SIDE OPERATOR ATTENDANCE EXCEL MATCHING VALIDATION
    const attendanceFileObj = formData.get('attendance_list');
    if (attendanceFileObj && attendanceFileObj.size > 0 && typeof window.XLSX !== 'undefined') {
        const fileReader = new FileReader();
        fileReader.onload = function (e) {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = window.XLSX.read(data, { type: 'array' });
                let excelText = '';

                workbook.SheetNames.forEach(sheetName => {
                    const worksheet = workbook.Sheets[sheetName];
                    const json = window.XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: false });
                    json.forEach(row => {
                        if (Array.isArray(row)) {
                            excelText += ' ' + row.join(' ').toLowerCase();
                        }
                    });
                });

                const missingOperators = [];
                (structuredOperatorList || []).forEach(op => {
                    const name = (op.name || '').trim().toLowerCase();
                    const mobile = (op.mobile || '').trim().toLowerCase();
                    const email = (op.email || '').trim().toLowerCase();
                    const user = (op.user || '').trim().toLowerCase();

                    let match = false;
                    if (mobile && excelText.includes(mobile)) {
                        match = true;
                    } else if (email && excelText.includes(email)) {
                        match = true;
                    } else if (user && user.length >= 3 && excelText.includes(user)) {
                        match = true;
                    } else if (name) {
                        if (excelText.includes(name)) {
                            match = true;
                        } else {
                            const nameParts = name.split(/\s+/).filter(p => p.length >= 3);
                            if (nameParts.length > 0 && nameParts.every(part => excelText.includes(part))) {
                                match = true;
                            }
                        }
                    }

                    if (!match) {
                        missingOperators.push(`<li><strong>${escapeHtmlString(op.name || 'Operator')}</strong> (Mobile: ${escapeHtmlString(op.mobile || 'N/A')})</li>`);
                    }
                });

                if (missingOperators.length > 0) {
                    Swal.fire({
                        title: 'Attendance Sheet Mismatch',
                        html: `<div style="text-align: left; font-size: 13px;">
                                <p style="margin-bottom: 8px;">The uploaded <strong>Operator Attendance Excel Sheet</strong> does not contain details for the following operator(s) added to the batch list:</p>
                                <ul style="color: #dc2626; padding-left: 20px; margin-bottom: 12px;">
                                    ${missingOperators.join('')}
                                </ul>
                                <p style="color: #64748b; margin-top: 8px;">Please upload an Attendance Excel Sheet containing all operators added to this request.</p>
                               </div>`,
                        icon: 'error',
                        confirmButtonColor: '#2563eb',
                        confirmButtonText: 'OK'
                    });
                    return;
                }

                startSubmissionProcess();
            } catch (err) {
                console.error("Client-side Excel validation error:", err);
                startSubmissionProcess();
            }
        };
        fileReader.onerror = function () { startSubmissionProcess(); };
        fileReader.readAsArrayBuffer(attendanceFileObj);
    } else {
        startSubmissionProcess();
    }
}


function getStatusBadgeHtml(status) {
    const s = (status || '').trim().toLowerCase().replace(/_/g, ' ');
    let badgeClass = 'badge-pending';
    let label = 'Pending';
    if (s.includes('approve')) { badgeClass = 'badge-approved'; label = 'Approved'; }
    else if (s.includes('revert')) { badgeClass = 'badge-reverted'; label = 'Reverted'; }
    else if (s.includes('forward') || s.includes('uidai')) { badgeClass = 'badge-forwarded'; label = s.includes('again') ? 'Sent to UIDAI Again' : 'Sent to UIDAI'; }
    else if (s.includes('reappl')) { badgeClass = 'badge-reapplied'; label = 'Reapplied'; }
    else if (s.includes('reject')) { badgeClass = 'badge-rejected'; label = 'Rejected'; }
    return `<span class="badge ${badgeClass}">${label}</span>`;
}

// 👁️ BATCH POPUP OPERATOR ROWS LOOKUP RENDERING
window.openHistoricalOperatorsModal = function (requestCode) {
    Swal.fire({
        title: `Operators Detail — Request ${requestCode}`,
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
        customClass: {
            confirmButton: 'swal-btn-close'
        }
    });

    fetch(`http://127.0.0.1:8000/reactivation/operators/${requestCode}?_t=${Date.now()}`)
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
                    let timelineHtml = `
                    <div class="remarks-timeline">
                        <div class="timeline-title">Reactivation Log Timeline</div>
                        <div class="timeline-track">`;

                    timelineLogs.forEach(log => {
                        const dateObj = new Date(log.timestamp.replace(' ', 'T'));
                        const formattedTime = dateObj.toLocaleDateString('en-GB') + ' ' + dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                        const isDC = log.sender_role === 'DC';
                        const sender = isDC ? 'District Coordinator' : 'CHiPS Admin';
                        const senderClass = isDC ? 'dc' : 'chips';

                        const statusAfter = log.status_after || '';
                        let statusBadgeHtmlInline = '';
                        let markerClass = 'marker-pending';
                        if (statusAfter) {
                            statusBadgeHtmlInline = ' ' + getStatusBadgeHtml(statusAfter);
                            const sLower = statusAfter.toLowerCase();
                            if (sLower.includes('approve')) markerClass = 'marker-approved';
                            else if (sLower.includes('revert') || sLower.includes('reject')) markerClass = 'marker-reverted';
                            else if (sLower.includes('forward') || sLower.includes('uidai')) markerClass = 'marker-forwarded';
                            else if (sLower.includes('reappl')) markerClass = 'marker-reapplied';
                        }

                        const username = log.sender_username || '';
                        const hasUsername = username && username !== sender && username.toLowerCase() !== 'candidate' && username !== 'Candidate' && sender !== 'CHiPS Admin';

                        timelineHtml += `
                            <div class="timeline-item ${senderClass}">
                                <div class="timeline-marker ${markerClass}"></div>
                                <div class="timeline-content">
                                    <div class="timeline-section-row">
                                        <span class="timeline-step-label">Operator Reactivation</span>${statusBadgeHtmlInline}
                                    </div>
                                    <div class="timeline-by-row">
                                        <span class="timeline-by">By: <strong>${sender}</strong>${hasUsername ? ' (' + escapeHtmlString(username) + ')' : ''}</span>
                                        <span class="timeline-time">${formattedTime}</span>
                                    </div>
                                    <div class="timeline-body">${escapeHtmlString(log.message)}</div>
                                </div>
                            </div>
                        `;
                    });

                    timelineHtml += `</div></div>`;
                    timelineContainer.innerHTML = timelineHtml;
                } else {
                    timelineContainer.innerHTML = `
                    <div class="remarks-timeline">
                        <div class="timeline-title">Reactivation Log Timeline</div>
                        <div style="text-align: center; color: #94a3b8; font-size: 13px; padding: 20px; font-style: italic;">No timeline logs available for this batch.</div>
                    </div>`;
                }
            }

            operators.forEach((op, idx) => {
                const row = document.createElement('tr');
                row.style.borderBottom = "1px solid #f1f5f9";

                const statusBadgeHtml = getStatusBadgeHtml(op.status);

                row.innerHTML = `
                <td style="padding: 10px; text-align: center; color: #64748b;">${idx + 1}</td>
                <td style="padding: 10px; padding-left: 15px; color: #1e293b;"><strong>${escapeHtmlString(op.operator_name)}</strong></td>
                <td style="padding: 10px; text-align: center;">${statusBadgeHtml}</td>
                <td style="padding: 10px; text-align: center;">
                    <button type="button" class="btn-details" 
                            onclick="openIndividualOperatorDetailCard(${idx})">
                        Details
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
    const noticeEl = document.getElementById('reapply-file-notice');
    if (noticeEl) noticeEl.style.display = 'block';
    const remarkEl = document.getElementById('reapply-remark-section');
    if (remarkEl) remarkEl.style.display = 'block';
    document.querySelectorAll('.doc-required-star').forEach(star => {
        star.style.display = 'none';
    });
    const titleEl = document.getElementById('reactivation-form-title');
    if (titleEl) {
        titleEl.innerText = `Modify & Reapply Operator Reactivation Request`;
    }

    if (trainingDate) {
        document.getElementById('doc_training_date').value = trainingDate;
    }

    Swal.fire({
        title: 'Loading Previous Data...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
    });

    fetch(`http://127.0.0.1:8000/reactivation/operators/${requestCode}?_t=${Date.now()}`)
        .then(res => {
            if (!res.ok) throw new Error('Failed to load previous operators');
            return res.json();
        })
        .then(payload => {
            Swal.close();

            // Clear previous documents display first
            document.querySelectorAll('.prev-doc-indicator').forEach(el => {
                el.style.display = 'none';
                el.innerText = '';
            });

            // Populate previous documents
            if (payload.documents) {
                for (const [docType, docInfo] of Object.entries(payload.documents)) {
                    const docEl = document.getElementById(`prev-${docType}`);
                    if (docEl && docInfo && docInfo.original_filename) {
                        docEl.innerText = `✓ ${docInfo.original_filename}`;
                        docEl.style.display = 'block';
                    }
                }
            }

            // Toggle batch revert reason displays
            const isBatchRevertedOrRejected = ['REVERTED', 'REJECTED'].includes((payload.batch_status || '').toUpperCase());
            const batchReason = payload.batch_revert_reason || '';

            const p1BatchContainer = document.getElementById('batch-revert-reason-container-p1');
            const p1BatchText = document.getElementById('batch-revert-reason-text-p1');
            const p1BatchLabel = document.getElementById('batch-revert-reason-label-p1');

            const p2BatchContainer = document.getElementById('batch-revert-reason-container-p2');
            const p2BatchText = document.getElementById('batch-revert-reason-text-p2');
            const p2BatchLabel = document.getElementById('batch-revert-reason-label-p2');

            if (isBatchRevertedOrRejected && batchReason) {
                window.isReapplyBatchReverted = true;
                const labelText = (payload.batch_status || '').toUpperCase() === 'REJECTED' ? 'BATCH REJECT REASON' : 'BATCH REVERT REASON / REMARKS';

                if (p1BatchContainer && p1BatchText && p1BatchLabel) {
                    p1BatchText.innerText = batchReason;
                    p1BatchLabel.innerText = labelText;
                    p1BatchContainer.style.display = 'block';
                }
                if (p2BatchContainer && p2BatchText && p2BatchLabel) {
                    p2BatchText.innerText = batchReason;
                    p2BatchLabel.innerText = labelText;
                    p2BatchContainer.style.display = 'block';
                }
            } else {
                window.isReapplyBatchReverted = false;
                if (p1BatchContainer) p1BatchContainer.style.display = 'none';
                if (p2BatchContainer) p2BatchContainer.style.display = 'none';
            }

            structuredOperatorList = [];
            window.structuredOperatorList = structuredOperatorList;
            const operators = payload.operators || [];
            operators.forEach(op => {
                const status = (op.status || '').toLowerCase().replace(/_/g, ' ');
                if (['reverted', 'revert back', 'rejected'].includes(status)) {
                    structuredOperatorList.push({
                        id: op.id,
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
                        remarks: op.remarks || '',
                        reject_reason: op.reject_reason || '',
                        status: op.status || '',
                        aadhar: op.aadhaar_number || ''
                    });
                }
            });
            renderOperatorSpreadsheetRows();
            window.switchReactivationView('app');
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
}

// 💳 DETAILS MODAL MAPPING INTERFACE CARD BUILDER
window.zoomPhoto = function (url) {
    viewDocument('Profile Photo', url, 'jpg');
};

window.viewDocument = function (title, fileUrl, extension) {
    if (!fileUrl) return;
    if (fileUrl && !fileUrl.startsWith('data:') && !fileUrl.startsWith('http') && !fileUrl.startsWith('/')) {
        fileUrl = '/candidate_upload/' + fileUrl;
    }
    const ext = extension || fileUrl.split('.').pop().toLowerCase();
    if (typeof window.previewDocument === 'function') {
        window.previewDocument(fileUrl, ext, title);
    }
};

window.buildDocumentCard = function (title, fileUrl, defaultName) {
    if (!fileUrl) return '';

    const extension = (defaultName || '').split('.').pop().toLowerCase();
    const isImage = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(extension) || fileUrl.startsWith('data:image/');

    let previewHtml = '';
    let previewButtonHtml = '';

    if (isImage) {
        previewHtml = `<img src="${fileUrl}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px; cursor: pointer;" onclick="viewDocument('${title}', '${fileUrl}', '${extension}')">`;
        previewButtonHtml = `
            <button type="button" onclick="viewDocument('${title}', '${fileUrl}', '${extension}')" style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: none; border-radius: 6px; background-color: #eff6ff; color: #3b82f6; cursor: pointer; transition: background-color 0.2s;" title="Preview">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            </button>
        `;
    } else {
        const isExcel = ['xls', 'xlsx'].includes(extension);
        const clickAttr = isExcel ? '' : `onclick="viewDocument('${title}', '${fileUrl}', '${extension}')"`;
        const cursorStyle = isExcel ? 'default' : 'pointer';

        previewHtml = `
            <div style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; background: #f8fafc; border-radius: 8px; cursor: ${cursorStyle};" ${clickAttr}>
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </div>
        `;

        if (!isExcel) {
            previewButtonHtml = `
                <button type="button" onclick="viewDocument('${title}', '${fileUrl}', '${extension}')" style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border: none; border-radius: 6px; background-color: #eff6ff; color: #3b82f6; cursor: pointer; transition: background-color 0.2s;" title="Preview">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                </button>
            `;
        }
    }

    const shortFileName = defaultName.length > 22 ? defaultName.substring(0, 19) + '...' : defaultName;

    return `
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div style="height: 100px; width: 100%; background: #f8fafc; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; border: 1px solid #edf2f7;">
                ${previewHtml}
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-top: 2px;">
                <div style="text-align: left; overflow: hidden; flex-grow: 1; min-width: 0;">
                    <div style="font-size: 12px; font-weight: 700; color: #1a202c; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2;" title="${title}">${title}</div>
                    <div style="font-size: 10px; color: #a0aec0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;" title="${defaultName}">${shortFileName}</div>
                </div>
                <div style="display: flex; gap: 6px; flex-shrink: 0;">
                    ${previewButtonHtml}
                    <a href="${fileUrl}" download="${defaultName}" style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 6px; background-color: #ecfdf5; color: #10b981; text-decoration: none; cursor: pointer; transition: background-color 0.2s;" title="Download">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    </a>
                </div>
            </div>
        </div>
    `;
};

window.showIndividualOperatorDetails = function (arrayIndex, activeView) {
    const op = window.currentViewingOperators[arrayIndex];
    if (!op) {
        console.error("Index target context maps outside viewing operator bounds matrix.");
        return;
    }

    const requestCode = window.currentViewingRequestCode;
    const reqObj = (window.historyRequestsPayload || []).find(r => r.request_code === requestCode);
    const requestStatus = op.status || (reqObj ? reqObj.status : 'PENDING');
    const statusBadge = getStatusBadgeHtml(requestStatus);

    const fullName = op.operator_name || op.name || '—';
    const roleProfile = op.role || 'Operator';
    const mobileNumber = op.operator_mobile || op.mobile || '—';
    const emailAddress = op.email_id || op.email || '—';
    const registrarCode = op.registrar_code || '986';
    const eaCode = op.ea_code || '—';
    const userCode = op.user_code || '—';
    const modelType = op.model_type || '—';
    const lmsCertId = op.lms_certificate_id || '—';
    const nseitCertNo = op.certificate_number || '—';
    const certificationDate = op.certification_date || '—';
    const explicitRemarks = op.remarks || '—';

    const cardEl = document.querySelector(`[data-request-id="${requestCode}"]`);
    const submittedAt = cardEl ? cardEl.getAttribute('data-created') || '—' : '—';
    const statusUpper = (op.status || '').toUpperCase().trim();
    const isRevertable = ['REVERTED', 'REVERT BACK', 'REVERTED BY CHIPS', 'REVERTED_BY_CHIPS'].includes(statusUpper);
    const isRejected = (statusUpper === 'REJECTED');

    if (activeView === 'details') {
        let htmlContent = `
        <div style="text-align: left; padding: 0 5px; max-height: 60vh; overflow-y: auto; font-family: 'Inter', sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 14px; color: #666;">Request ID: <strong>${requestCode}</strong></span>
                <span>${statusBadge}</span>
            </div>
            <div style="font-size: 12px; color: #64748b; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px;">
                Submitted At: <strong style="color: #475569;">${submittedAt}</strong>
            </div>

            ${isRevertable || isRejected ? `
            <div class="action-required-banner">
                <div class="action-required-title" style="color: var(--alert-warning-title) !important;"><span>⚠️</span> <span style="color: var(--alert-warning-title) !important;">Action Required — Request ${isRejected ? 'Rejected' : 'Reverted'}</span></div>
                <div class="action-required-desc" style="color: var(--alert-warning-desc) !important;">Review CHiPS Admin's remarks below, click "Modify & Reapply" to update details.</div>
            </div>
            ${op.reject_reason ? `
            <div class="revert-reason-box" style="margin-bottom: 20px;">
                <div class="revert-reason-header">
                    <span class="revert-reason-title">${isRejected ? 'Rejection Reason/Remark:' : 'Revert Reason/Remark:'}</span>
                </div>
                <div class="revert-reason-text">
                    ${escapeHtmlString(op.reject_reason)}
                </div>
            </div>` : ''}
            ` : ''}

            <!-- Personal Information Card -->
            <div style="margin-bottom: 20px;">
                <div style="font-size: 11px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 6px;">Personal Information</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                    <div style="grid-column: 1/-1; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Full Name</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(fullName)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Mobile Number</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(mobileNumber)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Primary Email ID</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(emailAddress)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Aadhaar Number</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${(op.aadhaar_number || op.aadhar) ? 'XXXX-XXXX-' + escapeHtmlString(String(op.aadhaar_number || op.aadhar).slice(-4)) : '—'}</div>
                    </div>
                </div>
            </div>

            <!-- Work & Certification Card -->
            <div style="margin-bottom: 20px;">
                <div style="font-size: 11px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 12px; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 6px;">Work &amp; Certification</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Role Profile</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(roleProfile)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Registrar Code</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(registrarCode)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">EA Code</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(eaCode)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">User Code</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(userCode)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Model Type</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(modelType)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">LMS Certificate ID</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;"><span style="font-family: monospace; font-weight: 700; color: #2563eb;">${escapeHtmlString(lmsCertId)}</span></div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">NSEIT Certificate #</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(nseitCertNo)}</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Certification Date</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(certificationDate)}</div>
                    </div>
                    <div style="grid-column: 1/-1; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
                        <div style="font-size: 10px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Remarks</div>
                        <div style="font-size: 13px; font-weight: 600; color: #495057;">${escapeHtmlString(explicitRemarks)}</div>
                    </div>
                </div>
            </div>

            <!-- View Action Buttons -->
            <div style="display: flex; justify-content: center; gap: 10px; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                ${(() => {
                    const approvedTabBtn = document.querySelector('.req-tab[data-tab="approved"]');
                    const approvedContainer = document.getElementById('view-approved-container');
                    const isApprovedTabActive = (approvedTabBtn && approvedTabBtn.classList.contains('active')) || 
                                               (approvedContainer && approvedContainer.classList.contains('active') && approvedContainer.offsetParent !== null);
                    return isApprovedTabActive ? `
                    <button type="button" id="btn-show-docs" style="background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; box-shadow: 0 1px 2px rgba(0,0,0,0.05); transition: all 0.2s ease-in-out;" onmouseover="this.style.background='#f8fafc'; this.style.borderColor='#94a3b8';" onmouseout="this.style.background='#ffffff'; this.style.borderColor='#cbd5e1';">View Documents</button>` : '';
                })()}
                <button type="button" id="btn-show-remarks" style="padding: 8px 16px; border-radius: 8px; background: #4f46e5; color: white; border: none; font-weight: 600; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#4338ca'" onmouseout="this.style.background='#4f46e5'">View Remarks</button>
            </div>
        </div>
        `;

        Swal.fire({
            title: `<span style="font-family:inherit; font-weight:800;">Submitted Operator Details</span>`,
            html: htmlContent,
            showCancelButton: false, // NO Cancel button
            showConfirmButton: true,
            confirmButtonText: (isRevertable || isRejected) ? 'Modify & Reapply' : 'Close',
            showDenyButton: (isRevertable || isRejected),
            denyButtonText: 'Close',
            customClass: {
                confirmButton: 'swal-btn-close',
                denyButton: 'swal-btn-back'
            },
            width: '600px',
            focusConfirm: false,
            didOpen: () => {
                document.getElementById('btn-show-remarks').onclick = () => {
                    window.showIndividualOperatorDetails(arrayIndex, 'remarks');
                };
                const btnShowDocs = document.getElementById('btn-show-docs');
                if (btnShowDocs) {
                    btnShowDocs.onclick = () => {
                        window.viewBatchDocuments(requestCode, arrayIndex);
                    };
                }
            }
        }).then((result) => {
            if (result.isConfirmed && (isRevertable || isRejected)) {
                const trainingDate = cardEl ? cardEl.getAttribute('data-training-date') || '' : '';
                window.reapplyIndividualOperator(op.id, requestCode, trainingDate);
            }
        });
    }
    else if (activeView === 'remarks') {
        Swal.fire({
            title: 'Fetching Remarks...',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });

        fetch(`/auth/dc/reactivation/operators/${requestCode}?_t=${Date.now()}`)
            .then(res => res.json())
            .then(payload => {
                Swal.close();
                let timelineHtml = '';
                const logsRaw = payload.timeline_logs || [];
                const logs = logsRaw.filter(log => {
                    if (log.operator_id) {
                        return String(log.operator_id) === String(op.id);
                    }
                    const msg = log.message || '';
                    return !msg.includes("Operator '") || msg.includes(`Operator '${op.operator_name}'`);
                });

                if (logs.length > 0) {
                    timelineHtml += `
                    <div class="remarks-timeline" style="display: flex; flex-direction: column; overflow: hidden; flex: 1 1 auto;">
                        <div class="timeline-title" style="flex: 0 0 auto; margin-bottom: 10px;">Audit Action History Log</div>
                        <div class="timeline-track" style="flex: 1 1 auto; overflow-y: auto; padding-right: 5px; padding-left: 35px !important; margin-left: 0 !important; border-left: none !important; background: linear-gradient(to right, transparent 12px, #e2e8f0 12px, #e2e8f0 14px, transparent 14px); background-attachment: local;">
                    `;
                    logs.forEach(item => {
                        const sender = (item.sender_role === 'CHIPS' || item.sender_role === 'CHIPS_ADMIN') ? 'CHiPS Admin' :
                            (item.sender_role === 'DC') ? 'District Coordinator' :
                                (item.sender_role === 'EDM') ? 'District Manager (EDM)' : 'Candidate';
                        const senderClass = (item.sender_role === 'CHIPS' || item.sender_role === 'CHIPS_ADMIN' || item.sender_role === 'DC' || item.sender_role === 'EDM') ? 'chips' : 'candidate';

                        let statusAfter = item.status_after || '';
                        const msg = item.message || item.remark || '';

                        // Fallback override for older logs where status_after was incorrectly logged as PENDING
                        if (statusAfter.toUpperCase() === 'PENDING' || !statusAfter) {
                            const m = msg.toLowerCase();
                            // Prevent 'reactivation' from triggering 'activat' match
                            if (m.includes('reject')) statusAfter = 'REJECTED';
                            else if (m.includes('revert')) statusAfter = 'REVERTED';
                            else if ((m.includes('approv') && !m.includes('reactivat')) || m.includes('approve')) statusAfter = 'APPROVED';
                            else if (m.includes('uidai')) statusAfter = 'SENT_TO_UIDAI';
                        }

                        let statusBadgeHtmlInline = '';
                        let markerClass = 'marker-pending';
                        if (statusAfter) {
                            statusBadgeHtmlInline = ' ' + getStatusBadgeHtml(statusAfter);
                            const sLower = statusAfter.toLowerCase();
                            if (sLower.includes('approve')) markerClass = 'marker-approved';
                            else if (sLower.includes('revert') || sLower.includes('reject')) markerClass = 'marker-reverted';
                            else if (sLower.includes('forward') || sLower.includes('uidai')) markerClass = 'marker-forwarded';
                            else if (sLower.includes('reappl')) markerClass = 'marker-reapplied';
                        }

                        const username = item.sender_username || '';
                        const hasUsername = username && username !== sender && username.toLowerCase() !== 'candidate' && username !== 'Candidate' && sender !== 'CHiPS Admin';

                        timelineHtml += `
                            <div class="timeline-item ${senderClass}">
                                <div class="timeline-marker ${markerClass}"></div>
                                <div class="timeline-content">
                                    <div class="timeline-section-row">
                                        <span class="timeline-step-label">Reactivation</span>${statusBadgeHtmlInline}
                                    </div>
                                    <div class="timeline-by-row">
                                        <span class="timeline-by">By: <strong>${sender}</strong>${hasUsername ? ' (' + escapeHtmlString(username) + ')' : ''}</span>
                                        <span class="timeline-time">${item.timestamp || item.created_at || '—'}</span>
                                    </div>
                                    <div class="timeline-body">${escapeHtmlString(item.message || item.remark || '')}</div>
                                </div>
                            </div>
                        `;
                    });
                    timelineHtml += `</div></div>`;
                } else {
                    timelineHtml = `<div style="text-align:center;padding:20px;font-style:italic;color:#94a3b8;font-size:13px;background:#f8fafc;border-radius:8px;border:1px dashed #e2e8f0;">No remarks or action history logged yet.</div>`;
                }

                Swal.fire({
                    title: `<span style="font-family:inherit; font-weight:800;">Action History</span>`,
                    html: `<div style="text-align: left; padding: 0 5px; max-height: 60vh; display: flex; flex-direction: column; font-family: 'Inter', sans-serif;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px; flex: 0 0 auto;">
                            <span style="font-size: 14px; color: #666;">Request: <strong>${requestCode}</strong></span>
                            <span>${statusBadge}</span>
                        </div>
                        ${timelineHtml}
                    </div>`,
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
                        window.showIndividualOperatorDetails(arrayIndex, 'details');
                    }
                });
            })
            .catch(err => {
                Swal.fire('Error', 'Failed to fetch remarks history', 'error');
            });
    }
};

window.openIndividualOperatorDetailCard = function (arrayIndex) {
    window.showIndividualOperatorDetails(arrayIndex, 'details');
};


// 🧼 WORKSPACE INPUT FIELD CLEANSER
window.clearFormInputs = function () {
    document.getElementById('op_role').value = 'Supervisor';
    document.getElementById('op_name').value = '';
    document.getElementById('op_reg').value = '986';
    document.getElementById('op_ea').value = '';

    const opUserEl = document.getElementById('user_code');
    opUserEl.value = '';

    document.getElementById('op_cert').value = '';
    document.getElementById('op_mobile').value = '';
    document.getElementById('op_email').value = '';
    document.getElementById('op_aadhaar').value = '';
    document.getElementById('op_cert_date').value = '';
    document.getElementById('op_remarks').value = '';
    document.getElementById('op_model').value = '';
    document.getElementById('op_lms_id').value = '';

    const searchSelect = document.getElementById('operator_search_input');
    if (searchSelect) {
        searchSelect.value = '';
        if (searchSelect.tomselect) {
            searchSelect.tomselect.clear();
        }
    }

    document.querySelectorAll('.error-msg').forEach(el => el.innerText = '');

    if (document.getElementById('editing_op_id')) document.getElementById('editing_op_id').value = '';
    if (document.getElementById('editing_op_status')) document.getElementById('editing_op_status').value = '';
    if (document.getElementById('editing_op_reject_reason')) document.getElementById('editing_op_reject_reason').value = '';
    const reasonContainer = document.getElementById('operator-revert-reason-container');
    if (reasonContainer) reasonContainer.style.display = 'none';
    window.isCurrentlyEditingOperator = false;
}

function resetEntireNewRequestForm() {
    clearFormInputs();
    structuredOperatorList = [];
    window.structuredOperatorList = structuredOperatorList;
    renderOperatorSpreadsheetRows();
    const countBadge = document.getElementById('operator-count-badge');
    if (countBadge) countBadge.innerText = '0 Operators';

    ['training_photo', 'nodal_letter', 'om_letter', 'attendance_list', 'training_date'].forEach(name => {
        const el = document.getElementsByName(name)[0];
        if (el) el.value = '';
    });

    if (typeof navigateWizardStep === 'function') {
        navigateWizardStep(1);
    } else {
        const s1Form = document.getElementById('section-operator-form-view');
        const s2Docs = document.getElementById('section-documents-upload-view');
        if (s1Form) s1Form.style.display = 'block';
        if (s2Docs) s2Docs.style.display = 'none';
    }

    window.currentReapplyCode = null;
    const remarkEl = document.getElementById('reapply-remark-section');
    if (remarkEl) remarkEl.style.display = 'none';
    const remarksField = document.getElementById('reapply_remarks_field');
    if (remarksField) remarksField.value = '';

    window.isReapplyBatchReverted = false;
    const p1BatchContainer = document.getElementById('batch-revert-reason-container-p1');
    if (p1BatchContainer) p1BatchContainer.style.display = 'none';
    const p2BatchContainer = document.getElementById('batch-revert-reason-container-p2');
    if (p2BatchContainer) p2BatchContainer.style.display = 'none';

    document.querySelectorAll('.prev-doc-indicator').forEach(el => {
        el.style.display = 'none';
        el.innerText = '';
    });
    const titleEl = document.querySelector('.container-title');
    if (titleEl) {
        titleEl.innerText = 'AADHAAR OPERATOR REACTIVATION';
    }
    const searchInput = document.getElementById('flat-op-search');
    const searchText = searchInput ? searchInput.value.toLowerCase().trim() : "";

    const rows = document.querySelectorAll('.flat-op-row');
    rows.forEach(row => {
        const opName = row.getAttribute('data-name') || "";
        const opMobile = row.getAttribute('data-mobile') || "";
        const opEmail = row.getAttribute('data-email') || "";
        if (opName.includes(searchText) || opMobile.includes(searchText) || opEmail.includes(searchText)) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

// 🔍 DISTRICT HISTORY DATA GRID CLIENT-SIDE FILTER PIPELINE
window.applyHistoryPanelFiltersPipeline = function () {
    // 1. Gather all input conditions safely
    const searchOperatorInput = document.getElementById("filter-search-operator");
    const statusInput = document.getElementById("filter-status");
    const datePeriodInput = document.getElementById("filter-date-period");

    const searchQuery = searchOperatorInput ? searchOperatorInput.value.trim().toLowerCase() : "";
    const statusValue = statusInput ? statusInput.value : "ALL";
    const dateFilter = datePeriodInput ? datePeriodInput.value : "month";

    const rows = document.querySelectorAll(".history-data-row");
    let matchCount = 0;
    let totalVisibleOperators = 0;

    // Track status counts of matching operators based on active time period and search operator filters
    let opPendingCount = 0;
    let opReappliedCount = 0;
    let opSentToUidaiCount = 0;
    let opRevertedCount = 0;
    let opRejectedCount = 0;
    let opApprovedCount = 0;

    window.currentReapplyCode = null;

    const now = new Date();
    const y = now.getFullYear();
    const m = (now.getMonth() + 1).toString().padStart(2, '0');
    const d = now.getDate().toString().padStart(2, '0');
    const todayPrefix = `${y}-${m}-${d}`;

    rows.forEach(row => {
        const rowId = row.getAttribute("data-request-id") || "";
        const rowCreated = row.getAttribute("data-created") || "";

        const cleanStatusFilter = statusValue.toUpperCase().replace(" ", "_").trim();

        let matchesDate = (dateFilter === 'all');
        if (dateFilter === 'today') {
            matchesDate = rowCreated.startsWith(todayPrefix);
        } else if (dateFilter === 'week') {
            if (rowCreated) {
                const rowDate = new Date(rowCreated.replace(' ', 'T'));
                const threshold = new Date();
                threshold.setDate(now.getDate() - 7);
                matchesDate = rowDate >= threshold;
            }
        } else if (dateFilter === 'month') {
            if (rowCreated) {
                const rowDate = new Date(rowCreated.replace(' ', 'T'));
                const threshold = new Date();
                threshold.setDate(now.getDate() - 30);
                matchesDate = rowDate >= threshold;
            }
        }

        if (matchesDate) {
            let isBatchMatch = !searchQuery || rowId.toLowerCase().includes(searchQuery);
            let visibleOpsCount = 0;
            const opRows = row.querySelectorAll('.op-row-item');

            opRows.forEach(opRow => {
                const opName = (opRow.getAttribute('data-name') || "").toLowerCase();
                const opMobile = (opRow.getAttribute('data-mobile') || "").toLowerCase();
                const opEmail = (opRow.getAttribute('data-email') || "").toLowerCase();
                const opStatus = (opRow.getAttribute('data-status') || "").toUpperCase();

                const matchesSearch = isBatchMatch || opName.includes(searchQuery) || opMobile.includes(searchQuery) || opEmail.includes(searchQuery);

                // Dashboard metrics update: only count if matches date filter and search query
                if (matchesSearch) {
                    if (opStatus === 'PENDING') opPendingCount++;
                    else if (opStatus === 'REAPPLIED') opReappliedCount++;
                    else if (opStatus === 'SENT_TO_UIDAI') opSentToUidaiCount++;
                    else if (opStatus === 'REVERTED') opRevertedCount++;
                    else if (opStatus === 'REJECTED') opRejectedCount++;
                    else if (opStatus === 'APPROVED') opApprovedCount++;
                }

                const matchesOpStatus = (statusValue === "ALL") || (opStatus === cleanStatusFilter);

                // Highlight delayed/aged > 7 days reverted and rejected items
                if (['REVERTED', 'REJECTED'].includes(opStatus)) {
                    let dateAttr = opRow.getAttribute('data-updated') || row.getAttribute('data-updated');
                    if (!dateAttr || dateAttr === 'None' || dateAttr === '—' || dateAttr.trim() === '') {
                        dateAttr = opRow.getAttribute('data-created') || row.getAttribute('data-created');
                    }
                    if (dateAttr && dateAttr !== 'None' && dateAttr !== '—' && dateAttr.trim() !== '') {
                        const dateObj = new Date(dateAttr.replace(' ', 'T'));
                        if (!isNaN(dateObj)) {
                            const diffTime = Math.abs(now - dateObj);
                            const diffDays = diffTime / (1000 * 60 * 60 * 24);
                            if (diffDays > 7) {
                                opRow.classList.add('delayed-row');
                            }
                        }
                    }
                }

                if (matchesSearch && matchesOpStatus) {
                    opRow.style.display = "";
                    visibleOpsCount++;
                } else {
                    opRow.style.display = "none";
                }
            });

            if (visibleOpsCount > 0 || (opRows.length === 0 && isBatchMatch && statusValue === "ALL")) {
                row.style.display = "";
                matchCount++;
                totalVisibleOperators += visibleOpsCount;
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

    // Beside the table heading, display the count of matching visible operators
    const countEl = document.getElementById('batches-count');
    if (countEl) countEl.textContent = totalVisibleOperators;

    // Filter Flat Approved Operators Table
    const approvedRows = document.querySelectorAll(".flat-op-row");
    let visibleApproved = 0;
    approvedRows.forEach((row, idx) => {
        const opName = (row.getAttribute("data-name") || "").toLowerCase();
        const opMobile = (row.getAttribute("data-mobile") || "").toLowerCase();
        const opEmail = (row.getAttribute("data-email") || "").toLowerCase();
        const reqId = (row.getAttribute("data-request-id") || "").toLowerCase();
        const rowCreated = row.getAttribute("data-created") || "";

        const matchSearch = !searchQuery ||
            opName.includes(searchQuery) ||
            opMobile.includes(searchQuery) ||
            opEmail.includes(searchQuery) ||
            reqId.includes(searchQuery);

        const matchStatus = (statusValue === "ALL") || (statusValue === "APPROVED");
        const show = matchSearch && matchStatus;
        row.style.display = show ? "" : "none";
        if (show) {
            visibleApproved++;
            row.cells[0].innerText = visibleApproved;
        }
    });

    const flatApprovedCountEl = document.getElementById("flat-approved-count");
    if (flatApprovedCountEl) flatApprovedCountEl.textContent = visibleApproved;

    const flatApprovedEmptyMsg = document.getElementById("flat-approved-empty-msg");
    if (flatApprovedEmptyMsg) {
        flatApprovedEmptyMsg.style.display = (visibleApproved === 0) ? "block" : "none";
    }

    // Metric cards display all-time counts irrespective of active filters
}

window.clearAllFilters = window.resetHistoryPanelFilters = function () {
    const searchOperatorInput = document.getElementById("filter-search-operator");
    if (searchOperatorInput) searchOperatorInput.value = "";

    const statusInput = document.getElementById("filter-status");
    if (statusInput) statusInput.value = "ALL";

    const datePeriodInput = document.getElementById("filter-date-period");
    if (datePeriodInput) datePeriodInput.value = "month";

    applyHistoryPanelFiltersPipeline();
};

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
                Swal.fire({
                    title: 'Success',
                    text: 'Operator reapplied successfully!',
                    icon: 'success',
                    confirmButtonColor: '#378ADD',
                    allowOutsideClick: false,
                    showConfirmButton: true,
                    timer: 3000,
                    timerProgressBar: true
                }).then(() => {
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

// District Code Lookup Map
const DISTRICT_CODES = {
    'Bastar': 'BAS',
    'Bilaspur': 'BLP',
    'Dakshin Bastar Dantewada': 'DNT',
    'Dantewada': 'DNT',
    'Dhamtari': 'DMT',
    'Durg': 'DRG',
    'Janjgir-Champa': 'JCH',
    'Jashpur': 'JSH',
    'Ultar Bastar Kanker': 'KNK',
    'Kanker': 'KNK',
    'Kabirdham': 'KDM',
    'Kabeerdham': 'KDM',
    'Korba': 'KRB',
    'Korea': 'KOR',
    'Mahasamund': 'MHS',
    'Raigarh': 'RGR',
    'Raipur': 'RPR',
    'Rajnandgaon': 'RJN',
    'Surguja': 'SRG',
    'Bijapur': 'BIJ',
    'Narayanpur': 'NRY',
    'Sukma': 'SKM',
    'Kondagaon': 'KON',
    'Baloda Bazar-Bhatapara': 'BLB',
    'Balodabazar-Bhatapara': 'BLB',
    'Gariaband': 'GRY',
    'Balod': 'BLD',
    'Mungeli': 'MUN',
    'Surajpur': 'SRJ',
    'Balrampur-Ramanujganj': 'BLM',
    'Bemetara': 'BEM',
    'Gaurela-Pendra-Marwahi': 'GRL',
    'Khairagarh-Chhuikhadan-Gandai': 'KCG',
    'Manendragarh-Chirmiri-Bharatpur': 'MNN',
    'Mohla-Manpur-Ambagarh Chowki': 'MHL',
    'Mohla-Manpur-Ambagarh Chouki': 'MHL',
    'Sakti': 'SKT',
    'Sarangarh-Bilaigarh': 'SRB',
    'Gaurela Pendra Marwahi': 'GRL',
};

window.autoFillUserCode = function () {
    // Auto-fill logic removed as per user request
};

window.exportReactivationHistoryToExcel = function () {
    const cards = document.querySelectorAll(".history-data-row.request-card");
    const ids = [];
    cards.forEach(card => {
        if (card.style.display !== 'none') {
            const opRows = card.querySelectorAll(".op-row-item");
            opRows.forEach(opRow => {
                if (opRow.style.display !== 'none') {
                    const id = opRow.getAttribute('data-id');
                    if (id) ids.push(id.trim());
                }
            });
        }
    });

    if (ids.length === 0) {
        Swal.fire({
            title: 'No Data',
            text: 'No records found to export.',
            icon: 'warning',
            confirmButtonColor: '#3085d6'
        });
        return;
    }

    // Forward to Flask proxy which streams CSV from FastAPI central exporter
    window.location.href = `/auth/reactivation/export-csv-all?ids=${ids.join(',')}`;
};

window.exportApprovedOperatorsCSV = function () {
    const rows = document.querySelectorAll(".flat-op-row");
    const ids = [];
    rows.forEach(row => {
        if (row.style.display !== 'none') {
            const id = row.getAttribute('data-id');
            if (id) ids.push(id.trim());
        }
    });

    if (ids.length === 0) {
        Swal.fire({
            title: 'No Data',
            text: 'No records found to export.',
            icon: 'warning',
            confirmButtonColor: '#3085d6'
        });
        return;
    }

    // Forward to Flask proxy which streams CSV from FastAPI central exporter for approved (UIDAI sent) reactivation records
    window.location.href = `/auth/reactivation/export-csv-uidai?ids=${ids.join(',')}`;
};


window.viewBatchDocuments = function (requestCode, backIndex = null) {
    const trainingPhotoUrl = `/auth/reactivation/requests/${requestCode}/files/training_photo`;
    const nodalLetterUrl = `/auth/reactivation/requests/${requestCode}/files/nodal_letter`;
    const omLetterUrl = `/auth/reactivation/requests/${requestCode}/files/om_letter`;
    const attendanceListUrl = `/auth/reactivation/requests/${requestCode}/files/attendance_list`;

    let htmlContent = `
    <div style="text-align: left; padding: 0 5px; max-height: 60vh; overflow-y: auto;">
        <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px;">
            ${buildDocumentCard('Training Photo', trainingPhotoUrl, 'training_photo.jpg')}
            ${buildDocumentCard('District Nodal Endorsement Letter', nodalLetterUrl, 'nodal_endorsement_letter.pdf')}
            ${buildDocumentCard('Office Memorandum (OM) Letter', omLetterUrl, 'office_memorandum.pdf')}
            ${buildDocumentCard('Operator Attendance List', attendanceListUrl, 'attendance_list.xlsx')}
        </div>
    </div>
    `;

    Swal.fire({
        title: `<span style="font-family:inherit; font-weight:800; font-size: 18px;">Uploaded Batch Documents</span>`,
        html: htmlContent,
        showCancelButton: false,
        showConfirmButton: true,
        confirmButtonText: 'Close',
        showDenyButton: backIndex !== null,
        denyButtonText: 'Back',
        customClass: {
            confirmButton: 'swal-btn-close',
            denyButton: 'swal-btn-back'
        },
        width: '600px',
        focusConfirm: false
    }).then((result) => {
        if (result.isDenied && backIndex !== null) {
            window.showIndividualOperatorDetails(backIndex, 'details');
        }
    });
};

window.reapplyIndividualOperator = function (operatorId, requestCode, trainingDate) {
    window.currentReapplyCode = requestCode;
    const noticeEl = document.getElementById('reapply-file-notice');
    if (noticeEl) noticeEl.style.display = 'block';
    const remarkEl = document.getElementById('reapply-remark-section');
    if (remarkEl) remarkEl.style.display = 'block';
    document.querySelectorAll('.doc-required-star').forEach(star => {
        star.style.display = 'none';
    });
    const titleEl = document.getElementById('reactivation-form-title');
    if (titleEl) {
        titleEl.innerText = `Modify & Reapply Operator Reactivation Request`;
    }

    if (trainingDate) {
        document.getElementById('doc_training_date').value = trainingDate;
    }

    Swal.fire({
        title: 'Loading Operator Data...',
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

            // Clear previous documents display first
            document.querySelectorAll('.prev-doc-indicator').forEach(el => {
                el.style.display = 'none';
                el.innerText = '';
            });

            // Populate previous documents
            if (payload.documents) {
                for (const [docType, docInfo] of Object.entries(payload.documents)) {
                    const docEl = document.getElementById(`prev-${docType}`);
                    if (docEl && docInfo && docInfo.original_filename) {
                        docEl.innerText = `✓ ${docInfo.original_filename}`;
                        docEl.style.display = 'block';
                    }
                }
            }

            // Toggle batch revert reason displays
            const isBatchRevertedOrRejected = ['REVERTED', 'REJECTED'].includes((payload.batch_status || '').toUpperCase());
            const batchReason = payload.batch_revert_reason || '';

            const p1BatchContainer = document.getElementById('batch-revert-reason-container-p1');
            const p1BatchText = document.getElementById('batch-revert-reason-text-p1');
            const p1BatchLabel = document.getElementById('batch-revert-reason-label-p1');

            const p2BatchContainer = document.getElementById('batch-revert-reason-container-p2');
            const p2BatchText = document.getElementById('batch-revert-reason-text-p2');
            const p2BatchLabel = document.getElementById('batch-revert-reason-label-p2');

            if (isBatchRevertedOrRejected && batchReason) {
                window.isReapplyBatchReverted = true;
                const labelText = (payload.batch_status || '').toUpperCase() === 'REJECTED' ? 'BATCH REJECT REASON' : 'BATCH REVERT REASON / REMARKS';

                if (p1BatchContainer && p1BatchText && p1BatchLabel) {
                    p1BatchText.innerText = batchReason;
                    p1BatchLabel.innerText = labelText;
                    p1BatchContainer.style.display = 'block';
                }
                if (p2BatchContainer && p2BatchText && p2BatchLabel) {
                    p2BatchText.innerText = batchReason;
                    p2BatchLabel.innerText = labelText;
                    p2BatchContainer.style.display = 'block';
                }
            } else {
                window.isReapplyBatchReverted = false;
                if (p1BatchContainer) p1BatchContainer.style.display = 'none';
                if (p2BatchContainer) p2BatchContainer.style.display = 'none';
            }

            structuredOperatorList = [];
            window.structuredOperatorList = structuredOperatorList;
            const operators = payload.operators || [];
            // Find only this specific operator!
            const op = operators.find(o => String(o.id) === String(operatorId));
            if (op) {
                structuredOperatorList.push({
                    id: op.id,
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
                    remarks: op.remarks || '',
                    reject_reason: op.reject_reason || '',
                    status: op.status || '',
                    aadhar: op.aadhaar_number || ''
                });
            }
            renderOperatorSpreadsheetRows();
            window.switchReactivationView('app');
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.oa-file-input').forEach(input => {
        input.addEventListener('change', function () {
            // Remove any existing error message
            const parent = this.closest('.oa-doc-card');
            if (parent) {
                let errEl = parent.querySelector('.error-msg-file');
                if (errEl) errEl.remove();

                const file = this.files[0];
                if (!file) return;

                const name = this.name;
                const maxMB = name === 'attendance_list' ? 5 : 2;
                const maxBytes = maxMB * 1024 * 1024;

                if (file.size > maxBytes) {
                    // Clear input to enforce strictness
                    this.value = '';

                    // Add red warning message below the field
                    errEl = document.createElement('div');
                    errEl.className = 'error-msg-file';
                    errEl.style.color = '#ef4444';
                    errEl.style.fontSize = '12px';
                    errEl.style.marginTop = '6px';
                    errEl.style.fontWeight = '600';
                    errEl.style.fontFamily = "'Inter', sans-serif";
                    errEl.innerText = `Must be smaller than ${maxMB}MB.`;
                    parent.appendChild(errEl);
                }
            }
        });
    });
});

function hasUnsavedOperatorFormFields() {
    const userEnteredFields = [
        'op_name',
        'op_mobile',
        'op_email',
        'op_aadhaar',
        'user_code',
        'op_lms_id',
        'op_cert',
        'op_cert_date',
        'op_ea',
        'op_model',
        'op_remarks'
    ];
    return userEnteredFields.some(id => {
        const el = document.getElementById(id);
        return el && el.value && el.value.trim() !== '';
    });
}

window.navigateWizardStep = async function (stepNumber) {
    const section1 = document.getElementById('section-operator-form-view');
    const section2 = document.getElementById('section-documents-upload-view');

    if (stepNumber === 1) {
        if (section1) section1.style.display = 'block';
        if (section2) section2.style.display = 'none';
        return;
    }

    if (stepNumber === 2) {
        const hasFormDetails = hasUnsavedOperatorFormFields();
        const hasListOperators = structuredOperatorList && structuredOperatorList.length > 0;

        // If user has filled operator details in the form without clicking "Add Operator Record to Log"
        if (hasFormDetails) {
            const result = await Swal.fire({
                title: 'Unsaved Operator Form Details',
                text: 'You have filled operator details in the form. Would you like to add this operator to the batch list before proceeding?',
                icon: 'question',
                showCancelButton: true,
                showDenyButton: true,
                confirmButtonText: 'Add to List & Proceed',
                denyButtonText: 'Ignore & Proceed',
                cancelButtonText: 'Cancel',
                confirmButtonColor: '#3085d6',
                denyButtonColor: '#64748b',
                cancelButtonColor: '#d33',
                focusConfirm: true
            });

            if (result.isConfirmed) {
                const countBefore = (structuredOperatorList || []).length;
                await window.addOperatorRecordToExcelLog();
                const countAfter = (structuredOperatorList || []).length;

                if (countAfter > countBefore) {
                    if (section1) section1.style.display = 'none';
                    if (section2) section2.style.display = 'block';
                }
                return;
            } else if (result.isDenied) {
                if (structuredOperatorList && structuredOperatorList.length > 0) {
                    if (section1) section1.style.display = 'none';
                    if (section2) section2.style.display = 'block';
                } else {
                    Swal.fire({
                        title: 'Operator List is Empty',
                        text: 'Your batch list is empty. You must add at least one operator to proceed to the next step.',
                        icon: 'warning',
                        confirmButtonColor: '#3085d6',
                        confirmButtonText: 'OK'
                    });
                }
                return;
            } else {
                return;
            }
        }

        // If form inputs are empty and operator list is empty
        if (!hasListOperators) {
            Swal.fire({
                title: 'Operator List is Empty',
                text: 'Your batch list is empty. Please fill in the operator details and click "Add Operator Record to Log" to proceed.',
                icon: 'warning',
                confirmButtonColor: '#3085d6',
                confirmButtonText: 'OK'
            });
            return;
        }

        // If form inputs are empty and list has 1+ operators
        if (section1) section1.style.display = 'none';
        if (section2) section2.style.display = 'block';
    }
};

window.switchMainView = function (viewType, btn) {
    const batchesContainer = document.getElementById('view-batches-container');
    const approvedContainer = document.getElementById('view-approved-container');

    if (viewType === 'batches') {
        if (batchesContainer) batchesContainer.style.display = 'block';
        if (approvedContainer) approvedContainer.style.display = 'none';
    } else {
        if (batchesContainer) batchesContainer.style.display = 'none';
        if (approvedContainer) approvedContainer.style.display = 'block';
    }

    // Toggle active classes on tabs
    document.querySelectorAll('.main-view-tab').forEach(tab => {
        tab.classList.remove('active-view');
        tab.style.color = '#64748b';
        tab.style.borderBottomColor = 'transparent';
        tab.style.fontWeight = '600';
    });

    if (btn) {
        btn.classList.add('active-view');
        btn.style.color = '#378ADD';
        btn.style.borderBottomColor = '#378ADD';
        btn.style.fontWeight = '700';
    }
};
