# 🚀 GitHub Actions CI/CD — Secure Self-Hosted Runner Setup
### Rocky Linux SDC VM — Auto Deployment for Aadhar Project

---

## 📋 OVERVIEW

| Step | Where | What You Do |
|------|--------|-------------|
| Step 1 | GitHub Website | Get the runner registration token |
| Step 2 | VM (SSH as root) | Create a dedicated `github-runner` user |
| Step 3 | VM (SSH as root) | Clone the project under the new user |
| Step 4 | VM (as github-runner) | Download, register & start the runner |
| Step 5 | GitHub Website | Confirm runner is 🟢 Online |
| Step 6 | Local PC | Push code to trigger auto-deploy |

> ⚠️ **Why not root?** This is an Aadhar (PII) project. Running the runner as root means
> a compromised workflow can read/modify all system files, secrets, and user data.
> A dedicated `github-runner` user limits the blast radius significantly.

---

## STEP 1 — Get Your Runner Token from GitHub

Do this in your **browser on your local PC**.

1. Go to: `https://github.com/CMITF/Aadhar-Project`
2. Click **Settings** → **Actions** → **Runners**
3. Click **"New self-hosted runner"**
4. Select: **OS: Linux** | **Architecture: x64**
5. Copy the `./config.sh` command shown — it contains your unique token.

> ⏰ Token expires in **1 hour**. Complete setup before it expires.

---

## STEP 2 — Create a Dedicated `github-runner` User (as root on VM)

SSH into your VM as root:

```bash
ssh root@YOUR_VM_IP
```

Create the runner user and give it Docker access:

```bash
# Create the user with a home directory
useradd -m -s /bin/bash github-runner

# Set a password (save this somewhere safe)
passwd github-runner

# Add to docker group so it can run docker compose
usermod -aG docker github-runner

# Verify the group was added
groups github-runner
# Expected output: github-runner : github-runner docker
```

---

## STEP 3 — Clone the Project Under the Runner User (as root on VM)

The runner needs its own copy of the project to deploy from:

```bash
# Switch to the github-runner user's home
su - github-runner

# Clone the repository
git clone https://github.com/CMITF/Aadhar-Project.git ~/Aadhar-Project

# Copy the .env file from the root deployment (ask your team for this)
# OR create it fresh:
cp /root/Aadhar-Project/.env ~/Aadhar-Project/.env

# Verify
ls ~/Aadhar-Project
```

> ✅ Project should now be at: `/home/github-runner/Aadhar-Project`

---

## STEP 4 — Install & Register the Runner (as github-runner user)

Still in the `github-runner` session (or `su - github-runner` again):

### 4a. Download the GitHub Actions Runner

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz

tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz
```

### 4b. Register the Runner with GitHub

Paste the `./config.sh` command you copied from Step 1:

```bash
./config.sh --url https://github.com/CMITF/Aadhar-Project --token YOUR_TOKEN_HERE
```

At the prompts, press **Enter** for all (or set a custom runner name):

```
Runner group:   [Enter]
Runner name:    rocky-sdc-runner   ← recommended name
Extra labels:   [Enter]
Work folder:    [Enter]
```

> ✅ You should see: `Runner registered successfully.`

### 4c. Install as a Systemd Service (so it survives reboots)

Exit back to root first:

```bash
exit   # back to root shell
```

Install and start the service:

```bash
cd /home/github-runner/actions-runner

# Install the service (runs as github-runner user)
sudo ./svc.sh install github-runner

# Start the service
sudo ./svc.sh start

# Check status
sudo ./svc.sh status
```

Expected output:
```
● actions.runner.CMITF-Aadhar-Project.rocky-sdc-runner.service
   Active: active (running)
```

---

## STEP 5 — Confirm Runner is Online on GitHub

1. Go to: `https://github.com/CMITF/Aadhar-Project`
2. Click **Settings → Actions → Runners**
3. You should see your runner with a **🟢 Green dot** and status **"Idle"**

> ✅ If green — setup is complete!

---

## STEP 6 — Update the Workflow File Path

The workflow currently deploys from `/root/Aadhar-Project`.
Now that the runner runs as `github-runner`, update it to use the correct path.

The [`deploy.yml`](.github/workflows/deploy.yml) file should already be updated.
Verify the path inside it reads `/home/github-runner/Aadhar-Project`.

Then push to trigger a test deployment:

```bash
# On your local Windows PC
cd c:\Aadhar-Project
git add .
git commit -m "ci: switch to secure non-root runner setup"
git push origin main
```

Watch it run live at: `https://github.com/CMITF/Aadhar-Project/actions`

---

## 🔧 TROUBLESHOOTING

### `docker: permission denied`
```bash
# As root on VM:
usermod -aG docker github-runner
# Then restart the runner service:
sudo ./svc.sh stop
sudo ./svc.sh start
```

### `git pull` fails — authentication error
```bash
# As github-runner on VM, configure git credentials:
git config --global credential.helper store
git pull    # enter GitHub username + Personal Access Token when prompted
```

### Runner shows "Offline" on GitHub
```bash
# Check logs
sudo journalctl -u actions.runner.* -n 50
# Restart
sudo ./svc.sh stop && sudo ./svc.sh start
```

### Token expired (more than 1 hour passed)
- Go to GitHub → Settings → Actions → Runners → New self-hosted runner
- Get a fresh token and re-run `./config.sh` with it

---

## 📁 Directory Layout on VM After Setup

```
/home/github-runner/
├── actions-runner/          ← Runner installation
│   └── _work/               ← Where GitHub Actions jobs run
└── Aadhar-Project/          ← Your project (git pull deploys here)
    ├── .env                 ← Secrets (never committed to git)
    ├── docker-compose.yml
    └── ...
```

---

## ✅ FINAL CHECKLIST

- [ ] Created `github-runner` user with Docker group access
- [ ] Project cloned to `/home/github-runner/Aadhar-Project`
- [ ] `.env` file copied/created in the cloned project
- [ ] Runner downloaded and registered (`Runner registered successfully`)
- [ ] Service installed with `sudo ./svc.sh install github-runner`
- [ ] Service started and shows `active (running)`
- [ ] Runner shows 🟢 **Idle/Online** on GitHub → Settings → Actions → Runners
- [ ] `deploy.yml` path updated to `/home/github-runner/Aadhar-Project`
- [ ] Test push triggered the workflow successfully

---

## 🔐 Security Benefits of This Setup

| Without this setup (root) | With this setup (github-runner user) |
|---------------------------|--------------------------------------|
| Compromised job = full root access | Compromised job = limited user access only |
| Can read `/root/.env`, all secrets | Cannot access root's files |
| Can modify system binaries | Cannot install system packages |
| Can destroy the entire VM | Cannot affect system outside its home folder |
