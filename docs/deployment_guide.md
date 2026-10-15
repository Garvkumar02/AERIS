# AERIS Production Deployment & Operations Guide

## 1. Architectural Overview

AERIS (**Autonomous Enterprise Record & Identification System**) is engineered for high-assurance, tamper-evident campus identity, attendance, and spatial access management. 

In a production environment, AERIS utilizes a three-tier architecture:
1. **Edge Gateway (Nginx Reverse Proxy)**: Terminates TLS 1.2/1.3, applies HTTP Strict Transport Security (HSTS), enforces Content Security Policies (CSP), and applies strict rate-limiting on authentication and API routes.
2. **Application Core (FastAPI / Uvicorn)**: Asynchronous ASGI microservices running in multi-worker mode with parameterized ORM access, timing-safe bcrypt cryptography, and rotating Fernet encryption.
3. **Admin Dashboard (React / Vite)**: Static SPA compiled and served via high-performance Nginx with cache-busting headers.

---

## 2. Infrastructure & System Requirements

### Recommended Hardware Specifications
* **CPU**: 4+ Cores (x86_64 or ARM64)
* **RAM**: 8 GB minimum (16 GB recommended for high-volume biometric embeddings)
* **Storage**: 100 GB NVMe SSD (High IOPS for SQLite WAL or PostgreSQL transaction logs)
* **Network**: 1 Gbps redundant network interface with static public IP

### Operating System & Dependencies
* **OS**: Ubuntu 22.04 LTS / Debian 12 / RHEL 9
* **Container Engine**: Docker Engine 24.0+ and Docker Compose v2.20+
* **Reverse Proxy**: Nginx 1.22+
* **Python Runtime** (for bare-metal): Python 3.11+

---

## 3. Production Deployment via Docker Compose (Recommended)

### Step 3.1: Clone & Configure Secrets
```bash
git clone https://github.com/organization/AERIS.git /opt/aeris
cd /opt/aeris

# Copy production environment template
cp backend/.env.production.example backend/.env.production
```

### Step 3.2: Generate High-Entropy Cryptographic Keys
Run the cryptographic key generation commands on the host machine:

```bash
# Generate 48-byte URL-safe JWT SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"

# Generate 32-byte Base64 AES-256 FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print('FERNET_KEY=' + Fernet.generate_key().decode())"
```
Paste these values into `backend/.env.production`.

### Step 3.3: Configure TLS / SSL Certificates
Place valid production certificates in `./certs`:
```bash
mkdir -p certs
# Copy fullchain and private key
cp /etc/letsencrypt/live/aeris.campus.edu/fullchain.pem certs/fullchain.pem
cp /etc/letsencrypt/live/aeris.campus.edu/privkey.pem certs/privkey.pem
chmod 600 certs/privkey.pem
```

### Step 3.4: Build and Launch Containers
```bash
docker compose pull
docker compose build --no-cache
docker compose up -d
```

### Step 3.5: Verify Deployment Status
```bash
# Verify running containers
docker compose ps

# Check container health status
curl -i https://aeris.campus.edu/health
```

---

## 4. Bare-Metal Systemd Deployment (Alternative)

For environments requiring direct host execution without containers:

### Step 4.1: Setup System User and Virtual Environment
```bash
sudo useradd -m -s /bin/bash aeris
sudo -u aeris -i

git clone https://github.com/organization/AERIS.git /home/aeris/app
cd /home/aeris/app/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4.2: Setup Systemd Service
Create `/etc/systemd/system/aeris-backend.service`:
```ini
[Unit]
Description=AERIS Enterprise FastAPI Service
After=network.target

[Service]
Type=simple
User=aeris
Group=aeris
WorkingDirectory=/home/aeris/app/backend
EnvironmentFile=/home/aeris/app/backend/.env.production
ExecStart=/home/aeris/app/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers
Restart=always
RestartSec=5s
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aeris-backend
sudo systemctl start aeris-backend
```

---

## 5. Automated Backup & Disaster Recovery Protocol

AERIS features an automated, encrypted SQLite snapshot system compliant with privacy mandates and retention rules.

### Step 5.1: Configure Daily Backup Cron
Add a root cron job (`crontab -e`):
```cron
# Daily encrypted backup at 02:00 AM UTC
0 2 * * * curl -X POST -H "Authorization: Bearer <ADMIN_SERVICE_TOKEN>" https://aeris.campus.edu/privacy/backups/create >> /var/log/aeris-backup.log 2>&1

# Daily 90-day retention cleanup at 03:00 AM UTC
0 3 * * * curl -X POST -H "Authorization: Bearer <ADMIN_SERVICE_TOKEN>" https://aeris.campus.edu/privacy/retention/cleanup >> /var/log/aeris-retention.log 2>&1
```

### Step 5.2: Disaster Recovery Verification Drill
To verify backup recoverability without interrupting live operations:
```bash
# Run automated sandbox recovery test
curl -X POST "https://aeris.campus.edu/privacy/backups/test-recovery?backup_id=<BACKUP_ID>" \
     -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Expected response:
```json
{
  "status": "RECOVERY_TEST_PASSED",
  "integrity_check": "ok",
  "disaster_recovery_certified": true
}
```

---

## 6. Zero-Downtime Cryptographic Key Rotation

When rotating the AES-256 biometric data encryption key:
1. Generate a new Fernet key: `KEY_NEW`.
2. Move current `FERNET_KEY` to `FERNET_KEYS_ROTATION`.
3. Set `FERNET_KEY=KEY_NEW`.
4. Reload backend (`docker compose restart backend` or `systemctl reload aeris-backend`).
5. MultiFernet will transparently decrypt records encrypted with older keys and re-encrypt them with `KEY_NEW` on access.

---

## 7. Monitoring, Probes & Alerting

| Endpoint | Method | Purpose | Authentication | Typical Response |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | `GET` | Comprehensive system telemetry | None | `{"status": "healthy", "database": {"connected": true}}` |
| `/health/ready` | `GET` | Kubernetes / Docker Readiness probe | None | `{"status": "READY"}` (200) or 503 |
| `/health/live` | `GET` | Container Liveness probe | None | `{"status": "ALIVE"}` (200) |
| `/metrics` | `GET` | Operational metrics feed | None | `{"system_status": "OPERATIONAL", ...}` |

### Prometheus Integration
Scrape configuration snippet:
```yaml
scrape_configs:
  - job_name: 'aeris-core'
    metrics_path: '/metrics'
    scheme: 'https'
    static_configs:
      - targets: ['aeris.campus.edu']
```

---

## 8. Incident Response & Emergency Procedures

### Database Lock Contention Mitigation
AERIS applies `PRAGMA journal_mode=WAL` with `busy_timeout=5000` automatically upon connection. If manual WAL checkpointing is needed:
```bash
sqlite3 /app/data/aeris.db "PRAGMA wal_checkpoint(FULL);"
```

### Emergency Tamper Incident
If `/reports/integrity/audit` reports `TAMPER_DETECTED`:
1. Isolate the affected node.
2. Check `audit_verification_logs` for timestamp and record IDs flagged.
3. Query the latest on-chain Merkle commitment at `/reports/merkle/commitments`.
4. Restore clean snapshot from prior encrypted backup via `/privacy/backups/restore`.
