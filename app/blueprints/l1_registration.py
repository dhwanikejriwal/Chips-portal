# app/blueprints/l1_registration.py
from flask import Blueprint, render_template, session, redirect, url_for, request
import requests

l1_bp = Blueprint("l1_registration", __name__)

@l1_bp.route("/dc/l1-registration")
def dc_l1_portal():
    access_token = session.get("access_token")
    if not access_token or session.get("role") == "Admin":
        return redirect(url_for("auth.login"))

    try:
        response = requests.get(
            "http://127.0.0.1:8000/l1-registration/requests",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        requests_data = response.json() if response.status_code == 200 else []
    except Exception:
        requests_data = []

    return render_template("dc/dc_l1_registration.html", requests=requests_data)

@l1_bp.route("/chips/l1-registration")
def chips_l1_portal():
    access_token = session.get("access_token")
    if not access_token or session.get("role") != "Admin":
        return redirect(url_for("auth.login"))

    try:
        response = requests.get(
            "http://127.0.0.1:8000/l1-registration/requests",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        requests_data = response.json() if response.status_code == 200 else []
    except Exception:
        requests_data = []

    return render_template("chips/chips_l1_registration.html", requests=requests_data)

FASTAPI_URL = "http://127.0.0.1:8000/l1-registration"

@l1_bp.route("/l1-registration/submit", methods=["POST"])
def submit_l1():
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    resp = requests.post(f"{FASTAPI_URL}/submit", headers=headers, data=request.form)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>", methods=["GET"])
def get_l1_request(request_code):
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    resp = requests.get(f"{FASTAPI_URL}/requests/{request_code}", headers=headers)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>/perform", methods=["POST"])
def perform_l1(request_code):
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    resp = requests.post(f"{FASTAPI_URL}/requests/{request_code}/perform", headers=headers)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/approve-all", methods=["POST"])
def approve_all_l1():
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    resp = requests.post(f"{FASTAPI_URL}/requests/approve-all", headers=headers)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>/revert", methods=["POST"])
def revert_l1(request_code):
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    resp = requests.post(f"{FASTAPI_URL}/requests/{request_code}/revert", headers=headers, data=request.form)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

@l1_bp.route("/l1-registration/requests/<request_code>/reapply", methods=["PUT"])
def reapply_l1(request_code):
    headers = {"Authorization": f"Bearer {session.get('access_token')}"} if session.get('access_token') else {}
    resp = requests.put(f"{FASTAPI_URL}/requests/{request_code}/reapply", headers=headers, data=request.form)
    return resp.content, resp.status_code, {'Content-Type': 'application/json'}

from flask import Response

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

@l1_bp.route("/l1-registration/export-all", methods=["GET"])
def proxy_export_l1_excel_all():
    if not session.get("username"):
        return "Unauthorized", 401
    try:
        headers = {}
        if session.get("access_token"):
            headers["Authorization"] = f"Bearer {session.get('access_token')}"
        file_response = requests.get(f"{FASTAPI_URL}/export-excel-all", headers=headers, stream=True, timeout=20)
        if file_response.status_code == 200:
            return Response(
                file_response.iter_content(chunk_size=4096),
                content_type=file_response.headers.get("content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                headers={
                    "Content-Disposition": "attachment; filename=Pending_L1_Requests.xlsx",
                    "Cache-Control": "no-cache"
                }
            )
        return f"Excel export failed. Backend status: {file_response.status_code}", file_response.status_code
    except Exception as excel_err:
        return f"Excel compilation failure: {str(excel_err)}", 500


@l1_bp.route("/l1-registration/export-v2", methods=["GET"])
def proxy_export_l1_excel_v2():
    if not session.get("access_token"):
        return "Unauthorized", 401
    ids = request.args.get("ids", "")
    FASTAPI_L1_URL = "http://127.0.0.1:8000/l1-registration"
    from flask import Response
    try:
        file_response = requests.get(f"{FASTAPI_L1_URL}/export-excel-v2", params={"ids": ids}, stream=True, timeout=20)
        if file_response.status_code == 200:
            return Response(
                file_response.iter_content(chunk_size=4096),
                content_type=file_response.headers.get("content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                headers={
                    "Content-Disposition": file_response.headers.get("Content-Disposition", "attachment; filename=l1_registration_requests.xlsx"),
                    "Cache-Control": "no-cache"
                }
            )
        return f"Excel export failed. Backend status: {file_response.status_code}", file_response.status_code
    except Exception as excel_err:
        return f"Excel compilation failure: {str(excel_err)}", 500
