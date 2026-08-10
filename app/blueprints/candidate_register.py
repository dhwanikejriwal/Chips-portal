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

    # Run on-demand cleanup of expired temp files older than 1 hour (3600 seconds)
    try:
        from app.utils.temp_cleaner import cleanup_temp_files
        cleanup_temp_files(upload_folder, max_age_seconds=3600)
    except Exception:
        pass

    # Read content to check size before saving
    content = file_obj.read()
    if len(content) > MAX_FILE_SIZE:
        return "TOO_LARGE"
    filename = secure_filename(file_obj.filename)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return f"/uploads/temp/{filename}"


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
    return render_template("user_registration/eligibility.html")


@candidate_register_bp.route("/check-mobile", methods=["GET"])
def check_mobile():
    mobile = request.args.get("mobile")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/check-mobile"
    try:
        response = requests.get(backend_url, params={"mobile": mobile})
        return response.json(), response.status_code
    except Exception:
        return {"exists": False}, 500

@candidate_register_bp.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.json.get("email")
    mobile = request.json.get("mobile")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/send-otp"
    try:
        payload = {"email": email}
        if mobile:
            payload["mobile"] = mobile
        response = requests.post(backend_url, json=payload)
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"success": False, "detail": "Error connecting to backend API."}, 500


@candidate_register_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.json.get("email")
    otp_code = request.json.get("otp_code")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/verify-otp"
    try:
        response = requests.post(backend_url, json={"email": email, "otp_code": otp_code})
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"success": False, "detail": "Error connecting to backend API."}, 500

@candidate_register_bp.route("/track", methods=["POST"])
def track():
    identifier = request.json.get("identifier")
    backend_url = f"{current_app.config['BACKEND_API_URL']}/candidate_register/track"
    try:
        response = requests.post(backend_url, json={"identifier": identifier})
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"success": False, "detail": "Error connecting to backend API."}, 500



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
        if qualification == "Other":
            other_qual = request.form.get("other_qualification")
            if other_qual:
                qualification = other_qual.strip()
        lms_id = request.form.get("lms_id")
        nseit_id = request.form.get("nseit_id")
        dob = request.form.get("dob")
        aadhaar = request.form.get("aadhaar")
        address = request.form.get("address")
        pincode = request.form.get("pincode")
        is_existing_operator = request.form.get("is_existing_operator") == "yes"

        upload_folder = os.path.join(current_app.root_path, "..", "uploads", "temp")
        form_data = dict(request.form)
        existing_photo = form_data.get('existing_photo')
        existing_tenth = form_data.get('existing_tenth_marksheet')
        existing_marksheet = form_data.get('existing_marksheet')
        existing_lms_certificate = form_data.get('existing_lms_certificate')
        existing_nseit_certificate = form_data.get('existing_nseit_certificate')
        
        global_field_errors = {}

        def add_ocr_error(e, file_key):
            import json
            error_msg = str(e)
            if error_msg.startswith('{'):
                try:
                    parsed = json.loads(error_msg)
                    sub = parsed.get('field_errors', {})
                    clean_vals = []
                    for val in sub.values():
                        val_str = str(val).strip()
                        if val_str.startswith("Validation Error:"):
                            val_str = val_str[len("Validation Error:"):].strip()
                        clean_vals.append(val_str)
                    global_field_errors[file_key] = "<br>".join(clean_vals)
                except:
                    global_field_errors[file_key] = error_msg
            else:
                if error_msg.startswith("Validation Error:"):
                    error_msg = error_msg[len("Validation Error:"):].strip()
                global_field_errors[file_key] = error_msg

        # ── 1. PHOTO UPLOAD ──
        photo_path = existing_photo
        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            result = save_upload(photo_file, upload_folder)
            if result == "TOO_LARGE":
                global_field_errors['photo'] = 'Profile photo must be under 1 MB.'
            else:
                photo_path = result
                form_data['existing_photo'] = photo_path
        elif not photo_path:
            global_field_errors['photo'] = 'Profile photo is required.'

        # ── 2. CONDITIONAL FILE STORAGE ROUTING ENGINE ──
        marksheet_path = existing_marksheet
        tenth_marksheet_path = existing_tenth

        # Process 10th File
        tenth_file = request.files.get("tenth_marksheet")
        if tenth_file and tenth_file.filename:
            try:
                result = save_upload(tenth_file, upload_folder)
                if result == "TOO_LARGE":
                    global_field_errors['tenth_marksheet'] = "10th marksheet must be under 1 MB."
                else:
                    tenth_marksheet_path = result
                    form_data['existing_tenth_marksheet'] = tenth_marksheet_path
            except ValueError as e:
                add_ocr_error(e, 'tenth_marksheet')
        elif not tenth_marksheet_path:
            global_field_errors['tenth_marksheet'] = "10th Standard marksheet is required."
        
        # Process Highest Qual
        if qualification != "High School (10th)":
            marksheet_file = request.files.get("marksheet")
            if marksheet_file and marksheet_file.filename:
                try:
                    result = save_upload(marksheet_file, upload_folder)
                    if result == "TOO_LARGE":
                        global_field_errors['marksheet'] = "Highest qualification marksheet must be under 1 MB."
                    else:
                        marksheet_path = result
                        form_data['existing_marksheet'] = marksheet_path
                except ValueError as e:
                    add_ocr_error(e, 'marksheet')
            elif not marksheet_path:
                global_field_errors['marksheet'] = "Highest qualification marksheet is required."
        else:
            marksheet_path = None
            
        # Process LMS Certificate
        lms_certificate_path = existing_lms_certificate
        lms_cert_file = request.files.get("lms_certificate")
        if lms_cert_file and lms_cert_file.filename:
            result = save_upload(lms_cert_file, upload_folder)
            if result == "TOO_LARGE":
                global_field_errors['lms_certificate'] = "LMS certificate must be under 1 MB."
            else:
                lms_certificate_path = result
                form_data['existing_lms_certificate'] = lms_certificate_path

        # Process NSEIT Certificate
        nseit_certificate_path = existing_nseit_certificate
        nseit_cert_file = request.files.get("nseit_certificate")
        if nseit_cert_file and nseit_cert_file.filename:
            result = save_upload(nseit_cert_file, upload_folder)
            if result == "TOO_LARGE":
                global_field_errors['nseit_certificate'] = "NSEIT certificate must be under 1 MB."
            else:
                nseit_certificate_path = result
                form_data['existing_nseit_certificate'] = nseit_certificate_path

        # Backend Validation: Certificate mandatory if ID is provided
        if lms_id and not lms_certificate_path:
            global_field_errors['lms_certificate'] = "LMS Certificate is required when LMS ID is provided."

        if nseit_id and not nseit_certificate_path:
            global_field_errors['nseit_certificate'] = "NSEIT Certificate is required when NSEIT Certificate Number is provided."

        if global_field_errors:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                from flask import jsonify
                return jsonify({"success": False, "field_errors": global_field_errors, "error": "Validation failed. Please check form entries."}), 400
            return render_template("user_registration/register.html", field_errors=global_field_errors, form_data=form_data, districts=districts)

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
            "lms_certificate_upload": lms_certificate_path,
            "nseit_certificate_upload": nseit_certificate_path,
        }

        try:
            reg_response = requests.post(register_url, json=payload)
            if reg_response.status_code == 200:
                data = reg_response.json()
                request_code = data["request_code"]
                
                # Move files to proper directory and update DB
                import shutil
                dist_name = "DISTRICT_" + district
                for d in districts:
                    if d['district_code'] == district:
                        dist_name = d['district_name']
                        break
                        
                final_dir = os.path.join(current_app.root_path, "..", "uploads", "candidate", dist_name, request_code)
                os.makedirs(final_dir, exist_ok=True)
                
                def move_file(temp_path):
                    if not temp_path: return None
                    filename = temp_path.split("/")[-1]
                    old_full_path = os.path.join(current_app.root_path, "..", "uploads", "temp", filename)
                    if not os.path.exists(old_full_path):
                        old_full_path = os.path.join(current_app.root_path, "static", "uploads", filename)
                    new_full_path = os.path.join(final_dir, filename)
                    if os.path.exists(old_full_path):
                        shutil.move(old_full_path, new_full_path)
                        print(f"[File Mover] Successfully moved {filename} from temp to {final_dir} (removed from temp)")
                    return f"/candidate_uploads/{dist_name}/{request_code}/{filename}"
                
                final_photo = move_file(photo_path)
                final_marksheet = move_file(marksheet_path)
                final_tenth = move_file(tenth_marksheet_path)
                final_lms_cert = move_file(lms_certificate_path)
                final_nseit_cert = move_file(nseit_certificate_path)
                
                from backend.database import SessionLocal
                from backend.models import Candidate
                db = SessionLocal()
                try:
                    cand = db.query(Candidate).filter(Candidate.request_code == request_code).first()
                    if cand:
                        if final_photo: cand.photo_upload = final_photo
                        if final_marksheet: cand.marksheet_upload = final_marksheet
                        if final_tenth: cand.tenth_marksheet_upload = final_tenth
                        if final_lms_cert: cand.lms_certificate_upload = final_lms_cert
                        if final_nseit_cert: cand.nseit_certificate_upload = final_nseit_cert
                        db.commit()
                finally:
                    db.close()
                
                session["reg_success_code"] = request_code
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    from flask import jsonify
                    return jsonify({"success": True, "redirect_url": url_for("candidate_register.register_success")})
                return redirect(url_for("candidate_register.register_success"))
            else:
                err_msg = get_backend_error(reg_response)
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    from flask import jsonify
                    return jsonify({"success": False, "error": err_msg}), 400
                flash(err_msg, "danger")
        except requests.exceptions.RequestException:
            err_msg = "Error connecting to backend API server for registration."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                from flask import jsonify
                return jsonify({"success": False, "error": err_msg}), 500
            flash(err_msg, "danger")

    return render_template("user_registration/register.html", districts=districts)


@candidate_register_bp.route("/register/success", methods=["GET"])
def register_success():
    request_code = session.pop("reg_success_code", None)
    if not request_code:
        return redirect("/")
    return render_template("user_registration/reg_success.html", request_code=request_code)


@candidate_register_bp.route("/ocr/extract-id", methods=["POST"])
def ocr_extract_id():
    from flask import jsonify
    import re
    file = request.files.get("file")
    doc_type = request.form.get("type") # 'lms' or 'nseit'
    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file uploaded."}), 400
        
    try:
        import io
        import os
        from PIL import Image, ImageEnhance
        import pytesseract
        
        file_bytes = file.read()
        
        # Check if PDF or Image
        is_pdf = file.content_type == "application/pdf" or file.filename.lower().endswith(".pdf")
        
        images_to_process = []
        if is_pdf:
            from pdf2image import convert_from_bytes
            poppler_path = os.getenv("POPPLER_PATH")
            if not poppler_path:
                common_poppler = [
                    r"C:\Program Files\poppler-26.02.0\Library\bin",
                    r"C:\poppler-26.02.0\Library\bin",
                    r"C:\poppler\Library\bin", 
                    r"C:\Release-24.02.0-0\poppler-24.02.0\Library\bin",
                    r"C:\Program Files (x86)\Windows Media Player\Release-26.02.0-0\poppler-26.02.0\Library\bin"
                ]
                for p in common_poppler:
                    if os.path.exists(p):
                        poppler_path = p
                        break
            images_to_process = convert_from_bytes(file_bytes, first_page=1, last_page=1, poppler_path=poppler_path)
        else:
            images_to_process = [Image.open(io.BytesIO(file_bytes))]
            
        text_content = ""
        if images_to_process:
            img = images_to_process[0]
            # Preprocessing: Grayscale -> 3x size -> Enhance contrast for small text
            img_gray = img.convert('L')
            img_large = img_gray.resize((img.width * 3, img.height * 3), Image.Resampling.LANCZOS)
            enhancer = ImageEnhance.Contrast(img_large)
            img_processed = enhancer.enhance(2.0)
            
            # Configure Tesseract path (already sets globally in ocr_utils, but let's be double sure)
            tesseract_cmd_path = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            if os.path.exists(tesseract_cmd_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
                
            # Perform OCR (PSM 3 handles fully automatic layout)
            text_content = pytesseract.image_to_string(img_processed, config='--psm 3')
            
            # Fallback to PSM 11 (sparse text) if blank
            if not text_content.strip():
                text_content = pytesseract.image_to_string(img_processed, config='--psm 11')
                
        print("===== ADVANCED OCR EXTRACTED TEXT =====")
        print(text_content)
        print("=======================================")
        with open("debug_ocr_text.txt", "w", encoding="utf-8") as f:
            f.write(text_content)
        
        # Validate that the uploaded document type matches the field category
        text_upper = text_content.upper()

        # Validate candidate name matches the certificate name
        name_input = request.form.get("name")
        if not name_input or not name_input.strip() or name_input.strip().lower() == "none":
            from flask import session
            name_input = session.get("candidate_name")
            
        if name_input and name_input.strip() and name_input.strip().lower() != "none":
            from thefuzz import fuzz
            name_upper = name_input.upper().strip()
            score = fuzz.token_set_ratio(name_upper, text_upper)
            if score < 65:
                doc_name = "LMS Certificate" if doc_type == "lms" else "NSEIT Certificate"
                return jsonify({
                    "success": False,
                    "error": f"Name Mismatch: The candidate name '{name_input}' does not match the name found in the uploaded {doc_name}."
                })

        if doc_type == "lms":
            # LMS keywords
            lms_keywords = ["ACCOMPLISHMENT", "COURSE", "COMPLETED", "LEARNING", "ENROLMENT & UPDATE", "CHILD ENROLMENT", "LMS", "omHcB8Nlyq", "C7KMeFxpJN"]
            is_lms = any(kw in text_upper for kw in lms_keywords)
            is_nseit_instead = "OPERATOR ELIGIBILITY" in text_upper or "ELIGIBILITY CERTIFICATE" in text_upper
            
            if is_nseit_instead or not is_lms:
                return jsonify({"success": False, "error": "Invalid Document: The uploaded file does not look like an LMS Certificate of Accomplishment."})
                
        elif doc_type == "nseit":
            # NSEIT keywords
            nseit_keywords = ["ELIGIBILITY", "OPERATOR ELIGIBILITY", "PASSED THE EXAMINATION", "NSEIT", "TESTING AND CERTIFICATION", "NS123456"]
            is_nseit = any(kw in text_upper for kw in nseit_keywords)
            is_lms_instead = "ACCOMPLISHMENT" in text_upper and "SUCCESSFULLY COMPLETED" in text_upper
            
            if is_lms_instead or not is_nseit:
                return jsonify({"success": False, "error": "Invalid Document: The uploaded file does not look like an NSEIT Operator Eligibility Certificate."})

            # Search for dates and check expiry
            import datetime
            
            def parse_date_match(match_obj):
                try:
                    d_val = int(match_obj.group(1))
                    mon_str = match_obj.group(2).upper()
                    y_val = int(match_obj.group(3))
                    
                    months_map = {
                        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
                        "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5,
                        "JUNE": 6, "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10,
                        "NOVEMBER": 11, "DECEMBER": 12
                    }
                    
                    if mon_str.isdigit():
                        m_val = int(mon_str)
                    else:
                        m_val = months_map.get(mon_str, 1)
                        
                    if 1 <= m_val <= 12 and 1 <= d_val <= 31:
                        return datetime.date(y_val, m_val, d_val)
                except ValueError:
                    pass
                return None

            date_pattern = r"\b(\d{1,2})[-/\.\s]+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2})[-/\.\s]+(\d{4})\b"
            
            found_dates = []
            for m in re.finditer(date_pattern, text_content, re.IGNORECASE):
                parsed = parse_date_match(m)
                if parsed:
                    found_dates.append(parsed)
            
            found_dates = sorted(list(set(found_dates)))
            issue_date = None
            expiry_date = None
            
            lines = text_content.splitlines()
            for idx, line in enumerate(lines):
                line_upper = line.upper()
                if "ISSUE" in line_upper:
                    context = " ".join(lines[max(0, idx-1):min(len(lines), idx+3)])
                    m_date = re.search(date_pattern, context, re.IGNORECASE)
                    if m_date:
                        parsed = parse_date_match(m_date)
                        if parsed:
                            issue_date = parsed
                if "EXPIRY" in line_upper or "EXPIRE" in line_upper:
                    context = " ".join(lines[max(0, idx-1):min(len(lines), idx+3)])
                    m_date = re.search(date_pattern, context, re.IGNORECASE)
                    if m_date:
                        parsed = parse_date_match(m_date)
                        if parsed:
                            expiry_date = parsed

            if not issue_date and not expiry_date:
                if len(found_dates) >= 2:
                    issue_date = found_dates[0]
                    expiry_date = found_dates[1]
                elif len(found_dates) == 1:
                    issue_date = found_dates[0]
            elif issue_date and not expiry_date:
                other_dates = [dt for dt in found_dates if dt != issue_date]
                if other_dates:
                    expiry_date = other_dates[0]
            elif expiry_date and not issue_date:
                other_dates = [dt for dt in found_dates if dt != expiry_date]
                if other_dates:
                    issue_date = other_dates[0]

            if issue_date and not expiry_date:
                try:
                    expiry_date = issue_date.replace(year=issue_date.year + 3)
                except ValueError:
                    expiry_date = issue_date + datetime.timedelta(days=3*365)

            current_date = datetime.date.today()
            if expiry_date and expiry_date < current_date:
                expiry_str = expiry_date.strftime("%d-%m-%Y")
                return jsonify({
                    "success": False, 
                    "error": f"Uploaded NSEIT Certificate has expired. (Expiry Date: {expiry_str}). Please upload a valid certificate."
                })

        # Parse extracted text with advanced regexes
        extracted_id = None
        
        if doc_type == "lms":
            # Match 'ID: omHcB8Nlyq' or 'ID: C7KMeFxpJN' (case-sensitive letters & digits)
            match = re.search(r"\bID\s*[:\.-]?\s*([a-zA-Z0-9]{6,15})\b", text_content)
            if match:
                extracted_id = match.group(1)
            else:
                # Match general LMS prefixed pattern
                match = re.search(r"\bLMS\s*[-_]?\s*([a-zA-Z0-9]{4,15})\b", text_content, re.IGNORECASE)
                if match:
                    extracted_id = match.group(0)
                else:
                    # Final fallback: any token starting with LMS
                    for word in text_content.split():
                        if word.upper().startswith("LMS"):
                            extracted_id = word
                            break
        elif doc_type == "nseit":
            # Match 'Certificate No: NS123456'
            match = re.search(r"Certificate\s+No[s\.]*\s*[:\.-]?\s*([a-zA-Z0-9_-]{4,15})", text_content, re.IGNORECASE)
            if match:
                extracted_id = match.group(1)
            else:
                # Match general NSEIT prefixed pattern
                match = re.search(r"\bNSEIT\s*[-_]?\s*([a-zA-Z0-9]{4,15})\b", text_content, re.IGNORECASE)
                if match:
                    extracted_id = match.group(0)
        # General Fallback if specific checks failed
        if not extracted_id:
            for line in text_content.splitlines():
                cleaned_line = re.sub(r"[^\w\s:-]", "", line)
                match = re.search(r"\b(ID|NO|NUMBER|CODE|CERTIFICATE|REGISTRATION|REG|USERID|USERNAME)\b\s*[:\.-]?\s*([a-zA-Z0-9_-]{5,15})\b", cleaned_line, re.IGNORECASE)
                if match:
                    extracted_id = match.group(2)
                    break
                            
        if extracted_id:
            # Clean special characters but keep casing and alphanumeric chars
            extracted_id = re.sub(r"[^a-zA-Z0-9]", "", extracted_id)
            saved_path = None
            try:
                upload_folder = os.path.join(current_app.root_path, "..", "uploads", "temp")
                file.seek(0)
                saved_path = save_upload(file, upload_folder)
            except Exception:
                pass
            return jsonify({"success": True, "id": extracted_id, "file_path": saved_path if saved_path != "TOO_LARGE" else None})
        else:
            return jsonify({"success": False, "error": "Could not find a valid ID in the document , please check the quality of document"})
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@candidate_register_bp.route("/upload-temp-file", methods=["POST"])
def upload_temp_file():
    from flask import jsonify, request, current_app
    import os
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file provided."}), 400
    upload_folder = os.path.join(current_app.root_path, "..", "uploads", "temp")
    saved_path = save_upload(file, upload_folder)
    if saved_path == "TOO_LARGE":
        return jsonify({"success": False, "error": "File size exceeds 1 MB limit."}), 400
    if not saved_path:
        return jsonify({"success": False, "error": "Failed to save file."}), 500
    return jsonify({"success": True, "file_path": saved_path})


@candidate_register_bp.route("/ocr/validate-marksheet", methods=["POST"])
def ocr_validate_marksheet():
    file = request.files.get("file")
    doc_type = request.form.get("type") # 'tenth' or 'highest'
    name = request.form.get("name")
    dob = request.form.get("dob")
    qualification = request.form.get("qualification", "High School (10th)")

    if not file or not file.filename:
        from flask import jsonify
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    try:
        from flask import jsonify, current_app
        import io
        import os
        import re
        from PIL import Image, ImageEnhance
        from backend.utils.ocr_utils import validate_marksheet, extract_text_from_bytes
        file_bytes = file.read()
        
        if qualification != "Other":
            text_content = extract_text_from_bytes(file_bytes, file.content_type, lang="eng+hin")
                
            # Run validation with simplified fallback word matching logging
            print("===== Flask Marksheet OCR Text =====")
            print(f"Name: {name}, DOB: {dob}, Qualification: {qualification}")
            print(text_content)
            print("====================================")
            with open("debug_ocr_marksheet.txt", "w", encoding="utf-8") as f:
                f.write(text_content)
            with open("debug_ocr_params.txt", "w", encoding="utf-8") as f:
                f.write(f"name={name}\ndob={dob}\nqualification={qualification}\n")
                
            validate_marksheet(text_content, name, dob, qualification)
        
        saved_path = None
        try:
            upload_folder = os.path.join(current_app.root_path, "..", "uploads", "temp")
            from werkzeug.datastructures import FileStorage
            f_obj = FileStorage(stream=io.BytesIO(file_bytes), filename=file.filename, content_type=file.content_type)
            saved_path = save_upload(f_obj, upload_folder)
        except Exception as se:
            print("Error saving temp marksheet:", se)
            
        return jsonify({"success": True, "file_path": saved_path if saved_path != "TOO_LARGE" else None})
        
    except ValueError as ve:
        err_msg = str(ve)
        try:
            import json
            parsed = json.loads(err_msg)
            if isinstance(parsed, dict) and "field_errors" in parsed:
                errors_dict = parsed["field_errors"]
                msg_list = []
                for field, field_err in errors_dict.items():
                    clean_err = field_err.strip()
                    if clean_err.startswith("Validation Error:"):
                        clean_err = clean_err[len("Validation Error:"):].strip()
                    msg_list.append(clean_err)
                err_msg = " ".join(msg_list)
        except Exception:
            pass
            
        if err_msg.startswith("Validation Error:"):
            err_msg = err_msg[len("Validation Error:"):].strip()
            
        return jsonify({"success": False, "error": err_msg})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to process document: {str(e)}"})

