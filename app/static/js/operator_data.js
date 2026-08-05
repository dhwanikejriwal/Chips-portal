/* Operator Data Management — upload + Aadhar search.
   Serves two mounts: the full admin page under /auth/chips/operator-data and
   the search-only DC page under /auth/dc/operator-data. The proxy prefix comes
   from data-api-base, so the same script drives both.
   All calls go through the Flask proxy, which attaches the session bearer
   token; no token is ever exposed to this script. The Aadhar typed into the
   search box is sent once and never stored client-side. */
(function () {
    "use strict";

    const root = document.getElementById("odRoot");
    if (!root) return;

    const BASE = root.dataset.apiBase || "/auth/chips/operator-data";
    const canReveal = root.dataset.canReveal === "1";

    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
        (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    function toast(icon, title, text) {
        if (window.Swal) Swal.fire({ icon, title, text, confirmButtonColor: "#378ADD" });
        else alert(title + (text ? "\n\n" + text : ""));
    }

    /* ===================================================================
       TABS — Upload data / Search operator
       The chosen tab is remembered per browser so a reload (e.g. after an
       upload) does not bounce the user back to the other panel.
       =================================================================== */
    const TAB_KEY = "od-active-tab";
    const tabs = Array.from(document.querySelectorAll(".od-tab"));
    // The DC page renders the search panel only, so build this from whatever
    // is actually present rather than assuming both exist.
    const panels = {};
    ["upload", "search"].forEach((name) => {
        const el = $("odPanel" + name[0].toUpperCase() + name.slice(1));
        if (el) panels[name] = el;
    });

    function selectTab(name) {
        if (!panels[name]) return;
        tabs.forEach((t) => {
            const on = t.dataset.tab === name;
            t.classList.toggle("active", on);
            t.setAttribute("aria-selected", String(on));
        });
        Object.entries(panels).forEach(([key, el]) => { el.hidden = key !== name; });
        try { localStorage.setItem(TAB_KEY, name); } catch (e) { /* private mode */ }
    }

    tabs.forEach((t) => t.addEventListener("click", () => selectTab(t.dataset.tab)));

    // Restore the last tab, defaulting to "search" tab first.
    try {
        const saved = localStorage.getItem(TAB_KEY);
        if (saved && (saved === "search" || (saved === "upload" && canReveal))) {
            selectTab(saved);
        } else {
            selectTab("search");
        }
    } catch (e) {
        selectTab("search");
    }

    /* ===================================================================
       FEATURE 1 — Upload
       =================================================================== */
    const form = $("odUploadForm");
    if (form) {
        const drop = $("odDrop");
        const fileInput = $("odFile");
        const chip = $("odFileChip");
        const chipName = $("odFileName");
        const uploadBtn = $("odUploadBtn");
        const ALLOWED = /\.(csv|xlsx|xls)$/i;
        let invalidRows = [];

        function setFile(file) {
            if (file && !ALLOWED.test(file.name)) {
                toast("error", "Unsupported file", "Choose a .csv, .xlsx or .xls file.");
                return;
            }
            if (file) {
                const dt = new DataTransfer();
                dt.items.add(file);
                fileInput.files = dt.files;
            } else {
                fileInput.value = "";
            }
            const picked = fileInput.files[0];
            chip.hidden = !picked;
            chipName.textContent = picked ? picked.name : "";
            uploadBtn.disabled = !picked;
        }

        fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
        $("odFileClear").addEventListener("click", () => setFile(null));

        drop.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
        });
        ["dragenter", "dragover"].forEach((evt) =>
            drop.addEventListener(evt, (e) => { e.preventDefault(); drop.classList.add("is-dragging"); }));
        ["dragleave", "drop"].forEach((evt) =>
            drop.addEventListener(evt, (e) => { e.preventDefault(); drop.classList.remove("is-dragging"); }));
        drop.addEventListener("drop", (e) => {
            const file = e.dataTransfer && e.dataTransfer.files[0];
            if (file) setFile(file);
        });

        const SUMMARY_KEY = "od-last-upload-summary";

        function renderSummary(data, isRestored = false) {
            if (!data) return;
            $("odSummaryEmpty").hidden = true;
            $("odSummaryBody").hidden = false;
            $("odStatAdded").textContent = (data.inserted || 0).toLocaleString();
            $("odStatDupe").textContent = (data.duplicates || 0).toLocaleString();
            $("odStatBad").textContent = (data.invalid || 0).toLocaleString();

            invalidRows = data.invalid_rows || [];
            const block = $("odInvalidBlock");
            block.hidden = invalidRows.length === 0;
            $("odInvalidBody").innerHTML = invalidRows.map((r) => `
                <tr>
                    <td>${esc(r.row)}</td>
                    <td>${esc(r.name) || "—"}</td>
                    <td>${esc(r.registrar_code) || "—"}</td>
                    <td>${esc(r.operator_code) || "—"}</td>
                    <td>${esc(r.status) || "—"}</td>
                    <td>${esc(r.reason)}</td>
                </tr>`).join("");

            const note = $("odInvalidNote");
            note.hidden = !data.invalid_truncated;
            if (data.invalid_truncated) {
                note.textContent = `Showing the first ${invalidRows.length} of ${data.invalid} rejected rows.`;
            }

            if (!isRestored) {
                try {
                    localStorage.setItem(SUMMARY_KEY, JSON.stringify(data));
                } catch (e) {}
            }
        }

        // Restore last upload summary on page refresh if available
        try {
            const savedSummary = localStorage.getItem(SUMMARY_KEY);
            if (savedSummary) {
                const parsed = JSON.parse(savedSummary);
                if (parsed) renderSummary(parsed, true);
            }
        } catch (e) {}

        $("odInvalidDownload").addEventListener("click", () => {
            if (!invalidRows.length) return;
            const csv = ["Row,Name,Registrar code,Operator code,Status,Reason"].concat(
                invalidRows.map((r) => [r.row, r.name, r.registrar_code, r.operator_code, r.status, r.reason]
                    .map((v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`).join(","))
            ).join("\r\n");
            const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = "rejected_operator_rows.csv";
            a.click();
            URL.revokeObjectURL(url);
        });

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const file = fileInput.files[0];
            if (!file) return;

            // Agency comes from the file's own Agency column; rows without one
            // are stored with no agency and display as "—".
            const body = new FormData();
            body.append("file", file);

            const label = uploadBtn.innerHTML;
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = '<i class="ti ti-loader-2"></i> Processing…';
            try {
                const resp = await fetch(`${BASE}/api-upload`, { method: "POST", body });
                const data = await resp.json().catch(() => ({}));
                if (!resp.ok) throw new Error(data.detail || `Upload failed (${resp.status}).`);
                renderSummary(data);
                toast("success", "Upload processed",
                    `${data.inserted} added · ${data.duplicates} duplicates skipped · ${data.invalid} rejected.`);
                setFile(null);
            } catch (err) {
                toast("error", "Upload failed", err.message);
            } finally {
                uploadBtn.innerHTML = label;
                uploadBtn.disabled = !fileInput.files[0];
            }
        });
    }

    /* ===================================================================
       FEATURE 2 — Search by Aadhar
       =================================================================== */
    const searchForm = $("odSearchForm");
    const input = $("odSearchInput");
    const errorEl = $("odSearchError");
    const tableWrap = $("odResultsTableWrap");
    const tbody = $("odResultsBody");

    // Digits only, grouped 1234 5678 9012 for readability while typing.
    input.addEventListener("input", () => {
        const digits = input.value.replace(/\D/g, "").slice(0, 12);
        input.value = digits.replace(/(\d{4})(?=\d)/g, "$1 ").trim();
        errorEl.hidden = true;
    });

    function showState({ empty = false, noData = false, table = false }) {
        $("odResultsEmpty").hidden = !empty;
        $("odNoData").hidden = !noData;
        tableWrap.hidden = !table;
    }

    // DEBOARDED-style statuses read as negative, ACTIVE/ONBOARDED as positive;
    // anything else stays neutral rather than guessing.
    function statusClass(status) {
        const s = String(status || "").toUpperCase();
        if (/DEBOARD|INACTIVE|SUSPEND|REJECT|BLOCK/.test(s)) return "od-status-off";
        if (/ONBOARD|ACTIVE|APPROVED|DONE/.test(s)) return "od-status-on";
        return "od-status-neutral";
    }

    function rowHtml(rec) {
        const reveal = canReveal
            ? `<button type="button" class="od-reveal" data-id="${rec.id}">
                   <i class="ti ti-eye"></i> Reveal</button>`
            : "";
        return `
            <tr data-id="${rec.id}">
                <td class="od-name">${esc(rec.name)}</td>
                <td><span class="od-agency-pill">${esc(rec.agency)}</span></td>
                <td>${esc(rec.registrar_code)}</td>
                <td class="od-mono">${esc(rec.operator_code)}</td>
                <td><span class="od-status ${statusClass(rec.status)}">${esc(rec.status)}</span></td>
                <td>
                    <div class="od-aadhar-cell">
                        <span class="od-aadhar-value" data-masked="${esc(rec.aadhar_masked)}">${esc(rec.aadhar_masked)}</span>
                        ${reveal}
                    </div>
                </td>
                <td>${esc(rec.created_at)}</td>
            </tr>`;
    }

    /* ---- Mode switcher: full Aadhar vs. name + last 4 ---- */
    const nameForm = $("odNameForm");
    const modeButtons = Array.from(document.querySelectorAll(".od-mode"));

    function selectMode(mode) {
        modeButtons.forEach((b) => {
            const on = b.dataset.mode === mode;
            b.classList.toggle("active", on);
            b.setAttribute("aria-selected", String(on));
        });
        searchForm.hidden = mode !== "aadhar";
        nameForm.hidden = mode !== "name";
        errorEl.hidden = true;
        $("odEmptyTitle").textContent = mode === "aadhar"
            ? "Enter an Aadhar number to search"
            : "Search by name and the last 4 digits of the Aadhar";
        $("odNoDataSub").textContent = mode === "aadhar"
            ? "No operator record matches that Aadhar number."
            : "No operator matches that name and those last 4 digits.";
        // Switching modes clears stale results from the other mode.
        showState({ empty: true });
    }

    modeButtons.forEach((b) => b.addEventListener("click", () => selectMode(b.dataset.mode)));

    const last4 = $("odLast4Input");
    last4.addEventListener("input", () => {
        last4.value = last4.value.replace(/\D/g, "").slice(0, 4);
        errorEl.hidden = true;
    });

    /* ---- Shared request runner for both modes ---- */
    async function runSearch(url, btn) {
        const label = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="ti ti-loader-2"></i> Searching…';
        try {
            const resp = await fetch(url);
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(data.detail || `Search failed (${resp.status}).`);

            if (!data.count) {
                showState({ noData: true });
            } else {
                tbody.innerHTML = data.results.map(rowHtml).join("");
                showState({ table: true });
            }
        } catch (err) {
            errorEl.textContent = err.message;
            errorEl.hidden = false;
            showState({ empty: true });
        } finally {
            btn.innerHTML = label;
            btn.disabled = false;
        }
    }

    // Mode 1 — full Aadhar (unchanged behaviour).
    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const aadhar = input.value.replace(/\D/g, "");
        if (aadhar.length !== 12) {
            errorEl.textContent = "Enter a valid 12-digit Aadhar number.";
            errorEl.hidden = false;
            return;
        }
        errorEl.hidden = true;
        runSearch(`${BASE}/api-search?aadhar=${encodeURIComponent(aadhar)}`, $("odSearchBtn"));
    });

    // Mode 2 — name + last 4, with an optional narrowing code.
    nameForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const name = $("odNameInput").value.trim();
        const digits = last4.value.replace(/\D/g, "");
        if (!name) {
            errorEl.textContent = "Enter the operator's name.";
            errorEl.hidden = false;
            return;
        }
        if (digits.length !== 4) {
            errorEl.textContent = "Enter exactly the last 4 digits of the Aadhar number.";
            errorEl.hidden = false;
            return;
        }
        errorEl.hidden = true;
        const qs = new URLSearchParams({
            name: name,
            last4: digits,
            code: $("odCodeInput").value.trim(),
        });
        runSearch(`${BASE}/api-search-by-name?${qs}`, $("odNameBtn"));
    });

    // Reveal — decryption happens server-side; this only swaps the displayed text.
    tbody.addEventListener("click", async (e) => {
        const btn = e.target.closest(".od-reveal");
        if (!btn) return;
        const cell = btn.closest(".od-aadhar-cell").querySelector(".od-aadhar-value");

        if (btn.dataset.shown === "1") {
            cell.textContent = cell.dataset.masked;
            btn.dataset.shown = "0";
            btn.innerHTML = '<i class="ti ti-eye"></i> Reveal';
            return;
        }

        btn.disabled = true;
        try {
            const resp = await fetch(`${BASE}/api-reveal`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ record_id: Number(btn.dataset.id) }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) throw new Error(data.detail || "Unable to reveal this record.");
            cell.textContent = String(data.aadhar).replace(/(\d{4})(?=\d)/g, "$1 ");
            btn.dataset.shown = "1";
            btn.innerHTML = '<i class="ti ti-eye-off"></i> Hide';
        } catch (err) {
            toast("error", "Reveal failed", err.message);
        } finally {
            btn.disabled = false;
        }
    });
})();
