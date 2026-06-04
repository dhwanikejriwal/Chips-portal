# app/__init__.py
from flask import Flask, render_template, request, redirect, url_for, session
from app.config import Config
import requests

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 1. Standard Login Page Route
    @app.route("/", methods=["GET"])
    def login_view():
        return render_template("auth/login.html")

    # 2. Login Submit Processor
    @app.route("/auth/login", methods=["POST"])
    def handle_login():
        username = request.form.get("username")
        password = request.form.get("password")

        login_payload = {
            "username": username,
            "password": password
        }
        try:
            # Authenticate directly against the FastAPI login gateway
            backend_auth_url = "http://127.0.0.1:8000/auth/login"
            response = requests.post(backend_auth_url, data=login_payload)
        
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                session["access_token"] = access_token
            
                # Fetch user details from backend to know their role and district
                me_response = requests.get(
                    "http://127.0.0.1:8000/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if me_response.status_code == 200:
                    profile = me_response.json()
                    session["username"] = profile.get("username")
                    session["role"] = profile.get("role")
                    session["district_id"] = profile.get("district_id")
                    session["district_name"] = profile.get("district_name")
                    
                    if profile.get("role") == "chips_admin":
                        redirect_url = url_for("chips_admin_dashboard")
                    else:
                        redirect_url = url_for("lms_dashboard")
                    
                    return f'<script>window.location.href = "{redirect_url}\";</script>'
                else:
                    return '<p class="text-red-500 text-xs text-center mt-2">❌ Failed to retrieve user profile.</p>'
            else:
                error_detail = response.json().get("detail", "Invalid credentials.")
                return f'<p class="text-red-500 text-xs text-center mt-2">❌ {error_detail}</p>'
            
        except requests.exceptions.ConnectionError:
            return '<p class="text-red-500 text-xs text-center mt-2">❌ Auth Gateway (Port 8000) Offline</p>'
        

    # 3. DC Dashboard Router View
    @app.route("/lms", methods=["GET"])
    def lms_dashboard():
        jwt_token = session.get("access_token")
        if not jwt_token:
            return redirect(url_for("login_view"))
            
        role = session.get("role")
        if role == "chips_admin":
            return redirect(url_for("chips_admin_dashboard"))
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
    @app.route("/chips/dashboard", methods=["GET"])
    def chips_admin_dashboard():
        jwt_token = session.get("access_token")
        if not jwt_token:
            return redirect(url_for("login_view"))
            
        role = session.get("role")
        if role == "dc":
            return redirect(url_for("lms_dashboard"))
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
    @app.route("/lms/request", methods=["POST"])
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
                from datetime import datetime, timedelta
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
    @app.route("/chips/assign/<int:request_id>", methods=["POST"])
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
                # Trigger a page reload in HTMX to refresh both tables
                return "", 200, {"HX-Refresh": "true"}
            else:
                error_msg = response.json().get("detail", "Backend operational failure.")
                return f'<p class="text-red-500 text-xs mt-2">❌ {error_msg}</p>', 400
                
        except requests.exceptions.ConnectionError:
            return '<p class="text-red-500 text-xs mt-2">❌ Connection to backend failed</p>', 500

    @app.route("/auth/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_view"))

    return app