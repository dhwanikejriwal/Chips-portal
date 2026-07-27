import os, json
import requests
from flask import Blueprint, render_template, request, jsonify, session, redirect, Response
from app.utils.aging import parse_aging_filter, filter_by_aging

reactivation_bp = Blueprint('reactivation', __name__)

# URL of your FastAPI backend service
FASTAPI_URL = "http://127.0.0.1:8000/reactivation"

@reactivation_bp.route("/dc/reactivation", methods=["GET"])
@reactivation_bp.route("/chips/reactivation", methods=["GET"])
def view_reactivation_dashboard():
    # 🌟 CONNECTED: Points directly back to your portal login check screen layout
    if not session.get("username"):
        return redirect("/auth/login")
        
    try:
        # 🌟 FIXED: Cleanly handles token extraction strings just like your working station_id.py file
        raw_token = session.get("access_token", "")
        if isinstance(raw_token, dict):
            raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
            
        headers = {"Authorization": f"Bearer {str(raw_token).strip()}"}
            
        is_dc = request.path.startswith("/dc")
        api_endpoint = f"{FASTAPI_URL}/requests-with-operators"
        response = requests.get(api_endpoint, headers=headers, timeout=5)
        
        if response.status_code == 401:
            print("⚠️ WARNING: Reactivation microservice token rejected the authorization context.")
            return redirect("/auth/logout")
        raw_history = response.json() if response.status_code == 200 else []
        with open("debug_chips.txt", "w") as f:
            f.write(f"Status: {response.status_code}\nText: {response.text[:500]}\n")
        
        # 🟢 BULLETPROOF DATA MAPPER: Safe parsing with multi-layered schema fallbacks
        normalized_history_list = []
        if isinstance(raw_history, dict):
            # Inspect common payload root wrapper keys used by the reactivation microservice
            normalized_history_list = raw_history.get("requests") or raw_history.get("operators") or raw_history.get("data") or []
            if not normalized_history_list and "request_code" in raw_history:
                normalized_history_list = [raw_history]
        elif isinstance(raw_history, list):
            normalized_history_list = raw_history

        requests_history = []
        if isinstance(normalized_history_list, list):
            for req in normalized_history_list:
                if not isinstance(req, dict):
                    continue

                # 1. Resolve status variations (String vs nested Enum objects)
                status_val = req.get("status", "PENDING")
                if isinstance(status_val, dict):
                    status_val = status_val.get("value", "PENDING")
                status_str = str(status_val).upper().replace("_", " ")

                # 2. Comprehensive District Identity Extraction Pipeline
                district_name = "Raipur"
                for key in ["district_details", "district", "district_info"]:
                    d_obj = req.get(key)
                    if isinstance(d_obj, dict) and d_obj.get("name"):
                        district_name = d_obj.get("name")
                        break
                else:
                    if req.get("district_name"):
                        district_name = req.get("district_name")
                    elif session.get("district_name"):
                        district_name = session.get("district_name")

                # 3. Compile clean data packet dictionary
                requests_history.append({
                    "request_code": str(req.get("request_code", "")).upper(),
                    "district_name": str(district_name),
                    "operator_count": int(req.get("operator_count", 0)),
                    "training_date": str(req.get("training_date", "")),
                    "status": status_str,
                    "created_at": str(req.get("timestamp") or req.get("created_at") or req.get("submitted_at") or "—")[:19],
                    "updated_at": str(req.get("updated_at") or "—")[:19],
                    "revert_reason": str(req.get("reject_reason") or req.get("revert_reason") or "None"),
                    "operators": [
                        dict(op, timeline_logs=req.get("timeline_logs", []))
                        for op in req.get("operators", [])
                    ] if isinstance(req.get("operators"), list) else [],
                    "timeline_logs": req.get("timeline_logs", [])
                })
        full_history = list(requests_history)

        all_time_metrics = {
            "pending": 0,
            "reapplied": 0,
            "sent_to_uidai": 0,
            "reverted": 0,
            "rejected": 0,
            "approved": 0,
        }
        for r in full_history:
            if not isinstance(r, dict):
                continue
            ops = r.get("operators")
            if ops and isinstance(ops, list) and len(ops) > 0:
                for op in ops:
                    st = str(op.get("status") or r.get("status") or "PENDING").upper().replace("_", " ").strip()
                    if "UIDAI" in st and "REJECT" not in st:
                        all_time_metrics["sent_to_uidai"] += 1
                    elif st in ["APPROVED", "REVIEWED", "ACTIVATED", "ACTIVE", "ASSIGNED"]:
                        all_time_metrics["approved"] += 1
                    elif st in ["REVERTED", "REVERT BACK", "REVERTED BY CHIPS"]:
                        all_time_metrics["reverted"] += 1
                    elif st in ["REJECTED", "UIDAI REJECTED", "REJECTED BY UIDAI"] or "REJECT" in st:
                        all_time_metrics["rejected"] += 1
                    elif st in ["REAPPLIED"]:
                        all_time_metrics["reapplied"] += 1
                    else:
                        all_time_metrics["pending"] += 1
            else:
                op_cnt = int(r.get("operator_count") or 1)
                st = str(r.get("status") or "PENDING").upper().replace("_", " ").strip()
                if "UIDAI" in st and "REJECT" not in st:
                    all_time_metrics["sent_to_uidai"] += op_cnt
                elif st in ["APPROVED", "REVIEWED", "ACTIVATED", "ACTIVE", "ASSIGNED"]:
                    all_time_metrics["approved"] += op_cnt
                elif st in ["REVERTED", "REVERT BACK", "REVERTED BY CHIPS"]:
                    all_time_metrics["reverted"] += op_cnt
                elif st in ["REJECTED", "UIDAI REJECTED", "REJECTED BY UIDAI"] or "REJECT" in st:
                    all_time_metrics["rejected"] += op_cnt
                elif st in ["REAPPLIED"]:
                    all_time_metrics["reapplied"] += op_cnt
                else:
                    all_time_metrics["pending"] += op_cnt

        total_requests = (
            all_time_metrics["pending"] +
            all_time_metrics["reapplied"] +
            all_time_metrics["sent_to_uidai"] +
            all_time_metrics["reverted"] +
            all_time_metrics["rejected"] +
            all_time_metrics["approved"]
        )

    except Exception as e:
        print(f"❌ CRITICAL BLUEPRINT DIAGNOSTIC LOOP ERROR: {str(e)}")
        requests_history = []
        full_history = []
        all_time_metrics = {"pending": 0, "reapplied": 0, "sent_to_uidai": 0, "reverted": 0, "rejected": 0, "approved": 0}
        total_requests = 0

    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_subset = []
        for r in requests_history:
            ops = r.get("operators", [])
            if ops:
                if any(str(op.get("status") or "").upper().replace("_", " ").strip() in ["PENDING", "REAPPLIED"] for op in ops):
                    pending_subset.append(r)
            else:
                if str(r.get("status") or "").upper().replace("_", " ").strip() in ["PENDING", "REAPPLIED"]:
                    pending_subset.append(r)
        requests_history = filter_by_aging(pending_subset, aging_filter, "created_at")

    # Extract flattened activated operators list
    activated_operators = []
    all_operators = []
    
    for req in requests_history:
        for op in req.get("operators", []):
            op_flat = op.copy()
            op_flat["request_code"] = req.get("request_code", "")
            op_flat["district_name"] = req.get("district_name", "")
            op_flat["training_date"] = req.get("training_date", "")
            op_flat["submitted_at"] = req.get("created_at", "")
            
            all_operators.append(op_flat)
            
            status_lower = str(op.get("status", "")).lower()
            if status_lower in ["active", "activated", "reviewed", "approved"]:
                activated_operators.append(op_flat)

    # 🌟 CONNECTED: Resolves correct structural template path targets
                
    with open("debug_all_operators.txt", "w") as f:
        f.write(str(all_operators))

    template_path = "chips/chips_reactivation.html" if "/chips" in request.path else "dc/dc_reactivation.html"
    return render_template(
        template_path,
        requests=requests_history,
        requests_history=full_history,
        full_history=full_history,
        activated_operators=activated_operators,
        all_operators=all_operators,
        metrics=all_time_metrics,
        total_requests=total_requests,
        aging_filter=aging_filter,
        aging_label=aging_label
    )


@reactivation_bp.route("/dc/reactivation/check-duplicate", methods=["GET"])
def check_duplicate():
    if not session.get("username"):
        return jsonify({"error": "Unauthorized session context"}), 401

    headers = {}
    if session.get("access_token"):
        headers["Authorization"] = f"Bearer {session.get('access_token')}"

    params = {
        "mobile": request.args.get("mobile"),
        "email": request.args.get("email"),
        "exclude_id": request.args.get("exclude_id")
    }

    try:
        response = requests.get(
            f"{FASTAPI_URL}/check-duplicate",
            params=params,
            headers=headers
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/dc/submit", methods=["POST"])
def submit_reactivation_form():
    if not session.get("username"):
        return jsonify({"success": False, "error": "Authentication required"}), 401

    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"

        # 🌟 FIXED: Safely load the JSON string from JavaScript back into an object format
        raw_operators = request.form.get("manual_operators")
        try:
            # If it's a string, ensure it's clean and unescaped for FastAPI
            operators_json = json.loads(raw_operators) if isinstance(raw_operators, str) else raw_operators
        except Exception:
            operators_json = raw_operators

        form_data = {
            "training_date": request.form.get("training_date"),
            "manual_operators": json.dumps(operators_json),  # Ensure clean serialization
        }
        
        if request.form.get("reapply_request_code"):
            form_data["reapply_request_code"] = request.form.get("reapply_request_code")
            
        if request.form.get("reapply_remarks"):
            form_data["dc_remark"] = request.form.get("reapply_remarks")

        # Capture file streams
        files_payload = {}
        file_keys = ["training_photo", "nodal_letter", "om_letter", "attendance_list"]
        for key in file_keys:
            if key in request.files:
                uploaded_file = request.files[key]
                if uploaded_file.filename:
                    files_payload[key] = (uploaded_file.filename, uploaded_file.read(), uploaded_file.content_type)

        backend_target = f"{FASTAPI_URL}/submit"
        response = requests.post(backend_target, headers=headers, data=form_data, files=files_payload, timeout=15)

        # Handle clean response checking
        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Batch verified successfully."})
        
        # 🌟 FIXED: Captures exact backend text trace if it fails to prevent throwing HTML pages to JS
        try:
            err_data = response.json()
            return jsonify({"success": False, "error": err_data.get("detail", "Backend rejection.")}), response.status_code
        except Exception:
            return jsonify({"success": False, "error": f"Backend Error (Status Code: {response.status_code})"}), response.status_code

    except Exception as submit_err:
        return jsonify({"success": False, "error": f"Internal proxy error: {str(submit_err)}"}), 500

@reactivation_bp.route("/dc/reactivation/operators/<request_code>", methods=["GET"])
def proxy_fetch_historical_operators(request_code):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized session context"}), 401

    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
            
        backend_route = f"{FASTAPI_URL}/operators/{request_code}"
        response = requests.get(backend_route, headers=headers, timeout=5)
        
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({"error": f"Backend returned status code {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"Proxy link failed: {str(e)}"}), 500


@reactivation_bp.route("/dc/reactivation/export/<request_code>", methods=["GET"])
def proxy_export_operators_excel(request_code):
    if not session.get("username"):
        return "Unauthorized profile session.", 401

    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"

        backend_url = f"{FASTAPI_URL}/export-excel/{request_code}"
        file_response = requests.get(backend_url, headers=headers, stream=True, timeout=10)

        if file_response.status_code == 200:
            return Response(
                file_response.iter_content(chunk_size=4096),
                content_type=file_response.headers.get("content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                headers={
                    "Content-Disposition": f"attachment; filename=Operators_List_{request_code}.xlsx",
                    "Cache-Control": "no-cache"
                }
            )
        return f"Excel export failed. Backend status: {file_response.status_code}", file_response.status_code
    except Exception as excel_err:
        return f"Excel compilation transport failure: {str(excel_err)}", 500


@reactivation_bp.route("/reactivation/export-csv-all", methods=["GET"])
def proxy_export_all_reactivation():
    if not session.get("username") or session.get("role") not in ["DC", "EDM", "Admin"]:
        return "Unauthorized", 401
        
    ids = request.args.get("ids", "")
    backend_target_url = f"{FASTAPI_URL}/export-csv-all"
    
    try:
        # Forward request to FastAPI backend and stream the chunked CSV data back
        response = requests.get(backend_target_url, params={"ids": ids}, headers={"Authorization": f"Bearer {session.get('access_token')}"}, stream=True)
        if response.status_code == 200:
            return Response(
                response.iter_content(chunk_size=4096),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", "attachment; filename=All_Pending_Reactivation_Operators.csv"),
                    "Cache-Control": "no-cache"
                }
            )
        else:
            return f"Backend Error: {response.status_code}", response.status_code
    except Exception as e:
        return f"Proxy Request Failed: {str(e)}", 500


@reactivation_bp.route("/reactivation/export-csv-uidai", methods=["GET"])
def proxy_export_uidai_reactivation():
    if not session.get("username") or session.get("role") not in ["DC", "EDM", "Admin"]:
        return "Unauthorized", 401
        
    ids = request.args.get("ids", "")
    backend_target_url = f"{FASTAPI_URL}/export-csv-uidai"
    
    try:
        # Forward request to FastAPI backend and stream the chunked CSV data back
        response = requests.get(backend_target_url, params={"ids": ids}, headers={"Authorization": f"Bearer {session.get('access_token')}"}, stream=True)
        if response.status_code == 200:
            return Response(
                response.iter_content(chunk_size=4096),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", "attachment; filename=UIDAI_Sent_Reactivation_Operators.csv"),
                    "Cache-Control": "no-cache"
                }
            )
        else:
            return f"Backend Error: {response.status_code}", response.status_code
    except Exception as e:
        return f"Proxy Request Failed: {str(e)}", 500


@reactivation_bp.route("/reactivation/requests/<request_code>/files/<file_type>", methods=["GET"])
def proxy_reactivation_file(request_code, file_type):
    if not session.get("username"):
        return "Unauthorized profile session.", 401

    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"

        backend_url = f"{FASTAPI_URL}/requests/{request_code}/files/{file_type}"
        response = requests.get(backend_url, headers=headers, stream=True, timeout=10)

        if response.status_code == 200:
            return Response(
                response.iter_content(chunk_size=8192),
                content_type=response.headers.get("content-type"),
                headers={
                    "Content-Disposition": response.headers.get("Content-Disposition", f"inline; filename={file_type}")
                }
            )
        return f"File not found or backend error (Status: {response.status_code})", response.status_code
    except Exception as e:
        return f"Proxy link failed: {str(e)}", 500


@reactivation_bp.route("/reactivation/operator/<int:operator_id>/activate", methods=["POST"])
def proxy_activate_operator(operator_id):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/operator/{operator_id}/activate"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/operator/<int:operator_id>/send-to-uidai", methods=["POST"])
def proxy_send_to_uidai_operator(operator_id):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/operator/{operator_id}/send-to-uidai"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/operator/<int:operator_id>/revert", methods=["POST"])
def proxy_revert_operator(operator_id):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/operator/{operator_id}/revert"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/operator/<int:operator_id>/reject", methods=["POST"])
def proxy_reject_operator(operator_id):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/operator/{operator_id}/reject"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/requests/<request_code>/finalize", methods=["POST"])
def proxy_finalize_batch(request_code):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/requests/{request_code}/finalize"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/requests/<request_code>/revert", methods=["POST"])
def proxy_revert_batch(request_code):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/requests/{request_code}/revert"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/requests/<request_code>/send-to-uidai", methods=["POST"])
def proxy_send_to_uidai_batch(request_code):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/requests/{request_code}/send-to-uidai"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/requests/<request_code>/approve-all", methods=["POST"])
def proxy_approve_all_batch(request_code):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/requests/{request_code}/approve-all"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reactivation_bp.route("/reactivation/requests/<request_code>/reject-all", methods=["POST"])
def proxy_reject_all_batch(request_code):
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        backend_target = f"{FASTAPI_URL}/requests/{request_code}/reject-all"
        response = requests.post(backend_target, headers=headers, data=request.form, timeout=10)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@reactivation_bp.route("/dc/operator-reactivation/search", methods=["GET"])
def search_suspended_operators():
    if not session.get("username"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        q = request.args.get("q", "")
        raw_token = session.get("access_token", "")
        if isinstance(raw_token, dict):
            raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
            
        headers = {}
        if raw_token:
            headers["Authorization"] = f"Bearer {str(raw_token).strip()}"
        
        backend_url = f"{FASTAPI_URL}/search-suspended-operators"
        response = requests.get(f"{backend_url}?q={q}", headers=headers, timeout=5)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"status": "error", "message": "Search failed"}), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
