import os
import requests
from flask import Blueprint, render_template, url_for, request, flash, current_app, session, redirect
from werkzeug.utils import secure_filename

candidate_register_bp = Blueprint("candidate_register", __name__)

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


def save_upload(file_obj, upload_folder):
    """Save an uploaded file and return the web-accessible path, or None on error."""
    if not file_obj or file_obj.filename == "":
        return None
    # Read content to check size before saving
    content = file_obj.read()
    if len(content) > MAX_FILE_SIZE:
        return "TOO_LARGE"
    filename = secure_filename(file_obj.filename)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    filepath = os.path.join(upload_folder, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return f"/static/uploads/{filename}"


def get_backend_error(response, fallback="Failed to register candidate."):
    try:
        data = response.json()
    except ValueError:
        return response.text or fallback

    detail = data.get("detail", fallback) if isinstance(data, dict) else data
    if isinstance(detail, list):
        return "; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail)
    return str(detail)


@candidate_register_bp.route("/eligibility")
def eligibility():
    return render_template("user/eligibility.html")


@candidate_register_bp.route("/register", methods=["GET", "POST"])
def register():
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/districts"
    districts = []
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            districts = response.json()
    except requests.exceptions.RequestException:
        flash("Could not fetch districts from API backend. Using default dropdown list.", "warning")

    if request.method == "POST":
        name = request.form.get("name")
        mobile = request.form.get("mobile")
        email = request.form.get("email")
        district = request.form.get("district")
        qualification = request.form.get("qualification")
        lms_id = request.form.get("lms_id")
        nseit_id = request.form.get("nseit_id")
        dob = request.form.get("dob")
        aadhaar = request.form.get("aadhaar")
        address = request.form.get("address")
        pincode = request.form.get("pincode")
        is_existing_operator = request.form.get("is_existing_operator") == "yes"

        upload_folder = os.path.join(current_app.root_path, "static", "uploads")

        # ── 1. PHOTO UPLOAD ──
        photo_path = None
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            result = save_upload(photo_file, upload_folder)
            if result == "TOO_LARGE":
                flash("Profile photo must be under 1 MB.", "danger")
                return render_template("user/register.html", districts=districts)
            photo_path = result

        # ── 2. CONDITIONAL FILE STORAGE ROUTING ENGINE ──
        marksheet_path = None
        tenth_marksheet_path = None

        if qualification == "High School (10th)":
            tenth_file = request.files.get("tenth_marksheet")
            if tenth_file and tenth_file.filename:
                result = save_upload(tenth_file, upload_folder)
                if result == "TOO_LARGE":
                    flash("10th Standard marksheet must be under 1 MB.", "danger")
                    return render_template("user/register.html", districts=districts)
                tenth_marksheet_path = result
                marksheet_path = None
            else:
                flash("10th Standard marksheet is required.", "danger")
                return render_template("user/register.html", districts=districts)
        else:
            # 🌟 Higher Degree Path: Extract and save both items separately
            tenth_file = request.files.get("tenth_marksheet")
            if tenth_file and tenth_file.filename:
                result = save_upload(tenth_file, upload_folder)
                if result == "TOO_LARGE":
                    flash("10th Standard marksheet must be under 1 MB.", "danger")
                    return render_template("user/register.html", districts=districts)
                tenth_marksheet_path = result

            marksheet_file = request.files.get("marksheet")
            if marksheet_file and marksheet_file.filename:
                result = save_upload(marksheet_file, upload_folder)
                if result == "TOO_LARGE":
                    flash("Qualification marksheet must be under 1 MB.", "danger")
                    return render_template("user/register.html", districts=districts)
                marksheet_path = result
            else:
                flash("Highest qualification marksheet is required.", "danger")
                return render_template("user/register.html", districts=districts)

        # ── 3. SEND CLEAN PAYLOAD TO FASTAPI BACKEND ──
        register_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/register-candidate"
        payload = {
            "name": name,
            "mobile": mobile,
            "email": email,
            "district": district,
            "qualification": qualification,
            "lms_id": lms_id if lms_id else None,
            "nseit_id": nseit_id if nseit_id else None,
            "dob": dob,
            "aadhaar": aadhaar,
            "address": address,
            "pincode": pincode,
            "is_existing_operator": str(is_existing_operator).lower(),
            "photo_upload": photo_path,
            "marksheet_upload": marksheet_path,
            "tenth_marksheet_upload": tenth_marksheet_path,
        }

        try:
            reg_response = requests.post(register_url, json=payload)
            if reg_response.status_code == 200:
                data = reg_response.json()
                session["reg_success_code"] = data["request_code"]
                return redirect(url_for("candidate_register.register_success"))
            else:
                flash(get_backend_error(reg_response), "danger")
        except requests.exceptions.RequestException:
            flash("Error connecting to backend API server for registration.", "danger")

    return render_template("user/register.html", districts=districts)


@candidate_register_bp.route("/register/success", methods=["GET"])
def register_success():
    request_code = session.pop("reg_success_code", None)
    if not request_code:
        return redirect("/")
    return render_template("user/reg_success.html", request_code=request_code)
