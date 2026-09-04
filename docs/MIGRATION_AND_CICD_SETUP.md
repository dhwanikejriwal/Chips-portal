# 🔐 Full Migration Guide: Root → Aadhar User + CI/CD Setup
### Rocky Linux SDC VM — Aadhar Project Secure Migration

---

## 📋 What This Guide Does

1. Gives `aadhar` user `sudo` + `docker` privileges
2. Stops all Docker containers running under root
3. Moves the project from `/root/Aadhar-Project` → `/home/aadhar/Aadhar-Project`
4. Preserves the PostgreSQL database (no data loss)
5. Sets up the GitHub Actions self-hosted runner under `aadhar`
6. Cleans up root completely
7. Verifies everything works end-to-end

> ⏱️ Estimated time: 15–20 minutes
> 🖥️ You need: SSH access to the VM as root + a browser open on GitHub

---

## ⚠️ Before You Begin

- [ ] Make sure you have **root SSH access** to the VM
- [ ] Have your **GitHub repository URL** ready: `https://github.com/CMITF/Aadhar-Project`
- [ ] Keep your **browser open** on GitHub — you'll need a fresh runner token midway
- [ ] Do **NOT** run `docker compose down -v` at any point — the `-v` flag deletes the database!

---

## PHASE 1 — Grant Privileges to `aadhar` User

> Run all commands in this phase **as root** on the VM

### 1.1 — SSH into your VM as root

```bash
ssh root@YOUR_VM_IP_ADDRESS
```

### 1.2 — Add `aadhar` to the `wheel` group (gives sudo access)

```bash
usermod -aG wheel aadhar
```

### 1.3 — Add `aadhar` to the `docker` group (gives docker access without sudo)

```bash
usermod -aG docker aadhar
```

### 1.4 — Verify both groups are applied

```bash
groups aadhar
```

✅ Expected output:
```
aadhar : aadhar wheel docker
```

---

## PHASE 2 — Stop Root's Docker Containers (Keep Database Safe)

> Still as **root** on the VM

### 2.1 — Navigate to the root project and stop containers

```bash
cd /root/Aadhar-Project
```

```bash
docker compose down
```

> ✅ This stops containers but **keeps all volumes (database) intact**
> ❌ Never add `-v` here — that deletes the database permanently

### 2.2 — Confirm containers are stopped

```bash
docker ps
```

✅ Expected: Empty list — no running containers.

### 2.3 — Confirm volumes still exist (database is safe)

```bash
docker volume ls
```

✅ You should see entries like:
```
local    aadhar-project_postgres_data
local    aadhar-project_uploads_data
```

---

## PHASE 3 — Move Project Files to `aadhar` User

> Still as **root** on the VM

### 3.1 — Copy entire project from root to aadhar's home

```bash
cp -r /root/Aadhar-Project /home/aadhar/Aadhar-Project
```

### 3.2 — Give aadhar ownership of all copied files

```bash
chown -R aadhar:aadhar /home/aadhar/Aadhar-Project
```

### 3.3 — Verify the copy and ownership

```bash
ls -la /home/aadhar/Aadhar-Project
```

✅ All files should show `aadhar aadhar` as owner.

### 3.4 — Confirm the .env file is present (critical — contains DB passwords)

```bash
cat /home/aadhar/Aadhar-Project/.env
```

✅ You should see your environment variables (DB_PASSWORD, SECRET_KEY, etc.)

> If `.env` is missing, copy it manually:
> ```bash
> cp /root/Aadhar-Project/.env /home/aadhar/Aadhar-Project/.env
> chown aadhar:aadhar /home/aadhar/Aadhar-Project/.env
> ```

---

## PHASE 4 — Stop Root's GitHub Actions Runner (if running)

> Still as **root** on the VM

### 4.1 — Check if a runner service is running under root

```bash
sudo systemctl list-units | grep actions.runner
```

### 4.2 — If a runner service exists, stop and uninstall it

```bash
cd ~/actions-runner

sudo ./svc.sh stop
sudo ./svc.sh uninstall
```

### 4.3 — Remove root's runner directory

```bash
rm -rf ~/actions-runner
```

---

## PHASE 5 — Switch to `aadhar` and Verify Privileges

### 5.1 — Switch to aadhar user

```bash
su - aadhar
```

> The `-` flag is important — it loads the full login environment including updated groups.

### 5.2 — Verify docker works (no sudo needed)

```bash
docker ps
```

✅ Expected: Empty list (no error about permissions)

> ❌ If you see `permission denied` — exit and SSH back in fresh as `aadhar`:
> ```bash
> exit
> ssh aadhar@YOUR_VM_IP_ADDRESS
> docker ps
> ```

### 5.3 — Verify sudo works

```bash
sudo whoami
```

✅ Expected output: `root`

### 5.4 — Verify the project is accessible

```bash
ls ~/Aadhar-Project
```

✅ You should see your project files: `docker-compose.yml`, `Dockerfile`, `.env`, etc.

---

## PHASE 6 — Start Docker Containers Under `aadhar`

> As **aadhar** user

### 6.1 — Navigate to the project

```bash
cd ~/Aadhar-Project
```

### 6.2 — Start all containers (this reuses the existing database!)

```bash
docker compose up -d
```

### 6.3 — Confirm all containers are running

```bash
docker ps
```

✅ Expected — all 4 containers running:
```
NAMES               STATUS
chips-nginx         Up
chips-frontend      Up
chips-backend       Up
chips-postgres      Up
```

### 6.4 — Confirm database data is intact

```bash
docker exec -it chips-postgres psql -U postgres -d chips_db_new -c "\dt"
```

✅ You should see your database tables listed — data is preserved!

---

## PHASE 7 — Set Up GitHub Actions Runner Under `aadhar`

> As **aadhar** user

### 7.1 — Get a fresh token from GitHub

1. Open browser → go to `https://github.com/CMITF/Aadhar-Project`
2. Click **Settings → Actions → Runners**
3. Click **"New self-hosted runner"**
4. Select **OS: Linux** | **Architecture: x64**
5. Copy the `./config.sh --url ... --token ...` line

> ⏰ Token is valid for **1 hour only** — complete the next steps quickly

### 7.2 — Create runner directory and download

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
```

```bash
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
```

```bash
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz
```

### 7.3 — Verify the extraction

```bash
ls -la
```

✅ You should see: `config.sh`, `run.sh`, `svc.sh`

### 7.4 — Register the runner with GitHub

Paste the command copied from GitHub in Step 7.1:

```bash
./config.sh --url https://github.com/CMITF/Aadhar-Project --token YOUR_TOKEN_HERE
```

At the interactive prompts:

```
Enter the name of the runner group:  [press Enter]
Enter the name of runner:            rocky-sdc-runner    ← type this, then Enter
This runner will have labels:        self-hosted, Linux, X64
Enter any additional labels:         [press Enter]
Enter name of work folder:           [press Enter]
```

✅ Expected:
```
Runner registered successfully.
Settings Saved.
```

### 7.5 — Install runner as a systemd service (auto-starts on reboot)

```bash
sudo ./svc.sh install
```

```bash
sudo ./svc.sh start
```

### 7.6 — Check service status

```bash
sudo ./svc.sh status
```

✅ Expected:
```
● actions.runner.CMITF-Aadhar-Project.rocky-sdc-runner.service
   Active: active (running)
```

---

## PHASE 8 — Confirm Runner is Online on GitHub

1. Go to `https://github.com/CMITF/Aadhar-Project`
2. Click **Settings → Actions → Runners**
3. Your runner `rocky-sdc-runner` should show 🟢 **Idle**

✅ If green — the runner is live and ready!

---

## PHASE 9 — Clean Up Root

> SSH back as **root** (or `sudo su` from aadhar)

### 9.1 — Remove the project from root's home

```bash
rm -rf /root/Aadhar-Project
```

### 9.2 — Verify root is clean

```bash
ls /root
```

✅ `Aadhar-Project` should no longer appear.

### 9.3 — Confirm Docker still works fine

```bash
docker ps
```

✅ All 4 containers should still be running under `aadhar`'s docker compose.

---

## PHASE 10 — Test the Full CI/CD Pipeline

> On your **local Windows PC**

### 10.1 — Make a small change and push to main

```bash
cd c:\Aadhar-Project
echo "# migration complete" >> README.md
git add .
git commit -m "ci: migrated runner to aadhar user - test deploy"
git push origin main
```

### 10.2 — Watch the deployment live

1. Go to `https://github.com/CMITF/Aadhar-Project`
2. Click the **Actions** tab
3. Watch **"Auto Deploy to SDC VM"** workflow run
4. It should complete in **30–60 seconds**

✅ Green checkmark = deployment successful! 🎉

---

## 🔧 TROUBLESHOOTING

### `docker ps` still shows permission denied after adding to docker group
```bash
# Log out completely and SSH back in fresh
exit
ssh aadhar@YOUR_VM_IP
docker ps
```

### `git pull` fails — authentication error during deployment
```bash
# As aadhar, configure git credentials
cd ~/Aadhar-Project
git config --global credential.helper store
git pull    # enter GitHub username + Personal Access Token (not password)
```

> For the PAT: GitHub → Settings → Developer Settings → Personal Access Tokens → Generate new token (classic) with `repo` scope

### `sudo ./svc.sh install` fails — sudo not found or denied
```bash
# As root, verify wheel group was applied
grep aadhar /etc/group
# Should show: wheel:x:10:aadhar

# If not, add manually
usermod -aG wheel aadhar
# Then logout and log back in as aadhar
```

### Runner shows "Offline" on GitHub
```bash
# Check logs
sudo journalctl -u actions.runner.* -n 50

# Restart the service
sudo ./svc.sh stop
sudo ./svc.sh start
```

### Token expired (more than 1 hour passed)
- Go to GitHub → Settings → Actions → Runners → New self-hosted runner
- Copy a fresh token and re-run `./config.sh`

### Database missing after migration
```bash
# Check volumes still exist
docker volume ls | grep aadhar

# If postgres_data volume exists, data is safe — just restart:
cd ~/Aadhar-Project
docker compose up -d
```

---

## ✅ FINAL CHECKLIST

### Privileges
- [ ] `aadhar` added to `wheel` group (sudo works)
- [ ] `aadhar` added to `docker` group (docker works without sudo)

### Migration
- [ ] Project copied to `/home/aadhar/Aadhar-Project`
- [ ] `.env` file present and correct
- [ ] All files owned by `aadhar:aadhar`

### Docker
- [ ] All 4 containers running under `aadhar` (`docker ps` shows chips-postgres, chips-backend, chips-frontend, chips-nginx)
- [ ] Database tables intact (`\dt` shows tables in psql)

### CI/CD Runner
- [ ] Runner downloaded to `/home/aadhar/actions-runner/`
- [ ] Runner registered successfully (`Settings Saved`)
- [ ] Service installed and `active (running)`
- [ ] Runner shows 🟢 **Idle** on GitHub → Settings → Actions → Runners

### Cleanup
- [ ] `/root/Aadhar-Project` deleted
- [ ] Root's old runner service removed

### Verification
- [ ] Test push from local PC triggered the workflow
- [ ] Workflow completed with ✅ green checkmark
- [ ] App is accessible and working on the VM

---

## 📁 Final Directory Layout on VM

```
/home/aadhar/
├── Aadhar-Project/              ← Main project (owned by aadhar)
│   ├── .env                     ← Secrets (never in git)
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── ...
└── actions-runner/              ← GitHub Actions runner
    └── _work/                   ← Where deployment jobs run

/var/lib/docker/volumes/
├── aadhar-project_postgres_data ← PostgreSQL data (safe!)
└── aadhar-project_uploads_data  ← Uploaded files (safe!)
```
