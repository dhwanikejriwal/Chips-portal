import os
import requests
from flask import Blueprint, render_template, url_for, request, flash, current_app, session, redirect
from werkzeug.utils import secure_filename

candidate_register_bp = Blueprint("candidate_register", __name__)

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB


import uuid


def save_upload(file_obj, upload_folder):
    """Save an uploaded file and return the web-accessible path, or None on error."""
    if not file_obj or not file_obj.filename:
        return None

    # Run on-demand cleanup of expired temp files older than 1 hour (3600 seconds)
    try:
        from app.utils.temp_cleaner import cleanup_temp_files
        cleanup_temp_files(upload_folder, max_age_seconds=3600)
    except Exception:
        pass

    try:
        content = file_obj.read()
        if len(content) > MAX_FILE_SIZE:
            return "TOO_LARGE"
        
        orig_name = file_obj.filename or "upload"
        base, ext = os.path.splitext(orig_name)
        safe_base = secure_filename(base)
        if not safe_base:
            safe_base = "upload"
        safe_ext = secure_filename(ext.lstrip("."))
        if safe_ext:
            filename = f"{safe_base}_{uuid.uuid4().hex[:8]}.{safe_ext}"
        else:
            filename = f"{safe_base}_{uuid.uuid4().hex[:8]}"

        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        return f"/uploads/temp/{filename}"
    except Exception as e:
        print(f"[save_upload error] {e}")
        return None


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
    from app.utils.backend_url import get_backend_base_url
    urls = [
        f"{current_app.config['BACKEND_API_URL']}/candidate_register/check-mobile",
        f"{get_backend_base_url()}/candidate_register/check-mobile",
        f"{get_backend_base_url()}/api/candidate_register/check-mobile"
    ]
    for backend_url in urls:
        try:
            response = requests.get(backend_url, params={"mobile": mobile}, timeout=5)
            if response.status_code == 200:
                return response.json(), 200
        except Exception:
            continue
    return {"exists": False}, 200

@candidate_register_bp.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.json.get("email")
    mobile = request.json.get("mobile")
    from flask import jsonify
    from app.utils.backend_url import get_backend_base_url
    urls = [
        f"{current_app.config['BACKEND_API_URL']}/candidate_register/send-otp",
        f"{get_backend_base_url()}/candidate_register/send-otp",
        f"{get_backend_base_url()}/api/candidate_register/send-otp"
    ]
    payload = {"email": email}
    if mobile:
        payload["mobile"] = mobile
    
    last_err = None
    for backend_url in urls:
        try:
            response = requests.post(backend_url, json=payload, timeout=20)
            try:
                data = response.json()
            except Exception:
                data = {"detail": response.text or "Error processing OTP request."}
            return jsonify(data), response.status_code
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            continue

    return jsonify({"success": False, "detail": f"Error connecting to backend API: {last_err}"}), 500


@candidate_register_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.json.get("email")
    otp_code = request.json.get("otp_code")
    from flask import jsonify
    from app.utils.backend_url import get_backend_base_url
    urls = [
        f"{current_app.config['BACKEND_API_URL']}/candidate_register/verify-otp",
        f"{get_backend_base_url()}/candidate_register/verify-otp",
        f"{get_backend_base_url()}/api/candidate_register/verify-otp"
    ]
    payload = {"email": email, "otp_code": otp_code}
    
    last_err = None
    for backend_url in urls:
        try:
            response = requests.post(backend_url, json=payload, timeout=15)
            try:
                data = response.json()
            except Exception:
                data = {"detail": response.text or "Error processing OTP verification."}
            return jsonify(data), response.status_code
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            continue

    return jsonify({"success": False, "detail": f"Error connecting to backend API: {last_err}"}), 500

@candidate_register_bp.route("/track", methods=["POST"])
def track():
    identifier = request.json.get("identifier")
    from flask import jsonify
    from app.utils.backend_url import get_backend_base_url
    urls = [
        f"{current_app.config['BACKEND_API_URL']}/candidate_register/track",
        f"{get_backend_base_url()}/candidate_register/track",
        f"{get_backend_base_url()}/api/candidate_register/track"
    ]
    
    last_err = None
    for backend_url in urls:
        try:
            response = requests.post(backend_url, json={"identifier": identifier}, timeout=15)
            try:
                data = response.json()
            except Exception:
                data = {"detail": response.text or "Error processing request."}
            return jsonify(data), response.status_code
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            continue

    return jsonify({"success": False, "detail": f"Error connecting to backend API: {last_err}"}), 500



@candidate_register_bp.route("/register", methods=["GET", "POST"])
def register():
    from app.utils.backend_url import get_backend_base_url
    urls_to_try = [
        f"{current_app.config['BACKEND_API_URL']}/candidate_register/districts",
        f"{get_backend_base_url()}/candidate_register/districts",
        f"{get_backend_base_url()}/api/candidate_register/districts"
    ]
    districts = []
    for backend_url in urls_to_try:
        try:
            response = requests.get(backend_url, timeout=5)
            if response.status_code == 200:
                districts = response.json()
                if districts:
                    break
        except Exception:
            continue
            
    if not districts:
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
            error_msg = str(e).strip()
            if error_msg.startswith('{') or 'field_errors' in error_msg:
                try:
                    parsed = json.loads(error_msg)
                    sub = parsed.get('field_errors', {}) if isinstance(parsed, dict) else {}
                    clean_vals = []
                    for val in sub.values():
                        val_str = str(val).strip()
                        if val_str.startswith("Validation Error:"):
                            val_str = val_str[len("Validation Error:"):].strip()
                        clean_vals.append(val_str)
                    if clean_vals:
                        global_field_errors[file_key] = "<br>".join(clean_vals)
                    else:
                        global_field_errors[file_key] = error_msg
                except Exception:
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
            reg_response = requests.post(register_url, json=payload, timeout=300)
            if reg_response.status_code == 200:
                data = reg_response.json()
                request_code = data["request_code"]
                
                # Move files to proper directory and update DB
                try:
                    import shutil
                    dist_name = "DISTRICT_" + str(district)
                    for d in (districts or []):
                        if isinstance(d, dict) and str(d.get('district_code')) == str(district):
                            dist_name = d.get('district_name') or dist_name
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
                    
                    try:
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
                    except Exception as db_err:
                        print(f"[Candidate Reg] DB direct update warning: {db_err}")
                except Exception as file_err:
                    print(f"[Candidate Reg] File moving warning: {file_err}")
                
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
        except Exception as ex:
            print(f"[Candidate Reg] Registration exception: {ex}")
            err_msg = "Error connecting to backend API server for registration." if isinstance(ex, requests.exceptions.RequestException) else str(ex)
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


# Thread safety & CPU optimization (prevents OpenMP thread thrashing on 4-core VM)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_THREAD_LIMIT"] = "1"

@candidate_register_bp.route("/ocr/extract-id", methods=["POST"])
def ocr_extract_id():
    from flask import jsonify, request, current_app, session
    import re
    import datetime
    import io
    from PIL import Image, ImageEnhance
    import pytesseract

    try:
        from thefuzz import fuzz
    except ImportError:
        import difflib
        class FuzzFallback:
            @staticmethod
            def ratio(a, b):
                return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)
            @staticmethod
            def token_set_ratio(a, b):
                return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)
        fuzz = FuzzFallback()

    file = request.files.get("file")
    doc_type = request.form.get("type") # 'lms' or 'nseit'
    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    try:
        file_bytes = file.read()
        content_type = file.content_type or ""
        filename = file.filename.lower()

        # -------------------------------------------------------------------------
        # 1. ULTRA-FAST MULTI-TIER TEXT EXTRACTION (< 0.01s for PDF, < 0.4s for Images)
        # -------------------------------------------------------------------------
        text_content = ""
        pdf_direct_text = ""
        is_pdf = "pdf" in content_type.lower() or filename.endswith(".pdf") or file_bytes.startswith(b"%PDF")

        # Set Tesseract CMD for Windows manually if not in PATH (on Linux container, default PATH is used)
        tesseract_cmd_path = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if os.path.exists(tesseract_cmd_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path

        if is_pdf:
            try:
                try:
                    import pymupdf as fitz
                except ImportError:
                    import fitz

                doc = fitz.open(stream=file_bytes, filetype="pdf")
                for page in doc:
                    pdf_direct_text += page.get_text() + "\n"

                clean_alpha = re.sub(r'[^a-zA-Z]', '', pdf_direct_text)
                if len(clean_alpha) >= 20:
                    text_content = pdf_direct_text
                elif len(doc) > 0:
                    # Scanned PDF: Render first page at 200 DPI
                    pix = doc[0].get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    
                    max_dim = 2000
                    w, h = img.size
                    if max(w, h) > max_dim:
                        scale = max_dim / float(max(w, h))
                        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

                    img_gray = img.convert('L')
                    enhancer = ImageEnhance.Contrast(img_gray)
                    img_processed = enhancer.enhance(1.4)

                    try:
                        text_content = pytesseract.image_to_string(img_processed, lang='eng', config='--psm 3')
                    except Exception:
                        text_content = ""

                    if not text_content.strip():
                        try:
                            text_content = pytesseract.image_to_string(img_gray, lang='eng', config='--psm 6')
                        except Exception:
                            pass
            except Exception as fe:
                print("PyMuPDF extraction notice, falling back to pdf2image:", fe)
                try:
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
                    images = convert_from_bytes(file_bytes, first_page=1, last_page=1, poppler_path=poppler_path, dpi=200)
                    if images:
                        img_gray = images[0].convert('L')
                        enhancer = ImageEnhance.Contrast(img_gray)
                        img_processed = enhancer.enhance(1.4)
                        text_content = pytesseract.image_to_string(img_processed, lang='eng', config='--psm 3')
                except Exception as pe:
                    print("Poppler fallback notice:", pe)
        else:
            try:
                img = Image.open(io.BytesIO(file_bytes))
                max_dim = 2000
                w, h = img.size
                if max(w, h) > max_dim:
                    scale = max_dim / float(max(w, h))
                    img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

                img_gray = img.convert('L')
                enhancer = ImageEnhance.Contrast(img_gray)
                img_processed = enhancer.enhance(1.4)

                try:
                    text_content = pytesseract.image_to_string(img_processed, lang='eng', config='--psm 3')
                except Exception:
                    text_content = ""

                if not text_content.strip():
                    try:
                        text_content = pytesseract.image_to_string(img_processed, lang='eng', config='--psm 6')
                    except Exception:
                        pass
            except Exception as ie:
                print("Image OCR notice:", ie)

        # Merge direct text and OCR text so no information is lost
        if pdf_direct_text.strip() and pdf_direct_text.strip() not in text_content:
            text_content = pdf_direct_text + "\n" + text_content

        text_upper = text_content.upper()
        despaced_text = re.sub(r'(?<![a-zA-Z0-9])[a-zA-Z0-9](?:\s+[a-zA-Z0-9])+(?![a-zA-Z0-9])', lambda m: re.sub(r'\s+', '', m.group(0)), text_content)
        despaced_upper = despaced_text.upper()
        text_alphanumeric = re.sub(r'[^A-Z0-9]', '', text_upper)
        fn_upper = (filename or '').upper()
        doc_label = "LMS Certificate" if doc_type == "lms" else "NSEIT Certificate"

        sources = [text_upper, despaced_upper, text_alphanumeric, fn_upper]

        def has_phrase(target_phrases):
            for phrase in target_phrases:
                p_upper = phrase.upper()
                p_no_space = re.sub(r'[^A-Z0-9]', '', p_upper)
                if any(p_upper in src for src in [text_upper, despaced_upper, fn_upper]):
                    return True
                if any(p_no_space in src for src in sources):
                    return True
            return False

        print("===== OCR EXTRACTED TEXT =====")
        print(text_content[:300])
        print("==============================")

        # -------------------------------------------------------------------------
        # 2. DOCUMENT AUTHENTICITY VALIDATION (LMS & NSEIT)
        # -------------------------------------------------------------------------
        # Common negative indicators (Bank Passbook, Resident Aadhaar, Academic Marksheet, PAN)
        has_academic = has_phrase([
            "BOARD OF SECONDARY EDUCATION", "CENTRAL BOARD", "CBSE", "ICSE",
            "HIGH SCHOOL CERTIFICATE", "HIGHER SECONDARY CERTIFICATE", "SECONDARY SCHOOL EXAMINATION",
            "MARKSHEET", "MARK SHEET", "STATEMENT OF MARKS", "CERTIFICATE-CUM-MARKSHEET",
            "PROVISIONAL CERTIFICATE", "PROVISIONAL DEGREE", "BACHELOR OF TECHNOLOGY", "BACHELOR OF",
            "MASTER OF", "DIPLOMA IN", "TECHNICAL UNIVERSITY", "SEMESTER EXAMINATION",
            "SUBJECT WISE MARKS", "MARKS OBTAINED", "MAX MARKS", "MIN PASS MARKS", "GRADE CARD"
        ]) or any(k in fn_upper for k in ["MARKSHEET", "CLASS 10", "CLASS 12", "10TH", "12TH", "PROVISIONAL", "DEGREE"])

        has_bank = has_phrase([
            "PASSBOOK", "ACCOUNT NUMBER", "ACCOUNT NO", "SAVINGS BANK", "IFSC CODE", "IFSC :", "IFSC:",
            "BRANCH :", "BRANCH:", "STATEMENT OF ACCOUNT", "CUSTOMER ID", "CIF NO", "CLEARING CHEQUE",
            "STATE BANK OF INDIA", "PUNJAB NATIONAL BANK", "BANK OF BARODA", "HDFC BANK", "ICICI BANK",
            "AXIS BANK", "CANARA BANK", "UNION BANK", "SAVINGS ACCOUNT", "CURRENT ACCOUNT"
        ]) or any(k in fn_upper for k in ["PASSBOOK", "PASS BOOK", "BANK", "STATEMENT"])

        has_pan = has_phrase(["PERMANENT ACCOUNT NUMBER", "INCOME TAX DEPARTMENT", "PAN CARD"]) or "PAN" in fn_upper

        has_cert_markers = has_phrase([
            "CERTIFICATE OF ACCOMPLISHMENT", "OPERATOR ELIGIBILITY", "ELIGIBILITY CERTIFICATE",
            "TESTING AND CERTIFICATION", "TESTING & CERTIFICATION", "DEXIT", "NSEIT"
        ])
        has_aadhaar_resident = (
            has_phrase(["MERA AADHAAR", "AADHAAR - AAM AADMI", "HELP@UIDAI.GOV.IN", "1947", "VID :"])
            or (has_phrase(["MALE", "FEMALE", "GENDER"]) and has_phrase(["ENROLMENT NO", "DOB", "YEAR OF BIRTH"]))
            or (has_phrase(["DOWNLOAD DATE", "ISSUE DATE"]) and has_phrase(["UNIQUE IDENTIFICATION", "UIDAI"]) and not has_cert_markers)
            or any(k in fn_upper for k in ["AADHAR CARD", "AADHAAR CARD", "ADHAR CARD", "AADHAR SCAN", "AADHAAR SCAN"])
        )

        is_invalid_generic = has_academic or has_bank or has_pan or (has_aadhaar_resident and not has_cert_markers)

        if doc_type == "lms":
            # Cross-upload check: NSEIT uploaded in LMS section
            if has_phrase(["AADHAAR OPERATOR ELIGIBILITY", "OPERATOR ELIGIBILITY", "ELIGIBILITY CERTIFICATE", "TESTING AND CERTIFICATION", "TESTING & CERTIFICATION", "DEXIT GLOBAL", "DEX IT", "NSEIT"]):
                return jsonify({
                    "success": False,
                    "error": "Invalid Document: The uploaded file appears to be an NSEIT Certificate. Please upload it in the NSEIT Certificate section below."
                })

            has_lms_title = has_phrase(["CERTIFICATE OF ACCOMPLISHMENT", "ACCOMPLISHMENT", "LEARNING MANAGEMENT SYSTEM", "UIDAI LMS", "LMS"])
            has_lms_topic = has_phrase(["CHILD ENROLMENT LITE CLIENT", "CHILD ENROLMENT", "CELC", "ECMP", "ENROLMENT & UPDATE", "ENROLMENT AND UPDATE", "COMPLETED THE COURSE", "COURSE ON"])

            if is_invalid_generic or not has_lms_title or not has_lms_topic:
                return jsonify({
                    "success": False,
                    "error": "Invalid Document: The uploaded file does not appear to be a valid LMS Certificate of Accomplishment. Please upload your official LMS Certificate."
                })

        elif doc_type == "nseit":
            # Cross-upload check: LMS uploaded in NSEIT section
            if has_phrase(["CERTIFICATE OF ACCOMPLISHMENT", "LEARNING MANAGEMENT SYSTEM", "UIDAI LMS"]) and not has_phrase(["DEXIT", "NSEIT", "OPERATOR ELIGIBILITY"]):
                return jsonify({
                    "success": False,
                    "error": "Invalid Document: The uploaded file appears to be an LMS Certificate. Please upload it in the LMS Certificate section above."
                })

            has_nseit_title = has_phrase(["AADHAAR OPERATOR ELIGIBILITY CERTIFICATE", "OPERATOR ELIGIBILITY CERTIFICATE", "OPERATOR ELIGIBILITY", "ELIGIBILITY CERTIFICATE", "OPERATOR / SUPERVISOR", "OPERATOR/SUPERVISOR", "PASSED THE EXAMINATION", "CERTIFICATE FOR TEST"])
            has_nseit_agency = has_phrase(["NSEIT", "NSE-IT", "NSE.IT", "NSE IT", "DEXIT GLOBAL", "DEX IT GLOBAL", "DEXIT", "DEX-IT", "TESTING AND CERTIFICATION AGENCY", "TESTING & CERTIFICATION AGENCY"])

            if is_invalid_generic or not has_nseit_title or not has_nseit_agency:
                return jsonify({
                    "success": False,
                    "error": "Invalid Document: The uploaded file does not appear to be a valid NSEIT Operator Eligibility Certificate. Please upload your official NSEIT Certificate."
                })

        # -------------------------------------------------------------------------
        # 3. CANDIDATE NAME VERIFICATION (Typo-Tolerant, Restored from 044cdfa)
        # -------------------------------------------------------------------------
        name_input = request.form.get("name")
        if not name_input or not name_input.strip() or name_input.strip().lower() == "none":
            name_input = session.get("candidate_name")

        if name_input and name_input.strip() and name_input.strip().lower() != "none":
            name_upper = name_input.upper().strip()
            score = fuzz.token_set_ratio(name_upper, text_upper)
            
            # Check despaced full name matching if spaced vector fonts were used
            name_no_space = re.sub(r'[^A-Z0-9]', '', name_upper)
            full_name_matched = bool(name_no_space and name_no_space in text_alphanumeric)

            if score < 55 and not full_name_matched:
                score_despaced = fuzz.token_set_ratio(name_upper, despaced_upper)
                if score_despaced < 55:
                    return jsonify({
                        "success": False,
                        "error": f"Name Mismatch: The candidate name '{name_input}' does not match the name found on the uploaded {doc_label}."
                    })

        # -------------------------------------------------------------------------
        # 4. NSEIT EXPIRY DATE CHECK
        # -------------------------------------------------------------------------
        if doc_type == "nseit":
            m_exp = re.search(r'EXPIRY\s*DATE\s*[:\.-]?\s*(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{4})', text_content, re.IGNORECASE)
            if m_exp:
                try:
                    d_val, m_val, y_val = int(m_exp.group(1)), int(m_exp.group(2)), int(m_exp.group(3))
                    exp_date = datetime.date(y_val, m_val, d_val)
                    if exp_date < datetime.date.today():
                        return jsonify({
                            "success": False,
                            "error": f"Uploaded NSEIT Certificate has expired. (Expiry Date: {exp_date.strftime('%d-%m-%Y')}). Please upload a valid certificate."
                        })
                except Exception:
                    pass

        # -------------------------------------------------------------------------
        # 5. ID EXTRACTION & GRACEFUL SAVE (Restored from 044cdfa)
        # -------------------------------------------------------------------------
        extracted_id = None

        if doc_type == "lms":
            match = re.search(r"\bID\s*[:\.-]?\s*([a-zA-Z0-9]{6,16})\b", text_content)
            if match:
                extracted_id = match.group(1)
            else:
                match = re.search(r"\bID\s*[:\.-]?\s*([a-zA-Z0-9]{6,16})\b", despaced_text)
                if match:
                    extracted_id = match.group(1)
                else:
                    match = re.search(r"\bLMS\s*[-_]?\s*([a-zA-Z0-9]{4,16})\b", text_content, re.IGNORECASE)
                    if match:
                        extracted_id = match.group(0)
        elif doc_type == "nseit":
            match = re.search(r"Certificate\s+No[s\.]*\s*[:\.-]?\s*([a-zA-Z0-9_-]{4,18})", text_content, re.IGNORECASE)
            if match:
                extracted_id = match.group(1)
            else:
                match = re.search(r"Certificate\s+No[s\.]*\s*[:\.-]?\s*([a-zA-Z0-9_-]{4,18})", despaced_text, re.IGNORECASE)
                if match:
                    extracted_id = match.group(1)
                else:
                    match = re.search(r"\b(NS[0-9]{6,10})\b", despaced_text, re.IGNORECASE)
                    if match:
                        extracted_id = match.group(1)
                    else:
                        match = re.search(r"\b((?:NSEIT|DEXIT)[-_]?[0-9]{4,16})\b", despaced_text, re.IGNORECASE)
                        if match:
                            extracted_id = match.group(1)
                        else:
                            match = re.search(r"(NS[0-9]{6,10})", text_alphanumeric)
                            if match:
                                extracted_id = match.group(1)

        saved_path = None
        try:
            upload_folder = os.path.join(current_app.root_path, "..", "uploads", "temp")
            file.seek(0)
            saved_path = save_upload(file, upload_folder)
        except Exception as se:
            print("Error saving temp cert file:", se)

        if extracted_id:
            clean_id = re.sub(r'[^a-zA-Z0-9_\/-]', '', extracted_id).strip()
            return jsonify({
                "success": True,
                "id": clean_id,
                "file_path": saved_path if saved_path != "TOO_LARGE" else None
            })
        else:
            return jsonify({
                "success": True,
                "id": "",
                "file_path": saved_path if saved_path != "TOO_LARGE" else None,
                "warning": "Certificate verified. Could not auto-read ID - please verify or enter your ID manually."
            })

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
    from flask import jsonify, request, current_app
    import io
    import os
    import re
    import json
    from backend.utils.ocr_utils import validate_marksheet, extract_text_from_bytes

    file = request.files.get("file")
    doc_type = request.form.get("type") # 'tenth' or 'highest'
    name = request.form.get("name")
    dob = request.form.get("dob")
    qualification = request.form.get("qualification", "High School (10th)")

    if not file or not file.filename:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    # 1. ALWAYS save the uploaded file FIRST so the candidate's document is safely stored regardless of OCR result
    saved_path = None
    file_bytes = b""
    upload_folder = os.path.join(current_app.root_path, "..", "uploads", "temp")
    try:
        saved_path = save_upload(file, upload_folder)
        file.seek(0)
        file_bytes = file.read()
    except Exception as se:
        print("Error saving temp marksheet file:", se)

    if saved_path == "TOO_LARGE":
        return jsonify({"success": False, "error": "File size exceeds 1 MB limit."}), 400

    if not saved_path:
        return jsonify({"success": False, "error": "Failed to save uploaded file."}), 500

    # 2. Attempt OCR validation
    try:
        text_content = extract_text_from_bytes(file_bytes, file.content_type, lang="eng+hin")

        # Write debug logs safely
        try:
            with open(os.path.join(upload_folder, "debug_ocr_marksheet.txt"), "w", encoding="utf-8") as f:
                f.write(text_content)
        except Exception:
            pass

        # Enforce validation for all qualifications
        try:
            validate_marksheet(text_content, name, dob, qualification, filename=file.filename)
            return jsonify({"success": True, "file_path": saved_path})
        except ValueError as ve:
            err_msg = str(ve)
            if err_msg.startswith("Validation Error:"):
                err_msg = err_msg[len("Validation Error:"):].strip()
            try:
                err_json = json.loads(err_msg)
                if "field_errors" in err_json:
                    fe = err_json["field_errors"]
                    clean_errs = []
                    for k, v in fe.items():
                        v_str = str(v).strip()
                        if v_str.startswith("Validation Error:"):
                            v_str = v_str[len("Validation Error:"):].strip()
                        clean_errs.append(v_str)
                    err_text = " | ".join(clean_errs)
                    return jsonify({"success": False, "error": err_text, "field_errors": fe}), 400
            except Exception:
                pass
            return jsonify({"success": False, "error": err_msg}), 400

    except Exception as e:
        print("Marksheet OCR handler exception:", e)
        return jsonify({"success": False, "error": f"OCR processing failed: {str(e)}"}), 400


