from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    Response,
    current_app,
)
import requests

operator_activation_bp = Blueprint("operator_activation", __name__)


def backend_url():
    api_url = current_app.config.get("BACKEND_API_URL", "http://127.0.0.1:8000/api")
    return api_url.removesuffix("/api") + "/operator-activation"


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────


@operator_activation_bp.route("/dc/operator-activation", methods=["GET"])
def dc_submit_form():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))
    return render_template(
        "operator_activation/submit_form.html",
        district_name=session.get("district_name", ""),
    )


@operator_activation_bp.route("/dc/operator-activation", methods=["POST"])
def dc_submit():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {jwt_token}"}

    # Collect text fields
    form_data = {
        "dc_id": session.get("user_id"),
        "district_id": session.get("district_id"),
        "role": request.form.get("role"),
        "name_as_per_aadhaar": request.form.get("name_as_per_aadhaar"),
        "registrar_code": request.form.get("registrar_code"),
        "ea_code": request.form.get("ea_code"),
        "user_code": request.form.get("user_code"),
        "nseit_certificate_number": request.form.get("nseit_certificate_number"),
        "nseit_certification_date": request.form.get("nseit_certification_date"),
        "nseit_certificate_expiry_date": request.form.get("nseit_certificate_expiry_date"),
        "operator_mobile": request.form.get("operator_mobile"),
        "primary_email": request.form.get("primary_email"),
        "operator_aadhaar": request.form.get("operator_aadhaar"),
        "operator_pan": request.form.get("operator_pan"),
        "pincode": request.form.get("pincode"),
    }

    # Collect 6 uploaded files
    files = {
        "hard_copy_form": (
            request.files["hard_copy_form"].filename,
            request.files["hard_copy_form"].read(),
            request.files["hard_copy_form"].content_type,
        ),
        "aadhaar_photo": (
            request.files["aadhaar_photo"].filename,
            request.files["aadhaar_photo"].read(),
            request.files["aadhaar_photo"].content_type,
        ),
        "pan_card": (
            request.files["pan_card"].filename,
            request.files["pan_card"].read(),
            request.files["pan_card"].content_type,
        ),
        "passbook": (
            request.files["passbook"].filename,
            request.files["passbook"].read(),
            request.files["passbook"].content_type,
        ),
        "nseit_certificate": (
            request.files["nseit_certificate"].filename,
            request.files["nseit_certificate"].read(),
            request.files["nseit_certificate"].content_type,
        ),
        "excel_sheet": (
            request.files["excel_sheet"].filename,
            request.files["excel_sheet"].read(),
            request.files["excel_sheet"].content_type,
        ),
    }

    try:
        response = requests.post(
            f"{backend_url()}/submit", data=form_data, files=files, headers=headers
        )
        if response.status_code == 200:
            return jsonify({"status": "success", "redirect_url": url_for("operator_activation.dc_requests_list")}), 200
        else:
            error = response.json().get("detail", "Submission failed.")
            return jsonify({"status": "error", "message": error}), 400

    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend offline."}), 500


@operator_activation_bp.route("/dc/operator-activation/list", methods=["GET"])
def dc_requests_list():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {jwt_token}"}
    dc_id = session.get("user_id")

    try:
        response = requests.get(f"{backend_url()}/dc/{dc_id}", headers=headers)
        requests_list = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        requests_list = []

    return render_template("operator_activation/dc_list.html", requests=requests_list)


@operator_activation_bp.route(
    "/dc/operator-activation/<int:request_id>/detail", methods=["GET"]
)
def dc_detail(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))
    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = requests.get(f"{backend_url()}/{request_id}", headers=headers)
    detail = response.json() if response.status_code == 200 else {}
    return render_template("operator_activation/reapply.html", r=detail)


@operator_activation_bp.route(
    "/dc/operator-activation/<int:request_id>/reapply", methods=["POST"]
)
def dc_reapply(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "dc_id": session.get("user_id"),
        "operator_name": request.form.get("operator_name"),
        "operator_mobile": request.form.get("operator_mobile"),
        "operator_aadhaar": request.form.get("operator_aadhaar", ""),
        "operator_pan": request.form.get("operator_pan", ""),
        "reapply_remark": request.form.get("reapply_remark"),
    }

    requests.post(
        f"{backend_url()}/dc/{request_id}/reapply",
        data=form_data,
        headers=headers,
    )
    return redirect(url_for("operator_activation.dc_requests_list"))


# @operator_activation_bp.route(
#     "/dc/operator-activation/<int:request_id>/reapply-json", methods=["POST"]
# )
# def dc_reapply_json(request_id):
#     jwt_token = session.get("access_token")
#     if not jwt_token:
#         return jsonify({"detail": "Unauthorized"}), 401

#     headers = {"Authorization": f"Bearer {jwt_token}"}
#     form_data = {
#         "dc_id": session.get("user_id"),
#         "operator_name": request.form.get("operator_name"),
#         "operator_mobile": request.form.get("operator_mobile"),
#         "operator_aadhaar": request.form.get("operator_aadhaar", ""),
#         "operator_pan": request.form.get("operator_pan", ""),
#         "reapply_remark": request.form.get("reapply_remark"),
#     }

#     response = requests.post(
#         f"{backend_url()}/dc/{request_id}/reapply",
#         data=form_data,
#         headers=headers,
#     )
#     return Response(
#         response.content,
#         status=response.status_code,
#         content_type=response.headers.get("Content-Type", "application/json"),
#     )

# ───────────────────────────────────────────────────────────────────
# 🌟 ADDED MISSING ASYNCHRONOUS JSON REAPPLY BRIDGE HANDLER
# ───────────────────────────────────────────────────────────────────

@operator_activation_bp.route("/dc/operator-activation/<int:id>/reapply-json", methods=["POST"])
def dc_reapply_json_handler(id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Session expired. Please log in again."}), 401
        
    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    # 🌟 FIXED: Form values correctly match the properties submitted by your SweetAlert form fields
    form_data = {
        "dc_id": int(session.get("user_id", 1)),
        "operator_mobile": request.form.get("operator_mobile", "").strip(),
        "operator_aadhaar": request.form.get("operator_aadhaar", "").strip()[-4:], # Grabs last 4 digits safely
        "operator_pan": request.form.get("operator_pan", "").strip().upper(),
        "reapply_remark": request.form.get("reapply_remark", "").strip(),
    }
    
    try:
        backend_api_url = backend_url()
        response = requests.post(f"{backend_api_url}/dc/{id}/reapply", data=form_data, headers=headers)
        
        if response.status_code in [200, 201]:
            return jsonify({"status": "success", "message": "Request reapplied successfully."})
        else:
            try:
                error_detail = response.json().get("detail", "Error processing updates.")
            except Exception:
                error_detail = response.text or "Backend validation error."
            return jsonify({"status": "error", "message": str(error_detail)}), 400
            
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend microservice core offline."}), 500
# ─────────────────────────────────────────────
# CHIPS ADMIN ROUTES
# ─────────────────────────────────────────────


@operator_activation_bp.route("/chips/operator-activation", methods=["GET"])
def chips_all_requests():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {jwt_token}"}

    try:
        response = requests.get(f"{backend_url()}/all", headers=headers)
        requests_list = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        requests_list = []

    return render_template(
        "operator_activation/chips_list.html", requests=requests_list
    )


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/approve", methods=["POST"]
)
def chips_approve(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "chips_remarks": request.form.get("chips_remarks", ""),
    }

    requests.patch(f"{backend_url()}/{request_id}/approve", data=form_data, headers=headers)
    return redirect(url_for("operator_activation.chips_all_requests"))


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/reject", methods=["POST"]
)
def chips_reject(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))

    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "rejection_reason": request.form.get("rejection_reason"),
        "chips_remarks": request.form.get("chips_remarks", ""),
    }

    requests.patch(f"{backend_url()}/{request_id}/reject", data=form_data, headers=headers)
    return redirect(url_for("operator_activation.chips_all_requests"))


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/detail", methods=["GET"]
)
def chips_detail(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))
    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = requests.get(f"{backend_url()}/{request_id}/detail", headers=headers)
    detail = response.json() if response.status_code == 200 else {}
    return render_template("operator_activation/detail.html", r=detail)


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/detail-json", methods=["GET"]
)
def chips_detail_json(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = requests.get(f"{backend_url()}/{request_id}", headers=headers)
    return Response(
        response.content,
        status=response.status_code,
        content_type=response.headers.get("Content-Type", "application/json"),
    )


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/view", methods=["GET"]
)
def chips_view_request(request_id):
    """Full operator profile + documents viewer page."""
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))
    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = requests.get(f"{backend_url()}/{request_id}", headers=headers)
    detail = response.json() if response.status_code == 200 else {}
    return render_template(
        "operator_activation/operator_detail_view.html",
        r=detail,
        request_id=request_id,
    )


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/file/<string:doc_type>", methods=["GET"]
)
def chips_serve_file(request_id, doc_type):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("auth.login"))
    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = requests.get(f"{backend_url()}/{request_id}/file/{doc_type}", headers=headers, stream=True)
    if response.status_code == 200:
        return Response(
            response.content,
            status=200,
            headers={
                "Content-Type": response.headers.get("Content-Type", "application/octet-stream"),
                "Content-Disposition": response.headers.get("Content-Disposition", f"inline; filename={doc_type}"),
            }
        )
    return "File not found", 404


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/send-to-uidai", methods=["POST"]
)
def chips_send_to_uidai(request_id):
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", ""),
    }
    requests.patch(
        f"{backend_url()}/{request_id}/send-to-uidai", data=form_data, headers=headers
    )
    return redirect(url_for("operator_activation.chips_all_requests"))


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/uidai-approve", methods=["POST"]
)
def chips_uidai_approve(request_id):
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", ""),
    }
    requests.patch(
        f"{backend_url()}/{request_id}/uidai-approve", data=form_data, headers=headers
    )
    return redirect(url_for("operator_activation.chips_all_requests"))


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/uidai-reject", methods=["POST"]
)
def chips_uidai_reject(request_id):
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks"),
    }
    requests.patch(
        f"{backend_url()}/{request_id}/uidai-reject", data=form_data, headers=headers
    )
    return redirect(url_for("operator_activation.chips_all_requests"))


@operator_activation_bp.route(
    "/chips/operator-activation/export-excel", methods=["GET"]
)
def chips_export_excel():
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    response = requests.get(f"{backend_url()}/export-excel", headers=headers)
    from flask import Response

    return Response(
        response.content,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=sent_to_uidai.xlsx"
        },
    )


@operator_activation_bp.route(
    "/chips/operator-activation/export-excel/pending", methods=["GET"]
)
def chips_export_pending():
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{backend_url()}/export-excel/pending", headers=headers, params=params)
    from flask import Response

    return Response(
        response.content,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=pending_activation_queue.xlsx"
        },
    )


@operator_activation_bp.route(
    "/chips/operator-activation/export-excel/credentials", methods=["GET"]
)
def chips_export_credentials():
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{backend_url()}/export-excel/credentials", headers=headers, params=params)
    from flask import Response

    return Response(
        response.content,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=credentials_log_history.xlsx"
        },
    )
