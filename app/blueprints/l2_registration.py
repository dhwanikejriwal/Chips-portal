# app/blueprints/l2_registration.py
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, Response
import requests
from app.utils.aging import parse_aging_filter, filter_by_aging

l2_registration_bp = Blueprint("l2_registration", __name__)
BACKEND = "http://127.0.0.1:8000/l2-registration"

# Statuses that are NOT part of the pending queue for aging purposes
_L2_NON_PENDING = {"approved", "activated", "rejected", "reverted", "reverted_by_chips", "sent_to_uidai"}

def get_valid_token():
    from flask import session
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        return raw_token.get("token", "") or raw_token.get("access_token", "")
    return str(raw_token).strip()


@l2_registration_bp.route("/dc/l2-registration/list", methods=["GET"])
def dc_list():
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
    
    dc_id = session.get("user_id")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get(f"{BACKEND}/dc/{dc_id}", headers=headers)
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        requests_list = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    requests_list.sort(key=lambda x: x.get("updated_at") or x.get("completed_at") or x.get("reviewed_at") or x.get("submitted_at") or "", reverse=True)
    return render_template("l2_registration/dc_list.html", requests=requests_list)


@l2_registration_bp.route("/dc/l2-registration/new", methods=["GET", "POST"])
def dc_new():
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
    
    if request.method == "POST":
        # Ensure disabled template dropdown forms fallback safely to active session dictionary values
        resolved_district = request.form.get("district_id") or request.form.get("district") or session.get("district_id")
        
        form_data = {
            "dc_id": int(session.get("user_id")),
            "district_id": str(resolved_district).strip(),
            "client_version": request.form.get("client_version"),
            "new_station_id": request.form.get("new_station_id"),
            "ea_code": request.form.get("ea_code"),
            "reg_code": request.form.get("reg_code"),
            "new_machine_id": request.form.get("new_machine_id"),
            "client_type": request.form.get("client_type"),
            "old_station_id": request.form.get("old_station_id"),
            "reason_for_l2_registration": request.form.get("reason_for_l2_registration"),
            "old_machine_id": request.form.get("old_machine_id"),
            "tech_center_remarks": request.form.get("tech_center_remarks"),
            "operator_name": request.form.get("operator_name"),
            "operator_id": request.form.get("operator_id"),
            "unique_id": request.form.get("unique_id") if request.form.get("unique_id") else None,
            "block": request.form.get("block"),
            "address_of_govt_premises": request.form.get("address_of_govt_premises"),
        }
        headers = {"Authorization": f"Bearer {jwt_token}"}
        try:
            response = requests.post(f"{BACKEND}/submit", data=form_data, headers=headers)
            
            # 🌟 FIX: Accept both 200 OK and 201 Created response states safely from the backend microservice
            if response.status_code in [200, 201]:
                return jsonify({"status": "success", "message": "L2 Registration request submitted successfully."})
            else:
                # 🌟 FIX: Safely unpack error detail text string dictionaries without crashing
                try:
                    backend_json = response.json()
                    err_msg = backend_json.get("detail") if isinstance(backend_json, dict) else response.text
                    if isinstance(err_msg, list): 
                        err_msg = err_msg[0].get("msg") if (len(err_msg) > 0 and isinstance(err_msg[0], dict)) else str(err_msg)
                except Exception:
                    err_msg = response.text if response.text else "Internal server lifecycle exception."
                    
                return jsonify({"status": "error", "message": str(err_msg)}), 400
        except requests.exceptions.ConnectionError:
            return jsonify({"status": "error", "message": "Backend Microservice Offline."}), 500

    return render_template("l2_registration/submit_form.html")


@l2_registration_bp.route("/dc/l2-registration/<int:request_id>/reapply", methods=["POST"])
def dc_reapply(request_id):
    jwt_token = get_valid_token()
    if not jwt_token:
        return jsonify({"detail": "Unauthorized"}), 401
        
    form_data = {
        "dc_id": session.get("user_id"),
        "client_version": request.form.get("client_version"),
        "new_station_id": request.form.get("new_station_id"),
        "ea_code": request.form.get("ea_code"),
        "reg_code": request.form.get("reg_code"),
        "new_machine_id": request.form.get("new_machine_id"),
        "client_type": request.form.get("client_type"),
        "old_station_id": request.form.get("old_station_id"),
        "reason_for_l2_registration": request.form.get("reason_for_l2_registration"),
        "old_machine_id": request.form.get("old_machine_id"),
        "tech_center_remarks": request.form.get("tech_center_remarks"),
        "operator_name": request.form.get("operator_name"),
        "operator_id": request.form.get("operator_id"),
        "unique_id": request.form.get("unique_id"),
        "block": request.form.get("block"),
        "address_of_govt_premises": request.form.get("address_of_govt_premises"),
        "reapply_remark": request.form.get("reapply_remark")
    }
    
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.post(f"{BACKEND}/dc/{request_id}/reapply", data=form_data, headers=headers)
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Reapplied successfully."})
        else:
            return jsonify({"status": "error", "detail": response.json().get("detail", "Error reapplying.")}), 400
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "detail": "Backend Offline."}), 500


@l2_registration_bp.route("/chips/l2-registration", methods=["GET"])
def chips_list():
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get(f"{BACKEND}/all", headers=headers)
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        requests_list = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        requests_list = []
        
    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_subset = [
            r for r in requests_list
            if str(r.get("status", "")).strip().lower() not in _L2_NON_PENDING
        ]
        requests_list = filter_by_aging(pending_subset, aging_filter, "submitted_at")

    return render_template(
        "l2_registration/chips_list.html",
        requests=requests_list,
        aging_filter=aging_filter,
        aging_label=aging_label,
    )


@l2_registration_bp.route("/chips/l2-registration/<int:request_id>/detail-json", methods=["GET"])
def chips_detail_json(request_id):
    jwt_token = get_valid_token()
    if not jwt_token:
        return jsonify({"detail": "Unauthorized"}), 401
    
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = requests.get(f"{BACKEND}/{request_id}", headers=headers)
        return Response(
            response.content,
            status=response.status_code,
            content_type=response.headers.get("Content-Type", "application/json")
        )
    except requests.exceptions.ConnectionError:
        return jsonify({"detail": "Backend offline"}), 500


@l2_registration_bp.route("/chips/l2-registration/<int:request_id>/send-to-uidai", methods=["POST"])
def chips_send_to_uidai(request_id):
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", "")
    }
    requests.patch(f"{BACKEND}/{request_id}/send-to-uidai", data=form_data, headers=headers)
    return redirect(url_for("l2_registration.chips_list"))


@l2_registration_bp.route("/chips/l2-registration/<int:request_id>/uidai-approve", methods=["POST"])
def chips_uidai_approve(request_id):
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", "")
    }
    requests.patch(f"{BACKEND}/{request_id}/uidai-approve", data=form_data, headers=headers)
    return redirect(url_for("l2_registration.chips_list"))


@l2_registration_bp.route("/chips/l2-registration/<int:request_id>/uidai-reject", methods=["POST"])
def chips_uidai_reject(request_id):
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", "")
    }
    requests.patch(f"{BACKEND}/{request_id}/uidai-reject", data=form_data, headers=headers)
    return redirect(url_for("l2_registration.chips_list"))


@l2_registration_bp.route("/chips/l2-registration/<int:request_id>/revert", methods=["POST"])
def chips_revert(request_id):
    jwt_token = get_valid_token()
    if not jwt_token:
        return redirect(url_for("login_view"))
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "revert_reason": request.form.get("revert_reason", "")
    }
    requests.patch(f"{BACKEND}/{request_id}/revert", data=form_data, headers=headers)
    return redirect(url_for("l2_registration.chips_list"))


@l2_registration_bp.route("/chips/l2-registration/export-excel", methods=["GET"])
def export_uidai():
    jwt_token = get_valid_token()
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{BACKEND}/export-excel/uidai", headers=headers, params=params, stream=True)
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=uidai_l2_queue.csv"}
    )


@l2_registration_bp.route("/chips/l2-registration/export-excel/pending", methods=["GET"])
def export_pending():
    jwt_token = get_valid_token()
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{BACKEND}/export-excel/pending", headers=headers, params=params, stream=True)
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pending_l2_queue.csv"}
    )


@l2_registration_bp.route("/chips/l2-registration/export-excel/credentials", methods=["GET"])
def export_creds():
    jwt_token = get_valid_token()
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{BACKEND}/export-excel/credentials", headers=headers, params=params, stream=True)
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=processed_l2_history.csv"}
    )


@l2_registration_bp.route("/dc/l2-registration/export-excel/pending", methods=["GET"])
def dc_export_pending():
    jwt_token = get_valid_token()
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{BACKEND}/export-excel/pending", headers=headers, params=params, stream=True)
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pending_l2_queue.csv"}
    )


@l2_registration_bp.route("/dc/l2-registration/export-excel/credentials", methods=["GET"])
def dc_export_creds():
    jwt_token = get_valid_token()
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{BACKEND}/export-excel/credentials", headers=headers, params=params, stream=True)
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=history_l2_queue.csv"}
    )
