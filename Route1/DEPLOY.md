# Route 1 — Deployment Guide (GitHub Pages frontend + AWS backend)

This is the **as-built** guide for the live deployment, plus notes on the snags hit along the
way so a redeploy is painless.

```
Browser
  ├── Frontend  → GitHub Pages   https://route1pathways.app        (static files)
  └── API calls → AWS EC2         https://api.route1pathways.app    (FastAPI behind Caddy HTTPS)
                        └── AWS RDS MySQL (private, same VPC, us-east-2)
```

- **Region:** everything AWS lives in **us-east-2** (Ohio). EC2 and RDS must share a region/VPC.
- **Domain:** `route1pathways.app`, registered free via **name.com** (GitHub Student Pack).
  `.app` is HTTPS-only (HSTS-preloaded) — both GitHub Pages and Caddy provide the required certs.
- **Server public IP (Elastic IP):** `3.18.244.88`

---

## Part 1 — Frontend on GitHub Pages

The site lives in the `Route1/frontend` subfolder, so it's published by a **GitHub Actions**
workflow (branch-based Pages can only serve repo root or `/docs`).

1. Workflow: [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) — publishes
   `Route1/frontend` on every push to `main`.
2. Repo → **Settings → Pages → Source: GitHub Actions** (not "Deploy from a branch").
3. **Custom domain:** Settings → Pages → Custom domain → `route1pathways.app` → tick
   **Enforce HTTPS**.
4. **DNS at name.com** (Advanced DNS / DNS Records) — delete the default parking records first:
   - Four **A** records, Host `@` → `185.199.108.153`, `.109.153`, `.110.153`, `.111.153`
   - One **CNAME**, Host `www` → `cakee0.github.io`

> Gotcha: if Pages shows the repo README instead of the app, the Source is still on
> "Deploy from a branch." Switch it to **GitHub Actions**.

---

## Part 2 — AWS account safety rails

- Root user: enable **MFA** (passkey or authenticator).
- Billing → **Budgets** → zero-spend budget + enable Free Tier usage alerts.
- Create an **IAM admin user** and use it instead of root.

---

## Part 3 — RDS MySQL (free tier, us-east-2)

1. RDS → Create database → **Standard create**, **MySQL 8.0**, Template **Free tier**.
2. Identifier `route1-db`, master user `admin`, **strong password (save it)**.
3. `db.t3.micro`, 20 GB, storage autoscaling **off**, **Public access: No**, default VPC.
4. Endpoint (the `DB_HOST`): `route1-db.cnuwayuqsvzp.us-east-2.rds.amazonaws.com`

> Gotcha #1 — **create the database itself.** If you don't set "Initial database name" at
> creation, the app fails with `Unknown database 'mysqlRouteOne'`. Create it once from the EC2
> box (see Part 5).
>
> Gotcha #2 — **let EC2 reach RDS.** A connection `timed out` means the security group blocks
> it. Easiest fix: RDS → `route1-db` → **Set up EC2 connection** → pick `route1-api`; AWS adds
> the inbound 3306 rule automatically. (Manual equivalent: add inbound MySQL/Aurora 3306 to the
> RDS security group with Source = the EC2 instance's security group.)

---

## Part 4 — EC2 server (free tier, us-east-2)

1. EC2 → Launch instance: name `route1-api`, **Ubuntu Server LTS**, `t3.micro`/`t2.micro`.
2. Key pair: create + download `.pem` (kept as `route1ec1.pem`).
3. Security group inbound: SSH 22 (My IP), HTTP 80 (Anywhere), HTTPS 443 (Anywhere).
4. **Elastic IP** → Allocate → Associate with `route1-api` (this is `3.18.244.88`).

**Connecting from Windows (PowerShell):**
```
# one-time: lock down the key so SSH will accept it
icacls "C:\path\route1ec1.pem" /inheritance:r
icacls "C:\path\route1ec1.pem" /grant:r "$($env:USERNAME):(R)"

ssh -i "C:\path\route1ec1.pem" ubuntu@3.18.244.88
```

> Gotcha: "UNPROTECTED PRIVATE KEY FILE" → run the two `icacls` lines above, then reconnect.

---

## Part 5 — Deploy the FastAPI backend (on the server)

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git
git clone https://github.com/Cakee0/Route-1-Pathways-Portal.git pathways
cd pathways/Route1/backend
```

> Gotcha — **Python version.** Recent Ubuntu ships Python 3.14, which has no prebuilt wheels
> for this project's pinned deps, so `pip install` tries to compile them with Rust and gets
> OOM-killed on a 1 GB instance. Fix: use `uv` with **Python 3.12** (all deps have wheels — no
> compiling):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

**Create the `.env`** (see `.env.example`) — the important prod-specific lines:
```
DB_HOST=route1-db.cnuwayuqsvzp.us-east-2.rds.amazonaws.com
DB_NAME=mysqlRouteOne
DB_USER=admin
DB_PASSWORD=<rds-master-password>
SECRET_KEY=<python3 -c "import secrets; print(secrets.token_hex(32))">
GOOGLE_CLIENT_ID=<oauth-web-client-id>
ALLOWED_ORIGINS=https://route1pathways.app,https://www.route1pathways.app
```

**Create the database once** (the app makes tables, not the DB):
```bash
sudo apt install -y mysql-client
mysql -h route1-db.cnuwayuqsvzp.us-east-2.rds.amazonaws.com -u admin -p \
  -e "CREATE DATABASE IF NOT EXISTS mysqlRouteOne CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

**Smoke test:** `uvicorn main:app --host 127.0.0.1 --port 8000` → in another SSH session
`curl http://127.0.0.1:8000/` should return `{"status":"ok",...}`. Ctrl-C to stop.

**Run as a service** (survives reboot/crash):
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
```
Then (run as a **single line** — some remote terminals mangle multi-line pastes):
```bash
sudo systemctl daemon-reload && sudo systemctl enable --now route1 && sudo systemctl status route1 --no-pager
```
Expect `active (running)`.

---

## Part 6 — HTTPS with Caddy

**DNS first** — name.com → add **A** record, Host `api`, Answer `3.18.244.88`.

On the server:
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

printf 'api.route1pathways.app {\n    reverse_proxy 127.0.0.1:8000\n}\n' | sudo tee /etc/caddy/Caddyfile
sudo systemctl restart caddy
```
Test: `https://api.route1pathways.app/` → `{"status":"ok",...}` with a padlock. First load can
take 10–20 s while Caddy fetches the cert.

---

## Part 7 — Wire frontend ↔ backend

1. `PROD_API_BASE` in [`../frontend/app.js`](../frontend/app.js) = `https://api.route1pathways.app`
   (committed). Pushing to `main` redeploys Pages.
2. Backend `.env` `ALLOWED_ORIGINS` includes the frontend origins (above); restart after edits:
   `sudo systemctl restart route1`.
3. **Google Sign-In:** Google Cloud Console → APIs & Services → Credentials → the **Web
   application** OAuth client → **Authorized JavaScript origins** → add
   `https://route1pathways.app`, `https://www.route1pathways.app`, `https://cakee0.github.io`.
   (The client ID in `app.js` and the backend `.env` must match. Watch the **project selector**
   at the top of the console — an empty Credentials page usually means the wrong project.)

---

## Everyday operations

| Task | Command / action |
|---|---|
| Update backend | SSH in → `cd ~/pathways && git pull` → `sudo systemctl restart route1` |
| Update frontend | push to `main` — the Pages Action redeploys |
| Backend logs | `sudo journalctl -u route1 -e` |
| Restart API / proxy | `sudo systemctl restart route1` · `sudo systemctl restart caddy` |

## Common fixes
- **Mixed content blocked** → frontend calling `http://`; `PROD_API_BASE` must be `https://`.
- **CORS error** → `ALLOWED_ORIGINS` must exactly match the browser origin; restart `route1`.
- **502 from Caddy** → app down: `sudo journalctl -u route1 -e`.
- **DB `timed out`** → RDS security group (Part 3, gotcha #2).
- **DB `Unknown database`** → create `mysqlRouteOne` (Part 5).
- **Cert won't issue** → `api` DNS not propagated, or 80/443 blocked.
- **IP changed after reboot** → Elastic IP not associated (Part 4).

## Cost
Free tier (12 months): EC2 + RDS each get 750 hrs/month (enough for one 24/7 instance each).
The domain is free for year 1 via the Student Pack. Keep the zero-spend budget from Part 2.
