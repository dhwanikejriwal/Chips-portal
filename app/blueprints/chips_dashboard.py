# app/blueprints/chips_dashboard.py
from flask import Blueprint, render_template, redirect, url_for, session, flash, jsonify, request as flask_request
import requests

chips_dashboard_bp = Blueprint("chips_dashboard", __name__)

FASTAPI_BASE = "http://127.0.0.1:8000"


def _get(path, token=None):
    """Helper: GET from FastAPI backend."""
    headers = {}
    if token:
        if isinstance(token, dict):
            token = token.get("token", "") or token.get("access_token", "")
        headers["Authorization"] = f"Bearer {str(token).strip()}"
    try:
        resp = requests.get(f"{FASTAPI_BASE}{path}", headers=headers, timeout=12)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {} if path.endswith(("/summary", "/stats")) else []


@chips_dashboard_bp.route("/chips/registration-settings")
def registration_settings():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
    token = session.get("access_token")
    res = _get("/dashboard/districts/settings", token)
    districts = res.get("districts", []) if isinstance(res, dict) else []
    return render_template("portal_settings/registration_settings.html", districts=districts)


@chips_dashboard_bp.route("/chips/registration-settings/update", methods=["POST"])
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


@chips_dashboard_bp.route("/chips/dashboard")
def chips_dashboard():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    token = session.get("access_token")

    # Single-payload aggregated API request to FastAPI
    res = _get("/dashboard/chips/summary", token)
    
    if isinstance(res, dict) and "lms_requests" in res:
        stats = res
        operator_funnel = stats.get("operator_funnel", {})
    else:
        _empty_nseit = {"expiring_soon": 0, "already_expired": 0, "monthly_trend": [], "expiring_soon_list": [], "expired_list": []}
        _empty_funnel = {"lms_applied": 0, "nseit_done": 0, "activation_submitted": 0, "sent_to_uidai": 0, "approved": 0}
        _empty_trend = {"monthly_trend": []}
        operator_funnel = _empty_funnel.copy()
        stats = {
            "districts": [],
            "lms_requests": [],
            "nseit_requests": [],
            "activation_requests": [],
            "station_id_requests": [],
            "l2_requests": [],
            "l1_requests": [],
            "reactivation_requests": [],
            "dcs": [],
            "district_resources": {},
            "nseit_analysis": _empty_nseit.copy(),
            "operator_funnel": operator_funnel,
            "lms_analysis": _empty_trend.copy(),
            "activation_analysis": _empty_trend.copy(),
            "reactivation_analysis": _empty_trend.copy(),
            "station_id_analysis": _empty_trend.copy(),
            "l1_analysis": _empty_trend.copy(),
            "l2_analysis": _empty_trend.copy(),
        }

    return render_template("dashboards/chips_dash.html", stats=stats, funnel=operator_funnel)


@chips_dashboard_bp.route("/chips/cg-map")
def cg_map():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
    return render_template("dashboards/cg_map.html")


@chips_dashboard_bp.route("/chips/cg-map-data")
def cg_map_data():
    """JSON API — returns per-district aggregated operator + kit stats."""
    if "access_token" not in session or session.get("role") != "Admin":
        return jsonify({"error": "unauthorized"}), 401

    token = session.get("access_token")
    
    # Fetch aggregated summary from backend
    res = _get("/dashboard/chips/summary", token)
    if not isinstance(res, dict):
        return jsonify({})
    
    districts_list = res.get("districts", [])
    data = {
        d: {
            "operator_total": 0, "operator_pending": 0,
            "operator_approved": 0, "operator_rejected": 0,
            "kit_total": 0, "kit_pending": 0, "kit_approved": 0,
            "reactivation_total": 0, "reactivation_pending": 0,
        }
        for d in districts_list
    }

    for r in res.get("activation_requests", []):
        dist = r.get("district")
        if dist in data:
            data[dist]["operator_total"] += 1
            status = r.get("status", "").lower()
            if status in ("pending", "sent_to_chips", "sent_to_uidai"):
                data[dist]["operator_pending"] += 1
            elif status in ("approved", "activated"):
                data[dist]["operator_approved"] += 1
            elif status == "rejected":
                data[dist]["operator_rejected"] += 1

    for d in data:
        op_total = data[d]["operator_total"]
        op_approved = data[d]["operator_approved"]
        data[d]["approval_rate"] = round((op_approved / op_total * 100) if op_total > 0 else 0, 1)
        data[d]["total_requests"] = op_total + data[d]["kit_total"]
        data[d]["total_pending"] = data[d]["operator_pending"] + data[d]["kit_pending"]

    return jsonify(data)
