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

station_id_bp = Blueprint("station_id", __name__)

BACKEND = "http://127.0.0.1:8000/station-id"


def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────


@station_id_bp.route("/dc/station-id/list", methods=["GET"])
def dc_list():
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))

    dc_id = session.get("user_id")
    try:
        resp = http.get(f"{BACKEND}/dc/{dc_id}", headers=_headers())
        raw_list = resp.json() if resp.status_code == 200 else []
        
        # 🌟 FIXED: Explicitly sanitize and normalize timestamp mapping properties 
        requests_list = []
        for r in raw_list:
            requests_list.append({
                "id": r.get("id"),
                "request_no": r.get("request_no"),
                "district_name": r.get("district_name"),
                "model": r.get("model"),
                "user_type": r.get("user_type"),
                "user_type_custom_reason": r.get("user_type_custom_reason"),
                "number_of_kits": r.get("number_of_kits"),
                "status": r.get("status"),
                "assigned_station_id": r.get("assigned_station_id") or r.get("station_id_inserted"),
                "submitted_at": r.get("submitted_at") or r.get("created_at") or "—",
                "reviewed_at": r.get("reviewed_at") or r.get("updated_at") or "—",
                "remarks_history": r.get("remarks_history", [])
            })
    except Exception:
        requests_list = []

    return render_template("station_id/dc_list.html", requests=requests_list)


@station_id_bp.route("/dc/station-id/new", methods=["GET"])
def dc_new_form():
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))
    return render_template("station_id/submit_form.html")


@station_id_bp.route("/dc/station-id/new", methods=["POST"])
def dc_submit():
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))

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
        return redirect(url_for("auth.login"))

    try:
        resp = http.get(f"{BACKEND}/all", headers=_headers())
        requests_list = resp.json() if resp.status_code == 200 else []
    except http.exceptions.ConnectionError:
        requests_list = []

    return render_template("station_id/chips_list.html", requests=requests_list)


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
        return jsonify({"success": False, "error": "Session expired. Please log in again."}), 401

    # Read parameter notes cleanly, treating empty fields as Python None values
    raw_remarks = request.form.get("chips_remarks", "").strip()
    
    # 🌟 FIXED: Prepare form payloads ensuring blank text strings do not crash validation constraints
    form_payload = {
        "reviewed_by": str(session.get("user_id")),
        "station_id_value": str(request.form.get("station_id_value", "")).strip(),
    }
    if raw_remarks:
        form_payload["chips_remarks"] = raw_remarks

    try:
        # 🌟 FIXED: Use data=form_payload to explicitly encode as clean x-www-form-urlencoded data streams
        resp = http.patch(f"{BACKEND}/{request_id}/approve", data=form_payload, headers=_headers(), timeout=10)
        
        if resp.status_code == 200:
            return jsonify({"success": True, "message": "Station ID allocated and verified successfully."})
        
        # Pull underlying FastAPI detail message blocks out clearly to display inside SweetAlert
        try:
            backend_err = resp.json().get("detail", "Backend service operational rejection.")
        except Exception:
            backend_err = f"Backend structural fault error (Status: {resp.status_code})"
            
        return jsonify({"success": False, "error": backend_err}), 400

    except Exception as network_err:
        return jsonify({"success": False, "error": f"Gateway microservice link timeout: {str(network_err)}"}), 500

@station_id_bp.route("/chips/station-id/<int:request_id>/revert", methods=["POST"])
def chips_revert(request_id):
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))

    form_data = {
        "reviewed_by": session.get("user_id"),
        "revert_reason": request.form.get("revert_reason", ""),
    }

    http.patch(f"{BACKEND}/{request_id}/revert", data=form_data, headers=_headers())
    return redirect(url_for("station_id.chips_list"))


@station_id_bp.route("/dc/station-id/export", methods=["GET"])
def dc_export_csv():
    if not session.get("access_token"):
        return "Unauthorized", 401
    ids = request.args.get("ids", "")
    try:
        params = {}
        if ids:
            params["ids"] = ids
        response = http.get(f"{BACKEND}/export-excel", params=params, headers=_headers(), stream=True)
        if response.status_code == 200:
            from flask import Response as FlaskResponse
            return FlaskResponse(
                response.iter_content(chunk_size=4096),
                content_type="text/csv",
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", "attachment; filename=station_id_requests.csv"),
                    "Cache-Control": "no-cache"
                }
            )
        return f"Export failed. Backend status: {response.status_code}", response.status_code
    except Exception as e:
        return f"Connection error: {str(e)}", 500


@station_id_bp.route("/station-id/export", methods=["GET"])
def export_station_id_proxy():
    if not session.get("access_token"):
        return "Unauthorized", 401
    ids = request.args.get("ids", "")
    try:
        response = http.get(f"{BACKEND}/export-excel", params={"ids": ids}, stream=True)
        if response.status_code == 200:
            from flask import Response as FlaskResponse
            return FlaskResponse(
                response.iter_content(chunk_size=4096),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", "attachment; filename=station_id_requests.xlsx"),
                    "Cache-Control": "no-cache"
                }
            )
        return f"Export failed. Backend status: {response.status_code}", response.status_code
    except Exception as e:
        return f"Connection error: {str(e)}", 500
