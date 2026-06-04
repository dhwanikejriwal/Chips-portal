# CHiPS LMS Credentials Portal

A modern, high-performance, decoupled web portal designed for the **Chhattisgarh Infotech Promotion Society (CHiPS)** to streamline the registration of Aadhaar operators and the assignment of LMS video credentials.

## 🏗️ Decoupled Architecture

The project is built using a cleanly decoupled architecture:
*   **Flask Frontend Proxy (Port 5000)**: Serves pure HTML layouts utilizing **HTMX** for smooth dynamic page swaps without full page reloads, and modular **Vanilla CSS** + **Tailwind CSS** for premium styling.
*   **FastAPI Backend Gateway (Port 8000)**: A high-performance RESTful API that handles all business logic, Pydantic data validation, JWT-based authentication, and direct database queries using **SQLAlchemy ORM** connected to a **PostgreSQL** database.

```
graph LR
    User([Browser Client]) <-->|HTMX / HTML| Flask[Flask Proxy Server (Port 5000)]
    Flask <-->|REST API / JWT| FastAPI[FastAPI Core Server (Port 8000)]
    FastAPI <-->|SQLAlchemy| DB[(PostgreSQL Database)]
```

---

## 🌟 Key Features

### 1. District Coordinator (DC) Portal
*   **Operator Registration**: Allows DCs to register new operators. Form validation errors are dynamically output as a floating card alert below the header instead of appending inside lists.
*   **Field Locking**: Automatically locks the **District** field to the DC's assigned district (pulled from session), ensuring DCs cannot submit operators for other districts.
*   **Form State Retention**: The form preserves all user-entered inputs in the event of validation errors (e.g. short phone number), eliminating redundant refilling.
*   **Time Period Date Filters**: Real-time client-side dropdown filters allowing filtering by **All Time**, **Today** (day-wise), **This Month** (month-wise, default), or **This Year** (year-wise).
*   **Queue prepending**: Newly registered requests immediately appear at the top of the history list in real-time.

### 2. CHiPS Admin Portal
*   **Pending Queue**: Displays all pending operator registration requests from all districts in real-time.
*   **District & Date Filtering**: Dynamic client-side dropdown filters to search by name/email, filter by district, or filter by date period (day, month, or year-wise).
*   **Secure Assignment Actions**: Admin-specific form action allowing the manual assignment of dynamic login credentials (ID and Password) for each operator.
*   **Row Autofill Isolation**: Forms utilize request-specific input names (e.g. `generated_login_id_5`), preventing browser autofill features from erroneously carrying over values to adjacent queue rows.

### 3. Localization & Formatting
*   **IST Timezone Alignment**: All database timestamps use Indian Standard Time (IST, UTC+5:30) representations.
*   **Consistent Formatting**: Timestamps are parsed and returned as user-friendly `YYYY-MM-DD HH:MM:SS` strings.

---

## 🛠️ Technology Stack

*   **Language**: Python 3.10+
*   **Frontend**: Flask, HTMX, Tailwind CSS, Modular Vanilla CSS
*   **Backend**: FastAPI, Pydantic, Jose (JWT), Bcrypt
*   **Database**: PostgreSQL, SQLAlchemy ORM, Alembic migrations

---

## 📂 Project Structure

```
Chips-portal/
├── app/                  # Flask Frontend Application
│   ├── static/           # Static CSS and Images
│   │   └── css/
│   │       ├── common.css          # Shared layout and grid styles
│   │       ├── dc_dashboard.css    # DC registration specific styles
│   │       └── chips_dashboard.css # Admin table specific styles
│   ├── templates/        # HTML Layout Templates
│   │   ├── auth/         # Login template
│   │   ├── chips/        # Admin dashboard templates
│   │   └── dc/           # DC portal templates
│   └── __init__.py       # Flask routing and proxy endpoints
├── backend/              # FastAPI Backend Gateway
│   ├── routers/          # Route handlers (auth, lms)
│   ├── database.py       # SQLAlchemy database connection session
│   ├── models.py         # Database model definitions & IST helpers
│   └── main.py           # FastAPI entrypoint and CORS configurations
├── seed.py               # Database initialization and baseline seeder
└── .env                  # Configuration variables (DB URL, Flask Configs)
```

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+ installed
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
    Create a `.env` file in the root directory (based on the sample) and configure your database URI:
    ```env
    FLASK_APP=app:create_app
    FLASK_ENV=development
    SECRET_KEY=dev-secret-key-replace-in-production
    DATABASE_URL=postgresql+psycopg2://<username>:<password>@localhost:5432/<dbname>
    ```

5.  **Initialize & Seed the Database**:
    Run the seeder script to build schemas and insert baseline test accounts:
    ```bash
    python seed.py
    ```

### Running the Applications

Open two separate terminals and activate your virtual environment in both:

*   **Terminal 1: Start the FastAPI Backend Gateway**
    ```bash
    uvicorn backend.main:app --reload
    ```
    *(Starts the backend core on `http://127.0.0.1:8000`)*

*   **Terminal 2: Start the Flask Frontend Proxy**
    ```bash
    flask --app app run --port 5000 --debug
    ```
    *(Starts the user portal on `http://127.0.0.1:5000`)*

---

## 🔑 Baseline Seed Accounts

The `seed.py` script populates two test accounts by default:

| Role | Username | Password | District |
| :--- | :--- | :--- | :--- |
| **District Coordinator (DC)** | `dc_raipur` | `password123` | Raipur |
| **CHiPS Administrator** | `chips_admin` | `admin123` | All Districts |
