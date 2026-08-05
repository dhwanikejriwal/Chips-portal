from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
import requests as http

operator_onboarding_bp = Blueprint("operator_onboarding", __name__, template_folder="../templates")

def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}

@operator_onboarding_bp.route("/dc/operator-onboarding", methods=["GET"])
def dc_operator_onboarding():
    # Only DCs can access
    if session.get("role") != "DC":
        return redirect(url_for("auth.login"))
        
    return render_template("operator_onboarding/onboarding_form.html")

@operator_onboarding_bp.route("/dc/operator-onboarding/options", methods=["GET"])
def get_onboarding_options():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-onboarding/dc/operator-onboarding/options"
        resp = http.get(backend_url, headers=_headers())
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@operator_onboarding_bp.route("/dc/operator-onboarding", methods=["POST"])
def confirm_onboarding():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-onboarding/dc/operator-onboarding"
        resp = http.post(backend_url, json=request.json, headers=_headers())
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
