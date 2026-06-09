import os
import requests
from flask import Blueprint, render_template, request, jsonify, session, redirect

reactivation_bp = Blueprint('reactivation', __name__)

# URL of your FastAPI backend service
FASTAPI_URL = "http://127.0.0.1:8000/reactivation"

@reactivation_bp.route("/dc/reactivation", methods=["GET"])
def view_reactivation_dashboard():
    # Enforce session protection matching your authentication system
    if not session.get("username"):
        return redirect("/auth/login")
        
    # Fetch existing batch tracking list from backend
    try:
        # Pass user identification headers if your system requires bearer cookies
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
            
        response = requests.get(f"{FASTAPI_URL}/requests", headers=headers)
        requests_history = response.json() if response.status_code == 200 else []
    except Exception:
        requests_history = []
        
    return render_template("dc/reactivation.html", requests=requests_history)


@reactivation_bp.route("/dc/reactivation/submit", methods=["POST"])
def submit_reactivation_form():
    if not session.get("username"):
        return jsonify({"success": False, "error": "Authentication required"}), 401

    # Extract parameters
    training_date = request.form.get("training_date")
    if not training_date:
        return jsonify({"success": False, "error": "Training completion date is required."}), 400

    # Build standard string data payload for form field inputs
    data_payload = {
        "training_date": str(training_date).strip()
    }

    # Extract incoming multi-part files securely from the web form request
    try:
        files_payload = [
            ("training_photo", (request.files['training_photo'].filename, request.files['training_photo'].stream, request.files['training_photo'].mimetype)),
            ("nodal_letter", (request.files['nodal_letter'].filename, request.files['nodal_letter'].stream, request.files['nodal_letter'].mimetype)),
            ("om_letter", (request.files['om_letter'].filename, request.files['om_letter'].stream, request.files['om_letter'].mimetype)),
            ("attendance_list", (request.files['attendance_list'].filename, request.files['attendance_list'].stream, request.files['attendance_list'].mimetype))
        ]
    except KeyError as e:
        return jsonify({"success": False, "error": f"Missing file input stream attachment: {str(e)}"}), 400

    # Include authorization tokens if your backend uses session gate dependencies
    headers = {}
    if session.get("access_token"):
        headers["Authorization"] = f"Bearer {session.get('access_token')}"

    try:
        # Dispatch forward transmission straight to FastAPI endpoints
        response = requests.post(f"{FASTAPI_URL}/submit", data=data_payload, files=files_payload, headers=headers)
        
        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Batch package submitted successfully!"})
            
        try:
            backend_error = response.json().get("detail", response.text)
        except Exception:
            backend_error = response.text

        return jsonify({"success": False, "error": f"Backend Error ({response.status_code}): {backend_error}"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": f"Gateway application network transport failure: {str(e)}"}), 500