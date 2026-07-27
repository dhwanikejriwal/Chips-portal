# CHiPS LMS Credentials Portal - Production Deployment Guide
## Tailored for Rocky Linux (4 vCPU | 8GB RAM | 250GB Root + 250GB Data HDD)

---

## 🏛️ SDC (State Data Center) Infrastructure & Security Checklist

Since this VM is hosted directly in the **State Data Center (SDC)** and already has a **Public IP assigned**, certain network firewalls and security policies are managed at the SDC network level. Use the checklist below to test and confirm each item directly from your VM terminal or local computer.

---

### 📋 Checklist & Exact Verification Commands

#### - [ ] **1. Inbound Network Firewall Ports (Port 80 & Port 22)**
* **Requirement**: Inbound `Port 80` (HTTP) allowed so users across Chhattisgarh can access the portal via `http://<YOUR_VM_PUBLIC_IP>`. `Port 22` allowed for SSH management.
* **How to Verify from your Local PC / Laptop**:
  ```powershell
  # Test HTTP Port 80 (Windows PowerShell):
  Test-NetConnection -ComputerName <YOUR_VM_PUBLIC_IP> -Port 80

  # Test SSH Port 22 (Windows PowerShell):
  Test-NetConnection -ComputerName <YOUR_VM_PUBLIC_IP> -Port 22
  ```
  *(If `TcpTestSucceeded : True`, the inbound firewall rule is OPEN and active!)*

* **How to Verify inside the VM**:
  ```bash
  # Check if Firewalld allows Port 80 locally:
  sudo firewall-cmd --list-ports --list-services
  ```

---

#### - [ ] **2. Outbound Network Firewall Ports (SMTP Port 587/25 & HTTPS Port 443)**
* **Requirement**: Outbound `Port 587/25` open to send candidate email notifications, and outbound `Port 443` open to download Docker images and Python packages.
* **How to Verify inside the VM Terminal**:
  ```bash
  # Test 1: Outbound HTTPS Port 443 (Docker & PyPI access):
  curl -I https://registry-1.docker.io/v2/
  curl -I https://pypi.org

  # Test 2: Outbound SMTP Email Port 587 (Office365 / Gmail SMTP):
  curl -v telnet://smtp.office365.com:587
  # OR if using Gmail:
  curl -v telnet://smtp.gmail.com:587
  ```
  *(If `curl` connects successfully and shows `Connected to ...`, outbound ports are OPEN!)*

---

#### - [ ] **3. Additional 250GB HDD Attachment**
* **Requirement**: Confirm the secondary 250GB disk is attached by SDC hypervisor.
* **How to Verify inside the VM Terminal**:
  ```bash
  # View all attached block devices and disk sizes:
  lsblk
  ```
  *Expected Output Example:*
  ```text
  NAME   MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
  sda      8:0    0   250G  0 disk 
  ├─sda1   8:1    0     1G  0 part /boot
  └─sda2   8:2    0   249G  0 part /
  sdb      8:16   0   250G  0 disk <--- YOUR SECONDARY 250GB HDD!
  ```

---

#### - [ ] **4. Local OS Firewall & SELinux Status**
* **Requirement**: Check Rocky Linux local `firewalld` and `SELinux` status.
* **How to Verify inside the VM Terminal**:
  ```bash
  # Check Firewall Status:
  sudo systemctl status firewalld

  # Check SELinux Status:
  sestatus
  ```

---

## 🚀 Recommended Deployment Strategy: Docker Compose

For **Rocky Linux**, the **best, cleanest, and easiest** approach for long-term maintenance is **Docker + Docker Compose** reverse-proxied with **Nginx**.

### Why Docker Compose is Best for Rocky Linux:
1. **No Python Mismatches**: Rocky Linux's default package repositories ship with Python 3.9/3.11. Docker guarantees your application runs on **Python 3.12+** in an isolated environment without needing EPEL or manual Python compilation.
2. **Additional 250GB HDD Utilization**: We will mount your extra 250GB disk at `/mnt/chips_data` and map Docker volumes for **PostgreSQL database data** and **uploaded candidate documents**. This keeps your 250GB Root OS partition clean and prevents disk full crashes.
3. **Easiest Maintenance**: Upgrading the application in production requires just **2 commands**: `git pull` and `docker compose up -d --build`.
4. **Optimal System Resource Usage**: Your 4 vCPUs and 8GB RAM are plenty to run PostgreSQL, FastAPI, Flask, and Nginx with minimal overhead (~1.5GB RAM total used by containers).

---

## 📊 Disk Space Allocation Plan

| Storage Partition | Size | Purpose |
| :--- | :--- | :--- |
| **Root HDD (`/`)** | 250 GB | Operating System, Docker Engine, Log files, System Packages |
| **Additional HDD (`/mnt/chips_data`)** | 250 GB | **Candidate Document Uploads** (`/mnt/chips_data/uploads`) + **PostgreSQL Data** (`/mnt/chips_data/postgres_db`) |

---

## 🛠️ Step-by-Step Rocky Linux Deployment Guide

### Phase 1: Disk Setup (Mounting the 250GB Additional HDD)

1. Identify the additional disk device name (e.g., `/dev/sdb` or `/dev/nvme1n1`):
```bash
lsblk
```

2. Format the additional 250GB disk with `ext4` (Skip if already formatted):
```bash
sudo mkfs.ext4 /dev/sdb
```

3. Create mount point `/mnt/chips_data` and mount the drive:
```bash
sudo mkdir -p /mnt/chips_data
sudo mount /dev/sdb /mnt/chips_data
```

4. Make the mount persistent across VM reboots by editing `/etc/fstab`:
```bash
# Get UUID of /dev/sdb
sudo blkid /dev/sdb

# Add to /etc/fstab:
# UUID=xxxx-xxxx-xxxx-xxxx  /mnt/chips_data  ext4  defaults  0  2
sudo nano /etc/fstab
```

5. Create data directories on the additional drive:
```bash
sudo mkdir -p /mnt/chips_data/uploads
sudo mkdir -p /mnt/chips_data/postgres_db
sudo chmod -R 777 /mnt/chips_data
```

---

### Phase 2: System Preparation & Installing Docker on Rocky Linux

1. Update Rocky Linux system packages:
```bash
sudo dnf update -y
sudo dnf install -y dnf-utils git curl nano
```

2. Add Docker CE official repository & install Docker Engine:
```bash
sudo dnf-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

3. Enable and start Docker service:
```bash
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and log back in or run: newgrp docker
```

4. Check Local OS Firewall Status (ReadOnly - Do not alter if managed by SDC):
```bash
# Just inspect if firewalld is active or managed by SDC:
sudo systemctl status firewalld
sudo firewall-cmd --list-ports --list-services
```

---

### Phase 3: Project Setup & Docker Configuration

1. Clone codebase to `/var/www/chips-portal`:
```bash
sudo mkdir -p /var/www/chips-portal
sudo chown -R $USER:$USER /var/www/chips-portal
cd /var/www/chips-portal

git clone https://github.com/dhwanikejriwal/Chips-portal.git .
```

2. Create Production `.env` file:
```bash
nano /var/www/chips-portal/.env
```

Paste your production secrets:
```env
# Production PostgreSQL URL (Points to internal Docker postgres service)
DATABASE_URL=postgresql+psycopg2://chips_admin:SuperSecurePassword2026!@db:5432/chips_db

# Backend API Endpoint (Used by Flask proxy inside Docker network)
BACKEND_API_URL=http://backend:8000/api

# Security Keys (Generate a random 64-char string)
SECRET_KEY=e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=360

# Production SMTP Email Settings for CHiPS Notifications
MAIL_USERNAME=notifications@chips.gov.in
MAIL_PASSWORD=ProductionSmtpAppPassword
MAIL_FROM=notifications@chips.gov.in
MAIL_PORT=587
MAIL_SERVER=smtp.office365.com
MAIL_FROM_NAME="CHiPS Admin Portal"
ENABLE_LANGUAGE_TOGGLE=True
```

3. Ensure production Dockerfiles exist:

#### `Dockerfile.backend`
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

COPY . .

EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "backend.main:app", "--bind", "0.0.0.0:8000"]
```

#### `Dockerfile.frontend`
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 5000
CMD ["gunicorn", "-w", "4", "app:app", "--bind", "0.0.0.0:5000"]
```

4. Create production `docker-compose.yml`:
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
      # Stores Database files on the Additional 250GB HDD
      - /mnt/chips_data/postgres_db:/var/lib/postgresql/data
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
      # Stores Candidate Uploaded Photos/Documents on Additional 250GB HDD
      - /mnt/chips_data/uploads:/app/uploads

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
      - /mnt/chips_data/uploads:/var/www/uploads:ro
    depends_on:
      - frontend
      - backend
```

5. Create `nginx.conf` for reverse proxy:
```nginx
server {
    listen 80;
    server_name _; # Accepts all requests directly via VM Public IP

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

    # Proxy API calls directly to FastAPI Backend
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

### Phase 4: Launch Application & Initialize Database

1. Build and start containers in background:
```bash
cd /var/www/chips-portal
docker compose up -d --build
```

2. Seed initial baseline database tables & default accounts:
```bash
docker exec -it chips_backend python seed.py
```

3. Verify running containers:
```bash
docker compose ps
```

---

## 🧹 Maintenance & Ops Playbook (How to Manage Day-to-Day)

### 1. How to Update Code in Production
When you have new updates pushed to GitHub:
```bash
cd /var/www/chips-portal
git pull origin main
docker compose up -d --build
```
*(Zero downtime / minimal restart time for backend & frontend!)*

### 2. How to View Live Logs
* **All Services**: `docker compose logs -f`
* **Backend FastAPI Logs**: `docker compose logs -f backend`
* **Frontend Flask Logs**: `docker compose logs -f frontend`
* **Nginx Access Logs**: `docker compose logs -f nginx`

### 3. How to Backup Database & Uploaded Candidate Files
Because data lives on your additional 250GB disk (`/mnt/chips_data`), backing up is super simple:

* **PostgreSQL Backup**:
```bash
docker exec -t chips_postgres pg_dump -U chips_admin chips_db | gzip > /mnt/chips_data/backup_$(date +%Y%m%d).sql.gz
```
* **Daily Cron Job setup**: Add this to `crontab -e`:
```cron
0 2 * * * docker exec -t chips_postgres pg_dump -U chips_admin chips_db | gzip > /mnt/chips_data/backup_$(date +\%Y\%m\%d).sql.gz
```

---

## 💡 Summary: Why This Choice Gives You Peace of Mind
* **System Specs**: Your 4 vCPU / 8GB RAM will run this stack smoothly at ~15-25% CPU usage.
* **Disk Safety**: Storing all uploads and PostgreSQL database files on `/mnt/chips_data` guarantees your Rocky Linux root filesystem will never fill up.
* **OS Stability**: Rocky Linux is enterprise-grade and stable. Docker isolates Python 3.12 dependencies so OS updates will never break your portal.
