from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app
import requests as http

operator_mapping_bp = Blueprint("operator_mapping", __name__, template_folder="../templates")

def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}

@operator_mapping_bp.route("/dc/operator-mapping", methods=["GET"])
def dc_operator_mapping():
    # Only DCs can access
    if session.get("role") != "DC":
        return redirect(url_for("auth.login"))
        
    return render_template("operator_mapping/dc_list.html")

@operator_mapping_bp.route("/dc/operator-mapping/options", methods=["GET"])
def get_mapping_options():
    try:
        print("Hitting /dc/operator-mapping/options in Flask proxy!!!")
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping/options"
        print("Backend URL:", backend_url)
        resp = http.get(backend_url, headers=_headers())
        with open("C:/chips-portal/debug_mapping.txt", "w") as f:
            f.write(f"Status: {resp.status_code}\nText: {resp.text}\n")
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        print("Flask Proxy Error:", str(e))
        return jsonify({"detail": str(e)}), 500

@operator_mapping_bp.route("/dc/operator-mapping", methods=["POST"])
def create_mapping():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping"
        resp = http.post(backend_url, json=request.json, headers=_headers())
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@operator_mapping_bp.route("/dc/operator-mapping/api-list", methods=["GET"])
def list_mappings():
    try:
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping"
        resp = http.get(backend_url, headers=_headers())
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@operator_mapping_bp.route("/dc/operator-mapping/<int:mapping_id>", methods=["DELETE"])
def delete_mapping(mapping_id):
    try:
        reason = request.args.get("reason", "")
        base = current_app.config['BACKEND_API_URL'].replace("/api", "")
        backend_url = f"{base}/operator-mapping/dc/operator-mapping/{mapping_id}?reason={reason}"
        resp = http.delete(backend_url, headers=_headers())
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
