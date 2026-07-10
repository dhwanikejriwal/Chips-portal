import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, Response

selection_bp = Blueprint("selection", __name__)

def _headers():
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    return {"Authorization": f"Bearer {str(raw_token).strip()}"}


@selection_bp.route("/dc/candidate-requests")
def dc_candidate_requests():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/candidates"
    pending_requests = []
    approved_requests = []
    try:
        response = requests.get(backend_url, params={"district_code": session.get("district_id")}, headers=_headers())
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        if response.status_code == 200:
            candidates = response.json()
            pending_requests = [c for c in candidates if str(c["status"]).strip().upper() == "PENDING"]
            approved_requests = [c for c in candidates if str(c["status"]).strip().upper() in ["APPROVED", "REJECTED"]]
        else:
            print(f"Backend API returned {response.status_code}: {response.text}")
            flash(f"Backend error: {response.text[:100]}", "danger")
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        
    return render_template(
        "dc/dc_candidate_requests.html",
        pending_requests=pending_requests,
        approved_requests=approved_requests
    )


@selection_bp.route("/dc/approve-candidate/<int:r_id>", methods=["POST"])
def approve_candidate(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    username = request.form.get("generated_login_id")
    password = request.form.get("generated_password_raw")
    remark = request.form.get("remark")
    force_without_email = request.form.get("force_without_email") == "true"
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user ID session expired. Please log in again."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/approve-candidate/{r_id}"
    try:
        response = requests.post(backend_url, json={
            "username": username,
            "password": password,
            "remark": remark,
            "by_user_id": by_user_id,
            "force_without_email": force_without_email
        }, headers=_headers())
        if response.status_code == 200:
            res_json = response.json()
            if not res_json.get("success", True):
                return res_json, 400
            return {"success": True}
        else:
            return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"detail": "Error connecting to backend API server."}, 500


@selection_bp.route("/dc/reject-candidate/<int:r_id>", methods=["POST"])
def reject_candidate(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("revert_reason")
    force_without_email = request.form.get("force_without_email") == "true"
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user ID session expired. Please log in again."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/reject-candidate/{r_id}"
    try:
        response = requests.post(backend_url, json={
            "remark": remark,
            "by_user_id": by_user_id,
            "force_without_email": force_without_email
        }, headers=_headers())
        if response.status_code == 200:
            res_json = response.json()
            if not res_json.get("success", True):
                return res_json, 400
            return {"success": True}
        else:
            return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"detail": "Error connecting to backend API server."}, 500


@selection_bp.route("/dc/candidate-requests/export")
def export_candidate_requests():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    ids = request.args.get("ids", "")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/export-excel"
    try:
        response = requests.get(backend_url, params={"ids": ids}, headers=_headers(), stream=True)
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        if response.status_code == 200:
            headers = {
                'Content-Disposition': response.headers.get('Content-Disposition', 'attachment; filename="candidate_requests.xlsx"'),
                'Content-Type': response.headers.get('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            return Response(
                response.iter_content(chunk_size=8192),
                status=response.status_code,
                headers=headers
            )
        else:
            flash("Failed to generate excel file from backend.", "danger")
            return redirect(url_for("selection.dc_candidate_requests"))
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        return redirect(url_for("selection.dc_candidate_requests"))
