# app/blueprints/noc.py
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
import requests
from datetime import datetime, timedelta

noc_bp = Blueprint('noc', __name__)

def get_error_detail(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            return data.get("detail", "Backend operational failure.")
        return data
    except Exception:
        return f"Backend Server Error ({response.status_code}). Please check backend logs."

# 1. DC NOC Page View
@noc_bp.route("/dc/noc", methods=["GET"])
def dc_noc_view():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    role = session.get("role")
    if role == "chips_admin":
        return redirect(url_for("noc.chips_noc_view"))
    elif role != "dc":
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get("http://127.0.0.1:8000/noc/requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
        else:
            requests_list = []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    return render_template("dc/noc.html", requests=requests_list)

# 2. CHIPS Admin NOC Review View
@noc_bp.route("/chips/noc", methods=["GET"])
def chips_noc_view():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    role = session.get("role")
    if role == "dc":
        return redirect(url_for("noc.dc_noc_view"))
    elif role != "chips_admin":
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get("http://127.0.0.1:8000/noc/requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
        else:
            requests_list = []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    pending_requests = [r for r in requests_list if r["status"] in ["pending", "reapplied"]]
    approved_requests = [r for r in requests_list if r["status"] in ["assigned", "revert back"]]
    
    return render_template(
        "chips/chips_noc.html",
        pending_requests=pending_requests,
        approved_requests=approved_requests
    )

# 3. DC Submit NOC Form
@noc_bp.route("/dc/noc/request", methods=["POST"])
def process_noc_form():
    jwt_token = session.get("access_token", "")
    
    payload = {
        "operator_unique_id": request.form.get("operator_unique_id"),
        "operator_first_name": request.form.get("first_name"),
        "operator_middle_name": request.form.get("middle_name") or None,
        "operator_last_name": request.form.get("last_name")
    }

    headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        fastapi_url = "http://127.0.0.1:8000/noc/request"
        response = requests.post(fastapi_url, json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            request_code = data.get("request_code", "-")
            ist_time_str = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
            middle = f" {payload['operator_middle_name']}" if payload.get('operator_middle_name') else ""
            full_name = f"{payload['operator_first_name']}{middle} {payload['operator_last_name']}"
            return f"""
            <tr data-id="{data.get('request_id')}"
                data-code="{request_code}"
                data-unique-id="{payload['operator_unique_id']}"
                data-first-name="{payload['operator_first_name']}"
                data-middle-name="{payload['operator_middle_name'] or ''}"
                data-last-name="{payload['operator_last_name']}"
                data-name="{full_name}"
                data-status="pending"
                data-remarks="[]"
                data-created="{ist_time_str}">
                <td>1</td>
                <td><strong>{request_code}</strong></td>
                <td>{payload['operator_unique_id']}</td>
                <td><strong>{full_name}</strong></td>
                <td><span class="badge badge-pending">Pending</span></td>
                <td>{ist_time_str}</td>
                <td>-</td>
                <td style="text-align: center;">
                    <button class="btn-details" onclick="openDetailsModal(this.closest('tr'))">Details</button>
                </td>
            </tr>
            """, 200, {"HX-Trigger": "clearError"}
        else:
            raw_detail = get_error_detail(response)
            if isinstance(raw_detail, list):
                error_messages = []
                for err in raw_detail:
                    loc = err.get("loc", [""])
                    field_name = str(loc[-1]).replace("_", " ").title() if loc else "Field"
                    msg = err.get("msg", "Invalid value")
                    error_messages.append(f"<strong>{field_name}</strong>: {msg}")
                error_msg = "<br>".join(error_messages)
            else:
                error_msg = str(raw_detail)
                
            error_html = f"""
            <div style="background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; padding: 12px; border-radius: 6px; font-size: 14px; margin-bottom: 15px;">
                {error_msg}
            </div>
            """
            return error_html, 400, {"HX-Retarget": "#dc-form-error"}
    except requests.exceptions.ConnectionError:
        error_html = """
        <div style="background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; padding: 12px; border-radius: 6px; font-size: 14px; margin-bottom: 15px;">
            ❌ Cannot connect to FastAPI Core Gateway (Port 8000)
        </div>
        """
        return error_html, 500, {"HX-Retarget": "#dc-form-error"}

# 4. CHIPS Issue NOC
@noc_bp.route("/chips/noc/assign/<int:request_id>", methods=["POST"])
def assign_noc_credentials(request_id):
    jwt_token = session.get("access_token", "")
    
    payload = {
        "remark": request.form.get("remark")
    }

    headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        fastapi_url = f"http://127.0.0.1:8000/noc/assign/{request_id}"
        response = requests.put(fastapi_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return "", 200, {"HX-Trigger": "credentialsAssigned"}
        else:
            error_msg = get_error_detail(response)
            return f'<p class="text-red-500 text-xs mt-2">❌ {error_msg}</p>', 400
            
    except requests.exceptions.ConnectionError:
        return '<p class="text-red-500 text-xs mt-2">❌ Connection to backend failed</p>', 500

# 5. CHIPS Revert NOC
@noc_bp.route("/chips/noc/revert/<int:request_id>", methods=["POST"])
def revert_noc_request(request_id):
    jwt_token = session.get("access_token", "")
    
    payload = {
        "revert_reason": request.form.get("revert_reason")
    }
    
    headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        fastapi_url = f"http://127.0.0.1:8000/noc/revert/{request_id}"
        response = requests.put(fastapi_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return "", 200, {"HX-Trigger": "requestReverted"}
        else:
            error_msg = get_error_detail(response)
            return f'<p class="text-red-500 text-xs mt-2">❌ {error_msg}</p>', 400
            
    except requests.exceptions.ConnectionError:
        return '<p class="text-red-500 text-xs mt-2">❌ Connection to backend failed</p>', 500

# 6. DC Reapply NOC
@noc_bp.route("/dc/noc/reapply/<int:request_id>", methods=["POST"])
def reapply_noc_request(request_id):
    jwt_token = session.get("access_token", "")
    
    payload = {
        "operator_unique_id": request.form.get("operator_unique_id"),
        "operator_first_name": request.form.get("first_name"),
        "operator_middle_name": request.form.get("middle_name") or None,
        "operator_last_name": request.form.get("last_name"),
        "remark": request.form.get("remark")
    }
    
    headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        fastapi_url = f"http://127.0.0.1:8000/noc/reapply/{request_id}"
        response = requests.put(fastapi_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return jsonify({"status": "success"}), 200
        else:
            error_msg = get_error_detail(response)
            return jsonify({"status": "error", "message": error_msg}), 400
            
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Connection to backend failed"}), 500
