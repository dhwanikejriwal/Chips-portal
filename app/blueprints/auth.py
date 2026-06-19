import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app

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
    session.clear()
    flash("You have been logged out successfully.", "success")
    if role == "Candidate":
        return redirect(url_for("auth.login", mode="candidate"))
    return redirect(url_for("auth.login"))
