#!/usr/bin/env bash
set -euo pipefail

### ====== CONFIG (you can edit these) ======
DOMAIN="${DOMAIN:-terminology-mapper.de}"
SERVICE_USER="${SERVICE_USER:-termmapper}"
REPO_SSH="${REPO_SSH:-git@github.com:org/umg-minai/terminology-mapper.git}"
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

require_root () {
  if [[ $EUID -ne 0 ]]; then
    echo "[ERR] Please run as root."
    exit 1
  fi
}

pause () {
  read -r -p "$(printf "\033[1;35m[PAUSE]\033[0m %s " "$*")"
}

require_root

info "Pre-flight: Ubuntu packages update + base tooling"
apt update
DEBIAN_FRONTEND=noninteractive apt -y full-upgrade
apt -y install git ufw fail2ban unattended-upgrades curl nginx python3-venv python3-pip snapd

info "Set hostname and local hosts entry"
hostnamectl set-hostname "${SHORT_HOSTNAME}"
if ! grep -q "${DOMAIN}" /etc/hosts; then
  echo "127.0.1.1 ${SHORT_HOSTNAME} ${DOMAIN}" >> /etc/hosts
fi
ok "Hostname set to $(hostnamectl --static)"

info "Configure UFW (firewall)"
ufw default deny incoming
ufw default allow outgoing
ufw limit "${SSH_PORT}/tcp" || true
ufw allow "Nginx Full"
ufw --force enable
ufw status verbose | sed 's/^/  /'

info "Enable automatic security updates"
bash -lc 'printf "APT::Periodic::Update-Package-Lists \"1\";\nAPT::Periodic::Unattended-Upgrade \"1\";\n" > /etc/apt/apt.conf.d/20auto-upgrades'
systemctl enable --now unattended-upgrades

info "Make journald persistent and bounded"
mkdir -p /var/log/journal
if ! grep -q '^Storage=persistent' /etc/systemd/journald.conf 2>/dev/null; then
  sed -i 's/^#\?Storage=.*/Storage=persistent/' /etc/systemd/journald.conf || true
fi
if ! grep -q '^SystemMaxUse=' /etc/systemd/journald.conf 2>/dev/null; then
  echo "SystemMaxUse=500M" >> /etc/systemd/journald.conf
fi
systemctl restart systemd-journald

info "Kernel/network hardening (sysctl)"
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

info "Fail2ban basic config"
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

warn "SSH hardening (disable password & root login) can lock you out if keys are not set."
pause "Press Enter to harden SSH now (or Ctrl+C to abort)."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%s)
sed -i \
  -e "s/^#\?PermitRootLogin .*/PermitRootLogin no/" \
  -e "s/^#\?PasswordAuthentication .*/PasswordAuthentication no/" \
  -e "s/^#\?PubkeyAuthentication .*/PubkeyAuthentication yes/" \
  /etc/ssh/sshd_config
sshd -t && systemctl reload ssh && ok "SSHD hardened (root login off, passwords off)"

info "Create ${SERVICE_USER} system user and directories"
id -u "${SERVICE_USER}" &>/dev/null || \
  useradd --system --create-home --home-dir "${APP_HOME}" --shell /usr/sbin/nologin "${SERVICE_USER}"
sudo -u "${SERVICE_USER}" mkdir -p "${APP_DIR}" "${APP_HOME}/.ssh"
chmod 700 "${APP_HOME}/.ssh"

info "Generate GitHub deploy key"
sudo -u "${SERVICE_USER}" ssh-keygen -t ed25519 -N "" -C "deploy@${DOMAIN}" -f "${APP_HOME}/.ssh/id_ed25519"
sudo -u "${SERVICE_USER}" bash -lc 'ssh-keyscan -H github.com >> "$HOME/.ssh/known_hosts"'
chmod 644 "${APP_HOME}/.ssh/known_hosts"
cat <<EOF

===== COPY THE PUBLIC DEPLOY KEY BELOW INTO GITHUB =====
Repo → Settings → Deploy keys → Add deploy key → (tick "Allow read access")
---------------------------------------------------------------------------
$(cat "${APP_HOME}/.ssh/id_ed25519.pub")
---------------------------------------------------------------------------
EOF
pause "Press Enter *after* you've added the deploy key in GitHub…"

# Ask for the real repo if still placeholder
if [[ "${REPO_SSH}" == "git@github.com:org/repo.git" ]]; then
  read -r -p "Enter your private repo SSH URL (e.g., git@github.com:ORG/REPO.git): " REPO_SSH
  if [[ -z "${REPO_SSH}" ]]; then
    echo "[ERR] No repo URL provided. Exiting."
    exit 1
  fi
fi
ok "Using repo: ${REPO_SSH}"

info "Clone the repo into ${APP_DIR}"
if [[ -d "${APP_DIR}/.git" ]]; then
  warn "Repo already exists at ${APP_DIR}; pulling latest."
  sudo -u "${SERVICE_USER}" git -C "${APP_DIR}" pull --ff-only
else
  sudo -u "${SERVICE_USER}" git clone "${REPO_SSH}" "${APP_DIR}"
fi

info "Python venv + dependencies"
sudo -u "${SERVICE_USER}" bash -lc "
  cd '${APP_DIR}' && python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip wheel
  if [ -f requirements.txt ]; then pip install -r requirements.txt; else
    pip install 'gunicorn>=21' 'uvicorn[standard]>=0.23' fastapi jinja2 'python-multipart>=0.0.9'
  fi
"
ok "Venv ready at ${VENV}"

info "App environment file at ${ENV_FILE}"
mkdir -p "${ENV_DIR}"
if ! grep -q '^SESSION_SECRET=' "${ENV_FILE}" 2>/dev/null; then
  printf "APP_ENV=production\nSESSION_SECRET=%s\n" "$(openssl rand -hex 32)" > "${ENV_FILE}"
fi
chown root:"${SERVICE_USER}" "${ENV_FILE}"
chmod 640 "${ENV_FILE}"

info "Create Nginx site for ${DOMAIN}"
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

info "Install certbot and request TLS certificates for ${DOMAIN}"
snap install core && snap refresh core
snap install --classic certbot
ln -sf /snap/bin/certbot /usr/bin/certbot
certbot --nginx \
  -d "${DOMAIN}" -d "www.${DOMAIN}" \
  --non-interactive --agree-tos -m "${EMAIL_TOS}" --redirect

# Add strict headers to HTTPS block (idempotent-ish append)
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

info "Create systemd service ${SERVICE_USER}.service"
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

info "Prepare data directory and PAUSE for manual upload of data.CSV"
sudo -u "${SERVICE_USER}" mkdir -p "${APP_DIR}/data"
echo
echo ">>> Now upload your data file:"
echo "    scp ./data.CSV root@${DOMAIN}:${APP_DIR}/data/data.CSV"
echo "    (or use your preferred method; target path must be exactly: ${APP_DIR}/data/data.CSV)"
echo
pause "Press Enter after you have uploaded data.CSV…"

if [[ ! -f "${APP_DIR}/data/data.CSV" ]]; then
  echo "[ERR] ${APP_DIR}/data/data.CSV not found. Upload it and rerun: systemctl restart ${SERVICE_USER}"
  exit 1
fi
chown "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}/data/data.CSV"
chmod 640 "${APP_DIR}/data/data.CSV"
ok "data.CSV present with safe permissions"

info "Start and enable the FastAPI service"
systemctl enable --now "${SERVICE_USER}"
sleep 2
systemctl status "${SERVICE_USER}" --no-pager || true

info "Final checks"
set +e
curl -I "http://${DOMAIN}" | sed 's/^/  /'
curl -I "https://${DOMAIN}" | sed 's/^/  /'
set -e

ok "All done. App should be live at https://${DOMAIN}"
echo "To deploy updates:"
echo "  sudo -u ${SERVICE_USER} git -C ${APP_DIR} pull && sudo systemctl restart ${SERVICE_USER}"
