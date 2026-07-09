import requests
from flask import Blueprint, render_template, redirect, url_for, session, flash, current_app, jsonify

monitoring_bp = Blueprint("monitoring", __name__)

@monitoring_bp.route("/chips/dc-monitoring")
def dc_monitoring():
    if "access_token" not in session or session.get("role") != "Admin":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/monitoring/dc-stats"
    districts_stats = []
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            districts_stats = response.json()
    except requests.exceptions.RequestException:
        flash("Error connecting to backend API server.", "danger")
        
    return render_template(
        "chips/dc_monitoring.html",
        districts_stats=districts_stats
    )

@monitoring_bp.route("/chips/dc-monitoring/district-detail/<district_code>")
def district_detail(district_code):
    if "access_token" not in session or session.get("role") != "Admin":
        return jsonify({"detail": "Unauthorized"}), 401
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/monitoring/district-detail/{district_code}"
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException:
        return jsonify({"detail": "Error connecting to backend API server."}), 500

@monitoring_bp.route("/chips/dc-monitoring/candidate-history/<request_code>")
def candidate_history(request_code):
    if "access_token" not in session or session.get("role") != "Admin":
        return jsonify({"detail": "Unauthorized"}), 401
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/monitoring/candidate-history/{request_code}"
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException:
        return jsonify({"detail": "Error connecting to backend API server."}), 500
