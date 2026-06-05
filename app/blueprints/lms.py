# app/blueprints/lms.py
from flask import Blueprint, render_template, request, session, redirect, url_for
import requests
from datetime import datetime, timedelta

lms_bp = Blueprint('lms', __name__)

# 3. DC Dashboard Overview View
@lms_bp.route("/dc/dashboard", methods=["GET"])
def dc_dashboard():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    role = session.get("role")
    if role == "chips_admin":
        return redirect(url_for("lms.chips_admin_dashboard"))
    elif role != "dc":
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get("http://127.0.0.1:8000/lms/requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
        else:
            requests_list = []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    lms_count = len(requests_list)
    l1_count = 0
    l2_count = 0
    noc_count = 0
    
    return render_template(
        "dc/dc_dash.html",
        lms_count=lms_count,
        l1_count=l1_count,
        l2_count=l2_count,
        noc_count=noc_count
    )

# 4. DC LMS Registration Router View
@lms_bp.route("/lms", methods=["GET"])
def lms_dashboard():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    role = session.get("role")
    if role == "chips_admin":
        return redirect(url_for("lms.chips_admin_dashboard"))
    elif role != "dc":
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get("http://127.0.0.1:8000/lms/requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
        else:
            requests_list = []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    return render_template("dc/lms.html", requests=requests_list)

# 4. Admin Dashboard Router View
@lms_bp.route("/chips/dashboard", methods=["GET"])
def chips_admin_dashboard():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    role = session.get("role")
    if role == "dc":
        return redirect(url_for("lms.lms_dashboard"))
    elif role != "chips_admin":
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get("http://127.0.0.1:8000/lms/requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
        else:
            requests_list = []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    total_count = len(requests_list)
    pending_count = len([r for r in requests_list if r["status"] == "pending"])
    approved_count = len([r for r in requests_list if r["status"] == "assigned"])
    rejected_count = 0
    recent_requests = requests_list[:10]  # Show recent 10 requests
    
    return render_template(
        "chips/chips_dash.html", 
        total_count=total_count,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        recent_requests=recent_requests
    )

# 4b. Admin LMS Review Page View
@lms_bp.route("/chips/lms", methods=["GET"])
def chips_lms_view():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    role = session.get("role")
    if role == "dc":
        return redirect(url_for("lms.lms_dashboard"))
    elif role != "chips_admin":
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get("http://127.0.0.1:8000/lms/requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
        else:
            requests_list = []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    # Filter pending vs approved requests
    pending_requests = [r for r in requests_list if r["status"] == "pending"]
    approved_requests = [r for r in requests_list if r["status"] == "assigned"]
    
    return render_template(
        "chips/chips_lms.html", 
        pending_requests=pending_requests, 
        approved_requests=approved_requests
    )

# 5. Form Submission Endpoint (Proxy to FastAPI)
@lms_bp.route("/lms/request", methods=["POST"])
def process_lms_form():
    jwt_token = session.get("access_token", "")
    
    payload = {
        "operator_first_name": request.form.get("first_name"),
        "operator_middle_name": request.form.get("middle_name") or None,
        "operator_last_name": request.form.get("last_name"),
        "operator_phone": request.form.get("phone"),
        "operator_email": request.form.get("email")
    }

    headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        fastapi_url = "http://127.0.0.1:8000/lms/request"
        response = requests.post(fastapi_url, json=payload, headers=headers)
        
        if response.status_code == 201:
            data = response.json()
            ist_time_str = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
            return f"""
            <tr data-name="{payload['operator_first_name']} {payload['operator_last_name']}" data-email="{payload['operator_email']}" data-status="pending" data-created="{ist_time_str}">
                <td>{payload['operator_first_name']} {payload['operator_last_name']}</td>
                <td>{payload['operator_email']}</td>
                <td><span class="badge badge-pending">Pending</span></td>
                <td>{ist_time_str}</td>
                <td>-</td>
                <td><code>-</code></td>
                <td><code>-</code></td>
            </tr>
            """, 200, {"HX-Trigger": "clearError"}
        else:
            raw_detail = response.json().get("detail", "Backend operational failure.")
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

# 6. Admin Credentials Assignment Endpoint (Proxy to FastAPI)
@lms_bp.route("/chips/assign/<int:request_id>", methods=["POST"])
def assign_credentials(request_id):
    jwt_token = session.get("access_token", "")
    
    payload = {
        "generated_login_id": request.form.get(f"generated_login_id_{request_id}"),
        "generated_password_raw": request.form.get(f"generated_password_raw_{request_id}")
    }
    print(f"DEBUG assign: form={request.form}, payload={payload}")

    headers = {
        "Authorization": f"Bearer {jwt_token}"
    }

    try:
        fastapi_url = f"http://127.0.0.1:8000/lms/assign/{request_id}"
        response = requests.put(fastapi_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return "", 200, {"HX-Refresh": "true"}
        else:
            error_msg = response.json().get("detail", "Backend operational failure.")
            return f'<p class="text-red-500 text-xs mt-2">❌ {error_msg}</p>', 400
            
    except requests.exceptions.ConnectionError:
        return '<p class="text-red-500 text-xs mt-2">❌ Connection to backend failed</p>', 500
