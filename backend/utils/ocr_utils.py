import io
import re
from datetime import datetime
from fastapi import UploadFile, HTTPException
import pandas as pd
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from thefuzz import fuzz
import os

# Set Tesseract CMD for Windows manually if not in PATH
tesseract_cmd_path = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.path.exists(tesseract_cmd_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path

def _do_ocr(image, lang: str) -> str:
    """Helper to run OCR with fallback if language is missing, plus image enhancement."""
    from PIL import ImageEnhance, ImageOps
    
    def run_tess(img, l, psm=3):
        try:
            config = f'--psm {psm}'
            return pytesseract.image_to_string(img, lang=l, config=config)
        except pytesseract.TesseractError as e:
            # If eng+hin fails, fallback to eng
            if l != "eng":
                print(f"Warning: OCR failed with lang={l}, falling back to 'eng'. Error: {e}")
                return pytesseract.image_to_string(img, lang="eng", config=config)
            raise e

    # 1. Normal extraction (PSM 3 - Default)
    text_normal = run_tess(image, lang)
    
    # 2. Enhanced extraction (Grayscale + High Contrast) 
    img_gray = image.convert('L')
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(3.0) 
    text_enhanced = run_tess(img_contrast, lang)
    
    # 3. Histogram Equalization (Extremely powerful for pulling out faded text on noisy backgrounds like PAN cards)
    try:
        img_equalized = ImageOps.equalize(img_gray)
        # PSM 11 is "Sparse text. Find as much text as possible in no particular order."
        # This is great when equalization makes the background noisy but the text legible
        text_equalized = run_tess(img_equalized, lang, psm=11)
    except Exception as e:
        text_equalized = ""
        print(f"Equalization failed: {e}")
        
    # 4. Binarization (Thresholding - excellent for dark text on colored backgrounds like PAN cards)
    try:
        # Simple thresholding: anything darker than 128 becomes black, else white
        img_binary = img_gray.point(lambda x: 0 if x < 128 else 255, '1')
        text_binary = run_tess(img_binary, lang, psm=3)
    except Exception as e:
        text_binary = ""
        print(f"Binarization failed: {e}")
    
    # 5. PSM 6 Pass (Assume uniform block of text) - Great for bypassing layout analysis that skips text next to QR codes
    try:
        text_psm6 = run_tess(img_gray, lang, psm=6)
    except Exception as e:
        text_psm6 = ""
        
    # 6. PSM 4 Pass (Assume single column) - Also good for forcing Tesseract to read line by line
    try:
        text_psm4 = run_tess(img_contrast, lang, psm=4)
    except Exception as e:
        text_psm4 = ""
    
    # Combine all passes to ensure absolute maximum text extraction coverage
    return text_normal + "\n" + text_enhanced + "\n" + text_equalized + "\n" + text_binary + "\n" + text_psm6 + "\n" + text_psm4

def extract_text_from_bytes(file_bytes: bytes, content_type: str, lang: str = "eng") -> str:
    """Extracts text directly from bytes (PDF or Image)."""
    try:
        extracted_text = ""
        
        if content_type == "application/pdf":
            # Check for Poppler path from env or common Windows locations
            poppler_path = os.getenv("POPPLER_PATH")
            if not poppler_path:
                common_poppler = [
                    r"C:\poppler-26.02.0\Library\bin",
                    r"C:\poppler\Library\bin", 
                    r"C:\Release-24.02.0-0\poppler-24.02.0\Library\bin",
                    r"C:\Program Files (x86)\Windows Media Player\Release-26.02.0-0\poppler-26.02.0\Library\bin"
                ]
                for p in common_poppler:
                    if os.path.exists(p):
                        poppler_path = p
                        break
            
            # Convert first page of PDF to image (use dpi=300 for better OCR)
            # Added a 30-second timeout so it doesn't hang indefinitely on Windows if Poppler stalls, but allows heavy PDFs
            images = convert_from_bytes(file_bytes, first_page=1, last_page=1, poppler_path=poppler_path, dpi=300, timeout=30)
            if images:
                extracted_text = _do_ocr(images[0], lang=lang)
        else:
            # Assume it's an image (JPG, PNG)
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text = _do_ocr(image, lang=lang)
            
        return extracted_text.upper()
    except Exception as e:
        import traceback
        with open("ocr_debug.txt", "a", encoding="utf-8") as f:
            f.write(f"\n--- OCR Extraction Error ---\n{traceback.format_exc()}\n")
        print(f"OCR Extraction Error: {e}")
        return ""

def extract_text_from_file(upload_file: UploadFile) -> str:
    """Legacy wrapper for FastAPI routes."""
    try:
        file_bytes = upload_file.file.read()
        return extract_text_from_bytes(file_bytes, upload_file.content_type)
    finally:
        upload_file.file.seek(0)

def validate_aadhaar(extracted_text: str, operator_name: str, operator_aadhaar: str = None) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: Could not read text from the Aadhaar document. Please upload a clear image."
    if "INCOME TAX DEPARTMENT" in extracted_text or "INCOME TAX" in extracted_text:
        return "Validation Error: The uploaded Aadhaar document appears to be a PAN Card."
    
    # Classification check
    keywords = ["AADHAAR", "UNIQUE IDENTIFICATION", "GOVERNMENT OF INDIA", "MERA AADHAAR", "DOB", "YEAR OF BIRTH", "MALE", "FEMALE"]
    if sum(1 for kw in keywords if kw in extracted_text) < 1:
        return "Validation Error: The uploaded document does not appear to be a valid Aadhaar Card."
    
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 50:
            fixed_text = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), extracted_text)
            score = max(score, fuzz.token_set_ratio(name_upper, fixed_text))
            name_no_space = name_upper.replace(" ", "")
            score = max(score, fuzz.token_set_ratio(name_no_space, fixed_text))
            
            # Simple match fallback using partial_ratio on no-space text
            extracted_no_space = extracted_text.replace(" ", "")
            name_parts = name_upper.split()
            simple_match = any(fuzz.partial_ratio(part, extracted_no_space) > 75 for part in name_parts if len(part) > 3)
            
            if simple_match or fuzz.partial_ratio(name_no_space, extracted_no_space) > 75:
                score = max(score, 50)
                
        if score < 50:
            with open("ocr_debug.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- AADHAAR OCR FAILED ---\nExpected: {operator_name}\nExtracted: {extracted_text}\nNo space: {extracted_no_space}\n")
            return f"Validation Error: The name on the Aadhaar document does not match the Operator's name '{operator_name}'."
            
    if operator_aadhaar:
        clean_aadhaar = "".join(filter(str.isdigit, operator_aadhaar))
        if clean_aadhaar and clean_aadhaar not in extracted_text.replace(" ", ""):
            return f"Validation Error: The Aadhaar number ending in '{clean_aadhaar}' was not found in the uploaded document."
            
    return None

def validate_pan(extracted_text: str, operator_name: str, operator_pan: str = None) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: Could not read text from the PAN document. Please upload a clear image."
    if "AADHAAR" in extracted_text or "UNIQUE IDENTIFICATION AUTHORITY" in extracted_text:
        return "Validation Error: The uploaded PAN document appears to be an Aadhaar Card."
        
    # Classification check
    keywords = ["INCOME TAX DEPARTMENT", "PERMANENT ACCOUNT NUMBER", "GOVT. OF INDIA", "SIGNATURE", "PAN"]
    if sum(1 for kw in keywords if kw in extracted_text) < 1:
        return "Validation Error: The uploaded document does not appear to be a valid PAN Card."

    if operator_pan:
        clean_pan = operator_pan.upper().strip()
        if clean_pan and clean_pan not in extracted_text.replace(" ", ""):
            return f"Validation Error: The PAN number '{clean_pan}' was not found in the uploaded document."
            
    return None

def validate_marksheet(extracted_text: str, candidate_name: str, candidate_dob: str, qualification: str = "High School (10th)") -> None:
    """Validates if the text looks like a marksheet, and matches name and DOB."""
    # print("===== OCR EXTRACTED TEXT =====")
    # try:
    #     print(extracted_text.encode('utf-8', errors='replace').decode('utf-8'))
    # except Exception:
    #     pass
    # print("==============================")
    if not extracted_text:
        return

    errors = {}

    # Rule 0: Reject completely wrong document types
    if "AADHAAR" in extracted_text or "UNIQUE IDENTIFICATION AUTHORITY" in extracted_text:
        raise ValueError("Validation Error: The uploaded document appears to be an Aadhaar Card, not a Marksheet.")
    if "INCOME TAX DEPARTMENT" in extracted_text or "PERMANENT ACCOUNT NUMBER" in extracted_text:
        raise ValueError("Validation Error: The uploaded document appears to be a PAN Card, not a Marksheet.")

    # Rule 1: Document Classification
    if qualification == "High School (10th)":
        keywords = ["BOARD", "EXAMINATION", "SECONDARY", "CERTIFICATE", "MARKS", "SCHOOL", "अंक", "प्रमाण", "परीक्षा", "10TH", "HIGH SCHOOL"]
        matches = sum(1 for kw in keywords if kw in extracted_text)
        if matches < 1:
            raise ValueError("Validation Error: The uploaded document does not appear to be a valid High School (10th) Marksheet.")
        
        # Ensure it's not a 12th certificate
        negative_kws = ["SENIOR SECONDARY EXAM", "HIGHER SECONDARY", "12TH", "INTERMEDIATE EXAM", "XII", "PRE-UNIVERSITY", "SENIOR SCHOOL CERTIFICATE"]
        if any(kw in extracted_text for kw in negative_kws):
            raise ValueError("Validation Error: Document appears to be a 12th standard marksheet, but 10th was expected.")

    elif qualification == "Higher Secondary (12th)":
        keywords = ["HIGHER SECONDARY", "SENIOR SECONDARY", "12TH", "INTERMEDIATE", "BOARD", "EXAMINATION", "SENIOR SCHOOL", "XII"]
        matches = sum(1 for kw in keywords if kw in extracted_text)
        if matches < 1:
            raise ValueError("Validation Error: The uploaded document does not appear to be a valid 12th Standard Marksheet.")
        
        # Ensure it's not a 10th certificate
        # If it says "SECONDARY SCHOOL EXAMINATION" or "HIGH SCHOOL EXAMINATION" but NOT "SENIOR"
        if ("SECONDARY SCHOOL EXAM" in extracted_text or "HIGH SCHOOL EXAM" in extracted_text or "10TH" in extracted_text) and not any(kw in extracted_text for kw in ["SENIOR", "HIGHER", "12TH", "INTERMEDIATE", "XII", "PRE-UNIVERSITY"]):
            raise ValueError("Validation Error: Document appears to be a 10th standard marksheet, but 12th was expected.")

    elif qualification == "Diploma / ITI":
        keywords = ["DIPLOMA", "POLYTECHNIC", "ITI", "COUNCIL", "BOARD", "CERTIFICATE", "EXAMINATION", "INSTITUTE"]
        matches = sum(1 for kw in keywords if kw in extracted_text)
        if matches < 1:
            raise ValueError("Validation Error: The uploaded document does not appear to be a valid Diploma/ITI certificate.")
            
    elif qualification in ["Graduation (Bachelor's Degree)", "Post Graduation (Master's Degree)"]:
        keywords = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "SEMESTER", "PROVISIONAL", "EXAMINATION", "COLLEGE"]
        matches = sum(1 for kw in keywords if kw in extracted_text)
        if matches < 1:
            raise ValueError(f"Validation Error: The uploaded document does not appear to be a valid {qualification} certificate.")
    else:
        # Fallback for "Other / Higher"
        pass

    # Rule 2: Name Verification
    if candidate_name:
        name_upper = candidate_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 65:
            errors['name'] = f"The name on the Marksheet does not match the Candidate's name '{candidate_name}'."

    # Rule 3: DOB Verification
    if candidate_dob and qualification == "High School (10th)":
        try:
            parsed_dob = datetime.strptime(candidate_dob, "%Y-%m-%d")
        except ValueError:
            errors['dob'] = "Invalid DOB format submitted."
        else:
            # Common DOB formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
            date_patterns = [
                r'\b(\d{2})[-/.](\d{2})[-/.](\d{4})\b',
                r'\b(\d{4})[-/.](\d{2})[-/.](\d{2})\b'
            ]
            
            found_match = False
            extracted_dates = []
            for pattern in date_patterns:
                matches = re.findall(pattern, extracted_text)
                for match in matches:
                    if len(match[0]) == 4: # YYYY-MM-DD
                        dt_str = f"{match[0]}-{match[1]}-{match[2]}"
                        fmt = "%Y-%m-%d"
                    else: # DD-MM-YYYY
                        dt_str = f"{match[0]}-{match[1]}-{match[2]}"
                        fmt = "%d-%m-%Y"
                    
                    try:
                        found_date = datetime.strptime(dt_str, fmt)
                        extracted_dates.append(found_date)
                        if found_date == parsed_dob:
                            found_match = True
                            break
                    except ValueError:
                        continue
                if found_match:
                    break
                    
            if extracted_dates and not found_match:
                errors['dob'] = f"DOB '{candidate_dob}' does not match the date(s) found on the Marksheet."

    if errors:
        import json
        raise ValueError(json.dumps({'field_errors': errors}))

def validate_consent_form(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: Could not read text from the Consent Form. Please upload a clear image."
    keywords = ["CONSENT FORM", "AUTHORIZATION LETTER", "DECLARATION FORM", "UNDERTAKING"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    if matches < 1:
        return "Validation Error: The uploaded document does not appear to be a valid Consent Form."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 50:
            fixed_text = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), extracted_text)
            score = max(score, fuzz.token_set_ratio(name_upper, fixed_text))
            name_no_space = name_upper.replace(" ", "")
            score = max(score, fuzz.token_set_ratio(name_no_space, fixed_text))
            
        if score < 50:
            return f"Validation Error: The name on the Consent Form does not match the Operator's name '{operator_name}'."
    return None

def validate_passbook(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: Could not read text from the Passbook. Please upload a clear image."
    
    # Exclude marksheets explicitly
    if "STATEMENT OF MARKS" in extracted_text or "BOARD OF" in extracted_text or "SCHOOL" in extracted_text:
        return "Validation Error: The uploaded document appears to be a Marksheet, not a Passbook."
        
    keywords = ["BANK", "BRANCH", "ACCOUNT", "IFSC", "PASSBOOK", "MICR"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    
    # Require at least 2 banking keywords to be sure
    if matches < 2:
        return "Validation Error: The uploaded document does not appear to be a valid Bank Passbook or statement."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        
        fixed_text = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), extracted_text)
        score = max(score, fuzz.token_set_ratio(name_upper, fixed_text))
        
        name_no_space = name_upper.replace(" ", "")
        score = max(score, fuzz.token_set_ratio(name_no_space, fixed_text))
        
        extracted_no_space = extracted_text.replace(" ", "")
        name_parts = name_upper.split()
        simple_match = any(fuzz.partial_ratio(part, extracted_no_space) > 75 for part in name_parts if len(part) > 3)

        if simple_match or fuzz.partial_ratio(name_no_space, extracted_no_space) > 75:
            score = max(score, 50)

        if score < 50:
            with open("ocr_debug.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- PASSBOOK OCR FAILED ---\nExpected: {operator_name}\nExtracted: {extracted_text}\nNo space: {extracted_no_space}\n")
            return f"Validation Error: The name on the Passbook does not match the Operator's name '{operator_name}'."
    return None

def validate_nseit_certificate(extracted_text: str, operator_name: str, cert_number: str) -> str | None:
    if not extracted_text or len(extracted_text.strip()) < 10:
        return "Validation Error: Could not read text from the NSEIT Certificate. Please upload a clear image."
    keywords = ["NSEIT", "CERTIFICATE", "TESTING", "CERTIFICATION", "UIDAI", "AADHAAR"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    if matches < 2:
        return "Validation Error: The uploaded document does not appear to be a valid NSEIT Certificate."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 60:
            fixed_text = re.sub(r'(?<![A-Z])[A-Z](?: [A-Z])+(?![A-Z])', lambda m: m.group(0).replace(" ", ""), extracted_text)
            score = max(score, fuzz.token_set_ratio(name_upper, fixed_text))
            name_no_space = name_upper.replace(" ", "")
            score = max(score, fuzz.token_set_ratio(name_no_space, fixed_text))
            
        if score < 60:
            return f"Validation Error: The name on the NSEIT Certificate does not match the Operator's name '{operator_name}'."
    if cert_number:
        clean_cert = "".join(c for c in str(cert_number).upper() if c.isalnum())
        text_no_space = "".join(c for c in extracted_text.upper() if c.isalnum())
        if clean_cert and clean_cert not in text_no_space:
            # Fallback to fuzzy match for certificate numbers to handle OCR errors (like 8 vs B, 5 vs S)
            if fuzz.partial_ratio(clean_cert, text_no_space) < 80:
                return f"Validation Error: Certificate number '{cert_number}' was not found in the uploaded document."
    return None

def validate_excel_sheet(file_bytes: bytes, operator_name: str, operator_mobile: str) -> str | None:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8", engine="python")
        except Exception:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin1", engine="python")
            except Exception:
                return "Validation Error: Could not read the uploaded Excel sheet. Please ensure it is a valid format."
    text_content = df.to_string().upper()
    if operator_name:
        name_upper = operator_name.upper().strip()
        if name_upper not in text_content:
            # Simple match fallback for excel sheets
            name_parts = name_upper.split()
            simple_match = any(part in text_content for part in name_parts if len(part) > 2)
            if not simple_match:
                return f"Validation Error: Operator name '{operator_name}' was not found in the Excel sheet."
    if operator_mobile:
        if str(operator_mobile) not in text_content:
            return f"Validation Error: Operator mobile '{operator_mobile}' was not found in the Excel sheet."
    return None