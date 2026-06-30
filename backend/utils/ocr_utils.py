import io
import re
from datetime import datetime
from fastapi import UploadFile, HTTPException
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
    """Helper to run OCR with fallback if language is missing."""
    try:
        return pytesseract.image_to_string(image, lang=lang)
    except pytesseract.TesseractError as e:
        # If eng+hin fails (usually because hin.traineddata is missing), fallback to eng
        if lang != "eng":
            print(f"Warning: OCR failed with lang={lang}, falling back to 'eng'. Error: {e}")
            return pytesseract.image_to_string(image, lang="eng")
        raise e

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
            
            # Convert first page of PDF to image
            images = convert_from_bytes(file_bytes, first_page=1, last_page=1, poppler_path=poppler_path)
            if images:
                extracted_text = _do_ocr(images[0], lang=lang)
        else:
            # Assume it's an image (JPG, PNG)
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

def validate_aadhaar(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text:
        return None
    if "INCOME TAX DEPARTMENT" in extracted_text or "INCOME TAX" in extracted_text:
        return "Validation Error: The uploaded Aadhaar document appears to be a PAN Card."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 70:
            return f"Validation Error: Operator name '{operator_name}' does not match the name found in the uploaded Aadhaar document (Match score: {score}%)."
    return None

def validate_pan(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text:
        return None
    if "AADHAAR" in extracted_text or "UNIQUE IDENTIFICATION AUTHORITY" in extracted_text:
        return "Validation Error: The uploaded PAN document appears to be an Aadhaar Card."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 70:
            return f"Validation Error: Operator name '{operator_name}' does not match the name found in the uploaded PAN document (Match score: {score}%)."
    return None

def validate_marksheet(extracted_text: str, candidate_name: str, candidate_dob: str) -> None:
    """Validates if the text looks like a marksheet, and matches name and DOB."""
    if not extracted_text:
        return

    errors = {}

    # Rule 1: Document Classification
    keywords = ["BOARD", "EXAMINATION", "SECONDARY", "CERTIFICATE", "MARKS", "SCHOOL", "अंक", "प्रमाण", "परीक्षा"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    if matches < 1:
        raise ValueError("Validation Error: The uploaded document does not appear to be a valid 10th Standard Marksheet.")

    # Rule 2: Name Verification
    if candidate_name:
        name_upper = candidate_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 65:
            errors['name'] = f"Candidate name '{candidate_name}' does not match the name found in the uploaded Marksheet."

    # Rule 3: DOB Verification
    if candidate_dob:
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
    if not extracted_text:
        return None
    keywords = ["CONSENT", "AGREEMENT", "AUTHORIZATION", "FORM", "DECLARATION"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    if matches < 1:
        return "Validation Error: The uploaded document does not appear to be a Consent Form."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 50:
            return f"Validation Error: Operator name '{operator_name}' does not match the name found in the uploaded Consent Form (Match score: {score}%)."
    return None

def validate_passbook(extracted_text: str, operator_name: str) -> str | None:
    if not extracted_text:
        return None
    keywords = ["BANK", "BRANCH", "ACCOUNT", "IFSC", "PASSBOOK", "STATEMENT"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    if matches < 1:
        return "Validation Error: The uploaded document does not appear to be a valid Bank Passbook or statement."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 50:
            return f"Validation Error: Operator name '{operator_name}' does not match the name found in the Passbook (Match score: {score}%)."
    return None

def validate_nseit_certificate(extracted_text: str, operator_name: str, cert_number: str) -> str | None:
    if not extracted_text:
        return None
    keywords = ["NSEIT", "CERTIFICATE", "TESTING", "CERTIFICATION", "UIDAI", "AADHAAR"]
    matches = sum(1 for kw in keywords if kw in extracted_text)
    if matches < 2:
        return "Validation Error: The uploaded document does not appear to be a valid NSEIT Certificate."
    if operator_name:
        name_upper = operator_name.upper().strip()
        score = fuzz.token_set_ratio(name_upper, extracted_text)
        if score < 60:
            return f"Validation Error: Operator name '{operator_name}' does not match the name found in the NSEIT Certificate (Match score: {score}%)."
    if cert_number:
        if cert_number.upper() not in extracted_text.upper():
            return f"Validation Error: Certificate number '{cert_number}' was not found in the uploaded document."
    return None

def validate_excel_sheet(file_bytes: bytes, operator_name: str, operator_mobile: str) -> str | None:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        return "Validation Error: Could not read the uploaded Excel sheet. Please ensure it is a valid format."
    text_content = df.to_string().upper()
    if operator_name:
        if operator_name.upper().strip() not in text_content:
            return f"Validation Error: Operator name '{operator_name}' was not found in the Excel sheet."
    if operator_mobile:
        if str(operator_mobile) not in text_content:
            return f"Validation Error: Operator mobile '{operator_mobile}' was not found in the Excel sheet."
    return None