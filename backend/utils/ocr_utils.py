import io
import re
from datetime import datetime
from fastapi import UploadFile, HTTPException
import pandas as pd
import pytesseract
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from pdf2image import convert_from_bytes
from thefuzz import fuzz
import os
import openpyxl
import pymupdf as fitz  # PyMuPDF

# Thread safety & CPU optimization (prevents OpenMP thread thrashing on 4-core VM)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_THREAD_LIMIT"] = "1"

# Set Tesseract CMD for Windows manually if not in PATH (on Linux container, default in PATH is used)
tesseract_cmd_path = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(tesseract_cmd_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path

def _do_ocr(image: Image.Image, lang: str = "eng") -> str:
    """Ultra-fast, adaptive single/multi-pass OCR with smart resolution control."""
    try:
        # 1. Downscale oversized images only if massive (> 2500px) to preserve memory & speed
        max_dim = 2500
        w, h = image.size
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            new_w, new_h = int(w * scale), int(h * scale)
            image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)

        # 2. Pass 1 (PSM 3 - Fully automatic layout)
        t1 = ""
        try:
            t1 = pytesseract.image_to_string(image, lang=lang, config='--psm 3 --oem 1')
        except Exception:
            t1 = ""

        # 3. Pass 2 (PSM 6 - Uniform block of text) to capture dense single-block ID cards / PAN cards
        t2 = ""
        try:
            t2 = pytesseract.image_to_string(image, lang=lang, config='--psm 6 --oem 1')
        except Exception:
            pass

        # 4. Pass 3 (PSM 6 on Sharpened Grayscale) to recover dot-matrix fonts on patterned security backgrounds
        t3 = ""
        try:
            gray = ImageOps.autocontrast(image.convert('L'), cutoff=1)
            sharp_gray = gray.filter(ImageFilter.SHARPEN)
            t3 = pytesseract.image_to_string(sharp_gray, lang=lang, config='--psm 6 --oem 1')
        except Exception:
            pass

        results = [t for t in [t1.strip(), t2.strip(), t3.strip()] if t]
        return "\n".join(results)
    except Exception as err:
        print(f"OCR Error: {err}")
        return ""

def _is_valid_digital_text(text: str) -> bool:
    """Checks if extracted digital PDF text is meaningful (not garbled CID fonts or empty metadata)."""
    if not text or len(text.strip()) < 35:
        return False
    # Check for excessive unmapped CID font tokens
    cid_count = text.count("(cid:")
    if cid_count > 3:
        return False
    # Check for at least 3 alphabetical words of length >= 3
    words = [w for w in re.findall(r'[a-zA-Z]{3,}', text)]
    return len(words) >= 3

def extract_text_from_bytes(file_bytes: bytes, content_type: str, lang: str = "eng") -> str:
    """Extracts text directly from bytes (PDF or Image) with instant digital bypass & high-speed rasterization."""
    try:
        is_pdf = False
        if content_type:
            is_pdf = content_type.lower() == "application/pdf"
        if not is_pdf and file_bytes:
            is_pdf = file_bytes.startswith(b"%PDF")

        if is_pdf:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            # Tier 1: Direct digital text extraction (Instant: < 0.01s)
            pdf_direct_text = ""
            try:
                for page in doc:
                    pdf_direct_text += page.get_text() + "\n"
            except Exception as fitz_err:
                print(f"PyMuPDF direct extraction notice: {fitz_err}")

            # If digital text is valid & rich, return immediately without heavy rasterization
            if _is_valid_digital_text(pdf_direct_text):
                return pdf_direct_text.upper()

            # Tier 2: Scanned PDF - Extract embedded raw image (Fast & distortion-free) or rasterize
            raster_texts = []
            try:
                max_pages = min(len(doc), 2)
                for page_idx in range(max_pages):
                    page = doc[page_idx]
                    page_text = ""
                    
                    # 2A. Check for raw embedded image inside the PDF page
                    page_imgs = page.get_images()
                    if page_imgs:
                        for img_info in page_imgs[:2]:
                            try:
                                xref = img_info[0]
                                base_image = doc.extract_image(xref)
                                if base_image and "image" in base_image:
                                    raw_img = Image.open(io.BytesIO(base_image["image"]))
                                    raw_text = _do_ocr(raw_img, lang=lang)
                                    if raw_text.strip():
                                        page_text += ("\n" + raw_text) if page_text else raw_text
                            except Exception:
                                pass

                    # 2B. If no embedded images or low text, rasterize page at 300 DPI
                    if len(page_text.strip()) < 25:
                        pix = page.get_pixmap(dpi=300, alpha=False)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        rendered_text = _do_ocr(img, lang=lang)
                        if rendered_text.strip():
                            page_text += ("\n" + rendered_text) if page_text else rendered_text

                    if page_text.strip():
                        raster_texts.append(page_text)
            except Exception as fitz_pix_err:
                print(f"PyMuPDF in-memory render fallback: {fitz_pix_err}")

            # Combine direct text (if any) and raster text
            parts = []
            if pdf_direct_text.strip():
                parts.append(pdf_direct_text.strip())
            if raster_texts:
                parts.append("\n".join(raster_texts))

            extracted_text = "\n".join(parts)

            # Tier 3: Poppler fallback only if PyMuPDF failed to extract text
            if not extracted_text.strip():
                poppler_path = os.getenv("POPPLER_PATH")
                if not poppler_path:
                    common_poppler = [
                        r"C:\poppler-26.02.0\Library\bin",
                        r"C:\Program Files\poppler-26.02.0\Library\bin",
                        r"C:\poppler\Library\bin", 
                        r"C:\Release-24.02.0-0\poppler-24.02.0\Library\bin",
                        r"C:\Program Files (x86)\Windows Media Player\Release-26.02.0-0\poppler-26.02.0\Library\bin"
                    ]
                    for p in common_poppler:
                        if os.path.exists(p):
                            poppler_path = p
                            break
                
                try:
                    images = convert_from_bytes(file_bytes, first_page=1, last_page=1, poppler_path=poppler_path, dpi=200, timeout=10)
                    if images:
                        extracted_text = "\n".join(_do_ocr(img, lang=lang) for img in images)
                except Exception as poppler_err:
                    print(f"Poppler conversion error: {poppler_err}")
        else:
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text = _do_ocr(image, lang=lang)

        return extracted_text.upper()
    except Exception as e:
        print(f"OCR Extraction Error: {e}")
        return ""

def extract_text_from_file(upload_file: UploadFile) -> str:
    """Legacy wrapper for FastAPI routes."""
    try:
        file_bytes = upload_file.file.read()
        return extract_text_from_bytes(file_bytes, upload_file.content_type)
    finally:
        upload_file.file.seek(0)

def _normalize_ocr_digits(text_upper: str) -> str:
    """Normalizes OCR character confusions for numeric strings (O->0, I/l/|->1, S->5, B->8, Z->2)."""
    text = re.sub(r'(?<=\d)[O](?=\d)|(?<=[X*])[O](?=\d)|(?<=\d)[O](?=\b)|(?<=\b)[O](?=\d)', '0', text_upper)
    text = re.sub(r'(?<=\d)[IL|](?=\d)|(?<=[X*])[IL|](?=\d)|(?<=\d)[IL|](?=\b)|(?<=\b)[IL|](?=\d)', '1', text)
    text = re.sub(r'(?<=\d)[S](?=\d)|(?<=[X*])[S](?=\d)|(?<=\d)[S](?=\b)', '5', text)
    text = re.sub(r'(?<=\d)[B](?=\d)|(?<=[X*])[B](?=\d)|(?<=\d)[B](?=\b)', '8', text)
    text = re.sub(r'(?<=\d)[Z](?=\d)|(?<=[X*])[Z](?=\d)|(?<=\d)[Z](?=\b)', '2', text)
    return text

def _match_operator_name(operator_name: str, text_upper: str) -> bool:
    """Strict and resilient operator name matcher ensuring accurate spelling matching against document OCR text."""
    if not operator_name or not operator_name.strip():
        return True

    clean_op_name = re.sub(r'[^A-Z\s]', ' ', operator_name.upper()).strip()
    name_tokens = [w for w in clean_op_name.split() if len(w) >= 2]
    if not name_tokens:
        return True

    # 1. Prepare normalized and despaced text representations
    # Fix common OCR letter-digit confusions in text (e.g. PR1YANSHU -> PRIYANSHU, 5UMIT -> SUMIT, AAYU5H -> AAYUSH)
    char_map = str.maketrans({'1': 'I', '0': 'O', '5': 'S', '8': 'B', '2': 'Z', '|': 'I', '/': ' ', '!': 'I', '$': 'S'})
    text_normalized = text_upper.translate(char_map)
    text_u_map = text_normalized.replace('V', 'U')
    text_y_map = text_normalized.replace('V', 'Y')

    # Multi-line single letter / segmented syllable despacer (handles PDF vertical letter streams)
    text_no_newlines = re.sub(r'\s*\n\s*', ' ', text_normalized)
    despaced_all = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(' ', ''), text_no_newlines)

    lines = [line.strip() for line in text_normalized.splitlines() if line.strip()]
    despaced_lines = [
        re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), line)
        for line in lines
    ]
    despaced_text = "\n".join(despaced_lines)
    all_text_sources = [text_upper, text_normalized, text_u_map, text_y_map, despaced_text, text_no_newlines, despaced_all]
    text_no_space = re.sub(r'[^A-Z]', '', text_normalized)
    text_no_space_u = re.sub(r'[^A-Z]', '', text_u_map)
    text_no_space_raw = re.sub(r'[^A-Z]', '', text_upper)
    all_no_space = [text_no_space, text_no_space_u, text_no_space_raw]

    # 2. Check full name phrase match on word boundaries
    full_name_regex = r'\b' + r'\s+'.join(re.escape(tok) for tok in name_tokens) + r'\b'
    for src in all_text_sources:
        if re.search(full_name_regex, src):
            return True

    # 3. Extract all distinct words in the document across all sources
    raw_words = []
    for src in all_text_sources:
        raw_words.extend(re.findall(r'[A-Z]{2,}', src))
    doc_words = set(raw_words)

    # 4. Token-by-token matching
    matched_tokens = 0
    for n_tok in name_tokens:
        tok_len = len(n_tok)
        tok_matched = False

        # 1. Exact match in doc_words
        if n_tok in doc_words:
            matched_tokens += 1
            continue

        # 2. Word boundary match in any source
        tok_boundary_regex = r'\b' + re.escape(n_tok) + r'\b'
        if any(re.search(tok_boundary_regex, src) for src in all_text_sources):
            matched_tokens += 1
            continue

        # 3. Exact token in continuous character stream (handles concatenation without spaces)
        if any(n_tok in ns for ns in all_no_space):
            is_truncated_var = any(
                len(w) == tok_len + 1 and n_tok in w
                for w in doc_words
            )
            if not is_truncated_var:
                matched_tokens += 1
                continue

        # 4. OCR fuzzy match against doc words with flexible length tolerance (+-2 chars)
        found_ocr_fuzzy = False
        for w in doc_words:
            if abs(len(w) - tok_len) <= 2 and tok_len >= 4:
                if fuzz.ratio(n_tok, w) >= 75 or (tok_len >= 5 and fuzz.partial_ratio(n_tok, w) >= 80):
                    found_ocr_fuzzy = True
                    break
        if found_ocr_fuzzy:
            matched_tokens += 1
            continue

        # 5. Sliding window match on compact character streams (<= 800 chars, e.g. PAN cards & ID cards)
        found_window_fuzzy = False
        if tok_len >= 4:
            for ns in all_no_space:
                if len(ns) <= 800:
                    for win_len in [tok_len, tok_len + 1, tok_len - 1]:
                        if win_len > len(ns):
                            continue
                        for i in range(len(ns) - win_len + 1):
                            window = ns[i:i+win_len]
                            if fuzz.ratio(n_tok, window) >= 80:
                                found_window_fuzzy = True
                                break
                        if found_window_fuzzy:
                            break
                if found_window_fuzzy:
                    break
        if found_window_fuzzy:
            matched_tokens += 1
            continue

    # Evaluation
    if len(name_tokens) == 1:
        return matched_tokens >= 1
    elif len(name_tokens) == 2:
        return matched_tokens == 2 or (matched_tokens >= 1 and any(n_tok in doc_words for n_tok in name_tokens))
    return matched_tokens >= min(2, len(name_tokens) - 1)

def validate_aadhaar(extracted_text: str, operator_name: str, operator_aadhaar: str = None) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: No readable text detected. Please upload a clear Aadhaar Card image or PDF."

    text_upper = extracted_text.upper()

    # -------------------------------------------------------------
    # 1. DISQUALIFY OTHER DOCUMENTS UPLOADED IN AADHAAR FIELD
    # -------------------------------------------------------------
    # A. NSEIT Certificate check
    nseit_indicators = [
        "OPERATOR ELIGIBILITY CERTIFICATE", "ELIGIBILITY CERTIFICATE", "NSEIT", "NSE-IT", "NSE.IT",
        "DEXIT", "TESTING AND CERTIFICATION", "TESTING & CERTIFICATION", "PASSED THE EXAMINATION",
        "CERTIFICATE NO: NS", "CERTIFICATE NO : NS", "CERTIFICATE NO:NS", "LANGUAGE PROFICIENCY"
    ]
    if any(k in text_upper for k in nseit_indicators):
        return "Validation Error: The uploaded document is not a recognized Aadhaar Card."

    # B. LMS Certificate check
    lms_indicators = [
        "CERTIFICATE OF ACCOMPLISHMENT", "ENROLMENT & UPDATE PROCESS", "COURSE ON",
        "SUCCESSFULLY COMPLETED THE COURSE"
    ]
    if any(k in text_upper for k in lms_indicators):
        return "Validation Error: The uploaded document is not a recognized Aadhaar Card."

    # C. Bank Passbook check
    clean_for_bank = text_upper.replace("PERMANENT ACCOUNT NUMBER", "").replace("PERMANENT ACCOUNT", "").replace("PERMANENT", "")
    bank_indicators = [
        "PASSBOOK", "SAVINGS A/C", "SAVINGS ACCOUNT", "CURRENT ACCOUNT",
        "A/C NO", "AC NO", "IFSC CODE", "IFSC:", "IFSC :", "MICR CODE", "MICR:", "CIF NO", "CIF NUMBER",
        "AVAILABLE BALANCE", "STATEMENT OF ACCOUNT", "BANK PASSBOOK", "ACCOUNT STATEMENT",
        "STATE BANK OF INDIA", "PUNJAB NATIONAL BANK", "BANK OF BARODA", "CANARA BANK",
        "UNION BANK OF INDIA", "HDFC BANK", "ICICI BANK", "AXIS BANK", "KOTAK MAHINDRA",
        "CHHATTISGARH RAJYA GRAMIN", "खाता संख्या", "पासबुक", "बचत खाता"
    ]
    if any(k in clean_for_bank for k in bank_indicators):
        return "Validation Error: The uploaded document is not a recognized Aadhaar Card."

    # D. PAN Card check
    pan_indicators = ["PERMANENT ACCOUNT NUMBER", "INCOME TAX DEPARTMENT", "आयकर विभाग"]
    if any(k in text_upper for k in pan_indicators):
        return "Validation Error: The uploaded document is not a recognized Aadhaar Card."

    # E. Marksheet check
    ms_indicators = [
        "BOARD OF SECONDARY", "CENTRAL BOARD OF SECONDARY", "SECONDARY SCHOOL EXAMINATION",
        "HIGHER SECONDARY", "MARKS STATEMENT", "STATEMENT OF MARKS", "REPORT CARD",
        "CUM CERTIFICATE", "HIGH SCHOOL CERTIFICATE"
    ]
    if any(k in text_upper for k in ms_indicators):
        return "Validation Error: The uploaded document is not a recognized Aadhaar Card."

    # -------------------------------------------------------------
    # 2. STRICT AADHAAR CARD ALLOWLIST & STRUCTURE VERIFICATION
    # -------------------------------------------------------------
    exclusive_aadhaar_markers = [
        "MERA AADHAAR", "MY AADHAAR", "MERA AADHAR", "MY AADHAR",
        "MERA AADHAAR, MERI PEHCHAN", "MERA AADHAR, MERI PEHCHAN", "MERA AADHAR MERI PEHCHAN",
        "MERA AADHAAR MERI PEHCHAN", "MERI PEHCHAN", "मेरा आधार, मेरी पहचान", "मेरा आधार मेरी पहचान",
        "YOUR AADHAAR NO", "YOUR AADHAAR NUMBER", "YOUR AADHAR NO", "YOUR AADHAR NUMBER",
        "आपका आधार क्रमांक", "आपका आधार", "आधार - आम आदमी का अधिकार", "आम आदमी का अधिकार",
        "HELP@UIDAI", "UIDAI.GOV.IN", "WWW.UIDAI.GOV.IN", "@UIDAI",
        "ENROLMENT NO", "ENROLMENT ID", "नामांकन संख्या", "VIRTUAL ID :", "VID :", "1947"
    ]
    has_exclusive_aadhaar = any(kw in text_upper for kw in exclusive_aadhaar_markers)

    despaced_text = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), text_upper)
    has_aadhaar_header = any(kw in text_upper or kw in despaced_text for kw in [
        "AADHAAR", "AADHAR", "आधार", "A A D H A A R", "A A D H A R"
    ])
    has_gov_authority = any(kw in text_upper for kw in [
        "GOVERNMENT OF INDIA", "GOVT OF INDIA", "GOVT. OF INDIA", "GOVT.OF INDIA", "GOVT OFINDIA", "भारत सरकार",
        "UNIQUE IDENTIFICATION AUTHORITY OF INDIA", "UNIQUE IDENTIFICATION AUTHORITY", "UNIQUE IDENTIFICATION", "भारतीय विशिष्ट पहचान"
    ]) or fuzz.partial_ratio("GOVERNMENT OF INDIA", text_upper) >= 80

    has_demographic_fields = any(kw in text_upper for kw in [
        "MALE", "FEMALE", "पुरुष", "महिला", "YEAR OF BIRTH", "DATE OF BIRTH", "DOB", "जन्म तिथि", "जन्म वर्ष",
        "ISSUE DATE", "PRINT DATE", "S/O", "D/O", "W/O", "C/O", "आत्मज", "आत्मजा", "पता:", "ADDRESS"
    ])
    has_aadhaar_num_format = bool(re.search(r'\b(?:\d{4}|[X*]{4})[ -]?(?:\d{4}|[X*]{4})[ -]?\d{4}\b', text_upper))

    is_authentic_aadhaar = has_exclusive_aadhaar or (
        has_aadhaar_header and (
            has_gov_authority or
            (has_demographic_fields and has_aadhaar_num_format)
        )
    ) or (has_gov_authority and (has_demographic_fields or has_aadhaar_num_format))

    if not is_authentic_aadhaar:
        return "Validation Error: The uploaded document is not a recognized Aadhaar Card."

    # 3. Validate Aadhaar Number (Last 4 digits check)
    if operator_aadhaar:
        clean_aadhaar = "".join(filter(str.isdigit, str(operator_aadhaar)))
        if clean_aadhaar:
            target_last4 = clean_aadhaar[-4:] if len(clean_aadhaar) >= 4 else clean_aadhaar
            normalized_ocr = _normalize_ocr_digits(text_upper)
            despaced_ocr = _normalize_ocr_digits(despaced_text)
            found_last4 = False

            # Check 1: 12-digit formatted Aadhaar numbers (e.g. 5299 5069 5754 or 5299-5069-5754)
            for src in [normalized_ocr, despaced_ocr]:
                if found_last4:
                    break
                aadhaar_12_matches = re.findall(r'\b(\d{4})[ -]?(\d{4})[ -]?(\d{4})\b', src)
                for g1, g2, g3 in aadhaar_12_matches:
                    if g3 == target_last4:
                        found_last4 = True
                        break

            # Check 2: Masked Aadhaar numbers (e.g. XXXX XXXX 5754 or ********5754)
            if not found_last4:
                for src in [normalized_ocr, despaced_ocr]:
                    masked_matches = re.findall(r'(?:[X*]{4}[ -]?[X*]{4}|[X*]{8})[ -]?(\d{4})\b', src)
                    for m_digits in masked_matches:
                        if m_digits == target_last4:
                            found_last4 = True
                            break

            # Check 3: Aadhaar keyword anchor (e.g. AADHAAR / आधार ... 5754)
            if not found_last4:
                kw_pattern = r'(?:AADHAAR|AADHAR|आधार|YOUR AADHAAR|MY AADHAAR|VID)[^\d\n\r]{0,30}(?:[X*0-9\s\-]{4,16})?(\d{4})\b'
                for m in re.finditer(kw_pattern, normalized_ocr, re.IGNORECASE):
                    if m.group(1) == target_last4:
                        found_last4 = True
                        break

            # Check 4: Continuous 12-digit number block
            if not found_last4:
                all_12_blocks = re.findall(r'\b\d{12}\b', normalized_ocr)
                for b in all_12_blocks:
                    if b.endswith(target_last4):
                        found_last4 = True
                        break

            # Check 5: Standalone 4-digit token adjacent to Aadhaar number prefix/masked block
            if not found_last4:
                if re.search(r'(?:[X*]{4}[ -]?|\b\d{4}[ -]\d{4}[ -])' + re.escape(target_last4) + r'\b', normalized_ocr):
                    found_last4 = True

            # Check 6: Digits sequence check
            if not found_last4:
                digits_only = re.sub(r'\D', '', text_upper)
                if len(digits_only) >= 12:
                    for i in range(len(digits_only) - 11):
                        if digits_only[i:i+12].endswith(target_last4):
                            found_last4 = True
                            break

            if not found_last4:
                return f"Validation Error: The Aadhaar number ending in '{target_last4}' was not found on the uploaded document."

    # 4. Validate Operator Name
    if operator_name and not _match_operator_name(operator_name, text_upper):
        return f"Validation Error: The name on the Aadhaar document does not match the Operator's name '{operator_name}'."

    return None

def _normalize_pan_candidate(token: str) -> str:
    """Normalizes OCR character confusions for a 10-character PAN token."""
    if len(token) != 10:
        return token
    char_to_letter = {'0': 'O', '1': 'I', '5': 'S', '8': 'B', '2': 'Z', '6': 'G'}
    char_to_digit = {'O': '0', 'I': '1', 'L': '1', 'S': '5', 'B': '8', 'Z': '2', 'G': '6', 'D': '0', 'Q': '0'}

    result = []
    for i, c in enumerate(token):
        if i < 5 or i == 9:
            result.append(char_to_letter.get(c, c))
        else:
            result.append(char_to_digit.get(c, c))
    return "".join(result)

def validate_pan(extracted_text: str, operator_name: str, operator_pan: str = None) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: No readable text detected. Please upload a clear PAN Card image or PDF."

    text_upper = extracted_text.upper()
    char_map = str.maketrans({'1': 'I', '0': 'O', '5': 'S', '8': 'B', '2': 'Z', '|': 'I', '/': ' '})
    text_normalized = text_upper.translate(char_map)
    despaced_text = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), text_upper)
    text_no_newlines = re.sub(r'\s*\n\s*', ' ', text_normalized)
    despaced_all = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(' ', ''), text_no_newlines)
    text_no_space = "".join(c for c in text_upper if c.isalnum())
    all_text_sources = [text_upper, text_normalized, despaced_text, text_no_newlines, despaced_all]

    # 1. Check if the operator's specific PAN number is found in the document
    matched_pan = False
    clean_pan = ""
    if operator_pan:
        clean_pan = "".join(c for c in operator_pan.upper().strip() if c.isalnum())
        if clean_pan and len(clean_pan) == 10:
            if clean_pan in text_no_space:
                matched_pan = True

            if not matched_pan:
                raw_tokens = re.findall(r'[A-Z0-9]{10}', text_no_space)
                for tok in raw_tokens:
                    norm_tok = _normalize_pan_candidate(tok)
                    if norm_tok == clean_pan or fuzz.ratio(clean_pan, norm_tok) >= 80:
                        matched_pan = True
                        break

            if not matched_pan:
                for i in range(max(0, len(text_no_space) - 9)):
                    window = text_no_space[i:i+10]
                    norm_win = _normalize_pan_candidate(window)
                    if norm_win == clean_pan or fuzz.ratio(clean_pan, norm_win) >= 80:
                        matched_pan = True
                        break

            if not matched_pan:
                raw_words = re.findall(r'[A-Z0-9]{8,12}', text_upper)
                for w in raw_words:
                    clean_w = "".join(c for c in w if c.isalnum())
                    if fuzz.ratio(clean_pan, clean_w) >= 75 or fuzz.ratio(clean_pan, _normalize_pan_candidate(clean_w[:10])) >= 75:
                        matched_pan = True
                        break

    # 2. Comprehensive Positive PAN Card Identifiers (Allowlist)
    pan_keywords = [
        "INCOME TAX DEPARTMENT", "INCOMETAX DEPARTMENT", "INCOME TAX DEPT", "INCOME TAX",
        "INCOMETAX", "INCOME-TAX", "TAX DEPARTMENT", "PERMANENT ACCOUNT NUMBER", "PERMANENT ACCOUNT",
        "ACCOUNT NUMBER CARD", "PERMANENT ACCOUNT NUMBER CARD", "PAN CARD", "PAN NO", "PAN NUMBER",
        "आयकर विभाग", "स्थायी खाता संख्या", "स्थायी लेखा संख्या", "आयकर", "आयकर आयुक्त",
        "NATIONAL SECURITIES DEPOSITORY", "NSDL", "UTIITSL", "UTI-ITSL", "UTI INFRASTRUCTURE",
        "PROTEAN", "E-PAN", "EPAN"
    ]
    has_pan_primary = any(kw in src for src in all_text_sources for kw in pan_keywords)

    # Check government identity combination + strict PAN pattern [A-Z]{5}[0-9]{4}[A-Z]
    has_gov_markers = any(kw in text_upper for kw in ["GOVERNMENT OF INDIA", "GOVT OF INDIA", "GOVT. OF INDIA", "GOVT.OF INDIA", "भारत सरकार"])
    has_pan_fields = any(kw in text_upper for kw in ["FATHER", "DATE OF BIRTH", "DOB", "SIGNATURE", "PERMANENT ACCOUNT"])
    has_pan_structure = bool(
        re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text_upper) or
        re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', despaced_text) or
        re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', despaced_all) or
        re.search(r'[A-Z]{5}[0-9]{4}[A-Z]', text_no_space)
    )

    # Check for clear banking passbook indicators to prevent passbooks from being treated as PAN cards
    has_banking_markers = any(kw in text_upper for kw in [
        "PASSBOOK", "SAVINGS ACCOUNT", "CURRENT ACCOUNT", "IFSC", "MICR", "CIF NO", "CIF NUMBER",
        "STATEMENT OF ACCOUNT", "BANK OF BARODA", "STATE BANK", "PUNJAB NATIONAL", "CANARA BANK",
        "UNION BANK", "INDIAN BANK", "CENTRAL BANK", "HDFC", "ICICI", "AXIS BANK", "KOTAK BANK"
    ])

    has_pan_kw = (has_pan_primary or matched_pan or (has_gov_markers and (has_pan_structure or has_pan_fields))) and not (has_banking_markers and not has_pan_primary and not matched_pan)

    if not has_pan_kw:
        return "Validation Error: The uploaded document is not a recognized PAN Card."

    # 3. Validate PAN Number for valid PAN Card documents
    if clean_pan and not matched_pan:
        return f"Validation Error: The PAN number '{clean_pan}' was not found in the uploaded document."

    # 4. Validate Operator Name on PAN Card if provided
    if operator_name and not _match_operator_name(operator_name, text_upper):
        return f"Validation Error: The name on the PAN Card does not match the Operator's name '{operator_name}'."

    return None

def get_year_in_words(year: int) -> list[str]:
    ones = ["", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]
    teens = ["TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN"]
    tens = ["", "", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"]
    
    if 1900 <= year < 2000:
        rem = year - 1900
        suffix = teens[rem - 10] if 10 <= rem < 20 else f"{tens[rem // 10]} {ones[rem % 10]}".strip()
        suffix_alt = suffix.replace(" ", "-")
        return [
            f"NINETEEN {suffix}", f"NINETEEN {suffix_alt}",
            f"NINETEEN HUNDRED {suffix}", f"NINETEEN HUNDRED {suffix_alt}",
            f"ONE THOUSAND NINE HUNDRED {suffix}", f"ONE THOUSAND NINE HUNDRED {suffix_alt}"
        ]
    elif 2000 <= year < 2030:
        rem = year - 2000
        suffix = teens[rem - 10] if 10 <= rem < 20 else f"{tens[rem // 10]} {ones[rem % 10]}".strip()
        suffix_alt = suffix.replace(" ", "-")
        return [
            f"TWO THOUSAND {suffix}".strip(), f"TWO THOUSAND {suffix_alt}".strip(),
            f"TWO THOUSAND AND {suffix}".strip(), f"TWO THOUSAND AND {suffix_alt}".strip()
        ]
    return []

def get_month_in_words(month: int) -> list[str]:
    months = ["", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
    return [months[month]]

def get_day_in_words(day: int) -> list[str]:
    DAYS_IN_WORDS = {
        1: ["FIRST", "ONE", "1ST", "01ST", "1", "01"],
        2: ["SECOND", "TWO", "2ND", "02ND", "2", "02"],
        3: ["THIRD", "THREE", "3RD", "03RD", "3", "03"],
        4: ["FOURTH", "FOUR", "4TH", "04TH", "4", "04"],
        5: ["FIFTH", "FIVE", "5TH", "05TH", "5", "05"],
        6: ["SIXTH", "SIX", "6TH", "06TH", "6", "06"],
        7: ["SEVENTH", "SEVEN", "7TH", "07TH", "7", "07"],
        8: ["EIGHTH", "EIGHT", "8TH", "08TH", "8", "08"],
        9: ["NINTH", "NINE", "9TH", "09TH", "9", "09"],
        10: ["TENTH", "TEN", "10TH", "10"],
        11: ["ELEVENTH", "ELEVEN", "11TH", "11"],
        12: ["TWELFTH", "TWELVE", "12TH", "12"],
        13: ["THIRTEENTH", "THIRTEEN", "13TH", "13"],
        14: ["FOURTEENTH", "FOURTEEN", "14TH", "14"],
        15: ["FIFTEENTH", "FIFTEEN", "15TH", "15"],
        16: ["SIXTEENTH", "SIXTEEN", "16TH", "16"],
        17: ["SEVENTEENTH", "SEVENTEEN", "17TH", "17"],
        18: ["EIGHTEENTH", "EIGHTEEN", "18TH", "18"],
        19: ["NINETEENTH", "NINETEEN", "19TH", "19"],
        20: ["TWENTIETH", "TWENTY", "20TH", "20"],
        21: ["TWENTY FIRST", "TWENTY-FIRST", "TWENTY ONE", "21ST", "21"],
        22: ["TWENTY SECOND", "TWENTY-SECOND", "TWENTY TWO", "22ND", "22"],
        23: ["TWENTY THIRD", "TWENTY-THIRD", "TWENTY THREE", "23RD", "23"],
        24: ["TWENTY FOURTH", "TWENTY-FOURTH", "TWENTY FOUR", "24TH", "24"],
        25: ["TWENTY FIFTH", "TWENTY-FIFTH", "TWENTY FIVE", "25TH", "25"],
        26: ["TWENTY SIXTH", "TWENTY-SIXTH", "TWENTY SIX", "26TH", "26"],
        27: ["TWENTY SEVENTH", "TWENTY-SEVENTH", "TWENTY SEVEN", "27TH", "27"],
        28: ["TWENTY EIGHTH", "TWENTY-EIGHTH", "TWENTY EIGHT", "28TH", "28"],
        29: ["TWENTY NINTH", "TWENTY-NINTH", "TWENTY NINE", "29TH", "29"],
        30: ["THIRTIETH", "THIRTY", "30TH", "30"],
        31: ["THIRTY FIRST", "THIRTY-FIRST", "THIRTY ONE", "31ST", "31"]
    }
    return DAYS_IN_WORDS.get(day, [])

def validate_marksheet(extracted_text: str, candidate_name: str, candidate_dob: str, qualification: str = "High School (10th)", filename: str = "") -> None:
    """Validates if the text looks like a marksheet, and matches name and DOB."""
    if not extracted_text or len(extracted_text.strip()) < 10:
        raise ValueError("Validation Error: Could not extract readable text from the uploaded document. Please upload a clear image or PDF.")

    errors = {}
    text_upper = extracted_text.upper()
    despaced_text = re.sub(r'(?<![a-zA-Z0-9])[a-zA-Z0-9](?:\s+[a-zA-Z0-9])+(?![a-zA-Z0-9])', lambda m: re.sub(r'\s+', '', m.group(0)), extracted_text)
    despaced_upper = despaced_text.upper()
    text_alphanumeric = re.sub(r'[^A-Z0-9]', '', text_upper)
    fn_upper = (filename or '').upper()

    sources = [text_upper, despaced_upper, text_alphanumeric, fn_upper]

    def has_phrase(target_phrases):
        for phrase in target_phrases:
            p_upper = phrase.upper().strip()
            if not p_upper:
                continue
            if any(p_upper in src for src in [text_upper, despaced_upper, fn_upper]):
                return True
            p_no_space = re.sub(r'\s+', '', p_upper)
            if p_no_space and any(p_no_space in src for src in sources):
                return True
        return False

    # Rule 0: Explicit Negative Document Type Rejections
    
    # A. Reject PAN Cards
    has_pan_text = has_phrase([
        "INCOME TAX DEPARTMENT", "INCOMETAX DEPARTMENT", "INCOME TAX", "आयकर विभाग", "आयकर",
        "PERMANENT ACCOUNT NUMBER", "स्थायी लेखा संख्या", "PAN CARD", "PAN APPLICATION"
    ])
    has_pan_filename = any(k in fn_upper for k in ["PAN.PDF", "PAN.JPG", "PAN.PNG", "PAN_CARD", "PANCARD", "PAN CARD", " PAN"])
    has_pan_num = bool(re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', despaced_upper))
    has_govt_india = has_phrase(["GOVT. OF INDIA", "GOVERNMENT OF INDIA", "भारत सरकार"])
    is_school_doc = has_phrase(["BOARD", "EXAMINATION", "MARKSHEET", "MARK SHEET", "SCHOOL", "COLLEGE", "UNIVERSITY", "DEGREE"])

    # B. Reject Aadhaar Cards
    is_aadhaar_card = (
        has_phrase(["MERA AADHAAR", "AADHAAR - AAM AADMI", "HELP@UIDAI.GOV.IN", "1947", "VID :"])
        or (has_phrase(["MALE", "FEMALE", "GENDER"]) and has_phrase(["ENROLMENT NO", "DOB", "YEAR OF BIRTH"]))
        or (has_phrase(["DOWNLOAD DATE", "UNIQUE IDENTIFICATION", "UIDAI"]) and not is_school_doc)
        or any(k in fn_upper for k in ["AADHAR CARD", "AADHAAR CARD", "ADHAR CARD", "AADHAR SCAN", "AADHAAR SCAN"])
    )

    # C. Reject Bank Passbooks / Statements
    is_bank_doc = has_phrase([
        "PASSBOOK", "ACCOUNT NUMBER", "ACCOUNT NO", "SAVINGS BANK", "IFSC CODE", "IFSC :", "IFSC:",
        "BRANCH :", "BRANCH:", "STATEMENT OF ACCOUNT", "CUSTOMER ID", "CIF NO"
    ]) or any(k in fn_upper for k in ["PASSBOOK", "PASS BOOK", "BANK", "STATEMENT"])

    # D. Reject LMS / NSEIT Certificates
    is_cert_doc = has_phrase([
        "CERTIFICATE OF ACCOMPLISHMENT", "OPERATOR ELIGIBILITY CERTIFICATE", "CHILD ENROLMENT LITE CLIENT",
        "TESTING AND CERTIFICATION AGENCY", "DEXIT GLOBAL", "NSEIT"
    ])

    is_invalid_doc = (
        has_pan_text or has_pan_filename or
        (has_pan_num and has_govt_india and not is_school_doc) or
        (is_aadhaar_card and not is_school_doc) or
        is_bank_doc or
        (is_cert_doc and not is_school_doc)
    )

    if is_invalid_doc:
        if qualification == "High School (10th)":
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid 10th standard Marksheet.")
        elif qualification == "Higher Secondary (12th)":
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid 12th standard Marksheet.")
        elif qualification == "Diploma / ITI":
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid Diploma/ITI certificate.")
        else:
            raise ValueError(f"Invalid Document: The uploaded file does not appear to be a valid {qualification} certificate.")

    # Rule 1: Positive Document Classification
    if qualification == "High School (10th)":
        keywords = [
            "BOARD OF SECONDARY EDUCATION", "CENTRAL BOARD", "CBSE", "ICSE", "STATE BOARD",
            "SECONDARY", "HIGH SCHOOL", "10TH", "MATRIC", "MATRICULATION", "CLASS 10", "CLASS X", "TENTH",
            "CERTIFICATE-CUM-MARKSHEET", "MARKSHEET", "MARK SHEET", "STATEMENT OF MARKS", "GRADE CARD",
            "माध्यमिक", "हाई स्कूल", "अंक सूची", "अंकसूची", "अंक-पत्र", "अंकपत्र"
        ]
        if not has_phrase(keywords):
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid 10th standard Marksheet.")
        
        # Ensure it's not a 12th certificate
        negative_kws = ["SENIOR SECONDARY", "HIGHER SECONDARY", "12TH", "INTERMEDIATE", "XII", "PRE-UNIVERSITY", "SENIOR SCHOOL", "12वीं"]
        if has_phrase(negative_kws):
            raise ValueError("Validation Error: Document appears to be a 12th standard marksheet, but 10th was expected.")
            
        # Ensure it's not a college/degree/diploma
        college_kws = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "DIPLOMA", "POLYTECHNIC", "ITI", "SEMESTER"]
        if any(re.search(r'\b' + re.escape(kw) + r'\b', text_upper) for kw in college_kws):
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid 10th standard Marksheet.")

    elif qualification == "Higher Secondary (12th)":
        keywords = ["HIGHER SECONDARY", "SENIOR SECONDARY", "12TH", "INTERMEDIATE", "XII", "PRE-UNIVERSITY", "SENIOR SCHOOL", "12वीं", "उच्‍चतर माध्‍यमिक"]
        if not has_phrase(keywords):
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid 12th standard Marksheet.")
            
        college_regex = r'\b(DEGREE|UNIVERSITY|BACHELOR|MASTER|DIPLOMA|POLYTECHNIC|ITI|SEMESTER)\b'
        if re.search(college_regex, text_upper):
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid 12th standard Marksheet.")

    elif qualification == "Diploma / ITI":
        keywords = ["DIPLOMA", "POLYTECHNIC", "ITI", "INDUSTRIAL TRAINING", "TECHNICAL EDUCATION"]
        if not has_phrase(keywords):
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid Diploma/ITI certificate.")
            
        degree_regex = r'\b(DEGREE|UNIVERSITY|BACHELOR|MASTER)\b'
        if re.search(degree_regex, text_upper):
            raise ValueError("Invalid Document: The uploaded file does not appear to be a valid Diploma/ITI certificate.")
            
        # Ensure it's not a simple school marksheet
        if any(kw in text_upper for kw in ["SECONDARY SCHOOL", "HIGH SCHOOL", "HIGHER SECONDARY", "INTERMEDIATE"]) and not any(kw in text_upper for kw in ["DIPLOMA", "POLYTECHNIC", "ITI"]):
            raise ValueError("Uploaded document is a school marksheet, but a Diploma/ITI was expected.")

    elif qualification in ["Graduation (Bachelor's Degree)", "Post Graduation (Master's Degree)"]:
        # Check graduation keywords
        grad_keywords = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "PROVISIONAL", "CONVOCATION", "SEMESTER", "COLLEGE", "GRADUATE", "B.A", "B.SC", "B.COM", "B.TECH", "B.E", "BCA", "BBA", "M.A", "M.SC", "M.COM", "M.TECH", "M.E", "MCA", "MBA"]
        if not has_phrase(grad_keywords):
            raise ValueError(f"Uploaded document is not a valid {qualification} certificate.")
            
        # Ensure it's not a simple school marksheet (10th/12th)
        if any(kw in text_upper for kw in ["SECONDARY SCHOOL EXAM", "HIGH SCHOOL EXAM", "HIGHER SECONDARY EXAM", "INTERMEDIATE EXAM"]) and not any(kw in text_upper for kw in ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "SEMESTER"]):
            raise ValueError(f"Uploaded document is a school marksheet, but a {qualification} was expected.")
            
        # If specific to master's, check for master's keywords
        if qualification == "Post Graduation (Master's Degree)":
            post_grad_keywords = ["MASTER", "POST GRADUATE", "M.A", "M.SC", "M.COM", "M.TECH", "M.E", "MCA", "MBA"]
            if not any(kw in text_upper for kw in post_grad_keywords):
                raise ValueError("Uploaded document is a Bachelor's degree, but a Post Graduation (Master's) was expected.")
    else:
        # Fallback for "Other / Higher"
        pass

    # Rule 2: Name Verification
    if candidate_name:
        name_upper = candidate_name.upper().strip()
        clean_cand_name = re.sub(r'[^A-Z\s]', ' ', name_upper)
        name_tokens = [w for w in clean_cand_name.split() if len(w) >= 2]
        
        if name_tokens:
            lines = [line.strip().upper() for line in extracted_text.splitlines() if line.strip()]
            despaced_lines = [
                re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), line)
                for line in lines
            ]
            
            all_doc_words = []
            for line in despaced_lines:
                words = re.findall(r'[A-Z]{2,}', line)
                all_doc_words.extend(words)
            
            # Check 1: Line-level match on specific lines (not the whole document string)
            full_name_clean = " ".join(name_tokens)
            line_match_found = any(
                fuzz.token_set_ratio(full_name_clean, l) >= 80 or (fuzz.partial_ratio(full_name_clean, l) >= 85 and len(l) <= len(full_name_clean) * 3)
                for l in despaced_lines
            )
            
            # Check 2: Word-by-word token matching against actual extracted document words
            token_matches = 0
            for n_tok in name_tokens:
                if len(n_tok) <= 2:
                    if any(n_tok == w for w in all_doc_words):
                        token_matches += 1
                else:
                    best_word_score = max((fuzz.ratio(n_tok, w) for w in all_doc_words), default=0)
                    if best_word_score >= 80:
                        token_matches += 1
            
            is_name_valid = False
            if line_match_found:
                is_name_valid = True
            elif len(name_tokens) == 1:
                is_name_valid = (token_matches >= 1)
            else:
                is_name_valid = (token_matches >= len(name_tokens)) or (len(name_tokens) >= 3 and token_matches >= len(name_tokens) - 1)
            
            if not is_name_valid:
                errors['name'] = f"Name '{candidate_name}' does not match the marksheet."

    # Rule 3: DOB Verification
    if candidate_dob and qualification == "High School (10th)":
        try:
            parsed_dob = datetime.strptime(candidate_dob, "%Y-%m-%d")
        except ValueError:
            errors['dob'] = "Invalid Date of Birth format."
        else:
            # Month mapping for textual dates
            month_map = {
                "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
                "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
            }
            
            # Create a normalized version of text for digit OCR confusion (O -> 0, I/l -> 1, S -> 5, B -> 8)
            normalized_ocr = text_upper
            # Fix O/0 confusion inside date patterns like 07/O1/2OO4
            normalized_ocr = re.sub(r'(?<=\d)O(?=\d|[-/.,])|(?<=[-/.,])O(?=\d)', '0', normalized_ocr)
            normalized_ocr = re.sub(r'(?<=\d)I(?=\d|[-/.,])|(?<=[-/.,])I(?=\d)', '1', normalized_ocr)
            
            date_patterns = [
                r'(?<!\d)(\d{1,2})\s*[-/.,]\s*(\d{1,2})\s*[-/.,]\s*(\d{4})(?!\d)',
                r'(?<!\d)(\d{4})\s*[-/.,]\s*(\d{1,2})\s*[-/.,]\s*(\d{1,2})(?!\d)',
                r'(?<!\d)(\d{1,2})\s*[-/.,\s]\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*[-/.,\s]\s*(\d{4})(?!\d)'
            ]
            
            found_match = False
            extracted_dates = []
            
            debug_logs = []
            debug_logs.append(f"Candidate DOB: {candidate_dob}")
            debug_logs.append(f"Parsed DOB: {parsed_dob}")
            debug_logs.append(f"Text upper sample: {text_upper[:300]}...")
            
            # 1. Check numeric patterns on original and normalized text
            for text_source in [text_upper, normalized_ocr]:
                if found_match:
                    break
                for i, pattern in enumerate(date_patterns[:2]):
                    matches = re.findall(pattern, text_source)
                    debug_logs.append(f"Pattern {i} ({pattern}): Matches: {matches}")
                    for match in matches:
                        possible_dates = []
                        if i == 1: # YYYY-MM-DD pattern
                            year = match[0]
                            month = match[1].zfill(2)
                            day = match[2].zfill(2)
                            possible_dates.append((f"{year}-{month}-{day}", "%Y-%m-%d"))
                        else: # DD-MM-YYYY pattern (or MM-DD-YYYY)
                            d1 = match[0].zfill(2)
                            d2 = match[1].zfill(2)
                            year = match[2]
                            possible_dates.append((f"{d1}-{d2}-{year}", "%d-%m-%Y")) # DD-MM-YYYY
                            possible_dates.append((f"{d2}-{d1}-{year}", "%d-%m-%Y")) # MM-DD-YYYY
                        
                        for dt_str, fmt in possible_dates:
                            try:
                                found_date = datetime.strptime(dt_str, fmt)
                                extracted_dates.append(found_date)
                                debug_logs.append(f"Parsed date {dt_str} -> {found_date} (Compare with {parsed_dob})")
                                if found_date == parsed_dob:
                                    found_match = True
                                    debug_logs.append("Match Found!")
                                    break
                            except ValueError as ex:
                                debug_logs.append(f"Parse error for {dt_str}: {ex}")
                                continue
                        if found_match:
                            break
                    if found_match:
                        break
            
            # 2. Check textual month patterns
            if not found_match:
                for text_source in [text_upper, normalized_ocr]:
                    matches = re.findall(date_patterns[2], text_source)
                    debug_logs.append(f"Pattern 2 ({date_patterns[2]}): Matches: {matches}")
                    for match in matches:
                        m_name = match[1].upper()[:3]
                        if m_name in month_map:
                            day = match[0].zfill(2)
                            month_num = month_map[m_name]
                            year = match[2]
                            dt_str = f"{day}-{month_num}-{year}"
                            try:
                                found_date = datetime.strptime(dt_str, "%d-%m-%Y")
                                extracted_dates.append(found_date)
                                debug_logs.append(f"Parsed textual date {dt_str} -> {found_date} (Compare with {parsed_dob})")
                                if found_date == parsed_dob:
                                    found_match = True
                                    debug_logs.append("Match Found!")
                                    break
                            except ValueError as ex:
                                debug_logs.append(f"Parse error for textual {dt_str}: {ex}")
                                continue
                    if found_match:
                        break
                            
            # Fallback 1: Textual Date of Birth verification in words (handles "7TH JANUARY TWO THOUSAND FOUR")
            if not found_match:
                c_year_words = get_year_in_words(parsed_dob.year)
                c_month_words = get_month_in_words(parsed_dob.month)
                c_day_words = get_day_in_words(parsed_dob.day)
                
                has_month = any(m_word in text_upper for m_word in c_month_words)
                has_year = any(y_word in text_upper or str(parsed_dob.year) in text_upper for y_word in c_year_words)
                has_day = any(d_word in text_upper for d_word in c_day_words)
                
                debug_logs.append(f"Textual fallback: Month matched={has_month}, Year matched={has_year}, Day matched={has_day}")
                if has_month and has_year and has_day:
                    found_match = True
                    debug_logs.append("Match Found via textual words fallback!")
                    
            # Check if any month name exists in the text (to see if a date is present in the document)
            all_months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
                          "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            has_any_month_in_text = any(m in text_upper for m in all_months)
            
            debug_logs.append(f"Extracted dates list: {extracted_dates}")
            debug_logs.append(f"Has any month name in text: {has_any_month_in_text}")
            debug_logs.append(f"Final found_match status: {found_match}")
            
            with open("debug_ocr_matching.txt", "w", encoding="utf-8") as df:
                df.write("\n".join(debug_logs) + "\n")
            if not found_match:
                if not extracted_dates and not has_any_month_in_text:
                    errors['dob'] = "Date of Birth not found on the marksheet."
                else:
                    errors['dob'] = f"Date of Birth '{candidate_dob}' does not match the marksheet."

    if errors:
        import json
        raise ValueError(json.dumps({'field_errors': errors}))

def validate_consent_form(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: No readable text detected. Please upload a clear Consent / Declaration Form."

    text_upper = extracted_text.upper()

    # Strict positive identifiers for genuine Consent / Undertaking / Declaration forms
    # A valid document MUST contain authentic consent/declaration headings or operative undertaking clauses
    strong_consent_phrases = [
        # Form Titles & Headers
        "CONSENT FORM", "DECLARATION FORM", "UNDERTAKING FORM", "CONSENT LETTER",
        "OPERATOR CONSENT", "EA CONSENT", "CONSENT OF OPERATOR", "OPERATOR UNDERTAKING",
        "SELF DECLARATION", "SELF-DECLARATION", "DECLARATION BY OPERATOR", "DECLARATION BY APPLICANT",
        "DECLARATION BY CANDIDATE", "UNDERTAKING BY OPERATOR", "UNDERTAKING BY CANDIDATE",
        "UNDERTAKING BY APPLICANT", "CONSENT / UNDERTAKING", "CONSENT CUM UNDERTAKING",
        "DECLARATION CUM UNDERTAKING", "AFFIDAVIT / UNDERTAKING", "ENROLMENT OPERATOR CONSENT",
        "ENROLMENT AGENCY CONSENT",
        
        # Operative Declaration & Undertaking Clauses
        "HEREBY DECLARE", "DO HEREBY DECLARE", "I HEREBY DECLARE", "I/WE HEREBY DECLARE",
        "HEREBY UNDERTAKE", "DO HEREBY UNDERTAKE", "I HEREBY UNDERTAKE", "I/WE HEREBY UNDERTAKE",
        "GIVE MY CONSENT", "GIVE CONSENT", "PROVIDE MY CONSENT", "HEREBY GIVE MY CONSENT",
        "HEREBY GIVE CONSENT", "HEREBY VOLUNTARILY", "GIVING MY CONSENT", "CONSENT TO WORK",
        "CONSENT FOR AADHAAR", "CONSENT FOR ADHAAR", "SOLEMNLY DECLARE", "SOLEMNLY AFFIRM",
        "SOLEMN AFFIRMATION",
        
        # Formal Attestation & Signature Phrases standard in Consent/Declaration forms
        "BEST OF MY KNOWLEDGE AND BELIEF", "TRUE AND CORRECT TO THE BEST OF MY KNOWLEDGE",
        "INFORMATION GIVEN ABOVE IS TRUE", "PARTICULARS GIVEN ABOVE ARE TRUE",
        "DETAILS FURNISHED ABOVE ARE TRUE", "SIGNATURE OF OPERATOR", "SIGNATURE OF THE OPERATOR",
        "SIGNATURE OF APPLICANT", "SIGNATURE OF THE APPLICANT", "SIGNATURE OF CANDIDATE",
        "SIGNATURE OF THE CANDIDATE", "SIGNATURE OF ENROLMENT OPERATOR",
        
        # Hindi Positive Identifiers
        "सहमति पत्र", "घोषणा पत्र", "शपथ पत्र", "वचन पत्र", "स्वघोषणा", "सहमति-पत्र", "घोषणा-पत्र",
        "सहमति देता हूँ", "सहमति देती हूँ", "घोषणा करता हूँ", "घोषणा करती हूँ",
        "सहमति प्रदान करता", "सहमति प्रदान करती", "शपथपूर्वक कथन", "एतद्द्वारा घोषणा",
        "आवेदक के हस्ताक्षर", "ऑपरेटर के हस्ताक्षर"
    ]

    has_strong_consent = any(phrase in text_upper for phrase in strong_consent_phrases)
    if not has_strong_consent:
        return "Validation Error: The uploaded document is not recognized as a valid Consent / Declaration Form."

    # Validate Operator Name
    if operator_name and not _match_operator_name(operator_name, text_upper):
        return f"Validation Error: The name on the Consent Form does not match the Operator's name '{operator_name}'."

    return None

def validate_passbook(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: No readable text detected. Please upload a clear Bank Passbook."

    text_upper = extracted_text.upper()
    clean_for_passbook = text_upper.replace("PERMANENT ACCOUNT NUMBER", "").replace("PERMANENT ACCOUNT", "").replace("PERMANENT", "")

    # 1. Positive Bank Passbook Keyword Check (Allowlist)
    # A valid passbook must explicitly contain authentic banking keywords / bank identifiers
    bank_keywords = [
        "PASSBOOK", "IFSC", "MICR", "SAVINGS ACCOUNT", "CURRENT ACCOUNT",
        "ACCOUNT NO", "ACCOUNT NUMBER", "A/C NO", "AC NO", "CIF NO", "CIF NUMBER",
        "CUSTOMER ID", "CUST ID", "BANK", "BRANCH", "DEPOSIT", "WITHDRAWAL",
        "STATE BANK", "PUNJAB NATIONAL", "BANK OF BARODA", "CANARA BANK",
        "UNION BANK", "BANK OF INDIA", "CENTRAL BANK", "INDIAN BANK", "ALLAHABAD BANK",
        "UCO BANK", "BANK OF MAHARASHTRA", "GRAMIN BANK", "CHHATTISGARH RAJYA GRAMIN",
        "HDFC", "ICICI", "AXIS BANK", "KOTAK", "IPPB", "INDIA POST PAYMENTS", "COOPERATIVE BANK",
        "SBIN", "PUNB", "BARB", "CNRB", "UBIN", "BKID", "CBIN", "IDIB", "UCBA", "MAHB", "CRGB",
        "खाता", "बैंक", "शाखा", "पासबुक", "बचत खाता", "आईएफएससी", "खाता संख्या", "खाता क्रमांक"
    ]

    has_bank_kw = any(kw in clean_for_passbook for kw in bank_keywords)
    if not has_bank_kw:
        return "Validation Error: The uploaded document is not recognized as a valid Bank Passbook."

    # 2. Validate Operator Name on Passbook if provided
    if operator_name and not _match_operator_name(operator_name, text_upper):
        return f"Validation Error: The name on the Passbook does not match the Operator's name '{operator_name}'."

    return None

def validate_nseit_certificate(extracted_text: str, operator_name: str, cert_number: str) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: No readable text detected. Please upload a clear NSEIT Certificate."

    text_upper = extracted_text.upper()
    despaced_text = re.sub(r'(?<![A-Z0-9])[A-Z0-9](?:\s+[A-Z0-9])+(?![A-Z0-9])', lambda m: re.sub(r'\s+', '', m.group(0)), extracted_text)
    despaced_upper = despaced_text.upper()
    text_no_space = "".join(c for c in text_upper if c.isalnum())
    normalized_text_no_space = text_no_space.replace('O', '0').replace('I', '1')

    # Strict positive identifiers for genuine NSEIT / DEXIT Aadhaar Eligibility Certificates (Allowlist)
    # A valid certificate must explicitly contain authentic testing agency or Aadhaar Operator exam titles
    strong_nseit_markers = [
        "NSEIT", "NSE-IT", "NSE.IT", "DEXIT", "DEX IT", "DEX-IT", "DEXIT GLOBAL",
        "OPERATOR ELIGIBILITY CERTIFICATE", "AADHAAR OPERATOR ELIGIBILITY",
        "AADHAAR ENROLMENT OPERATOR", "ENROLMENT OPERATOR / SUPERVISOR",
        "ENROLMENT OPERATOR/SUPERVISOR", "AADHAAR OPERATOR / SUPERVISOR",
        "AADHAAR OPERATOR/SUPERVISOR", "OPERATOR / SUPERVISOR CERTIFICATE",
        "TESTING AND CERTIFICATION AGENCY", "TESTING & CERTIFICATION AGENCY",
        "TESTING AND CERTIFICATION AGENCY (TCA)"
    ]
    has_direct_nseit = any(kw in text_upper for kw in strong_nseit_markers)
    has_operator_cert = (
        ("UIDAI" in text_upper or "UNIQUE IDENTIFICATION" in text_upper or "AADHAAR" in text_upper or "AADHAR" in text_upper) and
        ("OPERATOR" in text_upper or "SUPERVISOR" in text_upper) and
        ("ELIGIBILITY" in text_upper or "CERTIFICATE NO" in text_upper or "LANGUAGE PROFICIENCY" in text_upper or "CERTIFICATION AGENCY" in text_upper or "PASSED THE EXAMINATION" in text_upper)
    )

    if not has_direct_nseit and not has_operator_cert:
        return "Validation Error: The uploaded document is not recognized as a valid NSEIT Certificate."

    # 3. Strict Operator Name Validation
    if operator_name and operator_name.strip():
        name_clean = re.sub(r'[^A-Z\s]', ' ', operator_name.upper().strip())
        raw_tokens = [w for w in name_clean.split() if len(w) >= 2]
        name_tokens = [w for w in raw_tokens if w not in ('MR', 'MRS', 'MS', 'SHRI', 'SMT', 'SH', 'KUMAR')]
        if not name_tokens:
            name_tokens = raw_tokens

        # Check if certified candidate name is extractable from certificate
        cert_name_match = re.search(r'This is to certify that\s*\n+([A-Za-z\s]+?)\s*\n+has successfully passed', extracted_text, re.IGNORECASE)
        if not cert_name_match:
            cert_name_match = re.search(r'This is to certify that\s+([A-Za-z\s]+?)\s+has successfully passed', despaced_text, re.IGNORECASE)
        
        if cert_name_match:
            extracted_cert_name = cert_name_match.group(1).strip().upper()
            extracted_tokens = [w for w in re.sub(r'[^A-Z\s]', ' ', extracted_cert_name).split() if len(w) >= 2]
            
            # Check First Name token match
            first_name_match = name_tokens[0] in extracted_tokens or any(fuzz.ratio(name_tokens[0], et) >= 80 for et in extracted_tokens)
            # Check all tokens match
            all_tokens_matched = all(tok in extracted_tokens or any(fuzz.ratio(tok, et) >= 80 for et in extracted_tokens) for tok in name_tokens)
            
            if not first_name_match or not all_tokens_matched:
                return f"Validation Error: Name on NSEIT Certificate ('{extracted_cert_name}') does not match Operator's name '{operator_name}'."
        else:
            # Fallback document-wide strict token matching
            doc_words = set(re.findall(r'[A-Z]{2,}', text_upper) + re.findall(r'[A-Z]{2,}', despaced_upper))
            
            # First name is mandatory
            first_name_match = name_tokens[0] in doc_words or any(fuzz.ratio(name_tokens[0], w) >= 80 for w in doc_words if len(w) == len(name_tokens[0]))
            if not first_name_match:
                return f"Validation Error: Name on certificate does not match '{operator_name}'."

            # If 2 tokens (e.g. First + Last), BOTH must match
            if len(name_tokens) == 2:
                last_name_match = name_tokens[1] in doc_words or any(fuzz.ratio(name_tokens[1], w) >= 80 for w in doc_words if len(w) == len(name_tokens[1]))
                if not last_name_match:
                    return f"Validation Error: Name on certificate does not match '{operator_name}'."
            elif len(name_tokens) > 2:
                # 3+ tokens: at least len - 1 tokens must match
                matched = sum(1 for tok in name_tokens if tok in doc_words or any(fuzz.ratio(tok, w) >= 80 for w in doc_words if len(w) == len(tok)))
                if matched < len(name_tokens) - 1:
                    return f"Validation Error: Name on certificate does not match '{operator_name}'."

    # 4. Strict Certificate Number (ID) Validation
    if cert_number and str(cert_number).strip():
        clean_cert = "".join(c for c in str(cert_number).upper().strip() if c.isalnum())
        stripped_cert = re.sub(r'^(?:NS|DEX)', '', clean_cert)
        normalized_clean_cert = clean_cert.replace('O', '0').replace('I', '1')
        normalized_stripped_cert = stripped_cert.replace('O', '0').replace('I', '1')

        # Attempt to extract exact certificate number from certificate text
        extracted_cert = None
        cert_match = re.search(r'(?:Certificate\s*No\.?|Certificate\s*Number|CERTIFICATE\s*NO)\s*[:\.-]?\s*([A-Za-z0-9_-]+)', extracted_text, re.IGNORECASE)
        if not cert_match:
            cert_match = re.search(r'(?:Certificate\s*No\.?|Certificate\s*Number|CERTIFICATE\s*NO)\s*[:\.-]?\s*([A-Za-z0-9_-]+)', despaced_text, re.IGNORECASE)
        if cert_match:
            extracted_cert = cert_match.group(1).strip().upper()

        matched_cert = False
        if extracted_cert:
            clean_extracted = "".join(c for c in extracted_cert if c.isalnum())
            stripped_extracted = re.sub(r'^(?:NS|DEX)', '', clean_extracted)
            if clean_cert == clean_extracted or stripped_cert == stripped_extracted:
                matched_cert = True
            elif clean_cert.replace('O', '0') == clean_extracted.replace('O', '0') or stripped_cert.replace('O', '0') == stripped_extracted.replace('O', '0'):
                matched_cert = True

        if not matched_cert:
            # Check continuous character stream in text
            if clean_cert in text_no_space or (len(stripped_cert) >= 5 and stripped_cert in text_no_space):
                matched_cert = True
            elif normalized_clean_cert in normalized_text_no_space or (len(normalized_stripped_cert) >= 5 and normalized_stripped_cert in normalized_text_no_space):
                matched_cert = True

        if not matched_cert:
            return f"Validation Error: Certificate number '{cert_number}' does not match the uploaded NSEIT Certificate."

    return None

def _match_operator_in_excel_row(operator_name: str, operator_mobile: str, row_text: str) -> tuple[bool, bool]:
    """
    Checks if an operator's mobile and name match within a single row of an Excel sheet.
    Returns (mob_in_row, name_in_row).
    """
    row_upper = row_text.upper()
    row_digits = re.sub(r'\D', '', row_text)

    # 1. Mobile in row check
    clean_mob = re.sub(r'\D', '', str(operator_mobile or ''))
    mob_target = clean_mob[-10:] if len(clean_mob) >= 10 else clean_mob
    mob_in_row = False
    if mob_target:
        if mob_target in row_digits or mob_target in row_text:
            mob_in_row = True
    else:
        mob_in_row = True

    # 2. Name in row check
    name_str = str(operator_name or '').strip().upper()
    clean_name = re.sub(r'[^A-Z0-9\s]', ' ', name_str)
    raw_tokens = [w for w in clean_name.split() if len(w) >= 2]
    name_tokens = [w for w in raw_tokens if w not in ('MR', 'MRS', 'MS', 'SHRI', 'SMT', 'SH')]
    if not name_tokens:
        name_tokens = raw_tokens

    name_in_row = False
    if not name_tokens:
        name_in_row = True
    else:
        clean_full_name = " ".join(name_tokens)
        row_no_space = re.sub(r'[^A-Z0-9]', '', row_upper)
        name_no_space = "".join(name_tokens)

        if clean_full_name in row_upper or (len(name_no_space) >= 4 and name_no_space in row_no_space):
            name_in_row = True
        else:
            row_words = [w for w in re.findall(r'[A-Z0-9]{2,}', row_upper) if not w.isdigit()]
            matched_count = 0
            for tok in name_tokens:
                if tok in row_words:
                    matched_count += 1
                elif any(fuzz.ratio(tok, rw) >= 80 for rw in row_words):
                    matched_count += 1
                elif any(fuzz.partial_ratio(tok, rw) >= 85 for rw in row_words if len(rw) >= len(tok)):
                    matched_count += 1

            if len(name_tokens) == 1:
                name_in_row = (matched_count >= 1)
            elif len(name_tokens) == 2:
                name_in_row = (matched_count == 2)
            else:
                first_tok_matched = (name_tokens[0] in row_words or any(fuzz.ratio(name_tokens[0], rw) >= 80 for rw in row_words))
                name_in_row = (matched_count >= len(name_tokens) - 1 and first_tok_matched)

    return mob_in_row, name_in_row

def validate_excel_sheet(file_bytes: bytes, operator_name: str, operator_mobile: str) -> str | None:
    rows = []

    # 1. Try openpyxl across all worksheets (preserves exact values, numbers, formats)
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                cell_strs = []
                for cell in row:
                    if cell is None:
                        continue
                    if isinstance(cell, float) and cell.is_integer():
                        cell_strs.append(str(int(cell)))
                    elif isinstance(cell, (int, float)):
                        cell_strs.append(f"{cell:.0f}" if isinstance(cell, float) and cell.is_integer() else str(cell))
                    else:
                        cell_strs.append(str(cell).strip())
                cell_strs = [c for c in cell_strs if c and c.lower() not in ("none", "nan", "")]
                if cell_strs:
                    rows.append(" ".join(cell_strs))
    except Exception:
        pass

    # 2. Fallback to pandas with header=None across all sheets (handles all rows including row 1)
    if not rows:
        try:
            excel_file = pd.ExcelFile(io.BytesIO(file_bytes))
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, dtype=str)
                for _, r in df.iterrows():
                    cell_strs = [str(val).strip() for val in r.values if pd.notna(val) and str(val).strip().lower() not in ("nan", "none", "")]
                    if cell_strs:
                        rows.append(" ".join(cell_strs))
        except Exception:
            pass

    # 3. Fallback to CSV
    if not rows:
        try:
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str, encoding=enc)
                    for _, r in df.iterrows():
                        cell_strs = [str(val).strip() for val in r.values if pd.notna(val) and str(val).strip().lower() not in ("nan", "none", "")]
                        if cell_strs:
                            rows.append(" ".join(cell_strs))
                    if rows:
                        break
                except Exception:
                    pass
        except Exception:
            pass

    if not rows:
        return "Validation Error: The uploaded Excel sheet is empty or contains no readable rows."

    found_mobile_anywhere = False
    found_name_anywhere = False

    for row_text in rows:
        mob_in_row, name_in_row = _match_operator_in_excel_row(operator_name, operator_mobile, row_text)
        if mob_in_row:
            found_mobile_anywhere = True
        if name_in_row:
            found_name_anywhere = True

        # STRICT COMBINATION MATCH: Both must match in the exact same row
        if mob_in_row and name_in_row:
            return None

    # Granular Error Messages
    if found_mobile_anywhere and not found_name_anywhere:
        return f"Validation Error: Mobile number '{operator_mobile}' was found in the Excel sheet, but operator name '{operator_name}' did not match."
    elif found_name_anywhere and not found_mobile_anywhere:
        return f"Validation Error: Operator name '{operator_name}' was found in the Excel sheet, but mobile number '{operator_mobile}' was not found."
    elif found_mobile_anywhere and found_name_anywhere:
        return f"Validation Error: Mobile number '{operator_mobile}' and name '{operator_name}' were found in different rows of the Excel sheet, but must be in the same row."

    return f"Validation Error: Operator '{operator_name}' with mobile '{operator_mobile}' was not found in the uploaded Excel sheet."