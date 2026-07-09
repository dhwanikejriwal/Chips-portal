# app/blueprints/station_id.py
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    Response,
)
import requests as http
from app.utils.aging import parse_aging_filter, filter_by_aging

station_id_bp = Blueprint("station_id", __name__)

BACKEND = "http://127.0.0.1:8000/station-id"

# Statuses that are NOT part of the pending queue for aging purposes
_STATION_NON_PENDING = {"approved", "activated", "rejected", "reverted", "reverted_by_chips"}


def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────


@station_id_bp.route("/dc/station-id/list", methods=["GET"])
def dc_list():
    if not session.get("access_token"):
        return redirect(url_for("login_view"))

    dc_id = session.get("user_id")
    try:
        resp = http.get(f"{BACKEND}/dc/{dc_id}", headers=_headers())
        requests_list = resp.json() if resp.status_code == 200 else []
    except http.exceptions.ConnectionError:
        requests_list = []

    return render_template("station_id/dc_list.html", requests=requests_list)


@station_id_bp.route("/dc/station-id/new", methods=["GET"])
def dc_new_form():
    if not session.get("access_token"):
        return redirect(url_for("login_view"))
    return render_template("station_id/submit_form.html")


@station_id_bp.route("/dc/station-id/new", methods=["POST"])
def dc_submit():
    if not session.get("access_token"):
        return redirect(url_for("login_view"))

    form_data = {
        "dc_id": session.get("user_id"),
        "district_id": session.get("district_id"),
        "model": request.form.get("model"),
        "user_type": request.form.get("user_type"),
        "user_type_custom_reason": request.form.get("user_type_custom_reason", ""),
        "number_of_kits": request.form.get("number_of_kits"),
    }

    try:
        resp = http.post(f"{BACKEND}/submit", data=form_data, headers=_headers())
        if resp.status_code == 200:
            return jsonify({"success": True, "data": resp.json()})
        else:
            return jsonify({"success": False, "detail": resp.json().get("detail", "Submission failed.")}), 400
    except http.exceptions.ConnectionError:
        return jsonify({"success": False, "detail": "Backend offline."}), 503


@station_id_bp.route("/dc/station-id/<int:request_id>/reapply-json", methods=["POST"])
def dc_reapply_json(request_id):
    if not session.get("access_token"):
        return jsonify({"detail": "Unauthorized"}), 401

    form_data = {
        "dc_id": session.get("user_id"),
        "model": request.form.get("model"),
        "user_type": request.form.get("user_type"),
        "user_type_custom_reason": request.form.get("user_type_custom_reason", ""),
        "number_of_kits": request.form.get("number_of_kits"),
        "reapply_remark": request.form.get("reapply_remark"),
    }

    resp = http.post(
        f"{BACKEND}/dc/{request_id}/reapply",
        data=form_data,
        headers=_headers(),
    )
    return Response(
        resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/json"),
    )


# ─────────────────────────────────────────────
# CHIPS ADMIN ROUTES
# ─────────────────────────────────────────────


@station_id_bp.route("/chips/station-id", methods=["GET"])
def chips_list():
    if not session.get("access_token"):
        return redirect(url_for("login_view"))

    try:
        resp = http.get(f"{BACKEND}/all", headers=_headers())
        requests_list = resp.json() if resp.status_code == 200 else []
    except http.exceptions.ConnectionError:
        requests_list = []

    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_subset = [
            r for r in requests_list
            if str(r.get("status", "")).strip().lower() not in _STATION_NON_PENDING
        ]
        requests_list = filter_by_aging(pending_subset, aging_filter, "submitted_at")

    return render_template(
        "station_id/chips_list.html",
        requests=requests_list,
        aging_filter=aging_filter,
        aging_label=aging_label,
    )


@station_id_bp.route("/chips/station-id/<int:request_id>/detail-json", methods=["GET"])
def chips_detail_json(request_id):
    if not session.get("access_token"):
        return jsonify({"detail": "Unauthorized"}), 401

    resp = http.get(f"{BACKEND}/{request_id}/detail", headers=_headers())
    return Response(
        resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/json"),
    )


@station_id_bp.route("/chips/station-id/<int:request_id>/approve", methods=["POST"])
def chips_approve(request_id):
    if not session.get("access_token"):
        return redirect(url_for("login_view"))

    form_data = {
        "reviewed_by": session.get("user_id"),
        "station_id_value": request.form.get("station_id_value", ""),
        "chips_remarks": request.form.get("chips_remarks", ""),
    }

    http.patch(f"{BACKEND}/{request_id}/approve", data=form_data, headers=_headers())
    return redirect(url_for("station_id.chips_list"))


@station_id_bp.route("/chips/station-id/<int:request_id>/revert", methods=["POST"])
def chips_revert(request_id):
    if not session.get("access_token"):
        return redirect(url_for("login_view"))

    form_data = {
        "reviewed_by": session.get("user_id"),
        "revert_reason": request.form.get("revert_reason", ""),
    }

    http.patch(f"{BACKEND}/{request_id}/revert", data=form_data, headers=_headers())
    return redirect(url_for("station_id.chips_list"))
