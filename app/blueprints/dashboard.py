from flask import Blueprint, render_template, redirect, url_for, session, flash, jsonify, request as flask_request
from datetime import datetime
import requests
import os
import re

dashboard_bp = Blueprint("dashboard", __name__)

FASTAPI_BASE = "http://127.0.0.1:8000"


def _get(path, token=None):
    """Helper: GET from FastAPI backend. Returns list or empty list on failure."""
    headers = {}
    if token:
        if isinstance(token, dict):
            token = token.get("token", "") or token.get("access_token", "")
        headers["Authorization"] = f"Bearer {str(token).strip()}"
    try:
        resp = requests.get(f"{FASTAPI_BASE}{path}", headers=headers, timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def _days_ago(dt_str):
    """Return how many days ago an ISO datetime string is from now."""
    if not dt_str:
        return 9999
    try:
        now_date = datetime.now().date()
        dt = datetime.fromisoformat(str(dt_str).replace("T", " ")[:19])
        return max(0, (now_date - dt.date()).days)
    except Exception:
        return 9999


def _status_bucket(status):
    """Map any request's raw status onto one of the dashboard KPI buckets.

    Rules mirror mapStatusToUI / mapKitStatusToUI in chips_dash.html so the DC
    dashboard stays consistent with the CHiPS side. 'sent_to_uidai' is folded
    into 'approved' (CHiPS has acted on it and forwarded it onward), since the
    DC KPI strip intentionally exposes only pending/approved/reverted/rejected.
    """
    s = (status or "").strip().lower()
    if s in ("approved", "reviewed", "activated", "assigned", "sent_to_uidai", "sent to uidai"):
        return "approved"
    if s == "rejected":
        return "rejected"
    if s in ("reverted", "reverted by chips", "reverted_by_chips"):
        return "reverted"
    return "pending"


def _count_buckets(rows, status_key="status"):
    """Tally a list of request dicts into KPI buckets."""
    counts = {"total": 0, "pending": 0, "approved": 0, "reverted": 0, "rejected": 0}
    for r in (rows if isinstance(rows, list) else []):
        if not isinstance(r, dict):
            continue
        counts["total"] += 1
        counts[_status_bucket(r.get(status_key))] += 1
    return counts


@dashboard_bp.route("/dc/dashboard")
def dc_dashboard():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    token = session.get("access_token")
    dc_id = session.get("user_id")
    district_id = session.get("district_id")
    district_name = session.get("district_name", "your district")

    # ── District-scoped raw fetches (same endpoints the DC workflow pages use) ─
    lms_raw     = _get(f"/api/lms_manage/candidates?district_code={district_id}", token)
    nseit_raw   = _get(f"/api/nseit_manage/candidates?district_code={district_id}", token)
    act_raw     = _get(f"/operator-activation/dc/{dc_id}", token)
    react_raw   = _get("/reactivation/requests-with-operators", token)
    station_raw = _get(f"/station-id/dc/{dc_id}", token)
    l1_raw      = _get("/l1-registration/requests", token)
    l2_raw      = _get(f"/l2-registration/dc/{dc_id}", token)

    def _norm_cred(rows, status_key, id_key, id_field):
        out = []
        for r in (rows if isinstance(rows, list) else []):
            if not isinstance(r, dict):
                continue
            out.append({
                "name":               r.get("name", ""),
                "district":           r.get("district_name", district_name),
                "status":             (r.get(status_key) or r.get("status") or "Pending").strip(),
                "submitted_days_ago": _days_ago(r.get("created_at")),
                "created_at":         r.get("created_at"),
                id_field:             r.get(id_key, ""),
            })
        return out

    def _label(r):
        return (
            r.get("request_code") or r.get("operator_name") or r.get("name_as_per_aadhaar")
            or r.get("station_id") or (f"#{r.get('id')}" if r.get("id") else "Request")
        )

    def _norm_req(rows, date_key="submitted_at"):
        out = []
        for r in (rows if isinstance(rows, list) else []):
            if not isinstance(r, dict):
                continue
            out.append({
                "district":           r.get("district_name", district_name),
                "status":             (r.get("status") or "sent_to_chips").strip().lower(),
                "submitted_days_ago": _days_ago(r.get(date_key)),
                "created_at":         r.get(date_key),
                "label":              _label(r),
                "revert_reason":      r.get("revert_reason") or r.get("reject_reason") or "",
            })
        return out

    lms_requests   = _norm_cred(lms_raw, "lms_status", "lms_credential_id", "lms_id")
    nseit_requests = _norm_cred(nseit_raw, "nseit_status", "nseit_certificate_id", "nseit_id")

    activation_requests = []
    for r in (act_raw if isinstance(act_raw, list) else []):
        if not isinstance(r, dict):
            continue
        activation_requests.append({
            "name":               r.get("name_as_per_aadhaar") or r.get("operator_name", ""),
            "label":              r.get("name_as_per_aadhaar") or r.get("operator_name") or (f"#{r.get('id')}" if r.get("id") else "Request"),
            "district":           r.get("district_name", district_name),
            "status":             (r.get("status") or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.get("submitted_at")),
            "created_at":         r.get("submitted_at"),
            "revert_reason":      r.get("revert_reason") or r.get("reject_reason") or "",
        })

    reactivation_requests = []
    for r in (react_raw if isinstance(react_raw, list) else []):
        if not isinstance(r, dict):
            continue
        dist = r.get("district_name", district_name)
        req_code = r.get("request_code") or (f"#{r.get('id')}" if r.get("id") else "Batch")
        created = r.get("submitted_at") or r.get("created_at")
        ops = r.get("operators")
        if ops and isinstance(ops, list):
            for op in ops:
                op_status = (op.get("status") or r.get("status") or "PENDING").strip().upper()
                reactivation_requests.append({
                    "id":                 op.get("id") or r.get("id"),
                    "district":          dist,
                    "label":             req_code,
                    "status":            op_status,
                    "submitted_days_ago": _days_ago(created),
                    "created_at":         created,
                    "operator_count":     1,
                    "revert_reason":      op.get("revert_reason") or op.get("reject_reason") or r.get("revert_reason") or r.get("reject_reason") or "",
                })
        else:
            reactivation_requests.append({
                "id":                 r.get("id"),
                "district":          dist,
                "label":             req_code,
                "status":            (r.get("status") or "PENDING").strip().upper(),
                "submitted_days_ago": _days_ago(created),
                "created_at":         created,
                "operator_count":     r.get("operator_count") or 1,
                "revert_reason":      r.get("revert_reason") or r.get("reject_reason") or "",
            })

    cand_raw = _get(f"/api/selection/candidates?district_code={district_id}", token)

    cand_requests = []
    for r in (cand_raw if isinstance(cand_raw, list) else []):
        if not isinstance(r, dict):
            continue
        cand_requests.append({
            "name":               r.get("name") or r.get("candidate_name") or "",
            "label":              r.get("request_code") or r.get("name") or (f"#{r.get('r_id')}" if r.get("r_id") else "Request"),
            "district":           r.get("district_name", district_name),
            "status":             (r.get("status") or "PENDING").strip(),
            "submitted_days_ago": _days_ago(r.get("created_at")),
            "created_at":         r.get("created_at"),
            "revert_reason":      r.get("hold_remark") or r.get("reject_reason") or "",
        })



    allotted_raw = _get("/l1-registration/allotted-pending", token)
    awaiting_l2_raw = _get(f"/l2-registration/awaiting-l2/{dc_id}", token)

    l1_requests = _norm_req(l1_raw)
    for r in (allotted_raw if isinstance(allotted_raw, list) else []):
        if isinstance(r, dict):
            l1_requests.append({
                "district":           r.get("district_name", district_name),
                "status":             "awaiting_l1",
                "submitted_days_ago": _days_ago(r.get("created_at")),
                "created_at":         r.get("created_at"),
                "label":              _label(r),
                "revert_reason":      "",
            })

    l2_requests = _norm_req(l2_raw)
    for r in (awaiting_l2_raw if isinstance(awaiting_l2_raw, list) else []):
        if isinstance(r, dict):
            l2_requests.append({
                "district":           r.get("district_name", district_name),
                "status":             "awaiting_l2",
                "submitted_days_ago": _days_ago(r.get("created_at")),
                "created_at":         r.get("created_at"),
                "label":              _label(r),
                "revert_reason":      "",
            })

    stats = {
        "districts":             [district_name] if district_name else [],
        "district_name":         district_name,
        "cand_requests":         cand_requests,
        "lms_requests":          lms_requests,
        "nseit_requests":        nseit_requests,
        "activation_requests":   activation_requests,
        "reactivation_requests": reactivation_requests,
        "station_id_requests":   _norm_req(station_raw),
        "l1_requests":           l1_requests,
        "l2_requests":           l2_requests,
    }

    return render_template("dc/dc_dash.html", stats=stats)


@dashboard_bp.route("/chips/registration-settings")
def registration_settings():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
    token = session.get("access_token")
    res = _get("/dashboard/districts/settings", token)
    districts = res.get("districts", []) if isinstance(res, dict) else []
    return render_template("chips/registration_settings.html", districts=districts)

@dashboard_bp.route("/chips/registration-settings/update", methods=["POST"])
def update_district_setting():
    if "access_token" not in session or session.get("role") != "Admin":
        return jsonify({"success": False, "detail": "Unauthorized access"}), 403
    token = session.get("access_token")
    data = flask_request.get_json() or {}
    code = data.get("district_code")
    if not code:
        return jsonify({"success": False, "detail": "district_code is required"}), 400
    try:
        resp = requests.put(
            f"{FASTAPI_BASE}/dashboard/districts/{code}/settings",
            json=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=8
        )
        if resp.status_code == 200:
            try:
                res_json = resp.json()
                msg = res_json.get("message", "Settings updated successfully")
            except Exception:
                msg = "Settings updated successfully"
            return jsonify({"success": True, "message": msg})
        else:
            try:
                err_json = resp.json()
                detail = err_json.get("detail") or err_json.get("message") or "Update failed"
            except Exception:
                detail = f"Server returned error code {resp.status_code}"
            return jsonify({"success": False, "detail": str(detail)}), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "detail": str(e)}), 500

@dashboard_bp.route("/chips/dashboard")
def chips_dashboard():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    token = session.get("access_token")

    # ── Fetch raw data from FastAPI endpoints ─────────────────────────────
    lms_raw          = _get("/api/lms_manage/candidates", token)
    nseit_raw        = _get("/api/nseit_manage/candidates", token)
    activation_raw   = _get("/operator-activation/all", token)
    station_id_raw   = _get("/station-id/all", token)
    l2_raw           = _get("/l2-registration/all", token)
    l1_raw           = _get("/l1-registration/requests", token)
    reactivation_raw = _get("/reactivation/requests-with-operators", token)
    districts_raw    = _get("/dashboard/districts-with-resources", token)

    # ── Normalise LMS list ────────────────────────────────────────────────
    lms_requests = []
    for r in (lms_raw if isinstance(lms_raw, list) else []):
        lms_requests.append({
            "r_id":               r.get("r_id"),
            "district":           r.get("district_name", "Unknown"),
            "district_code":      r.get("district_code", ""),
            "name":               r.get("name", ""),
            "status":             (r.get("lms_status") or "Pending").strip(),
            "submitted_days_ago": _days_ago(r.get("created_at")),
            "lms_id":             r.get("lms_credential_id", ""),
        })

    # ── Normalise NSEIT list ──────────────────────────────────────────────
    nseit_requests = []
    for r in (nseit_raw if isinstance(nseit_raw, list) else []):
        nseit_requests.append({
            "r_id":               r.get("r_id"),
            "district":           r.get("district_name", "Unknown"),
            "district_code":      r.get("district_code", ""),
            "name":               r.get("name", ""),
            "status":             (r.get("nseit_status") or "Pending").strip(),
            "submitted_days_ago": _days_ago(r.get("created_at")),
            "nseit_id":           r.get("nseit_certificate_id", ""),
        })

    # ── Normalise Activation list ─────────────────────────────────────────
    activation_requests = []
    for r in (activation_raw if isinstance(activation_raw, list) else []):
        submitted_at = r.get("submitted_at", "")
        reviewed_at  = r.get("reviewed_at")
        days_ago     = _days_ago(submitted_at)

        # Compute response time in hours (submitted → reviewed)
        resp_hours = None
        if reviewed_at and submitted_at:
            try:
                sub_dt = datetime.fromisoformat(str(submitted_at).replace("T", " ")[:19])
                rev_dt = datetime.fromisoformat(str(reviewed_at).replace("T", " ")[:19])
                resp_hours = max(0, (rev_dt - sub_dt).total_seconds() / 3600)
            except Exception:
                pass

        activation_requests.append({
            "id":                       r.get("id"),
            "name":                     r.get("name_as_per_aadhaar") or r.get("operator_name", ""),
            "district":                 r.get("district_name", "Unknown"),
            "district_id":              str(r.get("district_id", "")),
            "status":                   (r.get("status") or "sent_to_chips").strip().lower(),
            "submitted_days_ago":       days_ago,
            "response_time_hours":      resp_hours,
            # nseit_certificate_number presence used as proxy for NSEIT step completion
            "nseit_certificate_number": r.get("operator_aadhaar", "") or "",
        })

    # ── Normalise Station ID list ──────────────────────────────────────────
    station_id_requests = []
    for r in (station_id_raw if isinstance(station_id_raw, list) else []):
        station_id_requests.append({
            "id":                 r.get("id"),
            "district":          r.get("district_name", "Unknown"),
            "status":            (r.get("status") or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.get("submitted_at")),
        })

    # ── Normalise L2 list ─────────────────────────────────────────────────
    l2_requests = []
    for r in (l2_raw if isinstance(l2_raw, list) else []):
        submitted_at = r.get("submitted_at")
        reviewed_at = r.get("reviewed_at")
        resp_hours = None
        if reviewed_at and submitted_at:
            try:
                sub_dt = datetime.fromisoformat(str(submitted_at).replace("T", " ")[:19])
                rev_dt = datetime.fromisoformat(str(reviewed_at).replace("T", " ")[:19])
                resp_hours = max(0, (rev_dt - sub_dt).total_seconds() / 3600)
            except Exception:
                pass
        l2_requests.append({
            "id":                 r.get("id"),
            "district":          r.get("district_name", "Unknown"),
            "status":            (r.get("status") or "sent_to_chips").strip().lower(),
            "client_type":       r.get("client_type", ""),
            "submitted_days_ago": _days_ago(submitted_at),
            "response_time_hours": resp_hours,
        })

    # ── Normalise L1 list ─────────────────────────────────────────────────
    l1_requests = []
    for r in (l1_raw if isinstance(l1_raw, list) else []):
        submitted_at = r.get("submitted_at")
        reviewed_at = r.get("reviewed_at")
        resp_hours = None
        if reviewed_at and submitted_at:
            try:
                sub_dt = datetime.fromisoformat(str(submitted_at).replace("T", " ")[:19])
                rev_dt = datetime.fromisoformat(str(reviewed_at).replace("T", " ")[:19])
                resp_hours = max(0, (rev_dt - sub_dt).total_seconds() / 3600)
            except Exception:
                pass
        l1_requests.append({
            "id":                 r.get("id"),
            "district":          r.get("district_name", "Unknown"),
            "status":            (r.get("status") or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(submitted_at),
            "response_time_hours": resp_hours,
        })

    # ── Normalise Reactivation list ───────────────────────────────────────
    reactivation_requests = []
    for r in (reactivation_raw if isinstance(reactivation_raw, list) else []):
        dist = r.get("district_name") or r.get("district") or "Unknown"
        created_at = r.get("created_at") or r.get("submitted_at")
        ops = r.get("operators")
        if ops and isinstance(ops, list):
            for op in ops:
                op_status = (op.get("status") or r.get("status") or "PENDING").strip().upper()
                reactivation_requests.append({
                    "id":                 op.get("id") or r.get("id"),
                    "district":          dist,
                    "status":            op_status,
                    "submitted_days_ago": _days_ago(created_at),
                    "operator_count":     1,
                })
        else:
            reactivation_requests.append({
                "id":                 r.get("id"),
                "district":          dist,
                "status":            (r.get("status") or "PENDING").strip().upper(),
                "submitted_days_ago": _days_ago(created_at),
                "operator_count":     r.get("operator_count") or 1,
            })

    # ── Collect unique district names for filter dropdown ─────────────────
    if districts_raw and isinstance(districts_raw, list):
        districts = sorted(set(d["district_name"] for d in districts_raw if isinstance(d, dict) and d.get("district_name")))
    else:
        all_names = (
            [r["district"] for r in lms_requests] +
            [r["district"] for r in nseit_requests] +
            [r["district"] for r in activation_requests] +
            [r["district"] for r in station_id_requests] +
            [r["district"] for r in l2_requests] +
            [r["district"] for r in l1_requests] +
            [r["district"] for r in reactivation_requests]
        )
        districts = sorted(set(n for n in all_names if n and n != "Unknown"))

    resources_map = {}
    if districts_raw and isinstance(districts_raw, list):
        for d in districts_raw:
            if isinstance(d, dict) and d.get("district_name"):
                resources_map[d["district_name"]] = d.get("aadhaar_resources")

    # ── Fetch NSEIT analysis and operator funnel from FastAPI /dashboard/stats ────────────────
    _empty_nseit = {
        "expiring_soon": 0,
        "already_expired": 0,
        "monthly_trend": [],
        "expiring_soon_list": [],
        "expired_list": [],
    }
    _empty_funnel = {
        "lms_applied": 0,
        "nseit_done": 0,
        "activation_submitted": 0,
        "sent_to_uidai": 0,
        "approved": 0,
    }
    _empty_trend = {"monthly_trend": []}
    nseit_analysis = _empty_nseit.copy()
    operator_funnel = _empty_funnel.copy()
    lms_analysis = _empty_trend.copy()
    activation_analysis = _empty_trend.copy()
    reactivation_analysis = _empty_trend.copy()
    station_id_analysis = _empty_trend.copy()
    l1_analysis = _empty_trend.copy()
    l2_analysis = _empty_trend.copy()
    try:
        dash_stats = requests.get(
            f"{FASTAPI_BASE}/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if dash_stats.status_code == 200:
            json_res = dash_stats.json()
            nseit_analysis = json_res.get("nseit_analysis", _empty_nseit)
            operator_funnel = json_res.get("operator_funnel", _empty_funnel)
            lms_analysis = json_res.get("lms_analysis", _empty_trend)
            activation_analysis = json_res.get("activation_analysis", _empty_trend)
            reactivation_analysis = json_res.get("reactivation_analysis", _empty_trend)
            station_id_analysis = json_res.get("station_id_analysis", _empty_trend)
            l1_analysis = json_res.get("l1_analysis", _empty_trend)
            l2_analysis = json_res.get("l2_analysis", _empty_trend)
    except Exception:
        pass

    stats = {
        "districts":            districts,
        "lms_requests":         lms_requests,
        "nseit_requests":       nseit_requests,
        "activation_requests":  activation_requests,
        "station_id_requests":  station_id_requests,
        "l2_requests":          l2_requests,
        "l1_requests":          l1_requests,
        "reactivation_requests": reactivation_requests,
        "dcs":                  [],
        "district_resources":   resources_map,
        "nseit_analysis":       nseit_analysis,
        "operator_funnel":      operator_funnel,
        "lms_analysis":         lms_analysis,
        "activation_analysis":  activation_analysis,
        "reactivation_analysis": reactivation_analysis,
        "station_id_analysis":  station_id_analysis,
        "l1_analysis":          l1_analysis,
        "l2_analysis":          l2_analysis,
    }

    return render_template("chips/chips_dash.html", stats=stats, funnel=operator_funnel)


# ── Lifecycle Analytics pages ────────────────────────────────────────────────




# ── CG District Map ───────────────────────────────────────────────────────────

# Mapping from common DB district name variants → canonical GeoJSON dist_name
_DISTRICT_ALIASES = {
    "baloda bazar": "Balodabazar-Bhatapara",
    "balodabazar": "Balodabazar-Bhatapara",
    "balodabazar bhatapara": "Balodabazar-Bhatapara",
    "balrampur": "Balrampur-Ramanujganj",
    "balrampur ramanujganj": "Balrampur-Ramanujganj",
    "gariaband": "Gariyaband",
    "janjgir": "Janjgir-Champa",
    "janjgir champa": "Janjgir-Champa",
    "kabirdham": "Kabirdham",
    "kawardha": "Kabirdham",
    "kabeerdham": "Kabirdham",
    "korea": "Koriya",
    "surguja": "Sarguja",
    "dakshin bastar dantewada": "Dantewada",
    "uttar bastar kanker": "Kanker",
    "mohla manpur ambagarh chouki": "Mohla-Manpur-Ambagarh Chowki",
    "mohlamanpurambagarh chouki": "Mohla-Manpur-Ambagarh Chowki",
    "manendragarh chirmiri bharatpur m c b": "Manendragarh-Chirmiri-Bharatpur",
    "manendragarhchirmiribharatpurm c b": "Manendragarh-Chirmiri-Bharatpur",
    "khairagarh": "Khairagarh-Chhuikhadan-Gandai",
    "kondagaon": "Kondagaon",
    "manendragarh": "Manendragarh-Chirmiri-Bharatpur",
    "mcb": "Manendragarh-Chirmiri-Bharatpur",
    "mohla manpur": "Mohla-Manpur-Ambagarh Chowki",
    "mohla": "Mohla-Manpur-Ambagarh Chowki",
    "sarangarh": "Sarangarh-Bilaigarh",
    "sarangarh bilaigarh": "Sarangarh-Bilaigarh",
    "gaurela pendra marwahi": "Gaurela-Pendra-Marwahi",
    "gpm": "Gaurela-Pendra-Marwahi",
}

_GEOJSON_DISTRICTS = [
    "Bastar", "Bilaspur", "Dantewada", "Dhamtari", "Durg", "Janjgir-Champa",
    "Jashpur", "Kanker", "Kabirdham", "Korba", "Koriya", "Mahasamund",
    "Raigarh", "Raipur", "Rajnandgaon", "Sarguja", "Bijapur", "Narayanpur",
    "Sukma", "Kondagaon", "Balodabazar-Bhatapara", "Gariyaband", "Balod",
    "Mungeli", "Surajpur", "Balrampur-Ramanujganj", "Bemetara",
    "Gaurela-Pendra-Marwahi", "Khairagarh-Chhuikhadan-Gandai",
    "Manendragarh-Chirmiri-Bharatpur", "Mohla-Manpur-Ambagarh Chowki",
    "Sakti", "Sarangarh-Bilaigarh",
]

_GEOJSON_LOWER = {d.lower(): d for d in _GEOJSON_DISTRICTS}


def _normalize_district(name):
    """Map a DB district name to the canonical GeoJSON dist_name."""
    if not name or name == "Unknown":
        return None
    key = re.sub(r'[^a-z0-9 ]', '', name.lower()).strip()
    # Direct lowercase match
    if key in _GEOJSON_LOWER:
        return _GEOJSON_LOWER[key]
    # Alias lookup
    if key in _DISTRICT_ALIASES:
        return _DISTRICT_ALIASES[key]
    # Strip hyphens/extra chars and retry
    key2 = key.replace('-', ' ').replace('_', ' ')
    if key2 in _GEOJSON_LOWER:
        return _GEOJSON_LOWER[key2]
    if key2 in _DISTRICT_ALIASES:
        return _DISTRICT_ALIASES[key2]
    return None


@dashboard_bp.route("/chips/cg-map")
def cg_map():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
    return render_template("chips/cg_map.html")


@dashboard_bp.route("/chips/cg-map-data")
def cg_map_data():
    """JSON API — returns per-district aggregated operator + kit stats."""
    if "access_token" not in session or session.get("role") != "Admin":
        return jsonify({"error": "unauthorized"}), 401

    token = session.get("access_token")

    lms_raw          = _get("/api/lms_manage/candidates", token)
    nseit_raw        = _get("/api/nseit_manage/candidates", token)
    activation_raw   = _get("/operator-activation/all", token)
    station_id_raw   = _get("/station-id/all", token)
    l1_raw           = _get("/l1-registration/requests", token)
    l2_raw           = _get("/l2-registration/all", token)
    reactivation_raw = _get("/reactivation/requests", token)

    # Initialise per-district buckets
    data = {
        d: {
            "operator_total": 0, "operator_pending": 0,
            "operator_approved": 0, "operator_rejected": 0,
            "kit_total": 0, "kit_pending": 0, "kit_approved": 0,
            "reactivation_total": 0, "reactivation_pending": 0,
        }
        for d in _GEOJSON_DISTRICTS
    }

    # ── LMS ───────────────────────────────────────────────────────────────
    for r in (lms_raw if isinstance(lms_raw, list) else []):
        dist = _normalize_district(r.get("district_name", ""))
        if not dist:
            continue
        status = (r.get("lms_status") or "Pending").strip()
        data[dist]["operator_total"] += 1
        if status in ("Forwarded", "Forwarded Again"):
            data[dist]["operator_pending"] += 1
        elif status == "Reverted by CHiPS":
            data[dist]["operator_rejected"] += 1

    # ── NSEIT ─────────────────────────────────────────────────────────────
    for r in (nseit_raw if isinstance(nseit_raw, list) else []):
        dist = _normalize_district(r.get("district_name", ""))
        if not dist:
            continue
        status = (r.get("nseit_status") or "Pending").strip()
        data[dist]["operator_total"] += 1
        if status in ("Forwarded", "Forwarded Again"):
            data[dist]["operator_pending"] += 1
        elif status == "Reverted by CHiPS":
            data[dist]["operator_rejected"] += 1

    # ── Operator activation ───────────────────────────────────────────────
    for r in (activation_raw if isinstance(activation_raw, list) else []):
        dist = _normalize_district(r.get("district_name", ""))
        if not dist:
            continue
        status = (r.get("status") or "sent_to_chips").strip().lower()
        data[dist]["operator_total"] += 1
        if status in ("pending", "sent_to_chips", "sent_to_uidai"):
            data[dist]["operator_pending"] += 1
        elif status in ("approved", "activated"):
            data[dist]["operator_approved"] += 1
        elif status == "rejected":
            data[dist]["operator_rejected"] += 1

    # ── Reactivation ─────────────────────────────────────────────────────
    for r in (reactivation_raw if isinstance(reactivation_raw, list) else []):
        dist = _normalize_district(r.get("district_name") or r.get("district") or "")
        if not dist:
            continue
        ops = r.get("operators")
        if ops and isinstance(ops, list):
            for op in ops:
                op_status = (op.get("status") or r.get("status") or "PENDING").strip().upper()
                data[dist]["operator_total"] += 1
                data[dist]["reactivation_total"] += 1
                if op_status in ("PENDING", "REAPPLIED", "SENT_TO_UIDAI"):
                    data[dist]["operator_pending"] += 1
                    data[dist]["reactivation_pending"] += 1
                elif op_status in ("REVIEWED", "ACTIVATED", "APPROVED"):
                    data[dist]["operator_approved"] += 1
                elif op_status in ("REVERTED", "REVERTED_BY_CHIPS", "REVERT_BACK", "REJECTED"):
                    data[dist]["operator_rejected"] += 1
        else:
            status = (r.get("status") or "PENDING").strip().upper()
            count = r.get("operator_count") or 1
            data[dist]["operator_total"] += count
            data[dist]["reactivation_total"] += count
            if status in ("PENDING", "REAPPLIED", "SENT_TO_UIDAI"):
                data[dist]["operator_pending"] += count
                data[dist]["reactivation_pending"] += count
            elif status in ("REVIEWED", "ACTIVATED", "APPROVED"):
                data[dist]["operator_approved"] += count
            elif status in ("REVERTED", "REVERTED_BY_CHIPS", "REVERT_BACK", "REJECTED"):
                data[dist]["operator_rejected"] += count

    # ── Kit requests: Station ID ──────────────────────────────────────────
    for r in (station_id_raw if isinstance(station_id_raw, list) else []):
        dist = _normalize_district(r.get("district_name", ""))
        if not dist:
            continue
        status = (r.get("status") or "sent_to_chips").strip().lower()
        data[dist]["kit_total"] += 1
        if status in ("sent_to_chips", "pending", "reapplied"):
            data[dist]["kit_pending"] += 1
        elif status in ("approved", "activated"):
            data[dist]["kit_approved"] += 1

    # ── Kit requests: L1 ─────────────────────────────────────────────────
    for r in (l1_raw if isinstance(l1_raw, list) else []):
        dist = _normalize_district(r.get("district_name", ""))
        if not dist:
            continue
        status = (r.get("status") or "sent_to_chips").strip().lower()
        data[dist]["kit_total"] += 1
        if status in ("sent_to_chips", "pending", "reapplied"):
            data[dist]["kit_pending"] += 1
        elif status in ("approved", "reviewed"):
            data[dist]["kit_approved"] += 1

    # ── Kit requests: L2 ─────────────────────────────────────────────────
    for r in (l2_raw if isinstance(l2_raw, list) else []):
        dist = _normalize_district(r.get("district_name", ""))
        if not dist:
            continue
        status = (r.get("status") or "sent_to_chips").strip().lower()
        data[dist]["kit_total"] += 1
        if status in ("sent_to_chips", "pending", "reapplied"):
            data[dist]["kit_pending"] += 1
        elif status in ("approved", "activated"):
            data[dist]["kit_approved"] += 1

    # ── Compute derived metrics ───────────────────────────────────────────
    for d in data:
        op_total = data[d]["operator_total"]
        op_approved = data[d]["operator_approved"]
        data[d]["approval_rate"] = round(
            (op_approved / op_total * 100) if op_total > 0 else 0, 1
        )
        data[d]["total_requests"] = op_total + data[d]["kit_total"]
        data[d]["total_pending"] = data[d]["operator_pending"] + data[d]["kit_pending"]

    return jsonify(data)
