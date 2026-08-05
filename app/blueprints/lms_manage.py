# app/blueprints/lms_manage.py
import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, Response
from app.utils.aging import parse_aging_filter, filter_by_aging

lms_manage_bp = Blueprint("lms_manage", __name__)

def _headers():
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    return {"Authorization": f"Bearer {str(raw_token).strip()}"}


@lms_manage_bp.route("/dc/lms")
def dc_lms():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/candidates"
    pending_requests = []
    processed_requests = []
    sent_to_chips_requests = []
    try:
        response = requests.get(backend_url, params={"district_code": session.get("district_id")}, headers=_headers())
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        if response.status_code == 200:
            requests_list = response.json()
            pending_requests = [r for r in requests_list if str(r["lms_status"]).strip().upper() in ["PENDING", "REAPPLIED"]]
            processed_requests = [r for r in requests_list if str(r["lms_status"]).strip().upper() in ["APPROVED", "REVERTED", "REVERTED_BY_CHIPS"]]
            sent_to_chips_requests = [r for r in requests_list if str(r["lms_status"]).strip().upper() in ["FORWARDED", "FORWARDED_AGAIN"]]
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        
    all_pending = list(pending_requests)
    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_requests = filter_by_aging(pending_requests, aging_filter, "created_at")
        
    return render_template(
        "lms/dc_lms.html",
        pending_requests=pending_requests,
        processed_requests=processed_requests,
        sent_to_chips_requests=sent_to_chips_requests,
        approved_requests=processed_requests,
        all_pending_requests=all_pending,
        aging_filter=aging_filter,
        aging_label=aging_label
    )

@lms_manage_bp.route("/chips/lms")
def chips_lms():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/candidates"
    pending_requests = []
    processed_requests = []
    try:
        response = requests.get(backend_url, headers=_headers())
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        if response.status_code == 200:
            requests_list = response.json()
            for r in requests_list:
                if str(r.get("lms_status")).strip().upper() == "REAPPLIED":
                    has_chips_remark = any(rem.get("sender_role") == "CHIPS" for rem in r.get("remarks_history", []))
                    if has_chips_remark:
                        r["lms_status"] = "REVERTED_BY_CHIPS"
            pending_requests = [r for r in requests_list if str(r["lms_status"]).strip().upper() in ["FORWARDED", "FORWARDED_AGAIN"]]
            processed_requests = [r for r in requests_list if str(r["lms_status"]).strip().upper() in ["APPROVED", "REVERTED_BY_CHIPS"]]
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        
    all_pending = list(pending_requests)
    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_requests = filter_by_aging(pending_requests, aging_filter, "created_at")

    return render_template(
        "lms/chips_lms.html",
        pending_requests=pending_requests,
        processed_requests=processed_requests,
        approved_requests=processed_requests,
        all_pending_requests=all_pending,
        aging_filter=aging_filter,
        aging_label=aging_label
    )

@lms_manage_bp.route("/dc/forward-lms/<int:r_id>", methods=["POST"])
def forward_lms(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("remark")
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user session expired. Please log in again."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/forward/{r_id}"
    try:
        response = requests.post(backend_url, json={
            "remark": remark,
            "by_user_id": by_user_id
        }, headers=_headers())
        if response.status_code == 200:
            return {"success": True}
        else:
            return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"detail": "Error connecting to backend API server."}, 500

@lms_manage_bp.route("/dc/approve-lms/<int:r_id>", methods=["POST"])
def approve_lms(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("remark")
    by_user_id = session.get("user_id")
    
    force_without_email = request.form.get("force_without_email") == "true"
    
    if not by_user_id:
        return {"detail": "Admin user session expired. Please log in again."}, 400

    if not remark:
        remark = ""

    backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/approve/{r_id}"
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

@lms_manage_bp.route("/dc/revert-lms/<int:r_id>", methods=["POST"])
def revert_lms(r_id):
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return {"detail": "Unauthorized"}, 401
        
    remark = request.form.get("revert_reason")
    by_user_id = session.get("user_id")
    
    if not by_user_id:
        return {"detail": "Admin user session expired. Please log in again."}, 400
    if not remark or not remark.strip():
        return {"detail": "Revert reason is mandatory."}, 400
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/revert/{r_id}"
    try:
        response = requests.post(backend_url, json={
            "remark": remark,
            "by_user_id": by_user_id
        }, headers=_headers())
        if response.status_code == 200:
            return {"success": True}
        else:
            return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"detail": "Error connecting to backend API server."}, 500

@lms_manage_bp.route("/lms-manage/export", methods=["GET"])
def export_lms_proxy():
    if "access_token" not in session or session.get("role") not in ["DC", "EDM", "Admin"]:
        return "Unauthorized", 401
    ids = request.args.get("ids", "")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/export-excel"
    try:
        response = requests.get(backend_url, params=request.args.to_dict(), headers=_headers(), stream=True)
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        if response.status_code == 200:
            return Response(
                response.iter_content(chunk_size=4096),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", "attachment; filename=lms_requests.csv"),
                    "Cache-Control": "no-cache"
                }
            )
        return f"Export failed. Backend status: {response.status_code}", response.status_code
    except Exception as e:
        return f"Connection error: {str(e)}", 500
