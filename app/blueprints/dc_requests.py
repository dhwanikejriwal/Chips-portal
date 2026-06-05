# app/blueprints/dc_requests.py
from flask import Blueprint, render_template, request, session, redirect, url_for
import requests

dc_requests_bp = Blueprint('dc_requests', __name__)

@dc_requests_bp.route("/dc/noc_activation", methods=["GET"])
def render_dc_noc_activation_page():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
    
    # Example proxy call to backend
    # headers = {"Authorization": f"Bearer {jwt_token}"}
    # response = requests.get("http://127.0.0.1:8000/dc_requests/noc", headers=headers)
    
    return render_template("dc_requests/dc_requests_view.html")
