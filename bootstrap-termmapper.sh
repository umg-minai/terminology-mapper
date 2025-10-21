#!/usr/bin/env bash
set -euo pipefail

### ====== CONFIG (you can edit these) ======
DOMAIN="${DOMAIN:-terminology-mapper.de}"
SERVICE_USER="${SERVICE_USER:-termmapper}"
REPO_URL="${REPO_URL:-https://github.com/umg-minai/terminology-mapper.git}" # public repo; will prompt if left as placeholder
SSH_PORT="${SSH_PORT:-22}"             # change if you use a nonstandard SSH port
SHORT_HOSTNAME="${SHORT_HOSTNAME:-terminology-mapper}"
EMAIL_TOS="${EMAIL_TOS:-you@example.com}"  # Let’s Encrypt contact email
### ========================================

APP_HOME="/srv/${SERVICE_USER}"
APP_DIR="${APP_HOME}/app"
VENV="${APP_DIR}/.venv"
ENV_DIR="/etc/${SERVICE_USER}"
ENV_FILE="${ENV_DIR}/env"
UNIT_FILE="/etc/systemd/system/${SERVICE_USER}.service"
SITE_AVAIL="/etc/nginx/sites-available/${SERVICE_USER}.conf"
SITE_ENAB="/etc/nginx/sites-enabled/${SERVICE_USER}.conf"

info () { printf "\n\033[1;36m[INFO]\033[0m %s\n" "$*"; }
warn () { printf "\n\033[1;33m[WARN]\033[0m %s\n" "$*"; }
ok   () { printf "\033[1;32m[OK]\033[0m %s\n" "$*"; }
pause () { read -r -p "$(printf "\033[1;35m[PAUSE]\033[0m %s " "$*")"; }
require_root () { [[ $EUID -eq 0 ]] || { echo "[ERR] Run as root."; exit 1; }; }
require_root

### 0) Ask for admin SSH user + pubkey (+ optional SSH port)
info "Admin SSH account setup"
read -r -p "Admin username to create (sudo-enabled) [suggestion: appadmin]: " ADMIN_USER
ADMIN_USER="${ADMIN_USER:-appadmin}"
echo "Paste the admin user's SSH PUBLIC key (single line starting with ssh-ed25519 or ssh-rsa):"
read -r ADMIN_PUBKEY
[[ -n "${ADMIN_PUBKEY}" ]] || { echo "[ERR] No public key provided."; exit 1; }
read -r -p "SSH port to use [${SSH_PORT}]: " SSH_PORT_INPUT
SSH_PORT="${SSH_PORT_INPUT:-$SSH_PORT}"

### 1) Packages
info "Updating packages and installing base tools"
apt update
DEBIAN_FRONTEND=noninteractive apt -y full-upgrade
apt -y install git ufw fail2ban unattended-upgrades curl nginx python3-venv python3-pip snapd

### 2) Hostname
info "Setting hostname and /etc/hosts entry"
hostnamectl set-hostname "${SHORT_HOSTNAME}"
grep -q "${DOMAIN}" /etc/hosts || echo "127.0.1.1 ${SHORT_HOSTNAME} ${DOMAIN}" >> /etc/hosts
ok "Hostname: $(hostnamectl --static)"

### 3) Create admin user with SSH key + sudo
info "Creating admin user '${ADMIN_USER}' with sudo + SSH key"
if ! id -u "${ADMIN_USER}" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "${ADMIN_USER}"
fi
usermod -aG sudo "${ADMIN_USER}"
install -d -m 700 -o "${ADMIN_USER}" -g "${ADMIN_USER}" "/home/${ADMIN_USER}/.ssh"
printf "%s\n" "${ADMIN_PUBKEY}" > "/home/${ADMIN_USER}/.ssh/authorized_keys"
chown "${ADMIN_USER}:${ADMIN_USER}" "/home/${ADMIN_USER}/.ssh/authorized_keys"
chmod 600 "/home/${ADMIN_USER}/.ssh/authorized_keys"
ok "Admin account ready: ${ADMIN_USER}"

### 4) UFW firewall
info "Configuring UFW firewall"
ufw default deny incoming
ufw default allow outgoing
ufw limit "${SSH_PORT}/tcp" || true
ufw allow "Nginx Full"
ufw --force enable
ufw status verbose | sed 's/^/  /'

### 5) Unattended upgrades
info "Enabling unattended security upgrades"
bash -lc 'printf "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";\n" > /etc/apt/apt.conf.d/20auto-upgrades'
systemctl enable --now unattended-upgrades

### 6) Journald persistence + size cap
info "Configuring journald persistence and size cap"
mkdir -p /var/log/journal
sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf || true
grep -q '^SystemMaxUse=' /etc/systemd/journald.conf || echo "SystemMaxUse=500M" >> /etc/systemd/journald.conf
systemctl restart systemd-journald

### 7) Sysctl hardening
info "Applying kernel/network hardening (sysctl)"
cat >/etc/sysctl.d/99-hardening.conf <<'EOF'
kernel.kptr_restrict=2
kernel.dmesg_restrict=1
kernel.unprivileged_bpf_disabled=1
fs.protected_hardlinks=1
fs.protected_symlinks=1
net.ipv4.conf.all.rp_filter=1
net.ipv4.conf.default.rp_filter=1
net.ipv4.tcp_syncookies=1
net.ipv4.conf.all.accept_source_route=0
net.ipv4.conf.default.accept_source_route=0
net.ipv4.conf.all.accept_redirects=0
net.ipv4.conf.default.accept_redirects=0
net.ipv4.conf.all.send_redirects=0
net.ipv4.conf.default.send_redirects=0
net.ipv4.icmp_echo_ignore_broadcasts=1
net.ipv4.icmp_ignore_bogus_error_responses=1
net.ipv4.conf.all.log_martians=1
net.ipv6.conf.all.accept_redirects=0
net.ipv6.conf.default.accept_redirects=0
EOF
sysctl --system >/dev/null

### 8) Fail2ban
info "Configuring Fail2ban"
cat >/etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
ignoreip = 127.0.0.1/8 ::1
[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
[nginx-http-auth]
enabled = true
[nginx-botsearch]
enabled = true
EOF
systemctl enable --now fail2ban

### 9) SSH hardening (with safety pause)
warn "We will now harden SSH: set Port ${SSH_PORT}, disable root login and password auth."
warn "Open a NEW terminal and confirm you can SSH as '${ADMIN_USER}' using your key on port ${SSH_PORT}."
pause "When you've confirmed the new login works, press Enter to apply SSH hardening…"

cp /etc/ssh/sshd_config "/etc/ssh/sshd_config.bak.$(date +%s)"

# Set Port (idempotent)
if grep -qE '^#?\s*Port ' /etc/ssh/sshd_config; then
  sed -i -E "s/^#?\s*Port .*/Port ${SSH_PORT}/" /etc/ssh/sshd_config
else
  echo "Port ${SSH_PORT}" >> /etc/ssh/sshd_config
fi
# Disable root & password, ensure pubkey
sed -i \
  -e "s/^#\?PermitRootLogin .*/PermitRootLogin no/" \
  -e "s/^#\?PasswordAuthentication .*/PasswordAuthentication no/" \
  -e "s/^#\?PubkeyAuthentication .*/PubkeyAuthentication yes/" \
  /etc/ssh/sshd_config

sshd -t && systemctl reload ssh
ok "SSH hardened (root login off, passwords off, port=${SSH_PORT}). Use: ssh -p ${SSH_PORT} ${ADMIN_USER}@${DOMAIN}"

### 10) termmapper service user (no shell)
info "Creating service user '${SERVICE_USER}'"
id -u "${SERVICE_USER}" &>/dev/null || \
  useradd --system --create-home --home-dir "${APP_HOME}" --shell /usr/sbin/nologin "${SERVICE_USER}"
sudo -u "${SERVICE_USER}" mkdir -p "${APP_DIR}"
ok "Service user ${SERVICE_USER} ready"

### 11) Clone PUBLIC repo + venv
# Prompt if REPO_URL still placeholder
if [[ "${REPO_URL}" == "https://github.com/org/repo.git" ]]; then
  read -r -p "Enter your PUBLIC repo URL (e.g., https://github.com/ORG/REPO.git): " REPO_URL
  [[ -n "${REPO_URL}" ]] || { echo "[ERR] No repo URL provided."; exit 1; }
fi
info "Cloning repo to ${APP_DIR}"
if [[ -d "${APP_DIR}/.git" ]]; then
  sudo -u "${SERVICE_USER}" git -C "${APP_DIR}" pull --ff-only
else
  sudo -u "${SERVICE_USER}" git clone "${REPO_URL}" "${APP_DIR}"
fi

info "Creating Python venv and installing deps"
sudo -u "${SERVICE_USER}" bash -lc "
  cd '${APP_DIR}' && python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip wheel
  if [ -f requirements.txt ]; then pip install -r requirements.txt; else
    pip install 'gunicorn>=21' 'uvicorn[standard]>=0.23' fastapi jinja2 'python-multipart>=0.0.9'
  fi
"

### 12) App env file (stable session secret)
info "Creating app env at ${ENV_FILE}"
mkdir -p "${ENV_DIR}"
if ! grep -q '^SESSION_SECRET=' "${ENV_FILE}" 2>/dev/null; then
  printf "APP_ENV=production\nSESSION_SECRET=%s\n" "$(openssl rand -hex 32)" > "${ENV_FILE}"
fi
chown root:"${SERVICE_USER}" "${ENV_FILE}"
chmod 640 "${ENV_FILE}"

### 13) Nginx HTTP (will be upgraded to HTTPS by certbot)
info "Configuring Nginx for ${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default || true
cat >"${SITE_AVAIL}" <<EOF
limit_req_zone \$binary_remote_addr zone=req_limit:10m rate=5r/s;

upstream ${SERVICE_USER}_upstream {
    server 127.0.0.1:5000;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    location / {
        limit_req zone=req_limit burst=20 nodelay;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_pass http://${SERVICE_USER}_upstream;
    }

    location = /healthz {
        access_log off;
        proxy_pass http://${SERVICE_USER}_upstream;
    }
}
EOF
ln -sf "${SITE_AVAIL}" "${SITE_ENAB}"
nginx -t && systemctl reload nginx

### 14) Let’s Encrypt TLS
info "Obtaining TLS certificates via Certbot"
snap install core && snap refresh core
snap install --classic certbot
ln -sf /snap/bin/certbot /usr/bin/certbot
certbot --nginx \
  -d "${DOMAIN}" -d "www.${DOMAIN}" \
  --non-interactive --agree-tos -m "${EMAIL_TOS}" --redirect

# Harden HTTPS headers
sed -i '/server_name .*;/a \
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always; \
    add_header X-Content-Type-Options "nosniff" always; \
    add_header X-Frame-Options "DENY" always; \
    add_header Referrer-Policy "strict-origin-when-cross-origin" always; \
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always; \
' "${SITE_AVAIL}" || true
nginx -t && systemctl reload nginx
systemctl list-timers | grep certbot || true
certbot renew --dry-run || true

### 15) Systemd service (gunicorn+uvicorn) on 127.0.0.1:5000, main:app
info "Creating systemd unit ${SERVICE_USER}.service"
cat >"${UNIT_FILE}" <<EOF
[Unit]
Description=${DOMAIN} FastAPI (gunicorn+uvicorn)
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV}/bin/python -m gunicorn main:app \\
  --workers 2 --threads 4 --timeout 60 \\
  --worker-class uvicorn.workers.UvicornWorker \\
  --bind 127.0.0.1:5000
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
MemoryDenyWriteExecute=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload

### 16) Ensure data file exists (pause for manual upload)
info "Preparing data directory and pausing for data upload"
sudo -u "${SERVICE_USER}" mkdir -p "${APP_DIR}/data"
echo
echo ">>> Upload your data file NOW:"
echo "    scp -P ${SSH_PORT} ./data.CSV ${ADMIN_USER}@${DOMAIN}:${APP_DIR}/data/data.CSV"
echo
pause "Press Enter after data.CSV is uploaded…"
if [[ ! -f "${APP_DIR}/data/data.CSV" ]]; then
  echo "[ERR] ${APP_DIR}/data/data.CSV not found. Upload it and then run: systemctl restart ${SERVICE_USER}"
  exit 1
fi
chown "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}/data/data.CSV"
chmod 640 "${APP_DIR}/data/data.CSV"
ok "data.CSV present and permissions set"

### 17) Start app
info "Starting and enabling ${SERVICE_USER} service"
systemctl enable --now "${SERVICE_USER}"
sleep 2
systemctl status "${SERVICE_USER}" --no-pager || true

### 18) Final checks
info "Final HTTP→HTTPS check"
set +e
curl -I "http://${DOMAIN}" | sed 's/^/  /'
curl -I "https://${DOMAIN}" | sed 's/^/  /'
set -e

ok "All done. App should be live at https://${DOMAIN}"
echo "Deploy updates:"
echo "  sudo -u ${SERVICE_USER} git -C ${APP_DIR} pull && sudo systemctl restart ${SERVICE_USER}"
echo "Remember to SSH with: ssh -p ${SSH_PORT} ${ADMIN_USER}@${DOMAIN}"
