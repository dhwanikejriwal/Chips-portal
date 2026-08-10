/* Operator Activity dashboard — talks to the FastAPI backend via the Flask
   proxy at /auth/chips/operator-activity/*. All aggregation is server-side. */
(function () {
  "use strict";

  console.log("[operator-activity] script build v7 loaded");

  var isDC = window.location.pathname.indexOf("/dc/") !== -1;
  var prefix = isDC ? "/auth/dc/operator-activity" : "/auth/chips/operator-activity";
  var API = prefix + "/api";        // GET proxy prefix
  var UPLOAD_URL = prefix + "/api-upload";
  var EXPORT_URL = prefix + "/api-export";

  // Hide upload button for DC users
  if (isDC) {
    document.addEventListener("DOMContentLoaded", function() {
      var btn = document.getElementById("oaUploadBtn");
      if (btn) btn.style.display = "none";
    });
  }

  var MEASURES = [
    ["New_Aadhaar_Enrolment", "New Enrolment"],
    ["New_Aadhar_18_plus", "18+"],
    ["Total_Updates", "Updates"],
    ["Total_Demographic_Updates", "Demo Upd"],
    ["Total_Biometric_Updates", "Bio Upd"],
    ["IS_MBU", "MBU"],
    ["NON_MBU", "Non-MBU"],
    ["COUNT_6AM_TO_10PM", "Day (6a-10p)"],
    ["COUNT_10PM_TO_6AM", "Night (10p-6a)"],
    ["Total_Enrollment_and_Updates", "Total E&U"],
  ];

  // ── helpers ──
  function $(id) { return document.getElementById(id); }
  function inr(n) {
    if (n === null || n === undefined || n === "" || isNaN(n)) return "0";
    var s = String(Math.round(n)); var neg = s[0] === "-"; if (neg) s = s.slice(1);
    var last3 = s.slice(-3), rest = s.slice(0, -3);
    if (rest) last3 = "," + last3;
    rest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",");
    return (neg ? "-" : "") + rest + last3;
  }
  function fmtDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  }
  function txt(v) { return (v === null || v === undefined || v === "") ? "—" : v; }
  function fmtDist(d) {
    if (!d || d === "—") return "—";
    var s = String(d).trim();
    s = s.replace(/â€“|â€”|â€|–|—/g, "-");
    s = s.replace(/manendragarh[- ]?chirmiri[- ]?bharatpur(\s*\(m\s*c\s*b\))?/i, "Manendragarh-Chirmiri-Bharatpur (MCB)");
    return s;
  }
  // Compliance marker: all three Kit Tracker statuses active vs. any inactive.
  function statusCell(flag) {
    var map = {
      active: ["oa-mark-active", "●", "Operator, station & onboarding all Active"],
      inactive: ["oa-mark-inactive", "▲", "One or more of operator / station / onboarding is Inactive"],
      unknown: ["oa-mark-unknown", "–", "No Kit Tracker record (status unknown)"]
    };
    var m = map[flag] || map.unknown;
    return '<td class="oa-num"><span class="oa-mark ' + m[0] + '" title="' + m[2] + '">' + m[1] + '</span></td>';
  }
  function api(path, params) {
    var qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return fetch(API + "/" + path + qs, { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) return r.json().then(function (e) { throw e; }); return r.json(); });
  }

  // ── filter state (serialised to URL) ──
  var state = {
    section: "activity",
    dateMode: "range", preset: "last30", from: null, to: null,
    districts: [], eaCodes: [],
    search: "", offHours: false, model: "",
    // "all" | "anomalies" — the section tab currently shown
    view: "all",
    groupBy: "operator", sortBy: "Total_Enrollment_and_Updates", sortDir: "desc",
    page: 1, pageSize: 50,
    anomPage: 1, anomSortBy: "", anomSortDir: "desc",
  };

  function todayISO(offset) {
    var d = new Date(); d.setDate(d.getDate() + (offset || 0));
    return d.toISOString().slice(0, 10);
  }
  function applyPreset(p) {
    var now = new Date(), y = now.getFullYear(), m = now.getMonth();
    if (p === "today") { state.from = state.to = todayISO(0); }
    else if (p === "yesterday") { state.from = state.to = todayISO(-1); }
    else if (p === "last7") { state.from = todayISO(-6); state.to = todayISO(0); }
    else if (p === "last30") { state.from = todayISO(-29); state.to = todayISO(0); }
    else if (p === "thismonth") { state.from = new Date(y, m, 1).toISOString().slice(0, 10); state.to = todayISO(0); }
    else if (p === "lastmonth") { state.from = new Date(y, m - 1, 1).toISOString().slice(0, 10); state.to = new Date(y, m, 0).toISOString().slice(0, 10); }
  }

  function serialiseURL() {
    var p = new URLSearchParams();
    ["from", "to", "search", "groupBy", "sortBy", "sortDir"].forEach(function (k) { if (state[k]) p.set(k, state[k]); });
    if (state.offHours) p.set("offHours", "1");
    if (state.model) p.set("model", state.model);
    if (state.view !== "all") p.set("view", state.view);
    if (state.districts.length) p.set("districts", state.districts.join(","));
    if (state.eaCodes.length) p.set("eaCodes", state.eaCodes.join(","));
    p.set("page", state.page); p.set("pageSize", state.pageSize);
    history.replaceState(null, "", "?" + p.toString());
  }
  function loadURL() {
    var p = new URLSearchParams(location.search);
    if (p.get("from")) { state.from = p.get("from"); state.preset = "custom"; }
    if (p.get("to")) state.to = p.get("to");
    if (p.get("search")) state.search = p.get("search");
    if (p.get("groupBy")) state.groupBy = p.get("groupBy");
    if (p.get("sortBy")) state.sortBy = p.get("sortBy");
    if (p.get("sortDir")) state.sortDir = p.get("sortDir");
    if (p.get("offHours")) state.offHours = true;
    if (p.get("model")) state.model = p.get("model");
    if (p.get("view") === "anomalies") state.view = "anomalies";
    if (p.get("districts")) state.districts = p.get("districts").split(",");
    if (p.get("eaCodes")) state.eaCodes = p.get("eaCodes").split(",").map(Number);
    if (p.get("page")) state.page = +p.get("page");
    if (p.get("pageSize")) state.pageSize = +p.get("pageSize");
  }

  // ── query params for the API ──
  function activityParams() {
    var pr = {};
    if (state.from) pr.from = state.from;
    if (state.to) pr.to = state.dateMode === "single" ? state.from : state.to;
    if (state.districts.length) pr.districts = state.districts;
    if (state.eaCodes.length) pr.eaCodes = state.eaCodes;
    if (state.search) pr.search = state.search;
    if (state.offHours) pr.offHoursOnly = "true";
    if (state.model) pr.model = state.model;
    pr.groupBy = state.groupBy; pr.sortBy = state.sortBy; pr.sortDir = state.sortDir;
    pr.page = state.page; pr.pageSize = state.pageSize;
    // URLSearchParams handles arrays only via repeated keys — build manually
    var usp = new URLSearchParams();
    Object.keys(pr).forEach(function (k) {
      if (Array.isArray(pr[k])) pr[k].forEach(function (v) { usp.append(k, v); });
      else usp.append(k, pr[k]);
    });
    return usp;
  }

  // ── summary cards ──
  function renderCards(sum) {
    var cards = [
      ["Total Enrolments & Updates", sum.Total_Enrollment_and_Updates, pctSub(sum)],
      ["New Aadhaar Enrolments", sum.New_Aadhaar_Enrolment],
      ["New Aadhaar 18+", sum.New_Aadhar_18_plus],
      ["Total Updates", sum.Total_Updates],
      ["Demographic Updates", sum.Total_Demographic_Updates],
      ["Biometric Updates", sum.Total_Biometric_Updates, "MBU " + inr(sum.IS_MBU) + " · Non-MBU " + inr(sum.NON_MBU)],
      ["Active Operators", sum.active_operators],
    ];
    $("oaCards").innerHTML = cards.map(function (c) {
      return '<div class="oa-card"><div class="oa-card-label">' + c[0] + '</div>' +
        '<div class="oa-card-value">' + inr(c[1]) + '</div>' +
        (c[2] ? '<div class="oa-card-sub">' + c[2] + '</div>' : '') + '</div>';
    }).join("");
  }
  function pctSub(sum) {
    if (sum.pct_change_total === null || sum.pct_change_total === undefined) return "";
    var up = sum.pct_change_total >= 0;
    return '<span class="' + (up ? "oa-delta-up" : "oa-delta-down") + '">' +
      (up ? "▲ " : "▼ ") + Math.abs(sum.pct_change_total) + "% vs prev</span>";
  }

  // ── table ──
  function renderTable(data) {
    var daily = state.groupBy === "daily";
    var head = [];
    head.push([null, "Status", false]);
    if (daily) head.push(["activity_date", "Date", false]);
    head.push(["session_operator_id", "Operator ID", false]);
    head.push([null, "Operator Name", false]);
    head.push([null, "Model", false]);
    head.push(["station_ea_code", "EA", true]);
    head.push(["station_number", "Station", true]);
    head.push(["machine_district", "District", false]);
    MEASURES.forEach(function (m) { head.push([m[0], m[1], true]); });
    if (!daily) { head.push(["days_active", "Days Active", true]); }

    $("oaThead").innerHTML = "<tr>" + head.map(function (h) {
      var ind = h[0] === state.sortBy ? '<span class="oa-sort-ind">' + (state.sortDir === "desc" ? "▼" : "▲") + "</span>" : "";
      return '<th class="' + (h[2] ? "oa-num" : "") + '" data-sort="' + (h[0] || "") + '">' + h[1] + " " + ind + "</th>";
    }).join("") + "</tr>";

    var rows = data.rows;
    if (!rows.length) {
      $("oaTbody").innerHTML = ""; $("oaTfoot").innerHTML = "";
      var e = $("oaEmpty"); e.hidden = false;
      e.innerHTML = "No activity for these filters. <button class='oa-link' id='oaEmptyReset'>Widen the date range / reset</button>";
      $("oaEmptyReset").onclick = resetFilters;
      return;
    }
    $("oaEmpty").hidden = true;
    $("oaTbody").innerHTML = rows.map(function (r) {
      var tds = [];
      tds.push(statusCell(r.status_flag));
      if (daily) tds.push('<td>' + fmtDate(r.activity_date) + '</td>');
      tds.push('<td class="oa-freeze oa-mono notranslate" translate="no" data-no-i18n="true"><span class="notranslate" translate="no">' + txt(r.session_operator_id) + '</span></td>');
      tds.push('<td>' + txt(r.operator_name) + '</td>');
      var mdl = r.model || "";
      tds.push('<td>' + (mdl ? '<span class="oa-model oa-model-' + mdl.toLowerCase() + '">' + mdl + '</span>' : "—") + '</td>');
      tds.push('<td class="oa-num">' + txt(r.station_ea_code) + '</td>');
      var stationCell = txt(r.station_number);
      if (!daily && r.stations_count > 1) stationCell += ' <span class="oa-badge">+' + (r.stations_count - 1) + '</span>';
      tds.push('<td class="oa-num">' + stationCell + '</td>');
      tds.push('<td>' + txt(fmtDist(r.machine_district)) + '</td>');
      MEASURES.forEach(function (m) {
        var off = m[0] === "COUNT_10PM_TO_6AM" && r[m[0]] > 0;
        tds.push('<td class="oa-num' + (off ? " oa-offhours" : "") + '">' + inr(r[m[0]]) + '</td>');
      });
      if (!daily) { tds.push('<td class="oa-num">' + txt(r.days_active) + '</td>'); }
      return '<tr tabindex="0" role="button" data-sid="' + encodeURIComponent(r.session_operator_id) + '">' + tds.join("") + '</tr>';
    }).join("");

    // footer totals over full filtered set
    var t = data.totals, foot = [];
    var lead = daily ? 8 : 7;
    foot.push('<td colspan="' + lead + '" style="text-align:left">Totals (all filtered)</td>');
    MEASURES.forEach(function (m) { foot.push('<td>' + inr(t[m[0]]) + '</td>'); });
    if (!daily) foot.push('<td></td>');
    $("oaTfoot").innerHTML = "<tr>" + foot.join("") + "</tr>";

    // row click -> drill-down
    Array.prototype.forEach.call($("oaTbody").querySelectorAll("tr"), function (tr) {
      function open() { openDrill(decodeURIComponent(tr.getAttribute("data-sid"))); }
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    });
    // header sort
    Array.prototype.forEach.call($("oaThead").querySelectorAll("th"), function (th) {
      var col = th.getAttribute("data-sort");
      if (!col) return;
      th.addEventListener("click", function () {
        if (state.sortBy === col) state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
        else { state.sortBy = col; state.sortDir = "desc"; }
        state.page = 1; loadActivity();
      });
    });
  }

  function renderPager(pg) {
    $("oaPager").innerHTML =
      '<span>Page ' + pg.page + ' / ' + Math.max(1, pg.pages) + ' · ' + inr(pg.total) + ' rows</span>' +
      '<button id="oaPrev"' + (pg.page <= 1 ? " disabled" : "") + '>Prev</button>' +
      '<button id="oaNext"' + (pg.page >= pg.pages ? " disabled" : "") + '>Next</button>';
    $("oaPrev").onclick = function () { if (state.page > 1) { state.page--; loadActivity(); } };
    $("oaNext").onclick = function () { if (state.page < pg.pages) { state.page++; loadActivity(); } };
  }

  // The list endpoint is the router root; call it directly with the query string.
  function loadActivity() {
    serialiseURL();
    $("oaRangeLabel").textContent = state.from ?
      (fmtDate(state.from) + (state.dateMode === "single" ? "" : " – " + fmtDate(state.to))) : "All dates";
    apiActivity().then(function (data) {
      renderCards(data.summary); renderTable(data); renderPager(data.pagination);
    }).catch(function (e) {
      $("oaEmpty").hidden = false;
      $("oaEmpty").innerHTML = "Error: " + (e.detail || "failed to load") + " <button class='oa-link' id='oaRetry'>Retry</button>";
      var rb = $("oaRetry"); if (rb) rb.onclick = loadActivity;
    });
  }

  function apiActivity() {
    return fetch("/auth/chips/operator-activity/api-list?" + activityParams().toString(), { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) return r.json().then(function (e) { throw e; }); return r.json(); });
  }

  // ── Operator Anomalies subsection ──
  // Reconciliation of the uploaded logs against the Kit Tracker. The backend
  // returns only flagged operator/station records, each with its reason(s).
  // [key, label, cellClass, numeric] — key doubles as the server sort column.
  var ANOM_COLS = [
    ["session_operator_id", "Operator ID", "oa-freeze oa-mono notranslate", false],
    ["operator_name", "Operator Name", "", false],
    ["station_number", "Station ID", "oa-num", true],
    ["station_ea_code", "EA", "oa-num", true],
    ["machine_district", "District", "", false],
    ["model", "Model", "", false],
    ["kit_tracker_operator", "Kit Tracker Operator", "oa-mono notranslate", false],
    ["kit_tracker_operator_name", "Kit Tracker Operator Name", "", false],
    ["days_active", "Days Active", "oa-num", true],
    ["Total_Enrollment_and_Updates", "Total E&U", "oa-num", true],
    ["reason", "Reason", "oa-reason", false],
  ];

  function esc(v) {
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function anomParams() {
    var usp = new URLSearchParams();
    if (state.from) usp.append("from", state.from);
    if (state.to) usp.append("to", state.dateMode === "single" ? state.from : state.to);
    state.districts.forEach(function (d) { usp.append("districts", d); });
    if (state.search) usp.append("search", state.search);
    if (state.anomSortBy) { usp.append("sortBy", state.anomSortBy); usp.append("sortDir", state.anomSortDir); }
    usp.append("page", state.anomPage);
    usp.append("pageSize", state.pageSize);
    return usp;
  }

  function loadAnomalies() {
    serialiseURL();
    $("oaRangeLabel").textContent = state.from ?
      (fmtDate(state.from) + (state.dateMode === "single" ? "" : " – " + fmtDate(state.to))) : "All dates";
    api("anomalies", anomParams()).then(renderAnomalies).catch(function (e) {
      $("oaAnomEmpty").hidden = false;
      $("oaAnomEmpty").innerHTML = "Error: " + (e.detail || "failed to load anomalies");
    });
  }

  function renderAnomalies(data) {
    var s = data.summary;
    $("oaAnomCards").innerHTML = [
      ["Flagged Records", s.flagged_records],
      ["Flagged Operators", s.flagged_operators],
      ["Records Checked", s.records_checked],
    ].map(function (c) {
      return '<div class="oa-card"><div class="oa-card-label">' + c[0] + '</div>' +
        '<div class="oa-card-value">' + inr(c[1]) + '</div></div>';
    }).join("");

    // Reason breakdown — a record can trip more than one check, so these
    // counts overlap and do not sum to the flagged-record total.
    var labels = data.reason_labels || {};
    var chips = Object.keys(labels).filter(function (k) { return s.by_reason[k]; })
      .map(function (k) {
        return '<span class="oa-anom-chip"><b>' + inr(s.by_reason[k]) + '</b> ' + esc(labels[k]) + '</span>';
      }).join("");
    $("oaAnomLegend").innerHTML = chips;

    $("oaAnomThead").innerHTML = "<tr>" + ANOM_COLS.map(function (c) {
      var ind = c[0] === state.anomSortBy
        ? '<span class="oa-sort-ind">' + (state.anomSortDir === "desc" ? "▼" : "▲") + "</span>" : "";
      var cls = (c[3] ? "oa-num " : "") + (c[2].indexOf("oa-freeze") >= 0 ? "oa-freeze" : "");
      return '<th class="' + cls.trim() + '" data-sort="' + c[0] + '">' + c[1] + " " + ind + '</th>';
    }).join("") + "</tr>";

    if (!data.rows.length) {
      $("oaAnomTbody").innerHTML = ""; $("oaAnomTfoot").innerHTML = "";
      var e = $("oaAnomEmpty"); e.hidden = false;
      e.innerHTML = "No anomalies found — every operator/station log record reconciles with the Kit Tracker for these filters.";
      renderAnomPager(data.pagination);
      bindAnomSort();
      return;
    }
    $("oaAnomEmpty").hidden = true;

    $("oaAnomTbody").innerHTML = data.rows.map(function (r) {
      var tds = ANOM_COLS.map(function (c) {
        var key = c[0], v = r[key];
        if (key === "model") {
          return '<td><span class="oa-model oa-model-' + String(v).toLowerCase() + '">' + esc(v) + '</span></td>';
        }
        // Reasons stack vertically one below another for clear readability
        if (key === "reason") {
          return '<td class="oa-reason" title="' + esc(v) + '">' + r.reason_codes.map(function (code) {
            return '<span class="oa-reason-tag oa-reason-' + code + '">' + esc(labels[code] || code) + '</span>';
          }).join("") + '</td>';
        }
        if (c[3]) return '<td class="oa-num">' + (v === null || v === undefined ? "—" : inr(v)) + '</td>';
        if (key === "machine_district") v = fmtDist(v);
        var isNoTrans = (c[2] && c[2].indexOf("notranslate") >= 0) || key === "session_operator_id" || key === "kit_tracker_operator";
        return '<td class="' + c[2] + '"' + (isNoTrans ? ' translate="no" data-no-i18n="true"' : '') + '>' +
          (v === null || v === undefined || v === "" ? "—" : (isNoTrans ? '<span class="notranslate" translate="no">' + esc(v) + '</span>' : esc(v))) + '</td>';
      });
      return '<tr tabindex="0" role="button" data-sid="' + encodeURIComponent(r.session_operator_id) + '">' + tds.join("") + '</tr>';
    }).join("");

    // Footer totals over the whole flagged set, matching the main table.
    var t = data.totals || {};
    $("oaAnomTfoot").innerHTML = "<tr>" +
      '<td colspan="8" style="text-align:left">Totals (all flagged)</td>' +
      '<td>' + inr(t.days_active) + '</td>' +
      '<td>' + inr(t.Total_Enrollment_and_Updates) + '</td><td></td></tr>';

    Array.prototype.forEach.call($("oaAnomTbody").querySelectorAll("tr"), function (tr) {
      function open() { openDrill(decodeURIComponent(tr.getAttribute("data-sid"))); }
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); }
      });
    });
    bindAnomSort();
    renderAnomPager(data.pagination);
  }

  function bindAnomSort() {
    Array.prototype.forEach.call($("oaAnomThead").querySelectorAll("th"), function (th) {
      var col = th.getAttribute("data-sort");
      if (!col) return;
      th.addEventListener("click", function () {
        if (state.anomSortBy === col) state.anomSortDir = state.anomSortDir === "desc" ? "asc" : "desc";
        else { state.anomSortBy = col; state.anomSortDir = "desc"; }
        state.anomPage = 1; loadAnomalies();
      });
    });
  }

  function renderAnomPager(pg) {
    $("oaAnomPager").innerHTML =
      '<span>Page ' + pg.page + ' / ' + Math.max(1, pg.pages) + ' · ' + inr(pg.total) + ' flagged rows</span>' +
      '<button id="oaAnomPrev"' + (pg.page <= 1 ? " disabled" : "") + '>Prev</button>' +
      '<button id="oaAnomNext"' + (pg.page >= pg.pages ? " disabled" : "") + '>Next</button>';
    $("oaAnomPrev").onclick = function () { if (state.anomPage > 1) { state.anomPage--; loadAnomalies(); } };
    $("oaAnomNext").onclick = function () { if (state.anomPage < pg.pages) { state.anomPage++; loadAnomalies(); } };
  }

  // Single entry point so every filter change refreshes whichever view is open.
  function loadCurrentView() {
    if (state.view === "anomalies") loadAnomalies();
    else loadActivity();
  }

  // ── filters UI ──
  function loadFilters() {
    return api("filters").then(function (f) {
      var sel = $("oaDistrict");
      var current = state.districts[0] || "";
      var seen = {};
      var opts = [];
      (f.districts || []).forEach(function (d) {
        var cleanD = fmtDist(d);
        if (cleanD && cleanD !== "—" && !seen[cleanD]) {
          seen[cleanD] = true;
          opts.push(cleanD);
        }
      });
      opts.sort();
      sel.innerHTML = '<option value="">All districts</option>' +
        opts.map(function (d) {
          var esc = String(d).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
          return '<option value="' + esc + '"' + (fmtDist(current) === d ? " selected" : "") + '>' + esc + '</option>';
        }).join("");
    });
  }

  function resetFilters() {
    state.districts = []; state.eaCodes = []; state.model = "";
    state.search = ""; state.offHours = false; state.preset = "last30";
    state.dateMode = "range"; state.groupBy = "operator";
    // clear district checkboxes handled by loadFilters() re-render below
    state.sortBy = "Total_Enrollment_and_Updates"; state.sortDir = "desc"; state.page = 1;
    state.anomPage = 1;
    applyPreset("last30");
    syncControls(); loadFilters().then(loadCurrentView);
  }

  function syncControls() {
    $("oaFrom").value = state.from || ""; $("oaTo").value = state.to || "";
    if (state.from) $("oaTo").min = state.from; else $("oaTo").removeAttribute("min");
    if (state.to) $("oaFrom").max = state.to; else $("oaFrom").removeAttribute("max");
    $("oaSearch").value = state.search;
    $("oaPageSize").value = state.pageSize;
    $("oaAnomPageSize").value = state.pageSize;
    if ($("oaModel")) $("oaModel").value = state.model || "";
    Array.prototype.forEach.call(document.querySelectorAll("[data-groupby]"), function (b) {
      b.classList.toggle("active", b.getAttribute("data-groupby") === state.groupBy);
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (b) {
      b.classList.toggle("active", b.getAttribute("data-view") === state.view);
    });
    // The anomalies subsection classifies by Kit Tracker presence itself, so the
    // Model filter does not apply to it.
    var anom = state.view === "anomalies";
    $("oaMainView").hidden = anom;
    $("oaAnomView").hidden = !anom;
    $("oaModelGroup").hidden = anom;
    // Export CSV covers the activity table only, not the anomalies subsection.
    $("oaExportBtn").hidden = anom;
  }

  // ── reminder ──
  function loadReminder() {
    api("missing-dates").then(function (m) {
      var el = $("oaReminder");
      if (m.count > 0) {
        el.hidden = false;
        var isExpanded = false;
        var renderReminder = function () {
          var html = '<div class="oa-reminder-content">' +
            '<div class="oa-reminder-header">' +
            '<div><i class="ti ti-alert-triangle"></i> Operator activity data missing for <b>' + m.count + '</b> date(s): ' +
            (isExpanded ? '' : m.dates.slice(-8).map(fmtDate).join(", ") + (m.count > 8 ? " …" : "")) +
            '</div>' +
            (m.count > 8 ? '<div><button class="oa-link" id="oaToggleMissingDates" style="font-size:12.5px; font-weight:700; color:inherit;">' + (isExpanded ? "Collapse ▲" : "View all " + m.count + " dates ▼") + '</button></div>' : '') +
            '</div>';

          if (isExpanded) {
            html += '<div class="oa-missing-grid">' +
              m.dates.map(function (d) {
                return '<span class="oa-missing-chip"><i class="ti ti-calendar" style="margin-right:4px; font-size:11px;"></i>' + fmtDate(d) + '</span>';
              }).join("") +
              '</div>';
          }
          html += '</div>';
          el.innerHTML = html;

          var toggleBtn = $("oaToggleMissingDates");
          if (toggleBtn) {
            toggleBtn.onclick = function () {
              isExpanded = !isExpanded;
              renderReminder();
            };
          }
        };
        renderReminder();
      } else el.hidden = true;
    }).catch(function () {});
  }

  // ── drill-down ──
  var slideState = { sid: null };
  function openDrill(sid) {
    slideState.sid = sid;
    history.pushState({ drill: sid }, "", location.pathname + location.search + "#op=" + encodeURIComponent(sid));
    $("oaSlideBackdrop").hidden = false; $("oaSlide").hidden = false;
    switchTab("profile");
    api("operators/" + encodeURIComponent(sid)).then(function (p) {
      $("oaSlideName").textContent = p.operator_name || sid;
      $("oaSlideSid").innerHTML = '<span class="notranslate" translate="no" data-no-i18n="true">' + esc(sid) + '</span>';
      $("oaSlideAvatar").textContent = (p.operator_name || sid).slice(0, 2).toUpperCase();
      var st = (p.current_status || "ACTIVE").toLowerCase();
      var pill = $("oaSlideStatus"); pill.textContent = p.current_status || "ACTIVE";
      pill.className = "oa-status-pill oa-status-" + st;
      renderProfile(p);
    }).catch(function () {
      $("oaSlideName").textContent = sid;
      $("oaSlideSid").innerHTML = '<span class="notranslate" translate="no" data-no-i18n="true">' + esc(sid) + '</span>';
      $("oaSlideAvatar").textContent = sid.slice(0, 2).toUpperCase();
      var pill = $("oaSlideStatus"); pill.textContent = "ACTIVE";
      pill.className = "oa-status-pill oa-status-active";
      renderProfile({ session_operator_id: sid, operator_name: sid, model: "UNKNOWN" });
    });
    loadDrillActivity(sid);
  }
  function closeDrill() {
    $("oaSlideBackdrop").hidden = true; $("oaSlide").hidden = true; slideState.sid = null;
    if (location.hash.indexOf("#op=") === 0) history.pushState(null, "", location.pathname + location.search);
  }
  function switchTab(tab) {
    Array.prototype.forEach.call(document.querySelectorAll(".oa-slide-tab"), function (b) {
      b.classList.toggle("active", b.getAttribute("data-tab") === tab);
    });
    $("oaTabProfile").hidden = tab !== "profile";
    $("oaTabActivity").hidden = tab !== "activity";
    $("oaTabStations").hidden = tab !== "stations";
  }
  function kv(k, v, noTranslate) {
    var val = txt(v);
    if (noTranslate && val !== "—") val = '<span class="notranslate" translate="no" data-no-i18n="true">' + val + '</span>';
    return '<div class="oa-kv"><span>' + k + '</span><span>' + val + '</span></div>';
  }
  function renderProfile(p) {
    var cp = p.current_posting || {};
    var isVle = (p.model || "").toUpperCase() === "VLE";
    // VLE operators have no Kit Tracker row, so compliance details are unavailable.
    var vleNote = isVle
      ? '<div class="oa-reminder"><i class="ti ti-info-circle"></i> This operator has no Kit Tracker record (VLE). Deposit, verification and kit details are not available.</div>'
      : '';
    $("oaTabProfile").innerHTML = vleNote +
      '<div class="oa-detail-card"><h4>Identity</h4>' +
      kv("Name", p.operator_name) + kv("Operator ID", p.session_operator_id, true) +
      kv("Model", p.model) + kv("Operator Code", p.operator_code, true) +
      kv("Mobile", p.mobile_number) + '</div>' +
      '<div class="oa-detail-card"><h4>Onboarding</h4>' +
      kv("Onboarding status", p.onboarding_status) +
      kv("Onboard date", fmtDate(p.onboarding_date)) +
      kv("Station allotted", fmtDate(p.station_id_allotted_date)) + '</div>' +
      '<div class="oa-detail-card oa-highlight"><h4>Security Deposit</h4>' +
      kv("Status", p.security_deposit_status) +
      kv("Date", fmtDate(p.security_deposit_date)) + '</div>' +
      '<div class="oa-detail-card"><h4>Verification</h4>' +
      kv("L1 status", p.l1_status) + kv("L1 date", fmtDate(p.l1_date)) +
      kv("L2 status", p.l2_status) + kv("L2 date", fmtDate(p.l2_date)) + '</div>' +
      '<div class="oa-detail-card"><h4>Operational Status</h4>' +
      kv("Operator status", p.operator_status) + kv("Station status", p.station_status) +
      kv("Kit working", p.kit_working == null ? null : (p.kit_working ? "Yes" : "No")) +
      kv("18+ permit", p.permit_18_plus == null ? null : (p.permit_18_plus ? "Yes" : "No")) +
      (p.inactive_reason ? kv("Inactive reason", p.inactive_reason) : "") +
      (p.inactive_date ? kv("Inactive date", fmtDate(p.inactive_date)) : "") + '</div>' +
      '<div class="oa-detail-card"><h4>Kit / Machine</h4>' +
      kv("Machine ID", p.machine_id) + kv("Laptop", p.laptop_name) +
      kv("Laptop serial", p.laptop_serial_no) + kv("Kit slot", p.kit_slot) + '</div>' +
      '<div class="oa-detail-card"><h4>Current Posting</h4>' +
      kv("Station", cp.station_number) + kv("Address", cp.machine_address) +
      kv("District", cp.machine_district) + kv("State", cp.machine_state) +
      kv("Pincode", cp.machine_pincode) +
      kv("Block", p.block) + kv("Category", p.category) + kv("Locality", p.locality) + '</div>' +
      (p.remarks ? '<p class="oa-card-sub">' + p.remarks + '</p>' : '');
  }
  function loadDrillActivity(sid) {
    var pr = {}; if (state.from) pr.from = state.from; if (state.to) pr.to = state.dateMode === "single" ? state.from : state.to;
    api("operators/" + encodeURIComponent(sid) + "/activity", pr).then(function (a) {
      // activity tab
      var maxV = Math.max.apply(null, a.daily.map(function (d) { return d.Total_Enrollment_and_Updates; }).concat([1]));
      var bars = a.daily.slice().reverse().map(function (d) {
        var h = Math.round(d.Total_Enrollment_and_Updates / maxV * 100);
        return '<div class="oa-bar" style="height:' + h + '%" data-label="' + fmtDate(d.activity_date) + ": " + inr(d.Total_Enrollment_and_Updates) + '"></div>';
      }).join("");
      var t = a.totals;
      var cards = [["Total E&U", t.Total_Enrollment_and_Updates], ["New Enrol", t.New_Aadhaar_Enrolment],
        ["Updates", t.Total_Updates], ["Bio", t.Total_Biometric_Updates]];
      $("oaTabActivity").innerHTML =
        '<div class="oa-cards">' + cards.map(function (c) {
          return '<div class="oa-card"><div class="oa-card-label">' + c[0] + '</div><div class="oa-card-value">' + inr(c[1]) + '</div></div>';
        }).join("") + '</div>' +
        '<div class="oa-detail-card"><h4>Total Enrolment & Updates per day</h4><div class="oa-bar-chart">' + bars + '</div></div>' +
        (a.off_hours_dates.length ? '<div class="oa-reminder"><i class="ti ti-moon"></i> Off-hours activity on: ' + a.off_hours_dates.map(fmtDate).join(", ") + '</div>' : '') +
        '<div class="oa-table-wrap"><table class="oa-table"><thead><tr><th>Date</th><th class="oa-num">Total</th><th class="oa-num">New</th><th class="oa-num">18+</th><th class="oa-num">Upd</th><th class="oa-num">Bio</th></tr></thead><tbody>' +
        a.daily.map(function (d) {
          return '<tr><td>' + fmtDate(d.activity_date) + '</td><td class="oa-num">' + inr(d.Total_Enrollment_and_Updates) +
            '</td><td class="oa-num">' + inr(d.New_Aadhaar_Enrolment) + '</td><td class="oa-num">' + inr(d.New_Aadhar_18_plus) +
            '</td><td class="oa-num">' + inr(d.Total_Updates) + '</td><td class="oa-num">' + inr(d.Total_Biometric_Updates) + '</td></tr>';
        }).join("") + '</tbody></table></div>';
      // stations tab
      $("oaTabStations").innerHTML = '<div class="oa-table-wrap"><table class="oa-table"><thead><tr><th>Station</th><th>District</th><th class="oa-num">Days worked</th><th class="oa-num">Total txns</th></tr></thead><tbody>' +
        a.stations.map(function (s) {
          return '<tr><td>' + s.station_number + '</td><td>' + txt(s.machine_district) + '</td><td class="oa-num">' + s.days_worked + '</td><td class="oa-num">' + inr(s.total_transactions) + '</td></tr>';
        }).join("") + '</tbody></table></div>';
    });
  }

  // ── upload modal ──
  var pollTimer = null;
  function openUpload(source) {
    $("oaUploadSource").value = source;
    $("oaUploadTitle").textContent = source === "kit_tracker" ? "Upload Kit Tracker" : "Upload RegistrarEA Data";
    $("oaProgress").hidden = true; $("oaUploadSummary").hidden = true; $("oaFileName").textContent = "";
    $("oaUploadModal").hidden = false;
    loadHistory();
  }
  function closeUpload() { $("oaUploadModal").hidden = true; if (pollTimer) clearInterval(pollTimer); }

  // Upload one or more files, one after another, so several daily sheets can be
  // added in a single go.
  function doUploadMany(files) {
    var list = Array.prototype.slice.call(files).filter(Boolean);
    if (!list.length) return;
    $("oaFileName").textContent = list.map(function (f) { return f.name; }).join(", ");
    var i = 0;
    (function next() {
      if (i >= list.length) return;
      var label = list.length > 1 ? " (file " + (i + 1) + " of " + list.length + ")" : "";
      doUpload(list[i], label, function () { i++; next(); });
    })();
  }

  function doUpload(file, label, onComplete) {
    label = label || "";
    var fd = new FormData();
    fd.append("file", file);
    fd.append("source", $("oaUploadSource").value);
    $("oaProgress").hidden = false; $("oaUploadSummary").hidden = true;
    $("oaProgressFill").style.width = "10%"; $("oaStage").textContent = "Uploading " + file.name + label + "…";
    var xhr = new XMLHttpRequest();
    xhr.open("POST", UPLOAD_URL);
    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) $("oaProgressFill").style.width = Math.min(40, e.loaded / e.total * 40) + "%";
    };
    xhr.onload = function () {
      if (xhr.status >= 400) { showUploadError(safeJSON(xhr.responseText)); return; }
      var res = JSON.parse(xhr.responseText);
      pollStatus(res.batch_id, file.name, label, onComplete);
    };
    xhr.onerror = function () { showUploadError({ detail: "Network error during upload." }); };
    xhr.send(fd);
  }
  function safeJSON(t) { try { return JSON.parse(t); } catch (e) { return { detail: t }; } }
  function pollStatus(batchId, fileName, label, onComplete) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function () {
      api("upload/" + batchId).then(function (s) {
        $("oaProgressFill").style.width = Math.max(45, s.progress || 45) + "%";
        $("oaStage").textContent = (fileName ? fileName + (label || "") + " — " : "") + (s.stage || s.status);
        if (s.status === "done") {
          clearInterval(pollTimer); $("oaProgressFill").style.width = "100%";
          showUploadSummary(s.summary, s.has_rejected, batchId, fileName);
          loadHistory(); loadFilters().then(loadCurrentView); loadReminder();
          if (onComplete) onComplete();
        } else if (s.status === "failed") {
          clearInterval(pollTimer); showUploadError({ detail: s.errors || "Processing failed." });
          if (onComplete) onComplete();
        }
      });
    }, 1000);
  }
  function showUploadSummary(s, hasRejected, batchId, fileName) {
    var el = $("oaUploadSummary"); el.hidden = false; el.className = "oa-upload-summary ok";
    el.innerHTML = '<b>Upload complete' + (fileName ? " — " + fileName : "") + '.</b>' +
      '<div class="oa-summary-grid">' +
      '<div><b>' + inr(s.rows_read) + '</b>rows read</div>' +
      '<div><b>' + inr(s.rows_after_filter) + '</b>after filter</div>' +
      '<div><b>' + inr(s.rows_written) + '</b>written</div>' +
      '<div><b>' + inr(s.rows_inserted) + '</b>inserted</div>' +
      '<div><b>' + inr(s.rows_updated) + '</b>updated</div>' +
      '<div><b>' + inr(s.rejected_count || 0) + '</b>rejected</div>' +
      '<div><b>' + inr(s.distinct_operators) + '</b>operators</div>' +
      '<div><b>' + (s.date_min ? fmtDate(s.date_min) : "—") + '</b>from</div>' +
      '<div><b>' + (s.date_max ? fmtDate(s.date_max) : "—") + '</b>to</div>' +
      '</div>' + (s.note ? '<p class="oa-card-sub">⚠ ' + s.note + '</p>' : '') +
      (hasRejected ? '<p><a class="oa-link" href="/auth/chips/operator-activity/api-rejected/' + batchId + '">Download rejected rows</a></p>' : '');
  }
  function showUploadError(e) {
    if (pollTimer) clearInterval(pollTimer);
    $("oaProgress").hidden = true;
    var el = $("oaUploadSummary"); el.hidden = false; el.className = "oa-upload-summary err";
    el.innerHTML = '<b>Upload failed.</b><p>' + (e.detail || "Unknown error") + '</p>';
  }
  function loadHistory() {
    api("uploads").then(function (rows) {
      $("oaHistBody").innerHTML = rows.map(function (b) {
        return '<tr><td>' + txt(b.filename) + '</td><td>' + txt(b.uploaded_by) + '</td>' +
          '<td>' + (b.uploaded_at ? fmtDate(b.uploaded_at.slice(0, 10)) : "—") + '</td>' +
          '<td>' + b.status + '</td><td>' + inr(b.rows_written || 0) + '</td>' +
          '<td>' + (b.date_min ? fmtDate(b.date_min) + "→" + fmtDate(b.date_max) : "—") + '</td>' +
          '<td><button class="oa-link" data-del="' + b.batch_id + '">Delete</button></td></tr>';
      }).join("");
      Array.prototype.forEach.call($("oaHistBody").querySelectorAll("[data-del]"), function (btn) {
        btn.onclick = function () {
          if (!confirm("Delete this batch and its rows?")) return;
          fetch("/auth/chips/operator-activity/api-uploads/" + btn.getAttribute("data-del"),
            { method: "DELETE", credentials: "same-origin" }).then(function () {
              loadHistory(); loadCurrentView(); loadReminder();
            });
        };
      });
    });
  }

  // ── wiring ──
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); var a = arguments, self = this; t = setTimeout(function () { fn.apply(self, a); }, ms); }; }

  function init() {
    loadURL();
    if (!state.from) applyPreset(state.preset);
    syncControls();

    // date pickers (From / To)
    function resetPages() { state.page = 1; state.anomPage = 1; }
    $("oaFrom").addEventListener("change", function () {
      state.from = this.value;
      if (state.to && state.from && state.from > state.to) {
        state.to = state.from;
      }
      syncControls();
      resetPages();
      loadCurrentView();
    });
    $("oaTo").addEventListener("change", function () {
      state.to = this.value;
      if (state.from && state.to && state.to < state.from) {
        state.from = state.to;
      }
      syncControls();
      resetPages();
      loadCurrentView();
    });
    $("oaSearch").addEventListener("input", debounce(function () { state.search = this.value; resetPages(); loadCurrentView(); }, 300));
    $("oaDistrict").addEventListener("change", function () {
      state.districts = this.value ? [this.value] : [];
      resetPages();
      console.log("[operator-activity] district selected:", state.districts);
      loadCurrentView();
    });
    if ($("oaModel")) $("oaModel").addEventListener("change", function () {
      state.model = this.value; state.page = 1; loadActivity();
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (b) {
      b.addEventListener("click", function () {
        state.view = b.getAttribute("data-view");
        resetPages(); syncControls(); loadCurrentView();
      });
    });
    $("oaReset").addEventListener("click", resetFilters);
    $("oaPageSize").addEventListener("change", function () { state.pageSize = +this.value; state.page = 1; loadActivity(); });
    $("oaAnomPageSize").addEventListener("change", function () {
      state.pageSize = +this.value; state.anomPage = 1; syncControls(); loadAnomalies();
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-groupby]"), function (b) {
      b.addEventListener("click", function () {
        state.groupBy = b.getAttribute("data-groupby");
        // Daily view defaults to oldest-date-first; operator view to total E&U.
        if (state.groupBy === "daily") { state.sortBy = "activity_date"; state.sortDir = "asc"; }
        else { state.sortBy = "Total_Enrollment_and_Updates"; state.sortDir = "desc"; }
        syncControls(); state.page = 1; loadActivity();
      });
    });

    // upload
    $("oaUploadBtn").addEventListener("click", function () { openUpload("registrar_ea"); });
    $("oaUploadClose").addEventListener("click", closeUpload);
    $("oaExportBtn").addEventListener("click", function () {
      window.location = EXPORT_URL + "?" + activityParams().toString();
    });
    var dz = $("oaDropzone"), fi = $("oaFileInput");
    fi.addEventListener("change", function () { if (fi.files.length) doUploadMany(fi.files); });
    ["dragover", "dragenter"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("dragover"); }); });
    ["dragleave", "drop"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("dragover"); }); });
    dz.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) doUploadMany(e.dataTransfer.files); });

    // drill-down
    $("oaSlideClose").addEventListener("click", closeDrill);
    $("oaSlideBackdrop").addEventListener("click", closeDrill);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("oaSlide").hidden) closeDrill(); });
    Array.prototype.forEach.call(document.querySelectorAll(".oa-slide-tab"), function (b) {
      b.addEventListener("click", function () { switchTab(b.getAttribute("data-tab")); if (b.getAttribute("data-tab") !== "profile" && slideState.sid) loadDrillActivity(slideState.sid); });
    });
    window.addEventListener("popstate", function () { if (location.hash.indexOf("#op=") !== 0 && !$("oaSlide").hidden) closeDrill(); });

    loadFilters().then(loadCurrentView);
    loadReminder();
    if (location.hash.indexOf("#op=") === 0) openDrill(decodeURIComponent(location.hash.slice(4)));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
