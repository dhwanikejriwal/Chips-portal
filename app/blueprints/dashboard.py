from flask import Blueprint, render_template, redirect, url_for, session, flash

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dc/dashboard")
def dc_dashboard():
    # Verify user is logged in as DC or EDM
    if "access_token" not in session or session.get("role") not in ["DC", "EDM"]:
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
    return render_template("dc/dc_dash.html")

@dashboard_bp.route("/chips/dashboard")
def chips_dashboard():
    # Verify user is logged in as Admin (CHIPS)
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
    return render_template("chips/chips_dash.html")
