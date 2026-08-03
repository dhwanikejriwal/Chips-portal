# app/blueprints/dc_dashboard.py
from flask import Blueprint, render_template, redirect, url_for, session, flash
import requests

dc_dashboard_bp = Blueprint("dc_dashboard", __name__)

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
    return {}


@dc_dashboard_bp.route("/dc/dashboard")
def dc_dashboard():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    token = session.get("access_token")
    dc_id = session.get("user_id")
    district_id = session.get("district_id")
    district_name = session.get("district_name", "your district")

    # Single-payload aggregated API request to FastAPI
    path = f"/dashboard/dc/{dc_id}"
    if district_id:
        path += f"?district_code={district_id}"

    res = _get(path, token)
    if isinstance(res, dict) and "cand_requests" in res:
        stats = res
    else:
        stats = {
            "districts": [district_name] if district_name else [],
            "district_name": district_name,
            "cand_requests": [],
            "lms_requests": [],
            "nseit_requests": [],
            "activation_requests": [],
            "reactivation_requests": [],
            "station_id_requests": [],
            "l1_requests": [],
            "l2_requests": [],
        }

    return render_template("dc/dc_dash.html", stats=stats)
