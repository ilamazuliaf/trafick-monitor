# MikroTik Traffic Monitor

A lightweight, configuration-driven web application to monitor interface traffic (RX/TX rates, real-time & historical graphs) on MikroTik RouterOS devices. Built specifically for low-resource Linux deployment (e.g. STB Ubuntu / Ubuntu Server).

---

## 🏗 Architecture & Configuration Principles

- **Configuration-Driven**: All application settings originate exclusively from `.env`.
- **Single Source of Truth**: Backend exposes configuration via `GET /api/config`. Frontend dynamically builds cards, dropdowns, and timers without hardcoded interfaces or graph periods.
- **Generic Duration Engine**: Generic `m`, `h`, `d` parser supports arbitrary time windows (e.g., `5m`, `15m`, `1h`, `2d`, `7d`).

---

## 🚀 Quick Start & Installation

### 1. Requirements
- Python 3.9+
- Linux (Ubuntu / STB Ubuntu recommended) or Windows

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the example environment file and configure your MikroTik router credentials and interface settings:

```bash
cp .env.example .env
nano .env
```

---

## ⚙️ Configuration (.env) Parameters

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MIKROTIK_HOST` | `192.168.1.1` | RouterOS IP address or hostname |
| `MIKROTIK_PORT` | `8728` | RouterOS API port (`8728` standard, `8729` for SSL) |
| `MIKROTIK_USERNAME` | `monitor` | API Username |
| `MIKROTIK_PASSWORD` | `password` | API Password |
| `MIKROTIK_USE_SSL` | `false` | Enable API-SSL connection |
| `MIKROTIK_VERIFY_SSL` | `false` | Verify SSL certificate validity |
| `MONITORED_INTERFACES` | `ether1-BAROKAH,ether2-BIZ,ether3-WAHED` | Comma-separated list of interface names to monitor |
| `POLL_INTERVAL` | `5` | MikroTik polling interval in seconds |
| `DATABASE_PATH` | `./data/traffic.db` | SQLite database file location |
| `WEB_HOST` | `0.0.0.0` | Web server bind IP |
| `WEB_PORT` | `8080` | Web server bind port |
| `GRAPH_PERIODS` | `5m,15m,30m,1h,12h,24h` | Time duration choices for frontend chart |
| `GRAPH_DEFAULT_PERIOD` | `15m` | Default selected period (must exist in `GRAPH_PERIODS`) |
| `GRAPH_REALTIME_MAX` | `30m` | Periods <= `GRAPH_REALTIME_MAX` are auto-refreshed in real-time |
| `GRAPH_REFRESH_INTERVAL` | `5000` | Real-time frontend refresh interval in milliseconds |
| `GRAPH_MAX_POINTS` | `500` | Maximum points returned after downsampling |
| `DATA_RETENTION` | `30d` | Historical data retention limit before cleanup |
| `TELEGRAM_ENABLED` | `true` | Enable Telegram Bot module |
| `TELEGRAM_BOT_TOKEN` | `YOUR_TELEGRAM_BOT_TOKEN` | Bot Father API Token |
| `TELEGRAM_ALLOWED_CHAT_IDS` | `123456789` | Comma-separated allowed Telegram Chat IDs |

---

## 🤖 Telegram PPPoE Offline Monitoring

Sistem terintegrasi dengan Telegram Bot untuk memantau pelanggan PPPoE yang offline dengan membandingkan database pelanggan lokal dengan sesi `/ppp/active/print` MikroTik RouterOS API.

### Command Telegram:
- `/start` - Menampilkan menu utama Telegram Bot.
- `/menu` - Menampilkan menu utama.
- `/pelanggan` - Menampilkan menu manajemen data pelanggan PPPoE.
- `/cek_off` - Memeriksa status koneksi pelanggan PPPoE yang sedang offline.

### Fitur Excel Pelanggan:
- **Download Template Excel**: Mengunduh format `.xlsx` standar.
- **Export Data Pelanggan**: Mengunduh seluruh data pelanggan dari SQLite ke `.xlsx`.
- **Import / Update Excel**: Mengunggah kembali file `.xlsx` untuk menambah/memperbarui data pelanggan.
- **Backup Otomatis**: Setiap import massal secara otomatis membuat backup database di `data/backups/`.


## 💻 Running the Application

### Development / Direct Run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
Open browser at `http://localhost:8080` or `http://<server-ip>:8080`.

### Running Automated Tests
```bash
pytest
```

---

## 🐧 Systemd Deployment (Ubuntu STB Server)

1. Copy application files to `/opt/mikrotik-traffic-monitor`:
   ```bash
   sudo mkdir -p /opt/mikrotik-traffic-monitor
   sudo cp -r . /opt/mikrotik-traffic-monitor/
   cd /opt/mikrotik-traffic-monitor
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. Install systemd service:
   ```bash
   sudo cp systemd/mikrotik-traffic-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable mikrotik-traffic-monitor
   sudo systemctl start mikrotik-traffic-monitor
   ```

3. Check service status & logs:
   ```bash
   sudo systemctl status mikrotik-traffic-monitor
   sudo journalctl -u mikrotik-traffic-monitor -f
   ```

---

## 🔧 Troubleshooting

### 1. Connection Failure (`mikrotik: false`)
- Verify MikroTik IP, API port (`8728`), and firewall rules.
- Ensure API service is enabled on MikroTik: `/ip service enable api`.

### 2. Authentication Failed
- Verify `MIKROTIK_USERNAME` and `MIKROTIK_PASSWORD` in `.env`.
- Ensure the user has `read` and `api` permissions in RouterOS (`/user group`).

### 3. Invalid Configuration Error on Startup
- Ensure `GRAPH_DEFAULT_PERIOD` is present inside `GRAPH_PERIODS`.
- Ensure all duration values match the format `^\d+(m|h|d)$` (e.g. `5m`, `1h`, `2d`).

### 4. Self-Signed Certificate Errors (API-SSL)
- If `MIKROTIK_USE_SSL=true` and using self-signed certificates, set `MIKROTIK_VERIFY_SSL=false` in `.env`.
