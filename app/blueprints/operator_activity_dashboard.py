# app/blueprints/operator_activity_dashboard.py
"""Flask blueprint for the Operator Activity dashboard section.

Renders the page and proxies browser XHR calls to the FastAPI backend,
injecting the session bearer token (the token lives in the Flask session and
is never exposed to client JS).
"""
from flask import (
    Blueprint, render_template, session, redirect, url_for, jsonify, request, Response,
)
import requests as http

operator_activity_dashboard_bp = Blueprint("operator_activity_dashboard", __name__)
BACKEND = "http://127.0.0.1:8000/operator-activity"


def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}


def _authed() -> bool:
    return bool(session.get("access_token"))


def _fwd_params():
    """Forward query params preserving repeated keys (e.g. districts=A&districts=B).

    `request.args` is a MultiDict; passing it straight to requests collapses
    repeated keys to a single value. A list of (key, value) tuples keeps them.
    """
    return list(request.args.items(multi=True))


@operator_activity_dashboard_bp.route("/chips/operator-activity", methods=["GET"])
@operator_activity_dashboard_bp.route("/dc/operator-activity", methods=["GET"])
def page():
    if not _authed():
        return redirect(url_for("auth.login"))
    return render_template("operator_activity/index.html")


# ── Activity list (router root) ──
@operator_activity_dashboard_bp.route(
    "/chips/operator-activity/api-list", methods=["GET"])
@operator_activity_dashboard_bp.route(
    "/dc/operator-activity/api-list", methods=["GET"])
def api_list():
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    try:
        resp = http.get(f"{BACKEND}/", headers=_headers(),
                        params=_fwd_params(), timeout=30)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502


# ── Generic GET proxy (filters, uploads, status, operators, kit-tracker) ──
@operator_activity_dashboard_bp.route(
    "/chips/operator-activity/api/<path:subpath>", methods=["GET"])
@operator_activity_dashboard_bp.route(
    "/dc/operator-activity/api/<path:subpath>", methods=["GET"])
def api_get(subpath):
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    try:
        resp = http.get(f"{BACKEND}/{subpath}", headers=_headers(),
                        params=_fwd_params(), timeout=30)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502


# ── Export (streamed CSV) ──
@operator_activity_dashboard_bp.route(
    "/chips/operator-activity/api-export", methods=["GET"])
@operator_activity_dashboard_bp.route(
    "/dc/operator-activity/api-export", methods=["GET"])
def api_export():
    if not _authed():
        return redirect(url_for("auth.login"))
    try:
        resp = http.get(f"{BACKEND}/export", headers=_headers(),
                        params=_fwd_params(), stream=True, timeout=120)
        return Response(
            resp.iter_content(chunk_size=8192), status=resp.status_code,
            headers={
                "Content-Disposition": resp.headers.get(
                    "Content-Disposition", "attachment; filename=operator_activity.csv"),
                "Content-Type": resp.headers.get("Content-Type", "text/csv"),
                "Cache-Control": "no-cache",
            })
    except Exception as e:
        return f"Gateway error: {e}", 502


# ── Rejected-rows CSV download ──
@operator_activity_dashboard_bp.route(
    "/chips/operator-activity/api-rejected/<batch_id>", methods=["GET"])
def api_rejected(batch_id):
    if not _authed():
        return redirect(url_for("auth.login"))
    resp = http.get(f"{BACKEND}/rejected/{batch_id}", headers=_headers(),
                    stream=True, timeout=60)
    return Response(
        resp.iter_content(chunk_size=8192), status=resp.status_code,
        headers={
            "Content-Disposition": resp.headers.get(
                "Content-Disposition", f"attachment; filename=rejected_{batch_id}.csv"),
            "Content-Type": resp.headers.get("Content-Type", "text/csv"),
        })


# ── Upload proxy (multipart) ──
@operator_activity_dashboard_bp.route(
    "/chips/operator-activity/api-upload", methods=["POST"])
def api_upload():
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    if session.get("role") not in ["Admin", "chips_admin"]:
        return jsonify({"detail": "Forbidden: Admin access required"}), 403
    f = request.files.get("file")
    if not f:
        return jsonify({"detail": "No file provided"}), 400
    data = {k: v for k, v in request.form.items()}
    source = data.get("source", "registrar_ea")
    target = f"{BACKEND}/kit-tracker/upload" if source == "kit_tracker" else f"{BACKEND}/upload"
    try:
        resp = http.post(
            target, headers=_headers(),
            files={"file": (f.filename, f.stream, f.mimetype)},
            data=data, timeout=300)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502


# ── Rollback / delete a batch ──
@operator_activity_dashboard_bp.route(
    "/chips/operator-activity/api-uploads/<batch_id>", methods=["DELETE"])
def api_delete(batch_id):
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    if session.get("role") not in ["Admin", "chips_admin"]:
        return jsonify({"detail": "Forbidden: Admin access required"}), 403
    try:
        resp = http.delete(f"{BACKEND}/uploads/{batch_id}", headers=_headers(), timeout=60)
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "application/json"))
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502
