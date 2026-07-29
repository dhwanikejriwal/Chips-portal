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
        
        is_pdf = False
        if content_type:
            is_pdf = content_type.lower() == "application/pdf"
        if not is_pdf and file_bytes:
            is_pdf = file_bytes.startswith(b"%PDF")

        if is_pdf:
            # Check for Poppler path from env or common Windows locations
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
            
            # Convert first page of PDF to image (use dpi=300 for better OCR)
            # Added a 30-second timeout so it doesn't hang indefinitely on Windows if Poppler stalls, but allows heavy PDFs
            images = convert_from_bytes(file_bytes, first_page=1, last_page=1, poppler_path=poppler_path, dpi=300, timeout=30)
            if images:
                extracted_text = _do_ocr(images[0], lang=lang)
        else:
            # Assume it's an image (JPG, PNG)
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text = _do_ocr(image, lang=lang)
            
        # Debug logger
        try:
            with open("ocr_debug.txt", "a", encoding="utf-8") as debug_file:
                debug_file.write(f"\n--- NEW EXTRACTION ---\n")
                debug_file.write(f"Content Type: {content_type}\n")
                debug_file.write(f"Is PDF: {is_pdf}\n")
                debug_file.write(f"Extracted Length: {len(extracted_text)}\n")
                debug_file.write(f"Extracted Text Snippet:\n{extracted_text[:1000]}\n")
        except Exception as logger_err:
            print("Logger error:", logger_err)

        return extracted_text.upper()
    except Exception as e:
        import traceback
        with open("ocr_debug.txt", "a", encoding="utf-8") as f:
            f.write(f"\n--- OCR Extraction Error ---\n{traceback.format_exc()}\n")
        print(f"OCR Extraction Error: {e}")
        # Debug logger on error
        try:
            with open("ocr_debug.txt", "a", encoding="utf-8") as debug_file:
                debug_file.write(f"\n--- EXTRACTION ERROR ---\n")
                debug_file.write(f"Content Type: {content_type}\n")
                debug_file.write(f"Error: {e}\n")
        except Exception:
            pass
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
        1: ["FIRST", "ONE"], 2: ["SECOND", "TWO"], 3: ["THIRD", "THREE"], 4: ["FOURTH", "FOUR"],
        5: ["FIFTH", "FIVE"], 6: ["SIXTH", "SIX"], 7: ["SEVENTH", "SEVEN"], 8: ["EIGHTH", "EIGHT"],
        9: ["NINTH", "NINE"], 10: ["TENTH", "TEN"], 11: ["ELEVENTH", "ELEVEN"], 12: ["TWELFTH", "TWELVE"],
        13: ["THIRTEENTH", "THIRTEEN"], 14: ["FOURTEENTH", "FOURTEEN"], 15: ["FIFTEENTH", "FIFTEEN"],
        16: ["SIXTEENTH", "SIXTEEN"], 17: ["SEVENTEENTH", "SEVENTEEN"], 18: ["EIGHTEENTH", "EIGHTEEN"],
        19: ["NINETEENTH", "NINETEEN"], 20: ["TWENTIETH", "TWENTY"], 21: ["TWENTY FIRST", "TWENTY-FIRST", "TWENTY ONE"],
        22: ["TWENTY SECOND", "TWENTY-SECOND", "TWENTY TWO"], 23: ["TWENTY THIRD", "TWENTY-THIRD", "TWENTY THREE"],
        24: ["TWENTY FOURTH", "TWENTY-FOURTH", "TWENTY FOUR"], 25: ["TWENTY FIFTH", "TWENTY-FIFTH", "TWENTY FIVE"],
        26: ["TWENTY SIXTH", "TWENTY-SIXTH", "TWENTY SIX"], 27: ["TWENTY SEVENTH", "TWENTY-SEVENTH", "TWENTY SEVEN"],
        28: ["TWENTY EIGHTH", "TWENTY-EIGHTH", "TWENTY EIGHT"], 29: ["TWENTY NINTH", "TWENTY-NINTH", "TWENTY NINE"],
        30: ["THIRTIETH", "THIRTY"], 31: ["THIRTY FIRST", "THIRTY-FIRST", "THIRTY ONE"]
    }
    return DAYS_IN_WORDS.get(day, [])

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
    text_upper = extracted_text.upper()
    if qualification == "High School (10th)":
        keywords = ["SECONDARY", "SCHOOL", "10TH", "MATRIC", "HIGH SCHOOL", "अंक", "प्रमाण", "परीक्षा"]
        matches = sum(1 for kw in keywords if kw in text_upper)
        if matches < 1:
            raise ValueError("Validation Error: The uploaded document does not appear to be a valid High School (10th) Marksheet.")
        
        # Ensure it's not a 12th certificate
        negative_kws = ["SENIOR SECONDARY", "HIGHER SECONDARY", "12TH", "INTERMEDIATE", "XII", "PRE-UNIVERSITY", "SENIOR SCHOOL"]
        if any(kw in text_upper for kw in negative_kws):
            raise ValueError("Validation Error: Document appears to be a 12th standard marksheet, but 10th was expected.")
            
        # Ensure it's not a college/degree/diploma
        college_kws = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "DIPLOMA", "POLYTECHNIC", "ITI", "SEMESTER"]
        if any(kw in text_upper for kw in college_kws):
            raise ValueError("Validation Error: Document appears to be a college degree or diploma, but a 10th marksheet was expected.")

    elif qualification == "Higher Secondary (12th)":
        # Must contain 12th indicator
        keywords = ["HIGHER SECONDARY", "SENIOR SECONDARY", "12TH", "INTERMEDIATE", "XII", "PRE-UNIVERSITY", "SENIOR SCHOOL"]
        matches = sum(1 for kw in keywords if kw in text_upper)
        if matches < 1:
            raise ValueError("Validation Error: The uploaded document does not appear to be a valid 12th Standard Marksheet.")
            
        # Ensure it's not a college/degree/diploma
        college_kws = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "DIPLOMA", "POLYTECHNIC", "ITI", "SEMESTER"]
        if any(kw in text_upper for kw in college_kws):
            raise ValueError("Validation Error: Document appears to be a college degree or diploma, but a 12th marksheet was expected.")

    elif qualification == "Diploma / ITI":
        keywords = ["DIPLOMA", "POLYTECHNIC", "ITI", "INDUSTRIAL TRAINING", "TECHNICAL EDUCATION"]
        matches = sum(1 for kw in keywords if kw in text_upper)
        if matches < 1:
            raise ValueError("Validation Error: The uploaded document does not appear to be a valid Diploma/ITI certificate.")
            
        # Ensure it's not a degree
        degree_kws = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER"]
        if any(kw in text_upper for kw in degree_kws):
            raise ValueError("Validation Error: Document appears to be a university degree, but a Diploma/ITI was expected.")
            
        # Ensure it's not a simple school marksheet
        if any(kw in text_upper for kw in ["SECONDARY SCHOOL", "HIGH SCHOOL", "HIGHER SECONDARY", "INTERMEDIATE"]) and not any(kw in text_upper for kw in ["DIPLOMA", "POLYTECHNIC", "ITI"]):
            raise ValueError("Validation Error: Document appears to be a standard school marksheet, but a Diploma/ITI was expected.")

    elif qualification in ["Graduation (Bachelor's Degree)", "Post Graduation (Master's Degree)"]:
        # Check graduation keywords
        grad_keywords = ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "PROVISIONAL", "CONVOCATION", "SEMESTER", "COLLEGE", "GRADUATE", "B.A", "B.SC", "B.COM", "B.TECH", "B.E", "BCA", "BBA", "M.A", "M.SC", "M.COM", "M.TECH", "M.E", "MCA", "MBA"]
        matches = sum(1 for kw in grad_keywords if kw in text_upper)
        if matches < 1:
            raise ValueError(f"Validation Error: The uploaded document does not appear to be a valid {qualification} certificate.")
            
        # Ensure it's not a simple school marksheet (10th/12th)
        if any(kw in text_upper for kw in ["SECONDARY SCHOOL EXAM", "HIGH SCHOOL EXAM", "HIGHER SECONDARY EXAM", "INTERMEDIATE EXAM"]) and not any(kw in text_upper for kw in ["DEGREE", "UNIVERSITY", "BACHELOR", "MASTER", "SEMESTER"]):
            raise ValueError(f"Validation Error: Document appears to be a school marksheet, but a {qualification} was expected.")
            
        # If specific to master's, check for master's keywords
        if qualification == "Post Graduation (Master's Degree)":
            post_grad_keywords = ["MASTER", "POST GRADUATE", "M.A", "M.SC", "M.COM", "M.TECH", "M.E", "MCA", "MBA"]
            if not any(kw in text_upper for kw in post_grad_keywords):
                raise ValueError("Validation Error: Document appears to be a Bachelor's degree, but a Post Graduation (Master's) was expected.")
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
            # Month mapping for textual dates
            month_map = {
                "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
                "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
            }
            
            # Common DOB formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD
            # Textual formats: DD-Month-YYYY, DD Month YYYY (e.g., 15-Jan-1995, 15 January 1995)
            # Tolerates optional spaces and commas around separators due to OCR noise
            date_patterns = [
                r'(?<!\d)(\d{1,2})\s*[-/.,]\s*(\d{1,2})\s*[-/.,]\s*(\d{4})(?!\d)',
                r'(?<!\d)(\d{4})\s*[-/.,]\s*(\d{1,2})\s*[-/.,]\s*(\d{1,2})(?!\d)',
                r'(?<!\d)(\d{1,2})\s*[-/.,\s]\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*[-/.,\s]\s*(\d{4})(?!\d)'
            ]
            
            found_match = False
            extracted_dates = []
            
            # Log matching details for diagnostics
            debug_logs = []
            debug_logs.append(f"Candidate DOB: {candidate_dob}")
            debug_logs.append(f"Parsed DOB: {parsed_dob}")
            debug_logs.append(f"Text upper sample: {text_upper[:300]}...")
            
            # 1. Check numeric patterns
            for i, pattern in enumerate(date_patterns[:2]):
                matches = re.findall(pattern, text_upper)
                debug_logs.append(f"Pattern {i} ({pattern}): Matches: {matches}")
                for match in matches:
                    if i == 1: # YYYY-MM-DD pattern
                        year = match[0]
                        month = match[1].zfill(2)
                        day = match[2].zfill(2)
                        dt_str = f"{year}-{month}-{day}"
                        fmt = "%Y-%m-%d"
                    else: # DD-MM-YYYY pattern
                        day = match[0].zfill(2)
                        month = match[1].zfill(2)
                        year = match[2]
                        dt_str = f"{day}-{month}-{year}"
                        fmt = "%d-%m-%Y"
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
            
            # 2. Check textual month patterns
            if not found_match:
                matches = re.findall(date_patterns[2], text_upper)
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
                            
            # Fallback 1: Textual Date of Birth verification in words
            if not found_match:
                c_year_words = get_year_in_words(parsed_dob.year)
                c_month_words = get_month_in_words(parsed_dob.month)
                c_day_words = get_day_in_words(parsed_dob.day)
                
                has_month = any(m_word in text_upper for m_word in c_month_words)
                has_year = any(y_word in text_upper for y_word in c_year_words)
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
                    errors['dob'] = "Could not find any Date of Birth in the uploaded High School (10th) marksheet. Please ensure it is a valid marksheet containing your DOB."
                else:
                    errors['dob'] = f"DOB '{candidate_dob}' does not match the date found on the Marksheet."

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
    keywords = ["NSEIT", "CERTIFICATE", "CERTIFICATION","TESTING", "UIDAI", "AADHAAR"]
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
            # Fallback to word-based fuzzy match for certificate numbers to handle OCR errors (like 8 vs B, 5 vs S)
            words = re.findall(r'[A-Z0-9]{4,25}', extracted_text.upper())
            best_score = 0
            for w in words:
                best_score = max(best_score, fuzz.ratio(clean_cert, w))
            if best_score < 80:
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