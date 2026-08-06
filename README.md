# CHiPS LMS Credentials Portal

A modern, high-performance, decoupled web portal designed for the **Chhattisgarh Infotech Promotion Society (CHiPS)** to streamline Aadhaar operator onboarding, document verification, and the assignment of LMS/NSEIT credentials.

---

## 🏗️ Architecture & System Design

The project uses a decoupled microservice architecture:
* **Flask Frontend Proxy (Port 5000)**: Serves HTML views using modular **Vanilla CSS** + **Tailwind CSS**, handles user sessions, and renders dynamic popups using **SweetAlert2**.
* **FastAPI Backend Gateway (Port 8000)**: High-performance REST API handling business logic, Pydantic validation, JWT authentication, background tasks, and **SQLAlchemy ORM** connected to **PostgreSQL**.

```
User (Browser Client) <--> [Flask Proxy Server (Port 5000)] <--> [FastAPI Core Gateway (Port 8000)] <--> [PostgreSQL Database]
```

---

## 🌟 Key Features & User Roles

### 1. Candidate Onboarding & Tracking Portal
* **Registration**: Public portal for candidates to register as Aadhaar Operators (uploading Photo, Aadhaar, and Marksheets).
* **Application Tracking**: Candidates can track real-time onboarding status using their unique Request Code.
* **Credential Dashboard**: Approved candidates can log in to view assigned LMS/NSEIT credentials and update their profile.

### 2. District Coordinator (DC) Portal
* **District Queue**: Review and verify candidate onboarding requests for specific assigned districts.
* **Approval Workflow**: DCs can approve (auto-generating credentials) or reject (with mandatory remarks) candidate applications.
* **Automated Notifications**: Automated email notifications sent synchronously to candidates upon status changes.

### 3. CHiPS State Admin & EDM Portal
* **Centralized Dashboard**: Multi-district administrative overview of candidate applications, LMS statuses, and NSEIT IDs.
* **Global Data Export**: Filter and export detailed candidate data across districts to Excel/CSV formats.

---

## 🛠️ Technology Stack

* **Language & Runtime**: Python 3.12+
* **Frontend**: Flask 3.x, JavaScript (Fetch API), Tailwind CSS, Vanilla CSS, SweetAlert2
* **Backend**: FastAPI, Pydantic v2, Jose (JWT), Bcrypt, FastMail
* **Database**: PostgreSQL 14+, SQLAlchemy 2.0 ORM, Alembic Migrations
* **OCR & Document Processing**: `pytesseract` (Tesseract OCR), `pdf2image` (Poppler)

---

## 📋 Prerequisites & System Dependencies

Before setting up the project, ensure the required system dependencies and external binaries are installed on your system.

> 💡 **Note on Python Wrappers vs System Binaries**:
> Python packages like `pytesseract` and `pdf2image` in `requirements.txt` are **wrapper libraries**. They require the actual standalone C++ binary tools (`tesseract.exe` and `pdftoppm.exe`) installed on your operating system and added to your `PATH`.

### Required External Dependencies

| Dependency | Purpose | Python Wrapper | Official Download Link / Command |
| :--- | :--- | :--- | :--- |
| **Python 3.12+** | Core Programming Runtime | N/A | [Download Python 3.12+](https://www.python.org/downloads/) |
| **PostgreSQL 14+** | Relational Database Server | `psycopg2-binary` | [Download PostgreSQL](https://www.postgresql.org/download/) |
| **Tesseract OCR** | Document OCR binary | `pytesseract` | [Windows Installer (UB-Mannheim)](https://github.com/UB-Mannheim/tesseract/wiki) \| [Official Docs](https://tesseract-ocr.github.io/tessdoc/Installation.html) |
| **Poppler** | PDF rendering utilities | `pdf2image` | [Windows Releases](https://github.com/oschwartz10612/poppler-windows/releases) \| [Official Docs](https://poppler.freedesktop.org/) |
| **uv** *(Recommended)* | Fast package & version manager | N/A | `pip install uv` \| [Install Guide](https://docs.astral.sh/uv/getting-started/installation/) |

---

### ⚙️ Adding Tesseract & Poppler to System `PATH` (Windows)

1. **Tesseract OCR**: Run the installer from [UB-Mannheim Wiki](https://github.com/UB-Mannheim/tesseract/wiki). Default path: `C:\Program Files\Tesseract-OCR`.
2. **Poppler**: Download the latest release `.7z` / `.zip` from [poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases). Extract it to a directory (e.g. `C:\Program Files\poppler`) and locate its `bin` folder.
3. **Configure Environment Variables**:
   * Press `Win + R`, type `sysdm.cpl`, and press **Enter**.
   * Go to the **Advanced** tab → click **Environment Variables...**.
   * Under **User variables** or **System variables**, select `Path` and click **Edit...**.
   * Click **New** and add the directory paths:
     - `C:\Program Files\Tesseract-OCR`
     - `C:\Program Files\poppler\bin` (or path to your poppler `Library/bin` folder)
   * Click **OK** on all dialogs and **restart your terminal / IDE** for changes to take effect.

#### Linux / macOS Binaries Setup
* **Ubuntu/Debian**:
  ```bash
  sudo apt update && sudo apt install -y tesseract-ocr poppler-utils postgresql
  ```
* **macOS (Homebrew)**:
  ```bash
  brew install tesseract poppler postgresql
  ```

---

## 🚀 Step-by-Step Local Setup Guide

Follow these steps in order to set up and run the complete project locally on a new machine.

### Step 1: Clone the Repository
Open your terminal and navigate to your workspace directory:
```bash
git clone https://github.com/CMITF/Aadhar-Project.git
cd Aadhar-Project
```

---

### Step 2: Create & Activate Virtual Environment (Python 3.12)

* **Option A: Standard Python (If default Python is 3.12)**
  ```bash
  python -m venv .venv
  ```

* **Option B: Using `uv` (Recommended if local system Python version differs)**
  `uv` automatically fetches and pins Python 3.12 inside your project folder:
  ```bash
  uv venv .venv --python 3.12
  ```

* **Activate the Virtual Environment**:
  ```bash
  # Windows PowerShell:
  .venv\Scripts\Activate.ps1

  # Linux / macOS:
  source .venv/bin/activate
  ```

---

### Step 3: Install Dependencies
With your virtual environment active, install all required packages:
```bash
# Using standard pip:
pip install -r requirements.txt

# OR using uv:
uv pip sync requirements.txt
```

---

### Step 4: Configure Environment Variables (`.env`)

Create a `.env` file in the root directory based on `env_example.txt`:
```bash
# Windows PowerShell:
Copy-Item env_example.txt .env

# Linux / macOS:
cp env_example.txt .env
```

Open `.env` in your text editor and configure your database connection and application settings:

```env
# 1. Database Connection (Replace <username>, <password>, and <dbname> with your local Postgres values)
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/<dbname>
BACKEND_API_URL=http://localhost:8000/api

# 2. Security Settings (For FastAPI JWT and Flask Session)
SECRET_KEY=dev-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=360

# 3. Security Encryption Keys (Generate base64 keys using the command below)
# Command: python -c "import backend.utils.aadhar_crypto as a; print(a.generate_keys())"
AADHAR_HMAC_KEY=your_generated_hmac_key_base64
AADHAR_ENC_KEY=your_generated_enc_key_base64

# 4. Email SMTP Settings (For automated candidate approval/rejection emails)
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_FROM_NAME="CHiPS Admin Portal"
ENABLE_LANGUAGE_TOGGLE=True
UIDAI_RECIPIENT_EMAIL=recipient_email@example.com
```

---

### Step 5: Create Database, Apply Migrations & Run Seeder

#### Step 5a: Create Empty PostgreSQL Database
Before running migrations, ensure an empty PostgreSQL database with the `<dbname>` specified in your `.env` `DATABASE_URL` exists:

* **Using `psql` Terminal**:
  ```bash
  psql -U postgres -c "CREATE DATABASE <dbname>;"
  ```
* **Using pgAdmin / DBeaver GUI**: Right-click **Databases** → **Create** → **Database** → Name: `<dbname>`.

#### Step 5b: Apply Schema Migrations & Seeder Pipeline
Once the empty database exists, run these commands to build all database tables and load initial data:

```bash
# 1. Apply Alembic schema migrations (builds all database tables and relationships):
alembic upgrade head

# 2. Run master seeder pipeline (seeds roles, statuses, districts, admin accounts, and test data):
python seed.py
```

---

## 🏃 Running the Application

To run the complete application, open **two separate terminal windows** and activate your virtual environment (`.venv`) in both:

### Terminal 1: Start FastAPI Backend Gateway
```bash
uvicorn backend.main:app --reload --port 8000
```
* **Backend REST API**: `http://localhost:8000`
* **Interactive API Docs (Swagger UI)**: `http://localhost:8000/docs`

### Terminal 2: Start Flask Frontend Proxy
```bash
flask --app app run --port 5000 --debug
```
* **Frontend Web Portal**: `http://localhost:5000`


## 🧪 Verification & Troubleshooting

1. **Verify Backend**: Open `http://localhost:8000/docs` in your browser. You should see the Swagger API documentation.
2. **Verify Frontend**: Open `http://localhost:5000` in your browser. The candidate landing page should render cleanly.
3. **Tesseract / Poppler Errors**: If you encounter `TesseractNotFoundError` or `PDFInfoNotInstalledError` when processing documents, double-check that Tesseract and Poppler `bin` folders are correctly added to your system `PATH` and restart your terminal.
