import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app

selection_bp = Blueprint("selection", __name__)

@selection_bp.route("/dc/candidate-requests")
def dc_candidate_requests():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/candidates"
    pending_requests = []
    approved_requests = []
    try:
        response = requests.get(backend_url, params={"district_code": session.get("district_id")})
        if response.status_code == 200:
            candidates = response.json()
            pending_requests = [c for c in candidates if c["status"] == "Pending"]
            approved_requests = [c for c in candidates if c["status"] in ["Approved", "Rejected"]]
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
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user ID session expired. Please log in again."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/approve-candidate/{r_id}"
    try:
        response = requests.post(backend_url, json={
            "username": username,
            "password": password,
            "remark": remark,
            "by_user_id": by_user_id
        })
        if response.status_code == 200:
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
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user ID session expired. Please log in again."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/reject-candidate/{r_id}"
    try:
        response = requests.post(backend_url, json={
            "remark": remark,
            "by_user_id": by_user_id
        })
        if response.status_code == 200:
            return {"success": True}
        else:
            return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"detail": "Error connecting to backend API server."}, 500
