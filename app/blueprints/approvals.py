# app/blueprints/approvals.py
from flask import Blueprint, render_template, request, session, redirect, url_for
import requests

approvals_bp = Blueprint('approvals', __name__)

@approvals_bp.route("/chips/approvals", methods=["GET"])
def render_chips_approvals_page():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
    
    return render_template("approvals/approvals_view.html")
