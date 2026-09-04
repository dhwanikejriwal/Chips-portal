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
                session["has_changed_password"] = data.get("has_changed_password", 1)
                session["full_name"] = data.get("full_name", "")

                # Check if a valid next URL destination parameter was provided
                next_url = request.args.get("next") or request.form.get("next")
                if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                    return redirect(next_url)
                
                # Redirect based on user role
                if data["role"] == "Admin":
                    return redirect(url_for("chips_dashboard.chips_dashboard"))
                elif data["role"] in ["DC", "EDM"]:
                    return redirect(url_for("dc_dashboard.dc_dashboard"))
                elif data["role"] == "Candidate":
                    session["r_id"] = data.get("r_id")
                    session["has_changed_password"] = data.get("has_changed_password", True)
                    session["candidate_name"] = data.get("name", "")
                    session["full_name"] = data.get("name", "")
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
    expired_user = request.args.get("expired_user") or session.get("username", "")
    next_param = request.args.get("next", "")
    reason = request.args.get("reason", "")

    if access_token and role in ["Admin", "DC", "EDM"]:
        backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/logout"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            requests.post(backend_url, headers=headers, timeout=5)
        except Exception as e:
            print(f"Error calling backend logout: {e}")

    session.clear()

    redirect_kwargs = {}
    if reason == "expired":
        flash("Your login session has expired. Please log in again.", "warning")
    else:
        flash("You have been logged out successfully.", "success")

    if role == "Candidate":
        redirect_kwargs["mode"] = "candidate"
    if expired_user:
        redirect_kwargs["expired_user"] = expired_user
    if next_param and next_param.startswith("/") and not next_param.startswith("//"):
        redirect_kwargs["next"] = next_param

    return redirect(url_for("auth.login", **redirect_kwargs))


@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password():
    return render_template("auth/forgot_password.html")

@auth_bp.route("/api/verify-candidate-exists", methods=["GET"])
def verify_candidate_exists():
    username = request.args.get("username", "")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/check-candidate-exists"
    try:
        response = requests.get(backend_url, params={"username": username})
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"exists": False, "detail": "Error connecting to backend API server."}, 500

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


@auth_bp.route("/api/session-has-changed-password", methods=["POST"])
def session_has_changed_password():
    session["has_changed_password"] = 1
    return {"success": True}


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("access_token"):
        flash("Please log in first.", "danger")
        return redirect(url_for("auth.login"))
    if session.get("role") not in ["Admin", "DC", "EDM"]:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            flash("New password and confirm password do not match.", "danger")
            return render_template("auth/change_password.html")

        backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/change-password"
        try:
            response = requests.post(
                backend_url,
                json={"current_password": current_password, "new_password": new_password},
                headers={"Authorization": f"Bearer {session['access_token']}"}
            )
            data = response.json()
            if response.status_code == 200:
                session["has_changed_password"] = 1
                flash("Password changed successfully!", "success")
                role = session.get("role")
                if role == "Admin":
                    return redirect(url_for("chips_dashboard.chips_dashboard"))
                return redirect(url_for("dc_dashboard.dc_dashboard"))
            else:
                flash(data.get("detail", "Failed to change password."), "danger")
        except requests.exceptions.RequestException:
            flash("Error connecting to backend API server.", "danger")

    return render_template("auth/change_password.html")

# =========================================================================
# 🌟 CENTRALIZED SECURE DATA EXPORT TUNNEL ROUTE
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
            return redirect(request.referrer or url_for("dc_dashboard.dc_dashboard"))

    except requests.exceptions.RequestException as e:
        flash(f"Unable to reach the backend export engine service: {str(e)}", "danger")
        return redirect(request.referrer or url_for("dc_dashboard.dc_dashboard"))

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
            return redirect(request.referrer or url_for("dc_dashboard.dc_dashboard"))

    except requests.exceptions.RequestException as e:
        flash(f"Unable to reach the backend export engine service: {str(e)}", "danger")
        return redirect(request.referrer or url_for("dc_dashboard.dc_dashboard"))


def _headers():
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    return {"Authorization": f"Bearer {str(raw_token).strip()}"}


@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "access_token" not in session:
        flash("Please log in to access your profile.", "warning")
        return redirect(url_for("auth.login"))

    role = session.get("role")
    if role == "Candidate":
        return redirect(url_for("candidate.profile"))

    if role not in ["DC", "EDM", "Admin"]:
        flash("Unauthorized role access.", "danger")
        return redirect(url_for("auth.logout"))

    backend_url = f"{current_app.config['BACKEND_API_URL']}/auth/profile"

    if request.method == "POST":
        payload = {
            "full_name": request.form.get("full_name"),
            "email": request.form.get("email"),
            "phone": request.form.get("phone")
        }
        try:
            res = requests.post(backend_url, json=payload, headers=_headers())
            if res.status_code == 200:
                # Update the full_name in session as well if it changed
                session["full_name"] = payload["full_name"] or ""
                flash("Profile updated successfully!", "success")
            else:
                err_msg = res.json().get("detail", "Failed to update profile.")
                flash(err_msg, "danger")
        except Exception:
            flash("Error connecting to backend API.", "danger")
        return redirect(url_for("auth.profile"))

    # GET request
    profile_data = {}
    try:
        res = requests.get(backend_url, headers=_headers())
        if res.status_code == 200:
            profile_data = res.json()
        elif res.status_code == 401:
            return redirect(url_for("auth.logout"))
        else:
            flash("Failed to retrieve profile details from backend.", "danger")
    except Exception:
        flash("Error connecting to backend API.", "danger")

    return render_template("auth/admin_dc_profile.html", profile_data=profile_data)


@auth_bp.route("/notifications/summary", methods=["GET"])
def notification_summary_proxy():
    from flask import jsonify
    from app.utils.backend_url import get_backend_base_url
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    headers = {"Authorization": f"Bearer {str(raw_token).strip()}"} if raw_token else {}
    
    backend_target = f"{get_backend_base_url()}/api/notifications/summary"
    try:
        resp = requests.get(backend_target, headers=headers, timeout=10)
        return Response(resp.content, status=resp.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

