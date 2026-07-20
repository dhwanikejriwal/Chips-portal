# app/blueprints/kit_registration.py
from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    jsonify,
    Response,
)
import requests as http

kit_registration_bp = Blueprint("kit_registration", __name__)
BACKEND = "http://127.0.0.1:8000/kit-registration"


def _headers():
    return {"Authorization": f"Bearer {session.get('access_token', '')}"}


@kit_registration_bp.route("/chips/kit-registration", methods=["GET"])
def chips_list():
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))

    try:
        resp = http.get(f"{BACKEND}/all", headers=_headers())
        if resp.status_code == 401:
            return redirect(url_for("auth.logout"))
        rows = resp.json() if resp.status_code == 200 else []
    except http.exceptions.ConnectionError:
        rows = []

    return render_template("kit_registration/chips_list.html", requests=rows)


@kit_registration_bp.route("/chips/kit-registration/<int:kit_id>/l1-done", methods=["POST"])
def chips_l1_done(kit_id):
    if not session.get("access_token"):
        return jsonify({"success": False, "error": "Session expired. Please log in again."}), 401
    try:
        resp = http.patch(f"{BACKEND}/{kit_id}/l1-done", headers=_headers(), timeout=10)
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"Gateway error: {str(e)}"}), 500


@kit_registration_bp.route("/chips/kit-registration/<int:kit_id>/l2-done", methods=["POST"])
def chips_l2_done(kit_id):
    if not session.get("access_token"):
        return jsonify({"success": False, "error": "Session expired. Please log in again."}), 401
    try:
        resp = http.patch(f"{BACKEND}/{kit_id}/l2-done", headers=_headers(), timeout=10)
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"Gateway error: {str(e)}"}), 500


@kit_registration_bp.route("/chips/kit-registration/export-excel", methods=["GET"])
def export_excel():
    if not session.get("access_token"):
        return redirect(url_for("auth.login"))
    from flask import request
    ids = request.args.get("ids", "")
    try:
        resp = http.get(f"{BACKEND}/export-excel?ids={ids}", headers=_headers(), stream=True)
        if resp.status_code == 401:
            return redirect(url_for("auth.logout"))
        
        headers = {
            'Content-Disposition': resp.headers.get('Content-Disposition', 'attachment; filename=export.csv'),
            'Content-Type': resp.headers.get('Content-Type', 'text/csv'),
            'Cache-Control': 'no-cache'
        }
        return Response(resp.iter_content(chunk_size=1024), status=resp.status_code, headers=headers)
    except Exception as e:
        return f"Gateway error: {str(e)}", 500
