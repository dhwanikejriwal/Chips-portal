# app/blueprints/l1_registration.py
from flask import Blueprint, render_template, session, redirect, url_for, request, Response
import requests
from app.utils.aging import parse_aging_filter, filter_by_aging

l1_bp = Blueprint("l1_registration", __name__)

# Statuses that are NOT part of the pending queue for aging purposes
_L1_NON_PENDING = {"reviewed", "approved", "reverted", "done"}

@l1_bp.route("/dc/l1-registration")
def dc_l1_portal():
    # 🌟 FIXED: Standardized token extractor matching your working station_id pattern
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
    
    if not raw_token or session.get("role") == "Admin":
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {str(raw_token).strip()}"}

    try:
        response = requests.get(
            "http://127.0.0.1:8000/l1-registration/requests",
            headers=headers,
            timeout=5
        )
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        if response.status_code != 200:
            print(f"DEBUG L1 API FAIL: {response.status_code} - {response.text}")
        raw_data = response.json() if response.status_code == 200 else []
        
        # 🌟 FIXED: Envelope-Aware normalization to handle both raw lists and wrapper dicts
        if isinstance(raw_data, dict):
            requests_data = raw_data.get("requests") or raw_data.get("data") or []
        else:
            requests_data = raw_data if isinstance(raw_data, list) else []
    except Exception:
        requests_data = []

    requests_data.sort(key=lambda x: x.get("updated_at") or x.get("reviewed_at") or x.get("created_at") or "", reverse=True)

    # Allotted Station IDs still awaiting an L1 request from the DC
    try:
        allotted_resp = requests.get(
            "http://127.0.0.1:8000/l1-registration/allotted-pending",
            headers=headers,
            timeout=5,
        )
        allotted_stations = allotted_resp.json() if allotted_resp.status_code == 200 else []
        if not isinstance(allotted_stations, list):
            allotted_stations = []
    except Exception:
        allotted_stations = []

    pending_cnt = 0
    reapplied_cnt = 0
    reverted_cnt = 0
    approved_cnt = 0
    total_cnt = len(requests_data)

    for r in requests_data:
        st = str(r.get("status") or "").lower().strip()
        if st in ["approved", "reviewed", "l1_done", "done"]:
            approved_cnt += 1
        elif st in ["reverted", "reverted_by_chips"]:
            reverted_cnt += 1
        elif st in ["reapplied"]:
            reapplied_cnt += 1
        else:
            pending_cnt += 1

    return render_template(
        "l1_registration/dc_l1.html",
        requests=requests_data,
        allotted_stations=allotted_stations,
        pending_count=pending_cnt,
        reapplied_count=reapplied_cnt,
        reverted_count=reverted_cnt,
        approved_count=approved_cnt,
        total_requests=total_cnt,
    )


@l1_bp.route("/chips/l1-registration")
def chips_l1_portal():
    # 🌟 FIXED: Standardized token extractor matching your working station_id pattern
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        raw_token = raw_token.get("token", "") or raw_token.get("access_token", "")
        
    if not raw_token or session.get("role") != "Admin":
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {str(raw_token).strip()}"}

    try:
        response = requests.get(
            "http://127.0.0.1:8000/l1-registration/requests",
            headers=headers,
            timeout=5
        )
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        raw_data = response.json() if response.status_code == 200 else []
        
        # 🌟 FIXED: Envelope-Aware normalization to handle both raw lists and wrapper dicts
        if isinstance(raw_data, dict):
            requests_data = raw_data.get("requests") or raw_data.get("data") or []
        else:
            requests_data = raw_data if isinstance(raw_data, list) else []
    except Exception:
        requests_data = []

    all_reqs = list(requests_data)
    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_subset = [
            r for r in requests_data
            if str(r.get("status", "")).strip().lower() not in _L1_NON_PENDING
        ]
        requests_data = filter_by_aging(pending_subset, aging_filter, "submitted_at")

    return render_template(
        "l1_registration/chips_l1.html",
        requests=requests_data,
        unfiltered_requests=all_reqs,
        aging_filter=aging_filter,
        aging_label=aging_label,
    )

FASTAPI_URL = "http://127.0.0.1:8000/l1-registration"

def get_valid_token():
    raw_token = session.get("access_token", "")
    if isinstance(raw_token, dict):
        return raw_token.get("token", "") or raw_token.get("access_token", "")
    return str(raw_token).strip()

@l1_bp.route("/l1-registration/submit", methods=["POST"])
def submit_l1():
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.post(f"{FASTAPI_URL}/submit", headers=headers, data=request.form)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>", methods=["GET"])
def get_l1_request(request_code):
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(f"{FASTAPI_URL}/requests/{request_code}", headers=headers)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>/perform", methods=["POST"])
def perform_l1(request_code):
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    # 🌟 FIXED: Read chips_remarks from the SweetAlert modal form map data
    form_data = {
        "chips_remarks": request.form.get("chips_remarks", "")
    }
    
    # 🌟 FIXED: Pass form_data explicitly inside the data payload parameter stream
    resp = requests.post(f"{FASTAPI_URL}/requests/{request_code}/perform", headers=headers, data=form_data)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/approve-all", methods=["POST"])
def approve_all_l1():
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.post(f"{FASTAPI_URL}/requests/approve-all", headers=headers)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>/revert", methods=["POST"])
def revert_l1(request_code):
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.post(f"{FASTAPI_URL}/requests/{request_code}/revert", headers=headers, data=request.form)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>/reapply", methods=["PUT"])
def reapply_l1(request_code):
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.put(f"{FASTAPI_URL}/requests/{request_code}/reapply", headers=headers, data=request.form)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}


@l1_bp.route("/l1-registration/export/<request_code>", methods=["GET"])
def proxy_export_l1_excel(request_code):
    if not session.get("username"):
        return "Unauthorized", 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        file_response = requests.get(f"{FASTAPI_URL}/export-excel/{request_code}", headers=headers, stream=True, timeout=10)
        if file_response.status_code == 200:
            return Response(
                file_response.iter_content(chunk_size=4096),
                content_type=file_response.headers.get("content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                headers={
                    "Content-Disposition": f"attachment; filename=L1_Request_{request_code}.xlsx",
                    "Cache-Control": "no-cache"
                }
            )
        return f"Excel export failed. Backend status: {file_response.status_code}", file_response.status_code
    except Exception as excel_err:
        return f"Excel compilation failure: {str(excel_err)}", 500


@l1_bp.route("/l1-registration/export", methods=["GET"])
def proxy_export_l1_csv_v2():
    if not session.get("access_token"):
        return "Unauthorized", 401
    ids = request.args.get("ids", "")
    FASTAPI_L1_URL = "http://127.0.0.1:8000/l1-registration"
    try:
        file_response = requests.get(f"{FASTAPI_L1_URL}/export-excel-v2", params={"ids": ids}, stream=True, timeout=20)
        if file_response.status_code == 200:
            return Response(
                file_response.iter_content(chunk_size=4096),
                content_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=l1_registration_requests.csv",
                    "Cache-Control": "no-cache"
                }
            )
        return f"CSV export failed. Backend status: {file_response.status_code}", file_response.status_code
    except Exception as excel_err:
        return f"CSV compilation failure: {str(excel_err)}", 500
