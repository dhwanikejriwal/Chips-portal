/**
 * mail_composer.js
 * Unified Gmail-style Email Composer & 2-Step Export Mail Handler for CHiPS Panel.
 */

window.CHiPSMailComposer = (function () {
    let currentConfig = null;

    function init() {
        const container = document.getElementById('gmailComposeContainer');
        if (container) {
            container.style.setProperty('display', 'none', 'important');
        }

        // Wire up formatting toolbar commands (using mousedown to preserve editor selection)
        document.querySelectorAll('.gmail-tool-btn').forEach(btn => {
            btn.addEventListener('mousedown', function (e) {
                e.preventDefault();
                const command = this.getAttribute('data-command');
                if (command) {
                    document.execCommand(command, false, null);
                }
            });
            btn.addEventListener('click', function (e) {
                e.preventDefault();
            });
        });

        // CC & BCC Toggles
        const toggleCc = document.getElementById('toggleCcBtn');
        const toggleBcc = document.getElementById('toggleBccBtn');
        const rowCc = document.getElementById('rowCc');
        const rowBcc = document.getElementById('rowBcc');

        if (toggleCc && rowCc) {
            toggleCc.addEventListener('click', function () {
                rowCc.classList.toggle('d-none');
                if (!rowCc.classList.contains('d-none')) {
                    document.getElementById('gmailMailCc').focus();
                }
            });
        }

        if (toggleBcc && rowBcc) {
            toggleBcc.addEventListener('click', function () {
                rowBcc.classList.toggle('d-none');
                if (!rowBcc.classList.contains('d-none')) {
                    document.getElementById('gmailMailBcc').focus();
                }
            });
        }

        // Header controls (Minimize, Expand, Close)
        const btnMin = document.getElementById('gmailBtnMinimize');
        const btnExp = document.getElementById('gmailBtnExpand');
        const btnClose = document.getElementById('gmailBtnClose');
        const btnDiscard = document.getElementById('gmailDiscardBtn');

        if (btnMin && container) {
            btnMin.addEventListener('click', function () {
                container.classList.toggle('minimized');
            });
        }

        if (btnExp && container) {
            btnExp.addEventListener('click', function () {
                const backdrop = document.getElementById('gmailComposeBackdrop');
                const isExpanded = container.classList.toggle('expanded');
                
                if (isExpanded) {
                    container.classList.remove('minimized');
                    if (backdrop) backdrop.classList.add('active');
                    btnExp.innerHTML = '<i class="ti ti-arrows-minimize"></i>';
                    btnExp.title = 'Pop-in / Exit Fullscreen';
                } else {
                    if (backdrop) backdrop.classList.remove('active');
                    btnExp.innerHTML = '<i class="ti ti-arrows-maximize"></i>';
                    btnExp.title = 'Full screen';
                }
            });
        }

        const backdrop = document.getElementById('gmailComposeBackdrop');
        if (backdrop && container) {
            backdrop.addEventListener('click', function () {
                container.classList.remove('expanded');
                this.classList.remove('active');
                if (btnExp) {
                    btnExp.innerHTML = '<i class="ti ti-arrows-maximize"></i>';
                    btnExp.title = 'Full screen';
                }
            });
        }

        if (btnClose && container) {
            btnClose.addEventListener('click', closeComposer);
        }
        if (btnDiscard && container) {
            btnDiscard.addEventListener('click', closeComposer);
        }

        // Submit Send in Composer
        const btnSend = document.getElementById('gmailSubmitSend');
        if (btnSend) {
            btnSend.addEventListener('click', handleComposerSend);
        }

        // Toggle Formatting Bar
        const btnToggleFmt = document.getElementById('btnToggleFormatting');
        const fmtBar = document.getElementById('gmailFormattingBar');
        if (btnToggleFmt && fmtBar) {
            btnToggleFmt.addEventListener('click', function () {
                fmtBar.classList.toggle('d-none');
                this.classList.toggle('active');
            });
        }

        // Attachment Action Handlers: View, Remove & Re-attach
        const btnPrev = document.getElementById('btnPreviewAttachment');
        if (btnPrev) {
            btnPrev.addEventListener('click', function () {
                if (!currentConfig || !currentConfig.exportApiUrl) return;
                let downloadUrl = currentConfig.exportApiUrl;
                if (currentConfig.ids && currentConfig.ids.length > 0) {
                    downloadUrl += (downloadUrl.includes('?') ? '&' : '?') + 'ids=' + currentConfig.ids.join(',');
                }
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.setAttribute('download', currentConfig.filename || 'export.csv');
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            });
        }

        const btnRem = document.getElementById('btnRemoveAttachment');
        if (btnRem) {
            btnRem.addEventListener('click', function () {
                isAttachmentRemoved = true;
                const pill = document.getElementById('gmailAttachmentPill');
                const detached = document.getElementById('gmailAttachmentDetached');
                if (pill) pill.style.setProperty('display', 'none', 'important');
                if (detached) detached.style.setProperty('display', 'flex', 'important');
            });
        }

        function reattachCsv() {
            isAttachmentRemoved = false;
            const pill = document.getElementById('gmailAttachmentPill');
            const detached = document.getElementById('gmailAttachmentDetached');
            if (pill) pill.style.setProperty('display', 'flex', 'important');
            if (detached) detached.style.setProperty('display', 'none', 'important');
        }

        const btnReattach = document.getElementById('btnReattachAttachment');
        if (btnReattach) {
            btnReattach.addEventListener('click', reattachCsv);
        }

        const fileInput = document.getElementById('gmailCustomFileInput');
        if (fileInput) {
            fileInput.addEventListener('change', function () {
                if (this.files && this.files.length > 0) {
                    Array.from(this.files).forEach(f => customAttachments.push(f));
                    this.value = '';
                    renderCustomAttachments();
                }
            });
        }

        const btnFooterPaperclip = document.getElementById('btnFooterPaperclip');
        if (btnFooterPaperclip) {
            btnFooterPaperclip.addEventListener('click', function () {
                if (isAttachmentRemoved) {
                    reattachCsv();
                }
                const input = document.getElementById('gmailCustomFileInput');
                if (input) input.click();
            });
        }
    }

    let isAttachmentRemoved = false;
    let customAttachments = [];

    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function getFileIconClass(filename) {
        const ext = (filename || '').split('.').pop().toLowerCase();
        if (['pdf'].includes(ext)) return 'ti ti-file-type-pdf text-danger';
        if (['doc', 'docx'].includes(ext)) return 'ti ti-file-type-doc text-primary';
        if (['xls', 'xlsx', 'csv'].includes(ext)) return 'ti ti-file-type-xls text-success';
        if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) return 'ti ti-photo text-info';
        if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return 'ti ti-file-zip text-warning';
        return 'ti ti-file text-secondary';
    }

    function renderCustomAttachments() {
        const container = document.getElementById('gmailCustomAttachmentsList');
        if (!container) return;
        container.innerHTML = '';

        customAttachments.forEach((file, idx) => {
            const pill = document.createElement('div');
            pill.className = 'gmail-attachment-pill shadow-sm';
            pill.style.cssText = 'display: flex !important; background-color: #f8fafc; border: 1px solid #cbd5e1;';

            const iconClass = getFileIconClass(file.name);
            pill.innerHTML = `
                <i class="${iconClass} fs-4 me-2"></i>
                <div class="d-flex flex-column me-auto text-truncate" style="max-width: 250px;">
                    <span class="fw-semibold text-dark small text-truncate" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                    <span class="text-muted" style="font-size: 11px;">${formatFileSize(file.size)} • Custom Attachment</span>
                </div>
                <div class="d-flex align-items-center ms-2">
                    <button type="button" class="btn btn-sm btn-light text-primary border me-1 px-2 py-1 btn-view-custom" style="font-size: 12px;" title="View file">
                        <i class="ti ti-eye me-1"></i>View
                    </button>
                    <button type="button" class="btn btn-sm btn-light text-danger border px-2 py-1 btn-remove-custom" style="font-size: 12px;" title="Remove attachment">
                        <i class="ti ti-x me-1"></i>Remove
                    </button>
                </div>
            `;

            pill.querySelector('.btn-view-custom').addEventListener('click', function () {
                const url = URL.createObjectURL(file);
                window.open(url, '_blank');
            });

            pill.querySelector('.btn-remove-custom').addEventListener('click', function () {
                customAttachments.splice(idx, 1);
                renderCustomAttachments();
            });

            container.appendChild(pill);
        });
    }

    function closeComposer() {
        const container = document.getElementById('gmailComposeContainer');
        const backdrop = document.getElementById('gmailComposeBackdrop');
        const btnExp = document.getElementById('gmailBtnExpand');

        if (container) {
            container.style.setProperty('display', 'none', 'important');
            container.classList.remove('minimized', 'expanded');
        }
        if (backdrop) {
            backdrop.classList.remove('active');
        }
        if (btnExp) {
            btnExp.innerHTML = '<i class="ti ti-arrows-maximize"></i>';
            btnExp.title = 'Full screen';
        }
        currentConfig = null;
        isAttachmentRemoved = false;
        customAttachments = [];
        renderCustomAttachments();
    }

    /**
     * Entry Point: Trigger Export & Mail Workflow
     * @param {Object} config 
     */
    function openExportModal(config) {
        currentConfig = config;

        const defaultSubject = `${config.moduleName} Requests - Ready for UIDAI Processing - CHiPS Portal`;
        const defaultBody = `<p>Respected Sir,</p>
<p>Please find attached the exported dataset of verified <strong>${escapeHtml(config.moduleName)}</strong> requests that are ready to be sent to UIDAI for processing.</p>
<p>Total Records: <strong>${config.recordCount}</strong></p>
<p>Best regards,<br>The CHiPS Aadhaar Admin Team</p>`;

        Swal.fire({
            title: `Export & Mail`,
            html: `
                <div class="export-modal-body" style="text-align: left; font-size: 14px; line-height: 1.5;">
                    <p class="export-modal-desc" style="margin-bottom: 12px;">Send exported CSV containing <strong>${config.recordCount}</strong> pending ${escapeHtml(config.moduleName).toLowerCase()} request(s)?</p>
                    <div class="export-target-box" style="padding: 12px 14px; border-radius: 6px; margin-top: 10px;">
                        <span class="export-target-label" style="font-size: 11px; text-transform: uppercase; font-weight: 700; display: block; margin-bottom: 2px;">TARGET RECIPIENT EMAIL:</span>
                        <strong class="export-target-val" style="font-size: 14px;">${escapeHtml(config.defaultRecipient || 'UIDAI Office')}</strong>
                    </div>
                </div>
            `,
            icon: 'question',
            showCancelButton: true,
            showDenyButton: true,
            confirmButtonText: 'Send Directly',
            confirmButtonColor: '#007bff',
            denyButtonText: 'Edit & Compose Mail',
            denyButtonColor: '#dc2626',
            cancelButtonText: 'Cancel',
            cancelButtonColor: '#6c757d',
            focusConfirm: false,
            customClass: {
                popup: 'doc-preview-modal-smooth'
            }
        }).then((result) => {
            if (result.isConfirmed) {
                // Send Directly
                executeExportAndMail({
                    ids: config.ids ? config.ids.join(',') : '',
                    email_to: config.defaultRecipient,
                    subject: defaultSubject,
                    body_html: defaultBody,
                    attach_csv: true
                });
            } else if (result.isDenied) {
                // Open Gmail Compose Window
                openComposerWindow({
                    to: config.defaultRecipient,
                    subject: defaultSubject,
                    body: defaultBody,
                    filename: config.filename,
                    count: config.recordCount
                });
            }
        });
    }

    function openComposerWindow(opts) {
        const container = document.getElementById('gmailComposeContainer');
        if (!container) return;

        document.getElementById('gmailHeaderTitle').innerText = `Compose Mail - ${currentConfig ? currentConfig.moduleName : ''}`;
        document.getElementById('gmailMailTo').value = opts.to || '';
        document.getElementById('gmailMailCc').value = '';
        document.getElementById('gmailMailBcc').value = '';
        document.getElementById('gmailMailSubject').value = opts.subject || '';
        document.getElementById('gmailAttachmentName').innerText = opts.filename || 'export_dataset.csv';
        document.getElementById('gmailAttachmentInfo').innerText = `${opts.count} record(s) attached`;
        document.getElementById('gmailEditorContent').innerHTML = opts.body || '';

        // Reset attachment UI state
        isAttachmentRemoved = false;
        customAttachments = [];
        renderCustomAttachments();

        const pill = document.getElementById('gmailAttachmentPill');
        const detached = document.getElementById('gmailAttachmentDetached');
        if (pill) pill.style.setProperty('display', 'flex', 'important');
        if (detached) detached.style.setProperty('display', 'none', 'important');

        // Reset rows
        document.getElementById('rowCc').classList.add('d-none');
        document.getElementById('rowBcc').classList.add('d-none');

        container.style.setProperty('display', 'block', 'important');
        container.classList.remove('minimized');
    }

    function readAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve({
                filename: file.name,
                content_type: file.type || 'application/octet-stream',
                content_base64: reader.result
            });
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async function handleComposerSend() {
        if (!currentConfig) return;

        const activeConfig = currentConfig;
        const emailTo = document.getElementById('gmailMailTo').value.trim();
        const emailCc = document.getElementById('gmailMailCc').value.trim();
        const emailBcc = document.getElementById('gmailMailBcc').value.trim();
        const subject = document.getElementById('gmailMailSubject').value.trim();
        const bodyHtml = document.getElementById('gmailEditorContent').innerHTML;

        if (!emailTo) {
            alert('Please specify at least one recipient email address.');
            return;
        }

        let customFilesData = [];
        if (customAttachments.length > 0) {
            try {
                customFilesData = await Promise.all(customAttachments.map(f => readAsBase64(f)));
            } catch (err) {
                console.error("Error reading custom attachments:", err);
                alert("Failed to read attached file(s). Please try again.");
                return;
            }
        }

        // Hide composer window
        const container = document.getElementById('gmailComposeContainer');
        const backdrop = document.getElementById('gmailComposeBackdrop');
        if (container) container.style.setProperty('display', 'none', 'important');
        if (backdrop) backdrop.classList.remove('active');

        executeExportAndMail({
            ids: activeConfig.ids ? activeConfig.ids.join(',') : '',
            email_to: emailTo,
            email_cc: emailCc || null,
            email_bcc: emailBcc || null,
            subject: subject,
            body_html: bodyHtml,
            attach_csv: !isAttachmentRemoved,
            custom_files: customFilesData
        }, activeConfig);
    }

    function executeExportAndMail(payload, activeConfig) {
        const cfg = activeConfig || currentConfig;
        if (!cfg) {
            alert("Export configuration missing. Please try again.");
            return;
        }

        // 1. Trigger CSV File Download in Browser if attachment is included
        if (payload.attach_csv !== false) {
            let downloadUrl = cfg.exportApiUrl;
            if (payload.ids) {
                downloadUrl += (downloadUrl.includes('?') ? '&' : '?') + 'ids=' + payload.ids;
            }
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', cfg.filename || 'export.csv');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        // 2. Display Buffering / Loading Modal
        Swal.fire({
            title: 'Sending Email & Processing...',
            html: `
                <div style="padding: 10px 0; text-align: center;">
                    <p style="font-size: 14px; color: #475569; margin: 0;">
                        Dispatching CSV export & attachments to <strong>${escapeHtml(payload.email_to)}</strong>...
                    </p>
                </div>
            `,
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            customClass: {
                popup: 'doc-preview-modal-smooth'
            },
            didOpen: () => {
                Swal.showLoading();
            }
        });

        // 3. Dispatch Email API POST Request
        fetch(cfg.mailApiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        }).then(async response => {
            let data = null;
            try {
                data = await response.json();
            } catch (e) { }

            if (response.ok && data && (data.success || response.status === 200)) {
                closeComposer();
                Swal.fire({
                    title: 'Email Sent Successfully!',
                    text: (data && data.detail) ? data.detail : `Export CSV emailed successfully to ${payload.email_to} and request moved to Under Processing queue.`,
                    icon: 'success',
                    confirmButtonText: 'OK',
                    confirmButtonColor: '#007bff',
                    customClass: {
                        popup: 'doc-preview-modal-smooth'
                    }
                }).then(() => {
                    if (typeof cfg.onSuccess === 'function') {
                        cfg.onSuccess();
                    } else {
                        sessionStorage.setItem('chips_action_reloading', 'true');
                        window.location.reload();
                    }
                });
            } else {
                Swal.fire({
                    title: 'Failed to Send Email',
                    text: (data && data.detail) ? data.detail : 'Error occurred while sending export email.',
                    icon: 'error',
                    confirmButtonColor: '#dc2626',
                    customClass: {
                        popup: 'doc-preview-modal-smooth'
                    }
                });
            }
        }).catch(err => {
            console.error(err);
            Swal.fire({
                title: 'Connection Error',
                text: 'Could not connect to server to send export email.',
                icon: 'error',
                confirmButtonColor: '#dc2626',
                customClass: {
                    popup: 'doc-preview-modal-smooth'
                }
            });
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        openExportModal: openExportModal,
        closeComposer: closeComposer
    };
})();
