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
                        redirect_url = url_for("lms.chips_admin_dashboard")
                    else:
                        redirect_url = url_for("lms.dc_dashboard")
                    
                    return f'<script>window.location.href = "{redirect_url}\";</script>'
                else:
                    return '<p class="text-red-500 text-xs text-center mt-2">❌ Failed to retrieve user profile.</p>'
            else:
                error_detail = response.json().get("detail", "Invalid credentials.")
                return f'<p class="text-red-500 text-xs text-center mt-2">❌ {error_detail}</p>'
            
        except requests.exceptions.ConnectionError:
            return '<p class="text-red-500 text-xs text-center mt-2">❌ Auth Gateway (Port 8000) Offline</p>'
        

    @app.route("/auth/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_view"))

    # Register modular feature blueprints
    from app.blueprints.noc import noc_bp
    from app.blueprints.station import station_bp
    from app.blueprints.approvals import approvals_bp
    from app.blueprints.lms import lms_bp

    app.register_blueprint(noc_bp)
    app.register_blueprint(station_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(lms_bp)

    return app