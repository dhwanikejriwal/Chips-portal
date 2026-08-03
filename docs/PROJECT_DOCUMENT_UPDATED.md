# CHiPS LMS Credentials & Kit Management Portal

## Module

Aadhaar Operator Onboarding, Kit Registration & Analytics Module

## Team Members

• [Information to be provided]

## Problem Statement

Prior to the deployment of this platform, the Chhattisgarh Infotech Promotion Society faced operational and administrative bottlenecks in managing Aadhaar enrollment centers and field operators across thirty-three districts. The legacy management framework relied on decentralized paper forms, fragmented spreadsheets, and unorganized email channels for candidate registration, document collection, and credential requests. Manual verification of mandatory NSEIT exam certificates, identity proofs, and operator credentials introduced severe processing delays, missing document records, and high risks of human error or unverified operator deployments. Furthermore, managing enrolment kit inventory, machine hardware specifications, and station allocations lacked a centralized tracking catalog. This fragmented workflow severely hindered district-wide operational oversight, delayed mandatory reporting, and prevented real-time monitoring of operator activities.

## Solution Proposed

An enterprise digital management platform was developed to streamline and automate Aadhaar operator lifecycle operations, credential issuance, and enrolment kit tracking across all districts. The platform provides unified portals for candidate self-registration, district coordinator application processing, and state-level administrative governance. Primary capabilities include automated document verification, centralized station catalog management, L1 and L2 kit registration workflows, role-based approval queues, automated transactional notifications, and analytical activity tracking. The system enables real-time monitoring of daily enrolment activity, detection of operator operational anomalies, and enforcement of reporting compliance. The expected outcome is a transparent, secure, and standardized operational framework that eliminates manual backlogs, reduces verification errors, prevents unauthorized operator activities, and optimizes district-wide Aadhaar center operations.

## Approach

1. Input: Candidates submit registration details and upload verification documents via the self-service portal, while field operators submit daily enrolment activity files.

2. Processing: The system executes role-based approval workflows across District Coordinators and State Admins, ingests daily activity files, and triggers document verification workflows.

3. Data Storage: Verified candidate profiles, credential logs, station allocations, hardware kit specifications, and daily activity logs are stored in a centralized relational database.

4. AI/ML Processing: The system applies Tesseract Optical Character Recognition and fuzzy text matching algorithms to extract data from uploaded identity documents, compute similarity scores, and detect verification mismatches.

5. Output: The system generates automated email notifications, releases LMS and NSEIT credentials, updates real-time district monitoring dashboards, and produces anomaly audit logs.

## Technology Used

| Component | Technology |
|---|---|
| Frontend | Flask, HTML5, Jinja2, Vanilla CSS, JavaScript |
| Backend | Python, FastAPI, Starlette |
| Database | PostgreSQL, SQLAlchemy ORM, Alembic |
| AI/ML | Tesseract OCR, Pytesseract, Fuzzy Matching |
| APIs | Asynchronous REST APIs, FastMail SMTP API |
| Frameworks | Flask, FastAPI, Celery |
| Deployment | Uvicorn ASGI Server, Redis |
| Other Tools | DuckDB, Pandas, Python-Calamine, SweetAlert2 |

## Relevant Screenshots

## Screenshot 1 – Candidate Self-Registration Portal

Purpose
Displays the candidate self-registration interface for online onboarding.

[Information to be provided]

Figure 1 – Candidate Self-Registration Portal

Description
• Interface supports dynamic bilingual language toggle.
• Candidate selects district and personal details.
• Required identity and educational documents uploaded.
• Form generates unique application tracking code.

## Screenshot 2 – District Coordinator Dashboard

Purpose
Displays the district management dashboard and verification queue.

[Information to be provided]

Figure 2 – District Coordinator Dashboard

Description
• Summary cards display district pending counts.
• Queue lists candidate requests for review.
• Built-in inspector previews uploaded proof documents.
• Action buttons enable application approval or rejection.

## Screenshot 3 – CHiPS State Admin Dashboard

Purpose
Displays state executive monitoring across thirty-three districts.

[Information to be provided]

Figure 3 – CHiPS State Admin Dashboard

Description
• Summary panel displays state-wide operational metrics.
• Table lists district performance indicators.
• Interactive map visualizes district status distribution.
• Control triggers generate analytical export files.

## Screenshot 4 – Operator Activity and Analytics Dashboard

Purpose
Displays analytical charts for operator enrolment activity tracking.

[Information to be provided]

Figure 4 – Operator Activity and Analytics Dashboard

Description
• Charts display daily enrolment volume trends.
• Analytics summarize demographic and biometric updates.
• Dropdown filters refine views by station.
• Audit panel highlights operational anomaly flags.
