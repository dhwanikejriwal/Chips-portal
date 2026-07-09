import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app
from datetime import datetime, date

nseit_manage_bp = Blueprint("nseit_manage", __name__)

DASHBOARD_API_BASE = "http://127.0.0.1:8000"

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

    aging_filter = request.args.get('aging')
    aging_label = ""
    if aging_filter in ['0-3', '4-7', '8-15', '15plus']:
        labels = {
            '0-3': '0–3 Days',
            '4-7': '4–7 Days', 
            '8-15': '8–15 Days',
            '15plus': '15+ Days'
        }
        aging_label = labels.get(aging_filter, '')
        
        filtered_pending = []
        today = date.today()
        for r in pending_requests:
            created_at_str = r.get("created_at")
            if not created_at_str:
                continue
            try:
                created_dt = datetime.strptime(created_at_str[:19], "%Y-%m-%d %H:%M:%S")
                created_date = created_dt.date()
            except Exception:
                try:
                    created_date = datetime.strptime(created_at_str[:10], "%Y-%m-%d").date()
                except Exception:
                    continue
            
            diff_days = (today - created_date).days
            if aging_filter == '0-3' and diff_days <= 3:
                filtered_pending.append(r)
            elif aging_filter == '4-7' and 4 <= diff_days <= 7:
                filtered_pending.append(r)
            elif aging_filter == '8-15' and 8 <= diff_days <= 15:
                filtered_pending.append(r)
            elif aging_filter == '15plus' and diff_days > 15:
                filtered_pending.append(r)
        
        pending_requests = filtered_pending
    else:
        aging_filter = None
        
    return render_template(
        "chips/chips_nseit.html",
        pending_requests=pending_requests,
        processed_requests=processed_requests,
        approved_requests=processed_requests,
        aging_filter=aging_filter,
        aging_label=aging_label
    )

@nseit_manage_bp.route("/chips/nseit/expiring")
def chips_nseit_expiring():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    records = []
    try:
        response = requests.get(f"{DASHBOARD_API_BASE}/dashboard/nseit/expiring", timeout=8)
        if response.status_code == 200:
            records = response.json()
    except requests.exceptions.RequestException:
        records = []

    return render_template(
        "chips/nseit_expiring.html",
        records=records,
        count=len(records),
        page_type="expiring",
    )


@nseit_manage_bp.route("/chips/nseit/expired")
def chips_nseit_expired():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    records = []
    try:
        response = requests.get(f"{DASHBOARD_API_BASE}/dashboard/nseit/expired", timeout=8)
        if response.status_code == 200:
            records = response.json()
    except requests.exceptions.RequestException:
        records = []

    return render_template(
        "chips/nseit_expired.html",
        records=records,
        count=len(records),
        page_type="expired",
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
