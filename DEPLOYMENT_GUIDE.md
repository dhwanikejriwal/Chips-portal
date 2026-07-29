# CHiPS LMS Credentials Portal - Full Docker Production Deployment Guide
## Tailored for SDC Rocky Linux VM (Non-Sudo User Execution)
### VM Specs: 4 vCPU | 8GB RAM | 250GB Root HDD + 250GB Secondary Data HDD

---

## 📌 Executive Rules for Non-Sudo Deployment

1. **Zero Root Privilege Assumptions**: All application operations (`git clone`, `docker compose up`, `.env` edits, container management, logs, database backups) run strictly as the standard non-root SSH user (`$USER`).
2. **Test First Approach**: Every section begins with a **Verification Command** to test what is installed/open before running any action.
3. **SDC Admin Request Protocol**: If a task strictly requires system root access (like installing Docker daemon, adding `$USER` to `docker` group, or opening network firewall ports), an exact copy-paste request message for the SDC Admin is provided.

---

## 🔍 STEP 1: SDC Network Firewall & Port Verification

### A. Inbound Port Verification (Port 80 HTTP & Port 22 SSH)
* **Requirement**: End-users access portal over **Port 80** (HTTP). Admins access VM over **Port 22** (SSH). Internal ports (5000, 8000, 5432) do NOT need to be open on public firewall.

* 🧪 **Verification Commands (Run inside VM SSH terminal ONLY)**:
  ```bash
  # Test 1: Check active listening sockets and open ports:
  ss -tulpn

  # Test 2: Check local Firewalld open ports and allowed services:
  firewall-cmd --list-ports --list-services 2>/dev/null

  # Test 3: Test local HTTP response on Port 80:
  curl -I http://127.0.0.1:80 2>/dev/null || echo "Port 80 ready for Nginx container"
  ```

* 🟢 **If Port 80 & Port 22 are open / ready**: Proceed to Step 2.
* 🔴 **If Port 80 is blocked by SDC network policy**: Non-sudo user cannot modify network firewalls.
  * 📩 **Action Required — Send this request to SDC Network Team**:
    > *"Please open inbound network firewall Port 80 (HTTP) for VM IP `<YOUR_VM_PUBLIC_IP>` so users across Chhattisgarh can access the CHiPS Credentials Portal."*

---

### B. Outbound Port Verification (Port 443 HTTPS & Port 587 SMTP)
* **Requirement**: Outbound **Port 443** (HTTPS) is needed to pull Docker images (Docker Hub) and GitHub repository. Outbound **Port 587** is needed for sending candidate email credentials.

* 🧪 **Verification Command (Run inside VM SSH terminal)**:
  ```bash
  # Test 1: Outbound HTTPS (Docker Registry & GitHub):
  curl -I --connect-timeout 5 https://registry-1.docker.io/v2/
  curl -I --connect-timeout 5 https://github.com

  # Test 2: Outbound Email SMTP Port 587:
  curl -v telnet://smtp.office365.com:587
  ```

* 🟢 **If `HTTP/2 200` or `Connected to ...`**: Outbound access is OPEN!
* 🔴 **If Connection Times Out / Fails**:
  * 📩 **Action Required — Send this request to SDC Network Team**:
    > *"Please enable outbound network access on Port 443 (HTTPS) and Port 587 (SMTP) for VM IP `<YOUR_VM_PUBLIC_IP>`."*

---

## 🔍 STEP 2: Storage & Disk Allocation Verification

* **Requirement**: Verify storage space for candidate document uploads and PostgreSQL database files.

* 🧪 **Verification Command (Run inside VM SSH terminal)**:
  ```bash
  lsblk
  df -h
  ```

* 🛠️ **Non-Sudo Action**: Create data directories inside your user home directory:
  ```bash
  mkdir -p ~/chips_data/uploads
  mkdir -p ~/chips_data/postgres_db
  ```
  *(Storing data in `~/chips_data` guarantees your user account has full read/write permissions without needing root or `sudo`).*

---

## 🔍 STEP 3: Docker & Docker Compose Installation Verification

* **Requirement**: Docker Engine and Docker Compose Plugin must be installed and `$USER` must belong to the `docker` user group.

* 🧪 **Verification Command (Run inside VM SSH terminal)**:
  ```bash
  # Test 1: Check Docker Engine & permissions without sudo
  docker ps

  # Test 2: Check Docker Compose Plugin
  docker compose version
  ```

* 🟢 **If `docker ps` returns container headers without permission errors**:
  Docker is installed and `$USER` has non-root permission! Proceed to Step 4.

* 🔴 **Case A: `command not found: docker` (Docker Engine NOT installed)**:
  * Non-sudo user cannot install host system services like Docker daemon (`dockerd`).
  * 📩 **Action Required — Send this request to SDC System Admin**:
    ```text
    Please install Docker Engine and Docker Compose on VM IP <YOUR_VM_PUBLIC_IP> and add user $USER to docker group:

    sudo dnf update -y
    sudo dnf install -y dnf-utils git curl nano
    sudo dnf-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
    ```

* 🔴 **Case B: `permission denied while trying to connect to Docker daemon socket`**:
  * Docker is installed, but `$USER` is not in the `docker` group yet.
  * 🧪 **First try non-sudo group refresh (If already added by admin)**:
    ```bash
    newgrp docker
    docker ps
    ```
  * 📩 **If still Permission Denied, send this request to SDC System Admin**:
    > *"Please add user `$USER` to the `docker` group: `sudo usermod -aG docker $USER`."*

---

## 🔍 STEP 4: Git Installation & Code Base Setup

* 🧪 **Verification Command**:
  ```bash
  git --version
  ```

* 🛠️ **Step-by-Step Actions**:
  1. Clone codebase into user home directory:
     ```bash
     cd ~
     git clone https://github.com/dhwanikejriwal/Chips-portal.git chips-portal
     cd ~/chips-portal
     ```

  2. Create production `.env` environment file:
     ```bash
     nano ~/chips-portal/.env
     ```
     Paste the production configuration:
     ```env
     # PostgreSQL Database URL (Points to internal Docker postgres service)
     DATABASE_URL=postgresql+psycopg2://chips_admin:SuperSecurePassword2026!@db:5432/chips_db

     # Backend API Endpoint (Used by Flask proxy inside Docker network)
     BACKEND_API_URL=http://backend:8000/api

     # Security Keys (Random 64-char string)
     SECRET_KEY=e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7
     JWT_ALGORITHM=HS256
     ACCESS_TOKEN_EXPIRE_MINUTES=360

     # Production SMTP Email Settings
     MAIL_USERNAME=notifications@chips.gov.in
     MAIL_PASSWORD=ProductionSmtpAppPassword
     MAIL_FROM=notifications@chips.gov.in
     MAIL_PORT=587
     MAIL_SERVER=smtp.office365.com
     MAIL_FROM_NAME="CHiPS Admin Portal"
     ENABLE_LANGUAGE_TOGGLE=True
     ```

---

## 🐳 STEP 5: Docker Compose Stack Configuration

Verify the production multi-container setup in `~/chips-portal/docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: chips_postgres
    restart: always
    environment:
      POSTGRES_DB: chips_db
      POSTGRES_USER: chips_admin
      POSTGRES_PASSWORD: SuperSecurePassword2026!
    volumes:
      # Persistent PostgreSQL Database Data
      - ${HOME}/chips_data/postgres_db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chips_admin -d chips_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: chips_backend
    restart: always
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      # Persistent Candidate Document Uploads
      - ${HOME}/chips_data/uploads:/app/uploads

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    container_name: chips_frontend
    restart: always
    env_file: .env
    depends_on:
      - backend

  nginx:
    image: nginx:alpine
    container_name: chips_nginx
    restart: always
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./app/static:/var/www/static:ro
      - ${HOME}/chips_data/uploads:/var/www/uploads:ro
    depends_on:
      - frontend
      - backend
```

Verify `nginx.conf` in `~/chips-portal/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 25M;

    # Serve static assets directly via Nginx
    location /static/ {
        alias /var/www/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Serve uploaded candidate documents directly
    location /uploads/ {
        alias /var/www/uploads/;
        expires 7d;
    }

    # Proxy API requests to FastAPI Backend
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy Web Pages to Flask Frontend
    location / {
        proxy_pass http://frontend:5000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🚀 STEP 6: Build, Deploy & Initialize Database

Run all commands as your regular user (`$USER`) without `sudo`:

1. **Build and launch Docker Compose services**:
   ```bash
   cd ~/chips-portal
   docker compose up -d --build
   ```

2. **Seed initial baseline tables & admin accounts**:
   ```bash
   docker exec -it chips_backend python seed.py
   ```

3. 🧪 **Verify container status**:
   ```bash
   docker compose ps
   ```
   *Expected Output:*
   ```text
   NAME             IMAGE              COMMAND                  SERVICE    STATUS
   chips_postgres   postgres:15-alpine "docker-entrypoint.s…"   db         running (healthy)
   chips_backend    chips-backend      "gunicorn -w 4 -k uv…"   backend    running
   chips_frontend   chips-frontend     "gunicorn -w 4 app:a…"   frontend   running
   chips_nginx      nginx:alpine       "/docker-entrypoint.s…"   nginx      running
   ```

---

## 🧹 STEP 7: Maintenance & Day-to-Day Operations Playbook

### 1. How to Deploy Code Updates
When new code is pushed to GitHub:
```bash
cd ~/chips-portal
git pull origin main
docker compose up -d --build
```

### 2. How to View Live Container Logs
* **All Services**: `docker compose logs -f`
* **FastAPI Backend Logs**: `docker compose logs -f backend`
* **Flask Frontend Logs**: `docker compose logs -f frontend`
* **Nginx Web Logs**: `docker compose logs -f nginx`

### 3. How to Backup Database & Candidate Upload Files
All backups can be executed directly by `$USER` without `sudo`:

* **Manual PostgreSQL Database Backup**:
  ```bash
  docker exec -t chips_postgres pg_dump -U chips_admin chips_db | gzip > ~/chips_data/backup_$(date +%Y%m%d).sql.gz
  ```

* **Automated Daily Backup Cron Job** (Add to non-root user crontab via `crontab -e`):
  ```cron
  0 2 * * * docker exec -t chips_postgres pg_dump -U chips_admin chips_db | gzip > ~/chips_data/backup_\$(date +\%Y\%m\%d).sql.gz
  ```

---

## 📋 Summary Checklist for Non-Sudo Deployment

| Component | Test Command | Non-Sudo Action | SDC Admin Request Needed? |
| :--- | :--- | :--- | :--- |
| **Inbound Port 80** | `Test-NetConnection IP -Port 80` | None needed if Open | **Yes**, if `TcpTestSucceeded: False` |
| **Outbound Port 443** | `curl -I https://registry-1.docker.io/v2/` | None needed if Open | **Yes**, if connection times out |
| **Storage / Disk** | `df -h` | Use `~/chips_data` | **No** (Runs in user home) |
| **Docker Engine** | `docker ps` | Run container commands | **Yes**, if `docker` command missing or permission denied |
| **Code & Services** | `docker compose ps` | Run `docker compose up -d` | **No** (Runs 100% as `$USER`) |
