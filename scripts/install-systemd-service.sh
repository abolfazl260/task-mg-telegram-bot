#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="task-mg-telegram-bot"
INSTALL_DIR="${INSTALL_DIR:-/opt/task-mg-telegram-bot}"
SERVICE_USER="${SERVICE_USER:-taskbot}"
SERVICE_GROUP="${SERVICE_GROUP:-$SERVICE_USER}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this script with sudo/root access." >&2
  exit 1
fi

if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
  groupadd --system "${SERVICE_GROUP}"
fi

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin --gid "${SERVICE_GROUP}" "${SERVICE_USER}"
fi

mkdir -p "${INSTALL_DIR}"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '.env' \
  --exclude '__pycache__' \
  ./ "${INSTALL_DIR}/"

chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}"

runuser -u "${SERVICE_USER}" -- "${PYTHON_BIN}" -m venv "${INSTALL_DIR}/.venv"
runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
runuser -u "${SERVICE_USER}" -- "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
  cat > "${INSTALL_DIR}/.env" <<'ENVEOF'
BOT_TOKEN=replace-with-your-telegram-bot-token
ENVEOF
  chown "${SERVICE_USER}:${SERVICE_GROUP}" "${INSTALL_DIR}/.env"
  chmod 600 "${INSTALL_DIR}/.env"
  echo "Created ${INSTALL_DIR}/.env. Edit BOT_TOKEN before starting the service." >&2
fi

sed \
  -e "s#WorkingDirectory=/opt/task-mg-telegram-bot#WorkingDirectory=${INSTALL_DIR}#" \
  -e "s#EnvironmentFile=/opt/task-mg-telegram-bot/.env#EnvironmentFile=${INSTALL_DIR}/.env#" \
  -e "s#ExecStart=/opt/task-mg-telegram-bot/.venv/bin/python /opt/task-mg-telegram-bot/main.py#ExecStart=${INSTALL_DIR}/.venv/bin/python ${INSTALL_DIR}/main.py#" \
  -e "s#User=taskbot#User=${SERVICE_USER}#" \
  -e "s#Group=taskbot#Group=${SERVICE_GROUP}#" \
  "${INSTALL_DIR}/deploy/systemd/${SERVICE_NAME}.service" > "/etc/systemd/system/${SERVICE_NAME}.service"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

echo "Installed and enabled ${SERVICE_NAME}.service."
echo "Start it with: sudo systemctl start ${SERVICE_NAME}"
echo "Check logs with: sudo journalctl -u ${SERVICE_NAME} -f"
