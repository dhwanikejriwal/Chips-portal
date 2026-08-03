# app/blueprints/operator_data.py
"""Flask blueprint for the Operator Data Management page.

Renders the page and proxies browser XHR calls to the FastAPI backend,
injecting the session bearer token (the token lives in the Flask session and is
never exposed to client JS). The backend re-checks the admin role on the
upload and reveal endpoints - the checks here are only to fail fast.
"""
from flask import (
    Blueprint, render_template, session, redirect, url_for, jsonify, request, Response,
)
import requests as http

operator_data_bp = Blueprint("operator_data", __name__)
BACKEND = "http://127.0.0.1:8000/operator-data"


def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}


def _authed() -> bool:
    return bool(session.get("access_token"))


def _is_admin() -> bool:
    return session.get("role") in ("Admin", "chips_admin")


def _relay(resp):
    return Response(resp.content, status=resp.status_code,
                    content_type=resp.headers.get("Content-Type", "application/json"))


@operator_data_bp.route("/chips/operator-data", methods=["GET"])
def page():
    if not _authed():
        return redirect(url_for("auth.login"))
    return render_template("operator_data/index.html", can_reveal=_is_admin())


# ── DC mount: Aadhar lookup only, no upload and no reveal ──
@operator_data_bp.route("/dc/operator-data", methods=["GET"])
def dc_page():
    if not _authed():
        return redirect(url_for("auth.login"))
    return render_template(
        "operator_data/index.html",
        can_reveal=False,          # decryption stays an admin-only action
        search_only=True,
        api_base="/auth/dc/operator-data",
    )


@operator_data_bp.route("/dc/operator-data/api-search", methods=["GET"])
def dc_api_search():
    return api_search()


@operator_data_bp.route("/dc/operator-data/api-search-by-name", methods=["GET"])
def dc_api_search_by_name():
    return api_search_by_name()


# ── Upload (multipart) ──
@operator_data_bp.route("/chips/operator-data/api-upload", methods=["POST"])
def api_upload():
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    if not _is_admin():
        return jsonify({"detail": "Admin access required."}), 403
    f = request.files.get("file")
    if not f:
        return jsonify({"detail": "No file provided"}), 400
    try:
        resp = http.post(
            f"{BACKEND}/upload", headers=_headers(),
            files={"file": (f.filename, f.stream, f.mimetype)},
            data={"agency": request.form.get("agency", "")}, timeout=300)
        return _relay(resp)
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502


# ── Search by Aadhar ──
@operator_data_bp.route("/chips/operator-data/api-search", methods=["GET"])
def api_search():
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    try:
        resp = http.get(f"{BACKEND}/search", headers=_headers(),
                        params={"aadhar": request.args.get("aadhar", "")}, timeout=30)
        return _relay(resp)
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502


# ── Search by name + last 4 Aadhar digits ──
@operator_data_bp.route("/chips/operator-data/api-search-by-name", methods=["GET"])
def api_search_by_name():
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    try:
        resp = http.get(f"{BACKEND}/search-by-name", headers=_headers(), params={
            "name": request.args.get("name", ""),
            "last4": request.args.get("last4", ""),
            "code": request.args.get("code", ""),
        }, timeout=30)
        return _relay(resp)
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502


# ── Reveal a single Aadhar (admin only; decryption happens in the backend) ──
@operator_data_bp.route("/chips/operator-data/api-reveal", methods=["POST"])
def api_reveal():
    if not _authed():
        return jsonify({"detail": "Session expired"}), 401
    if not _is_admin():
        return jsonify({"detail": "Admin access required."}), 403
    try:
        resp = http.post(f"{BACKEND}/reveal", headers=_headers(),
                         json={"record_id": (request.get_json(silent=True) or {}).get("record_id")},
                         timeout=30)
        return _relay(resp)
    except Exception as e:
        return jsonify({"detail": f"Gateway error: {e}"}), 502
