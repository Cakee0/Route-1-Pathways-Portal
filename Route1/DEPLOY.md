# Route 1 — Deployment Guide (GitHub Pages frontend + AWS backend)

Architecture you're building:

```
Browser
  │
  ├── Frontend  → GitHub Pages   https://<you>.github.io/<repo>   (static files)
  │
  └── API calls → AWS EC2         https://api.<you>.me            (FastAPI + Caddy HTTPS)
                        │
                        └── AWS RDS MySQL (private, same VPC)
```

Everything below fits inside the AWS **free tier** (12 months) plus your **GitHub Student
Developer Pack** (free `.me` domain from Namecheap + GitHub Pro for private-repo Pages).

Pick **one AWS region** at the start (e.g. `us-east-1`) and do **every** AWS step in that
same region — RDS and EC2 must share a region/VPC to talk to each other.

---

## Part 1 — New AWS account + safety rails (30 min)

1. Create the account at https://aws.amazon.com → "Create an AWS Account". You'll need a
   card (won't be charged on free tier, but required) and phone verification.
2. **Secure the root user:** IAM → enable **MFA** on the root account (authenticator app).
3. **Stop surprise bills** — this is the single most important step:
   - Billing → **Budgets** → create a **Zero-spend budget** (or a $1 budget). Email alert.
   - Billing → Billing preferences → enable **"Receive Free Tier usage alerts"** and
     **"Receive CloudWatch billing alerts"**. Enter your email.
4. **Create an admin IAM user** (don't use root day-to-day):
   - IAM → Users → Create user → attach policy `AdministratorAccess` → enable console access.
   - Log out of root, log back in as this IAM user for everything below.

---

## Part 2 — Claim your free `.me` domain (Student Pack) (15 min)

1. Go to https://education.github.com/pack → find **Namecheap** → get a free `.me` domain
   for 1 year (or **.tech** / others in the pack).
2. Register something like `yourname.me`.
3. Leave the Namecheap dashboard open — you'll add a DNS record in Part 6 pointing
   `api.yourname.me` at your EC2 server.

> You'll use the **root/apex** or a subdomain for the API. This guide uses
> `api.yourname.me` for the backend and keeps the frontend on `github.io`.

---

## Part 3 — RDS MySQL database (free tier) (20 min)

1. AWS Console → **RDS** → Create database.
2. Settings:
   - **Standard create**, Engine **MySQL** (8.0.x).
   - Template: **Free tier**.
   - DB instance identifier: `route1-db`.
   - Master username: `admin` — set a **strong master password** and save it.
   - Instance class: `db.t3.micro` (whatever shows "Free tier eligible").
   - Storage: 20 GB gp2/gp3, **disable** storage autoscaling.
   - **Public access: No** (only EC2 in the same VPC will reach it).
   - VPC: default VPC. Note the VPC — EC2 must be in the same one.
   - **Additional configuration → Initial database name: `mysqlRouteOne`**  ← important, the
     app expects this DB to exist (`DB_NAME` in `database.py`).
3. Create it. Wait ~5–10 min until status is **Available**.
4. Copy the **Endpoint** (e.g. `route1-db.xxxx.us-east-1.rds.amazonaws.com`) — that's your
   `DB_HOST`.

The app auto-creates its tables on first boot (`create_tables()` in `main.py`), so you don't
need to load `schemas.sql` manually — but you can if you prefer (see Part 5, note).

---

## Part 4 — EC2 server (free tier) (20 min)

1. AWS Console → **EC2** → Launch instance.
   - Name: `route1-api`.
   - AMI: **Ubuntu Server 24.04 LTS**.
   - Instance type: `t3.micro` or `t2.micro` (whichever says "Free tier eligible").
   - Key pair: **Create a new key pair** (RSA, `.pem`), download and keep it safe — it's your
     SSH login.
   - Network: same **default VPC** as RDS.
   - **Security group** (create new), inbound rules:
     - SSH (22) → Source: **My IP**
     - HTTP (80) → Source: **Anywhere** (needed for Let's Encrypt)
     - HTTPS (443) → Source: **Anywhere**
   - Storage: 30 GB gp3 (free-tier limit).
2. Launch.
3. **Elastic IP** (so the IP survives reboots) — EC2 → Elastic IPs → Allocate → Associate
   with `route1-api`. Copy this IP; it's what your domain will point to.

### Let the server reach the database
1. EC2 → your instance → note its **security group**.
2. RDS → `route1-db` → Connectivity & security → its **security group** → Edit inbound rules:
   - Add rule: **MySQL/Aurora (3306)** → Source: **the EC2 instance's security group**.
   This lets only your EC2 box connect to the DB.

---

## Part 5 — Deploy the FastAPI backend on EC2 (30 min)

SSH in (from your machine, in the folder with the `.pem`):

```bash
chmod 400 route1-api.pem                 # Git Bash / macOS / Linux
ssh -i route1-api.pem ubuntu@<ELASTIC_IP>
```

On the server:

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git

# Get the code (public repo, or use a token/deploy key for private)
git clone https://github.com/<you>/<repo>.git pathways
cd pathways/Route1/backend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create the backend `.env` (never committed) — use `.env.example` as reference:

```bash
cat > .env <<'EOF'
DB_HOST=route1-db.xxxx.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=mysqlRouteOne
DB_USER=admin
DB_PASSWORD=<your-rds-master-password>
SECRET_KEY=<paste output of: python3 -c "import secrets; print(secrets.token_hex(32))">
GOOGLE_CLIENT_ID=398142413341-n6glr5jnmh60li4nmefnh5fdehr3u00p.apps.googleusercontent.com
ALLOWED_ORIGINS=https://<you>.github.io
EOF
```

> `ALLOWED_ORIGINS` is the GitHub Pages **origin** (scheme + host only, no repo subpath,
> no trailing slash). You'll confirm the exact value in Part 7.

Quick smoke test (foreground):

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
# In another SSH session:  curl http://127.0.0.1:8000/   → {"status":"ok",...}
# Ctrl-C to stop.
```

If that fails with a DB error, the RDS security-group rule (Part 4) or `.env` values are wrong.

> **Optional — load schemas.sql instead of relying on auto-create:**
> `sudo apt install -y mysql-client` then
> `mysql -h $DB_HOST -u admin -p mysqlRouteOne < schemas.sql`

### Run it as a service (survives reboots/crashes)

```bash
sudo tee /etc/systemd/system/route1.service > /dev/null <<'EOF'
[Unit]
Description=Route1 FastAPI
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/pathways/Route1/backend
ExecStart=/home/ubuntu/pathways/Route1/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now route1
sudo systemctl status route1        # should be active (running)
```

(The app reads `.env` from its working directory via `load_dotenv()`, so systemd doesn't
need the env vars listed explicitly.)

---

## Part 6 — HTTPS with Caddy + point your domain (20 min)

### Point the domain at the server
In **Namecheap** → Domain List → Manage → **Advanced DNS** → add:
- Type **A Record**, Host `api`, Value `<ELASTIC_IP>`, TTL Automatic.

Wait a few minutes, then verify from your laptop: `nslookup api.yourname.me` → your IP.

### Install Caddy (automatic Let's Encrypt HTTPS)
On the server:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
api.yourname.me {
    reverse_proxy 127.0.0.1:8000
}
EOF

sudo systemctl restart caddy
```

Caddy automatically obtains a TLS cert (needs DNS pointing correctly + ports 80/443 open).
Test from your laptop: open `https://api.yourname.me/` → you should see the JSON health
response over HTTPS. **This URL is your backend base.**

---

## Part 7 — Publish the frontend to GitHub Pages (20 min)

Your frontend lives in `Route1/frontend/`, a subfolder — so use a GitHub Actions workflow to
publish just that folder (branch-based Pages can only serve repo root or `/docs`).

1. **Make sure your repo is private-Pages-capable:** with GitHub Pro (from the Student Pack),
   Pages works on private repos. Otherwise make the repo public.
2. Add this workflow at `.github/workflows/pages.yml` (I can create it for you — just ask):

```yaml
name: Deploy frontend to Pages
on:
  push:
    branches: [main]
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: Route1/frontend
      - id: deployment
        uses: actions/deploy-pages@v4
```

3. Repo → **Settings → Pages → Source: GitHub Actions**.
4. Push to `main`. The Action runs and gives you the live URL, typically
   `https://<you>.github.io/<repo>/`.

---

## Part 8 — Wire the two halves together

1. **Frontend → backend URL.** In `Route1/frontend/app.js` set the placeholder to your API:
   ```js
   const PROD_API_BASE = "https://api.yourname.me";
   ```
   Commit + push (redeploys Pages).
2. **Backend → allowed origin.** Confirm the `.env` on EC2 has the exact Pages origin:
   ```
   ALLOWED_ORIGINS=https://<you>.github.io
   ```
   (origin = scheme + host only; the `/<repo>` path is NOT part of it.) After editing:
   `sudo systemctl restart route1`.
3. **Google Sign-In.** Google Cloud Console → your OAuth 2.0 **Web application** client →
   **Authorized JavaScript origins** → add `https://<you>.github.io`. Without this the Google
   button won't render. (The client ID in `app.js` and backend `.env` must match — they do.)

---

## Part 9 — Verify end-to-end

- Open `https://<you>.github.io/<repo>/` → app loads over HTTPS (no mixed-content errors in
  DevTools console).
- Register / log in → Network tab shows calls to `https://api.yourname.me/...` returning 200,
  with an `access-control-allow-origin` header matching your Pages origin.
- Sign in with Google works.

### Common gotchas
- **Mixed content blocked** → frontend is calling `http://` not `https://`. Fix `PROD_API_BASE`.
- **CORS error** → `ALLOWED_ORIGINS` doesn't exactly match the browser origin (trailing slash,
  http vs https, or you included the repo path). Restart the service after changing `.env`.
- **502 from Caddy** → the `route1` service isn't running: `sudo journalctl -u route1 -e`.
- **DB connection refused** → RDS security group missing the inbound rule from EC2's SG.
- **Cert not issued** → DNS A record not propagated yet, or port 80/443 blocked in the SG.
- **Instance IP changed** → you skipped the Elastic IP (Part 4); re-point the DNS record.

---

## Ongoing / cost notes
- Free tier lasts **12 months**; EC2 and RDS each get 750 hrs/month (enough for one 24/7
  instance each). The zero-spend budget from Part 1 warns you if anything slips outside it.
- To update the backend: SSH in → `cd ~/pathways && git pull` →
  `sudo systemctl restart route1`.
- To update the frontend: just push to `main` — the Pages Action redeploys.
