# CHiPS LMS Credentials Portal

A modern, high-performance, decoupled web portal designed for the **Chhattisgarh Infotech Promotion Society (CHiPS)** to streamline Aadhaar operator onboarding, document verification, and the assignment of LMS/NSEIT credentials.

## 🏗️ Architecture

The project uses a decoupled microservice-like architecture:
*   **Flask Frontend Proxy (Port 5000)**: Serves HTML layouts using modular **Vanilla CSS** + **Tailwind CSS**. Uses **SweetAlert2** for interactive popups and native `fetch` API for dynamic data interactions without full page reloads.
*   **FastAPI Backend Gateway (Port 8000)**: A high-performance REST API handling business logic, Pydantic validation, JWT authentication, background email tasks, and **SQLAlchemy ORM** connected to **PostgreSQL**.



    User([Browser Client]) <-->|Fetch API / HTML| Flask[Flask Proxy Server (5000)]
    
    Flask <-->|REST API / JWT| FastAPI[FastAPI Core Server (8000)]
    
    FastAPI <-->|SQLAlchemy| DB[(PostgreSQL Database)]


## 🌟 Key Features

### 1. Candidate Onboarding & Tracking
*   **Registration**: Public portal for candidates to register as Aadhaar Operators (uploading Photo, Aadhaar, and Marksheets).
*   **Tracking**: Candidates can track their application status using their Request Code.
*   **Dashboard**: Approved candidates can log in to view their assigned LMS/NSEIT credentials and reset their password.

### 2. District Coordinator (DC) Portal
*   **Pending Queue**: View and review new candidate onboarding requests specific to their district.
*   **Approval Workflow**: DCs can Approve (auto-generates credentials) or Reject (with mandatory remarks) requests.
*   **Automated Emails**: Integrated email notifications sent synchronously to candidates upon approval/rejection with failure retry popups.
*   **Log History & Export**: DCs can filter, view details, and export candidate data to CSV.

### 3. CHiPS Admin & EDM Portal
*   **Centralized View**: Displays all approved requests across all districts.
*   **LMS & NSEIT Management**: Assign and track LMS statuses and NSEIT IDs for approved candidates.
*   **Global Export**: Bulk export candidate data with robust filtering by district and time periods.

---

## 🛠️ Technology Stack

*   **Language**: Python 3.12+
*   **Frontend**: Flask, JavaScript (Fetch), Tailwind CSS, Vanilla CSS, SweetAlert2
*   **Backend**: FastAPI, Pydantic, Jose (JWT), Bcrypt, FastMail
*   **Database**: PostgreSQL, SQLAlchemy ORM, Alembic migrations

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.12+ installed
*   PostgreSQL running locally

### Installation & Setup

1.  **Clone the Repository** and navigate into the workspace:
    ```bash
    cd Chips-portal
    ```

2.  **Create and Activate a Virtual Environment**:
    ```bash
    python -m venv .venv
    # Windows PowerShell:
    .venv\Scripts\Activate.ps1
    # Linux/Mac:
    source .venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**:
    Create a `.env` file in the root directory (based on `.env.example`) and configure your database and email SMTP:
    ```env
    DATABASE_URL=postgresql+psycopg2://<username>:<password>@localhost:5432/<dbname>
    BACKEND_API_URL=http://localhost:8000/api

    # Security settings (for FastAPI JWT and Flask Session)

    SECRET_KEY=dev-secret-key-replace-in-production
    JWT_ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=360

    # SMTP settings for fastapi-mail
    MAIL_USERNAME=your_email@gmail.com
    MAIL_PASSWORD=your_app_password
    MAIL_FROM=your_email@gmail.com
    MAIL_PORT=587
    MAIL_SERVER=smtp.gmail.com
    MAIL_FROM_NAME="CHiPS Admin Portal"
    ENABLE_LANGUAGE_TOGGLE=True

    ```

5.  **Initialize & Seed the Database**:
    Run the master seeder script to build schemas and execute all 4 database seeders in `seed_files/`:
    ```bash
    python seed.py
    ```

### Running the Applications

Open two separate terminals and activate your virtual environment in both:

*   **Terminal 1: Start the FastAPI Backend Gateway**
    ```bash
    uvicorn backend.main:app --reload
    ```

*   **Terminal 2: Start the Flask Frontend Proxy**
    ```bash
    flask --app app run --port 5000 --debug
    ```
