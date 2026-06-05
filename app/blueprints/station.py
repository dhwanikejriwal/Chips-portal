# app/blueprints/station.py
from flask import Blueprint, render_template, request, session, redirect, url_for
import requests

station_bp = Blueprint('station', __name__)

@station_bp.route("/dc/station", methods=["GET"])
def render_dc_station_page():
    jwt_token = session.get("access_token")
    if not jwt_token:
        return redirect(url_for("login_view"))
    
    return render_template("station/station_view.html")
