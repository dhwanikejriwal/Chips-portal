import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app

nseit_manage_bp = Blueprint("nseit_manage", __name__)

@nseit_manage_bp.route("/dc/nseit")
def dc_nseit():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/nseit_manage/candidates"
    pending_requests = []
    processed_requests = []
    try:
        response = requests.get(backend_url, params={"district_code": session.get("district_id")})
        if response.status_code == 200:
            requests_list = response.json()
            pending_requests = [r for r in requests_list if r["nseit_status"] in ["Pending", "Reapplied"]]
            processed_requests = [r for r in requests_list if r["nseit_status"] in ["Forwarded", "Forwarded Again", "Approved", "Reverted", "Reverted by CHiPS"]]
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        
    return render_template(
        "dc/dc_nseit.html",
        pending_requests=pending_requests,
        processed_requests=processed_requests,
        approved_requests=processed_requests
    )

@nseit_manage_bp.route("/chips/nseit")
def chips_nseit():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/nseit_manage/candidates"
    pending_requests = []
    processed_requests = []
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            requests_list = response.json()
            for r in requests_list:
                if r.get("nseit_status") == "Reapplied":
                    has_chips_remark = any(rem.get("sender_role") == "CHIPS" for rem in r.get("remarks_history", []))
                    if has_chips_remark:
                        r["nseit_status"] = "Reverted by CHiPS"
            pending_requests = [r for r in requests_list if r["nseit_status"] in ["Forwarded", "Forwarded Again"]]
            processed_requests = [r for r in requests_list if r["nseit_status"] in ["Approved", "Reverted by CHiPS"]]
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        
    return render_template(
        "chips/chips_nseit.html",
        pending_requests=pending_requests,
        processed_requests=processed_requests,
        approved_requests=processed_requests
    )

@nseit_manage_bp.route("/dc/forward-nseit/<int:r_id>", methods=["POST"])
def forward_nseit(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("remark")
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user session expired. Please log in again."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/nseit_manage/forward/{r_id}"
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

@nseit_manage_bp.route("/dc/approve-nseit/<int:r_id>", methods=["POST"])
def approve_nseit(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("remark")
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user session expired. Please log in again."}, 400

    if not remark or not remark.strip():
        return {"detail": "Approval remarks are mandatory."}, 400
            
    backend_url = f"{current_app.config['BACKEND_API_URL']}/nseit_manage/approve/{r_id}"
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

@nseit_manage_bp.route("/dc/revert-nseit/<int:r_id>", methods=["POST"])
def revert_nseit(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("revert_reason")
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user session expired. Please log in again."}, 400
    if not remark or not remark.strip():
        return {"detail": "Revert reason is mandatory."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/nseit_manage/revert/{r_id}"
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
