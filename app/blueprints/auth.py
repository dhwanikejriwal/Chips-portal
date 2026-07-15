import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app, Response

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Call the FastAPI backend for login
        backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/login"
        
        try:
            response = requests.post(backend_url, json={
                "username": username,
                "password": password
            })
            
            if response.status_code == 200:
                data = response.json()
                # Store JWT and info in Flask Session
                session.permanent = True
                session["access_token"] = data["access_token"]
                session["role"] = data["role"]
                session["username"] = username
                session["district_id"] = data["district_id"]
                session["district_name"] = data.get("district_name", "")
                session["user_id"] = data.get("user_id")
                
                # Redirect based on user role
                if data["role"] == "Admin":
                    return redirect(url_for("dashboard.chips_dashboard"))
                elif data["role"] in ["DC", "EDM"]:
                    return redirect(url_for("dashboard.dc_dashboard"))
                elif data["role"] == "Candidate":
                    session["r_id"] = data.get("r_id")
                    session["has_changed_password"] = data.get("has_changed_password", True)
                    return redirect(url_for("candidate.instructions"))
                else:
                    flash("Role not supported in this interface.", "danger")
            else:
                error_msg = response.json().get("detail", "Invalid credentials")
                flash(error_msg, "danger")
                
        except requests.exceptions.RequestException as e:
            flash("Error connecting to backend API server.", "danger")
            
    return render_template("auth/login.html")

@auth_bp.route("/logout")
def logout():
    role = session.get("role")
    access_token = session.get("access_token")

    if access_token and role in ["Admin", "DC", "EDM"]:
        backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/logout"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            requests.post(backend_url, headers=headers, timeout=5)
        except Exception as e:
            print(f"Error calling backend logout: {e}")

    session.clear()
    flash("You have been logged out successfully.", "success")
    if role == "Candidate":
        return redirect(url_for("auth.login", mode="candidate"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password():
    return render_template("auth/forgot_password.html")

@auth_bp.route("/api/send-reset-otp", methods=["POST"])
def send_reset_otp():
    username = request.json.get("username")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/forgot-password"
    try:
        response = requests.post(backend_url, json={"username": username})
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"success": False, "detail": "Error connecting to backend API server."}, 500

@auth_bp.route("/api/verify-reset-otp", methods=["POST"])
def verify_reset_otp():
    payload = request.json
    backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/reset-password"
    try:
        response = requests.post(backend_url, json=payload)
        # If successful, we can also flash a message for the next page load (login)
        if response.status_code == 200:
            flash("Password reset successfully. You can now login.", "success")
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"success": False, "detail": "Error connecting to backend API server."}, 500


# =========================================================================
# 🌟 CENTRALIZED SECURE DATA EXPORT TUNNEL ROUTE
# =========================================================================
# =========================================================================
# 🌟 UPDATE THIS STRING AT THE BOTTOM OF app/blueprints/auth.py
# =========================================================================
@auth_bp.route('/admin-dc/export/<string:module_endpoint>')
def proxy_backend_excel_export(module_endpoint):
    if not session.get("access_token"):
        flash("Unauthorized access. Please log in first.", "danger")
        return redirect(url_for("auth.login"))

    if module_endpoint == 'lms-requests':
        backend_url = f"{current_app.config['BACKEND_API_URL']}/lms_manage/export-excel"
    elif module_endpoint == 'nseit-requests':
        backend_url = f"{current_app.config['BACKEND_API_URL']}/nseit_manage/export-excel"
    elif module_endpoint == 'candidate-requests':
        backend_url = f"{current_app.config['BACKEND_API_URL']}/selection/export-excel"
    else:
        backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/export-download/{module_endpoint}"
    
    params = request.args.to_dict()
    access_token = session.get("access_token", "")

    try:
        response = requests.get(
            backend_url,
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            stream=True
        )
        if response.status_code == 200:
            return Response(
                response.raw.read(),
                headers={
                    'Content-Disposition': response.headers.get('Content-Disposition'),
                    'Content-Type': response.headers.get('Content-Type'),
                    'Cache-Control': 'no-cache'
                }
            )
        else:
            try:
                err_detail = response.json().get("detail", "Generation failed.")
            except Exception:
                err_detail = f"Server returned status code {response.status_code}"
            flash(f"Export Compilation Error: {err_detail}", "danger")
            return redirect(request.referrer or url_for("dashboard.dc_dashboard"))

    except requests.exceptions.RequestException as e:
        flash(f"Unable to reach the backend export engine service: {str(e)}", "danger")
        return redirect(request.referrer or url_for("dashboard.dc_dashboard"))

@auth_bp.route('/admin-dc/export-l2/<string:module_endpoint>')
def proxy_l2_excel_export(module_endpoint):
    if not session.get("access_token"):
        flash("Unauthorized access. Please log in first.", "danger")
        return redirect(url_for("auth.login"))
    
    backend_url = f"{current_app.config['BACKEND_API_URL']}/l2-registration/export-excel/{module_endpoint}"

    try:
        response = requests.get(backend_url, stream=True)
        if response.status_code == 200:
            return Response(
                response.raw.read(),
                headers={
                    'Content-Disposition': response.headers.get('Content-Disposition'),
                    'Content-Type': response.headers.get('Content-Type'),
                    'Cache-Control': 'no-cache'
                }
            )
        else:
            try:
                err_detail = response.json().get("detail", "Generation failed.")
            except Exception:
                err_detail = f"Server returned status code {response.status_code}"
            flash(f"Export Compilation Error: {err_detail}", "danger")
            return redirect(request.referrer or url_for("dashboard.dc_dashboard"))

    except requests.exceptions.RequestException as e:
        flash(f"Unable to reach the backend export engine service: {str(e)}", "danger")
        return redirect(request.referrer or url_for("dashboard.dc_dashboard"))
