import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, flash, current_app

candidate_bp = Blueprint("candidate", __name__)

@candidate_bp.before_request
def load_candidate_name():
    if "access_token" in session and session.get("role") == "Candidate" and not session.get("candidate_name"):
        r_id = session.get("r_id")
        if r_id:
            backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
            try:
                res = requests.get(backend_url)
                if res.status_code == 200:
                    session["candidate_name"] = res.json().get("name", "")
            except Exception:
                pass

@candidate_bp.route("/candidate/instructions")
def instructions():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    status_data = {}
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            status_data = response.json()
    except Exception:
        flash("Error connecting to backend API.", "danger")
        
    return render_template("candidate_panel/instructions.html", status_data=status_data)

@candidate_bp.route("/candidate/lms", methods=["GET", "POST"])
def candidate_lms():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    login_id = session.get("user_id")
    
    if request.method == "POST":
        remark = request.form.get("remark")
        name = request.form.get("name")
        mobile = request.form.get("mobile")
        email = request.form.get("email")
        district = request.form.get("district")
        
        backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/submit-lms/{r_id}"
        params = {
            "remark": remark,
            "login_id": login_id,
            "name": name,
            "mobile": mobile,
            "email": email,
            "district": district
        }
        try:
            response = requests.post(backend_url, params=params)
            if response.status_code == 200:
                flash("LMS Request submitted successfully!", "success")
            else:
                detail = response.json().get("detail", "Failed to submit request.")
                flash(detail, "danger")
        except Exception:
            flash("Error connecting to backend API.", "danger")
        return redirect(url_for("candidate.candidate_lms"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    status_data = {}
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            status_data = response.json()
    except Exception:
        flash("Error fetching request details.", "danger")
        
    districts_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/districts"
    districts = []
    try:
        dist_response = requests.get(districts_url)
        if dist_response.status_code == 200:
            districts = dist_response.json()
    except Exception:
        pass
        
    return render_template("candidate_panel/lms.html", status_data=status_data, districts=districts)


@candidate_bp.route("/candidate/nseit", methods=["GET", "POST"])
def candidate_nseit():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    login_id = session.get("user_id")
    
    if request.method == "POST":
        remark = request.form.get("remark")
        name = request.form.get("name")
        exam_unique_code = request.form.get("exam_unique_code")
        lms_id = request.form.get("lms_id")
        
        # Get candidate status data to check existing upload path and district/request_code
        district_name = "Unknown"
        request_code = "UNKNOWN"
        existing_lms_certificate_upload = None
        backend_url_status = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
        try:
            res = requests.get(backend_url_status)
            if res.status_code == 200:
                s_data = res.json()
                district_name = s_data.get("district_name", "Unknown")
                request_code = s_data.get("request_code", "UNKNOWN")
                existing_lms_certificate_upload = s_data.get("lms_certificate_upload")
        except Exception:
            pass

        lms_file = request.files.get("lms_certificate")
        lms_certificate_path = None
        if lms_file and lms_file.filename:
            import os
            from werkzeug.utils import secure_filename
            
            # Read content to check size
            content = lms_file.read()
            if len(content) > 1 * 1024 * 1024:
                flash("LMS Certificate must be under 1 MB.", "danger")
                return redirect(url_for("candidate.candidate_nseit"))
                
            filename = secure_filename(lms_file.filename)
            upload_folder = os.path.join(current_app.root_path, "..", "uploads", "candidate", district_name, request_code)
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            filepath = os.path.join(upload_folder, filename)
            with open(filepath, "wb") as f:
                f.write(content)
            lms_certificate_path = f"/candidate_uploads/{district_name}/{request_code}/{filename}"
        
        # If lms_id is filled but they don't have a certificate uploaded yet
        if lms_id and not existing_lms_certificate_upload and not lms_certificate_path:
            flash("LMS Certificate is required.", "danger")
            return redirect(url_for("candidate.candidate_nseit"))

        backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/submit-nseit/{r_id}"
        params = {
            "remark": remark,
            "login_id": login_id,
            "name": name,
            "exam_unique_code": exam_unique_code,
            "lms_id": lms_id
        }
        if lms_certificate_path:
            params["lms_certificate_upload"] = lms_certificate_path

        try:
            response = requests.post(backend_url, params=params)
            if response.status_code == 200:
                flash("NSEIT Request submitted successfully!", "success")
            else:
                detail = response.json().get("detail", "Failed to submit request.")
                flash(detail, "danger")
        except Exception:
            flash("Error connecting to backend API.", "danger")
        return redirect(url_for("candidate.candidate_nseit"))
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    status_data = {}
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            status_data = response.json()
    except Exception:
        flash("Error fetching request details.", "danger")
        
    return render_template("candidate_panel/nseit.html", status_data=status_data)

@candidate_bp.route("/candidate/skip-lms", methods=["POST"])
def skip_lms():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    login_id = session.get("user_id")
    lms_id = request.form.get("lms_id")
    
    if not lms_id:
        flash("LMS ID is required to skip the request.", "danger")
        return redirect(url_for("candidate.instructions"))

    district_name = "Unknown"
    request_code = "UNKNOWN"
    backend_url_status = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    try:
        res = requests.get(backend_url_status)
        if res.status_code == 200:
            status_data = res.json()
            district_name = status_data.get("district_name", "Unknown")
            request_code = status_data.get("request_code", "UNKNOWN")
    except Exception:
        pass

    lms_file = request.files.get("lms_certificate")
    lms_certificate_path = None
    if lms_file and lms_file.filename:
        import os
        from werkzeug.utils import secure_filename
        
        content = lms_file.read()
        if len(content) > 1 * 1024 * 1024:
            flash("LMS Certificate must be under 1 MB.", "danger")
            return redirect(url_for("candidate.instructions"))
            
        filename = secure_filename(lms_file.filename)
        upload_folder = os.path.join(current_app.root_path, "..", "uploads", "candidate", district_name, request_code)
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        filepath = os.path.join(upload_folder, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        lms_certificate_path = f"/candidate_uploads/{district_name}/{request_code}/{filename}"
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/skip-lms/{r_id}"
    params = {"lms_id": lms_id, "login_id": login_id}
    if lms_certificate_path:
        params["lms_certificate_upload"] = lms_certificate_path
        
    try:
        response = requests.post(backend_url, params=params)
        if response.status_code == 200:
            flash("LMS step skipped successfully!", "success")
        else:
            detail = response.json().get("detail", "Failed to skip LMS request.")
            flash(detail, "danger")
    except Exception:
        flash("Error connecting to backend API.", "danger")
        
    return redirect(url_for("candidate.instructions"))

@candidate_bp.route("/candidate/skip-nseit", methods=["POST"])
def skip_nseit():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    login_id = session.get("user_id")
    nseit_id = request.form.get("nseit_id")
    
    if not nseit_id:
        flash("NSEIT Certificate ID is required to skip the request.", "danger")
        return redirect(url_for("candidate.instructions"))

    district_name = "Unknown"
    request_code = "UNKNOWN"
    backend_url_status = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    try:
        res = requests.get(backend_url_status)
        if res.status_code == 200:
            status_data = res.json()
            district_name = status_data.get("district_name", "Unknown")
            request_code = status_data.get("request_code", "UNKNOWN")
    except Exception:
        pass

    nseit_file = request.files.get("nseit_certificate")
    nseit_certificate_path = None
    if nseit_file and nseit_file.filename:
        import os
        from werkzeug.utils import secure_filename
        
        content = nseit_file.read()
        if len(content) > 1 * 1024 * 1024:
            flash("NSEIT Certificate must be under 1 MB.", "danger")
            return redirect(url_for("candidate.instructions"))
            
        filename = secure_filename(nseit_file.filename)
        upload_folder = os.path.join(current_app.root_path, "..", "uploads", "candidate", district_name, request_code)
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        filepath = os.path.join(upload_folder, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        nseit_certificate_path = f"/candidate_uploads/{district_name}/{request_code}/{filename}"
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/skip-nseit/{r_id}"
    params = {"nseit_id": nseit_id, "login_id": login_id}
    if nseit_certificate_path:
        params["nseit_certificate_upload"] = nseit_certificate_path
        
    try:
        response = requests.post(backend_url, params=params)
        if response.status_code == 200:
            flash("NSEIT step skipped and ID registered successfully!", "success")
        else:
            detail = response.json().get("detail", "Failed to skip NSEIT request.")
            flash(detail, "danger")
    except Exception:
        flash("Error connecting to backend API.", "danger")
        
    return redirect(url_for("candidate.instructions"))

@candidate_bp.route("/candidate/profile")
def profile():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    status_data = {}
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            status_data = response.json()
    except Exception:
        flash("Error fetching candidate profile details.", "danger")
        
    return render_template("candidate_panel/candidate_profile.html", status_data=status_data)


@candidate_bp.route("/candidate/update-lms-id", methods=["POST"])
def update_lms_id():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    login_id = session.get("user_id")
    lms_id = request.form.get("lms_id")
    
    if not lms_id:
        flash("LMS ID is required.", "danger")
        return redirect(url_for("candidate.candidate_lms"))

    # Fetch status to get district & request code
    district_name = "Unknown"
    request_code = "UNKNOWN"
    backend_url_status = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    try:
        res = requests.get(backend_url_status)
        if res.status_code == 200:
            status_data = res.json()
            district_name = status_data.get("district_name", "Unknown")
            request_code = status_data.get("request_code", "UNKNOWN")
    except Exception:
        pass

    lms_file = request.files.get("lms_certificate")
    if not lms_file or not lms_file.filename:
        flash("LMS Certificate is required.", "danger")
        return redirect(url_for("candidate.candidate_lms"))
        
    lms_certificate_path = None
    if lms_file and lms_file.filename:
        import os
        from werkzeug.utils import secure_filename
        
        # Read content to check size
        content = lms_file.read()
        if len(content) > 1 * 1024 * 1024:
            flash("LMS Certificate must be under 1 MB.", "danger")
            return redirect(url_for("candidate.candidate_lms"))
            
        filename = secure_filename(lms_file.filename)
        upload_folder = os.path.join(current_app.root_path, "..", "uploads", "candidate", district_name, request_code)
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        filepath = os.path.join(upload_folder, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        lms_certificate_path = f"/candidate_uploads/{district_name}/{request_code}/{filename}"
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/update-lms-id/{r_id}"
    params = {"lms_id": lms_id, "login_id": login_id}
    if lms_certificate_path:
        params["lms_certificate_upload"] = lms_certificate_path
        
    try:
        response = requests.post(backend_url, params=params)
        if response.status_code == 200:
            flash("LMS ID updated successfully!", "success")
        else:
            detail = response.json().get("detail", "Failed to update LMS ID.")
            flash(detail, "danger")
    except Exception:
        flash("Error connecting to backend API.", "danger")
        
    return redirect(url_for("candidate.candidate_lms"))


@candidate_bp.route("/candidate/update-nseit-id", methods=["POST"])
def update_nseit_id():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))
        
    r_id = session.get("r_id")
    login_id = session.get("user_id")
    nseit_id = request.form.get("nseit_id")
    
    if not nseit_id:
        flash("NSEIT Certificate ID is required.", "danger")
        return redirect(url_for("candidate.candidate_nseit"))

    # Fetch status to get district & request code
    district_name = "Unknown"
    request_code = "UNKNOWN"
    backend_url_status = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    try:
        res = requests.get(backend_url_status)
        if res.status_code == 200:
            status_data = res.json()
            district_name = status_data.get("district_name", "Unknown")
            request_code = status_data.get("request_code", "UNKNOWN")
    except Exception:
        pass

    nseit_file = request.files.get("nseit_certificate")
    if not nseit_file or not nseit_file.filename:
        flash("NSEIT Certificate is required.", "danger")
        return redirect(url_for("candidate.candidate_nseit"))
        
    nseit_certificate_path = None
    if nseit_file and nseit_file.filename:
        import os
        from werkzeug.utils import secure_filename
        
        # Read content to check size
        content = nseit_file.read()
        if len(content) > 1 * 1024 * 1024:
            flash("NSEIT Certificate must be under 1 MB.", "danger")
            return redirect(url_for("candidate.candidate_nseit"))
            
        filename = secure_filename(nseit_file.filename)
        upload_folder = os.path.join(current_app.root_path, "..", "uploads", "candidate", district_name, request_code)
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        filepath = os.path.join(upload_folder, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        nseit_certificate_path = f"/candidate_uploads/{district_name}/{request_code}/{filename}"
        
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/update-nseit-id/{r_id}"
    params = {"nseit_id": nseit_id, "login_id": login_id}
    if nseit_certificate_path:
        params["nseit_certificate_upload"] = nseit_certificate_path
        
    try:
        response = requests.post(backend_url, params=params)
        if response.status_code == 200:
            flash("NSEIT Certificate ID updated successfully!", "success")
        else:
            detail = response.json().get("detail", "Failed to update NSEIT Certificate ID.")
            flash(detail, "danger")
    except Exception:
        flash("Error connecting to backend API.", "danger")
        
    return redirect(url_for("candidate.candidate_nseit"))

@candidate_bp.route("/candidate/change-password", methods=["GET", "POST"])
def change_password():
    if "access_token" not in session or session.get("role") != "Candidate":
        flash("Unauthorized access. Please log in.", "danger")
        return redirect(url_for("auth.login"))

    r_id = session.get("r_id")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate/status/{r_id}"
    status_data = {}
    try:
        response = requests.get(backend_url)
        if response.status_code == 200:
            status_data = response.json()
    except Exception:
        pass

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return render_template("candidate_panel/change_password.html", status_data=status_data)
            
        if current_password == new_password:
            flash("New password cannot be the same as your current password.", "danger")
            return render_template("candidate_panel/change_password.html", status_data=status_data)

        backend_pw_url = f"{current_app.config['BACKEND_API_URL']}/auth/change-password"
        headers = {"Authorization": f"Bearer {session.get('access_token')}"}
        payload = {
            "current_password": current_password,
            "new_password": new_password
        }

        try:
            response = requests.post(backend_pw_url, json=payload, headers=headers)
            if response.status_code == 200:
                flash("Password updated successfully!", "success")
                session["has_changed_password"] = True
                return redirect(url_for("candidate.profile"))
            else:
                detail = response.json().get("detail", "Failed to update password.")
                flash(detail, "danger")
        except Exception:
            flash("Error connecting to backend API.", "danger")

    return render_template("candidate_panel/change_password.html", status_data=status_data)


