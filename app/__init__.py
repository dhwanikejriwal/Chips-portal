# app/__init__.py
from flask import Flask, render_template, request, redirect, url_for, session
from flask_migrate import Migrate
from app.models import db
from app.config import Config
import requests

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

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
        # 2. Authenticate directly against the FastAPI login gateway
            backend_auth_url = "http://127.0.0.1:8000/auth/login"
            response = requests.post(backend_auth_url, data=login_payload) # sends as form-data
        
            if response.status_code == 200:
                token_data = response.json()
            # 3. Save the actual cryptographic JWT token inside the user's session cookie
                session["access_token"] = token_data.get("access_token")
            
                return f'<script>window.location.href = "{url_for("lms_dashboard")}\";</script>'
            else:
                error_detail = response.json().get("detail", "Invalid credentials.")
                return f'<p class="text-red-500 text-xs text-center mt-2">❌ {error_detail}</p>'
            
        except requests.exceptions.ConnectionError:
            return '<p class="text-red-500 text-xs text-center mt-2">❌ Auth Gateway (Port 8000) Offline</p>'
        

    # 3. Main Dashboard Router View
    @app.route("/lms", methods=["GET"])
    def lms_dashboard():
        return render_template("dc/lms.html")

    # 4. Form Submission Endpoint (MOVE SESSION LOGIC HERE)
    @app.route("/lms/request", methods=["POST"])
    def process_lms_form():
        # ✅ FIX: Grabbing session variable INSIDE the request context wrapper
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
            # Outbound forward directly to the live running FastAPI port engine
            fastapi_url = "http://127.0.0.1:8000/lms/request"
            response = requests.post(fastapi_url, json=payload, headers=headers)
            
            if response.status_code == 201:
                data = response.json()
                return f"""
                <tr>
                    <td class="p-3 text-white">{payload['operator_first_name']} {payload['operator_last_name']}</td>
                    <td class="p-3 text-gray-400">{payload['operator_email']}</td>
                    <td class="p-3"><span class="text-yellow-500">Pending (ID: {data.get('request_id')})</span></td>
                </tr>
                """
            else:
                error_msg = response.json().get("detail", "Backend operational failure.")
                return f'<tr><td colspan="3" class="p-3 text-red-500">❌ Error: {error_msg}</td></tr>'
                
        except requests.exceptions.ConnectionError:
            return '<tr><td colspan="3" class="p-3 text-red-500">❌ Cannot connect to FastAPI Core Gateway (Port 8000)</td></tr>'

    @app.route("/auth/logout")
    def logout():
        session.clear() # Wipe session data clear
        return redirect(url_for("login_view"))

    return app