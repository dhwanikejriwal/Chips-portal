from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
import requests as http

operator_mapping_bp = Blueprint("operator_mapping", __name__, template_folder="../templates")

def _headers():
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    return {"Authorization": f"Bearer {str(raw_token).strip()}"} if raw_token else {}

@operator_mapping_bp.route("/dc/operator-mapping", methods=["GET"])
def dc_operator_mapping():
    # Only DCs can access
    if session.get("role") not in ["DC", "EDM", "Admin", "chips_admin"]:
        return redirect(url_for("auth.login"))
        
    return render_template("operator_mapping/mapping_form.html")

@operator_mapping_bp.route("/dc/operator-mapping/options", methods=["GET"])
def get_mapping_options():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping/options"
        resp = http.get(backend_url, headers=_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@operator_mapping_bp.route("/dc/operator-mapping", methods=["POST"])
def create_mapping():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping"
        resp = http.post(backend_url, json=request.json, headers=_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@operator_mapping_bp.route("/dc/operator-mapping/api-list", methods=["GET"])
def list_mappings():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping"
        resp = http.get(backend_url, headers=_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@operator_mapping_bp.route("/dc/operator-mapping/<int:mapping_id>", methods=["DELETE"])
def delete_mapping(mapping_id):
    try:
        reason = request.args.get("reason", "Inactive")
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping/{mapping_id}?reason={reason}"
        resp = http.delete(backend_url, headers=_headers(), timeout=30)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
