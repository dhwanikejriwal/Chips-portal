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
from app.utils.aging import parse_aging_filter, filter_by_aging

operator_activation_bp = Blueprint("operator_activation", __name__)

# Statuses that are NOT part of the "pending" queue for aging purposes
_ACTIVATION_NON_PENDING_STATUSES = {
    "approved", "reviewed", "activated",
    "sent_to_uidai", "sent to uidai",
    "reverted", "reverted_by_chips",
    "rejected",
}

def backend_url():
    api_url = current_app.config.get("BACKEND_API_URL", "http://127.0.0.1:8000/api")
    return api_url.removesuffix("/api") + "/operator-activation"


# ─────────────────────────────────────────────
# DC ROUTES
# ─────────────────────────────────────────────


@operator_activation_bp.route("/dc/operator-activation/search", methods=["GET"])
def search_eligible_candidates():
    jwt_token = session.get("access_token")
    if isinstance(jwt_token, dict):
        jwt_token = jwt_token.get("token", "") or jwt_token.get("access_token", "")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    headers = {"Authorization": f"Bearer {str(jwt_token).strip()}"}
    query = request.args.get("q", "")

    try:
        response = requests.get(
            f"{backend_url()}/search-eligible-candidates",
            params={"q": query},
            headers=headers
        )
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({"status": "error", "message": "Search failed"}), response.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend offline"}), 500


@operator_activation_bp.route("/dc/operator-activation/autofill-nseit", methods=["POST"])
def autofill_from_certificate():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    file_obj = request.files.get("nseit_certificate")
    if not file_obj or not file_obj.filename:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    files = {"nseit_certificate": (file_obj.filename, file_obj.read(), file_obj.content_type)}
    data = {}
    operator_name = request.form.get("operator_name")
    if operator_name:
        data["operator_name"] = operator_name

    try:
        response = requests.post(
            f"{backend_url()}/autofill-from-certificate",
            files=files,
            data=data,
            headers=headers
        )
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            try:
                err_detail = response.json().get("message") or response.json().get("detail") or "Autofill failed"
            except Exception:
                err_detail = response.text or "Autofill failed"
            return jsonify({"status": "error", "message": err_detail}), response.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend offline"}), 500


@operator_activation_bp.route("/dc/operator-activation/check-duplicate", methods=["GET"])
def check_duplicate():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    headers = {"Authorization": f"Bearer {jwt_token}"}
    params = {
        "mobile": request.args.get("mobile"),
        "email": request.args.get("email"),
        "exclude_id": request.args.get("exclude_id")
    }

    try:
        response = requests.get(
            f"{backend_url()}/check-duplicate",
            params=params,
            headers=headers
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@operator_activation_bp.route("/dc/operator-activation/validate-document", methods=["POST"])
def validate_single_document():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    file_obj = request.files.get("file")
    if not file_obj or not file_obj.filename:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    files = {"file": (file_obj.filename, file_obj.read(), file_obj.content_type)}
    
    data = {
        "doc_type": request.form.get("doc_type"),
        "name_as_per_aadhaar": request.form.get("name_as_per_aadhaar", ""),
        "operator_aadhaar": request.form.get("operator_aadhaar", ""),
        "operator_pan": request.form.get("operator_pan", ""),
        "operator_mobile": request.form.get("operator_mobile", ""),
        "nseit_certificate_number": request.form.get("nseit_certificate_number", ""),
    }

    try:
        response = requests.post(
            f"{backend_url()}/validate-document",
            files=files,
            data=data,
            headers=headers
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@operator_activation_bp.route("/dc/operator-activation/validate_ocr", methods=["POST"])
def validate_ocr_proxy():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    headers = {"Authorization": f"Bearer {jwt_token}"}
    file_obj = request.files.get("file")
    if not file_obj or not file_obj.filename:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    files = {"file": (file_obj.filename, file_obj.read(), file_obj.content_type)}
    data = {
        "doc_type": request.form.get("doc_type"),
        "name_as_per_aadhaar": request.form.get("name_as_per_aadhaar", ""),
        "operator_aadhaar": request.form.get("operator_aadhaar", ""),
        "operator_pan": request.form.get("operator_pan", ""),
        "nseit_id": request.form.get("nseit_id", "") or request.form.get("nseit_certificate_number", ""),
    }

    try:
        response = requests.post(
            f"{backend_url()}/validate_ocr",
            files=files,
            data=data,
            headers=headers
        )
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@operator_activation_bp.route("/dc/operator-activation", methods=["GET"])
def dc_submit_form():
    return redirect(url_for("operator_activation.dc_requests_list"))


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
    
    reapply_id = request.form.get("reapply_id")
    if reapply_id:
        form_data["reapply_remark"] = request.form.get("reapply_remark")

    # Collect 6 uploaded files safely
    files = {}
    for field in ["hard_copy_form", "aadhaar_photo", "pan_card", "passbook", "nseit_certificate", "excel_sheet"]:
        file_obj = request.files.get(field)
        if file_obj and file_obj.filename:
            files[field] = (file_obj.filename, file_obj.read(), file_obj.content_type)

    try:
        url = f"{backend_url()}/submit"
        if reapply_id:
            url = f"{backend_url()}/dc/{reapply_id}/reapply"
            
        response = requests.post(
            url, data=form_data, files=files if files else None, headers=headers
        )
        if response.status_code == 200:
            return jsonify({"status": "success", "redirect_url": url_for("operator_activation.dc_requests_list")}), 200
        else:
            try:
                detail = response.json().get("detail", "Submission failed.")
            except Exception:
                detail = f"Server Error: {response.status_code} - {response.text[:200]}"
            if isinstance(detail, dict) and "field_errors" in detail:
                return jsonify({"status": "error", "field_errors": detail["field_errors"]}), 400
            else:
                return jsonify({"status": "error", "message": detail}), 400

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
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        requests_list = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        requests_list = []

    error = request.args.get("error")
    reapply_id = request.args.get("reapply_id")
    request_data = None
    
    if reapply_id:
        try:
            detail_res = requests.get(f"{backend_url()}/{reapply_id}/detail", headers=headers)
            if detail_res.status_code == 200:
                request_data = detail_res.json()
        except requests.exceptions.ConnectionError:
            pass

    return render_template(
        "operator_activation/dc_list.html", 
        requests=requests_list, 
        error=error,
        reapply_id=reapply_id,
        request_data=request_data
    )


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
        "primary_email": request.form.get("primary_email", "").strip(),
        "pincode": request.form.get("pincode", "").strip(),
        "role": request.form.get("role", "").strip(),
        "registrar_code": request.form.get("registrar_code", "").strip(),
        "ea_code": request.form.get("ea_code", "").strip(),
        "user_code": request.form.get("user_code", "").strip(),
        "nseit_certificate_number": request.form.get("nseit_certificate_number", "").strip(),
        "nseit_certification_date": request.form.get("nseit_certification_date", "").strip(),
        "nseit_certificate_expiry_date": request.form.get("nseit_certificate_expiry_date", "").strip(),
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
        if response.status_code == 401:
            return redirect(url_for("auth.logout"))
        requests_list = response.json() if response.status_code == 200 else []
    except requests.exceptions.ConnectionError:
        requests_list = []

    all_reqs = list(requests_list)
    aging_filter, aging_label = parse_aging_filter(request.args)
    if aging_filter:
        pending_subset = [
            r for r in requests_list
            if str(r.get("status", "")).strip().lower() not in _ACTIVATION_NON_PENDING_STATUSES
        ]
        requests_list = filter_by_aging(pending_subset, aging_filter, "submitted_at")

    return render_template(
        "operator_activation/chips_list.html",
        requests=requests_list,
        unfiltered_requests=all_reqs,
        aging_filter=aging_filter,
        aging_label=aging_label,
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
        return jsonify({"status": "error", "message": "Session expired."}), 401

    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "rejection_reason": request.form.get("rejection_reason"),
        "chips_remarks": request.form.get("chips_remarks", ""),
    }

    try:
        resp = requests.patch(f"{backend_url()}/{request_id}/reject", data=form_data, headers=headers)
        if resp.status_code in (200, 201):
            return jsonify({"status": "success", "message": "Request rejected successfully."})
        else:
            try:
                detail = resp.json().get("detail", "Backend validation error.")
            except Exception:
                detail = resp.text or "Unknown backend error."
            return jsonify({"status": "error", "message": str(detail)}), resp.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend service is offline."}), 503


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
    if not jwt_token:
        return jsonify({"status": "error", "message": "Session expired."}), 401

    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", ""),
    }

    try:
        resp = requests.patch(
            f"{backend_url()}/{request_id}/send-to-uidai",
            data=form_data,
            headers=headers,
        )
        if resp.status_code in (200, 201):
            return jsonify({"status": "success", "message": "Sent to UIDAI successfully."})
        else:
            try:
                detail = resp.json().get("detail", "Backend validation error.")
            except Exception:
                detail = resp.text or "Unknown backend error."
            return jsonify({"status": "error", "message": str(detail)}), resp.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend service is offline."}), 503


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/uidai-approve", methods=["POST"]
)
def chips_uidai_approve(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Session expired."}), 401
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks", ""),
    }
    try:
        resp = requests.patch(
            f"{backend_url()}/{request_id}/uidai-approve", data=form_data, headers=headers
        )
        if resp.status_code in (200, 201):
            return jsonify({"status": "success", "message": "UIDAI approval recorded."})
        else:
            try:
                detail = resp.json().get("detail", "Backend validation error.")
            except Exception:
                detail = resp.text or "Unknown backend error."
            return jsonify({"status": "error", "message": str(detail)}), resp.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend service is offline."}), 503


@operator_activation_bp.route(
    "/chips/operator-activation/<int:request_id>/uidai-reject", methods=["POST"]
)
def chips_uidai_reject(request_id):
    jwt_token = session.get("access_token")
    if not jwt_token:
        return jsonify({"status": "error", "message": "Session expired."}), 401
    headers = {"Authorization": f"Bearer {jwt_token}"}
    form_data = {
        "reviewed_by": session.get("user_id"),
        "uidai_remarks": request.form.get("uidai_remarks"),
    }
    try:
        resp = requests.patch(
            f"{backend_url()}/{request_id}/uidai-reject", data=form_data, headers=headers
        )
        if resp.status_code in (200, 201):
            return jsonify({"status": "success", "message": "UIDAI rejection recorded."})
        else:
            try:
                detail = resp.json().get("detail", "Backend validation error.")
            except Exception:
                detail = resp.text or "Unknown backend error."
            return jsonify({"status": "error", "message": str(detail)}), resp.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "message": "Backend service is offline."}), 503


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
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sent_to_uidai.csv"
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
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=pending_activation_queue.csv"
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
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=credentials_log_history.csv"
        },
    )


@operator_activation_bp.route("/dc/operator-activation/export-excel/pending", methods=["GET"])
def dc_export_pending():
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{backend_url()}/export-excel/pending", headers=headers, params=params)
    from flask import Response
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pending_activation_queue.csv"}
    )

@operator_activation_bp.route("/dc/operator-activation/export-excel/credentials", methods=["GET"])
def dc_export_credentials():
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{backend_url()}/export-excel/credentials", headers=headers, params=params)
    from flask import Response
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=credentials_log_history.csv"}
    )

@operator_activation_bp.route("/dc/operator-activation/export-excel/uidai", methods=["GET"])
def dc_export_uidai():
    jwt_token = session.get("access_token")
    headers = {"Authorization": f"Bearer {jwt_token}"}
    ids = request.args.get("ids", "")
    params = {"ids": ids} if ids else {}
    response = requests.get(f"{backend_url()}/export-excel/pending", headers=headers, params=params)
    from flask import Response
    return Response(
        response.content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=sent_to_uidai_activation_queue.csv"}
    )
